# Local test environment

A throwaway Home Assistant with a fake AI Task and speech-to-text (`fake_ai/`), so the Recipes integration can be tested without OpenAI or the real Home Assistant.

```bash
./dev/setup.sh            # once
./dev/run.sh              # keep running in its own terminal
python3 dev/bootstrap.py  # once, after the first start
python3 dev/e2e.py        # backend tests
node dev/ui_check.js      # app tests + screenshots in dev/shots/
```

- Home Assistant: http://127.0.0.1:8123, user `dev` / `devpass123`
- App: http://127.0.0.1:8123/recipes/
- `fixtures/` is served on port 8000. It holds a recipe web page with JSON-LD, a photo, and an H.264 and an HEVC video. The videos are fetched as "TikTok" via `tiktok.com.localhost`, which macOS resolves to 127.0.0.1 without an `/etc/hosts` entry.
- Everything the instance creates lives in `dev/config/`, which git ignores. Delete that folder to start over.
