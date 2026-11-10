"""Weekly refresh of the supermarket offers: fetch four shops, add search words, store them."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import ai, discounts, offer_terms, offers
from .const import CONF_AI_TASK_ENTITY
from .store import utcnow_iso

if TYPE_CHECKING:
    from . import RecipesData

_LOGGER = logging.getLogger(__name__)

# A list is fetched again when it is missing, has ended, or is this many days old.
MAX_AGE_DAYS = 5
FETCHERS = {"ah": offers.fetch_ah, "jumbo": offers.fetch_jumbo, "lidl": offers.fetch_lidl, "dirk": offers.fetch_dirk}


def needs_refresh(entry: dict[str, Any] | None, today: str, now: datetime) -> bool:
    """Missing, ended, or older than MAX_AGE_DAYS (the offers change every week)."""
    if not entry or not entry.get("items") or entry.get("valid_to", "") < today:
        return True
    if not entry.get("fetched"):
        return False  # a list fed in by hand (recipes.set_discounts) is only replaced once it has ended
    try:
        return now - datetime.fromisoformat(str(entry["fetched"])) > timedelta(days=MAX_AGE_DAYS)
    except ValueError:
        return True


def _fixture_urls(base: str) -> dict[str, dict[str, Any]]:
    """Fixture pages on this machine for the dev tests; never a real host."""
    host = (urlsplit(base).hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1") and not host.endswith(".localhost"):
        raise ValueError("test_base must point at this machine")
    base = base.rstrip("/")
    return {
        "ah": {"token_url": f"{base}/ah/token", "search_url": f"{base}/ah/search", "token_method": "GET", "queries": ("kip",), "delay": 0},
        "jumbo": {"url": f"{base}/jumbo.html"},
        "lidl": {"url": f"{base}/lidl.html"},
        "dirk": {"url": f"{base}/dirk.html"},
    }


def _offer_to_item(o: dict[str, Any]) -> dict[str, Any]:
    note = o.get("note")
    if o.get("pack") and (not note or o["pack"].lower() not in note.lower()):
        note = f"{o['pack']} · {note}" if note else o["pack"]
    item = {"name": o["name"], "terms": o["terms"], "valid_from": o["valid_from"], "valid_to": o["valid_to"]}
    for key, value in (("price", o.get("price")), ("was", o.get("was")), ("note", note)):
        if value:
            item[key] = value
    return item


async def refresh_discounts(
    hass: HomeAssistant,
    data: RecipesData,
    stores: list[str] | None = None,
    *,
    force: bool = False,
    test_base: str | None = None,
) -> dict[str, Any]:
    """Fetch the offers of the given stores (default all) that need it. Returns a report per store.

    A store that fails keeps its old list; one failing shop never touches the others.
    """
    options = data.processor.options
    # Lidl sends a security header larger than aiohttp's default 8 KB limit
    session = async_create_clientsession(hass, max_line_size=65536, max_field_size=65536)
    try:
        return await _refresh(hass, data, session, stores, force, test_base)
    finally:
        await session.close()


async def _refresh(hass, data, session, stores, force, test_base) -> dict[str, Any]:
    options = data.processor.options
    now = datetime.now(offers.TZ)
    today = now.date().isoformat()
    kwargs = _fixture_urls(test_base) if test_base else {}
    discount_store = data.store.discounts
    cache = discount_store.terms_cache()
    entity = options.get(CONF_AI_TASK_ENTITY) or ai.default_ai_task_entity(hass)
    ai_call = (lambda prompt: ai.run_ai_task(hass, entity, prompt)) if entity else None
    report: dict[str, Any] = {}
    for key in stores or list(discounts.STORES):
        existing = discount_store.data["stores"].get(key)
        if not force and not needs_refresh(existing, today, now):
            report[key] = {
                "skipped": "still fresh", "items": len(existing["items"]),
                "valid_from": existing["valid_from"], "valid_to": existing["valid_to"],
            }
            continue
        try:
            raw = await FETCHERS[key](session, today, **kwargs.get(key, {}))
            food = [o for o in raw if offers.is_food_category(o.get("category"))]
            stats = await offer_terms.add_terms(food, ai_call, cache)
            if not food:
                raise ValueError("no offers found (did the shop change its page?)")
            items = [_offer_to_item(o) for o in food]
            entry = discounts.clean_store(
                key, min(i["valid_from"] for i in items), max(i["valid_to"] for i in items), items
            )
            entry["fetched"] = utcnow_iso()
        except Exception as err:  # noqa: BLE001 - one shop must never stop the others
            _LOGGER.warning("Offers of %s could not be refreshed: %s", key, err)
            report[key] = {"error": f"{type(err).__name__}: {err}"[:200]}
            continue
        discount_store.set_store(key, entry)
        report[key] = {"found": len(raw), "items": len(items), "valid_from": entry["valid_from"], "valid_to": entry["valid_to"], **stats}
        _LOGGER.info("Offers of %s: %s", key, report[key])
    discount_store.save_cache()
    return report
