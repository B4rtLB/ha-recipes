"""End-to-end test of the Recipes integration against the dev Home Assistant.

Run dev/run.sh first (and dev/bootstrap.py once). Deletes all recipes in the dev instance!
"""

import base64, json, os, subprocess, sys, time, urllib.error, urllib.request, uuid

from hadev import BASE as B, CONFIG, DEV, access_token, media_root

TOK = access_token()
MEDIA = media_root()
FIX = "http://127.0.0.1:8000"


def req(method, path, body=None, headers=None, auth=True, raw=False):
    h = dict(headers or {})
    if auth: h["Authorization"] = "Bearer " + TOK
    data = None
    if body is not None and not isinstance(body, (bytes, bytearray)):
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    elif body is not None: data = body
    r = urllib.request.Request(B + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            out = resp.read()
            return resp.status, (out if raw else json.loads(out or b"{}")), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500], e.headers
def wait(rid, t=120):
    end = time.time() + t
    while time.time() < end:
        s, r, _ = req("GET", f"/api/recipes/{rid}")
        if r.get("status") in ("ready", "error"): return r
        time.sleep(1)
    raise SystemExit(f"timeout {rid} {r.get('status')} {r.get('progress')}")
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or FAIL.append(m))
FAIL = []
s, st, _ = req("GET", "/api/recipes/settings"); ok(s == 200 and st["webhook_path"].startswith("/api/webhook/"), f"settings {st}")
HOOK = st["webhook_path"]
for r0 in req("GET", "/api/recipes")[1]["recipes"]: req("DELETE", f"/api/recipes/{r0['id']}")
# A web json-ld
s, r, _ = req("POST", "/api/recipes", {"url": FIX + "/p/curry.html"}); ok(s == 201, f"create web {s} {r}")
a = wait(r["id"])
ok(a["status"] == "ready" and a["title"] == "Weeknight Chicken Curry", f"web title {a.get('title')} {a.get('error')}")
ok(a["tags"] == ["Main", "Chicken", "Asian"], f"tags filtered {a['tags']}")
ok(a["media"].get("image") == "image.jpg" and a["image_url"] and "authSig" in a["image_url"], "web image signed")
ok(a["total_min"] == 35 and a["steps"][1]["timers"][0]["seconds"] == 600, f"total+fallback timer {a['total_min']} {a['steps'][1]['timers']}")
ok("input_text" not in a, "no input_text leak")
# F duplicate
s, r2, _ = req("POST", "/api/recipes", {"url": FIX + "/p/curry.html/"}); ok(r2["created"] is False and r2["id"] == a["id"], "duplicate detected")
# G signed media + range, no auth
s, body, h = req("GET", a["image_url"], auth=False, raw=True); ok(s == 200 and body[:2] == b"\xff\xd8", f"signed image no-auth {s}")
s, body, h = req("GET", a["image_url"].split("?")[0], auth=False, raw=True); ok(s == 401, f"unsigned media blocked {s}")
# B social video via webhook (no auth)
s, r, _ = req("POST", HOOK, {"url": "http://tiktok.com.localtest:8000/video.mp4"}, auth=False); ok(s == 200 and r["ok"], f"webhook {r}")
b = wait(r["id"], 180)
ok(b["status"] == "ready", f"video recipe {b.get('status')} {b.get('error')} {b.get('pipeline_notes')}")
ok(b["media"].get("video") == "video.mp4" and b["video_url"], f"video stored {b['media']}")
ok(b["media"].get("poster") == "poster.jpg", "poster from frame")
ok(b["media"].get("width") == 720 and b["media"].get("height") == 1280, "dims")
ok("transcribed" in (b.get("pipeline_notes") or []), f"transcribed {b.get('pipeline_notes')}")
s, body, h = req("GET", b["video_url"], auth=False, raw=True, headers={"Range": "bytes=0-99"}); ok(s == 206 and len(body) == 100, f"range {s}")
# C hevc
s, r, _ = req("POST", HOOK, {"url": "http://tiktok.com.localtest:8000/hevc.mp4"}, auth=False)
c = wait(r["id"], 180)
p = str(MEDIA / c["id"] / "video.mp4")
tag = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_tag_string","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip()
ok(tag == "hvc1", f"hevc retagged {tag}")
# D upload multipart via webhook
bnd = uuid.uuid4().hex
img = open(DEV / "fixtures" / "dish.jpg","rb").read()
mp = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"shot.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode()+img+f"\r\n--{bnd}--\r\n".encode()
s, r, _ = req("POST", HOOK, mp, auth=False, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"}); ok(s == 200 and r["created"], f"upload {s} {r}")
d = wait(r["id"])
ok(d["status"] == "ready" and d["media"].get("image") == "image.jpg", f"upload recipe {d.get('status')} {d.get('error')}")
# D2 raw jpeg body (Shortcuts "File" body)
s, r, _ = req("POST", HOOK, img, auth=False, headers={"Content-Type": "image/jpeg"}); ok(s == 200 and r["created"], f"raw upload {s} {r}")
d2 = wait(r["id"]); ok(d2["status"] == "ready" and d2["media"].get("image") == "image.jpg", f"raw upload recipe {d2.get('error')}")
last = json.load(urllib.request.urlopen(urllib.request.Request(B + "/api/states/ai_task.fake_ai", headers={"Authorization": "Bearer " + TOK})))
# E import with b64
s, r, _ = req("POST", HOOK, {"import": {"title": "Butter Bean Curry", "text": "Butter Bean Curry\nPrep time: 10\nIngredients\n- 1 can beans", "image_b64": base64.b64encode(img).decode(), "source_url": FIX + "/p/none.html", "created": "2026-03-03T18:39:43+00:00"}}, auth=False)
e = wait(r["id"])
ok(e["status"] == "ready" and e["title"] == "Butter Bean Curry" and e["created"].startswith("2026-03-03") and e["media"].get("image"), f"import {e.get('title')} {e.get('created')} {e.get('error')}")
# H no recipe
s, r, _ = req("POST", HOOK, {"text": "NO_RECIPE just a dance video with lots of words to exceed forty characters"}, auth=False)
h_ = wait(r["id"]); ok(h_["status"] == "error" and "No recipe" in h_["error"], f"no recipe -> error {h_.get('error')}")
# retry endpoint
s, _, _ = req("POST", f"/api/recipes/{h_['id']}/retry"); ok(s == 200, "retry")
# I cookies
s, r, _ = req("POST", "/api/recipes/settings", {"instagram_cookies": "sessionid=abc%3A123; csrftoken=xyz"}); ok(s == 200 and r["instagram_cookies"], f"cookies {r}")
txt = open(CONFIG / ".storage" / "recipes_instagram_cookies.txt").read(); ok("\tsessionid\tabc%3A123" in txt, "netscape cookie file")
s, r, _ = req("POST", "/api/recipes/settings", {"instagram_cookies": "garbage"}); ok(s == 400, f"bad cookies rejected {s}")
# list
s, l, _ = req("GET", "/api/recipes"); ok(s == 200 and len(l["recipes"]) >= 6, f"list {len(l['recipes'])}")
# PATCH + DELETE
s, r, _ = req("PATCH", f"/api/recipes/{a['id']}", {"favorite": True, "status": "hacked"}); ok(r["favorite"] and r["status"] == "ready", "patch whitelist")
s, r, _ = req("DELETE", f"/api/recipes/{c['id']}"); import os; ok(not (MEDIA / c["id"]).exists(), "delete removes media")
# app shell
s, html, _ = req("GET", "/recipes/", auth=False, raw=True); ok(s == 200 and b"app.js?v=" in html and b"__VERSION__" not in html, "index served")
s, js, h = req("GET", "/recipes/sw.js", auth=False, raw=True); ok(s == 200 and h.get("Service-Worker-Allowed") == "/recipes/", "sw headers")
s, _, _ = req("GET", "/recipes/static/app.css", auth=False, raw=True); ok(s == 200, "static")
s, _, _ = req("GET", "/recipes/manifest.webmanifest", auth=False, raw=True); ok(s == 200, "manifest")
s, _, _ = req("GET", "/api/recipes", auth=False); ok(s == 401, "api requires auth")
print("FAILED:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
