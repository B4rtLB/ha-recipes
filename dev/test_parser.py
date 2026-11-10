"""Golden tests for the deterministic part of reading a recipe (no Home Assistant needed).

Covers dev/golden/*.json: ingredient parsing and metric conversion, step text and timers,
the preprocessing of captions / transcripts / web text, and the JSON-LD shortcut.

    .venv/bin/python test_parser.py            # check
    .venv/bin/python test_parser.py --update   # rewrite "expected" after a deliberate change, then READ the diff

New fixtures: dev/make_golden.py turns a debug.json into a sanitized golden file.
"""

import importlib.util, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "recipes"
GOLDEN = pathlib.Path(__file__).resolve().parent / "golden"


def load(name):
    """Import a pure module of the integration without importing Home Assistant."""
    spec = importlib.util.spec_from_file_location(f"recipes_{name}", ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


parser, preprocess, discounts = load("parser"), load("preprocess"), load("discounts")


def jsonld_case(recipe):
    """What the JSON-LD shortcut produces without AI (ingredients parsed, steps with timers)."""
    # sources.py needs aiohttp and the package for .const; import it as part of the package
    sys.path.insert(0, str(ROOT.parent.parent))
    from custom_components.recipes import ai, sources  # noqa: PLC0415

    data = sources.jsonld_to_data(recipe)
    if data is None:
        return None
    full = ai.lean_to_full(data)
    return {
        "title": data["title"], "servings": data["servings"], "servings_text": data["servings_text"],
        "minutes": [data["prep_min"], data["cook_min"], data["total_min"]], "hints": data["_hints"],
        "ingredients": [[i["qty"], i["unit"], i["name"], i["note"], i["original"]] for g in full["ingredient_groups"] for i in g["items"]],
        "steps": [[s["text"], [[t["seconds"], t["label"]] for t in s["timers"]]] for s in full["steps"]],
    }


def _package():
    sys.path.insert(0, str(ROOT.parent.parent))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from custom_components.recipes import offer_terms, offers  # noqa: PLC0415
    import offer_fixtures  # noqa: PLC0415

    return offers, offer_terms, offer_fixtures


def offers_case(value):
    """A store's invented page through its parser: the food offers that are still running."""
    offers, _, fixtures = _package()
    today = value["today"]
    if value["store"] == "ah":
        raw = offers.parse_ah_products(json.loads(fixtures.ah(today)[1])["products"], today)
    else:
        raw = {"jumbo": offers.parse_jumbo, "dirk": offers.parse_dirk, "lidl": offers.parse_lidl}[value["store"]](
            fixtures.pages(today)[value["store"] + ".html"]
        )
    done = offers.finish(raw, today)
    return {
        "found": len(raw),
        "running": len(done),
        "food": [
            [o["name"], o["pack"], o["price"], o["was"], o["note"], o["valid_from"], o["valid_to"], o["category"]]
            for o in done if offers.is_food_category(o["category"])
        ],
    }


def terms_case(value):
    """Search words for product names from the built-in word list, or the parse of an AI reply."""
    _, terms, _ = _package()
    if "reply" in value:
        try:
            return {str(k): v for k, v in terms.parse_terms_reply(value["reply"], value["size"]).items()}
        except ValueError as err:
            return {"error": str(err)}
    return {name: terms.dictionary_terms(name) for name in value["names"]}


def add_terms_case(value):
    """add_terms with a scripted AI: which offers keep which terms, and how the work was split."""
    import asyncio  # noqa: PLC0415

    _, terms, _ = _package()
    offers = [{"name": n} for n in value["offers"]]
    calls = []

    async def ai_call(prompt):
        calls.append(prompt)
        lines = prompt.split("OFFERS (number | name | pack | category)\n", 1)[1].splitlines()
        items = [{"i": int(l.split("|")[0]), "terms": value["ai"].get(l.split("|")[1], [])} for l in lines]
        if value.get("broken"):
            raise ValueError("AI is down")
        return json.dumps({"items": items})

    cache = dict(value.get("cache", {}))
    stats = asyncio.run(terms.add_terms(offers, None if value.get("no_ai") else ai_call, cache))
    return {"kept": {o["name"]: o["terms"] for o in offers}, "stats": {k: v for k, v in stats.items() if k != "last_error"},
            "asked": len(calls), "cache": sorted(cache)}


def run(kind, case):
    value = case["input"]
    if kind == "ingredient":
        return parser.parse_ingredient(value)
    if kind == "step":
        text = parser.convert_text(value)
        return {"text": text, "timers": [[t["seconds"], t["label"]] for t in parser.find_timers(text)]}
    if kind == "prepare":
        return preprocess.prepare(value)
    if kind == "discount":  # an ingredient name against some stores: offers + the store that glows
        offers = discounts.match_ingredient(value["ingredient"], discounts.active_stores({"stores": value["stores"]}, value.get("today", "2026-11-10")))
        return {"offers": [[o["store"], o["item"]] for o in offers], "best": discounts.best_offer(offers) if offers else None}
    if kind == "discount-active":  # which stores count on a given day
        return sorted(discounts.active_stores({"stores": value["stores"]}, value["today"]))
    if kind == "discount-clean":  # validation: the stored entry, or the error
        try:
            return discounts.clean_store(*value)
        except ValueError as err:
            return {"error": str(err)}
    if kind == "jsonld":
        return jsonld_case(value)
    if kind == "offers":
        return offers_case(value)
    if kind == "terms":
        return terms_case(value)
    if kind == "add-terms":
        return add_terms_case(value)
    raise SystemExit(f"unknown kind {kind}")


def main():
    update = "--update" in sys.argv
    failed = total = 0
    for path in sorted(GOLDEN.glob("*.json")):
        doc = json.loads(path.read_text())
        for case in doc["cases"]:
            total += 1
            got = run(doc["kind"], case)
            label = f"{path.stem}: {case.get('name') or str(case['input'])[:60]!r}"
            if update:
                case["expected"] = got
            elif "expected" not in case:
                failed += 1
                print(f"FAIL {label}: no expected result yet (run --update and read it)")
            elif got != case["expected"]:
                failed += 1
                print(f"FAIL {label}\n  want {json.dumps(case['expected'], ensure_ascii=False)}\n  got  {json.dumps(got, ensure_ascii=False)}")
        if update:
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"{'updated' if update else 'checked'} {total} golden cases, {failed} failed")
    sys.exit(1 if failed else 0)


main()
