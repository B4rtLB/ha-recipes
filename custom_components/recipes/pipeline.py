"""The processing pipeline: source -> media + AI extraction -> stored recipe."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
import logging
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import ai, sources, video
from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_LANGUAGE,
    CONF_NOTIFY_SERVICE,
    CONF_STT_ENTITY,
    CONF_TRANSCRIBE,
    DEFAULT_LANGUAGE,
    MAX_TRANSCRIBE_SECONDS,
    STATUS_ERROR,
    STATUS_PROCESSING,
    STATUS_QUEUED,
    STATUS_READY,
)
from .store import RecipeStore, normalize_url

_LOGGER = logging.getLogger(__name__)

IMAGE_MAX = 15 * 1024 * 1024
CAPTION_IS_ENOUGH = 350  # characters; shorter captions get a transcript as well


class RecipeProcessor:
    """Queue that processes one recipe at a time (the HA host is a laptop)."""

    def __init__(self, hass: HomeAssistant, store: RecipeStore, options: dict[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self.store = store
        self.options = options
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self.cookie_file: Path = Path(hass.config.path(".storage", "recipes_instagram_cookies.txt"))

    @property
    def session(self) -> aiohttp.ClientSession:
        """Shared aiohttp session."""
        return async_get_clientsession(self.hass)

    def start(self) -> None:
        """Start the worker and re-queue unfinished work."""
        self._worker = self.hass.async_create_background_task(self._run(), "recipes worker")
        for recipe in self.store.recipes.values():
            if recipe.get("status") in (STATUS_QUEUED, STATUS_PROCESSING):
                self._queue.put_nowait(recipe["id"])

    async def stop(self) -> None:
        """Stop the worker."""
        if self._worker:
            self._worker.cancel()

    def enqueue(self, recipe_id: str) -> None:
        """Add a recipe to the processing queue."""
        self.store.async_update(recipe_id, {"status": STATUS_QUEUED, "error": None})
        self._queue.put_nowait(recipe_id)

    async def _run(self) -> None:
        while True:
            recipe_id = await self._queue.get()
            if recipe_id not in self.store.recipes:
                continue
            try:
                await self.process(recipe_id)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # keep the worker alive whatever happens
                _LOGGER.exception("Processing recipe %s failed", recipe_id)
                if recipe_id in self.store.recipes:
                    self.store.async_update(
                        recipe_id, {"status": STATUS_ERROR, "error": str(err) or type(err).__name__}
                    )
                    await self._notify(recipe_id, failed=True)

    # ------------------------------------------------------------------ steps

    def _set(self, recipe_id: str, **changes: Any) -> None:
        self.store.async_update(recipe_id, changes)

    async def process(self, recipe_id: str) -> None:
        """Process a single recipe end to end."""
        recipe = self.store.recipes[recipe_id]
        folder = self.store.media_dir(recipe_id)
        await self.hass.async_add_executor_job(lambda: folder.mkdir(parents=True, exist_ok=True))
        self._set(recipe_id, status=STATUS_PROCESSING, progress="Reading source")

        source = recipe.get("source") or {}
        url: str | None = source.get("url")
        platform = source.get("platform") or (
            sources.detect_platform(url) if url else ("notes" if recipe.get("imported_from") else "text" if recipe.get("input_text") else "upload")
        )
        material: list[str] = []
        attachments: list[Path] = []
        media: dict[str, Any] = dict(recipe.get("media") or {})
        notes: list[str] = []

        # 1. Imported text (Apple Notes import / shared text) --------------------
        if recipe.get("input_text"):
            material.append("RECIPE TEXT:\n" + recipe["input_text"])

        # 2. Uploaded file (image / PDF from the share sheet) ---------------------
        upload = recipe.get("upload")
        if upload:
            path = folder / upload
            if path.exists():
                if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".webp"):
                    # Normalize to JPEG: the AI and Safari both handle that best.
                    ok = await self.hass.async_add_executor_job(
                        lambda: video.save_image(path.read_bytes(), folder / "image.jpg")
                    )
                    if ok:
                        media["image"] = "image.jpg"
                        attachments.append(folder / "image.jpg")
                    else:
                        attachments.append(path)
                else:
                    attachments.append(path)

        # 3. Social video --------------------------------------------------------
        if url and platform in ("tiktok", "instagram", "youtube"):
            self._set(recipe_id, progress="Downloading video")
            social = await self._social(url, platform, folder, media, notes)
            if social.get("canonical_url"):
                source["url_canonical"] = social["canonical_url"]
            if social.get("author"):
                source["author"] = social["author"]
            if social.get("text") and not recipe.get("input_text"):
                material.append("SOCIAL MEDIA CAPTION:\n" + social["text"])
            caption_len = len(social.get("text") or "")
            if (
                media.get("video")
                and self.options.get(CONF_TRANSCRIBE, True)
                and not recipe.get("input_text")
                and (caption_len < CAPTION_IS_ENOUGH or not _looks_like_recipe(social.get("text", "")))
            ):
                self._set(recipe_id, progress="Listening to video")
                transcript = await self._transcribe(folder / media["video"], social.get("text", ""))
                if transcript:
                    material.append("SPEECH TRANSCRIPT OF THE VIDEO:\n" + transcript)
                    notes.append("transcribed")

        # 4. Regular web page ----------------------------------------------------
        elif url and not recipe.get("input_text"):
            self._set(recipe_id, progress="Reading web page")
            web = await sources.fetch_web(self.session, url)
            material.append(web.text)
            source["url_canonical"] = web.canonical_url
            if web.image_url and not media.get("image"):
                await self._save_remote_image(web.image_url, folder, media, referer=url)

        if url and recipe.get("input_text") and platform in ("web",) and not media.get("image"):
            # Imported note with a web link: grab the page photo if we have none.
            try:
                web = await sources.fetch_web(self.session, url)
                if web.image_url:
                    await self._save_remote_image(web.image_url, folder, media, referer=url)
            except (aiohttp.ClientError, TimeoutError):
                pass

        if not material and not attachments:
            raise ValueError("Nothing found to read a recipe from (empty caption and no video audio)")

        # 5. AI extraction -------------------------------------------------------
        self._set(recipe_id, progress="Writing recipe", media=media, source={**source, "platform": platform})
        entity_id = self.options.get(CONF_AI_TASK_ENTITY) or ai.default_ai_task_entity(self.hass)
        if not entity_id:
            raise ValueError("No AI Task entity configured (Settings → Recipes → Configure)")
        prompt = ai.build_prompt("\n\n".join(material) or "(see attachment)", self.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE))
        text = await ai.run_ai_task(self.hass, entity_id, prompt, attachments)
        try:
            data = ai.parse_json(text)
        except ValueError:
            _LOGGER.debug("Unparseable AI output: %s", text[:2000])
            text = await ai.run_ai_task(
                self.hass, entity_id, prompt + "\n\nReturn ONLY valid JSON this time.", attachments
            )
            data = ai.parse_json(text)

        if data.get("recipe_found") is False:
            self._set(
                recipe_id,
                status=STATUS_ERROR,
                title=recipe.get("title") or data.get("title") or "No recipe found",
                error="No recipe found in this post. Is the recipe in the comments or behind a link in bio?",
                media=media,
                progress=None,
            )
            await self._notify(recipe_id, failed=True)
            return

        fields = ai.normalize(data)
        if not media.get("image") and media.get("poster"):
            media["image"] = media["poster"]
        self._set(
            recipe_id,
            **fields,
            media=media,
            source={**source, "platform": platform},
            status=STATUS_READY,
            progress=None,
            error=None,
            pipeline_notes=notes,
        )
        await self._notify(recipe_id)

    async def _social(
        self, url: str, platform: str, folder: Path, media: dict[str, Any], notes: list[str]
    ) -> dict[str, Any]:
        """Download the video and caption of a TikTok/Instagram/YouTube post."""
        result: dict[str, Any] = {}
        info = None
        # 1) without login, 2) with Instagram cookies if the user saved them
        attempts: list[Path | None] = [None]
        if platform == "instagram" and await self.hass.async_add_executor_job(self.cookie_file.exists):
            attempts.append(self.cookie_file)
        for cookie in attempts:
            try:
                info = await self.hass.async_add_executor_job(video.download_video, url, folder, cookie)
                if cookie:
                    notes.append("used instagram cookies")
                break
            except video.VideoError as err:
                _LOGGER.info("yt-dlp could not get %s (cookies=%s): %s", url, bool(cookie), err)
                notes.append(f"yt-dlp{' +cookies' if cookie else ''}: {str(err)[:200]}")

        if info:
            result["text"] = info.get("description") or ""
            result["author"] = info.get("uploader")
            result["canonical_url"] = info.get("webpage_url")
            if info.get("path"):
                media.update(
                    video="video.mp4",
                    width=info.get("width"),
                    height=info.get("height"),
                    duration=info.get("duration"),
                    has_audio=info.get("has_audio", True),
                )
            if info.get("thumbnail"):
                await self._save_remote_image(info["thumbnail"], folder, media, key="poster", referer=url)

        if platform == "instagram" and self.options.get("instagram_embed_fallback") and (
            not info or not info.get("path") or not result.get("text")
        ):
            # The public embed page used to carry caption + video_url; Instagram now renders
            # it client-side, so this is off by default and kept for if that changes back.
            embed = await sources.fetch_instagram_embed(self.session, url)
            if embed:
                notes.append("instagram embed fallback")
                result.setdefault("canonical_url", embed.canonical_url)
                if embed.text and not result.get("text"):
                    result["text"] = embed.text
                if embed.author and not result.get("author"):
                    result["author"] = embed.author
                if embed.video_url and not media.get("video"):
                    try:
                        data, _ = await sources.download_file(
                            self.session, embed.video_url, 400 * 1024 * 1024, referer="https://www.instagram.com/"
                        )
                        raw = folder / "download.mp4"
                        await self.hass.async_add_executor_job(video.write_bytes, raw, data)
                        await self.hass.async_add_executor_job(video.make_ios_friendly, raw, folder / "video.mp4")
                        probe = await self.hass.async_add_executor_job(video.probe, folder / "video.mp4")
                        media.update(video="video.mp4", **{k: probe.get(k) for k in ("width", "height", "duration")})
                    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                        notes.append(f"embed video failed: {err}")
                if embed.image_url and not media.get("poster"):
                    await self._save_remote_image(embed.image_url, folder, media, key="poster")

        if not result.get("text") or not (media.get("video") or media.get("poster")):
            meta = await sources.fetch_social_meta(self.session, url)
            if meta:
                notes.append("og-meta fallback")
                if meta.text and not result.get("text"):
                    result["text"] = meta.text
                if meta.image_url and not media.get("poster"):
                    await self._save_remote_image(meta.image_url, folder, media, key="poster")

        if media.get("video") and not media.get("poster"):
            ok = await self.hass.async_add_executor_job(
                video.poster_from_video, folder / "video.mp4", folder / "poster.jpg"
            )
            if ok:
                media["poster"] = "poster.jpg"
        return result

    async def _save_remote_image(
        self, url: str, folder: Path, media: dict[str, Any], *, key: str = "image", referer: str | None = None
    ) -> None:
        try:
            data, _ = await sources.download_file(self.session, url, IMAGE_MAX, referer=referer)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Image download failed %s: %s", url, err)
            return
        name = f"{key}.jpg"
        if await self.hass.async_add_executor_job(video.save_image, data, folder / name):
            media[key] = name

    async def _transcribe(self, video_path: Path, caption: str) -> str | None:
        """Speech-to-text of the video's audio via the configured STT entity."""
        from homeassistant.components import stt  # noqa: PLC0415

        entity_id = self.options.get(CONF_STT_ENTITY)
        if not entity_id:
            ids = [e for e in self.hass.states.async_entity_ids("stt") if "openai" in e] or list(
                self.hass.states.async_entity_ids("stt")
            )
            entity_id = ids[0] if ids else None
        if not entity_id:
            return None
        engine = stt.async_get_speech_to_text_entity(self.hass, entity_id)
        if engine is None:
            return None
        audio = video_path.with_name("audio.ogg")
        ok = await self.hass.async_add_executor_job(
            video.extract_audio, video_path, audio, MAX_TRANSCRIBE_SECONDS
        )
        if not ok:
            return None
        data = await self.hass.async_add_executor_job(audio.read_bytes)
        await self.hass.async_add_executor_job(audio.unlink)

        language = ai.guess_language(caption)
        supported = engine.supported_languages
        if supported and language not in supported:
            language = next((lang for lang in supported if lang.startswith(language)), supported[0])
        metadata = stt.SpeechMetadata(
            language=language,
            format=stt.AudioFormats.OGG,
            codec=stt.AudioCodecs.OPUS,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )

        async def stream() -> AsyncIterator[bytes]:
            yield data

        try:
            result = await engine.internal_async_process_audio_stream(metadata, stream())
        except Exception as err:  # STT providers raise a variety of errors
            _LOGGER.info("Transcription failed: %s", err)
            return None
        if result.result == stt.SpeechResultState.SUCCESS and result.text:
            return result.text
        return None

    async def _notify(self, recipe_id: str, failed: bool = False) -> None:
        service = (self.options.get(CONF_NOTIFY_SERVICE) or "").strip()
        recipe = self.store.recipes.get(recipe_id) or {}
        if not service or recipe.get("imported_from"):
            return  # no notification storm during a bulk import
        domain, _, name = service.partition(".")
        if not name:
            domain, name = "notify", domain
        title = recipe.get("title") or "Recipe"
        message = (
            f"Couldn't save: {recipe.get('error')}" if failed else "Saved to your recipes."
        )
        try:
            if self.hass.states.get(service) is not None:
                # notify entity (e.g. notify.barts_iphone)
                await self.hass.services.async_call(
                    "notify", "send_message", {"entity_id": service, "title": title, "message": message}, blocking=False
                )
                return
            await self.hass.services.async_call(
                domain, name, {"title": title, "message": message, "data": {"tag": f"recipe-{recipe_id}"}}, blocking=False
            )
        except Exception as err:  # never fail a recipe on a notification
            _LOGGER.debug("Notification failed: %s", err)


def _looks_like_recipe(text: str) -> bool:
    """Does a caption already contain amounts? (then a transcript adds little)."""
    import re  # noqa: PLC0415

    amounts = re.findall(
        r"\b\d+(?:[.,/]\d+)?\s*(?:g|kg|ml|l|tbsp|tsp|el|tl|cups?|oz|lbs?|gram|grams|cloves?|teen|tenen)\b",
        text,
        re.IGNORECASE,
    )
    return len(amounts) >= 3


def new_recipe_from_payload(
    hass: HomeAssistant, store: RecipeStore, payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Create a recipe record from a webhook/API payload.

    Returns (recipe, created). Existing URLs are not duplicated unless force=True.
    """
    url = payload.get("url") or sources.first_url(payload.get("text") or "")
    text = payload.get("text") or ""
    if url and text.strip() == url:
        text = ""
    imp_in = payload.get("import") or {}
    if not payload.get("force"):
        existing = None
        if url:
            existing = store.find_by_url(url)
        elif imp_in.get("source_url"):
            existing = store.find_by_url(imp_in["source_url"])
        elif imp_in.get("title"):
            existing = next(
                (r for r in store.recipes.values()
                 if r.get("imported_from") == "apple_notes" and r.get("import_title") == imp_in["title"]),
                None,
            )
        if existing:
            return existing, False

    data: dict[str, Any] = {"status": STATUS_QUEUED}
    if url:
        data["source"] = {"url": url, "platform": sources.detect_platform(url)}
    if payload.get("import"):
        imp = payload["import"]
        data["input_text"] = imp.get("text")
        data["title"] = imp.get("title")
        data["imported_from"] = "apple_notes"
        data["import_title"] = imp.get("title")
        if imp.get("created"):
            data["created"] = imp["created"]
        if imp.get("source_url"):
            data["source"] = {"url": imp["source_url"], "platform": sources.detect_platform(imp["source_url"])}
    elif text and len(text) > 40 and (not url or len(text) > len(url) + 40):
        # Shared text that contains a recipe (e.g. copied from somewhere)
        data["input_text"] = text
    recipe = store.async_create(data)
    return recipe, True


async def save_upload(
    hass: HomeAssistant, store: RecipeStore, recipe_id: str, filename: str, content: bytes
) -> str:
    """Store an uploaded file in the recipe's folder, return its name."""
    suffix = Path(filename or "upload.jpg").suffix.lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".heic", ".webp", ".pdf"):
        suffix = ".jpg"
    name = f"upload{suffix}"
    await hass.async_add_executor_job(video.write_bytes, store.media_dir(recipe_id) / name, content)
    return name


async def save_import_image(hass: HomeAssistant, store: RecipeStore, recipe_id: str, b64: str) -> str | None:
    """Store an imported (base64) image as the recipe photo."""
    try:
        raw = base64.b64decode(b64)
    except ValueError:
        return None
    folder = store.media_dir(recipe_id)
    ok = await hass.async_add_executor_job(video.save_image, raw, folder / "image.jpg")
    return "image.jpg" if ok else None


__all__ = ["RecipeProcessor", "new_recipe_from_payload", "normalize_url", "save_upload"]
