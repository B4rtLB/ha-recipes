"""Turn raw source material into a structured recipe using a HA AI Task entity."""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import LANGUAGES, TAG_GROUPS

_LOGGER = logging.getLogger(__name__)

PROMPT = """You receive source material for ONE recipe: it can be a social media caption, \
a speech transcript of a cooking video, schema.org JSON-LD, the text of a web page, OCR \
text, an attached photo/screenshot or an attached PDF. Extract only the recipe and return \
it as a single JSON object. Output JSON only: no markdown, no code fences, no comments.

CRITICAL RULES
- No hallucination: use only information found in the source. Never add or invent \
ingredients or steps. When a caption and a transcript are both given, combine them: \
amounts written in the caption win, the transcript fills in what the caption lacks.
- Write all human-readable text in {language}. Translate if the source is in another \
language. Keep it natural and concise.
- Metric only: convert cups, oz, lb, fl oz, inches and °F to g, kg, ml, l, cm and °C. \
Put the original amount in "original" (e.g. "7 oz", "1 cup"). For flour, sugar, rice \
and similar dry goods convert cups to grams when you are confident, otherwise to ml. \
Keep tsp/tbsp as "tsp"/"tbsp" (they are fine in a metric kitchen). Inside step text \
write temperatures as "200 °C (400 °F)" when converted.
- Numbers: "qty" is a number (fractions as decimals, 1/2 -> 0.5), "qty_max" only for \
ranges ("2-3 cloves" -> qty 2, qty_max 3). Use null when there is no amount ("salt to \
taste"). "unit" is short and lowercase (g, kg, ml, l, tsp, tbsp, clove, pinch, can, \
bunch, slice...) or null for countable items ("2 eggs" -> qty 2, unit null, name "eggs").
- Keep ingredient groups if the source has them (e.g. "Marinade", "Sauce"); otherwise \
use one group with "name": null.
- Steps: keep the order and all details of the source, one step per instruction \
paragraph. Do not repeat the ingredient list inside steps unless the source does.
- Timers: for every explicit waiting/cooking time in a step (bake 25 min, simmer 10-15 \
minutes, rest 1 hour, marinate overnight = 8 h) add a timer with the duration in seconds \
(for a range use the lower bound) and a 1-3 word label (e.g. "Simmer sauce"). No timers \
for vague times ("until golden").
- Times and servings: use the source. If missing you may estimate prep/cook/total minutes \
and servings from cues in the source (oven time, pan size, "serves 4") and then set \
"estimated": true. Estimates must never lead you to invent ingredients or steps.
- Title: the real dish name, no emojis, no hashtags, no clickbait ("You NEED this" -> \
the dish name). Description: one short sentence about the dish, or null.
- Tags: pick AT MOST ONE tag per group below, skip a group when nothing clearly fits, \
use tags exactly as written:
{tags}
  Quick = ready in 30 minutes or less. MealPrep = keeps well in the fridge and reheats well.

OUTPUT SHAPE
{{
  "recipe_found": true,
  "title": "string",
  "description": "string or null",
  "servings": number or null,
  "servings_text": "string or null (e.g. '12 cookies')",
  "prep_min": number or null,
  "cook_min": number or null,
  "total_min": number or null,
  "estimated": false,
  "ingredient_groups": [
    {{"name": null, "items": [
      {{"qty": 200, "qty_max": null, "unit": "g", "name": "chicken thigh", "note": "boneless, diced", "original": "7 oz"}}
    ]}}
  ],
  "steps": [
    {{"text": "string", "timers": [{{"seconds": 600, "label": "Simmer"}}]}}
  ],
  "tags": ["Main", "Chicken", "Indian", "Quick"],
  "source_notes": "string or null (tips/variations from the source worth keeping)"
}}

If the source contains no recipe at all, return {{"recipe_found": false, "title": "short \
description of what the source is"}}.

SOURCE MATERIAL
{source}"""


def build_prompt(source: str, language: str) -> str:
    """Build the extraction prompt."""
    tags = "\n".join(f"  {group}: {' '.join(values)}" for group, values in TAG_GROUPS.items())
    return PROMPT.format(language=LANGUAGES.get(language, language), tags=tags, source=source)


def default_ai_task_entity(hass: HomeAssistant) -> str | None:
    """Return the preferred AI task entity, or the first one available."""
    try:
        from homeassistant.components.ai_task.const import DATA_PREFERENCES  # noqa: PLC0415

        prefs = hass.data.get(DATA_PREFERENCES)
        if prefs is not None and prefs.gen_data_entity_id:
            return prefs.gen_data_entity_id
    except ImportError:
        pass
    ids = hass.states.async_entity_ids("ai_task")
    return ids[0] if ids else None


async def run_ai_task(
    hass: HomeAssistant,
    entity_id: str,
    instructions: str,
    attachments: list[Path] | None = None,
) -> str:
    """Run an AI task, optionally with local file attachments, return text."""
    from homeassistant.components import ai_task, conversation  # noqa: PLC0415

    if not attachments:
        result = await ai_task.async_generate_data(
            hass, task_name="recipe extraction", entity_id=entity_id, instructions=instructions
        )
        return result.data if isinstance(result.data, str) else json.dumps(result.data)

    from homeassistant.components.ai_task.const import DATA_COMPONENT  # noqa: PLC0415
    from homeassistant.components.ai_task.task import GenDataTask  # noqa: PLC0415
    from homeassistant.helpers.chat_session import async_get_chat_session  # noqa: PLC0415

    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(f"AI Task entity {entity_id} not found")
    files = []
    for path in attachments:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append(
            conversation.Attachment(
                media_content_id=f"media-source://recipes/{path.parent.name}/{path.name}",
                mime_type=mime,
                path=path,
            )
        )
    with async_get_chat_session(hass) as session:
        result = await entity.internal_async_generate_data(
            session,
            GenDataTask(name="recipe extraction", instructions=instructions, attachments=files),
            None,
        )
    return result.data if isinstance(result.data, str) else json.dumps(result.data)


def parse_json(text: str) -> dict[str, Any]:
    """Parse the model output, tolerating code fences and chatter."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object")
    return data


_DURATION_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)(?:\s*(?:-|–|to|tot)\s*(\d+(?:[.,]\d+)?))?\s*"
    r"(hours?|hrs?|uur|h|minutes?|mins?|minuten|min|m|seconds?|secs?|seconden|sec|s)\b",
    re.IGNORECASE,
)


def find_durations(text: str) -> list[int]:
    """Find durations (seconds) mentioned in a step; fallback when the AI gives none."""
    found = []
    for match in _DURATION_RE.finditer(text):
        value = float(match.group(1).replace(",", "."))
        unit = match.group(3).lower()
        if unit.startswith(("h", "u")):
            seconds = value * 3600
        elif unit.startswith("s"):
            seconds = value
        else:
            seconds = value * 60
        if 10 <= seconds <= 48 * 3600:
            found.append(int(seconds))
    return found


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean the model output into our recipe fields."""
    allowed = {t for values in TAG_GROUPS.values() for t in values}
    groups = []
    for group in data.get("ingredient_groups") or []:
        if not isinstance(group, dict):
            continue
        items = []
        for item in group.get("items") or []:
            if isinstance(item, str):
                items.append({"qty": None, "qty_max": None, "unit": None, "name": item, "note": None, "original": None})
                continue
            if not isinstance(item, dict) or not item.get("name"):
                continue
            items.append(
                {
                    "qty": _num(item.get("qty")),
                    "qty_max": _num(item.get("qty_max")),
                    "unit": (item.get("unit") or None),
                    "name": str(item["name"]).strip(),
                    "note": item.get("note") or None,
                    "original": item.get("original") or None,
                }
            )
        if items:
            groups.append({"name": group.get("name") or None, "items": items})

    steps = []
    for step in data.get("steps") or []:
        if isinstance(step, str):
            step = {"text": step}
        if not isinstance(step, dict) or not step.get("text"):
            continue
        text = str(step["text"]).strip()
        timers = []
        for timer in step.get("timers") or []:
            if isinstance(timer, dict) and (sec := _num(timer.get("seconds"))) and sec > 0:
                timers.append({"seconds": int(sec), "label": timer.get("label") or None})
        if not timers:
            timers = [{"seconds": s, "label": None} for s in find_durations(text)[:2]]
        steps.append({"text": text, "timers": timers})

    tags = []
    for tag in data.get("tags") or []:
        tag = str(tag).lstrip("#").strip()
        if tag in allowed and tag not in tags:
            tags.append(tag)

    def minutes(key: str) -> int | None:
        value = _num(data.get(key))
        return int(round(value)) if value and value > 0 else None

    prep, cook, total = minutes("prep_min"), minutes("cook_min"), minutes("total_min")
    if total is None and (prep or cook):
        total = (prep or 0) + (cook or 0)

    servings = _num(data.get("servings"))
    return {
        "title": (data.get("title") or "Untitled recipe").strip(),
        "description": data.get("description") or None,
        "servings": servings if servings and servings > 0 else None,
        "servings_text": data.get("servings_text") or None,
        "prep_min": prep,
        "cook_min": cook,
        "total_min": total,
        "estimated": bool(data.get("estimated")),
        "ingredient_groups": groups,
        "steps": steps,
        "tags": tags,
        "source_notes": data.get("source_notes") or None,
    }


def guess_language(text: str) -> str:
    """Rough language guess for speech-to-text (en/nl/de/fr/es/it)."""
    words = re.findall(r"[a-zà-ÿ]+", (text or "").lower())
    if not words:
        return "en"
    markers = {
        "nl": {"de", "het", "een", "en", "met", "voor", "van", "je", "ik", "dit", "is", "recept", "lekker", "niet"},
        "de": {"der", "die", "das", "und", "mit", "für", "ich", "ein", "rezept", "nicht"},
        "fr": {"le", "la", "les", "et", "avec", "pour", "une", "recette", "pas"},
        "es": {"el", "la", "los", "y", "con", "para", "una", "receta", "que"},
        "it": {"il", "la", "e", "con", "per", "una", "ricetta", "che", "di"},
        "en": {"the", "and", "with", "for", "this", "you", "recipe", "to", "of", "is"},
    }
    scores = {lang: sum(w in m for w in words) for lang, m in markers.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "en"
