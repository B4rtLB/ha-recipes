"""Deterministic recipe text parsing: amounts, units, metric conversion, timers.

This is the work a small local model gets wrong, so the "lean" extraction mode takes it
away from the AI. Pure Python on purpose (no Home Assistant imports): it is unit-tested on
its own with golden fixtures (dev/test_parser.py).
"""

from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------ numbers

_VULGAR = {
    "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅕": 0.2, "⅖": 0.4, "⅗": 0.6,
    "⅘": 0.8, "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}
_V = "".join(_VULGAR)
# One number: 1½, ½, 1 1/2, 1/2, 1.5 or 1,5. Order matters (longest forms first).
_NUM = rf"(?:\d+\s*[{_V}]|[{_V}]|\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:[.,]\d+)?)"
_RANGE_SEP = r"(?:\s*[-–—]\s*|\s+(?:to|tot|or|of)\s+)"
_AMOUNT_RE = re.compile(rf"(?P<a>{_NUM})(?:{_RANGE_SEP}(?P<b>{_NUM}))?(?![\d/])", re.IGNORECASE)

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "half": 0.5,
    "een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
    "negen": 9, "tien": 10, "elf": 11, "twaalf": 12, "halve": 0.5, "anderhalf": 1.5,
    "anderhalve": 1.5,
}
_HALF_RE = re.compile(r"^(?:een\s+halve?|a\s+half|half\s+an?|halve?|half)\s+", re.IGNORECASE)
_WORD_NUM_RE = re.compile(r"(?P<w>" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _value(token: str) -> float:
    """Value of one number token ("1½", "1 1/2", "1,5")."""
    token = token.strip()
    if token in _VULGAR:
        return round(_VULGAR[token], 3)
    if match := re.fullmatch(rf"(\d+)\s*([{_V}])", token):
        return round(int(match.group(1)) + _VULGAR[match.group(2)], 3)
    if match := re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", token):
        return round(int(match.group(1)) + int(match.group(2)) / max(int(match.group(3)), 1), 3)
    if match := re.fullmatch(r"(\d+)\s*/\s*(\d+)", token):
        return round(int(match.group(1)) / max(int(match.group(2)), 1), 3)
    return round(float(token.replace(",", ".")), 3)


def _clean_number(value: float | None) -> float | int | None:
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


# ------------------------------------------------------------------ units

# canonical unit -> (kind, factor to the base unit g/ml, words)
_UNIT_DEFS: dict[str, tuple[str, float, tuple[str, ...]]] = {
    "g": ("mass", 1, ("g", "gr", "gram", "grams", "gramme", "grammes")),
    "kg": ("mass", 1000, ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms")),
    "mg": ("mass", 0.001, ("mg", "milligram", "milligrams")),
    "oz": ("mass", 28.3495, ("oz", "ounce", "ounces")),
    "lb": ("mass", 453.592, ("lb", "lbs", "pound", "pounds")),
    "ml": ("volume", 1, ("ml", "milliliter", "milliliters", "millilitre", "millilitres")),
    "cl": ("volume", 10, ("cl", "centiliter", "centiliters", "centilitre", "centilitres")),
    "dl": ("volume", 100, ("dl", "deciliter", "deciliters", "decilitre", "decilitres")),
    "l": ("volume", 1000, ("l", "ltr", "liter", "liters", "litre", "litres")),
    "cup": ("volume", 240, ("cup", "cups")),
    "fl oz": ("volume", 30, ("fl oz", "fl. oz", "fl.oz", "fluid ounce", "fluid ounces", "fluid oz")),
    "pint": ("volume", 475, ("pint", "pints", "pt")),
    "quart": ("volume", 950, ("quart", "quarts", "qt")),
    "gallon": ("volume", 3800, ("gallon", "gallons", "gal")),
    "tsp": ("spoon", 1, ("tsp", "tsps", "teaspoon", "teaspoons", "tl", "theelepel", "theelepels", "kl", "koffielepel", "koffielepels")),
    "tbsp": ("spoon", 1, ("tbsp", "tbsps", "tablespoon", "tablespoons", "el", "eetlepel", "eetlepels")),
    "clove": ("count", 1, ("clove", "cloves", "teen", "tenen", "teentje", "teentjes")),
    "pinch": ("count", 1, ("pinch", "pinches", "snuf", "snufje", "snufjes")),
    "can": ("count", 1, ("can", "cans", "tin", "tins", "blik", "blikje", "blikken", "blikjes")),
    "bunch": ("count", 1, ("bunch", "bunches", "bos", "bosje", "bosjes")),
    "slice": ("count", 1, ("slice", "slices", "plak", "plakje", "plakjes", "plakken", "sneetje", "sneetjes")),
    "stick": ("count", 1, ("stick", "sticks")),
    "stalk": ("count", 1, ("stalk", "stalks", "stengel", "stengels", "steel")),
    "sprig": ("count", 1, ("sprig", "sprigs", "takje", "takjes", "tak")),
    "handful": ("count", 1, ("handful", "handfuls", "handvol", "handjevol")),
    "piece": ("count", 1, ("piece", "pieces")),
    "dash": ("count", 1, ("dash", "dashes", "splash", "splashes", "drizzle", "scheut", "scheutje", "scheutjes")),
    "package": ("count", 1, ("package", "packages", "pack", "packs", "packet", "packets", "pak", "pakje", "pakken", "pakjes", "zakje", "zakjes")),
    "head": ("count", 1, ("head", "heads", "krop", "kroppen")),
    "bag": ("count", 1, ("bag", "bags", "zak", "zakken")),
    "jar": ("count", 1, ("jar", "jars", "potje", "potjes")),
    "leaf": ("count", 1, ("leaf", "leaves", "blad", "blaadjes", "bladeren")),
    "drop": ("count", 1, ("drop", "drops", "druppel", "druppels")),
    "knob": ("count", 1, ("knob", "knobs", "klont", "klontje")),
    # Dutch "stuk(s)" only says "countable": no unit, like "2 eggs".
    "": ("count", 1, ("stuk", "stuks", "stukje", "stukjes")),
}
_UNIT_LOOKUP: dict[str, str] = {}
for _canon, (_kind, _factor, _words) in _UNIT_DEFS.items():
    for _word in _words:
        _UNIT_LOOKUP[_word] = _canon
_UNIT_RE = re.compile(
    r"(?P<u>" + "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in sorted(_UNIT_LOOKUP, key=len, reverse=True))
    + r")(?:\.(?!\w)|(?![A-Za-zÀ-ÿ]))",
    re.IGNORECASE,
)

# Grams per US cup (240 ml) of common dry goods; the lookup takes the longest name that matches.
DENSITY_G_PER_CUP: dict[str, float] = {
    "all-purpose flour": 125, "all purpose flour": 125, "plain flour": 125, "bread flour": 130,
    "whole wheat flour": 120, "wholemeal flour": 120, "cake flour": 115, "self-raising flour": 125,
    "self-rising flour": 125, "almond flour": 96, "flour": 125, "bloem": 125, "tarwebloem": 125,
    "powdered sugar": 120, "icing sugar": 120, "confectioners sugar": 120, "confectioners' sugar": 120,
    "poedersuiker": 120, "brown sugar": 215, "light brown sugar": 215, "dark brown sugar": 215,
    "bruine suiker": 215, "caster sugar": 200, "granulated sugar": 200, "sugar": 200, "suiker": 200,
    "basmati rice": 185, "jasmine rice": 185, "long grain rice": 185, "rice": 185, "rijst": 185,
    "rolled oats": 90, "oats": 90, "haver": 90, "havermout": 90, "cocoa powder": 85, "cocoa": 85, "cacao": 85,
    "cornstarch": 130, "corn starch": 130, "maizena": 130, "butter": 227, "boter": 227,
    "honey": 340, "honing": 340, "peanut butter": 260, "pindakaas": 260, "chocolate chips": 170,
    "breadcrumbs": 110, "panko": 60, "semolina": 170, "couscous": 175, "lentils": 190, "linzen": 190,
    "quinoa": 170, "grated parmesan": 100, "parmesan": 100, "shredded cheese": 115, "grated cheese": 115,
    "raisins": 150, "rozijnen": 150, "walnuts": 120, "almonds": 140, "amandelen": 140,
}
_DENSITY_KEYS = sorted(DENSITY_G_PER_CUP, key=len, reverse=True)


def density_for(name: str) -> float | None:
    """Grams per cup for an ingredient name, or None when we don't know it."""
    lowered = (name or "").lower()
    if re.search(r"cooked|gekookt|boiled|leftover|soaked", lowered):
        return None  # the table is for dry goods
    for key in _DENSITY_KEYS:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            return DENSITY_G_PER_CUP[key]
    return None


# Conventional rounding of common US package sizes (oz -> g).
_OZ_SNAP = {1: 30, 2: 55, 3: 85, 4: 115, 5: 140, 6: 170, 7: 200, 8: 225, 9: 250, 10: 285, 12: 340,
            14: 400, 15: 425, 16: 450, 28: 800, 32: 900}


def _round_amount(value: float) -> float | int:
    """Round for display: whole numbers from 20 up, nearest 5 from 50 up."""
    if value >= 50:
        return int(round(value / 5) * 5)
    if value >= 20:
        return int(round(value))
    if value >= 5:
        return round(value * 2) / 2 if value % 1 else int(value)
    return round(value, 2)


def _mass_to_metric(grams: float) -> tuple[float | int, str]:
    if grams >= 1000:
        return round(grams / 1000, 2), "kg"
    return _round_amount(grams), "g"


def _volume_to_metric(ml: float) -> tuple[float | int, str]:
    if ml >= 1000:
        return round(ml / 1000, 2), "l"
    return _round_amount(ml), "ml"


def to_metric(qty: float | None, unit: str, name: str = "") -> tuple[float | int | None, str | None, bool]:
    """Convert (qty, canonical unit) to metric. Returns (qty, unit, converted?).

    cups of flour/sugar/rice (see DENSITY_G_PER_CUP) become grams, other cups ml.
    Units that are fine in a metric kitchen (tsp, tbsp, pinch ...) stay as they are.
    """
    if qty is None:
        return None, unit or None, False
    kind, factor, _ = _UNIT_DEFS.get(unit, ("count", 1, ()))
    if unit == "oz":
        grams = _OZ_SNAP.get(qty) if float(qty).is_integer() and int(qty) in _OZ_SNAP else qty * factor
        return (*_mass_to_metric(grams), True)
    if unit == "lb":
        ounces = qty * 16
        grams = _OZ_SNAP.get(int(ounces)) if float(ounces).is_integer() and int(ounces) in _OZ_SNAP else qty * factor
        return (*_mass_to_metric(grams), True)
    if unit == "cup":
        if (density := density_for(name)) is not None:
            return (*_mass_to_metric(qty * density), True)
        return (*_volume_to_metric(qty * factor), True)
    if unit in ("fl oz", "pint", "quart", "gallon", "cl", "dl"):
        return (*_volume_to_metric(qty * factor), True)
    return _clean_number(qty), unit or None, False


# ------------------------------------------------------------------ ingredients

_LEAD_JUNK = re.compile(r"^[\s\-–—•*·▪◦☐☑✓✔►▶➤>]+")
_VAGUE_PREFIX = re.compile(
    r"^(?:a\s+(?:little|bit|touch)(?:\s+of)?|een\s+(?:beetje|klein\s+beetje)(?:\s+van)?|some|wat|a\s+few|een\s+paar)\s+",
    re.IGNORECASE,
)
_NOTE_SUFFIX = re.compile(
    r"\b(to taste|as needed|if needed|for serving|to serve|for garnish|for garnishing|for frying|for dusting|"
    r"naar smaak|voor erbij|ter garnering|om te bakken|optional|optioneel)\s*$",
    re.IGNORECASE,
)
_OF_PREFIX = re.compile(r"^(?:of|van)\s+", re.IGNORECASE)


def _paren_amount(inner: str) -> tuple[float, float | None, str, str] | None:
    """If a parenthesis is just an amount with a unit ("14 oz"), return qty, qty_max, unit, text."""
    match = _AMOUNT_RE.match(inner.strip())
    if not match:
        return None
    rest = inner.strip()[match.end():].strip()
    unit_match = _UNIT_RE.fullmatch(rest)
    if not unit_match:
        return None
    unit = _UNIT_LOOKUP[re.sub(r"\s+", " ", unit_match.group("u").lower())]
    if _UNIT_DEFS[unit][0] not in ("mass", "volume"):
        return None
    qty_max = _value(match.group("b")) if match.group("b") else None
    return _value(match.group("a")), qty_max, unit, inner.strip()


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if float(value).is_integer() else str(round(value, 2)).rstrip("0").rstrip(".")


def _lower_first(text: str) -> str:
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


def parse_ingredient(raw: str) -> dict[str, Any]:
    """Split "1½ cups flour, sifted" into qty, qty_max, unit, name, note and original.

    Metric units are kept. US/imperial ones are converted and the text as written goes in
    "original" ("1½ cups"). Works for English and Dutch ("een snuf zout", "2 el olie").
    """
    text = re.sub(r"\s+", " ", _LEAD_JUNK.sub("", raw or "")).strip()
    result: dict[str, Any] = {"qty": None, "qty_max": None, "unit": None, "name": text, "note": None, "original": None}
    if not text:
        return result

    qty: float | None = None
    qty_max: float | None = None
    rest = text
    amount_text = ""
    note_parts: list[str] = []

    if vague := _VAGUE_PREFIX.match(text):
        if not re.match(r"some|wat", vague.group(0), re.IGNORECASE):
            note_parts.append(re.sub(r"\s+(of|van)$", "", vague.group(0).strip(), flags=re.IGNORECASE))
        rest = text[vague.end():]
    elif half := _HALF_RE.match(text):
        qty, rest, amount_text = 0.5, text[half.end():], half.group(0).strip()
    elif match := _AMOUNT_RE.match(text):
        qty = _value(match.group("a"))
        qty_max = _value(match.group("b")) if match.group("b") else None
        rest = text[match.end():].lstrip()
        amount_text = text[: match.end()].strip()
    elif (word := _WORD_NUM_RE.match(text)) and text[word.end():].strip():
        qty = float(_WORD_NUMBERS[word.group("w").lower()])
        rest = text[word.end():].lstrip()
        amount_text = word.group("w")

    # "2 (14 oz) cans tomatoes": an amount in a parenthesis before the unit.
    paren_first = None
    if qty is not None and rest.startswith("("):
        close = rest.find(")")
        if close != -1 and (paren_first := _paren_amount(rest[1:close])):
            rest = rest[close + 1:].lstrip()

    unit = ""
    unit_text = ""
    if qty is not None or _UNIT_RE.match(rest):
        if unit_match := _UNIT_RE.match(rest):
            unit = _UNIT_LOOKUP[re.sub(r"\s+", " ", unit_match.group("u").lower())]
            unit_text = rest[: unit_match.end()].strip()
            tail = rest[unit_match.end():].lstrip()
            # "pinch of salt" / "1 cup of flour"
            rest = _OF_PREFIX.sub("", tail) if tail else tail
            if not tail and qty is None:
                unit = ""  # a lone word like "can" is a name, not a unit
    # "400 g (14 oz) tomatoes": the parenthesis right after the unit
    paren_after = None
    if rest.startswith("("):
        close = rest.find(")")
        if close != -1 and (paren_after := _paren_amount(rest[1:close])):
            rest = rest[close + 1:].lstrip()

    # Everything after the first comma is a note; parentheses in the name too.
    name, _, tail_note = rest.partition(",")
    for group in re.findall(r"\(([^()]*)\)", name):
        note_parts.append(group.strip())
    name = re.sub(r"\s*\([^()]*\)", "", name)
    name = _OF_PREFIX.sub("", name.strip()).strip(" .;:-–")
    if suffix := _NOTE_SUFFIX.search(name):
        note_parts.append(suffix.group(1).lower())
        name = name[: suffix.start()].strip(" ,.;:-–")
    if tail_note.strip():
        note_parts.append(tail_note.strip(" .;"))
    if not name:
        name = text  # nothing sensible found: keep the line as it is
        qty, qty_max, unit, amount_text, unit_text = None, None, "", "", ""

    original = None
    final_qty, final_max, final_unit = qty, qty_max, unit
    if qty is not None and unit:
        final_qty, final_unit, converted = to_metric(qty, unit, name)
        if converted:
            original = f"{amount_text} {unit_text}".strip()
            if qty_max is not None:
                max_qty, _, _ = to_metric(qty_max, unit, name)
                final_max = max_qty
        else:
            final_qty = _clean_number(qty)
            final_max = _clean_number(qty_max)
    elif qty is not None:
        final_qty, final_max = _clean_number(qty), _clean_number(qty_max)

    # A parenthesis with the other measuring system: keep as original (or convert into a note).
    for paren in (paren_first, paren_after):
        if not paren:
            continue
        p_qty, p_max, p_unit, p_text = paren
        if final_unit in ("g", "kg", "ml", "l") and original is None and p_unit in ("oz", "lb", "cup", "fl oz"):
            original = p_text
        elif final_unit in ("g", "kg", "ml", "l") and original is None:
            original = p_text
        else:
            m_qty, m_unit, converted = to_metric(p_qty, p_unit, name)
            note_parts.insert(0, f"{_fmt(m_qty)} {m_unit}")

    result.update(
        qty=_clean_number(final_qty),
        qty_max=_clean_number(final_max) if final_max else None,
        unit=final_unit or None,
        name=_lower_first(name),
        note=", ".join(p for p in note_parts if p) or None,
        original=original,
    )
    return result


# ------------------------------------------------------------------ temperatures and sizes

_OVEN_F_TO_C = {250: 120, 275: 140, 300: 150, 325: 165, 350: 180, 375: 190, 400: 200, 425: 220, 450: 230, 475: 245, 500: 260}
_TEMP_F_RE = re.compile(r"(?<![\d.])(\d{3})\s*(?:°|º|˚|degrees?\s+)\s*F(?:ahrenheit)?\b|(?<![\d.])(\d{3})\s*F\b")
_INCH_RE = re.compile(
    r"(?<![\d.])(?:(?P<a>\d+(?:[.,]\d+)?)\s*(?:x|×|by)\s*(?P<b>\d+(?:[.,]\d+)?)|(?P<s>\d+(?:[.,]\d+)?))"
    r"(?:\s*-\s*|\s+)?(?:inch(?:es)?|in\b\.?|\")(?!\w)",
    re.IGNORECASE,
)


def fahrenheit_to_celsius(fahrenheit: int) -> int:
    """Oven temperature in °C, using the conventional pairs (350 °F -> 180 °C)."""
    if fahrenheit in _OVEN_F_TO_C:
        return _OVEN_F_TO_C[fahrenheit]
    return int(round((fahrenheit - 32) * 5 / 9 / 5) * 5)


def convert_text(text: str) -> str:
    """Write °F as "200 °C (400 °F)" and inches as "23 cm (9 in)" inside a step."""

    def temp(match: re.Match[str]) -> str:
        before = text[max(0, match.start() - 14): match.start()]
        after = text[match.end(): match.end() + 14]
        if re.search(r"\d\s*[°º˚]?\s*C\s*[/(]?\s*$", before) or re.match(r"\s*[/(]?\s*\d+\s*[°º˚]?\s*C\b", after):
            return match.group(0)  # the metric value is already there
        fahrenheit = int(match.group(1) or match.group(2))
        if not 200 <= fahrenheit <= 600:
            return match.group(0)
        return f"{fahrenheit_to_celsius(fahrenheit)} °C ({fahrenheit} °F)"

    def inches(match: re.Match[str]) -> str:
        numbers = [float(match.group(g).replace(",", ".")) for g in ("a", "b", "s") if match.group(g)]
        if not numbers or any(not 0 < n <= 60 for n in numbers):
            return match.group(0)
        metric = " x ".join(str(int(round(n * 2.54))) for n in numbers)
        return f"{metric} cm ({' x '.join(_fmt(n) for n in numbers)} in)"

    return _INCH_RE.sub(inches, _TEMP_F_RE.sub(temp, text))


# ------------------------------------------------------------------ durations and timers

_DURATION_RE = re.compile(
    r"(?P<n>\d+(?:[.,]\d+)?)(?:\s*(?:-|–|to|tot)\s*(?P<n2>\d+(?:[.,]\d+)?))?"
    r"(?:\s*(?P<long>hours?|hrs?|uren|uur|minutes?|mins?|minuten|minuut|seconds?|secs?|seconden|seconde)\b"
    r"|(?P<short>[hms])\b)",
    re.IGNORECASE,
)
_HOUR_MIN_RE = re.compile(r"\b(\d+)\s*h\s*(\d{2})\b", re.IGNORECASE)
_WORD_DURATIONS = (
    (re.compile(r"\b(?:half an hour|een half uur|een halfuur|halfuur)\b", re.IGNORECASE), 1800),
    (re.compile(r"\b(?:an hour|one hour|een uur)\b", re.IGNORECASE), 3600),
    (re.compile(r"\b(?:overnight|overnacht|de hele nacht)\b", re.IGNORECASE), 8 * 3600),
)
_JOIN_RE = re.compile(r"^\s*(?:,|&|and|en)?\s*$", re.IGNORECASE)


def _unit_seconds(unit: str) -> int:
    unit = unit.lower()
    if unit.startswith(("h", "u")):
        return 3600
    if unit.startswith("s"):
        return 1
    return 60


def _duration_matches(text: str) -> list[tuple[int, int, int]]:
    """(start, end, seconds) of every duration in the text; "1 hour 30 minutes" counts once."""
    found: list[tuple[int, int, int]] = []
    taken: list[tuple[int, int]] = []
    for match in _HOUR_MIN_RE.finditer(text):
        found.append((match.start(), match.end(), int(match.group(1)) * 3600 + int(match.group(2)) * 60))
        taken.append((match.start(), match.end()))
    for match in _DURATION_RE.finditer(text):
        if any(s <= match.start() < e for s, e in taken):
            continue
        value = float(match.group("n").replace(",", "."))  # a range uses its lower bound
        found.append((match.start(), match.end(), int(value * _unit_seconds(match.group("long") or match.group("short")))))
    for pattern, seconds in _WORD_DURATIONS:
        for match in pattern.finditer(text):
            if not any(s <= match.start() < e for s, e, _ in found):
                found.append((match.start(), match.end(), seconds))
    found.sort()
    merged: list[tuple[int, int, int]] = []
    for item in found:
        if merged and _JOIN_RE.match(text[merged[-1][1]: item[0]]) and item[2] < merged[-1][2]:
            start, _, seconds = merged[-1]
            merged[-1] = (start, item[1], seconds + item[2])  # 1 h + 30 min
        else:
            merged.append(item)
    return merged


def find_durations(text: str) -> list[int]:
    """Durations (seconds) mentioned in a step, for the timer buttons."""
    return [s for _, _, s in _duration_matches(text) if 10 <= s <= 48 * 3600]


_VERB_LABELS = {
    "bake": "Bake", "bak": "Bake", "simmer": "Simmer", "sudder": "Simmer", "boil": "Boil",
    "kook": "Cook", "cook": "Cook", "fry": "Fry", "braad": "Fry", "saut": "Sauté", "roast": "Roast",
    "rooster": "Roast", "grill": "Grill", "sear": "Sear", "toast": "Toast", "rest": "Rest", "rust": "Rest",
    "marinate": "Marinate", "marineer": "Marinate", "chill": "Chill", "refrigerate": "Chill", "koel": "Chill",
    "freeze": "Freeze", "vries": "Freeze", "rise": "Rise", "proof": "Rise", "rijzen": "Rise", "steep": "Steep",
    "soak": "Soak", "week": "Soak", "cool": "Cool", "knead": "Knead", "kneed": "Knead", "steam": "Steam",
    "stoom": "Steam", "braise": "Braise", "stoof": "Braise", "reduce": "Reduce", "whisk": "Whisk",
    "blend": "Blend", "stir": "Stir", "roer": "Stir", "mix": "Mix", "sit": "Rest", "stand": "Rest",
    "let": "Rest", "laat": "Rest", "leave": "Rest", "heat": "Heat", "verwarm": "Heat", "preheat": "Preheat",
    "drain": "Drain", "set": "Set", "infuse": "Steep", "poach": "Poach", "pocheer": "Poach",
}
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+")


def _label_for(text: str, start: int) -> str | None:
    """Name a timer after the cooking verb in the part of the sentence before the time."""
    prefix = re.split(r"[.;!?]\s", text[:start])[-1][-80:]
    label = None
    for word in _WORD_RE.findall(prefix):
        lowered = word.lower()
        for stem, name in _VERB_LABELS.items():
            if lowered.startswith(stem):
                label = name
                break
    return label


def find_timers(text: str, limit: int = 3) -> list[dict[str, Any]]:
    """Timer buttons for a step: [{"seconds": 600, "label": "Simmer"}]."""
    timers = []
    for start, _, seconds in _duration_matches(text):
        if 10 <= seconds <= 48 * 3600:
            timers.append({"seconds": seconds, "label": _label_for(text, start)})
    return timers[:limit]
