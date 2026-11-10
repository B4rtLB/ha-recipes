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
s, r, _ = req("POST", HOOK, {"url": "http://tiktok.com.localhost:8000/video.mp4"}, auth=False); ok(s == 200 and r["ok"], f"webhook {r}")
b = wait(r["id"], 180)
ok(b["status"] == "ready", f"video recipe {b.get('status')} {b.get('error')} {b.get('pipeline_notes')}")
ok(b["media"].get("video") == "video.mp4" and b["video_url"], f"video stored {b['media']}")
ok(b["media"].get("poster") == "poster.jpg", "poster from frame")
ok(b["media"].get("width") == 720 and b["media"].get("height") == 1280, "dims")
ok("transcribed" in (b.get("pipeline_notes") or []), f"transcribed {b.get('pipeline_notes')}")
s, body, h = req("GET", b["video_url"], auth=False, raw=True, headers={"Range": "bytes=0-99"}); ok(s == 206 and len(body) == 100, f"range {s}")
# C hevc
s, r, _ = req("POST", HOOK, {"url": "http://tiktok.com.localhost:8000/hevc.mp4"}, auth=False)
c = wait(r["id"], 180)
cdir = next(MEDIA.glob("*" + c["id"]))
p = str(cdir / "video.mp4")
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
s, r, _ = req("DELETE", f"/api/recipes/{c['id']}"); ok(not cdir.exists() and not list(MEDIA.glob("*" + c["id"])), "delete removes media")
# J readable media folders: <slug-of-title>-<id>, renamed when the title changes
ok((MEDIA / f"weeknight-chicken-curry-{a['id']}" / "image.jpg").is_file(), f"folder named after title {[x.name for x in MEDIA.iterdir()]}")
s, body, h = req("GET", a["image_url"], auth=False, raw=True); ok(s == 200, f"media still served after rename {s}")
s, r, _ = req("PATCH", f"/api/recipes/{a['id']}", {"title": "Bart's Curry!"}); time.sleep(0.5)
ok((MEDIA / f"bart-s-curry-{a['id']}" / "image.jpg").is_file(), f"folder follows a new title {[x.name for x in MEDIA.iterdir()]}")
# K integration options in the app
s, st, _ = req("GET", "/api/recipes/settings")
ok(st["options"]["ai_task_entity"] == "ai_task.fake_ai" and st["options"]["language"] == "en" and st["options"]["transcribe"] is True, f"options {st.get('options')}")
ok({"id": "stt.fake_stt", "name": "Fake STT"} in st["choices"]["stt_entity"] and len(st["choices"]["language"]) == 2, f"choices {st.get('choices')}")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"language": "nl", "transcribe": False, "notify_service": "notify.mobile_app_test"}})
ok(s == 200 and r["options"]["language"] == "nl" and r["options"]["transcribe"] is False, f"options saved {s} {r}")
ok(os.path.exists(CONFIG / ".storage" / "recipes_instagram_cookies.txt"), "saving options keeps the cookies")
s, r, _ = req("POST", "/api/recipes", {"url": FIX + "/p/curry.html", "force": True}); nl = wait(r["id"])
dbg = req("GET", f"/api/recipes/{nl['id']}/debug")[1]
ok("in Dutch" in dbg["debug"]["ai"]["prompt"], "new language used without a restart")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"ai_task_entity": "ai_task.nope"}}); ok(s == 400, f"unknown entity rejected {s}")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"bogus": 1}}); ok(s == 400, f"unknown option rejected {s}")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"language": "en", "transcribe": True, "notify_service": ""}})
ok(s == 200 and r["options"]["notify_service"] is None and r["options"]["language"] == "en", f"options reset {r.get('options')}")
# L developer view: debug record, AI re-run, save on confirm
d = dbg["debug"]
ok(dbg["available"] and dbg["folder"] == f"weeknight-chicken-curry-{nl['id']}", f"debug available {dbg.get('folder')}")
ok(d["web_text"].startswith("SCHEMA.ORG") and d["material"] == [d["web_text"]] and d["platform"] == "web", "debug has the web material")
ok(d["ai"]["entity"] == "ai_task.fake_ai" and d["ai"]["output"].startswith("```json") and "SOURCE MATERIAL" in d["ai"]["prompt"], "debug has prompt and raw output")
ok(d["timings"].get("ai") is not None and d["timings"].get("web") is not None and d["status"] == "ready", f"timings {d['timings']}")
vd = req("GET", f"/api/recipes/{b['id']}/debug")[1]["debug"]
ok(vd["transcript"] == "spoken: two cups of rice" and "download" in vd["timings"] and "transcribe" in vd["timings"] and vd["shared"], f"video debug {vd.get('transcript')} {vd.get('timings')}")
ed = req("GET", f"/api/recipes/{h_['id']}/debug")[1]["debug"]
ok(ed["status"] == "error" and "NO_RECIPE" in ed["input_text"], f"debug kept for a failed recipe {ed.get('status')}")
s, x, _ = req("POST", f"/api/recipes/{nl['id']}/debug/rerun", {"instruction": "Always say hello"})
ok(s == 200 and x["fields"]["title"] == "Weeknight Chicken Curry" and x["prompt"].rstrip().endswith("Always say hello"), f"rerun with instruction {s}")
s, x, _ = req("POST", f"/api/recipes/{nl['id']}/debug/rerun", {"prompt": d["ai"]["prompt"].replace("Weeknight Chicken Curry", "Renamed Curry")})
ok(s == 200 and x["fields"]["title"] == "Renamed Curry", f"rerun with edited prompt {s} {x if s != 200 else ''}")
ok(req("GET", f"/api/recipes/{nl['id']}")[1]["title"] == "Weeknight Chicken Curry", "rerun saves nothing")
s, r, _ = req("POST", f"/api/recipes/{nl['id']}/debug/apply"); time.sleep(0.5)
ok(s == 200 and r["title"] == "Renamed Curry" and (MEDIA / f"renamed-curry-{nl['id']}" / "debug.json").is_file(), f"apply saves and renames {s}")
s, r, _ = req("POST", f"/api/recipes/{nl['id']}/debug/apply"); ok(s == 400, f"apply needs a new run {s}")
s, _, _ = req("GET", f"/api/recipes/media/{nl['id']}/debug.json"); ok(s == 404, f"debug.json is not served as media {s}")
req("DELETE", f"/api/recipes/{nl['id']}")
# M lean extraction mode: preprocess + parser + JSON-LD shortcut instead of an AI that converts
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"extraction_mode": "bogus"}}); ok(s == 400, f"unknown mode rejected {s}")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"extraction_mode": "lean"}})
ok(s == 200 and r["options"]["extraction_mode"] == "lean", f"lean mode saved {s}")
s, r, _ = req("POST", "/api/recipes", {"url": FIX + "/p/curry.html", "force": True}); lj = wait(r["id"])
ld = req("GET", f"/api/recipes/{lj['id']}/debug")[1]["debug"]
ok(ld["mode"] == "lean" and ld["ai"]["shortcut"] == "jsonld" and ld["ai"]["prompt"].startswith("A recipe is already parsed"), f"json-ld shortcut, only a tags call {ld.get('mode')} {ld['ai'].get('shortcut')}")
ing = [i for g in lj["ingredient_groups"] for i in g["items"]]
ok(ing[0]["qty"] == 450 and ing[0]["unit"] == "g" and ing[0]["original"] == "1 lb" and ing[1]["unit"] == "clove", f"parser converts json-ld ingredients {ing}")
ok(lj["status"] == "ready" and lj["title"] == "Weeknight Chicken Curry" and lj["total_min"] == 35 and lj["tags"] == ["Main", "Chicken", "Asian"], f"shortcut recipe {lj['title']} {lj['tags']} {lj['total_min']}")
ok(lj["steps"][1]["timers"] == [{"seconds": 1200, "label": "Simmer"}], f"timers found in step text {lj['steps'][1]['timers']}")
s, r, _ = req("POST", HOOK, {"url": "http://tiktok.com.localhost:8000/video.mp4", "force": True}, auth=False); lv = wait(r["id"], 180)
lvd = req("GET", f"/api/recipes/{lv['id']}/debug")[1]["debug"]
ok(lv["status"] == "ready" and lvd["mode"] == "lean" and lvd["ai"]["prompt"].startswith("Extract ONE recipe") and "shortcut" not in lvd["ai"], f"lean video recipe {lv.get('status')} {lv.get('error')}")
ok(lvd["prepared"] and lvd["prepared"][-1].startswith("SPEECH TRANSCRIPT") and lvd["ai"]["output"].count("{") >= 3, "lean keeps the prepared material and the raw output")
g0 = lv["ingredient_groups"][0]["items"]
ok((g0[0]["qty"], g0[0]["unit"], g0[0]["name"], g0[0]["note"], g0[0]["original"]) == (500, "g", "chicken thighs", "boneless", "1.1 lb"), f"raw string parsed and converted {g0[0]}")
ok((g0[1]["qty"], g0[1]["qty_max"], g0[1]["unit"]) == (2, 3, "clove") and g0[2]["qty"] == 0.5 and g0[3]["qty"] is None and g0[3]["note"] == "to taste", f"ranges, fractions, to taste {g0[1:]}")
g1 = lv["ingredient_groups"][1]["items"]
ok(lv["ingredient_groups"][1]["name"] == "Sauce" and (g1[0]["qty"], g1[0]["unit"]) == (200, "ml") and (g1[1]["qty"], g1[1]["unit"], g1[1]["name"]) == (1, "pinch", "zout"), f"groups and Dutch words {g1}")
st = lv["steps"]
ok(st[2]["text"] == "Bake at 200 °C (400 °F) for 1 hour 30 minutes." and st[2]["timers"] == [{"seconds": 5400, "label": "Bake"}], f"°F converted, 1 h 30 min one timer {st[2]}")
ok(st[0]["timers"] == [{"seconds": 300, "label": "Fry"}] and st[1]["timers"] == [{"seconds": 600, "label": "Simmer"}] and st[3]["timers"] == [], f"timers per step {[x['timers'] for x in st]}")
ok(lv["tags"] == ["Main", "Chicken", "Asian"], f"tags {lv['tags']}")
# compare the two modes on the same material with "Re-run AI only"
s, x, _ = req("POST", f"/api/recipes/{lv['id']}/debug/rerun", {"mode": "classic"})
ok(s == 200 and x["mode"] == "classic" and "CRITICAL RULES" in x["prompt"] and x["fields"]["ingredient_groups"][0]["items"][0]["original"] == "1.1 lb", f"lean recipe re-run as classic {s}")
s, x, _ = req("POST", f"/api/recipes/{b['id']}/debug/rerun", {"mode": "lean"})
ok(s == 200 and x["mode"] == "lean" and x["prompt"].startswith("Extract ONE recipe") and x["prepared"] and x["fields"]["steps"][2]["timers"][0]["seconds"] == 5400, f"classic recipe re-run as lean {s}")
s, x, _ = req("POST", f"/api/recipes/{lj['id']}/debug/rerun", {"mode": "classic"})
ok(s == 200 and x["mode"] == "classic" and "shortcut" not in x, f"json-ld recipe re-run as classic {s}")
s, x, _ = req("POST", f"/api/recipes/{lj['id']}/debug/rerun", {})
ok(s == 200 and x["mode"] == "lean" and x["shortcut"] == "jsonld", f"re-run follows the setting {s}")
s, x, _ = req("POST", f"/api/recipes/{lj['id']}/debug/rerun", {"mode": "bogus"}); ok(s == 400, f"bad mode in re-run {s}")
s, r, _ = req("POST", "/api/recipes/settings", {"options": {"extraction_mode": "classic"}}); ok(r["options"]["extraction_mode"] == "classic", "back to classic")
for rid in (lj["id"], lv["id"]): req("DELETE", f"/api/recipes/{rid}")
# app shell
s, html, _ = req("GET", "/recipes/", auth=False, raw=True); ok(s == 200 and b"app.js?v=" in html and b"__VERSION__" not in html, "index served")
s, js, h = req("GET", "/recipes/sw.js", auth=False, raw=True); ok(s == 200 and h.get("Service-Worker-Allowed") == "/recipes/", "sw headers")
s, _, _ = req("GET", "/recipes/static/app.css", auth=False, raw=True); ok(s == 200, "static")
s, _, _ = req("GET", "/recipes/manifest.webmanifest", auth=False, raw=True); ok(s == 200, "manifest")
s, _, _ = req("GET", "/api/recipes", auth=False); ok(s == 401, "api requires auth")
print("FAILED:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
