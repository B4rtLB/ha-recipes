"""Shared helpers for the dev scripts: base URL, tokens, paths."""

import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

DEV = Path(__file__).resolve().parent
CONFIG = DEV / "config"
BASE = os.environ.get("HA_URL", "http://127.0.0.1:" + os.environ.get("HA_PORT", "8123"))
CLIENT_ID = BASE + "/"
TOKENS = DEV / ".tokens.json"


def media_root() -> Path:
    """Same rule as store.media_root(): /media if it exists, else <config>/recipes_media."""
    return Path("/media/recipes") if Path("/media").is_dir() else CONFIG / "recipes_media"


def post_form(path: str, data: dict) -> dict:
    req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(data).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def access_token() -> str:
    """Fresh access token from the stored refresh token (access tokens live 30 min)."""
    tokens = json.loads(TOKENS.read_text())
    out = post_form("/auth/token", {"grant_type": "refresh_token", "client_id": CLIENT_ID,
                                    "refresh_token": tokens["refresh_token"]})
    return out["access_token"]
