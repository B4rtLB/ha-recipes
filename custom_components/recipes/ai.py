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

from . import parser
from .const import LANGUAGES, TAG_GROUPS

_LOGGER = logging.getLogger(__name__)

PROMPT = """You receive source material for ONE recipe: a social media caption, a speech \
transcript, schema.org JSON-LD, web page text, OCR text, a photo or a PDF. Return the recipe \
as a single JSON object. JSON only: no markdown, no code fences, no comments.

CRITICAL RULES
- Use only the source. Never add or invent ingredients or steps. Caption and transcript \
together: amounts in the caption win, the transcript fills the gaps. "RECIPE TEXT" is the \
user's own note: it wins on amounts, the caption fills in missing steps.
- Write all text in {language}; translate if the source is in another language. Natural \
and concise.
- Metric only: convert cups, oz, lb, fl oz, inches and °F to g, kg, ml, l, cm and °C and \
put the original amount in "original" (e.g. "7 oz", "1 cup"). Cups of flour, sugar, rice \
and similar dry goods become grams when you are confident, otherwise ml. Keep tsp and \
tbsp. In step text write converted temperatures as "200 °C (400 °F)".
- "qty" is a number (1/2 -> 0.5); "qty_max" only for ranges ("2-3 cloves" -> qty 2, qty_max \
3); null when there is no amount. "unit" is short and lowercase (g, kg, ml, l, tsp, tbsp, \
clove, pinch, can, bunch, slice...) or null for countable items ("2 eggs" -> qty 2, unit null).
- Keep the source's ingredient groups ("Marinade", "Sauce"); otherwise one group with \
"name": null.
- Steps: keep the order and all details, one step per instruction. Don't repeat the \
ingredient list inside steps.
- Timers: for every explicit waiting or cooking time in a step (bake 25 min, simmer 10-15 \
minutes, marinate overnight = 8 h) add a timer in seconds (range: lower bound) with a 1-3 \
word label ("Simmer sauce"). None for vague times ("until golden").
- Times and servings: use the source. If missing, estimate prep/cook/total minutes and \
servings from cues (oven time, pan size, "serves 4") and set "estimated": true. Estimates \
never justify inventing ingredients or steps.
- Title: the real dish name, no emoji, hashtags or clickbait. Description: one short \
sentence about the dish, or null.
- Tags: AT MOST ONE per group, exactly as written, skip a group when nothing clearly fits:
{tags}
  Quick = ready in 30 minutes or less. MealPrep = keeps and reheats well. Protein: always \
tag the main meat or fish (bacon, ham and chorizo are Pork); Vegetarian only when there is \
no meat or fish at all.

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


def build_prompt(source: str, language: str, extra: str | None = None) -> str:
    """Build the extraction prompt. ``extra`` is an optional instruction for an experiment."""
    tags = "\n".join(f"  {group}: {' '.join(values)}" for group, values in TAG_GROUPS.items())
    prompt = PROMPT.format(language=LANGUAGES.get(language, language), tags=tags, source=source)
    if extra and extra.strip():
        prompt += (
            "\n\nEXTRA INSTRUCTION (it overrides the rules above where they conflict, "
            "but never invent ingredients or steps):\n" + extra.strip()
        )
    return prompt


LEAN_PROMPT = """Extract ONE recipe from the source below. Answer with a single JSON object and nothing else.

RULES
- Use only what the source says. Never invent ingredients or steps.
- Several parts (caption, transcript, note): combine them. Amounts in the caption win.
- "title" and "description" and every step: write in {language}. The title is the dish name only, no emoji.
- "ingredient_groups": copy every ingredient line exactly as written, with its amount and unit \
(like "1 cup flour" or "200 g chicken thigh, diced"). Do NOT convert units and do NOT calculate. \
You may translate the words to {language}. Use one group with "name": null unless the source has groups.
- "steps": one string per instruction, in order, with all details. Keep temperatures and times as written.
- "tags": at most one tag per group, exactly as written, skip a group when unsure:
{tags}
  Quick = ready in 30 minutes or less. Protein: tag the main meat or fish (bacon and ham are Pork).
- Times and servings: use the source. If they are missing you may estimate prep/cook/total \
minutes and servings from cues (oven time, pan size, "serves 4") and then set "estimated": true. \
Never invent ingredients or steps.

JSON SHAPE
{{"recipe_found": true, "title": "...", "description": "one short sentence or null", "servings": 4, \
"servings_text": null, "prep_min": null, "cook_min": null, "total_min": null, "estimated": false, \
"ingredient_groups": [{{"name": null, "items": ["200 g chicken thigh, diced", "1 tsp salt"]}}], \
"steps": ["Fry the chicken for 5 minutes.", "Add the sauce."], "tags": ["Main", "Chicken"], "source_notes": null}}

No recipe in the source: {{"recipe_found": false, "title": "what the source is"}}

SOURCE MATERIAL
{source}"""

TAGS_PROMPT = """A recipe is already parsed. Only choose tags and, when missing, write a description. \
Answer with a single JSON object and nothing else.

TITLE: {title}
INGREDIENTS: {ingredients}
CATEGORY / CUISINE / KEYWORDS: {hints}
TOTAL TIME: {minutes}
DESCRIPTION: {description}

Tags: at most one per group, exactly as written, skip a group when unsure:
{tags}
  Quick = ready in 30 minutes or less. Protein: tag the main meat or fish (bacon and ham are Pork).
Description: one short sentence in {language}, or keep the one above when it is fine.

{{"tags": ["Main", "Chicken"], "description": "..."}}"""


def _tag_lines() -> str:
    return "\n".join(f"  {group}: {' '.join(values)}" for group, values in TAG_GROUPS.items())


def _with_extra(prompt: str, extra: str | None) -> str:
    if extra and extra.strip():
        prompt += (
            "\n\nEXTRA INSTRUCTION (it overrides the rules above where they conflict, "
            "but never invent ingredients or steps):\n" + extra.strip()
        )
    return prompt


def build_lean_prompt(source: str, language: str, extra: str | None = None) -> str:
    """The short prompt for small models: raw ingredient strings and step text only."""
    return _with_extra(
        LEAN_PROMPT.format(language=LANGUAGES.get(language, language), tags=_tag_lines(), source=source), extra
    )


def build_tags_prompt(data: dict[str, Any], language: str, extra: str | None = None) -> str:
    """Tiny prompt for the JSON-LD shortcut: only tags and a description are left to the AI."""
    names = [
        parser.parse_ingredient(item)["name"] if isinstance(item, str) else str(item.get("name", ""))
        for group in data.get("ingredient_groups") or []
        for item in group.get("items") or []
    ]
    return _with_extra(
        TAGS_PROMPT.format(
            title=data.get("title") or "",
            ingredients=", ".join(n for n in names if n)[:1500],
            hints=data.get("_hints") or "-",
            minutes=data.get("total_min") or data.get("cook_min") or "unknown",
            description=data.get("description") or "(none)",
            language=LANGUAGES.get(language, language),
            tags=_tag_lines(),
        ),
        extra,
    )


def lean_to_full(data: dict[str, Any]) -> dict[str, Any]:
    """Turn the lean AI output (raw strings) into the full shape that ``normalize`` reads.

    Ingredient strings go through the parser, step text gets °F/inches converted and
    timers from the durations in it. Dict items (a model that ignored the lean shape) pass.
    """
    out = dict(data)
    groups: list[dict[str, Any]] = []
    raw_groups = data.get("ingredient_groups")
    if not raw_groups and data.get("ingredients"):
        raw_groups = [{"name": None, "items": data["ingredients"]}]
    for group in raw_groups or []:
        if isinstance(group, str):
            group = {"name": None, "items": [group]}
        if not isinstance(group, dict):
            continue
        current: dict[str, Any] = {"name": group.get("name") or None, "items": []}
        groups.append(current)
        for item in group.get("items") or []:
            if isinstance(item, str):
                text = item.strip()
                # A small model sometimes puts a heading in the list: "For the sauce:"
                if text.endswith(":") and not text[:1].isdigit():
                    current = {"name": text.rstrip(": ").strip() or None, "items": []}
                    groups.append(current)
                    continue
                if text:
                    current["items"].append(parser.parse_ingredient(text))
            elif isinstance(item, dict):
                if item.get("qty") is None and item.get("unit") is None and re.match(r"\s*[\d½¼¾⅓⅔]", str(item.get("name") or "")):
                    parsed = parser.parse_ingredient(str(item["name"]))
                    parsed["note"] = parsed["note"] or item.get("note")
                    current["items"].append(parsed)
                else:
                    current["items"].append(item)
    out["ingredient_groups"] = [g for g in groups if g["items"]]

    steps = []
    for step in data.get("steps") or []:
        if isinstance(step, str):
            step = {"text": step}
        if not isinstance(step, dict) or not step.get("text"):
            continue
        text = parser.convert_text(str(step["text"]).strip())
        timers = [t for t in step.get("timers") or [] if isinstance(t, dict) and t.get("seconds")]
        steps.append({"text": text, "timers": timers or parser.find_timers(text)})
    out["steps"] = steps
    return out


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


def find_durations(text: str) -> list[int]:
    """Find durations (seconds) mentioned in a step; fallback when the AI gives none."""
    return parser.find_durations(text)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


# The AI sometimes forgets the Protein tag; these words in the title or an ingredient
# name settle it then. Stock, broth and sauces don't count ("chicken stock", "fish sauce").
_PROTEIN_WORDS = {
    "Chicken": r"chicken|kip\w*",
    "Beef": r"beef|steak|brisket|rund\w*|biefstuk",
    "Pork": r"pork|bacon|ham|pancetta|chorizo|prosciutto|guanciale|lardons?|spek\w*|varkens\w*",
    "Fish": r"fish|salmon|tuna|cod|trout|haddock|vis|zalm|tonijn|kabeljauw",
    "Seafood": r"shrimps?|prawns?|mussels?|squid|crab|lobster|scallops?|clams?|garnalen|mosselen",
}
_PROTEIN_RE = {tag: re.compile(rf"\b(?:{words})\b", re.IGNORECASE) for tag, words in _PROTEIN_WORDS.items()}
_NOT_THE_PROTEIN = re.compile(r"stock|broth|bouillon|sauce|saus|seasoning|flavou?r", re.IGNORECASE)


def guess_protein(title: str, ingredient_names: list[str]) -> str | None:
    """Protein tag from the title, else from the first ingredient that names one."""
    for text in [title, *ingredient_names]:
        if not text or _NOT_THE_PROTEIN.search(text):
            continue
        for tag, pattern in _PROTEIN_RE.items():
            if pattern.search(text):
                return tag
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
            timers = parser.find_timers(text, 2)
        steps.append({"text": text, "timers": timers})

    tags = []
    for tag in data.get("tags") or []:
        tag = str(tag).lstrip("#").strip()
        if tag in allowed and tag not in tags:
            tags.append(tag)

    if not any(tag in TAG_GROUPS["Protein"] for tag in tags):
        names = [item["name"] for group in groups for item in group["items"]]
        if protein := guess_protein(str(data.get("title") or ""), names):
            order = [t for values in TAG_GROUPS.values() for t in values]
            tags = sorted([*tags, protein], key=order.index)

    def minutes(key: str) -> int | None:
        value = _num(data.get(key))
        return int(round(value)) if value and value > 0 else None

    prep, cook, total = minutes("prep_min"), minutes("cook_min"), minutes("total_min")
    if total is None and (prep or cook):
        total = (prep or 0) + (cook or 0)

    # Keep the "Quick" tag honest (<= 30 minutes in total).
    if total and total > 30 and "Quick" in tags:
        tags.remove("Quick")

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
