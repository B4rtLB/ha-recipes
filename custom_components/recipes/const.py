"""Constants for the Recipes integration."""

from __future__ import annotations

DOMAIN = "recipes"
VERSION = "0.1.0"

STORAGE_KEY = "recipes.recipes"
STORAGE_VERSION = 1

CONF_AI_TASK_ENTITY = "ai_task_entity"
CONF_STT_ENTITY = "stt_entity"
CONF_LANGUAGE = "language"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_INSTAGRAM_COOKIES = "instagram_cookies"
CONF_TRANSCRIBE = "transcribe"
CONF_WEBHOOK_ID = "webhook_id"
CONF_TODO_ENTITY = "todo_entity"

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English", "nl": "Dutch (Nederlands)"}

URL_APP = "/recipes"
URL_STATIC = "/recipes/static"
URL_API = "/api/recipes"

MAX_VIDEO_BYTES = 400 * 1024 * 1024
MAX_TRANSCRIBE_SECONDS = 8 * 60
SIGNED_URL_HOURS = 24 * 7

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_ERROR = "error"

# Same tag groups as the original "Save Recipes" shortcut.
TAG_GROUPS: dict[str, list[str]] = {
    "Course": ["Main", "Breakfast", "Lunch", "Snack", "Dessert", "Baking", "Sauce"],
    "Protein": ["Chicken", "Beef", "Pork", "Fish", "Seafood", "Vegetarian"],
    "Cuisine": ["Indian", "Somali", "Asian", "MiddleEastern", "Mexican", "Mediterranean", "Dutch"],
    "Extra": ["Quick", "MealPrep"],
}

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
)
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
