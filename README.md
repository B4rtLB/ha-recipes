# Recipes for Home Assistant

Save recipes from your iPhone in one tap — from TikTok, Instagram, recipe websites, photos or PDFs — and cook from a fast, full-screen web app in an Apple Music–style dark design.

Home Assistant does the heavy lifting in the background:

- **Videos**: TikTok / Instagram / YouTube videos are downloaded with [yt-dlp](https://github.com/yt-dlp/yt-dlp) and stored locally, made iPhone-friendly (H.264/HEVC `hvc1`, fast start).
- **Recipe extraction**: your existing **AI Task** entity (e.g. OpenAI) turns the caption, web page (schema.org JSON-LD), photo or PDF into a clean recipe: metric units (original in brackets), ingredient groups, steps with timers, tags. No invented ingredients.
- **Spoken recipes**: when a caption is short, the video's audio is transcribed with your **speech-to-text** entity and used as extra input.
- **Instagram without login** works for most posts. Fallbacks: your own cookies (optional) → page metadata (caption + cover photo).

## The app (`/recipes/`)

- Library with artwork grid, tag chips, favourites and search in a floating "liquid glass" tab bar.
- Recipe page: title, time and photo/video on top; video shows a thumbnail first, plays inline on tap, pauses when you scroll away.
- Ingredients you can tick off, servings stepper (scales amounts), steps you can tick off.
- Timer buttons start a timer in the iOS **Clock** app through the *Recipe Timer* shortcut.
- **Add to shopping list**: sends the ingredients you still need to a Home Assistant to-do list (e.g. `todo.shopping_list`).
- Keeps the screen on while cooking; works offline for recipes you opened before.
- Signs in with your normal Home Assistant account (HA's own OAuth), works at home and via Nabu Casa.

Open `https://<your-home-assistant>/recipes/` in Safari → Share → **Add to Home Screen**.

## Install

1. HACS → ⋮ → Custom repositories → `B4rtLB/ha-recipes`, category *Integration* → download → restart Home Assistant.
2. Settings → Devices & services → Add integration → **Recipes**. Pick your AI Task entity and speech-to-text entity.
3. Install the two shortcuts on your iPhone (see `shortcuts/`):
   - **Save Recipe** – in the share sheet of TikTok, Instagram, Safari and Photos. Sends the link/photo/PDF to the Recipes webhook.
   - **Recipe Timer** – started by the app's timer buttons; starts a Clock timer.

### Weekly supermarket offers

Recipes whose ingredients are on offer at Albert Heijn, Jumbo, Lidl or Dirk get a glow in the store's colour and show up in the **Bonus** playlist. The offers are fetched automatically (option *Refresh the weekly supermarket offers automatically*, on by default) from the shops' public offer pages, about once a week, and search words come from your AI Task. Service `recipes.refresh_discounts` fetches now (`force: true` to ignore freshness); `recipes.set_discounts` feeds a list by hand.

## API

All endpoints need a Home Assistant token, except the webhook and the app shell.

| Method | Path | |
|---|---|---|
| GET/POST | `/api/recipes` | list / add (`{"url": …}`, `{"text": …}`, multipart file) |
| GET/PATCH/DELETE | `/api/recipes/{id}` | one recipe |
| POST | `/api/recipes/{id}/retry` | process again |
| POST | `/api/recipes/{id}/shopping` | add `{"items": [...]}` to the to-do list |
| GET/POST | `/api/recipes/settings` | status / Instagram cookies (admin) |
| GET | `/api/recipes/discounts` | active supermarket discounts and, per recipe id, the discounted ingredient lines |
| PUT/DELETE | `/api/recipes/discounts/{store}` | replace / clear one supermarket (`ah`, `jumbo`, `lidl`, `dirk`) with `{"valid_from", "valid_to", "items": [{"name", "terms", "price", "was", "note"}]}` (admin) |
| POST | `/api/webhook/{webhook_id}` | share-sheet endpoint (JSON, form, or raw image/PDF body) |

Services: `recipes.add` with `url`; `recipes.set_discounts` with `store`, `valid_from`, `valid_to`, `items` (feed it from an automation or script, see below).

### Discounts

The **Bonus** playlist and the ingredient highlights come from this week's supermarket offers, kept in their own store (`.storage/recipes.discounts`). Each supermarket is replaced on its own and is only active between `valid_from` and `valid_to` (Europe/Amsterdam date). Recipes are in English but supermarkets are Dutch, so every item carries `terms`: Dutch and English keywords. An ingredient matches when all words of one term appear in its name (plurals and accents are ignored), so use specific terms (`chicken breast`, not `chicken`).

```yaml
service: recipes.set_discounts
data:
  store: ah
  valid_from: "2026-11-09"
  valid_to: "2026-11-15"
  items:
    - name: Chicken breast
      terms: [kipfilet, chicken breast, chicken fillet]
      price: "€4.99"
      was: "€6.49"
      note: 2nd half price
```

Media lives in `/media/recipes/<id>/` (outside the config folder, so it does not bloat config backups).
