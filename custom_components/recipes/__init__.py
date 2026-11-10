"""Recipes: save recipes (incl. TikTok/Instagram videos) from your phone into Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path

from homeassistant.components import webhook
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_time_change

from . import discounts, sources
from .const import CONF_AUTO_DISCOUNTS, CONF_WEBHOOK_ID, DOMAIN, URL_STATIC
from .pipeline import RecipeProcessor, new_recipe_from_payload
from .refresh import refresh_discounts
from .store import RecipeStore
from .views import FRONTEND, handle_webhook, register_views

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class RecipesData:
    """Runtime data."""

    entry: ConfigEntry
    store: RecipeStore
    processor: RecipeProcessor
    asset_version: str


def _asset_version() -> str:
    from .icons import ensure_icons  # noqa: PLC0415

    ensure_icons(FRONTEND / "icons")
    digest = hashlib.sha1()
    for path in sorted(FRONTEND.rglob("*")):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register static paths and views once."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_STATIC, str(FRONTEND), cache_headers=True)]
    )
    register_views(hass)

    async def add_recipe(call: ServiceCall) -> ServiceResponse:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        recipe, created = new_recipe_from_payload(
            hass, data.store, {"url": call.data["url"], "force": call.data.get("force", False)}
        )
        if created:
            data.processor.enqueue(recipe["id"])
        return {"id": recipe["id"], "created": created}

    async def status(call: ServiceCall) -> ServiceResponse:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        recipes = sorted(data.store.recipes.values(), key=lambda r: r.get("created") or "", reverse=True)
        if call.data.get("id"):
            r = data.store.recipes.get(call.data["id"])
            if r is None:
                raise vol.Invalid("Unknown recipe")
            return {
                "id": r["id"],
                "title": r.get("title"),
                "status": r.get("status"),
                "source": r.get("source"),
                "media": r.get("media"),
                "shared": r.get("shared"),
                "input_text": (r.get("input_text") or "")[:1500] or None,
                "links_found": sources.all_urls(r.get("shared"), r.get("input_text"))[:60],
                "notes": r.get("pipeline_notes"),
                "created": r.get("created"),
                "updated": r.get("updated"),
            }
        return {
            "webhook_path": f"/api/webhook/{data.entry.data[CONF_WEBHOOK_ID]}",
            "count": len(recipes),
            "recipes": [
                {
                    "id": r["id"],
                    "title": r.get("title"),
                    "status": r.get("status"),
                    "progress": r.get("progress"),
                    "error": r.get("error"),
                    "platform": (r.get("source") or {}).get("platform"),
                    "source_url": (r.get("source") or {}).get("url"),
                    "has_video": bool((r.get("media") or {}).get("video")),
                    "ingredients": sum(len(g.get("items", [])) for g in r.get("ingredient_groups") or []),
                    "steps": len(r.get("steps") or []),
                    "total_min": r.get("total_min"),
                    "tags": r.get("tags"),
                    "notes": r.get("pipeline_notes"),
                }
                for r in recipes[: call.data.get("limit", 20)]
            ],
        }

    async def delete(call: ServiceCall) -> None:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        await data.store.async_delete(call.data["id"])

    async def retry(call: ServiceCall) -> None:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        ids = [call.data["id"]] if call.data.get("id") else [
            r["id"] for r in data.store.recipes.values() if r.get("status") == "error"
        ]
        for rid in ids:
            if rid in data.store.recipes:
                data.processor.enqueue(rid)

    async def set_discounts(call: ServiceCall) -> None:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        try:
            entry = discounts.clean_store(
                call.data["store"], call.data["valid_from"], call.data["valid_to"], call.data["items"]
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        data.store.discounts.set_store(call.data["store"], entry)

    hass.services.async_register(
        DOMAIN,
        "set_discounts",
        set_discounts,
        schema=vol.Schema({
            vol.Required("store"): vol.In(list(discounts.STORES)),
            vol.Required("valid_from"): cv.date,
            vol.Required("valid_to"): cv.date,
            vol.Required("items"): list,
        }),
    )
    async def refresh_offers(call: ServiceCall) -> ServiceResponse:
        data: RecipesData | None = hass.data.get(DOMAIN)
        if data is None:
            raise vol.Invalid("Recipes is not set up")
        try:
            return await refresh_discounts(
                hass, data, call.data.get("store"), force=call.data["force"], test_base=call.data.get("test_base")
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        "refresh_discounts",
        refresh_offers,
        schema=vol.Schema({
            vol.Optional("store"): vol.All(cv.ensure_list, [vol.In(list(discounts.STORES))]),
            vol.Optional("force", default=False): cv.boolean,
            vol.Optional("test_base"): cv.string,
        }),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(DOMAIN, "delete", delete, schema=vol.Schema({vol.Required("id"): cv.string}))
    hass.services.async_register(DOMAIN, "retry", retry, schema=vol.Schema({vol.Optional("id"): cv.string}))

    hass.services.async_register(
        DOMAIN,
        "status",
        status,
        schema=vol.Schema({
            vol.Optional("limit", default=20): vol.All(int, vol.Range(min=1, max=500)),
            vol.Optional("id"): cv.string,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "add",
        add_recipe,
        schema=vol.Schema({vol.Required("url"): cv.url, vol.Optional("force", default=False): cv.boolean}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Recipes from a config entry."""
    store = RecipeStore(hass)
    await store.async_load()
    processor = RecipeProcessor(hass, store, {**entry.data, **entry.options})
    version = await hass.async_add_executor_job(_asset_version)
    hass.data[DOMAIN] = RecipesData(entry, store, processor, version)

    webhook.async_register(
        hass, DOMAIN, "Recipes share", entry.data[CONF_WEBHOOK_ID], handle_webhook,
        local_only=False, allowed_methods=["POST", "PUT"],
    )
    processor.start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def auto_refresh(_now=None) -> None:
        """Fetch the weekly offers of the shops whose list is missing, ended or old (see refresh.py)."""
        current: RecipesData | None = hass.data.get(DOMAIN)
        if current and current.processor.options.get(CONF_AUTO_DISCOUNTS, True):
            try:
                await refresh_discounts(hass, current)
            except Exception:  # noqa: BLE001 - never let the schedule die
                _LOGGER.exception("Automatic offers refresh failed")

    entry.async_on_unload(async_track_time_change(hass, auto_refresh, hour=6, minute=15, second=0))
    entry.async_on_unload(async_call_later(hass, 180, auto_refresh))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data: RecipesData = hass.data[DOMAIN]
    data.processor.options = {**entry.data, **entry.options}


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    data: RecipesData | None = hass.data.pop(DOMAIN, None)
    if data:
        await data.processor.stop()
    return True


__all__ = ["RecipesData", "Path"]
