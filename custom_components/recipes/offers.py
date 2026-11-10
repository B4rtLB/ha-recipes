"""This week's supermarket offers (Albert Heijn, Jumbo, Lidl, Dirk), read from their public pages.

Parsing is pure Python and tested against small invented samples (dev/test_parser.py); only the
fetch functions touch the network. The shops have no public API for this, so it uses what their
own sites and apps use, at low volume (about 130 requests a week, one second apart). If a shop
changes its page the store simply yields nothing and the log says so; the other three keep working.

Every parser returns raw offers:
    {"name", "pack", "price", "was", "note", "valid_from", "valid_to", "category"}
Search words (terms) and the non-food filter come later (offer_terms.py).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import html as html_lib
import json
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import DESKTOP_USER_AGENT

_LOGGER = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Amsterdam")

JUMBO_URL = "https://www.jumbo.com/aanbiedingen/nu"
DIRK_URL = "https://www.dirk.nl/aanbiedingen"
LIDL_URL = "https://www.lidl.nl/aanbiedingen"
AH_TOKEN_URL = "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous"
AH_SEARCH_URL = "https://api.ah.nl/mobile-services/product/search/v2"

# Albert Heijn only lists offers through its product search, so we search broad grocery words
# (Dutch) and keep what is on the weekly bonus. Each search returns up to 1000 products.
AH_QUERIES = (
    "kip kipfilet kippendij gehakt rundergehakt rundvlees biefstuk varkensvlees speklapjes spek ham worst "
    "rookworst gehaktbal vleeswaren lam kalkoen schnitzel vis zalm kabeljauw tonijn garnalen pangasius "
    "haring makreel ei eieren melk yoghurt kwark skyr vla room slagroom kookroom crème fraîche boter "
    "margarine kaas geraspte kaas feta mozzarella parmezaanse kaas roomkaas brood broodjes wraps tortilla "
    "pita naan croissant pasta spaghetti penne lasagne macaroni noedels rijst basmati couscous bulgur quinoa "
    "aardappelen friet gnocchi tomaat tomaten ui uien knoflook paprika wortel wortelen broccoli bloemkool "
    "spinazie courgette aubergine champignons sla komkommer prei spitskool witlof sperziebonen mais "
    "avocado pompoen zoete aardappel bieten radijs rucola salade groente soepgroente wokgroente appel "
    "peer banaan citroen limoen sinaasappel mandarijn druiven aardbeien blauwe bessen framboos mango ananas "
    "meloen kiwi bonen kidneybonen kikkererwten linzen witte bonen tofu tempeh vegetarisch vegan hummus "
    "pesto tomatensaus passata tomatenpuree ketchup mayonaise mosterd currypasta kokosmelk sojasaus ketjap "
    "sambal olie olijfolie zonnebloemolie azijn bouillon kruiden specerijen peper zout paprikapoeder "
    "kerrie komijn kaneel suiker bloem bakmeel bakpoeder gist honing jam pindakaas hagelslag chocolade "
    "noten amandelen walnoten cashew rozijnen haver muesli cornflakes soep conserven tonijn blik maaltijd "
    "pizza diepvries ijs sauzen dressing"
).split()
AH_QUERIES = tuple(dict.fromkeys(AH_QUERIES))  # one search per word, without repeats

# Words in a shop's own category name that mean "not something you cook with".
NON_FOOD_WORDS = (
    "drogisterij", "gezondheid", "verzorging", "huishoud", "baby", "dier", "non-food", "nonfood", "kleding",
    "speelgoed", "tuin", "bloemen", "planten", "bier", "wijn", "frisdrank", "sappen", "sterke drank", "alcohol",
    "snoep", "koek", "chips", "koffie", "thee", "kantoor", "elektronica", "slapen", "personal", "household",
    "cosmetic",
)


def is_food_category(category: str | None) -> bool:
    """False for categories like "Drogisterij en gezondheid" or "Bier en wijn"."""
    lowered = (category or "").lower()
    return not any(word in lowered for word in NON_FOOD_WORDS)


# ------------------------------------------------------------------ small helpers


def eur(value: Any) -> str | None:
    """1.99 -> "€1.99"; anything that is not a positive number gives None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"€{number:.2f}" if number > 0 else None


def _date(value: Any) -> str | None:
    """"2026-11-11T00:00:00.000Z" / "2026-11-11" -> "2026-11-11"."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return match.group(1) if match else None


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(text or ""))).strip()


def _offer(name: Any, *, pack=None, price=None, was=None, note=None, valid_from=None, valid_to=None, category=None):
    name = _clean(name)
    if not name:
        return None
    return {
        "name": name,
        "pack": _clean(pack).rstrip(".") or None,
        "price": price,
        "was": was,
        "note": _clean(note) or None,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "category": _clean(category) or None,
    }


def finish(offers: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    """Fill in missing dates, drop what has already ended and exact duplicates."""
    out, seen = [], set()
    for offer in offers:
        if not offer:
            continue
        start = offer.get("valid_from") or today
        end = offer.get("valid_to") or (date.fromisoformat(start) + timedelta(days=6)).isoformat()
        if end < today or end < start:
            continue
        key = (offer["name"].lower(), offer.get("pack"), start, end)
        if key in seen:
            continue
        seen.add(key)
        out.append({**offer, "valid_from": start, "valid_to": end})
    return out


# ------------------------------------------------------------------ Nuxt payloads (Jumbo, Dirk)


def nuxt_data(page: str) -> list[Any] | None:
    """The __NUXT_DATA__ payload of a Nuxt page: a flat list where numbers point at other entries."""
    match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    return data if isinstance(data, list) else None


class _Resolver:
    """Turns the flat Nuxt list back into nested dicts and lists (entries may be shared)."""

    WRAPPERS = ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef", "readonly")

    def __init__(self, data: list[Any]) -> None:
        self.data = data
        self.cache: dict[int, Any] = {}

    def get(self, index: int) -> Any:
        if index in self.cache:
            return self.cache[index]
        value = self.data[index]
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            self.cache[index] = out
            for key, ref in value.items():
                out[key] = self._ref(ref)
            return out
        if isinstance(value, list):
            if value and isinstance(value[0], str) and value[0] in self.WRAPPERS:
                out = self._ref(value[1]) if len(value) > 1 else None
                self.cache[index] = out
                return out
            items: list[Any] = []
            self.cache[index] = items
            items.extend(self._ref(ref) for ref in value)
            return items
        self.cache[index] = value
        return value

    def _ref(self, ref: Any) -> Any:
        return self.get(ref) if isinstance(ref, int) and not isinstance(ref, bool) and 0 <= ref < len(self.data) else ref


def nuxt_objects(page: str, required_key: str) -> list[dict[str, Any]]:
    """Every object in the payload that has the given key, fully resolved."""
    data = nuxt_data(page)
    if not data:
        return []
    resolver = _Resolver(data)
    return [resolver.get(i) for i, v in enumerate(data) if isinstance(v, dict) and required_key in v]


# ------------------------------------------------------------------ parsers


def parse_jumbo(page: str) -> list[dict[str, Any]]:
    """Promotions of https://www.jumbo.com/aanbiedingen/nu with their price tag and own period."""
    data = nuxt_data(page)
    if not data:
        return []
    resolver = _Resolver(data)
    category: dict[str, str] = {}
    for i, v in enumerate(data):
        if isinstance(v, dict) and {"id", "promotions", "title"} <= set(v):
            group = resolver.get(i)
            for promo in group.get("promotions") or []:
                if isinstance(promo, dict) and promo.get("id") is not None:
                    # a specific group beats the catch-all "Nu in de aanbieding"
                    if str(promo["id"]) not in category or group["title"] != "Nu in de aanbieding":
                        category[str(promo["id"])] = group["title"]
    out = []
    for promo in (resolver.get(i) for i, v in enumerate(data) if isinstance(v, dict) and "durationTexts" in v):
        if not promo.get("active", True) or promo.get("hidden"):
            continue
        tags = [t.get("text") for t in promo.get("tags") or [] if isinstance(t, dict) and not t.get("inverse")]
        tag = _clean(tags[0]) if tags else ""
        single = re.fullmatch(r"(?:voor\s+)?(\d+),(\d{2})", tag)
        out.append(
            _offer(
                promo.get("title"),
                pack=promo.get("subtitle"),
                price=f"€{single.group(1)}.{single.group(2)}" if single else None,
                note=None if single else tag,
                valid_from=_date((promo.get("start") or {}).get("iso")),
                valid_to=_date((promo.get("end") or {}).get("iso")),
                category=category.get(str(promo.get("id"))),
            )
        )
    return out


def parse_dirk(page: str) -> list[dict[str, Any]]:
    """Offers of https://www.dirk.nl/aanbiedingen (name, pack, price, normal price, own period)."""
    out = []
    for offer in nuxt_objects(page, "offerId"):
        products = [p for p in offer.get("products") or [] if isinstance(p, dict)]
        info = (products[0].get("productInformation") if products else None) or {}
        out.append(
            _offer(
                offer.get("headerText"),
                pack=offer.get("packaging"),
                price=eur(offer.get("offerPrice")),
                was=eur(offer.get("normalPrice")),
                valid_from=_date(offer.get("startDate")),
                valid_to=_date(offer.get("endDate")),
                category=info.get("department"),
            )
        )
    return out


def parse_lidl(page: str) -> list[dict[str, Any]]:
    """Tiles of https://www.lidl.nl/aanbiedingen (their data-grid-data attributes)."""
    out = []
    for raw in re.findall(r'data-grid-data="([^"]+)"', page):
        try:
            tile = json.loads(html_lib.unescape(raw))
        except ValueError:
            continue
        price = tile.get("price") or {}
        discount = price.get("discount") or {}

        def day(key: str) -> str | None:
            stamp = tile.get(key)
            return datetime.fromtimestamp(stamp, TZ).date().isoformat() if isinstance(stamp, (int, float)) else None

        out.append(
            _offer(
                tile.get("fullTitle") or tile.get("title"),
                pack=(price.get("packaging") or {}).get("text"),
                price=eur(price.get("price")),
                was=eur(discount.get("deletedPrice") or price.get("oldPrice")),
                note=(price.get("basePrice") or {}).get("text"),
                valid_from=day("storeStartDate"),
                valid_to=day("storeEndDate"),
                category=tile.get("category"),
            )
        )
    return out


def parse_ah_products(products: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    """Weekly bonus items out of AH product search results.

    The search also flags permanent online bundles ("2% volume voordeel", end date 2999) and
    perpetual deals as bonus; only NATIONAL promotions with a real end date are weekly offers.
    """
    out = []
    for p in products or []:
        end = _date(p.get("bonusEndDate"))
        if not p.get("isBonus") or p.get("promotionType") != "NATIONAL" or not end or end >= "2100":
            continue
        labels = p.get("discountLabels") or []
        note = p.get("bonusMechanism") or (labels[0].get("defaultDescription") if labels else None)
        was = eur(p.get("priceBeforeBonus"))
        price = eur(p.get("currentPrice"))
        out.append(
            _offer(
                p.get("title"),
                pack=p.get("salesUnitSize"),
                price=price,
                was=was if was != price else None,
                note=note,
                valid_from=_date(p.get("bonusStartDate")),
                valid_to=end,
                category=p.get("mainCategory"),
            )
        )
    return out


# ------------------------------------------------------------------ fetching


async def _get_text(session: aiohttp.ClientSession, url: str) -> str:
    headers = {"User-Agent": DESKTOP_USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9", "Accept": "text/html,*/*"}
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=45)) as resp:
        resp.raise_for_status()
        return await resp.text()


async def fetch_jumbo(session: aiohttp.ClientSession, today: str, url: str = JUMBO_URL) -> list[dict[str, Any]]:
    """Jumbo's offers page."""
    return finish(parse_jumbo(await _get_text(session, url)), today)


async def fetch_dirk(session: aiohttp.ClientSession, today: str, url: str = DIRK_URL) -> list[dict[str, Any]]:
    """Dirk's offers page."""
    return finish(parse_dirk(await _get_text(session, url)), today)


async def fetch_lidl(session: aiohttp.ClientSession, today: str, url: str = LIDL_URL) -> list[dict[str, Any]]:
    """Lidl's offers page."""
    return finish(parse_lidl(await _get_text(session, url)), today)


AH_HEADERS = {
    "User-Agent": "Appie/8.22.3",
    "x-client-name": "recipes-for-home-assistant",
    "x-application": "AHWEBSHOP",
    "Accept": "application/json",
}


async def fetch_ah(
    session: aiohttp.ClientSession,
    today: str,
    *,
    token_url: str = AH_TOKEN_URL,
    search_url: str = AH_SEARCH_URL,
    queries: tuple[str, ...] = AH_QUERIES,
    delay: float = 1.0,
    token_method: str = "POST",
) -> list[dict[str, Any]]:
    """Albert Heijn's weekly bonus: an anonymous app token, then one product search per grocery word."""
    timeout = aiohttp.ClientTimeout(total=45)
    async with session.request(
        token_method, token_url, json={"clientId": "appie"} if token_method == "POST" else None, headers=AH_HEADERS, timeout=timeout
    ) as resp:
        resp.raise_for_status()
        token = (await resp.json(content_type=None))["access_token"]
    headers = {**AH_HEADERS, "Authorization": f"Bearer {token}"}
    found: dict[str, dict[str, Any]] = {}
    failures = 0
    for query in queries:
        try:
            async with session.get(
                search_url, params={"application": "AHWEBSHOP", "query": query, "size": 1000, "page": 0}, headers=headers, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                products = (await resp.json(content_type=None)).get("products") or []
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            failures += 1
            _LOGGER.debug("AH search %r failed: %s", query, err)
            if failures > 10:
                raise
            continue
        for product in products:
            parsed = parse_ah_products([product], today)
            if parsed and product.get("webshopId") not in found:
                found[product.get("webshopId")] = parsed[0]
        if delay:
            await asyncio.sleep(delay)
    return finish(list(found.values()), today)
