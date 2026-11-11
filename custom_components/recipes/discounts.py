"""Supermarket discounts: validation and matching against recipe ingredients.

Pure Python, no Home Assistant imports (golden-tested in dev/test_parser.py).

Discounts are stored per supermarket as
    {"valid_from": "2026-11-09", "valid_to": "2026-11-15",
     "items": [{"name": "Kipfilet", "terms": ["kipfilet", "chicken breast"],
                "price": "€4.99", "was": "€6.49", "note": "2e halve prijs"}]}
An item may also carry its own "valid_from" / "valid_to" (default: the list's period).
Recipes are written in English while the supermarkets are Dutch, so matching is
done on ``terms``: normalised keywords in Dutch AND English that whoever feeds the
data supplies. An ingredient matches an item when ALL tokens of ONE of its terms
appear as whole words in the ingredient name and the ingredient has no other meaningful
word (preparation words like "sliced" or "boneless" are ignored, see IGNORABLE). So
"chicken breast" matches "boneless chicken breast, diced", but "chicken" matches only an
ingredient called just "chicken", and "garlic" does not match "garlic powder".
"""

from __future__ import annotations

from datetime import date
import re
import unicodedata
from typing import Any

# key -> display name, in the order they are shown
STORES: dict[str, str] = {"ah": "Albert Heijn", "jumbo": "Jumbo", "lidl": "Lidl", "dirk": "Dirk"}

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _strip_plural(word: str) -> str:
    """Very simple singular: -en (Dutch), -es, -s. Applied to both sides of a match."""
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes", "oes", "en")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """Lowercase, no accents or punctuation, plurals stripped: "Crème fraîches" -> ["creme", "fraich"]."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    # twice, so "chickens" and "chicken" end up the same word ("chicken" itself loses its -en)
    return [_strip_plural(_strip_plural(w)) for w in _TOKEN_RE.split(text) if w]


# Words in an ingredient name that do not make it a different ingredient: preparation, size, freshness.
# "sliced cucumber" is cucumber, "garlic powder" and "smoked paprika" are not garlic or paprika.
IGNORABLE = frozenset(
    tokens(
        "fresh freshly ripe large big medium small baby young whole raw organic free-range freerange boneless "
        "skinless skin-on bone-in sliced slice chopped diced minced grated shredded crushed peeled roasted "
        "toasted trimmed halved quartered cubed finely roughly thinly thickly coarsely optional extra virgin "
        "good-quality quality plain clove cloves juice zest wedge wedges piece pieces bunch handful sprig "
        "leaf leaves of or and the a an to for taste serving garnish cut into"
    )
)


# -ed words that change the product ("smoked paprika", "dried oregano"), everything else ending in
# -ed or -ly is treated as preparation ("softened", "finely").
MEANINGFUL_ED = frozenset(
    tokens("smoked dried cured salted unsalted sweetened unsweetened powdered pickled fermented condensed evaporated "
           "canned jarred bottled frozen blanched sundried sun-dried")
)


def _ignorable(word: str) -> bool:
    return (
        word in IGNORABLE
        or word.isdigit()
        or (len(word) >= 5 and word.endswith(("ed", "ly")) and word not in MEANINGFUL_ED)
    )


def term_matches(ingredient: str, term: str) -> bool:
    """All words of the term are in the ingredient and nothing else meaningful is.

    "chicken breast" matches "boneless chicken breast, diced" (boneless and diced are only
    preparation), but "garlic" does not match "garlic powder" and "oil" does not match "olive oil".
    """
    want = tokens(term)
    if not want:
        return False
    have = tokens(ingredient)
    if not all(t in have for t in want):
        return False
    return all(t in want or _ignorable(t) for t in have)


def item_matches(ingredient: str, item: dict[str, Any]) -> bool:
    """Whether the ingredient name matches any term of a discount item."""
    return any(term_matches(ingredient, t) for t in item.get("terms") or [])


def parse_price(text: Any) -> float | None:
    """"€4.99" / "4,99" / "EUR 4.99" -> 4.99, anything else None."""
    m = re.search(r"(\d+)(?:[.,](\d{1,2}))?", str(text or ""))
    if not m:
        return None
    return float(f"{m.group(1)}.{m.group(2) or '0'}")


def clean_store(store: str, valid_from: Any, valid_to: Any, items: Any) -> dict[str, Any]:
    """Validate one supermarket's list and return what is stored. Raises ValueError."""
    if store not in STORES:
        raise ValueError(f"Unknown store {store!r}; use one of {', '.join(STORES)}")
    try:
        d_from, d_to = date.fromisoformat(str(valid_from)), date.fromisoformat(str(valid_to))
    except ValueError as err:
        raise ValueError("valid_from and valid_to must be dates like 2026-11-09") from err
    if d_to < d_from:
        raise ValueError("valid_to is before valid_from")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            raise ValueError(f"item {i} needs a name")
        name = str(item["name"]).strip()
        terms = item.get("terms")
        if terms is None:
            terms = [name]
        if not isinstance(terms, list) or not [t for t in terms if tokens(t)]:
            raise ValueError(f"item {name!r}: terms must be a list with at least one keyword")
        clean = {"name": name, "terms": [str(t).strip() for t in terms if tokens(t)]}
        for key in ("price", "was", "note"):
            if item.get(key) not in (None, ""):
                clean[key] = str(item[key]).strip()
        # Optional own period: shops start and end offers on different days within one list.
        for key in ("valid_from", "valid_to"):
            if item.get(key) not in (None, ""):
                try:
                    clean[key] = date.fromisoformat(str(item[key])).isoformat()
                except ValueError as err:
                    raise ValueError(f"item {name!r}: {key} must be a date like 2026-11-09") from err
        out.append(clean)
    return {"valid_from": d_from.isoformat(), "valid_to": d_to.isoformat(), "items": out}


def active_stores(data: dict[str, Any], today: str) -> dict[str, dict[str, Any]]:
    """The stores whose list is valid today (ISO date in the local timezone). Expired lists count as none."""
    out = {}
    for key, entry in ((data or {}).get("stores") or {}).items():
        if key not in STORES or not entry.get("valid_from", "") <= today <= entry.get("valid_to", ""):
            continue
        # items may carry their own period; the list's period is the default
        items = [
            i for i in entry.get("items") or []
            if i.get("valid_from", entry["valid_from"]) <= today <= i.get("valid_to", entry["valid_to"])
        ]
        if items:
            out[key] = {**entry, "items": items}
    return out


def match_ingredient(name: str, stores: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Offers for one ingredient, in store order: [{store, item, price, was, note}]."""
    offers = []
    for key in STORES:
        for item in (stores.get(key) or {}).get("items", []):
            if item_matches(name, item):
                offers.append({"store": key, "item": item["name"],
                               **{k: item[k] for k in ("price", "was", "note") if k in item}})
                break  # one offer per store and ingredient
    return offers


def best_offer(offers: list[dict[str, Any]]) -> str:
    """Store key to glow in: the cheapest when every price parses, else the first."""
    prices = [parse_price(o.get("price")) for o in offers]
    if offers and all(p is not None for p in prices):
        return offers[min(range(len(offers)), key=lambda i: prices[i])]["store"]
    return offers[0]["store"]


def match_recipe(recipe: dict[str, Any], stores: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Discounted ingredient lines of a recipe: {"<group>.<item>": {"best": store, "offers": [...]}}.

    The keys are the same as the ones the app uses for its ingredient checkboxes.
    """
    lines = {}
    for gi, group in enumerate(recipe.get("ingredient_groups") or []):
        for ii, item in enumerate(group.get("items") or []):
            offers = match_ingredient(item.get("name") or "", stores)
            if offers:
                lines[f"{gi}.{ii}"] = {"best": best_offer(offers), "offers": offers}
    return lines


def match_all(recipes: list[dict[str, Any]], stores: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{recipe id: {"count": discounted lines, "lines": {...}}} for ready recipes with at least one match."""
    out = {}
    if not stores:
        return out
    for recipe in recipes:
        if recipe.get("status") != "ready":
            continue
        lines = match_recipe(recipe, stores)
        if lines:
            out[recipe["id"]] = {"count": len(lines), "lines": lines}
    return out
