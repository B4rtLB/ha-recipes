# Backlog

Nothing planned right now. The previous list (top buttons, sheets, readable media folders, integration settings in the app, developer view) is done; see `CLAUDE.md` for how each works.

## Check on the real iPhone

These were only tested in an emulated iPhone (Chromium), not in the installed app on iOS:

- Sheets: the page behind an open sheet stays still, and the scroll position is back after closing (`ScrollLock` in `app.js`).
- Sheets run to the bottom edge, also with the home indicator.
- Developer view full screen (••• → Developer), and as a sidebar on the iPad/Mac.

## Try lean mode on a real small model

Built and tested with the fake AI only (`dev/test_parser.py`, `dev/e2e.py` section M). Still to do on Bart's Home Assistant:

- Set Extraction to Lean with an Ollama AI Task, read a TikTok, an Instagram post, a web page with and without JSON-LD and a photo; compare with "Re-run AI only" (Extraction picker).
- Send a few real `debug.json` files (Developer view data) to turn into golden fixtures in `dev/golden/`, then tune `preprocess.py` (headings, promo lines) and the parser on them.
- Dutch sources with `language: en`: a JSON-LD page in Dutch goes through the AI (translation); check that it does.

## Known content issues

- Instagram post "Cheddar Chili Garlic Bread" has no video because yt-dlp needs cookies (app → Settings → Instagram).
- A missing Protein tag is now filled in from the title or ingredients (`guess_protein` in `ai.py`). Existing recipes only get it when they are read again, or with "Re-run AI only" in the developer view.
