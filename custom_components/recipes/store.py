"""Persistence for recipes: metadata in HA storage, media files on disk."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from pathlib import Path
import secrets
import shutil
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


def utcnow_iso() -> str:
    """Return the current UTC time as ISO string."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def media_root(hass: HomeAssistant) -> Path:
    """Return the folder where recipe media is stored.

    On Home Assistant OS ``/media`` exists and is excluded from config backups
    by default, which keeps videos out of the config folder.
    """
    media = Path("/media")
    if media.is_dir():
        return media / "recipes"
    return Path(hass.config.path("recipes_media"))


class RecipeStore:
    """Keeps all recipes in a single HA Store document."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.recipes: dict[str, dict[str, Any]] = {}
        self.root = media_root(hass)
        self._listeners: list[Callable[[str], None]] = []

    async def async_load(self) -> None:
        """Load recipes from disk."""
        data = await self._store.async_load()
        self.recipes = (data or {}).get("recipes", {})
        # One-off cleanup: "Quick" means ready in 30 minutes or less.
        changed = False
        for recipe in self.recipes.values():
            tags = recipe.get("tags") or []
            if "Quick" in tags and (recipe.get("total_min") or 0) > 30:
                tags.remove("Quick")
                changed = True
        if changed:
            self._schedule_save()
        await self.hass.async_add_executor_job(self.root.mkdir, 0o755, True, True)

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(lambda: {"recipes": self.recipes}, 1)

    @callback
    def async_add_listener(self, listener: Callable[[str], None]) -> Callable[[], None]:
        """Listen for recipe changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self, recipe_id: str) -> None:
        for listener in list(self._listeners):
            listener(recipe_id)

    def media_dir(self, recipe_id: str) -> Path:
        """Return the media folder for a recipe (not created)."""
        return self.root / recipe_id

    @callback
    def async_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new recipe record."""
        recipe_id = secrets.token_hex(6)
        now = utcnow_iso()
        recipe: dict[str, Any] = {
            "id": recipe_id,
            "created": now,
            "updated": now,
            "title": None,
            "media": {},
            "favorite": False,
            **data,
        }
        self.recipes[recipe_id] = recipe
        self._schedule_save()
        self._notify(recipe_id)
        return recipe

    @callback
    def async_update(self, recipe_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Update a recipe."""
        recipe = self.recipes[recipe_id]
        recipe.update(changes)
        recipe["updated"] = utcnow_iso()
        self._schedule_save()
        self._notify(recipe_id)
        return recipe

    async def async_delete(self, recipe_id: str) -> None:
        """Delete a recipe and its media."""
        self.recipes.pop(recipe_id, None)
        self._schedule_save()
        folder = self.media_dir(recipe_id)
        await self.hass.async_add_executor_job(shutil.rmtree, folder, True)
        self._notify(recipe_id)

    @callback
    def find_by_url(self, url: str) -> dict[str, Any] | None:
        """Return an existing recipe for this source URL."""
        norm = normalize_url(url)
        for recipe in self.recipes.values():
            src = (recipe.get("source") or {}).get("url")
            if src and normalize_url(src) == norm:
                return recipe
        return None


def normalize_url(url: str) -> str:
    """Normalize a URL for duplicate detection."""
    from urllib.parse import urlsplit  # noqa: PLC0415

    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/")
    return f"{host}{path}"
