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


parser, preprocess = load("parser"), load("preprocess")


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


def run(kind, case):
    value = case["input"]
    if kind == "ingredient":
        return parser.parse_ingredient(value)
    if kind == "step":
        text = parser.convert_text(value)
        return {"text": text, "timers": [[t["seconds"], t["label"]] for t in parser.find_timers(text)]}
    if kind == "prepare":
        return preprocess.prepare(value)
    if kind == "jsonld":
        return jsonld_case(value)
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
