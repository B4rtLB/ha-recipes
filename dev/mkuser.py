"""Print an access token of a non-admin dev user (created on first use). Run with dev/.venv/bin/python."""

import asyncio, json, urllib.error, urllib.parse, urllib.request

import aiohttp

from hadev import BASE, CLIENT_ID, access_token

USER, PASS = "viewer", "viewerpass123"


def form(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


async def ensure_user():
    async with aiohttp.ClientSession() as s, s.ws_connect(BASE + "/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": access_token()})
        await ws.receive_json()
        await ws.send_json({"id": 1, "type": "config/auth/create", "name": "Viewer", "group_ids": ["system-users"]})
        r = await ws.receive_json()
        if not r["success"]:
            return
        uid = r["result"]["user"]["id"]
        await ws.send_json({"id": 2, "type": "config/auth_provider/homeassistant/create", "user_id": uid, "username": USER, "password": PASS})
        await ws.receive_json()


def login():
    flow = form("/auth/login_flow", {"client_id": CLIENT_ID, "handler": ["homeassistant", None], "redirect_uri": CLIENT_ID})
    res = form("/auth/login_flow/" + flow["flow_id"], {"client_id": CLIENT_ID, "username": USER, "password": PASS})
    if res.get("type") != "create_entry":
        return None
    data = urllib.parse.urlencode({"grant_type": "authorization_code", "code": res["result"], "client_id": CLIENT_ID}).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + "/auth/token", data=data, method="POST"), timeout=30) as r:
        return json.load(r)["access_token"]


tok = login()
if not tok:
    asyncio.run(ensure_user())
    tok = login()
print(tok)
