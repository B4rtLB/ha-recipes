"""Onboard the dev Home Assistant and add the Recipes integration (run once, HA must be running).

Creates user dev / devpass123 and stores a refresh token in dev/.tokens.json.
"""

import json
import sys
import time
import urllib.error
import urllib.request

from hadev import BASE, CLIENT_ID, TOKENS, post_form


def call(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


for _ in range(60):
    try:
        status = call("GET", "/api/onboarding")
        break
    except (urllib.error.URLError, ConnectionError):
        time.sleep(2)
else:
    sys.exit(f"Home Assistant not reachable at {BASE} - start it with dev/run.sh")

if not any(s["step"] == "user" and s["done"] for s in status):
    code = call("POST", "/api/onboarding/users", {"client_id": CLIENT_ID, "name": "Dev", "username": "dev",
                                                  "password": "devpass123", "language": "en"})["auth_code"]
    tok = post_form("/auth/token", {"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID})
    TOKENS.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    access = tok["access_token"]
    for step, body in (("core_config", {}), ("analytics", {}),
                       ("integration", {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID})):
        try:
            call("POST", f"/api/onboarding/{step}", body, access)
        except urllib.error.HTTPError as err:
            print("onboarding", step, err.code)
    print("Onboarded: user dev / devpass123")
else:
    from hadev import access_token
    access = access_token()

entries = call("GET", "/api/config/config_entries/entry", token=access)
if not any(e["domain"] == "recipes" for e in entries):
    for _ in range(30):  # wait for the fake AI entities
        if all(any(s["entity_id"] == e for s in call("GET", "/api/states", token=access))
               for e in ("ai_task.fake_ai", "stt.fake_stt")):
            break
        time.sleep(1)
    flow = call("POST", "/api/config/config_entries/flow", {"handler": "recipes"}, access)
    res = call("POST", f"/api/config/config_entries/flow/{flow['flow_id']}",
               {"ai_task_entity": "ai_task.fake_ai", "stt_entity": "stt.fake_stt",
                "language": "en", "transcribe": True}, access)
    print("Recipes integration:", res.get("type"), res.get("title"))
print("Ready. Open", BASE + "/recipes/  (dev / devpass123)")
