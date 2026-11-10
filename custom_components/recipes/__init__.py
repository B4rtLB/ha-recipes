"""Recipes: save recipes (incl. TikTok/Instagram videos) from your phone into Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path

from homeassistant.components import webhook
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .const import CONF_WEBHOOK_ID, DOMAIN, URL_STATIC
from .pipeline import RecipeProcessor, new_recipe_from_payload
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
