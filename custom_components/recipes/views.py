"""HTTP: the web app, the JSON API, media streaming and the share webhook."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_LANGUAGE,
    CONF_NOTIFY_SERVICE,
    CONF_STT_ENTITY,
    CONF_TODO_ENTITY,
    CONF_TRANSCRIBE,
    CONF_WEBHOOK_ID,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LANGUAGES,
    SIGNED_URL_HOURS,
    STATUS_ERROR,
    STATUS_READY,
    URL_API,
    URL_APP,
    VERSION,
)
from .pipeline import new_recipe_from_payload, save_import_image, save_upload

if TYPE_CHECKING:
    from . import RecipesData

_LOGGER = logging.getLogger(__name__)

FRONTEND = Path(__file__).parent / "frontend"
MEDIA_NAMES = re.compile(r"^(video\.mp4|poster\.jpg|image\.jpg|upload\.(jpg|jpeg|png|heic|webp|pdf))$")
MAX_UPLOAD = 40 * 1024 * 1024

SUMMARY_KEYS = (
    "id", "title", "status", "progress", "error", "created", "updated", "total_min",
    "prep_min", "cook_min", "tags", "favorite", "servings",
)


def _data(hass: HomeAssistant) -> RecipesData:
    return hass.data[DOMAIN]


def _media_url(hass: HomeAssistant, recipe_id: str, name: str | None) -> str | None:
    if not name:
        return None
    return async_sign_path(
        hass, f"{URL_API}/media/{recipe_id}/{name}", timedelta(hours=SIGNED_URL_HOURS)
    )


def serialize(hass: HomeAssistant, recipe: dict[str, Any], *, full: bool) -> dict[str, Any]:
    """Recipe as returned to the app (with signed media URLs)."""
    media = recipe.get("media") or {}
    rid = recipe["id"]
    image = media.get("image") or media.get("poster")
    out: dict[str, Any]
    if full:
        out = {k: v for k, v in recipe.items() if k not in ("input_text", "upload")}
        if recipe.get("status") == "error" and recipe.get("input_text"):
            out["original_text"] = recipe["input_text"][:5000]
    else:
        out = {k: recipe.get(k) for k in SUMMARY_KEYS}
        out["platform"] = (recipe.get("source") or {}).get("platform")
        out["has_video"] = bool(media.get("video"))
    out["image_url"] = _media_url(hass, rid, image)
    if full:
        out["poster_url"] = _media_url(hass, rid, media.get("poster") or media.get("image"))
        out["video_url"] = _media_url(hass, rid, media.get("video"))
    return out


def _sniff(head: bytes) -> str | None:
    """Detect common upload types from magic bytes."""
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG"):
        return ".png"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return ".heic"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp"
    return None


async def _read_payload(request: web.Request) -> tuple[dict[str, Any], tuple[str, bytes] | None]:
    """Read JSON, form or multipart bodies (Shortcuts can send all three)."""
    ctype = request.content_type or ""
    upload: tuple[str, bytes] | None = None
    payload: dict[str, Any] = {}
    if ctype.startswith("multipart/") or ctype == "application/x-www-form-urlencoded":
        form = await request.post()
        for key, value in form.items():
            if hasattr(value, "file"):
                content = value.file.read(MAX_UPLOAD + 1)
                if len(content) > MAX_UPLOAD:
                    raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=len(content))
                if content:
                    upload = (value.filename or "upload.jpg", content)
            elif isinstance(value, str) and value.strip():
                payload[key] = value.strip()
    elif ctype.startswith("image/") or ctype in ("application/pdf", "application/octet-stream") or (
        ctype not in ("application/json", "text/plain") and _sniff((await request.read())[:16])
    ):
        # Raw file body (iOS Shortcuts "File" request body)
        content = await request.read()
        if len(content) > MAX_UPLOAD:
            raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=len(content))
        ext = _sniff(content[:16]) or ".jpg"
        upload = (f"upload{ext}", content)
    elif ctype == "application/json" or (await request.text()).startswith("{"):
        try:
            payload = await request.json()
        except ValueError as err:
            raise web.HTTPBadRequest(text="Invalid JSON") from err
    else:
        body = (await request.text()).strip()
        if body:
            payload = {"text": body}
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Expected an object")
    return payload, upload


async def create_from_request(hass: HomeAssistant, request: web.Request) -> dict[str, Any]:
    """Shared by the API POST and the webhook."""
    data = _data(hass)
    payload, upload = await _read_payload(request)
    if not payload and not upload:
        raise web.HTTPBadRequest(text="Send a url, text, file or import")
    if upload and not (payload.get("url") or payload.get("text")):
        payload["force"] = True
    recipe, created = new_recipe_from_payload(hass, data.store, payload)
    if created:
        if upload:
            name = await save_upload(hass, data.store, recipe["id"], upload[0], upload[1])
            data.store.async_update(recipe["id"], {"upload": name, "source": recipe.get("source") or {"platform": "upload"}})
        imp = payload.get("import") or {}
        if imp.get("image_b64"):
            name = await save_import_image(hass, data.store, recipe["id"], imp["image_b64"])
            if name:
                data.store.async_update(recipe["id"], {"media": {"image": name}})
        data.processor.enqueue(recipe["id"])
    return {"id": recipe["id"], "created": created, "status": recipe.get("status"), "title": recipe.get("title")}


# ------------------------------------------------------------------ webhook


async def handle_webhook(hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
    """Webhook used by the iOS share-sheet shortcut and the Notes import."""
    try:
        result = await create_from_request(hass, request)
    except web.HTTPException as err:
        return web.json_response({"ok": False, "error": err.text}, status=err.status)
    if result["created"]:
        message = "Saving recipe…"
    else:
        message = f"Already saved: {result.get('title') or 'recipe'}"
    return web.json_response({"ok": True, "message": message, **result})


# ------------------------------------------------------------------ app shell


class AppIndexView(HomeAssistantView):
    """Serve the web app (no auth: it signs in with HA OAuth itself)."""

    url = URL_APP
    extra_urls = [f"{URL_APP}/"]
    name = "recipes:app"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return index.html."""
        hass: HomeAssistant = request.app["hass"]
        if request.path == URL_APP:
            raise web.HTTPFound(f"{URL_APP}/")
        html = await hass.async_add_executor_job((FRONTEND / "index.html").read_text)
        data = hass.data.get(DOMAIN)  # not there yet while HA is still starting
        html = html.replace("__VERSION__", data.asset_version if data else "starting")
        return web.Response(
            text=html, content_type="text/html",
            headers={"Cache-Control": "no-cache", "X-Frame-Options": "SAMEORIGIN"},
        )


class ServiceWorkerView(HomeAssistantView):
    """Service worker must live at the app scope."""

    url = f"{URL_APP}/sw.js"
    name = "recipes:sw"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return sw.js."""
        hass: HomeAssistant = request.app["hass"]
        js = await hass.async_add_executor_job((FRONTEND / "sw.js").read_text)
        data = hass.data.get(DOMAIN)
        if data is None:
            raise web.HTTPServiceUnavailable
        js = js.replace("__VERSION__", data.asset_version)
        return web.Response(
            text=js, content_type="application/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": f"{URL_APP}/"},
        )


class ManifestView(HomeAssistantView):
    """Web app manifest."""

    url = f"{URL_APP}/manifest.webmanifest"
    name = "recipes:manifest"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the manifest."""
        hass: HomeAssistant = request.app["hass"]
        text = await hass.async_add_executor_job((FRONTEND / "manifest.webmanifest").read_text)
        return web.Response(text=text, content_type="application/manifest+json")


# ------------------------------------------------------------------ API


class RecipesListView(HomeAssistantView):
    """List and create recipes."""

    url = URL_API
    name = "api:recipes"

    async def get(self, request: web.Request) -> web.Response:
        """List recipes, newest first."""
        hass: HomeAssistant = request.app["hass"]
        recipes = sorted(_data(hass).store.recipes.values(), key=lambda r: r.get("created") or "", reverse=True)
        return self.json({"recipes": [serialize(hass, r, full=False) for r in recipes], "version": VERSION})

    async def post(self, request: web.Request) -> web.Response:
        """Add a recipe from the app (url/text/file)."""
        hass: HomeAssistant = request.app["hass"]
        result = await create_from_request(hass, request)
        return self.json(result, HTTPStatus.CREATED if result["created"] else HTTPStatus.OK)


class RecipeView(HomeAssistantView):
    """Get, edit or delete one recipe."""

    url = URL_API + "/{recipe_id}"
    name = "api:recipes:recipe"

    async def get(self, request: web.Request, recipe_id: str) -> web.Response:
        """Return a full recipe."""
        hass: HomeAssistant = request.app["hass"]
        recipe = _data(hass).store.recipes.get(recipe_id)
        if recipe is None:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        return self.json(serialize(hass, recipe, full=True))

    async def patch(self, request: web.Request, recipe_id: str) -> web.Response:
        """Edit simple fields."""
        hass: HomeAssistant = request.app["hass"]
        store = _data(hass).store
        if recipe_id not in store.recipes:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        body = await request.json()
        allowed = {"favorite", "title", "my_notes", "tags", "servings", "last_cooked"}
        changes = {k: v for k, v in body.items() if k in allowed}
        recipe = store.async_update(recipe_id, changes)
        if "title" in changes:
            await store.async_rename_media(recipe_id)
        return self.json(serialize(hass, recipe, full=True))

    async def delete(self, request: web.Request, recipe_id: str) -> web.Response:
        """Delete a recipe and its media."""
        hass: HomeAssistant = request.app["hass"]
        await _data(hass).store.async_delete(recipe_id)
        return self.json({"ok": True})


class RecipeRetryView(HomeAssistantView):
    """Process a recipe again (e.g. after adding Instagram cookies)."""

    url = URL_API + "/{recipe_id}/retry"
    name = "api:recipes:retry"

    async def post(self, request: web.Request, recipe_id: str) -> web.Response:
        """Re-queue."""
        hass: HomeAssistant = request.app["hass"]
        data = _data(hass)
        if recipe_id not in data.store.recipes:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        data.processor.enqueue(recipe_id)
        return self.json({"ok": True})


class RecipeShoppingView(HomeAssistantView):
    """Add ingredients to a Home Assistant to-do list (e.g. the shopping list)."""

    url = URL_API + "/{recipe_id}/shopping"
    name = "api:recipes:shopping"

    async def post(self, request: web.Request, recipe_id: str) -> web.Response:
        """Body: {"items": ["200 g chicken", ...], "entity_id": optional}."""
        hass: HomeAssistant = request.app["hass"]
        data = _data(hass)
        if recipe_id not in data.store.recipes:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        body = await request.json()
        items = [str(i).strip() for i in body.get("items") or [] if str(i).strip()][:100]
        entity_id = body.get("entity_id") or data.processor.options.get(CONF_TODO_ENTITY) or (
            "todo.shopping_list" if hass.states.get("todo.shopping_list") else next(iter(hass.states.async_entity_ids("todo")), None)
        )
        if not entity_id or not items:
            return self.json_message("No to-do list or no items", HTTPStatus.BAD_REQUEST)
        try:
            for item in items:
                await hass.services.async_call(
                    "todo", "add_item", {"entity_id": entity_id, "item": item},
                    blocking=True, context=self.context(request),
                )
        except HomeAssistantError as err:
            return self.json_message(f"Could not add to {entity_id}: {err}", HTTPStatus.BAD_REQUEST)
        return self.json({"ok": True, "added": len(items), "entity_id": entity_id})


class RecipeMediaView(HomeAssistantView):
    """Stream media (supports Range requests for video)."""

    url = URL_API + "/media/{recipe_id}/{filename}"
    name = "api:recipes:media"

    async def get(self, request: web.Request, recipe_id: str, filename: str) -> web.StreamResponse:
        """Return a media file."""
        hass: HomeAssistant = request.app["hass"]
        store = _data(hass).store
        if recipe_id not in store.recipes or not MEDIA_NAMES.match(filename):
            raise web.HTTPNotFound
        path = store.media_dir(recipe_id) / filename
        if not await hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=604800"})


ENTITY_OPTIONS = {CONF_AI_TASK_ENTITY: "ai_task", CONF_STT_ENTITY: "stt", CONF_TODO_ENTITY: "todo"}


def _entity_choices(hass: HomeAssistant, domain: str) -> list[dict[str, str]]:
    return sorted(
        ({"id": state.entity_id, "name": state.name} for state in hass.states.async_all(domain)),
        key=lambda c: c["name"].lower(),
    )


def _notify_choices(hass: HomeAssistant) -> list[dict[str, str]]:
    """Notify entities plus the classic notify.* services (e.g. notify.mobile_app_...)."""
    choices = _entity_choices(hass, "notify")
    taken = {c["id"] for c in choices}
    for name in sorted(hass.services.async_services().get("notify", {})):
        service = f"notify.{name}"
        if name != "send_message" and service not in taken:
            choices.append({"id": service, "name": service})
    return choices


def _options_payload(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Current integration options and what can be picked for each."""
    return {
        "options": {
            CONF_AI_TASK_ENTITY: options.get(CONF_AI_TASK_ENTITY) or None,
            CONF_STT_ENTITY: options.get(CONF_STT_ENTITY) or None,
            CONF_LANGUAGE: options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            CONF_TRANSCRIBE: bool(options.get(CONF_TRANSCRIBE, True)),
            CONF_TODO_ENTITY: options.get(CONF_TODO_ENTITY) or None,
            CONF_NOTIFY_SERVICE: options.get(CONF_NOTIFY_SERVICE) or None,
        },
        "choices": {
            **{key: _entity_choices(hass, domain) for key, domain in ENTITY_OPTIONS.items()},
            CONF_NOTIFY_SERVICE: _notify_choices(hass),
            CONF_LANGUAGE: [{"id": k, "name": v} for k, v in LANGUAGES.items()],
        },
    }


def _validate_options(hass: HomeAssistant, current: dict[str, Any], changes: Any) -> dict[str, Any]:
    """Merge changed options into the current ones; ValueError when one is not valid."""
    if not isinstance(changes, dict):
        raise ValueError("Expected an object with options")
    options = dict(current)
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        if key in ENTITY_OPTIONS:
            domain = ENTITY_OPTIONS[key]
            if value and not (
                isinstance(value, str) and value.startswith(f"{domain}.") and hass.states.get(value)
            ):
                raise ValueError(f"Unknown {domain} entity: {value}")
        elif key == CONF_LANGUAGE:
            if value not in LANGUAGES:
                raise ValueError(f"Unknown language: {value}")
        elif key == CONF_TRANSCRIBE:
            if not isinstance(value, bool):
                raise ValueError("transcribe must be true or false")
        elif key == CONF_NOTIFY_SERVICE:
            if value and not (isinstance(value, str) and re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", value)):
                raise ValueError(f"Not a notify entity or service: {value}")
        else:
            raise ValueError(f"Unknown option: {key}")
        if value in (None, ""):
            options.pop(key, None)  # same as leaving the field empty in the options flow
        else:
            options[key] = value
    return options


class SettingsView(HomeAssistantView):
    """App info and admin settings (integration options, Instagram cookies)."""

    url = URL_API + "/settings"
    name = "api:recipes:settings"

    async def get(self, request: web.Request) -> web.Response:
        """Return status info for the settings sheet."""
        hass: HomeAssistant = request.app["hass"]
        data = _data(hass)
        from .video import ytdlp_version  # noqa: PLC0415

        cookies = await hass.async_add_executor_job(data.processor.cookie_file.exists)
        recipes = data.store.recipes.values()
        is_admin = request["hass_user"].is_admin
        return self.json(
            {
                "version": VERSION,
                "yt_dlp": await hass.async_add_executor_job(ytdlp_version),
                "instagram_cookies": cookies,
                "webhook_path": f"/api/webhook/{data.entry.data[CONF_WEBHOOK_ID]}",
                "count": len(data.store.recipes),
                "errors": sum(1 for r in recipes if r.get("status") == STATUS_ERROR),
                "ready": sum(1 for r in recipes if r.get("status") == STATUS_READY),
                "is_admin": is_admin,
                "todo_entity": data.processor.options.get(CONF_TODO_ENTITY)
                or ("todo.shopping_list" if hass.states.get("todo.shopping_list") else None),
                **(_options_payload(hass, dict(data.entry.options)) if is_admin else {}),
            }
        )

    async def post(self, request: web.Request) -> web.Response:
        """Admin only. Body: {"options": {...}} and/or {"instagram_cookies": "..."}.

        Options are the same keys as the Home Assistant options flow. Cookies
        are in Netscape cookies.txt format, a cookie header or a bare sessionid;
        an empty value removes them.
        """
        hass: HomeAssistant = request.app["hass"]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        data = _data(hass)
        body = await request.json()
        result: dict[str, Any] = {"ok": True}

        if "options" in body:
            try:
                options = _validate_options(hass, dict(data.entry.options), body["options"])
            except ValueError as err:
                return self.json_message(str(err), HTTPStatus.BAD_REQUEST)
            hass.config_entries.async_update_entry(data.entry, options=options)
            # The update listener does this too, but only after this request.
            data.processor.options = {**data.entry.data, **options}
            result.update(_options_payload(hass, options))

        if "instagram_cookies" in body:
            cookies = (body.get("instagram_cookies") or "").strip()
            path = data.processor.cookie_file
            if not cookies:
                await hass.async_add_executor_job(lambda: path.unlink(missing_ok=True))
                result["instagram_cookies"] = False
            else:
                text = cookies_to_netscape(cookies)
                if text is None:
                    return self.json_message(
                        "Could not read these cookies. Paste a cookies.txt export or the sessionid value.",
                        HTTPStatus.BAD_REQUEST,
                    )

                def write() -> None:
                    path.write_text(text)
                    path.chmod(0o600)

                await hass.async_add_executor_job(write)
                result["instagram_cookies"] = True
        return self.json(result)


# ------------------------------------------------------------------ developer view


class RecipeDebugView(HomeAssistantView):
    """What the pipeline saw and did for one recipe (admin only)."""

    url = URL_API + "/{recipe_id}/debug"
    name = "api:recipes:debug"

    async def get(self, request: web.Request, recipe_id: str) -> web.Response:
        """Return debug.json of the last processing run."""
        hass: HomeAssistant = request.app["hass"]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        data = _data(hass)
        recipe = data.store.recipes.get(recipe_id)
        if recipe is None:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        debug = await data.processor.read_debug(recipe_id)
        return self.json(
            {
                "available": debug is not None,
                "debug": debug or {},
                "folder": data.store.media_dir(recipe_id).name,
                "language": data.processor.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            }
        )


class RecipeDebugRerunView(HomeAssistantView):
    """Experiment: run only the AI step again on the cached material (admin only)."""

    url = URL_API + "/{recipe_id}/debug/rerun"
    name = "api:recipes:debug:rerun"

    async def post(self, request: web.Request, recipe_id: str) -> web.Response:
        """Body: {"instruction": optional extra instruction, "prompt": optional full prompt}.

        Returns the new result; nothing is saved until /debug/apply.
        """
        hass: HomeAssistant = request.app["hass"]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        data = _data(hass)
        if recipe_id not in data.store.recipes:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        body = await request.json()
        try:
            result = await data.processor.rerun_ai(
                recipe_id,
                instruction=str(body.get("instruction") or "").strip() or None,
                prompt=str(body.get("prompt") or "").strip() or None,
            )
        except (ValueError, HomeAssistantError) as err:
            return self.json_message(f"AI re-run failed: {err}", HTTPStatus.BAD_REQUEST)
        return self.json(result)


class RecipeDebugApplyView(HomeAssistantView):
    """Save the result of the last AI re-run as the recipe (admin only)."""

    url = URL_API + "/{recipe_id}/debug/apply"
    name = "api:recipes:debug:apply"

    async def post(self, request: web.Request, recipe_id: str) -> web.Response:
        """Apply the pending experiment."""
        hass: HomeAssistant = request.app["hass"]
        if not request["hass_user"].is_admin:
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        data = _data(hass)
        if recipe_id not in data.store.recipes:
            return self.json_message("Not found", HTTPStatus.NOT_FOUND)
        try:
            await data.processor.apply_experiment(recipe_id)
        except ValueError as err:
            return self.json_message(str(err), HTTPStatus.BAD_REQUEST)
        return self.json(serialize(hass, data.store.recipes[recipe_id], full=True))


def cookies_to_netscape(raw: str) -> str | None:
    """Accept a cookies.txt export, a 'name=value; name2=value2' header, or a bare sessionid."""
    if "\t" in raw and ".instagram.com" in raw:
        text = raw if raw.startswith("# Netscape") else "# Netscape HTTP Cookie File\n" + raw
        return text if text.endswith("\n") else text + "\n"
    pairs: list[tuple[str, str]] = []
    if "=" in raw:
        for part in raw.replace("\n", ";").split(";"):
            if "=" in part:
                name, _, value = part.strip().partition("=")
                if name and value:
                    pairs.append((name.strip(), value.strip()))
    elif len(raw) >= 20 and re.fullmatch(r"[A-Za-z0-9%:_\-]+", raw):
        pairs.append(("sessionid", raw))
    if not any(name == "sessionid" for name, _ in pairs):
        return None
    lines = ["# Netscape HTTP Cookie File"]
    for name, value in pairs:
        lines.append(f".instagram.com\tTRUE\t/\tTRUE\t2147483647\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def register_views(hass: HomeAssistant) -> None:
    """Register all HTTP views."""
    for view in (
        AppIndexView, ServiceWorkerView, ManifestView, RecipesListView, SettingsView,
        RecipeView, RecipeRetryView, RecipeShoppingView, RecipeMediaView,
        RecipeDebugView, RecipeDebugRerunView, RecipeDebugApplyView,
    ):
        hass.http.register_view(view())
