"""Fetching and parsing of recipe sources (web pages, Instagram fallbacks)."""

from __future__ import annotations

from dataclasses import dataclass, field
import html as html_lib
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp

from .const import DESKTOP_USER_AGENT, USER_AGENT

_LOGGER = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def detect_platform(url: str) -> str:
    """Return tiktok, instagram, youtube or web."""
    host = urlsplit(url).netloc.lower()
    if "tiktok.com" in host:
        return "tiktok"
    if "instagram.com" in host or host.endswith("instagr.am"):
        return "instagram"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    return "web"


def first_url(text: str) -> str | None:
    """Find the first URL in a block of shared text."""
    match = URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,;!?]")


ASSET_EXT = (
    ".js", ".mjs", ".css", ".map", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".ico", ".woff", ".woff2", ".ttf", ".otf", ".wasm", ".xml",
)
ASSET_HOSTS = (
    "tiktokcdn", "ttwstatic", "byteimg", "ibytedtos", "byteoversea", "tiktokv.", "fbcdn.net",
    "cdninstagram.com", "akamaized.net", "fonts.googleapis.com", "fonts.gstatic.com",
    "googletagmanager.com", "google-analytics.com", "doubleclick.net", "ytimg.com", "ggpht.com",
)


def is_asset_url(url: str) -> bool:
    """A script/style/image/CDN link that can never be the recipe itself.

    Some apps share a whole web page with the share sheet; "Get URLs from Input"
    then also returns the page's script and image links.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return True
    host, path = parts.netloc.lower(), parts.path.lower()
    if not host:
        return True
    return path.endswith(ASSET_EXT) or any(h in host for h in ASSET_HOSTS)


def is_post_url(url: str) -> bool:
    """A link to a single TikTok / Instagram / YouTube post."""
    parts = urlsplit(url)
    host, path = parts.netloc.lower(), parts.path.lower()
    if host.endswith("tiktok.com"):
        return host.split(".")[0] in ("vm", "vt") or "/video/" in path or "/photo/" in path or path.startswith("/t/")
    if "instagram.com" in host:
        return any(f"/{k}/" in path for k in ("p", "reel", "reels", "tv"))
    if "youtu.be" in host:
        return len(path) > 1
    if "youtube.com" in host:
        return path.startswith(("/shorts/", "/watch"))
    return False


def best_url(*texts: str | None) -> str | None:
    """Pick the recipe link out of everything that was shared.

    Script/image/CDN links are skipped; a TikTok/Instagram/YouTube post wins
    over other links, otherwise the first remaining link is used.
    """
    found = all_urls(*texts)
    posts = [u for u in found if is_post_url(u)]
    if posts:
        return posts[0]
    return found[0] if found else None


def all_urls(*texts: str | None) -> list[str]:
    """Every non-asset link in the texts, in order (handles links inside shared HTML/JSON)."""
    found: list[str] = []
    for text in texts:
        text = (text or "").replace("\\u002F", "/").replace("\\u002f", "/").replace("\\/", "/")
        text = html_lib.unescape(text)
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(").,;!?]")
            if url not in found and not is_asset_url(url):
                found.append(url)
    return found


@dataclass
class SourceContent:
    """What we found at the source, ready for the AI step."""

    text: str = ""
    image_url: str | None = None
    video_url: str | None = None
    title: str | None = None
    author: str | None = None
    canonical_url: str | None = None
    jsonld: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


async def fetch_html(
    session: aiohttp.ClientSession, url: str, *, desktop: bool = False
) -> tuple[str, str]:
    """Fetch a page, return (final_url, html)."""
    headers = {
        "User-Agent": DESKTOP_USER_AGENT if desktop else USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
    }
    async with session.get(
        url, headers=headers, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True
    ) as resp:
        resp.raise_for_status()
        raw = await resp.read()
        charset = resp.charset or "utf-8"
        return str(resp.url), raw.decode(charset, errors="replace")


# ---------------------------------------------------------------- JSON-LD


def _iter_jsonld(html: str):
    for match in re.finditer(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        raw = match.group(1).strip()
        try:
            yield json.loads(raw)
        except ValueError:
            # Some sites put invalid control characters in JSON-LD.
            try:
                yield json.loads(re.sub(r"[\x00-\x1f]", " ", raw))
            except ValueError:
                continue


def _walk(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def _is_recipe(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    if isinstance(kind, list):
        return any(str(k).lower() == "recipe" for k in kind)
    return str(kind).lower() == "recipe"


def find_jsonld_recipe(html: str) -> dict[str, Any] | None:
    """Return the schema.org Recipe object from a page, if any."""
    for doc in _iter_jsonld(html):
        for node in _walk(doc):
            if _is_recipe(node):
                return node
    return None


def jsonld_image(recipe: dict[str, Any]) -> str | None:
    """Pick the best image URL from a JSON-LD recipe."""
    image = recipe.get("image")
    candidates: list[str] = []
    for item in image if isinstance(image, list) else [image]:
        if isinstance(item, str):
            candidates.append(item)
        elif isinstance(item, dict) and item.get("url"):
            candidates.append(item["url"])
    return candidates[-1] if candidates else None  # last is usually largest


_JSONLD_KEEP = (
    "name", "description", "recipeYield", "prepTime", "cookTime", "totalTime",
    "recipeIngredient", "recipeInstructions", "recipeCategory", "recipeCuisine",
    "keywords", "author",
)


def slim_jsonld(recipe: dict[str, Any]) -> dict[str, Any]:
    """The keys of a JSON-LD recipe that matter for reading it."""
    return {k: v for k, v in recipe.items() if k in _JSONLD_KEEP}


def compact_jsonld(recipe: dict[str, Any]) -> str:
    """Strip noisy keys from a JSON-LD recipe for the AI prompt."""
    return json.dumps(slim_jsonld(recipe), ensure_ascii=False)[:30000]


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def iso_minutes(value: Any) -> int | None:
    """ISO 8601 duration ("PT1H15M") in minutes."""
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", str(value or "").strip(), re.IGNORECASE
    )
    if not match:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    total = days * 1440 + hours * 60 + minutes + (1 if seconds >= 30 else 0)
    return total or None


def _instruction_steps(node: Any) -> list[str]:
    """Flatten recipeInstructions (text, HowToStep, HowToSection) into step strings."""
    if isinstance(node, str):
        parts = [p for p in re.split(r"\n+|\r+", node) if p.strip()]
        return [_clean(p) for p in parts if _clean(p)]
    if isinstance(node, list):
        return [step for item in node for step in _instruction_steps(item)]
    if isinstance(node, dict):
        if node.get("itemListElement"):
            return _instruction_steps(node["itemListElement"])
        return _instruction_steps(node.get("text") or node.get("name") or "")
    return []


def jsonld_to_data(recipe: dict[str, Any]) -> dict[str, Any] | None:
    """Build the lean AI output from a schema.org Recipe, without any AI.

    None when the JSON-LD has no usable ingredients and steps. Title, times, servings,
    ingredient lines and steps come from the page; tags and (if missing) the description
    are left to a very small AI call.
    """
    ingredients = recipe.get("recipeIngredient")
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    lines = [_clean(i) for i in ingredients or [] if _clean(i)]
    steps = _instruction_steps(recipe.get("recipeInstructions"))
    if len(lines) < 2 or not steps:
        return None
    servings_text = recipe.get("recipeYield")
    if isinstance(servings_text, list):
        servings_text = next((s for s in servings_text if s), None)
    servings_text = _clean(servings_text) or None
    servings = re.search(r"\d+", servings_text or "")
    hints = []
    for key in ("recipeCategory", "recipeCuisine", "keywords"):
        value = recipe.get(key)
        hints += [_clean(v) for v in (value if isinstance(value, list) else [value]) if _clean(v)]
    prep, cook, total = (iso_minutes(recipe.get(k)) for k in ("prepTime", "cookTime", "totalTime"))
    return {
        "recipe_found": True,
        "title": _clean(recipe.get("name")) or "Untitled recipe",
        "description": _clean(recipe.get("description")) or None,
        "servings": int(servings.group(0)) if servings else None,
        "servings_text": servings_text,
        "prep_min": prep,
        "cook_min": cook,
        "total_min": total,
        "estimated": False,
        "ingredient_groups": [{"name": None, "items": lines}],
        "steps": steps,
        "tags": [],
        "source_notes": None,
        "_hints": ", ".join(hints)[:300],
    }


# ---------------------------------------------------------------- meta tags


def meta_content(html: str, *names: str) -> str | None:
    """Return the content of the first matching <meta property/name>."""
    for name in names:
        for pattern in (
            rf"<meta[^>]+(?:property|name)=[\"']{re.escape(name)}[\"'][^>]*content=[\"']([^\"']*)[\"']",
            rf"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]*(?:property|name)=[\"']{re.escape(name)}[\"']",
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return html_lib.unescape(match.group(1)).strip()
    return None


def html_to_text(html: str, limit: int = 30000) -> str:
    """Very small readability: drop scripts/nav and keep visible text."""
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form|iframe)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", body)
    body = re.sub(r"(?i)<li[^>]*>", "\n- ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html_lib.unescape(body)
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in body.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:limit]


async def fetch_web(session: aiohttp.ClientSession, url: str) -> SourceContent:
    """Fetch a regular recipe web page."""
    final_url, html = await fetch_html(session, url)
    content = SourceContent(canonical_url=final_url)
    recipe = find_jsonld_recipe(html)
    if recipe is None:
        # Some sites only render JSON-LD for desktop user agents.
        try:
            _, desktop_html = await fetch_html(session, url, desktop=True)
            recipe = find_jsonld_recipe(desktop_html)
            if recipe is not None:
                html = desktop_html
        except aiohttp.ClientError:
            pass
    content.title = meta_content(html, "og:title", "twitter:title")
    content.image_url = meta_content(html, "og:image", "twitter:image")
    if recipe is not None:
        content.jsonld = recipe
        content.text = "SCHEMA.ORG RECIPE (JSON-LD):\n" + compact_jsonld(recipe)
        content.image_url = jsonld_image(recipe) or content.image_url
        content.title = recipe.get("name") or content.title
    else:
        content.text = "WEB PAGE TEXT:\n" + (f"Title: {content.title}\n" if content.title else "") + html_to_text(html)
    if content.image_url:
        content.image_url = urljoin(final_url, content.image_url)
    return content


# ---------------------------------------------------------------- Instagram


def instagram_shortcode(url: str) -> str | None:
    """Extract the post/reel shortcode from an Instagram URL."""
    match = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


def _json_unescape(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except ValueError:
        return value.replace("\\/", "/").replace("\\u0026", "&")


async def fetch_instagram_embed(
    session: aiohttp.ClientSession, url: str
) -> SourceContent | None:
    """Fallback without login: the public embed page.

    The embed page usually contains the caption, a cover image and for many
    reels also a direct ``video_url``.
    """
    code = instagram_shortcode(url)
    if not code:
        return None
    embed_url = f"https://www.instagram.com/p/{code}/embed/captioned/"
    try:
        _, html = await fetch_html(session, embed_url, desktop=True)
    except aiohttp.ClientError as err:
        _LOGGER.debug("Instagram embed fetch failed: %s", err)
        return None
    content = SourceContent(canonical_url=f"https://www.instagram.com/p/{code}/")

    # Caption block in the server-rendered HTML.
    cap = re.search(r'<div class="Caption"[^>]*>(.*?)<div class="CaptionComments"', html, re.DOTALL)
    if cap:
        caption = re.sub(r"<br\s*/?>", "\n", cap.group(1))
        caption = re.sub(r"<a[^>]*class=\"CaptionUsername\"[^>]*>.*?</a>", "", caption, flags=re.DOTALL)
        caption = html_lib.unescape(re.sub(r"<[^>]+>", "", caption)).strip()
        content.text = caption
    user = re.search(r'class="UsernameText"[^>]*>([^<]+)<', html)
    if user:
        content.author = html_lib.unescape(user.group(1)).strip()

    # Data embedded as escaped JSON (contextJSON / gql_data).
    video = re.search(r'\\?"video_url\\?"\s*:\s*\\?"(.*?)\\?"', html)
    if video:
        content.video_url = _json_unescape(video.group(1).replace('\\\\', '\\'))
    if not content.text:
        text = re.search(r'\\?"edge_media_to_caption\\?".*?\\?"text\\?"\s*:\s*\\?"(.*?)\\?"\}', html, re.DOTALL)
        if text:
            content.text = _json_unescape(text.group(1).replace('\\\\', '\\'))
    img = re.search(r'<img[^>]+class="EmbeddedMediaImage"[^>]+src="([^"]+)"', html)
    if img:
        content.image_url = html_lib.unescape(img.group(1))
    else:
        disp = re.search(r'\\?"display_url\\?"\s*:\s*\\?"(.*?)\\?"', html)
        if disp:
            content.image_url = _json_unescape(disp.group(1).replace('\\\\', '\\'))
    if not (content.text or content.video_url or content.image_url):
        return None
    return content


async def fetch_social_meta(session: aiohttp.ClientSession, url: str) -> SourceContent | None:
    """Last resort: og:description / og:image like the old shortcut did."""
    try:
        final_url, html = await fetch_html(session, url)
    except aiohttp.ClientError:
        return None
    content = SourceContent(canonical_url=final_url)
    content.text = meta_content(html, "og:description", "description") or ""
    content.image_url = meta_content(html, "og:image", "twitter:image")
    content.title = meta_content(html, "og:title")
    # Instagram: '304 likes, 24 comments - user on October 2, 2026: "CAPTION"'
    ig = re.match(r'^[\d.,KkMm]+ likes?, [\d.,KkMm]+ comments? - ([\w.]+) on [^:]+:\s*["“](.*)["”]\.?\s*$',
                  content.text, re.DOTALL)
    if ig:
        content.author = ig.group(1)
        content.text = ig.group(2).strip()
    # TikTok web pages embed the full description as JSON.
    desc = re.search(r'"desc":"(.*?)","createTime"', html)
    if desc:
        content.text = _json_unescape(desc.group(1))
    if not (content.text or content.image_url):
        return None
    return content


async def download_file(
    session: aiohttp.ClientSession, url: str, max_bytes: int, *, referer: str | None = None
) -> tuple[bytes, str]:
    """Download a binary file into memory (images, small videos)."""
    headers = {"User-Agent": DESKTOP_USER_AGENT}
    if referer:
        headers["Referer"] = referer
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
        resp.raise_for_status()
        chunks = []
        size = 0
        async for chunk in resp.content.iter_chunked(1 << 16):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("file too large")
            chunks.append(chunk)
        return b"".join(chunks), resp.headers.get("Content-Type", "")
