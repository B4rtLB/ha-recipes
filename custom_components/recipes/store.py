"""Persistence for recipes: metadata in HA storage, media files on disk."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from pathlib import Path
import secrets
import shutil
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

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
        # Held by the pipeline while it writes into a media folder, so a folder
        # is never renamed under it.
        self.media_lock = asyncio.Lock()

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
        await self._async_migrate_folders()

    async def _async_migrate_folders(self) -> None:
        """One-off: give existing media folders a readable name (<title>-<id>)."""
        todo = [
            (rid, rid, name)
            for rid, recipe in self.recipes.items()
            if not recipe.get("folder") and (name := folder_name(recipe)) != rid
        ]
        if not todo:
            return

        def rename_all() -> list[tuple[str, str]]:
            done = []
            for rid, old, new in todo:
                if _rename(self.root / old, self.root / new):
                    done.append((rid, new))
            return done

        for rid, new in await self.hass.async_add_executor_job(rename_all):
            self.recipes[rid]["folder"] = new
        self._schedule_save()

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(lambda: {"recipes": self.recipes}, 1)

    def media_dir(self, recipe_id: str) -> Path:
        """Return the media folder for a recipe (not created)."""
        recipe = self.recipes.get(recipe_id) or {}
        return self.root / (recipe.get("folder") or recipe_id)

    async def async_rename_media(self, recipe_id: str, *, locked: bool = False) -> None:
        """Name the media folder after the recipe title: <slug-of-title>-<id>.

        The pipeline calls this with locked=True when it has finished. Other
        callers are skipped while the pipeline is busy; it renames at the end.
        """
        if not locked:
            if self.media_lock.locked():
                return
            async with self.media_lock:
                await self.async_rename_media(recipe_id, locked=True)
            return
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            return
        old = recipe.get("folder") or recipe_id
        new = folder_name(recipe)
        if new == old:
            return
        if await self.hass.async_add_executor_job(_rename, self.root / old, self.root / new):
            if recipe_id in self.recipes:
                recipe["folder"] = new
                self._schedule_save()

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
        return recipe

    @callback
    def async_update(self, recipe_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Update a recipe."""
        recipe = self.recipes[recipe_id]
        recipe.update(changes)
        recipe["updated"] = utcnow_iso()
        self._schedule_save()
        return recipe

    async def async_delete(self, recipe_id: str) -> None:
        """Delete a recipe and its media."""
        folder = self.media_dir(recipe_id)
        self.recipes.pop(recipe_id, None)
        self._schedule_save()
        await self.hass.async_add_executor_job(shutil.rmtree, folder, True)

    @callback
    def find_by_url(self, url: str) -> dict[str, Any] | None:
        """Return an existing recipe for this source URL."""
        norm = normalize_url(url)
        for recipe in self.recipes.values():
            src = (recipe.get("source") or {}).get("url")
            if src and normalize_url(src) == norm:
                return recipe
        return None


def folder_name(recipe: dict[str, Any]) -> str:
    """Media folder name: readable title plus the id, which keeps it unique."""
    slug = slugify(recipe.get("title") or "", separator="-")[:60].strip("-")
    return f"{slug}-{recipe['id']}" if slug and slug != "unknown" else recipe["id"]


def _rename(old: Path, new: Path) -> bool:
    """Rename a media folder (blocking). True when the new name is now valid."""
    if new.exists():
        return False
    if not old.exists():
        return True  # nothing on disk yet; the new name is used from now on
    try:
        old.rename(new)
    except OSError as err:
        _LOGGER.warning("Could not rename %s to %s: %s", old, new, err)
        return False
    return True


def normalize_url(url: str) -> str:
    """Normalize a URL for duplicate detection."""
    from urllib.parse import urlsplit  # noqa: PLC0415

    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/")
    return f"{host}{path}"
