// Recipes web app — vanilla JS, no build step.
// Signs in with Home Assistant's own OAuth flow, talks to /api/recipes.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem("recipes." + key); return v === null ? fallback : JSON.parse(v); }
    catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem("recipes." + key, JSON.stringify(value)); } catch { /* private mode */ }
  },
};

// ------------------------------------------------------------------ icons (SF Symbols-like)
const I = {
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  minus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M5 12h14"/></svg>',
  more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M15 4l-8 8 8 8"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.6-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4.2" height="16" rx="1.4"/><rect x="13.8" y="4" width="4.2" height="16" rx="1.4"/></svg>',
  soundOn: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 9h3.5L12 5v14l-4.5-4H4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  soundOff: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 9h3.5L12 5v14l-4.5-4H4z"/><path d="M16 9.5l5 5M21 9.5l-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/></svg>',
  heartFill: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  timer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 2M10 2.5h4M18.5 6l1.5-1.5"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19a1 1 0 0 1 1 1v13.5a.5.5 0 0 1-.5.5H6.5a1 1 0 0 0 0 2H19.5a.5.5 0 0 1 0 1h-13A2.5 2.5 0 0 1 4 18.5z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 6.5h16M9 6.5V4.5h6v2M6.5 6.5l1 13h9l1-13"/></svg>',
  retry: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3L4.5 9"/><path d="M4.5 4v5h5"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6" stroke-linecap="round"/></svg>',
  share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7.5 7.5L12 3l4.5 4.5"/><path d="M5 12v7.5h14V12"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>',
  pot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10h16v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"/><path d="M2 10h2M20 10h2M9 3.5c0 1.5 1 1.5 1 3M13 3.5c0 1.5 1 1.5 1 3"/></svg>',
  photo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="9" cy="10" r="1.6"/><path d="M21 15l-5-4.5L7 19"/></svg>',
  cart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h2.5l2.2 10.5a1.5 1.5 0 0 0 1.5 1.2h7.9a1.5 1.5 0 0 0 1.5-1.1L20.5 8H6.3"/><circle cx="10" cy="20" r="1.3"/><circle cx="17" cy="20" r="1.3"/></svg>',
  code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/></svg>',
  tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7a1 1 0 0 1 .7.3l7.6 7.6a1.5 1.5 0 0 1 0 2.1l-6.2 6.2a1.5 1.5 0 0 1-2.1 0L3.8 12.9a1 1 0 0 1-.3-.7z"/><circle cx="8.3" cy="8.3" r="1.4" fill="currentColor"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h3.5c5 0 6 10 11 10H21M3 17h3.5c1.8 0 3-1 4-2.2M13.5 9.2C14.5 8 15.7 7 17.5 7H21M18.5 4L21.5 7l-3 3M18.5 14l3 3-3 3"/></svg>',
  paste: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16.5" rx="2.5"/><path d="M9 4.5V3h6v1.5"/></svg>',
};

// ------------------------------------------------------------------ auth (HA OAuth)
const ORIGIN = location.origin;
const CLIENT_ID = ORIGIN + "/";
const REDIRECT = ORIGIN + "/recipes/";

const Auth = {
  tokens: store.get("auth", null),
  save(t) { this.tokens = t; store.set("auth", t); },
  login() {
    const state = Math.random().toString(36).slice(2);
    store.set("oauth_state", state);
    const url = new URL("/auth/authorize", ORIGIN);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", CLIENT_ID);
    url.searchParams.set("redirect_uri", REDIRECT);
    url.searchParams.set("state", state);
    location.assign(url.toString());
  },
  async tokenRequest(body) {
    const res = await fetch("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: CLIENT_ID, ...body }),
    });
    if (!res.ok) throw new Error("auth " + res.status);
    return res.json();
  },
  async handleCallback() {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    if (!code) return false;
    history.replaceState(null, "", "/recipes/" + location.hash);
    const t = await this.tokenRequest({ grant_type: "authorization_code", code });
    this.save({ access: t.access_token, refresh: t.refresh_token, exp: Date.now() + t.expires_in * 1000 });
    return true;
  },
  async access() {
    if (!this.tokens) { this.login(); throw new Error("login"); }
    if (Date.now() > this.tokens.exp - 60_000) {
      try {
        const t = await this.tokenRequest({ grant_type: "refresh_token", refresh_token: this.tokens.refresh });
        this.save({ ...this.tokens, access: t.access_token, exp: Date.now() + t.expires_in * 1000 });
      } catch (err) {
        if (String(err).includes("auth 4")) { this.save(null); this.login(); }
        throw err;
      }
    }
    return this.tokens.access;
  },
};

async function api(path, opts = {}) {
  const token = await Auth.access();
  const headers = { Authorization: "Bearer " + token, ...(opts.headers || {}) };
  let body = opts.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch("/api/recipes" + path, { ...opts, headers, body });
  if (res.status === 401) { Auth.save(null); Auth.login(); throw new Error("unauthorized"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "Request failed (" + res.status + ")");
  return data;
}

// ------------------------------------------------------------------ helpers
const PLATFORM = { tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube", web: "Web", upload: "Photo", text: "Text", notes: "Notes" };
const PLURAL = { clove: "cloves", can: "cans", bunch: "bunches", slice: "slices", sprig: "sprigs", stalk: "stalks", piece: "pieces", pinch: "pinches", handful: "handfuls", cup: "cups", sheet: "sheets", leaf: "leaves", packet: "packets", jar: "jars", tin: "tins" };
const unitLabel = (u, q) => (q != null && q > 1 && PLURAL[u]) ? PLURAL[u] : u;

function hash(str) { let h = 2166136261; for (const c of str) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; }
function genArt(title, big = false) {
  const h = hash(title || "?");
  const a = h % 360, b = (a + 35 + (h >> 9) % 60) % 360;
  const style = `background: radial-gradient(120% 90% at 0% 0%, hsl(${a} 80% 58%), transparent 60%),
    radial-gradient(120% 120% at 100% 100%, hsl(${b} 75% 42%), transparent 65%), hsl(${(a + b) / 2} 55% 22%);`;
  // On the recipe page the real title sits right below, so the big version has no text.
  return `<div class="gen-art ${big ? "big" : ""}" style="${style}">${big ? "" : esc(title || "")}</div>`;
}

function minutesLabel(min) {
  if (!min) return null;
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60;
  return m ? `${h} h ${m}` : `${h} h`;
}

function secondsLabel(s) {
  if (s >= 3600) { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return m ? `${h} h ${m} min` : `${h} h`; }
  if (s >= 60) { const m = Math.floor(s / 60), r = s % 60; return r ? `${m}:${String(r).padStart(2, "0")} min` : `${m} min`; }
  return `${s} sec`;
}

function clock(s) {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(r).padStart(2, "0");
}

const FRACTIONS = [[0.125, "⅛"], [0.25, "¼"], [0.333, "⅓"], [0.5, "½"], [0.667, "⅔"], [0.75, "¾"]];
function formatQty(q, unit) {
  if (q == null) return "";
  const u = (unit || "").toLowerCase();
  const metricBulk = ["g", "ml"].includes(u);
  if (metricBulk) {
    if (q >= 100) return String(Math.round(q / 5) * 5);
    if (q >= 10) return String(Math.round(q));
    return String(Math.round(q * 10) / 10).replace(".", ",");
  }
  if (["kg", "l"].includes(u)) return String(Math.round(q * 100) / 100).replace(".", ",");
  const whole = Math.floor(q), frac = q - whole;
  if (frac < 0.06) return String(whole || (q > 0 ? "" : "0")) || String(Math.round(q * 100) / 100);
  if (frac > 0.94) return String(whole + 1);
  const best = FRACTIONS.reduce((a, b) => (Math.abs(b[0] - frac) < Math.abs(a[0] - frac) ? b : a));
  if (Math.abs(best[0] - frac) < 0.06) return (whole ? whole : "") + best[1];
  return String(Math.round(q * 10) / 10).replace(".", ",");
}

function toast(msg, ms = 2400) {
  const el = $("#toast");
  el.className = "glass dense show";
  el.textContent = msg;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), ms);
}

function lazyImg(src, alt = "") {
  if (!src) return "";
  return `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" onload="this.classList.add('loaded')">`;
}

// ------------------------------------------------------------------ state
const state = {
  recipes: null,
  filters: new Set(store.get("filters", [])),
  tab: "all",
  search: "",
  searching: false,
  current: null,
  discounts: null, // {stores, recipes}: this week's offers, matched server-side
  shuffle: null, // {pool, queue, last, busy}: set while a shuffle session runs
  admin: false,
};
let pollTimer = null;

// Whether the signed-in user is a Home Assistant admin (developer view, integration settings).
let adminReady = Promise.resolve();
function loadAdmin() {
  adminReady = api("/settings").then((info) => { state.admin = !!info.is_admin; }).catch(() => {});
  return adminReady;
}

// While a sheet is open the page behind it must not scroll. iOS ignores
// overflow:hidden on the body in standalone mode, so the body is pinned
// instead and the scroll position is put back afterwards.
const ScrollLock = {
  on: false,
  y: 0,
  lock() {
    if (this.on) return;
    this.on = true;
    this.y = window.scrollY;
    document.body.style.top = -this.y + "px";
    document.documentElement.classList.add("locked");
  },
  unlock() {
    if (!this.on) return;
    this.on = false;
    document.documentElement.classList.remove("locked");
    document.body.style.top = "";
    window.scrollTo(0, this.y);
  },
};

async function loadList() {
  const data = await api("");
  state.recipes = data.recipes;
  await loadDiscounts();
  schedulePoll();
  return state.recipes;
}

function schedulePoll() {
  clearTimeout(pollTimer);
  const busy = (state.recipes || []).some((r) => r.status === "queued" || r.status === "processing");
  if (busy) pollTimer = setTimeout(async () => {
    const before = JSON.stringify(state.recipes.map((r) => [r.id, r.status, r.progress]));
    await loadList().catch(() => {});
    const after = JSON.stringify(state.recipes.map((r) => [r.id, r.status, r.progress]));
    if (before !== after && route().name === "library") renderLibrary(false);
  }, 3000);
}

// ------------------------------------------------------------------ router
function route() {
  const m = location.hash.match(/^#\/r\/([\w-]+)/);
  return m ? { name: "detail", id: m[1] } : { name: "library" };
}

async function render() {
  cleanupDetail();
  $("#sheet-root").innerHTML = "";
  ScrollLock.unlock();
  const r = route();
  if (r.name !== "detail") state.shuffle = null; // leaving to the library ends a shuffle session
  if (r.name === "detail") return renderDetail(r.id);
  return renderLibrary(true);
}

// ------------------------------------------------------------------ library
// Same groups (and order) as the backend's TAG_GROUPS.
const TAG_GROUPS = [
  ["Course", ["Main", "Breakfast", "Lunch", "Snack", "Dessert", "Baking", "Sauce"]],
  ["Protein", ["Chicken", "Beef", "Pork", "Fish", "Seafood", "Vegetarian"]],
  ["Cuisine", ["Indian", "Somali", "Asian", "MiddleEastern", "Mexican", "Mediterranean", "Dutch"]],
  ["Extra", ["Quick", "MealPrep", "Video"]],
];
const groupOf = (tag) => (TAG_GROUPS.find(([, tags]) => tags.includes(tag)) || ["Other"])[0];
const tagLabel = (t) => ({ MiddleEastern: "Middle Eastern", MealPrep: "Meal Prep" })[t] || t;

function saveFilters() { store.set("filters", [...state.filters]); }

function setOnlyFilter(tag) {
  state.filters = new Set([tag]);
  saveFilters();
}

// Within a group a recipe may match any selected tag (Chicken OR Beef),
// across groups it must match all (Main AND Chicken AND Quick).
function matchesFilters(r) {
  const byGroup = {};
  for (const t of state.filters) (byGroup[groupOf(t)] ||= []).push(t);
  return Object.values(byGroup).every((tags) =>
    tags.some((t) => (t === "Video" ? r.has_video : (r.tags || []).includes(t)))
  );
}

function visibleRecipes() {
  let list = state.recipes || [];
  if (state.tab === "fav") list = list.filter((r) => r.favorite);
  if (state.filters.size) list = list.filter(matchesFilters);
  const q = state.search.trim().toLowerCase();
  if (q) list = list.filter((r) => (r.title || "").toLowerCase().includes(q) || (r.tags || []).some((t) => t.toLowerCase().includes(q)));
  return list;
}

function cardHTML(r) {
  const sub = [minutesLabel(r.total_min), PLATFORM[r.platform]].filter(Boolean).join(" · ");
  let state_ = "";
  const busy = r.status === "queued" || r.status === "processing";
  if (busy) state_ = `<div class="state glass dense"><span class="spinner"></span>${esc(r.progress || "Waiting")}</div>`;
  if (r.status === "error") state_ = `<div class="state glass dense"><span class="err-dot"></span>Couldn't read</div>`;
  const art = r.image_url ? lazyImg(r.image_url, r.title) : genArt(r.title || (busy ? "" : "Recipe"));
  const badge = r.has_video && !busy ? `<span class="badge glass">${I.play}</span>` : "";
  return `<a class="card" href="#/r/${r.id}">
    <div class="art ${busy ? "busy" : ""}">${art}${badge}${state_}</div>
    <div class="card-title">${esc(r.title || (busy ? "Saving recipe…" : "Untitled"))}</div>
    <div class="card-sub">${esc(sub || (busy ? "Processing" : ""))}</div>
  </a>`;
}

function chipsHTML() {
  const present = new Set();
  for (const r of state.recipes || []) {
    for (const t of r.tags || []) present.add(t);
    if (r.has_video) present.add("Video");
  }
  for (const t of [...state.filters]) if (!present.has(t)) state.filters.delete(t);
  let html = `<button class="chip glass press" data-chip="" aria-pressed="${state.filters.size === 0}">All</button>`;
  for (const [, tags] of TAG_GROUPS) {
    const shown = tags.filter((t) => present.has(t));
    if (!shown.length) continue;
    html += `<span class="chip-sep" aria-hidden="true"></span>`;
    html += shown.map((t) => `<button class="chip glass press" data-chip="${esc(t)}" aria-pressed="${state.filters.has(t)}">${esc(tagLabel(t))}</button>`).join("");
  }
  return html;
}

function filterTitle() {
  if (state.search) return "Results";
  if (!state.filters.size) return "Recently Added";
  return [...state.filters].map(tagLabel).join(" · ");
}

async function renderLibrary(fetch_ = true) {
  const app = $("#app");
  if (fetch_ || !state.recipes) {
    if (!state.recipes) app.innerHTML = `<div class="splash"><div><img src="/recipes/static/icons/icon-180.png" alt=""><p>Loading recipes…</p></div></div>`;
    try { await loadList(); } catch (err) { if (!state.recipes) { app.innerHTML = errorSplash(err); return; } }
  }
  const scroll = window.scrollY;
  const plX = $(".pl-row")?.scrollLeft || 0;
  const list = visibleRecipes();
  const count = (state.recipes || []).filter((r) => r.status === "ready").length;
  const title = state.tab === "fav" ? "Favourites" : "Recipes";
  app.innerHTML = `<main class="library ${fetch_ ? "page" : ""}">
    <div class="scroll-edge" id="edge"></div>
    <div class="lib-top" id="libtop">
      <div class="compact">${title}</div>
      <button class="icon-btn glass press accent" data-act="add" aria-label="Add recipe">${I.plus}</button>
      <button class="icon-btn glass press" data-act="settings" aria-label="Settings">${I.more}</button>
    </div>
    <div class="lib-top-space"></div>
    <h1 class="large-title" id="ltitle">${title}</h1>
    <div class="lib-sub">${count} recipe${count === 1 ? "" : "s"}</div>
    <div class="chips">${chipsHTML()}</div>
    ${playlistsHTML()}
    ${list.length ? `<div class="section-head"><h2>${esc(filterTitle())}</h2></div>
      <div class="grid">${list.map(cardHTML).join("")}</div>`
      : emptyHTML()}
  </main>
  ${tabbarHTML()}`;
  if (!fetch_) window.scrollTo(0, scroll);
  if (plX && $(".pl-row")) $(".pl-row").scrollLeft = plX;
  bindLibrary();
  GlassLight.update();
}

// ------------------------------------------------------------------ playlists
// A row of tiles between the filter chips and the grid. Shuffle opens a random
// recipe (of the filtered list) and starts a session; Bonus does the same over
// the recipes with ingredients on offer this week. In a session a swipe from
// right to left goes forward (through the history, then on to a new random
// recipe), a swipe from left to right goes back through the last 5. The third
// tile is a placeholder.
const HISTORY = 5; // how many recipes you can go back

const STORE_SHORT = { ah: "AH", jumbo: "Jumbo", lidl: "Lidl", dirk: "Dirk" };
const STORE_NAME = { ah: "Albert Heijn", jumbo: "Jumbo", lidl: "Lidl", dirk: "Dirk" };

async function loadDiscounts() {
  try { state.discounts = await api("/discounts"); } catch { state.discounts = state.discounts || null; }
}

// Recipes (ready) with at least BONUS_MIN ingredient lines on offer, most offers first. Four shops
// have hundreds of offers a week, so nearly every recipe has one or two lines on offer; the Bonus
// playlist is for the ones where a real part of the shopping is cheaper.
const BONUS_MIN = 4;
function bonusRecipes() {
  const d = state.discounts;
  if (!d || !Object.keys(d.stores || {}).length) return [];
  return (state.recipes || []).filter((r) => r.status === "ready" && (d.recipes?.[r.id]?.count || 0) >= BONUS_MIN)
    .sort((a, b) => d.recipes[b.id].count - d.recipes[a.id].count);
}

function shufflePool() {
  const ready = (r) => r.status === "ready";
  const filtered = visibleRecipes().filter(ready);
  return filtered.length ? filtered : (state.recipes || []).filter(ready);
}

function playlistsHTML() {
  if (state.searching || !(state.recipes || []).some((r) => r.status === "ready")) return "";
  const n = shufflePool().length;
  const sub = `${n} recipe${n === 1 ? "" : "s"}${state.filters.size && visibleRecipes().some((r) => r.status === "ready") ? " · filtered" : ""}`;
  const b = bonusRecipes().length;
  const bonusSub = b ? `${b} recipe${b === 1 ? "" : "s"} on offer` : "No offers yet";
  return `<div class="section-head"><h2>Playlists</h2></div>
  <div class="pl-row" role="list">
    <button class="pl-card" role="listitem" data-pl="shuffle" aria-label="Shuffle, ${esc(sub)}">
      <div class="art pl-art pl-shuffle">${I.shuffle}</div>
      <div class="card-title">Shuffle</div><div class="card-sub">${esc(sub)}</div></button>
    ${b ? `<button class="pl-card" role="listitem" data-pl="bonus" aria-label="Bonus, ${esc(bonusSub)}">
      <div class="art pl-art pl-bonus">${I.tag}</div>
      <div class="card-title">Bonus</div><div class="card-sub">${esc(bonusSub)}</div></button>`
    : `<div class="pl-card disabled" role="listitem" aria-disabled="true" data-pl-off="bonus">
      <div class="art pl-art pl-bonus">${I.tag}</div>
      <div class="card-title">Bonus</div><div class="card-sub">${esc(bonusSub)}</div></div>`}
    <div class="pl-card disabled" role="listitem" aria-disabled="true">
      <div class="art pl-art pl-soon-b"><span>${I.plus}</span></div>
      <div class="card-title">Playlist 3</div><div class="card-sub">Coming soon</div></div>
  </div>`;
}

// The queue is a shuffled "bag": every recipe once before any repeats, and a
// new bag never starts with the recipe that was just shown.
function shuffleBag(ids, last) {
  const a = ids.slice();
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  if (a.length > 1 && a[0] === last) [a[0], a[1]] = [a[1], a[0]];
  return a;
}

function nextShuffleId() {
  const sh = state.shuffle;
  if (!sh) return null;
  const alive = new Set((state.recipes || []).filter((r) => r.status === "ready").map((r) => r.id));
  const last = sh.hist[sh.hist.length - 1];
  if (!sh.queue.length) sh.queue = shuffleBag(sh.pool.filter((id) => alive.has(id)), last);
  let id;
  while ((id = sh.queue.shift()) && !alive.has(id)) { /* deleted meanwhile */ }
  return id || null;
}

function startSession(kind, pool, first) {
  state.shuffle = { kind, pool, queue: first ? [first, ...shuffleBag(pool.filter((i) => i !== first), first)] : [], hist: [], pos: 0, busy: false, hinted: false };
  const id = nextShuffleId();
  state.shuffle.hist = [id];
  location.hash = "#/r/" + id;
}

function startShuffle() {
  const pool = shufflePool().map((r) => r.id);
  if (!pool.length) { toast("Nothing to shuffle yet"); return; }
  startSession("shuffle", pool);
}

function startBonus() {
  const list = bonusRecipes();
  if (!list.length) { toast("No offers yet"); return; }
  // open with a recipe that has the most discounted ingredients, the rest in random order
  const top = list.filter((r) => state.discounts.recipes[r.id].count === state.discounts.recipes[list[0].id].count);
  startSession("bonus", list.map((r) => r.id), top[Math.floor(Math.random() * top.length)].id);
}

const detailParts = (det) => [...det.children].filter((c) => !c.matches(".nav-bar, .nav-float")); // fixed children must not sit inside a transform

// dir: 1 = forward (swipe right to left), -1 = back (left to right)
async function shuffleGo(dir) {
  const sh = state.shuffle, det = $(".detail");
  if (!sh || sh.busy || !det) return;
  let id, pos = sh.pos + dir, fresh = false;
  if (dir < 0) {
    if (sh.pos <= 0) { swipeReset(det); return; }
    id = sh.hist[pos];
  } else if (pos < sh.hist.length) {
    id = sh.hist[pos];
  } else {
    if (sh.pool.length < 2) { toast("That's the only recipe in this shuffle"); swipeReset(det); return; }
    id = nextShuffleId(); fresh = true;
    if (!id || id === sh.hist[sh.pos]) { swipeReset(det); return; }
  }
  sh.busy = true;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const parts = detailParts(det);
  const fetched = api("/" + id).catch((err) => { toast(err.message); return null; });
  if (!reduce) {
    parts.forEach((c) => { c.style.transition = "transform 0.22s var(--ease), opacity 0.22s var(--ease)"; c.style.transform = `translateX(${-dir * 60}vw)`; c.style.opacity = "0"; });
    await new Promise((res) => setTimeout(res, 230));
  }
  const r = await fetched;
  if (!r || route().name !== "detail" || !state.shuffle) { sh.busy = false; parts.forEach((c) => { c.style.transform = c.style.opacity = c.style.transition = ""; }); return; }
  if (fresh) { sh.hist.push(id); if (sh.hist.length > HISTORY + 1) { sh.hist.shift(); pos--; } }
  sh.pos = pos;
  history.replaceState(null, "", "#/r/" + id); // Back goes to the library, not through the shuffle
  cleanupDetail();
  $("#sheet-root").innerHTML = "";
  await renderDetail(id, { slide: dir, data: r });
  sh.busy = false;
}

function swipeReset(det) {
  detailParts(det).forEach((c) => { c.style.transition = "transform 0.3s var(--spring), opacity 0.3s"; c.style.transform = ""; c.style.opacity = ""; });
  setTimeout(() => [...det.children].forEach((c) => { c.style.transition = ""; }), 320);
}

// Swipes while a shuffle session runs. Only a clearly horizontal move counts, so
// vertical scrolling, the hero pull-down and the video scrub bar keep working;
// the page follows the finger a little as feedback.
function setupShuffleSwipe() {
  if (!state.shuffle) return;
  const det = $(".detail");
  det.classList.add("shuffling");
  let x0 = null, y0 = 0, t0 = 0, mode = "";
  const onStart = (e) => {
    mode = "";
    x0 = e.touches.length === 1 && !state.shuffle?.busy && !ScrollLock.on && !hasHorizontalScroller(e.target) ? e.touches[0].clientX : null;
    y0 = e.touches[0].clientY; t0 = Date.now();
  };
  const onMove = (e) => {
    if (x0 == null || mode === "v") return;
    const dx = e.touches[0].clientX - x0, dy = e.touches[0].clientY - y0;
    if (!mode) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      mode = Math.abs(dx) > Math.abs(dy) * 1.6 ? "h" : "v";
      if (mode === "v") return;
    }
    if (e.cancelable) e.preventDefault();
    Swipe.horizontal = true;
    const sh = state.shuffle, canBack = sh.pos > 0;
    const px = dx < 0 ? dx * 0.55 : dx * (canBack ? 0.55 : 0.12);
    detailParts(det).forEach((c) => { c.style.transition = "none"; c.style.transform = `translateX(${px}px)`; c.style.opacity = String(1 - Math.min(0.5, Math.abs(px) / 320)); });
  };
  const onEnd = (e) => {
    const wasH = mode === "h";
    const dx = (e.changedTouches?.[0]?.clientX ?? x0) - (x0 ?? 0);
    const fast = Math.abs(dx) > 40 && Date.now() - t0 < 260;
    x0 = null; mode = ""; Swipe.horizontal = false;
    if (!wasH) return;
    if (dx < -90 || (fast && dx < 0)) shuffleGo(1);
    else if (dx > 90 || (fast && dx > 0)) shuffleGo(-1);
    else swipeReset(det);
  };
  const onKey = (e) => {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "")) return;
    if (e.key === "ArrowRight") shuffleGo(1); else if (e.key === "ArrowLeft") shuffleGo(-1);
  };
  document.addEventListener("touchstart", onStart, { passive: true });
  document.addEventListener("touchmove", onMove, { passive: false });
  document.addEventListener("touchend", onEnd);
  document.addEventListener("touchcancel", onEnd);
  document.addEventListener("keydown", onKey);
  detailCleanup.push(() => {
    document.removeEventListener("touchstart", onStart); document.removeEventListener("touchmove", onMove);
    document.removeEventListener("touchend", onEnd); document.removeEventListener("touchcancel", onEnd);
    document.removeEventListener("keydown", onKey);
  });
  if (!state.shuffle.hinted) { state.shuffle.hinted = true; toast("Swipe left for next, right for back", 3200); }
}
const Swipe = { horizontal: false };
const hasHorizontalScroller = (el) => !!el.closest(".scrub, .sheet, .dev-panel, .timers, .stepper");

function emptyHTML() {
  if ((state.recipes || []).length === 0) {
    return `<div class="empty">${I.pot}<h3>No recipes yet</h3>Share a TikTok, Instagram post or recipe website with the <b>Save Recipe</b> shortcut, or tap + to paste a link.</div>`;
  }
  return `<div class="empty">${I.search}<h3>Nothing found</h3>Try another search or filter.</div>`;
}

function tabbarHTML() {
  if (state.searching) {
    return `<nav class="tabbar"><label class="searchbar glass">${I.search}<input id="q" type="search" placeholder="Recipes, ingredients, tags" value="${esc(state.search)}" autocomplete="off" enterkeyhint="search"></label>
      <button class="search-btn glass press" data-act="close-search" aria-label="Close search">${I.plus.replace("<path", '<path transform="rotate(45 12 12)"')}</button></nav>`;
  }
  return `<nav class="tabbar">
    <div class="tabs glass" role="tablist">
      <button class="tab press" role="tab" data-tab="all" aria-selected="${state.tab === "all"}">${I.book}Library</button>
      <button class="tab press" role="tab" data-tab="fav" aria-selected="${state.tab === "fav"}">${I.star}Favourites</button>
    </div>
    <button class="search-btn glass press" data-act="search" aria-label="Search">${I.search}</button>
  </nav>`;
}

let libScroll = null;
function bindLibrary() {
  // compact title + scroll edge once the large title has scrolled under the buttons
  const top = $("#libtop"), edge = $("#edge"), lt = $("#ltitle");
  if (libScroll) window.removeEventListener("scroll", libScroll);
  libScroll = () => {
    if (!top.isConnected) { window.removeEventListener("scroll", libScroll); libScroll = null; return; }
    if (ScrollLock.on) return;
    const past = lt.getBoundingClientRect().bottom < top.getBoundingClientRect().bottom + 44;
    top.classList.toggle("scrolled", past);
    edge.classList.toggle("show", window.scrollY > 4);
  };
  window.addEventListener("scroll", libScroll, { passive: true });
  libScroll();

  $$("[data-chip]").forEach((b) => b.onclick = () => {
    const tag = b.dataset.chip;
    if (!tag) state.filters.clear();
    else if (state.filters.has(tag)) state.filters.delete(tag);
    else state.filters.add(tag);
    saveFilters();
    const chips = $(".chips"), x = chips.scrollLeft;
    renderLibrary(false);
    $(".chips").scrollLeft = x;
  });
  $('[data-pl="shuffle"]')?.addEventListener("click", startShuffle);
  $('[data-pl="bonus"]')?.addEventListener("click", startBonus);
  $('[data-pl-off="bonus"]')?.addEventListener("click", () => toast("No offers yet. They show up when this week's discounts are added."));
  $$("[data-tab]").forEach((b) => b.onclick = () => { state.tab = b.dataset.tab; window.scrollTo(0, 0); renderLibrary(false); });
  $('[data-act="add"]').onclick = openAddSheet;
  $('[data-act="settings"]').onclick = openSettingsSheet;
  const s = $('[data-act="search"]');
  if (s) s.onclick = () => { state.searching = true; renderLibrary(false); setTimeout(() => $("#q")?.focus(), 30); };
  const c = $('[data-act="close-search"]');
  if (c) c.onclick = () => { state.searching = false; state.search = ""; renderLibrary(false); };
  const q = $("#q");
  if (q) q.oninput = () => {
    state.search = q.value;
    const grid = $(".grid");
    const list = visibleRecipes();
    if (grid && list.length) grid.innerHTML = list.map(cardHTML).join("");
    else { renderLibrary(false); const nq = $("#q"); nq.focus(); nq.setSelectionRange(nq.value.length, nq.value.length); }
  };
}

function errorSplash(err) {
  return `<div class="splash"><div><img src="/recipes/static/icons/icon-180.png" alt="">
    <h3>Can't reach Home Assistant</h3><p>${esc(err.message || err)}</p>
    <button class="btn plain press" onclick="location.reload()">Try again</button></div></div>`;
}

// ------------------------------------------------------------------ detail
let detailCleanup = [];
function cleanupDetail() { detailCleanup.forEach((f) => f()); detailCleanup = []; Dev.close(); }

async function renderDetail(id, opts = {}) {
  const app = $("#app");
  const cached = (state.recipes || []).find((r) => r.id === id);
  if (cached && !app.querySelector(".detail")) {
    app.innerHTML = `<div class="detail page"><div class="hero">${cached.image_url ? `<img class="poster" src="${esc(cached.image_url)}" alt="">` : genArt(cached.title, true)}<div class="fade"></div></div>
      <div class="head"><h1 class="title">${esc(cached.title || "")}</h1></div></div>`;
  }
  let r;
  try { r = opts.data || await api("/" + id); }
  catch (err) { app.innerHTML = errorSplash(err); return; }
  if (route().id !== id) return;
  state.current = r;
  window.scrollTo(0, 0);
  app.innerHTML = detailHTML(r);
  if (opts.slide) { const d = $(".detail"); d.classList.remove("page"); d.classList.add(opts.slide > 0 ? "slide-in" : "slide-in-back"); }
  bindDetail(r);
  setupShuffleSwipe();
  // Wide screens: the developer sidebar sits next to the recipe (admins, until closed).
  if (Dev.el) Dev.open(r);
  else adminReady.then(() => { if (state.admin && Dev.wide() && store.get("dev", true) && route().id === id) Dev.open(r); });
  if (r.status === "queued" || r.status === "processing") {
    const t = setTimeout(() => route().id === id && renderDetail(id), 3000);
    detailCleanup.push(() => clearTimeout(t));
  }
}

function sourceLink(r) {
  const src = r.source || {};
  const url = src.url_canonical || src.url;
  if (!url) return "";
  const who = src.author ? (src.platform === "web" ? src.author : "@" + String(src.author).replace(/^@/, "")) : null;
  let host = "";
  try { host = new URL(url).hostname.replace(/^www\./, ""); } catch { /* ignore */ }
  const label = PLATFORM[src.platform] && src.platform !== "web" ? PLATFORM[src.platform] : host;
  return `<div class="source-row">${I.link}<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}${who ? " · " + esc(who) : ""}</a></div>`;
}

function factsHTML(r) {
  const facts = [];
  const est = r.estimated ? "<small> est.</small>" : "";
  if (r.total_min) facts.push(["Total", minutesLabel(r.total_min) + est]);
  if (r.prep_min) facts.push(["Prep", minutesLabel(r.prep_min)]);
  if (r.cook_min) facts.push(["Cook", minutesLabel(r.cook_min)]);
  if (r.servings_text) facts.push(["Makes", esc(r.servings_text)]);
  else if (r.servings) facts.push(["Serves", String(r.servings)]);
  if (!facts.length) return "";
  return `<div class="facts">${facts.map(([k, v]) => `<div class="fact glass"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("")}</div>`;
}

function heroHTML(r) {
  const m = r.media || {};
  const portrait = m.width && m.height ? m.height / m.width > 1.1 : true;
  const poster = r.poster_url || r.image_url;
  if (r.video_url) {
    const dur = m.duration ? clock(m.duration) : "";
    return `<div class="hero ${portrait ? "" : "square"}" id="hero">
      ${poster ? `<img class="poster" src="${esc(poster)}" alt="">` : ""}
      <video id="vid" playsinline webkit-playsinline preload="none" ${poster ? `poster="${esc(poster)}"` : ""} src="${esc(r.video_url)}"></video>
      <div class="top-fade"></div><div class="fade"></div>
      <div class="pull-hint" id="pullhint">${I.expand}<span>Pull for full screen</span></div>
      <div class="video-ui"><div class="scrub" id="scrub"><div class="scrub-track"><div class="scrub-fill" id="fill"></div></div></div>
        ${dur ? `<span class="vid-time" id="vtime">${dur}</span>` : ""}
        <button class="icon-btn glass press" id="full" aria-label="Full screen">${I.expand}</button>
        <button class="icon-btn glass press" id="mute" aria-label="Mute">${I.soundOn}</button></div>
    </div>`;
  }
  if (poster) return `<div class="hero ${portrait ? "" : "square"}"><img class="poster" src="${esc(poster)}" alt=""><div class="top-fade"></div><div class="fade"></div></div>`;
  return `<div class="hero square no-media">${genArt(r.title, true)}<div class="fade"></div></div>`;
}

// "On offer" under an ingredient: one small pill per supermarket (colour dot AND its name), with price and note.
function dealHTML(deal) {
  return `<span class="deal-info">${deal.offers.map((o) => {
    const price = [o.price, o.was ? `was ${o.was}` : "", o.note].filter(Boolean).join(" · ");
    return `<span class="deal-pill s-${o.store}" title="${esc(STORE_NAME[o.store])}: ${esc(o.item)}"><i></i>${esc(STORE_SHORT[o.store])}${price ? `<span class="deal-price"> ${esc(price)}</span>` : ""}</span>`;
  }).join("")}</span>`;
}

function ingredientsHTML(r, factor) {
  const checked = new Set(store.get("checked." + r.id, []));
  return (r.ingredient_groups || []).map((g, gi) => `
    ${g.name ? `<div class="group-name">${esc(g.name)}</div>` : ""}
    <ul class="ingredients">${g.items.map((it, ii) => {
      const key = gi + "." + ii;
      let qty = "";
      if (it.qty != null) {
        qty = formatQty(it.qty * factor, it.unit);
        if (it.qty_max != null) qty += "–" + formatQty(it.qty_max * factor, it.unit);
        if (it.unit) qty += " " + esc(unitLabel(it.unit, (it.qty_max ?? it.qty) * factor));
      }
      const orig = it.original && factor === 1 ? ` <span class="orig">${esc(it.original)}</span>` : "";
      const deal = (r.offers || {})[key];
      return `<li class="ing ${checked.has(key) ? "done" : ""}${deal ? " deal deal-" + deal.best : ""}" data-ing="${key}">
        <span class="check">${I.check}</span>
        <span class="txt">${qty ? `<span class="qty">${qty}</span> ` : ""}${esc(it.name)}${it.note ? `<span class="note">, ${esc(it.note)}</span>` : ""}${orig}${deal ? dealHTML(deal) : ""}</span></li>`;
    }).join("")}</ul>`).join("");
}

function ingredientText(it, factor) {
  let qty = "";
  if (it.qty != null) {
    qty = formatQty(it.qty * factor, it.unit);
    if (it.qty_max != null) qty += "–" + formatQty(it.qty_max * factor, it.unit);
    if (it.unit) qty += " " + unitLabel(it.unit, (it.qty_max ?? it.qty) * factor);
  }
  return [qty, it.name].filter(Boolean).join(" ") + (it.note ? ", " + it.note : "");
}

function openShoppingSheet(r) {
  const factor = r.servings ? store.get("servings." + r.id, r.servings) / r.servings : 1;
  const have = new Set(store.get("checked." + r.id, []));
  const rows = [];
  (r.ingredient_groups || []).forEach((g, gi) => g.items.forEach((it, ii) => rows.push({ key: gi + "." + ii, text: ingredientText(it, factor), on: !have.has(gi + "." + ii) })));
  openSheet(`<h3>Shopping List</h3>
    <p class="hint">Ingredients you already ticked off are left out.</p>
    <ul class="ingredients" id="shop">${rows.map((x) => `<li class="ing ${x.on ? "done" : ""}" data-k="${x.key}"><span class="check">${I.check}</span><span class="txt" style="text-decoration:none;color:var(--label)">${esc(x.text)}</span></li>`).join("")}</ul>
    <div class="actions"><button class="btn primary press" id="shop-go">Add to list</button></div>`,
  (sh, close) => {
    const count = () => { const n = $$(".ing.done", sh).length; $("#shop-go", sh).textContent = n ? `Add ${n} item${n === 1 ? "" : "s"}` : "Nothing selected"; $("#shop-go", sh).disabled = !n; };
    $("#shop", sh).onclick = (e) => { const li = e.target.closest("[data-k]"); if (li) { li.classList.toggle("done"); count(); } };
    count();
    $("#shop-go", sh).onclick = async () => {
      const items = $$(".ing.done", sh).map((li) => rows.find((x) => x.key === li.dataset.k).text);
      try { const res = await api("/" + r.id + "/shopping", { method: "POST", body: { items } }); close(); toast(`Added ${res.added} to your list`); }
      catch (err) { toast(err.message); }
    };
  });
}

function stepsHTML(r) {
  const done = new Set(store.get("steps." + r.id, []));
  return `<ol class="steps">${(r.steps || []).map((s, i) => `
    <li class="step ${done.has(i) ? "done" : ""}" data-step="${i}">
      <span class="num">${i + 1}</span>
      <div class="body"><p>${esc(s.text)}</p>
      ${(s.timers || []).length ? `<div class="timers">${s.timers.map((t) =>
        `<button class="timer-chip glass press" data-timer="${t.seconds}" data-label="${esc(t.label || "Step " + (i + 1))}">${I.timer}${esc(secondsLabel(t.seconds))}</button>`).join("")}</div>` : ""}
      </div></li>`).join("")}</ol>`;
}

function detailHTML(r) {
  const busy = r.status === "queued" || r.status === "processing";
  const servings = r.servings || null;
  const wanted = store.get("servings." + r.id, servings);
  const factor = servings && wanted ? wanted / servings : 1;
  const eyebrow = r.tags && r.tags.length
    ? r.tags.slice(0, 3).map((t) => `<button class="eyebrow-tag" data-tag="${esc(t)}">${esc(tagLabel(t))}</button>`).join('<span class="dot">·</span>')
    : esc(PLATFORM[(r.source || {}).platform] || "");
  const errorPanel = r.status === "error" ? `<div class="error-panel"><h3>Couldn't read this recipe</h3><p>${esc(r.error || "Unknown error")}</p>
      <div class="row"><button class="btn plain press" data-act="retry">${I.retry}Try again</button>
      <button class="btn danger press" data-act="delete">${I.trash}Delete</button></div>
      ${r.original_text ? `<div class="notes-box" style="white-space:pre-wrap;margin-top:16px"><b>Your original note</b>${esc(r.original_text)}</div>` : ""}</div>` : "";
  const busyPanel = busy ? `<div class="error-panel"><h3 style="display:flex;gap:10px;align-items:center"><span class="spinner"></span>${esc(r.progress || "Waiting in line")}</h3>
      <p>This usually takes 20–60 seconds. You can leave this page.</p></div>` : "";
  const cookOn = store.get("wake", true);
  return `<div class="detail page">
    <div class="nav-bar glass dense" id="navbar"><div class="t">${esc(r.title || "")}</div></div>
    <div class="nav-float">
      <div><button class="icon-btn glass press" data-act="back" aria-label="Back">${I.back}</button></div>
      <div><button class="icon-btn glass press ${r.favorite ? "accent" : ""}" data-act="fav" aria-label="Favourite">${r.favorite ? I.heartFill : I.heart}</button>
      <button class="icon-btn glass press" data-act="more" aria-label="More">${I.more}</button></div>
    </div>
    ${heroHTML(r)}
    <div class="head">
      ${eyebrow ? `<div class="eyebrow">${eyebrow}</div>` : ""}
      <h1 class="title" id="title">${esc(r.title || (busy ? "Saving recipe…" : "Untitled"))}</h1>
      ${r.description ? `<div class="desc">${esc(r.description)}</div>` : ""}
      ${factsHTML(r)}
      ${sourceLink(r)}
    </div>
    ${errorPanel}${busyPanel}
    ${(r.ingredient_groups || []).length ? `<section class="block">
      <div class="block-head"><h2>Ingredients</h2>
        ${servings ? `<div class="stepper glass"><button class="press" data-serv="-1" aria-label="Fewer servings">${I.minus}</button>
          <span id="serv">${wanted} serving${wanted === 1 ? "" : "s"}</span>
          <button class="press" data-serv="1" aria-label="More servings">${I.plus}</button></div>` : ""}
      </div>
      <div id="ings">${ingredientsHTML(r, factor)}</div>
      <button class="cook-toggle glass press" data-act="shop">${I.cart}<span>Add to shopping list</span></button>
    </section>` : ""}
    ${(r.steps || []).length ? `<section class="block">
      <div class="block-head"><h2>Steps</h2></div>
      ${stepsHTML(r)}
      <button class="cook-toggle glass press ${cookOn ? "on" : ""}" data-act="wake">${I.sun}<span>${cookOn ? "Screen stays on while cooking" : "Keep screen on while cooking"}</span></button>
      ${r.source_notes ? `<div class="notes-box"><b>Tips</b>${esc(r.source_notes)}</div>` : ""}
      ${r.tags && r.tags.length ? `<div class="tags">${r.tags.map((t) => `<button class="tag press" data-tag="${esc(t)}">#${esc(tagLabel(t))}</button>`).join("")}</div>` : ""}
    </section>` : ""}
  </div>`;
}

function bindDetail(r) {
  $('[data-act="back"]').onclick = () => { if (history.length > 1 && state.recipes) history.back(); else location.hash = "#/"; };
  $('[data-act="more"]').onclick = () => openMoreSheet(r);
  $('[data-act="fav"]').onclick = async (e) => {
    r.favorite = !r.favorite;
    e.currentTarget.innerHTML = r.favorite ? I.heartFill : I.heart;
    e.currentTarget.classList.toggle("accent", r.favorite);
    const item = (state.recipes || []).find((x) => x.id === r.id);
    if (item) item.favorite = r.favorite;
    await api("/" + r.id, { method: "PATCH", body: { favorite: r.favorite } }).catch((err) => toast(err.message));
  };
  $('[data-act="retry"]')?.addEventListener("click", () => retry(r));
  $$("[data-tag]").forEach((b) => b.onclick = () => {
    setOnlyFilter(b.dataset.tag);
    state.tab = "all";
    location.hash = "#/";
    window.scrollTo(0, 0);
  });
  $('[data-act="shop"]')?.addEventListener("click", () => openShoppingSheet(r));
  $('[data-act="delete"]')?.addEventListener("click", () => removeRecipe(r));

  // compact nav bar after the title scrolls away
  const navbar = $("#navbar"), title = $("#title");
  const onScroll = () => navbar.classList.toggle("show", title.getBoundingClientRect().bottom < 60);
  window.addEventListener("scroll", onScroll, { passive: true });
  detailCleanup.push(() => window.removeEventListener("scroll", onScroll));

  // ingredients
  const ings = $("#ings");
  if (ings) ings.onclick = (e) => {
    const li = e.target.closest("[data-ing]");
    if (!li) return;
    li.classList.toggle("done");
    const set = new Set(store.get("checked." + r.id, []));
    li.classList.contains("done") ? set.add(li.dataset.ing) : set.delete(li.dataset.ing);
    store.set("checked." + r.id, [...set]);
    navigator.vibrate?.(8);
  };
  $$("[data-serv]").forEach((b) => b.onclick = () => {
    const cur = store.get("servings." + r.id, r.servings);
    const next = Math.max(1, Math.min(99, cur + Number(b.dataset.serv)));
    store.set("servings." + r.id, next);
    $("#serv").textContent = `${next} serving${next === 1 ? "" : "s"}`;
    $("#ings").innerHTML = ingredientsHTML(r, next / r.servings);
  });

  // steps + timers
  $$(".step").forEach((li) => li.onclick = (e) => {
    if (e.target.closest(".timer-chip")) return;
    li.classList.toggle("done");
    const set = new Set(store.get("steps." + r.id, []));
    const i = Number(li.dataset.step);
    li.classList.contains("done") ? set.add(i) : set.delete(i);
    store.set("steps." + r.id, [...set]);
  });
  $$(".timer-chip").forEach((b) => b.onclick = () => Timers.start(Number(b.dataset.timer), b.dataset.label, r));

  const wake = $('[data-act="wake"]');
  if (wake) wake.onclick = () => {
    const on = !store.get("wake", true);
    store.set("wake", on);
    wake.classList.toggle("on", on);
    wake.querySelector("span").textContent = on ? "Screen stays on while cooking" : "Keep screen on while cooking";
    on ? WakeLock.on() : WakeLock.off();
  };
  if (store.get("wake", true) && (r.steps || []).length) WakeLock.on();
  detailCleanup.push(() => WakeLock.off());

  if (r.video_url) setupVideo();
}

// ------------------------------------------------------------------ video
function setupVideo() {
  const hero = $("#hero"), vid = $("#vid"), mute = $("#mute"), fill = $("#fill"), scrub = $("#scrub");
  const full = $("#full"), hint = $("#pullhint"), vtime = $("#vtime");
  const total = vtime ? vtime.textContent : "";

  const sync = () => hero.classList.toggle("playing", !vid.paused && !vid.ended);
  const play = () => { hero.classList.add("started"); vid.play().catch(() => {}); };
  // No play button: tap the video (or its poster) to play / pause.
  hero.addEventListener("click", (e) => {
    if (e.target.closest(".video-ui, .pull-hint")) return;
    vid.paused ? play() : vid.pause();
  });
  vid.onplay = sync; vid.onpause = sync;
  vid.onended = () => { vid.currentTime = 0; sync(); };
  vid.ontimeupdate = () => {
    if (!vid.duration) return;
    fill.style.width = (vid.currentTime / vid.duration) * 100 + "%";
    if (vtime) vtime.textContent = clock(Math.max(0, vid.duration - vid.currentTime));
  };
  mute.onclick = (e) => { e.stopPropagation(); vid.muted = !vid.muted; mute.innerHTML = vid.muted ? I.soundOff : I.soundOn; };

  const seek = (clientX) => {
    const rect = scrub.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    if (vid.duration) { vid.currentTime = p * vid.duration; fill.style.width = p * 100 + "%"; }
  };
  scrub.onpointerdown = (e) => { e.stopPropagation(); scrub.setPointerCapture(e.pointerId); scrub.classList.add("active"); seek(e.clientX); };
  scrub.onpointermove = (e) => { if (scrub.classList.contains("active")) seek(e.clientX); };
  scrub.onpointerup = () => scrub.classList.remove("active");
  scrub.onclick = (e) => e.stopPropagation();

  // Pause when scrolled away; never auto-resume (the user decides).
  const io = new IntersectionObserver(([entry]) => {
    if (entry.intersectionRatio < 0.35 && !vid.paused) vid.pause();
  }, { threshold: [0, 0.35, 1] });
  io.observe(hero);
  const onHide = () => { if (document.hidden && !vid.paused) vid.pause(); };
  document.addEventListener("visibilitychange", onHide);
  detailCleanup.push(() => { io.disconnect(); document.removeEventListener("visibilitychange", onHide); vid.pause(); vid.removeAttribute("src"); vid.load(); });
  void total;

  // ---- full screen: the video grows to fill the screen inside the page, the
  // recipe stays below it (title over the bottom), so you simply scroll on.
  // Everything animates the hero's height, also while pulling, so there is
  // never a switch between two kinds of animation.
  let base = hero.offsetHeight;
  const isTall = () => hero.classList.contains("tall");
  const animateTo = (px, then) => {
    hero.classList.remove("pulling");
    hero.style.height = hero.offsetHeight + "px";
    void hero.offsetHeight;
    hero.style.height = px + "px";
    let done = false;
    const fin = () => { if (!done) { done = true; then?.(); } };
    hero.addEventListener("transitionend", fin, { once: true });
    setTimeout(fin, 550);
  };
  const expand = () => {
    if (isTall()) return;
    if (window.scrollY > 0) window.scrollTo({ top: 0 });
    hero.classList.add("tall");
    animateTo(window.innerHeight);
    vid.muted = false; mute.innerHTML = I.soundOn;
    play();
    full.innerHTML = I.collapse;
    full.setAttribute("aria-label", "Exit full screen");
  };
  const collapse = () => {
    if (!isTall()) return;
    hero.classList.remove("tall");
    full.innerHTML = I.expand;
    full.setAttribute("aria-label", "Full screen");
    animateTo(base, () => { if (!isTall()) hero.style.height = ""; });
  };
  // Fold back silently once the full screen video has been scrolled away and
  // scrolling has come to rest (changing it mid-scroll makes iOS jump).
  let touching = false, idle = 0;
  const foldIfAway = () => {
    if (touching) { idle = setTimeout(foldIfAway, 250); return; }
    if (!isTall() || hero.getBoundingClientRect().bottom > 0) return;
    // Keep whatever is on screen exactly where it is: measure an element below
    // the video before and after, and scroll by the difference (works whether
    // or not the browser does its own scroll anchoring).
    const anchor = hero.nextElementSibling || hero.parentElement;
    const before = anchor.getBoundingClientRect().top;
    hero.style.transition = "none";
    hero.classList.remove("tall");
    hero.style.height = "";
    full.innerHTML = I.expand;
    full.setAttribute("aria-label", "Full screen");
    const shift = anchor.getBoundingClientRect().top - before;
    if (shift) window.scrollBy(0, shift);
    void hero.offsetHeight;
    hero.style.transition = "";
  };
  const onScroll = () => { clearTimeout(idle); if (isTall()) idle = setTimeout(foldIfAway, 300); };
  window.addEventListener("scroll", onScroll, { passive: true });
  const onResize = () => { if (isTall()) hero.style.height = window.innerHeight + "px"; else if (!hero.style.height) base = hero.offsetHeight; };
  window.addEventListener("resize", onResize);
  detailCleanup.push(() => { clearTimeout(idle); window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onResize); });
  full.onclick = (e) => { e.stopPropagation(); isTall() ? collapse() : expand(); };

  // Pull down at the very top: the video stretches with your finger; let go
  // far enough and it continues to full screen (or back when already full).
  const PULL = 90;
  let startY = null, pull = 0, startH = 0;
  const eased = (d) => PULL * 1.6 * (1 - Math.exp(-d / (PULL * 1.6)));
  const hideHint = () => { hint.style.opacity = 0; hint.classList.remove("ready"); delete hint.dataset.buzzed; };
  const onStart = (e) => {
    touching = true;
    startY = e.touches.length === 1 && !ScrollLock.on && window.scrollY <= 0 && !e.target.closest(".scrub, .sheet, .dev-panel") ? e.touches[0].clientY : null;
    pull = 0;
  };
  const onMove = (e) => {
    if (startY == null || Swipe.horizontal) return;
    const dy = e.touches[0].clientY - startY;
    if (dy <= 0 || window.scrollY > 0) {
      if (pull) { pull = 0; hideHint(); animateTo(startH, () => { if (!isTall()) hero.style.height = ""; }); }
      return;
    }
    e.preventDefault();
    if (!pull) startH = hero.offsetHeight;
    pull = dy;
    const p = eased(dy);
    hero.classList.add("pulling");
    hero.style.height = startH + p + "px";
    hint.querySelector("span").textContent = isTall() ? "Release to shrink" : "Release for full screen";
    hint.style.opacity = Math.min(1, p / PULL);
    hint.classList.toggle("ready", p >= PULL * 0.95);
    if (p >= PULL * 0.95 && !hint.dataset.buzzed) { hint.dataset.buzzed = 1; navigator.vibrate?.(10); }
  };
  const onEnd = (e) => {
    if (!e.touches || e.touches.length === 0) touching = false;
    if (startY == null) return;
    const wasPulling = pull > 0;
    const go = eased(pull) >= PULL * 0.95;
    hideHint();
    startY = null; pull = 0;
    if (!wasPulling) return;
    if (go) isTall() ? collapse() : expand();
    else animateTo(isTall() ? window.innerHeight : startH, () => { if (!isTall()) hero.style.height = ""; });
  };
  document.addEventListener("touchstart", onStart, { passive: true });
  document.addEventListener("touchmove", onMove, { passive: false });
  document.addEventListener("touchend", onEnd);
  document.addEventListener("touchcancel", onEnd);
  detailCleanup.push(() => {
    document.removeEventListener("touchstart", onStart);
    document.removeEventListener("touchmove", onMove);
    document.removeEventListener("touchend", onEnd);
    document.removeEventListener("touchcancel", onEnd);
  });
}

// ------------------------------------------------------------------ glass light
// Gently slides the specular highlight of visible .glass elements as they move
// over the screen (scrolling, chip row swiping): light seems to come from the
// top of the display. Kept subtle on purpose.
const GlassLight = (() => {
  let raf = 0;
  const run = () => {
    raf = 0;
    const vw = window.innerWidth, vh = window.innerHeight;
    const todo = [];
    for (const el of document.querySelectorAll(".glass")) {
      const r = el.getBoundingClientRect();
      if (!r.width || r.bottom < -20 || r.top > vh + 20) continue;
      todo.push([el, r]);
    }
    for (const [el, r] of todo) {
      const x = Math.min(1, Math.max(0, (r.left + r.width / 2) / vw));
      const y = Math.min(1, Math.max(0, (r.top + r.height / 2) / vh));
      el.style.setProperty("--gx", (12 + x * 26).toFixed(1) + "%");
      el.style.setProperty("--gy", (-16 + y * 14).toFixed(1) + "%");
    }
  };
  const update = () => { if (!raf) raf = requestAnimationFrame(run); };
  document.addEventListener("scroll", update, { passive: true, capture: true });
  window.addEventListener("resize", update);
  new MutationObserver(update).observe(document.body, { childList: true, subtree: true });
  return { update };
})();

// ------------------------------------------------------------------ timers
const Timers = {
  list: store.get("timers", []).filter((t) => t.end > Date.now() - 10 * 60_000),
  tick: null,
  start(seconds, label, r) {
    const mode = store.get("timerMode", "clock");
    const t = { id: Date.now(), end: Date.now() + seconds * 1000, label, seconds, recipe: r?.id };
    this.list.push(t);
    this.save();
    this.render();
    if (mode === "clock") {
      const name = store.get("timerShortcut", "Recipe Timer");
      const url = `shortcuts://run-shortcut?name=${encodeURIComponent(name)}&input=text&text=${encodeURIComponent(String(seconds))}`;
      location.href = url;
    } else {
      toast(`Timer set: ${secondsLabel(seconds)}`);
    }
  },
  save() { store.set("timers", this.list); },
  remove(id) { this.list = this.list.filter((t) => t.id !== id); this.save(); this.render(); },
  render() {
    let dock = $("#dock");
    if (!this.list.length) { dock?.remove(); clearInterval(this.tick); this.tick = null; return; }
    if (!dock) { dock = document.createElement("div"); dock.id = "dock"; dock.className = "timer-dock"; document.body.appendChild(dock); }
    const now = Date.now();
    dock.innerHTML = this.list.map((t) => {
      const left = (t.end - now) / 1000;
      const p = Math.max(0, Math.min(1, left / t.seconds));
      const ring = `<svg class="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="4"/>
        <circle cx="18" cy="18" r="15" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"
        stroke-dasharray="${(94.2 * p).toFixed(1)} 94.2" transform="rotate(-90 18 18)"/></svg>`;
      return `<button class="dock-pill glass dense press ${left <= 0 ? "done" : ""}" data-tid="${t.id}">${ring}<span>${left <= 0 ? "Done" : clock(left)}</span><small>${esc(t.label || "")}</small></button>`;
    }).join("");
    $$("[data-tid]", dock).forEach((b) => b.onclick = () => {
      const t = this.list.find((x) => x.id === Number(b.dataset.tid));
      if (t && t.end > Date.now() && !confirmTimerStop()) return;
      this.remove(Number(b.dataset.tid));
    });
    if (!this.tick) this.tick = setInterval(() => this.render(), 1000);
  },
};
function confirmTimerStop() { return window.confirm("Remove this timer from the list? (The Clock timer keeps running.)"); }

const WakeLock = {
  lock: null,
  async on() {
    try { if ("wakeLock" in navigator && !this.lock) { this.lock = await navigator.wakeLock.request("screen"); this.lock.addEventListener("release", () => { this.lock = null; }); } }
    catch { /* not allowed right now */ }
  },
  off() { this.lock?.release().catch(() => {}); this.lock = null; },
};
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && route().name === "detail" && store.get("wake", true)) WakeLock.on();
});

// ------------------------------------------------------------------ sheets
function openSheet(html, onMount) {
  const root = $("#sheet-root");
  root.innerHTML = `<div class="sheet-backdrop"></div><div class="sheet glass dense" role="dialog"><div class="grabber"></div>${html}</div>`;
  const bd = $(".sheet-backdrop", root), sh = $(".sheet", root);
  ScrollLock.lock();
  requestAnimationFrame(() => { bd.classList.add("open"); sh.classList.add("open"); });
  const close = () => {
    ScrollLock.unlock();
    bd.classList.remove("open"); sh.classList.remove("open");
    setTimeout(() => { if (root.contains(sh)) root.innerHTML = ""; }, 380);
  };
  bd.onclick = close;
  // drag down to dismiss
  let y0 = null;
  sh.addEventListener("touchstart", (e) => { if (sh.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener("touchmove", (e) => { if (y0 == null) return; const dy = e.touches[0].clientY - y0; if (dy > 0) { sh.style.transition = "none"; sh.style.transform = `translateY(${dy}px)`; } }, { passive: true });
  sh.addEventListener("touchend", (e) => {
    if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null;
    sh.style.transition = ""; sh.style.transform = "";
    if (dy > 110) close();
  });
  onMount?.(sh, close);
  return close;
}

function openAddSheet() {
  openSheet(`<h3>Add Recipe</h3>
    <p class="hint">Paste a link to a TikTok, Instagram post or recipe website. Tip: the Save Recipe shortcut in the share sheet does this in one tap.</p>
    <textarea class="field" id="add-url" rows="2" placeholder="https://…" autocapitalize="off" autocorrect="off" spellcheck="false"></textarea>
    <div class="actions">
      <button class="btn plain press" id="add-paste">${I.paste}Paste</button>
      <label class="btn plain press">${I.photo}Photo/PDF<input type="file" id="add-file" accept="image/*,application/pdf" hidden></label>
    </div>
    <div class="actions"><button class="btn primary press" id="add-go">Save Recipe</button></div>`,
  (sh, close) => {
    const field = $("#add-url", sh);
    setTimeout(() => field.focus(), 350);
    $("#add-paste", sh).onclick = async () => {
      try { field.value = (await navigator.clipboard.readText()).trim(); } catch { toast("Long-press the field to paste"); }
    };
    const submit = async (body) => {
      const go = $("#add-go", sh); go.disabled = true; go.textContent = "Saving…";
      try {
        const res = await api("", { method: "POST", body });
        close();
        toast(res.created ? "Saving recipe…" : "Already in your recipes");
        await loadList();
        if (route().name === "library") renderLibrary(false); else location.hash = "#/";
      } catch (err) { toast(err.message); go.disabled = false; go.textContent = "Save Recipe"; }
    };
    $("#add-go", sh).onclick = () => {
      const v = field.value.trim();
      if (!v) return toast("Paste a link first");
      submit(/^https?:\/\//i.test(v) ? { url: v } : { text: v });
    };
    $("#add-file", sh).onchange = (e) => {
      const f = e.target.files[0]; if (!f) return;
      const fd = new FormData(); fd.append("file", f, f.name); submit(fd);
    };
  });
}

function openMoreSheet(r) {
  const url = (r.source || {}).url_canonical || (r.source || {}).url;
  openSheet(`<div class="menu">
      ${url ? `<button data-m="open">${I.link}Open original</button>` : ""}
      ${navigator.share ? `<button data-m="share">${I.share}Share link</button>` : ""}
      <button data-m="reset">${I.check}Uncheck ingredients and steps</button>
      <button data-m="retry">${I.retry}Read recipe again</button>
      ${state.admin ? `<button data-m="dev">${I.code}${Dev.el ? "Hide developer view" : "Developer"}</button>` : ""}
      <button data-m="delete" class="danger">${I.trash}Delete recipe</button>
    </div>`,
  (sh, close) => {
    $$("[data-m]", sh).forEach((b) => b.onclick = async () => {
      const m = b.dataset.m; close();
      if (m === "open") window.open(url, "_blank");
      if (m === "share") navigator.share({ title: r.title, url }).catch(() => {});
      if (m === "reset") { store.set("checked." + r.id, []); store.set("steps." + r.id, []); renderDetail(r.id); }
      if (m === "retry") retry(r);
      if (m === "dev") Dev.toggle(r);
      if (m === "delete") removeRecipe(r);
    });
  });
}

async function retry(r) {
  await api("/" + r.id + "/retry", { method: "POST" }).catch((err) => toast(err.message));
  toast("Reading recipe again…");
  renderDetail(r.id);
}

async function removeRecipe(r) {
  if (!window.confirm(`Delete “${r.title || "this recipe"}”?`)) return;
  await api("/" + r.id, { method: "DELETE" }).catch((err) => toast(err.message));
  state.recipes = (state.recipes || []).filter((x) => x.id !== r.id);
  location.hash = "#/";
}

async function openSettingsSheet() {
  let info = {};
  try { info = await api("/settings"); } catch (err) { toast(err.message); }
  const mode = store.get("timerMode", "clock");
  const shortcut = store.get("timerShortcut", "Recipe Timer");
  const opts = info.options || {}, choices = info.choices || {};
  const select = (key, label, emptyLabel) => {
    const list = [...(choices[key] || [])];
    if (opts[key] && !list.some((c) => c.id === opts[key])) list.push({ id: opts[key], name: opts[key] });
    return `<label class="opt"><span>${label}</span><select class="field" data-opt="${key}">
      ${emptyLabel ? `<option value="">${emptyLabel}</option>` : ""}
      ${list.map((c) => `<option value="${esc(c.id)}" ${c.id === opts[key] ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
    </select></label>`;
  };
  openSheet(`<h3>Recipes</h3>
    <div class="sub-h">Timers</div>
    <div class="menu">
      <button data-mode="clock">${mode === "clock" ? I.check : '<svg viewBox="0 0 24 24"></svg>'}Start in the Clock app (via Shortcuts)</button>
      <button data-mode="app">${mode === "app" ? I.check : '<svg viewBox="0 0 24 24"></svg>'}Only show in this app</button>
    </div>
    <input class="field" id="sc-name" value="${esc(shortcut)}" placeholder="Shortcut name" style="margin-top:8px">
    ${info.is_admin && info.options ? `<div class="sub-h">Reading recipes</div>
      ${select("ai_task_entity", "AI Task", "Automatic")}
      ${select("language", "Recipe language")}
      ${select("extraction_mode", "Extraction")}
      <label class="opt row"><span>Listen to videos<small>Speech-to-text when the caption is short</small></span>
        <button class="switch" role="switch" data-opt-toggle="transcribe" aria-checked="${!!opts.transcribe}" aria-label="Listen to videos"></button></label>
      ${select("stt_entity", "Speech-to-text", "Automatic")}
      <div class="sub-h">Shopping and notifications</div>
      ${select("todo_entity", "To-do list for shopping", "Automatic")}
      ${select("notify_service", "Notify when a recipe is saved", "No notification")}
      <label class="opt row"><span>Weekly supermarket offers<small>Fetched from Albert Heijn, Jumbo, Lidl and Dirk for the Bonus playlist</small></span>
        <button class="switch" role="switch" data-opt-toggle="auto_discounts" aria-checked="${opts.auto_discounts !== false}" aria-label="Weekly supermarket offers"></button></label>` : ""}
    ${info.is_admin ? `<div class="sub-h">Instagram</div>
      <p class="hint" style="text-align:left">Instagram blocks some downloads without a login. Paste the <b>sessionid</b> cookie (or a cookies.txt export) of an Instagram account here. A second account is safest. ${info.instagram_cookies ? "<b>Cookies are set.</b>" : ""}</p>
      <textarea class="field" id="ig" rows="2" placeholder="${info.instagram_cookies ? "Paste new cookies to replace, or leave empty and save to remove" : "sessionid=…"}"></textarea>
      <div class="actions"><button class="btn plain press" id="ig-save">Save cookies</button></div>` : ""}
    <div class="sub-h">About</div>
    <div class="kv"><span>Recipes</span><span>${info.count ?? "–"}</span></div>
    ${info.errors ? `<div class="kv"><span>Couldn't read</span><span>${info.errors}</span></div>` : ""}
    <div class="kv"><span>Version</span><span>${esc(info.version || "")}</span></div>
    <div class="kv"><span>yt-dlp</span><span>${esc(info.yt_dlp || "not installed")}</span></div>
    ${info.webhook_path ? `<div class="kv"><span>Share webhook</span><span>${esc(location.origin + info.webhook_path)}</span></div>
      <div class="actions"><button class="btn plain press" id="copy-hook">Copy webhook URL</button></div>` : ""}
    <div class="actions"><button class="btn plain press" id="logout">Sign out</button></div>`,
  (sh) => {
    $$("[data-mode]", sh).forEach((b) => b.onclick = () => { store.set("timerMode", b.dataset.mode); openSettingsSheet(); });
    $("#sc-name", sh).onchange = (e) => store.set("timerShortcut", e.target.value.trim() || "Recipe Timer");
    const saveOption = async (key, value, undo) => {
      try { await api("/settings", { method: "POST", body: { options: { [key]: value } } }); toast("Saved"); }
      catch (err) { undo(); toast(err.message, 4000); }
    };
    $$("[data-opt]", sh).forEach((el) => {
      let last = el.value;
      el.onchange = () => { const prev = last; last = el.value; saveOption(el.dataset.opt, el.value, () => { el.value = last = prev; }); };
    });
    $$("[data-opt-toggle]", sh).forEach((el) => el.onclick = () => {
      const on = el.getAttribute("aria-checked") !== "true";
      el.setAttribute("aria-checked", on);
      saveOption(el.dataset.optToggle, on, () => el.setAttribute("aria-checked", !on));
    });
    $("#ig-save", sh)?.addEventListener("click", async () => {
      try { const res = await api("/settings", { method: "POST", body: { instagram_cookies: $("#ig", sh).value } }); toast(res.instagram_cookies ? "Cookies saved" : "Cookies removed"); }
      catch (err) { toast(err.message, 4000); }
    });
    $("#copy-hook", sh)?.addEventListener("click", () => navigator.clipboard.writeText(location.origin + info.webhook_path).then(() => toast("Copied")));
    $("#logout", sh).onclick = () => { Auth.save(null); location.reload(); };
  });
}

// ------------------------------------------------------------------ developer view
// What the pipeline saw and did for a recipe, plus "re-run AI only" experiments.
// A sidebar next to the recipe on wide screens, full screen on the phone.
const Dev = {
  el: null,
  recipe: null,
  wide: () => window.matchMedia("(min-width: 1000px)").matches,
  toggle(r) {
    if (this.el) { store.set("dev", false); this.close(); }
    else { store.set("dev", true); this.open(r); }
  },
  open(r) {
    this.recipe = r;
    if (!this.el) {
      this.el = document.createElement("aside");
      this.el.className = "dev-panel";
      document.body.appendChild(this.el);
      document.body.classList.add("dev-open");
      if (!this.wide()) ScrollLock.lock();
    }
    this.load();
  },
  close() {
    if (!this.el) return;
    this.el.remove();
    this.el = null;
    document.body.classList.remove("dev-open");
    ScrollLock.unlock();
  },
  block(title, text, open = false) {
    if (text == null || text === "") return "";
    text = String(text);
    return `<details ${open ? "open" : ""}><summary>${title}<small>${text.length.toLocaleString("en")} chars</small></summary><pre>${esc(text)}</pre></details>`;
  },
  async load() {
    const r = this.recipe, el = this.el;
    const head = `<div class="dev-head"><h3>Developer</h3><button class="icon-btn glass press" data-dev="close" aria-label="Close developer view">${I.close}</button></div>`;
    const bindClose = () => { $('[data-dev="close"]', el).onclick = () => { store.set("dev", false); this.close(); }; };
    if (!el.firstChild) { el.innerHTML = head + `<p class="hint">Loading…</p>`; bindClose(); }
    let res;
    try { res = await api("/" + r.id + "/debug"); }
    catch (err) { if (this.el === el) { el.innerHTML = head + `<p class="hint">${esc(err.message)}</p>`; bindClose(); } return; }
    if (this.el !== el || this.recipe !== r) return;
    const d = res.debug || {}, ai = d.ai || {};
    const kv = (k, v) => (v == null || v === "" ? "" : `<div class="kv"><span>${k}</span><span>${esc(v)}</span></div>`);
    const steps = [["download", "Download video"], ["transcribe", "Speech-to-text"], ["web", "Fetch web page"], ["collect", "All material"], ["ai", "AI"]];
    const timings = steps.filter(([k]) => d.timings && d.timings[k] != null).map(([k, label]) => kv(label, d.timings[k].toFixed(1) + " s")).join("");
    const errors = [...(d.errors || []), ...(d.error && !(d.errors || []).some((e) => e.includes(d.error)) ? [d.error] : [])];
    el.innerHTML = head + `
      ${kv("Status", r.status)}${kv("Platform", d.platform || (r.source || {}).platform)}${kv("Chosen link", d.url || (r.source || {}).url)}
      ${kv("AI Task", ai.entity)}${kv("Extraction", d.mode ? (d.mode === "lean" ? "Lean" : "Classic") + (ai.shortcut ? " · JSON-LD shortcut" : "") : "")}${kv("Processed", d.finished ? new Date(d.finished).toLocaleString() : "")}${kv("Media folder", res.folder)}
      ${!res.available ? `<p class="hint" style="margin-top:18px">No debug data for this recipe yet. It is recorded the next time the recipe is read.</p>
        <div class="actions"><button class="btn plain press" data-dev="retry">${I.retry}Read recipe again</button></div>` : `
      ${timings ? `<div class="sub-h">Timings</div>${timings}` : ""}
      ${(d.notes || []).length ? `<div class="sub-h">Pipeline notes</div>${d.notes.map((n) => `<div class="dev-note">${esc(n)}</div>`).join("")}` : ""}
      ${errors.length ? `<div class="sub-h">Errors</div>${errors.map((n) => `<div class="dev-note err">${esc(n)}</div>`).join("")}` : ""}
      <div class="sub-h">Material</div>
      ${this.block("Shared input", d.shared)}${this.block("Saved note / text", d.input_text)}
      ${this.block("Caption", d.caption)}${this.block("Transcript", d.transcript)}${this.block("Web page", d.web_text)}
      ${(d.attachments || []).length ? kv("Attachments", d.attachments.join(", ")) : ""}
      <div class="sub-h">AI</div>
      ${this.block("Prepared material (lean)", (ai.prepared || d.prepared || []).join("\n\n"))}
      ${this.block("Prompt sent", ai.prompt)}${this.block("Raw output", ai.output)}${this.block("First output (not valid JSON)", ai.unparseable_output)}
      <div class="sub-h">Experiment</div>
      <p class="hint" style="text-align:left">Runs only the AI step again on the material above. Nothing is saved until you confirm.</p>
      <label class="opt"><span>Extraction</span><select class="field" id="dev-mode">
        <option value="">As set (${res.mode === "lean" ? "Lean" : "Classic"})</option>
        <option value="classic">Classic</option><option value="lean">Lean</option></select></label>
      <textarea class="field" id="dev-instr" rows="2" placeholder="Extra instruction (optional)"></textarea>
      <details class="dev-edit"><summary>Edit the full prompt</summary><textarea class="field mono" id="dev-prompt" rows="14" spellcheck="false">${esc(ai.prompt || "")}</textarea></details>
      <div class="actions"><button class="btn primary press" id="dev-run">Re-run AI only</button></div>
      <div id="dev-result"></div>`}`;
    bindClose();
    $('[data-dev="retry"]', el)?.addEventListener("click", () => retry(r));
    const run = $("#dev-run", el);
    if (run) run.onclick = async () => {
      const instruction = $("#dev-instr", el).value.trim();
      let prompt = $("#dev-prompt", el).value;
      const mode = $("#dev-mode", el).value;
      const runMode = d.mode || "classic";
      // The edited prompt belongs to the mode of the last run; another mode builds its own.
      const edited = (!mode || mode === runMode) && prompt.trim() !== (ai.prompt || "").trim();
      if (edited && instruction) prompt += "\n\nEXTRA INSTRUCTION:\n" + instruction;
      run.disabled = true; run.textContent = "Asking the AI…";
      const out = $("#dev-result", el);
      try {
        const result = await api("/" + r.id + "/debug/rerun", { method: "POST", body: { ...(edited ? { prompt } : { instruction }), ...(mode ? { mode } : {}) } });
        if (out.isConnected) this.showResult(out, result);
      } catch (err) { if (out.isConnected) out.innerHTML = `<div class="dev-note err">${esc(err.message)}</div>`; }
      run.disabled = false; run.textContent = "Re-run AI only";
    };
  },
  // The parts of a recipe that the AI writes, as [label, html] rows.
  rows(x) {
    const time = [["Prep", x.prep_min], ["Cook", x.cook_min], ["Total", x.total_min]].filter(([, v]) => v).map(([k, v]) => `${k} ${minutesLabel(v)}`).join(" · ");
    return [
      ["Title", esc(x.title || "")],
      ["Description", esc(x.description || "")],
      ["Time", esc(time + (x.estimated ? " (estimated)" : ""))],
      ["Servings", esc([x.servings, x.servings_text].filter(Boolean).join(" · "))],
      ["Tags", esc((x.tags || []).map(tagLabel).join(", "))],
      ["Ingredients", (x.ingredient_groups || []).map((g) => (g.name ? `<b>${esc(g.name)}</b>` : "") +
        g.items.map((it) => `<div>${esc(ingredientText(it, 1))}${it.original ? ` <small>(${esc(it.original)})</small>` : ""}</div>`).join("")).join("")],
      ["Steps", (x.steps || []).map((st, i) => `<div>${i + 1}. ${esc(st.text)}${(st.timers || []).map((t) => ` <small>[${esc(secondsLabel(t.seconds))}]</small>`).join("")}</div>`).join("")],
      ["Tips", esc(x.source_notes || "")],
    ];
  },
  showResult(out, result) {
    const r = this.recipe;
    const raw = this.block("Raw output of this run", result.output);
    const secs = Number(result.seconds || 0).toFixed(1);
    if (!result.fields) {
      out.innerHTML = `<div class="dev-note err">The AI found no recipe in the material (${secs} s).</div>${raw}`;
      return;
    }
    const cur = this.rows(r), next = this.rows(result.fields);
    const changed = cur.filter((row, i) => row[1] !== next[i][1]).length;
    out.innerHTML = `<div class="sub-h">Result · ${result.mode === "lean" ? "Lean" : "Classic"}${result.shortcut ? " (JSON-LD)" : ""} · ${secs} s · ${changed ? `${changed} part${changed === 1 ? "" : "s"} changed` : "no changes"}</div>
      <div class="cmp cols"><div>Current</div><div>New</div></div>
      ${cur.map(([label, html], i) => (html || next[i][1]) ? `<div class="cmp-k ${html !== next[i][1] ? "diff" : ""}">${label}${html !== next[i][1] ? " · changed" : ""}</div>
        <div class="cmp"><div>${html || "–"}</div><div>${next[i][1] || "–"}</div></div>` : "").join("")}
      ${raw}
      <div class="actions"><button class="btn plain press" id="dev-discard">Discard</button><button class="btn primary press" id="dev-save">Save new version</button></div>`;
    $("#dev-discard", out).onclick = () => { out.innerHTML = ""; };
    $("#dev-save", out).onclick = async () => {
      try {
        await api("/" + r.id + "/debug/apply", { method: "POST" });
        toast("Saved");
        loadList().catch(() => {});
        renderDetail(r.id);
      } catch (err) { toast(err.message, 4000); }
    };
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  },
};

// ------------------------------------------------------------------ boot
async function boot() {
  try {
    await Auth.handleCallback();
  } catch (err) {
    $("#app").innerHTML = errorSplash(err);
    return;
  }
  if (!Auth.tokens) { Auth.login(); return; }
  window.addEventListener("hashchange", render);
  Timers.render();
  loadAdmin();
  await render();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/recipes/sw.js", { scope: "/recipes/" }).catch(() => {});
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && route().name === "library") renderLibrary(true);
  });
}

boot();
