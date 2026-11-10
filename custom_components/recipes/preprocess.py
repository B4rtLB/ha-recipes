"""Cut source material down to what a small model needs: the recipe and nothing else.

Hashtags, emoji, "follow me" lines and everything outside the ingredient and step sections
cost tokens and confuse small models. Pure Python, no Home Assistant imports.
"""

from __future__ import annotations

import re

_EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\U0001f000-\U0001f2ff\U0001f1e6-\U0001f1ff☀-➿⬀-⯿"
    "️‍⃣⌀-⏿■-◿]"
)
_HASHTAG_RE = re.compile(r"(?<![\w&])#[\w\-]+", re.UNICODE)
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<![\w.])@[\w.]{2,}")
_AMOUNT_RE = re.compile(
    r"\d\s*(?:g|gr|kg|ml|cl|dl|l|tbsp|tsp|el|tl|cups?|oz|lbs?|gram|grams|cloves?|teen|tenen|can|blik)\b"
    r"|[½¼¾⅓⅔]\s*(?:cup|tsp|tbsp|el|tl)",
    re.IGNORECASE,
)
_PROMO_RE = re.compile(
    r"follow (?:me|us|my|for|@)|volg (?:mij|ons|me|voor|mijn)|link in (?:my |mijn )?bio|like (?:and|&|en) subscribe|"
    r"\bsubscribe\b|abonneer|save (?:this|it)\b|bewaar (?:dit|deze)|share (?:this|it) with|tag (?:a|your|someone)|"
    r"comment\b.{0,40}\b(?:recipe|recept|link)|dm me|stuur (?:me )?een dm|check out my|check mijn|"
    r"full recipe (?:is |can be found )?(?:on|in|at)|volledig recept|thanks? for watching|bedankt voor het kijken|"
    r"turn on (?:post )?notifications|discount code|kortingscode|use code|sponsored|\badvertisement\b|affiliate|"
    r"my (?:new )?(?:cookbook|book|ebook)|mijn (?:nieuwe )?(?:kookboek|boek)|let me know (?:in the comments|how)|"
    r"laat (?:het )?(?:me )?weten|part \d+ of|credits?:|music:|muziek:",
    re.IGNORECASE,
)

_BULLETS = "-–—•*·▪◦☐☑✓✔►▶➤>"
_ING_HEAD = re.compile(
    r"^(?:the\s+)?(?:ingredients?|ingredi[eë]nten|ingredienten|what you(?:'|’)?(?:ll| will)? ?need|you(?:'|’)?(?:ll| will) need|"
    r"benodigdheden|wat heb je nodig|shopping list|boodschappen(?:lijst)?)(?:\s*\(.*\))?\s*:?$",
    re.IGNORECASE,
)
_STEP_HEAD = re.compile(
    r"^(?:the\s+)?(?:instructions?|directions?|method|steps?|preparation|how to (?:make|cook|prepare)(?: it)?|"
    r"bereiding(?:swijze)?|werkwijze|zo maak je (?:het|dit)|instructies|aan de slag)\s*:?$",
    re.IGNORECASE,
)
_END_HEAD = re.compile(
    r"^(?:nutrition(?:al)?(?: (?:info|information|facts|per serving))?|voedingswaarde|comments?|reacties|"
    r"related (?:recipes?|posts?)|more recipes|leave a (?:comment|reply)|reviews?|you (?:might|may) also like|"
    r"share this|print recipe|rate this recipe|tags?|categories|about the author|subscribe|newsletter|"
    r"recent posts|popular recipes|verwante recepten|meer recepten|reageer)\b",
    re.IGNORECASE,
)
_META_LINE = re.compile(
    r"^(?:servings?|serves|yield|makes|portions?|porties|personen|prep(?:aration)?(?: time)?|cook(?: time)?|total(?: time)?|"
    r"bereidingstijd|kooktijd|oventemperatuur|oven)\b.{0,70}$",
    re.IGNORECASE,
)


def _line_key(line: str) -> str:
    return _EMOJI_RE.sub("", line).strip().strip(_BULLETS + " \t#*_:").strip()


def strip_noise(text: str, *, drop_promo: bool = True) -> str:
    """Remove emoji, hashtags, links, @mentions and "follow me" lines. Keeps line breaks."""
    out: list[str] = []
    for raw in (text or "").replace("\r", "").split("\n"):
        line = _URL_RE.sub(" ", raw)
        line = _EMOJI_RE.sub("", line)
        line = _HASHTAG_RE.sub(" ", line)
        line = _MENTION_RE.sub(" ", line)
        line = re.sub(r"[ \t\xa0]+", " ", line).strip()
        if not line:
            if out and out[-1] != "":
                out.append("")  # one blank line keeps the paragraph structure
            continue
        if drop_promo and len(line) <= 220 and _PROMO_RE.search(line) and not _AMOUNT_RE.search(line):
            continue
        if not re.search(r"\w", line):
            continue  # only punctuation left, like "---" or "• •"
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def focus_recipe(text: str, limit: int = 12000, *, first_line_is_title: bool = True) -> str:
    """Keep the title, servings/time lines and the ingredient and step sections.

    Works on headings ("Ingredients", "Method", "Bereiding") and, without headings, on the
    first line that looks like an ingredient. Falls back to the whole text when unsure.
    """
    lines = [ln for ln in text.split("\n")]
    keyed = [_line_key(ln) for ln in lines]
    ing = next((i for i, k in enumerate(keyed) if len(k) <= 48 and _ING_HEAD.match(k)), None)
    step = next((i for i, k in enumerate(keyed) if len(k) <= 48 and _STEP_HEAD.match(k) and (ing is None or i > ing)), None)
    if ing is not None:
        start = ing
    elif step is not None:
        start = next((i for i in range(step) if _AMOUNT_RE.search(lines[i])), step)
    else:
        start = next((i for i, ln in enumerate(lines) if _AMOUNT_RE.search(ln)), 0)

    end = len(lines)
    after = max(start, step or 0) if step is not None else start
    for i in range(after + 1, len(lines)):
        if len(keyed[i]) <= 48 and _END_HEAD.match(keyed[i]):
            end = i
            break

    head: list[str] = []
    if start > 0:
        before = [ln for ln in lines[:start] if ln.strip()]
        if before and before[0].startswith("Title: "):
            head.append(before[0])  # the page title, added by the web fetch
        elif first_line_is_title and before and len(before[0]) <= 140:
            head.append(before[0])  # a caption usually starts with the dish name
        head += [ln for ln in before[1:] if _META_LINE.match(_line_key(ln))][:5]
    body = "\n".join(lines[start:end]).strip()
    focused = "\n".join([*head, body]).strip() if head else body
    if len(focused) < 60:
        return text[:limit]
    return focused[:limit]


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def clean_transcript(text: str, limit: int = 6000) -> str:
    """Speech transcript without the channel promo sentences, capped in length."""
    kept = [s for s in _SENTENCE_RE.split(re.sub(r"\s+", " ", text or "").strip()) if not _PROMO_RE.search(s)]
    out = " ".join(kept).strip()
    return out[:limit]


_LABEL_RE = re.compile(r"^(?P<label>[A-Z][A-Z .()/-]{3,60}[A-Z)]):\n(?P<body>.*)$", re.DOTALL)


def prepare(material: list[str]) -> list[str]:
    """Clean every labeled block of the material for the lean prompt.

    JSON-LD (already compact) and the user's own notes are kept as they are, apart from
    emoji and hashtags.
    """
    prepared = []
    for block in material:
        match = _LABEL_RE.match(block)
        if not match:
            if cleaned := strip_noise(block):
                prepared.append(cleaned)
            continue
        label, body = match.group("label"), match.group("body")
        if label.startswith("SCHEMA.ORG"):
            prepared.append(block)
            continue
        if label.startswith("SPEECH TRANSCRIPT"):
            cleaned = clean_transcript(strip_noise(body, drop_promo=False))
        elif label.startswith("RECIPE TEXT"):
            cleaned = strip_noise(body, drop_promo=False)
        elif label.startswith("WEB PAGE"):
            cleaned = focus_recipe(strip_noise(body), 12000, first_line_is_title=False)
        else:  # social media caption and anything else
            cleaned = focus_recipe(strip_noise(body), 6000)
        if cleaned:
            prepared.append(f"{label}:\n{cleaned}")
    return prepared
