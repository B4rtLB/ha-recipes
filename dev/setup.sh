#!/usr/bin/env bash
# One-time setup of a local Home Assistant for testing the Recipes integration.
# Needs: Python 3.14 (Home Assistant 2026.10), ffmpeg/ffprobe, Node.js (for the UI check).
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3.14}"
command -v "$PY" >/dev/null || { echo "Need $PY (macOS: brew install python@3.14)"; exit 1; }
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found (macOS: brew install ffmpeg) - video tests will fail"
[ -d .venv ] || "$PY" -m venv .venv
if command -v uv >/dev/null; then
  uv pip install -q --python .venv/bin/python "homeassistant==2026.10.4" "yt-dlp==2026.10.26" Pillow
else
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q "homeassistant==2026.10.4" "yt-dlp==2026.10.26" Pillow
fi
# Test media (generated, not committed): portrait H.264 + HEVC videos with sound, and a photo.
if command -v ffmpeg >/dev/null; then
  [ -f fixtures/video.mp4 ] || ffmpeg -v error -y -f lavfi -i testsrc2=size=720x1280:rate=25 -f lavfi -i sine=frequency=440 -t 6 \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest fixtures/video.mp4
  [ -f fixtures/hevc.mp4 ] || ffmpeg -v error -y -f lavfi -i testsrc2=size=720x1280:rate=25 -f lavfi -i sine=frequency=660 -t 4 \
    -c:v libx265 -x265-params log-level=error -pix_fmt yuv420p -c:a aac -shortest fixtures/hevc.mp4
  [ -f fixtures/dish.jpg ] || ffmpeg -v error -y -f lavfi -i "gradients=size=1200x900:c0=orange:c1=red" -frames:v 1 fixtures/dish.jpg
fi
mkdir -p config/custom_components
ln -sfn "$(pwd)/../custom_components/recipes" config/custom_components/recipes
ln -sfn "$(pwd)/fake_ai" config/custom_components/fake_ai
cat > config/configuration.yaml <<YAML
homeassistant:
  name: Recipes dev
  time_zone: Europe/Amsterdam
http:
  server_port: ${HA_PORT:-8123}
logger:
  default: warning
  logs:
    custom_components.recipes: debug
frontend:
onboarding:
webhook:
fake_ai:
YAML
if [ -z "${SKIP_NODE:-}" ] && [ -f package.json ]; then npm install --silent && npx playwright install chromium; fi
grep -q "tiktok.com.localtest" /etc/hosts || echo "Add this line to /etc/hosts for the video tests:  127.0.0.1 tiktok.com.localtest   (sudo sh -c 'echo \"127.0.0.1 tiktok.com.localtest\" >> /etc/hosts')"
echo "Done. Next: ./dev/run.sh (keeps running), then python3 dev/bootstrap.py once."
