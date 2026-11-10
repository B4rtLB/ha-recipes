#!/usr/bin/env python3
"""Export the Apple Notes 'Recipes' folder to /tmp/recipes-export (read-only on Notes)."""
import json, os, re, subprocess, sys, html, base64
OUT = "/tmp/recipes-export"
os.makedirs(OUT, exist_ok=True)
SKIP = set()  # filtering happens in import_notes.py
def osa(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True).stdout
ids = osa('tell application "Notes" to get id of every note of folder "Recipes"').strip().split(", ")
rows = []
for i, nid in enumerate(ids):
    script = f'''tell application "Notes"
set n to note id "{nid}"
set AppleScript's text item delimiters to ""
return (name of n) & "@@SEP@@" & ((creation date of n) as «class isot» as string) & "@@SEP@@" & (body of n)
end tell'''
    try:
        raw = osa(script)
    except subprocess.CalledProcessError as e:
        print("fail", nid, e.stderr[:200], file=sys.stderr); continue
    name, created, body = raw.split("@@SEP@@", 2)
    if name in SKIP: continue
    imgs = re.findall(r'src="data:(image/[a-z]+);base64,([^"]+)"', body)
    text = re.sub(r'<img[^>]*>', '', body)
    text = re.sub(r'(?i)<br\s*/?>|</(div|p|li|h[1-6])>', '\n', text)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    links = re.findall(r'https?://[^\s<>"]+', text)
    img_file = None
    if imgs:
        mime, b64 = max(imgs, key=lambda x: len(x[1]))
        img_file = f"{OUT}/img_{i:03d}.{mime.split('/')[1]}"
        open(img_file, "wb").write(base64.b64decode(b64))
    rows.append({"name": name.strip(), "created": created.strip(), "text": text, "links": links, "image": img_file})
    print(f"{i+1}/{len(ids)} {name[:40]} links={len(links)} img={'y' if img_file else 'n'}", file=sys.stderr)
json.dump(rows, open(f"{OUT}/notes.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({"count": len(rows), "with_links": sum(1 for r in rows if r["links"]), "with_img": sum(1 for r in rows if r["image"])}))
