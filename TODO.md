# Backlog

Nothing planned right now. The previous list (top buttons, sheets, readable media folders, integration settings in the app, developer view) is done; see `CLAUDE.md` for how each works.

## Check on the real iPhone

These were only tested in an emulated iPhone (Chromium), not in the installed app on iOS:

- Sheets: the page behind an open sheet stays still, and the scroll position is back after closing (`ScrollLock` in `app.js`).
- Sheets run to the bottom edge, also with the home indicator.
- Developer view full screen (••• → Developer), and as a sidebar on the iPad/Mac.

## Known content issues

- "Curry" (Apple Notes import) fails because the note has almost nothing in it. A few imports have 0 steps because the notes had none.
- Instagram post "Cheddar Chili Garlic Bread" has no video because yt-dlp needs cookies (app → Settings → Instagram).
- A missing Protein tag is now filled in from the title or ingredients (`guess_protein` in `ai.py`). Existing recipes only get it when they are read again, or with "Re-run AI only" in the developer view.
