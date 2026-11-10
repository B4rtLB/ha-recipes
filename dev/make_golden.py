"""Turn debug.json files (Developer view data of real recipes) into golden test fixtures.

    .venv/bin/python make_golden.py [--name=short-name] <debug.json or recipe media folder>
    .venv/bin/python test_parser.py --update     # fills in the expected results
    git diff dev/golden                          # READ it: the repo is public

What is kept: the material the AI got (caption, transcript, web text, JSON-LD). What is
removed: the shared input, links, @handles, e-mail addresses, phone numbers and the JSON-LD
author. Names inside free text can't be found automatically, so always read the result.
"""

import json, pathlib, re, sys

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden"


def scrub(text):
    text = re.sub(r"https?://\S+|www\.\S+", "https://example.com/post", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "user@example.com", text)  # e-mail before @handle
    text = re.sub(r"(?<![\w.])@[\w.]{2,}", "@someone", text)
    text = re.sub(r"(?<!\d)\+?\d[\d\s().-]{8,}\d(?!\d)", "0000000000", text) if re.search(r"tel|phone|whatsapp|call", text, re.I) else text
    return text


def scrub_json(node):
    """Scrub the strings of a JSON document, not its keys ("@type" is not a handle)."""
    if isinstance(node, str):
        return scrub(node)
    if isinstance(node, list):
        return [scrub_json(n) for n in node]
    if isinstance(node, dict):
        return {k: scrub_json(v) for k, v in node.items()}
    return node


def build(path, label=None):
    path = pathlib.Path(path)
    if path.is_dir():
        path = path / "debug.json"
    dbg = json.loads(path.read_text())
    name = re.sub(r"[^a-z0-9]+", "-", (path.parent.name or "recipe").lower()).strip("-")[:40]
    name = label or re.sub(r"-[0-9a-f]{12}$", "", name) or "recipe"  # drop the recipe id
    made = []
    material = [scrub(m) for m in dbg.get("material") or []]
    if material:
        file = GOLDEN / f"prepare-{name}.json"
        file.write_text(json.dumps({"kind": "prepare", "cases": [{"name": name, "input": material}]}, indent=1, ensure_ascii=False) + "\n")
        made.append(file)
    if isinstance(dbg.get("jsonld"), dict):
        slim = {k: v for k, v in dbg["jsonld"].items() if k != "author"}
        file = GOLDEN / f"jsonld-{name}.json"
        file.write_text(json.dumps({"kind": "jsonld", "cases": [{"name": name, "input": scrub_json(slim)}]}, indent=1, ensure_ascii=False) + "\n")
        made.append(file)
    return made


if len(sys.argv) < 2:
    raise SystemExit(__doc__)
label = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--name=")), None)
for arg in (a for a in sys.argv[1:] if not a.startswith("--name=")):
    for file in build(arg, label):
        print("wrote", file.relative_to(GOLDEN.parent))
