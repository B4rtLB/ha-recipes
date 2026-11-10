# Recipes for Home Assistant: notes for Claude Code

Bart's personal recipe app. Recipes are shared from the iPhone (TikTok, Instagram, websites, photos, PDFs, text) to a Home Assistant webhook. A custom integration turns them into structured recipes. A full-screen web app in Apple Music dark style is served by Home Assistant at `/recipes/`.

This repo is **public** (HACS installs from GitHub). Never commit URLs, webhook ids, tokens, cookies or other personal data. Bart's Nabu Casa URL and webhook id are not in the repo; ask him if you need them.

Open work is in `TODO.md`.

## Layout

| Path | What |
|---|---|
| `custom_components/recipes/__init__.py` | Setup, services (`recipes.add/status/retry/delete`), webhook registration, asset version |
| `custom_components/recipes/pipeline.py` | `RecipeProcessor`: sequential queue. `_collect` gathers the material (social video / web page / upload / text), `_extract` is the AI step, then save. Writes `debug.json`; `rerun_ai` / `apply_experiment` for the developer view. `new_recipe_from_payload` picks the URL and dedupes |
| `custom_components/recipes/sources.py` | Platform detection, link picking (`best_url`, skips script/CDN links), web fetch + JSON-LD, social og-meta fallback |
| `custom_components/recipes/video.py` | yt-dlp download, ffmpeg (iOS-friendly mp4, `hvc1` tag, faststart), poster, audio for speech-to-text |
| `custom_components/recipes/ai.py` | The extraction prompt, AI Task call (with attachments), JSON parsing, `normalize` (tags, timers, "Quick" ≤ 30 min, Protein tag fallback from title/ingredients) |
| `custom_components/recipes/views.py` | HTTP API (`/api/recipes...`), app shell, signed media with Range support, webhook payload parsing, settings (integration options + cookies, admin), developer endpoints (`/api/recipes/<id>/debug`, `/debug/rerun`, `/debug/apply`, admin) |
| `custom_components/recipes/store.py` | All recipes in one HA Store (`.storage/recipes.recipes`), media in `/media/recipes/<slug-of-title>-<id>/` (`recipe["folder"]`; renamed when the title changes, never while the pipeline holds `media_lock`) |
| `custom_components/recipes/config_flow.py` | Setup + options (AI Task, STT, language, transcribe, to-do list, notify) |
| `custom_components/recipes/const.py` | Keys, `TAG_GROUPS` (order = filter chip order in the app; mirrored in `app.js`) |
| `custom_components/recipes/frontend/` | The PWA: `index.html`, `app.js` (vanilla JS, no build step), `app.css`, `sw.js`, manifest. Icons are drawn at runtime by `icons.py` |
| `shortcuts/build_shortcuts.py` | Builds the iOS shortcuts "Save Recipe" and "Recipe Timer" (sign on a Mac: `shortcuts sign --mode anyone`) |
| `tools/` | One-off Apple Notes export/import |
| `dev/` | Local test Home Assistant with a fake AI; e2e and UI tests (see below) |

## How a recipe is made

1. The shortcut POSTs `{url}`, `{text}` or a file to the webhook. Some apps share a whole HTML page; `sources.best_url` finds the post link inside it, and the raw input is kept in `recipe["shared"]`.
2. `pipeline.process`:
   - **Social:** yt-dlp without cookies, then with Instagram cookies, then og-meta caption. The audio is transcribed when the caption is short or doesn't look like a recipe.
   - **Web:** JSON-LD or page text.
   - **Upload / text:** used as is.
   - Then the AI Task writes the recipe, `ai.normalize` cleans it up, and a notification goes to the phone (skipped for imports).
3. The app loads `/api/recipes`; media URLs are signed (`async_sign_path`), so `<video>`/`<img>` work without headers. They are `/api/recipes/media/<id>/<file>`, whatever the folder is called.
4. Every run leaves `debug.json` in the media folder: shared input, chosen URL, caption, transcript, web text, the material and prompt sent to the AI, the raw output, timings and errors. It is not in the Store and not served as media.

## Settings and developer view

- The Settings sheet (•••) shows the integration options to admins (AI Task, language, transcribe, speech-to-text, to-do list, notify). They are the same keys as the Home Assistant options flow (`const.py`) and are saved with `async_update_entry`; the processor uses them at once.
- Developer view (admins): ••• on a recipe → Developer. Full screen on the phone, a sidebar next to the recipe from 1000px wide (on by default there, remembered per device). "Re-run AI only" uses the cached material with an extra instruction or an edited prompt, shows current next to new, and saves only on confirm.

## Design rules (Bart's preferences)

- Apple Music dark look. UI text in English, metric units with the original amount shown small.
- Liquid glass: keep it **subtle**. The current `.glass` style is the one he likes. He rejected a version with bright moving rims as "fake glimmering". Only the highlight drifts slightly while scrolling (`GlassLight` in `app.js`).
- Video: no play button and no autoplay. Tap the video to play. Pull down at the top, or tap the expand button, for in-page full screen: the hero grows to screen height and the recipe stays below it, so you just scroll on. It pauses when scrolled away and folds back only when scrolling has stopped.
- Filters: chips grouped Course / Protein / Cuisine / Extra; OR within a group, AND across groups; "All" clears. Tags on a recipe link to the filter.
- Library top right: **+** first, then **•••**.
- Sheets are attached to the bottom edge of the screen and the page behind them does not scroll.
- Ask Bart when a request is ambiguous; he often sends screenshots or screen recordings. Pull frames from recordings with ffmpeg and look at them before guessing.

## Develop and test

One-time setup on the Mac (needs `brew install python@3.14 ffmpeg node`; all three are installed on Bart's Mac):

```bash
./dev/setup.sh            # venv with Home Assistant 2026.10.4, symlinks the integration, Playwright
./dev/run.sh              # keeps running: fixture server :8000 + Home Assistant :8123
python3 dev/bootstrap.py  # once: onboarding (user dev / devpass123) + adds Recipes with the fake AI
```

The video tests fetch the fixtures as "TikTok" via `tiktok.com.localhost`, which macOS resolves to 127.0.0.1 by itself.

Every change:

```bash
python3 dev/e2e.py        # backend end to end (deletes all recipes in the dev instance)
node dev/ui_check.js      # emulated iPhone 15 Pro + a wide screen: buttons, sheets, settings, filters, video, developer view; screenshots in dev/shots/
```

Restart `dev/run.sh` after Python changes. Frontend changes only need a reload, but the asset version (`?v=`) is computed at startup, so restart to be sure. Look at the screenshots: visual changes are judged by eye. The fake AI (`dev/fake_ai`) always returns the same "Test Dish"; real extraction quality can only be checked on Bart's Home Assistant.

## Deploy to Bart's Home Assistant

1. Commit and `git push` to `main` (GitHub `B4rtLB/ha-recipes`).
2. HACS: refresh and download the repo (HACS id `1452012367`). With the Home Assistant MCP tools: `ha_manage_hacs` `update_information`, then `download`. Without them, Bart does it in HACS → Recipes → ⋮ → Redownload.
3. Restart Home Assistant (`ha_restart`). It takes 1–6 minutes; the MCP server is down meanwhile and may return 502s for a bit.
4. Check `/recipes/` serves a new `app.js?v=`, and `recipes.status` (optionally with `id`) shows the recipes are fine.
5. Bart closes and reopens the app. The service worker serves the old shell once (stale-while-revalidate).

Bart has a Home Assistant backup and allows deploying tested changes. Re-processing one recipe: `recipes.retry` with `id`.

## Gotchas

- iOS ignores `overflow: hidden` on the body in standalone mode. `ScrollLock` pins the body (`position: fixed` + negative top) while a sheet is open; code that reads `window.scrollY` must check `ScrollLock.on`.
- The sheet opens with a spring that overshoots, so it extends 48px below the screen; keep that when changing `.sheet`.
- `position: fixed` breaks inside an element with a transform. Page transitions use `animation-fill-mode: backwards` for that reason; keep it.
- iOS ignores scroll corrections during momentum scrolling. Change layout above the viewport only when scrolling has stopped, and compensate by measuring an anchor element.
- Safari has no SVG-filter backdrops (no real refraction); glass is blur, saturation and highlights.
- `yt-dlp` is pinned in `manifest.json`; bump it when TikTok or Instagram downloads break. Instagram often needs cookies (app → Settings).
- Don't edit `.storage` files by hand; use the API or services.
