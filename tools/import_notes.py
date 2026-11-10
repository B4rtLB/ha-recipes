#!/usr/bin/env python3
"""Import recipes from the Apple Notes "Recipes" folder into Home Assistant Recipes.

Step 1 (Mac): export the notes   ->  python3 tools/export_notes.py
Step 2 (Mac): send them to HA    ->  python3 tools/import_notes.py https://<ha>/api/webhook/<id>

Notes are only read, never changed. Re-running is safe: notes with a link that is
already in Recipes are skipped by Home Assistant (duplicate detection).
"""
import base64
import json
import ssl
import sys
import time
import urllib.request

EXPORT = "/tmp/recipes-export/notes.json"
# Notes in the folder that are not a single recipe.
SKIP_TITLES = {"Koken", "⚠️Save Recipe Config Noot", "Recepten opnieuw proberen"}


def ssl_context():
    try:
        import certifi  # noqa: PLC0415

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    webhook = sys.argv[1]
    dry = "--dry-run" in sys.argv
    rows = json.load(open(EXPORT, encoding="utf-8"))
    ctx = ssl_context()
    sent = skipped = 0
    for row in rows:
        title = row["name"].strip()
        if title in SKIP_TITLES:
            print(f"skip   {title}")
            skipped += 1
            continue
        payload = {
            "import": {
                "title": title.removeprefix("Recipe name: ").strip(),
                "text": row["text"],
                "source_url": next(
                    (link for link in row["links"] if "apple.com" not in link), None
                ),
                "created": row["created"],
            }
        }
        if row.get("image"):
            with open(row["image"], "rb") as fh:
                payload["import"]["image_b64"] = base64.b64encode(fh.read()).decode()
        if dry:
            print(f"would  {title}  link={payload['import']['source_url']}")
            continue
        req = urllib.request.Request(
            webhook, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                result = json.loads(resp.read() or b"{}")
            print(f"{'sent ' if result.get('created') else 'exists'} {title}")
            sent += 1
        except Exception as err:  # keep going, report at the end
            print(f"ERROR  {title}: {err}")
        time.sleep(0.3)
    print(f"\nDone: {sent} sent, {skipped} skipped. Home Assistant processes them one by one;")
    print("open the Recipes app to watch them come in (videos are downloaded as well).")


if __name__ == "__main__":
    main()
