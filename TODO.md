# Backlog

Bart's wishes, roughly in order. Each has notes on the approach; confirm details with Bart where marked.

## 1. Swap the library's top buttons

The **+** (add) button should come first (left) and **•••** (settings) second (right). They are in `.lib-top` in `renderLibrary()` (`app.js`).
*Ask Bart:* swap the two in place at the top right, or + at the far left and ••• at the far right? He described it as "top left corner".

## 2. Sheets: lock the page and reach the bottom

- While a sheet (add, settings, •••, shopping list) is open, the page behind must not scroll. Lock it, e.g. `overflow: hidden` on `html`/`body` plus `overscroll-behavior: contain` on the sheet, and restore it on close (`openSheet` in `app.js`). iOS standalone needs testing; a fixed-body technique with the scroll position saved may be needed.
- The sheet should run to the bottom edge of the screen; there is now a gap under it. Check `.sheet` in `app.css` (bottom offset / safe-area padding).

## 3. Readable media folder names

Media now lives in `/media/recipes/<id>/` (e.g. `01b166e00eb1`). Make it `<slug-of-title>-<id>/`, e.g. `pumpkin-tart-with-ricotta-01b166e00eb1`. Keep the id so names stay unique.

- Store the folder name on the recipe (`recipe["folder"]`); `RecipeStore.media_dir()` uses it, with the bare id as fallback.
- Rename after processing has finished, once the title is known (the pipeline writes into the folder while working). Also rename when a title changes.
- Migrate existing folders once on load, in the executor.
- Media URLs stay `/api/recipes/<id>/media/<file>`, so nothing changes in the app or the service worker cache.

## 4. Integration settings in the app

The options from Settings → Devices & services → Recipes → Configure should also be editable in the app's Settings sheet (admin users only):

- AI Task entity
- speech-to-text entity
- language (en/nl)
- transcribe on/off
- to-do list for shopping
- notification target

Approach: extend `SettingsView` (`views.py`). GET returns the current options plus choices: entity ids with friendly names for `ai_task`, `stt` and `todo`, and `notify` entities plus `notify.*` services. POST validates and calls `hass.config_entries.async_update_entry(entry, options=...)`. Check the code reads options at use time, or reload the entry. Keep the HA options flow working with the same keys (`const.py`).

## 5. Developer view

A detailed view for improving extraction quality and testing recipe customisations:

- **Data**: keep a per-recipe `debug.json` in the media folder (not in the Store, which must stay small). It should hold:
  - the raw shared input
  - the platform and the chosen URL
  - the yt-dlp result/notes
  - the full social caption
  - the full transcript
  - the web text excerpt
  - the exact material and prompt sent to the AI
  - the raw AI output
  - timings per step
  - errors

  Captions and transcripts are not stored anywhere yet.
- **API**: `GET /api/recipes/<id>/debug` (admin only).
- **UI**: on wide screens (iPad/Mac, ≥ 1000px) a sidebar next to the normal recipe page. On the phone, a "Developer" item in the ••• sheet opens it full screen.
- **Experiments**: "re-run AI only", using the cached material plus an optional extra instruction or edited prompt. Show the result side by side, and save only on confirm. This needs the AI step split from material collection in `pipeline.py`.

## Known content issues

- After re-processing, "One Pot Pasta with Sun-Dried Tomatoes and Bacon" lost the Pork tag (AI variance). Maybe reinforce the protein tag in the prompt, or add a simple keyword rule in `normalize`.
- "Curry" (Apple Notes import) fails because the note has almost nothing in it. A few imports have 0 steps because the notes had none.
- Instagram post "Cheddar Chili Garlic Bread" has no video because yt-dlp needs cookies.
