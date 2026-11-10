#!/usr/bin/env bash
# Start the fixture web server (port 8000) and the dev Home Assistant (port 8123).
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"
(cd fixtures && exec python3 -m http.server 8000 --bind 127.0.0.1 >/dev/null 2>&1) &
FIX=$!
trap 'kill $FIX 2>/dev/null' EXIT
exec .venv/bin/hass -c config
