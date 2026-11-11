"""Search words (terms) for supermarket offers: Dutch and English, so English recipes match Dutch shops.

Two sources, combined:
- a built-in Dutch to English word list (free, covers the common ingredients),
- the configured AI Task, asked in batches, which also says which offers are not ingredients at all.
Pure Python; the AI call is passed in as a function so it can be tested.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

# (Dutch words, English terms). A Dutch word matches a word of the product name when it is
# that word or its end (Dutch compounds put the head last: "rundergehakt" ends in "gehakt").
DICTIONARY: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("kipfilet", "kipfiletstukjes", "kipborst"), ("chicken breast", "chicken fillet")),
    (("kippendij", "kippendijfilet", "kipdij", "dijfilet"), ("chicken thigh",)),
    (("kipdrumstick", "drumstick", "kippenpoot"), ("chicken drumstick", "chicken leg")),
    (("kip", "kippen"), ("chicken",)),
    (("rundergehakt",), ("ground beef", "minced beef", "beef mince")),
    (("varkensgehakt",), ("ground pork", "minced pork", "pork mince")),
    (("gehakt",), ("minced meat", "ground meat")),
    (("biefstuk", "entrecote", "ribeye", "rosbief"), ("steak", "beef steak")),
    (("rundvlees", "stoofvlees", "riblap"), ("beef",)),
    (("speklapjes", "spekjes", "spek", "bacon", "ontbijtspek"), ("bacon",)),
    (("ham", "achterham"), ("ham",)),
    (("worst", "rookworst", "braadworst"), ("sausage",)),
    (("chorizo",), ("chorizo",)),
    (("varkensvlees", "varkenshaas", "procureur", "karbonade"), ("pork",)),
    (("lamsvlees", "lam"), ("lamb",)),
    (("zalm", "zalmfilet"), ("salmon",)),
    (("kabeljauw",), ("cod",)),
    (("tonijn",), ("tuna",)),
    (("garnalen", "garnaal"), ("shrimp", "prawn")),
    (("makreel",), ("mackerel",)),
    (("haring",), ("herring",)),
    (("pangasius", "witvis", "visfilet"), ("white fish", "fish fillet")),
    (("eieren", "ei"), ("egg",)),
    (("melk", "halfvolle melk", "volle melk"), ("milk",)),
    (("yoghurt",), ("yogurt", "yoghurt")),
    (("kwark",), ("quark",)),
    (("slagroom",), ("whipping cream", "heavy cream")),
    (("kookroom", "room"), ("cream", "cooking cream")),
    (("crème fraîche", "creme fraiche"), ("creme fraiche", "sour cream")),
    (("boter", "roomboter"), ("butter",)),
    (("geraspte kaas",), ("grated cheese", "shredded cheese")),
    (("feta",), ("feta",)),
    (("mozzarella",), ("mozzarella",)),
    (("parmezaanse kaas", "parmezaan", "parmigiano"), ("parmesan",)),
    (("roomkaas", "smeerkaas"), ("cream cheese",)),
    (("mascarpone",), ("mascarpone",)),
    (("ricotta",), ("ricotta",)),
    (("kaas", "kaasplakken"), ("cheese",)),
    (("spaghetti",), ("spaghetti",)),
    (("penne",), ("penne",)),
    (("macaroni",), ("macaroni",)),
    (("lasagne", "lasagnebladen"), ("lasagne sheets", "lasagna")),
    (("noedels", "mie", "mihoen", "udon"), ("noodles",)),
    (("pasta", "tagliatelle", "fusilli", "farfalle"), ("pasta",)),
    (("basmatirijst", "basmati"), ("basmati rice", "rice")),
    (("rijst", "zilvervliesrijst"), ("rice",)),
    (("couscous",), ("couscous",)),
    (("bulgur",), ("bulgur",)),
    (("quinoa",), ("quinoa",)),
    (("zoete aardappel", "zoete aardappelen", "bataat"), ("sweet potato",)),
    (("aardappelen", "aardappel", "aardappels", "krieltjes"), ("potato", "potatoes")),
    (("friet", "frites"), ("fries", "french fries")),
    (("gnocchi",), ("gnocchi",)),
    (("tomaten", "tomaat", "trostomaten", "cherrytomaten", "snoeptomaten"), ("tomato", "tomatoes")),
    (("uien", "ui", "rode uien", "sjalotten", "lente-ui", "bosui"), ("onion", "shallot", "spring onion")),
    (("knoflook",), ("garlic",)),
    (("paprika", "paprika's", "puntpaprika", "puntpaprika's"), ("bell pepper",)),
    (("wortelen", "wortel", "winterpeen", "peen"), ("carrot", "carrots")),
    (("broccoli",), ("broccoli",)),
    (("bloemkool",), ("cauliflower",)),
    (("spinazie",), ("spinach",)),
    (("courgette",), ("zucchini", "courgette")),
    (("aubergine",), ("eggplant", "aubergine")),
    (("champignons", "champignon", "paddenstoelen", "oesterzwammen", "kastanjechampignons"), ("mushroom", "mushrooms")),
    (("ijsbergsla", "sla", "romaine", "little gem", "andijvie"), ("lettuce", "salad")),
    (("komkommer",), ("cucumber",)),
    (("prei",), ("leek",)),
    (("mais", "maiskolven", "suikermais"), ("corn", "sweetcorn")),
    (("avocado", "avocado's"), ("avocado",)),
    (("pompoen", "butternut"), ("pumpkin", "butternut squash")),
    (("bieten", "rode bieten"), ("beetroot",)),
    (("rucola",), ("arugula", "rocket")),
    (("spitskool", "witte kool", "rode kool", "savooiekool"), ("cabbage",)),
    (("witlof",), ("chicory", "endive")),
    (("sperziebonen", "snijbonen", "boontjes"), ("green beans",)),
    (("doperwten", "erwten", "peultjes", "sugarsnaps"), ("peas",)),
    (("wokgroenten", "roerbakgroenten", "soepgroenten"), ("stir fry vegetables", "mixed vegetables")),
    (("kikkererwten",), ("chickpeas",)),
    (("kidneybonen", "kidney bonen"), ("kidney beans",)),
    (("witte bonen", "cannellinibonen"), ("white beans", "cannellini beans")),
    (("bruine bonen", "zwarte bonen"), ("beans",)),
    (("linzen",), ("lentils",)),
    (("tofu",), ("tofu",)),
    (("tempeh",), ("tempeh",)),
    (("hummus",), ("hummus",)),
    (("appels", "appel"), ("apple",)),
    (("peren", "peer"), ("pear",)),
    (("bananen", "banaan"), ("banana",)),
    (("citroenen", "citroen"), ("lemon",)),
    (("limoenen", "limoen"), ("lime",)),
    (("sinaasappels", "sinaasappel", "handsinaasappels"), ("orange",)),
    (("mandarijnen", "mandarijn", "clementines"), ("mandarin", "tangerine")),
    (("druiven",), ("grapes",)),
    (("aardbeien", "aardbei"), ("strawberry", "strawberries")),
    (("blauwe bessen", "bosbessen"), ("blueberries",)),
    (("frambozen", "framboos"), ("raspberries",)),
    (("mango", "mango's"), ("mango",)),
    (("ananas",), ("pineapple",)),
    (("meloen", "watermeloen"), ("melon",)),
    (("kiwi", "kiwi's"), ("kiwi",)),
    (("pesto",), ("pesto",)),
    (("tomatenpuree",), ("tomato paste",)),
    (("passata", "gezeefde tomaten", "tomatenblokjes", "tomatenstukjes"), ("passata", "canned tomatoes", "chopped tomatoes")),
    (("tomatensaus", "pastasaus"), ("tomato sauce", "pasta sauce")),
    (("ketchup",), ("ketchup",)),
    (("mayonaise",), ("mayonnaise",)),
    (("mosterd",), ("mustard",)),
    (("sojasaus", "ketjap", "ketjap manis"), ("soy sauce",)),
    (("sambal",), ("sambal", "chili paste")),
    (("currypasta", "kerriepasta"), ("curry paste",)),
    (("kokosmelk",), ("coconut milk",)),
    (("olijfolie",), ("olive oil",)),
    (("zonnebloemolie", "olie", "bak- en braadolie"), ("oil", "sunflower oil")),
    (("azijn", "balsamico"), ("vinegar", "balsamic vinegar")),
    (("bouillon", "bouillonblokjes", "fond"), ("stock", "broth", "bouillon")),
    (("kerrie", "kerriepoeder", "currypoeder"), ("curry powder",)),
    (("komijn", "djinten"), ("cumin",)),
    (("kaneel",), ("cinnamon",)),
    (("paprikapoeder",), ("paprika powder", "paprika")),
    (("peper",), ("pepper", "black pepper")),
    (("zout", "zeezout"), ("salt",)),
    (("kruiden", "specerijen"), ("spices", "herbs")),
    (("suiker", "kristalsuiker", "basterdsuiker", "poedersuiker"), ("sugar",)),
    (("bloem", "tarwebloem", "bakmeel", "zelfrijzend bakmeel"), ("flour", "all-purpose flour")),
    (("bakpoeder",), ("baking powder",)),
    (("gist",), ("yeast",)),
    (("honing",), ("honey",)),
    (("pindakaas",), ("peanut butter",)),
    (("jam",), ("jam",)),
    (("chocolade", "pure chocolade"), ("chocolate",)),
    (("amandelen", "amandel"), ("almonds",)),
    (("walnoten",), ("walnuts",)),
    (("cashewnoten", "cashew", "cashews"), ("cashews",)),
    (("pinda's", "pindas"), ("peanuts",)),
    (("noten", "notenmix"), ("nuts", "mixed nuts")),
    (("rozijnen",), ("raisins",)),
    (("havermout", "haver", "haverdrink"), ("oats", "rolled oats")),
    (("brood", "volkorenbrood", "witbrood", "tosti"), ("bread",)),
    (("wraps", "tortilla", "tortilla's", "wrap"), ("tortilla", "wraps")),
    (("pitabroodjes", "pita"), ("pita",)),
    (("naan",), ("naan",)),
    (("pizzadeeg", "bladerdeeg", "filodeeg"), ("pizza dough", "puff pastry", "filo pastry")),
    (("soep",), ("soup",)),
)

_WORD = re.compile(r"[a-zà-ÿ']+")
_NOISE = re.compile(
    r"\b(?:ah|jumbo|jumbo's|lidl|dirk|1 de beste|ah basic|ah excellent|huismerk|biologisch|bio|scharrel|"
    r"alle|van de|verpakkingen|verpakking|zelfbedieningsafdeling|per|stuk|stuks|pak|zak|bak|schaal|"
    r"doos|potje|pot|blik|fles|gram|kilo|kg|ml|liter|cl|gr|g|l|à|a|of|en|met|voor|vers|verse)\b|\d+[.,]?\d*\s*(?:g|gr|kg|ml|l|cl|stuks?)?",
    re.IGNORECASE,
)


def cleaned(name: str, pack: str | None = None) -> str:
    """Product name without brand, size and pack words: "AH Scharrel kipfilet 600 g" -> "kipfilet"."""
    text = _NOISE.sub(" ", f"{name or ''}".lower())
    return re.sub(r"\s+", " ", text).strip(" -,.")


# (the word list is for the fallback when no AI answered: plain products only, whole words)
# every Dutch word with its English terms, longest word first: "currypasta" is a curry paste and
# then no longer also "pasta", "zoete aardappel" is not also a potato
_KEYS = tuple(
    sorted(((key, english) for words, english in DICTIONARY for key in words), key=lambda pair: -len(pair[0]))
)


# Ready-made foods contain ingredient words ("ovenschotel kipfilet") but are not that ingredient.
READY_MADE = re.compile(
    r"ovenschotel|maaltijd|stamppot|pizza|burger|nugget|kebab|schnitzel|sandwich|taart|koek|vlaai|chips|snack|"
    r"pudding|gebak|cordon bleu|loempia|bapao|salade|wrap met|pastei|gegrilde|gebraden|gekruide",
    re.IGNORECASE,
)


# Words that describe a plain product without making it something else ("verse gerookte zalm").
MODIFIERS = frozenset((
    "verse vers los hollandse hollands franse spaanse griekse italiaanse biologisch biologische bio rode rood witte "
    "wit groene groen gele geel zwarte zwart gerookte gerookt gedroogde gedroogd kleinverpakking grote groot kleine "
    "klein extra vol volle halfvolle magere jonge jong oude oud belegen naturel scharrel vrije uitloop gesneden "
    "gehakte fijn grof ongezouten gezouten zoete zoet pittige mild milde nieuwe oogst stuks stuk pers per kilo bos "
    "bosje tros trosjes mix mixed noten"
).split())


def dictionary_terms(name: str) -> list[str]:
    """Dutch and English terms from the built-in word list for a plain product name.

    [] for composite products: "AH Verse soep tomaat" or "Gehakt met ui" contain ingredient words
    but are not that ingredient, so exactly one food of the list may match and every other word must be
    a plain modifier. Deliberately strict: this is only the fallback when the AI is not available.
    """
    text = cleaned(name)
    if READY_MADE.search(text):
        return []
    words = _WORD.findall(text)
    used: set[int] = set()  # a word of the product explains one entry only
    matched: set[int] = set()  # entries of the word list that matched
    out: list[str] = []
    for key, english in _KEYS:
        if " " in key:
            parts = key.split()
            if key not in text:
                continue
            hit = [i for i, w in enumerate(words) if any(w.startswith(p) for p in parts)]
            if hit and all(i in used for i in hit):
                continue
        else:
            hit = [
                i for i, w in enumerate(words)
                if i not in used and w == key
            ]
            if not hit:
                continue
        used.update(hit)
        matched.add(id(english))
        for term in (key, *english):
            if term not in out:
                out.append(term)
    unexplained = sum(1 for i, w in enumerate(words) if i not in used and w not in MODIFIERS and len(w) > 2)
    if unexplained or len(matched) > 1:
        return []  # another word or a second food is in there ("gehakt met ui"): a composite, not the plain ingredient
    return out


# ------------------------------------------------------------------ AI


TERMS_VERSION = 2  # bump when TERMS_PROMPT changes: cached answers are then asked again

TERMS_PROMPT = """For each Dutch supermarket offer below, give the plain cooking ingredient it is as short search \
words in Dutch and English: singular, generic, no brand, no size, specific ("chicken breast", not "chicken"). \
Fresh produce, meat, fish, dairy, eggs, bread and pantry items always get terms. Give an EMPTY list for \
everything that is not one plain ingredient: snacks, sweets, cakes, drinks, coffee, ready meals, meal kits, \
vegetable kits, salads, soups, pickles, spreads, flavoured or mixed products (flavoured yoghurt, "tomato pulp with \
garlic", "chicken curry kit"), household, cosmetics, pet food. At most 6 terms.
JSON only, for example: {{"items": [{{"i": 0, "terms": ["kipfilet", "chicken breast"]}}, {{"i": 1, "terms": []}}]}}

OFFERS (number | name | pack | category)
{lines}"""


def build_terms_prompt(batch: list[dict[str, Any]]) -> str:
    """The prompt for one batch of offers (each with name, pack, category)."""
    lines = "\n".join(
        f"{i}|{o['name']}|{o.get('pack') or ''}|{o.get('category') or ''}" for i, o in enumerate(batch)
    )
    return TERMS_PROMPT.format(lines=lines)


def parse_terms_reply(text: str, size: int) -> dict[int, list[str]]:
    """{index: terms} from the AI's JSON; tolerant of code fences and chatter, ignores bad entries."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON in the reply")
    data = json.loads(text[start : end + 1])
    out: dict[int, list[str]] = {}
    for entry in data.get("items") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("i"), int) or not 0 <= entry["i"] < size:
            continue
        terms = entry.get("terms")
        if isinstance(terms, list):
            out[entry["i"]] = [str(t).strip().lower() for t in terms if str(t).strip()][:6]
    return out


AiCall = Callable[[str], Awaitable[str]]


async def add_terms(
    offers: list[dict[str, Any]],
    ai_call: AiCall | None,
    cache: dict[str, list[str]],
    batch_size: int = 40,
) -> dict[str, int]:
    """Give every offer a "terms" list (offers without any are removed from the list in place).

    ``cache`` maps a cleaned product name to its terms (kept between weeks, so the AI only sees
    new products). Returns counts: {"ai_calls", "from_ai", "from_dictionary", "dropped"}.
    """
    stats = {"ai_calls": 0, "from_ai": 0, "from_dictionary": 0, "dropped": 0}
    keys = {id(o): cleaned(o["name"]) or o["name"].lower() for o in offers}
    unknown: dict[str, dict[str, Any]] = {}
    for offer in offers:
        key = keys[id(offer)]
        if key not in cache and key not in unknown:
            unknown[key] = offer
    pending = list(unknown.items())
    if ai_call is not None:
        for start in range(0, len(pending), batch_size):
            chunk = pending[start : start + batch_size]
            try:
                reply = await ai_call(build_terms_prompt([o for _, o in chunk]))
                answers = parse_terms_reply(reply, len(chunk))
            except Exception as err:  # noqa: BLE001 - a failed batch falls back to the word list
                stats["errors"] = stats.get("errors", 0) + 1
                stats["last_error"] = f"{type(err).__name__}: {err}"[:200]
                continue
            stats["ai_calls"] += 1
            for index, (key, _) in enumerate(chunk):
                if index in answers:
                    cache[key] = answers[index]  # [] means: not an ingredient
                    stats["from_ai"] += 1
    kept = []
    for offer in offers:
        key = keys[id(offer)]
        known = cache.get(key)
        if READY_MADE.search(key):
            terms: list[str] = []  # whatever the AI said, a ready-made food is not the ingredient in it
        elif known is not None:
            terms = known  # the AI decided, including "not an ingredient" ([])
        else:  # the AI did not answer for this one: only a plain product from the word list
            terms = dictionary_terms(offer["name"])
            stats["from_dictionary"] += bool(terms)
        if terms:
            offer["terms"] = terms
            kept.append(offer)
        else:
            stats["dropped"] += 1
    offers[:] = kept
    return stats
