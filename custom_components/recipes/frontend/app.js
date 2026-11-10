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
  return `<div class="gen-art ${big ? "big" : ""}" style="${style}">${esc(title || "")}</div>`;
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
  filter: store.get("filter", "All"),
  tab: "all",
  search: "",
  searching: false,
  current: null,
};
let pollTimer = null;

async function loadList() {
  const data = await api("");
  state.recipes = data.recipes;
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
  const r = route();
  if (r.name === "detail") return renderDetail(r.id);
  return renderLibrary(true);
}

// ------------------------------------------------------------------ library
function visibleRecipes() {
  let list = state.recipes || [];
  if (state.tab === "fav") list = list.filter((r) => r.favorite);
  if (state.filter === "Video") list = list.filter((r) => r.has_video);
  else if (state.filter !== "All") list = list.filter((r) => (r.tags || []).includes(state.filter));
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
  const counts = {};
  for (const r of state.recipes || []) for (const t of r.tags || []) counts[t] = (counts[t] || 0) + 1;
  const tags = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  const hasVideo = (state.recipes || []).some((r) => r.has_video);
  const all = ["All", ...(hasVideo ? ["Video"] : []), ...tags];
  if (!all.includes(state.filter)) state.filter = "All";
  return all.map((t) => `<button class="chip glass press" data-chip="${esc(t)}" aria-pressed="${t === state.filter}">${esc(t)}</button>`).join("");
}

async function renderLibrary(fetch_ = true) {
  const app = $("#app");
  if (fetch_ || !state.recipes) {
    if (!state.recipes) app.innerHTML = `<div class="splash"><div><img src="/recipes/static/icons/icon-180.png" alt=""><p>Loading recipes…</p></div></div>`;
    try { await loadList(); } catch (err) { if (!state.recipes) { app.innerHTML = errorSplash(err); return; } }
  }
  const scroll = window.scrollY;
  const list = visibleRecipes();
  const count = (state.recipes || []).filter((r) => r.status === "ready").length;
  const title = state.tab === "fav" ? "Favourites" : "Recipes";
  app.innerHTML = `<main class="library ${fetch_ ? "page" : ""}">
    <div class="lib-top">
      <button class="icon-btn glass press" data-act="settings" aria-label="Settings">${I.more}</button>
      <button class="icon-btn glass press accent" data-act="add" aria-label="Add recipe">${I.plus}</button>
    </div>
    <h1 class="large-title">${title}</h1>
    <div class="lib-sub">${count} recipe${count === 1 ? "" : "s"}</div>
    <div class="chips">${chipsHTML()}</div>
    ${list.length ? `<div class="section-head"><h2>${state.search ? "Results" : state.filter === "All" ? "Recently Added" : esc(state.filter)}</h2></div>
      <div class="grid">${list.map(cardHTML).join("")}</div>`
      : emptyHTML()}
  </main>
  ${tabbarHTML()}`;
  if (!fetch_) window.scrollTo(0, scroll);
  bindLibrary();
}

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

function bindLibrary() {
  $$("[data-chip]").forEach((b) => b.onclick = () => { state.filter = b.dataset.chip; store.set("filter", state.filter); renderLibrary(false); });
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
function cleanupDetail() { detailCleanup.forEach((f) => f()); detailCleanup = []; }

async function renderDetail(id) {
  const app = $("#app");
  const cached = (state.recipes || []).find((r) => r.id === id);
  if (cached && !app.querySelector(".detail")) {
    app.innerHTML = `<div class="detail page"><div class="hero">${cached.image_url ? `<img class="poster" src="${esc(cached.image_url)}" alt="">` : genArt(cached.title, true)}<div class="fade"></div></div>
      <div class="head"><h1 class="title">${esc(cached.title || "")}</h1></div></div>`;
  }
  let r;
  try { r = await api("/" + id); }
  catch (err) { app.innerHTML = errorSplash(err); return; }
  if (route().id !== id) return;
  state.current = r;
  window.scrollTo(0, 0);
  app.innerHTML = detailHTML(r);
  bindDetail(r);
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
      <button class="play-btn glass press" id="play" aria-label="Play video">${I.play}</button>
      ${dur ? `<div class="duration">${dur}</div>` : ""}
      <div class="video-ui"><div class="scrub" id="scrub"><div class="scrub-track"><div class="scrub-fill" id="fill"></div></div></div>
        <button class="icon-btn glass press" id="mute" aria-label="Mute">${I.soundOn}</button></div>
    </div>`;
  }
  if (poster) return `<div class="hero ${portrait ? "" : "square"}"><img class="poster" src="${esc(poster)}" alt=""><div class="top-fade"></div><div class="fade"></div></div>`;
  return `<div class="hero square no-media">${genArt(r.title, true)}<div class="fade"></div></div>`;
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
      return `<li class="ing ${checked.has(key) ? "done" : ""}" data-ing="${key}">
        <span class="check">${I.check}</span>
        <span class="txt">${qty ? `<span class="qty">${qty}</span> ` : ""}${esc(it.name)}${it.note ? `<span class="note">, ${esc(it.note)}</span>` : ""}${orig}</span></li>`;
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
  const eyebrow = r.tags && r.tags.length ? r.tags.slice(0, 3).join(" · ") : PLATFORM[(r.source || {}).platform] || "";
  const errorPanel = r.status === "error" ? `<div class="error-panel"><h3>Couldn't read this recipe</h3><p>${esc(r.error || "Unknown error")}</p>
      <div class="row"><button class="btn plain press" data-act="retry">${I.retry}Try again</button>
      <button class="btn danger press" data-act="delete">${I.trash}Delete</button></div></div>` : "";
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
      ${eyebrow ? `<div class="eyebrow">${esc(eyebrow)}</div>` : ""}
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
      ${r.tags && r.tags.length ? `<div class="tags">${r.tags.map((t) => `<span class="tag">#${esc(t)}</span>`).join("")}</div>` : ""}
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
  const hero = $("#hero"), vid = $("#vid"), play = $("#play"), mute = $("#mute"), fill = $("#fill"), scrub = $("#scrub");
  let userPaused = true;

  const sync = () => {
    hero.classList.toggle("playing", !vid.paused && !vid.ended);
    play.innerHTML = I.play;
  };
  play.onclick = (e) => { e.stopPropagation(); hero.classList.add("started"); userPaused = false; vid.play().catch(() => {}); };
  vid.onclick = () => {
    if (vid.paused) { userPaused = false; vid.play(); } else { userPaused = true; vid.pause(); }
  };
  vid.onplay = sync; vid.onpause = sync;
  vid.onended = () => { hero.classList.remove("started"); vid.currentTime = 0; sync(); };
  vid.ontimeupdate = () => { if (vid.duration) fill.style.width = (vid.currentTime / vid.duration) * 100 + "%"; };
  mute.onclick = (e) => { e.stopPropagation(); vid.muted = !vid.muted; mute.innerHTML = vid.muted ? I.soundOff : I.soundOn; };

  const seek = (clientX) => {
    const rect = scrub.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    if (vid.duration) { vid.currentTime = p * vid.duration; fill.style.width = p * 100 + "%"; }
  };
  scrub.onpointerdown = (e) => { scrub.setPointerCapture(e.pointerId); scrub.classList.add("active"); seek(e.clientX); };
  scrub.onpointermove = (e) => { if (scrub.classList.contains("active")) seek(e.clientX); };
  scrub.onpointerup = () => scrub.classList.remove("active");

  // Pause when scrolled away; never auto-resume (the user decides).
  const io = new IntersectionObserver(([entry]) => {
    if (entry.intersectionRatio < 0.35 && !vid.paused) vid.pause();
  }, { threshold: [0, 0.35, 1] });
  io.observe(hero);
  const onHide = () => { if (document.hidden && !vid.paused) vid.pause(); };
  document.addEventListener("visibilitychange", onHide);
  detailCleanup.push(() => { io.disconnect(); document.removeEventListener("visibilitychange", onHide); vid.pause(); vid.removeAttribute("src"); vid.load(); });
  void userPaused;
}

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
  requestAnimationFrame(() => { bd.classList.add("open"); sh.classList.add("open"); });
  const close = () => {
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
      <button data-m="delete" class="danger">${I.trash}Delete recipe</button>
    </div>`,
  (sh, close) => {
    $$("[data-m]", sh).forEach((b) => b.onclick = async () => {
      const m = b.dataset.m; close();
      if (m === "open") window.open(url, "_blank");
      if (m === "share") navigator.share({ title: r.title, url }).catch(() => {});
      if (m === "reset") { store.set("checked." + r.id, []); store.set("steps." + r.id, []); renderDetail(r.id); }
      if (m === "retry") retry(r);
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
  openSheet(`<h3>Recipes</h3>
    <div class="sub-h">Timers</div>
    <div class="menu">
      <button data-mode="clock">${mode === "clock" ? I.check : '<svg viewBox="0 0 24 24"></svg>'}Start in the Clock app (via Shortcuts)</button>
      <button data-mode="app">${mode === "app" ? I.check : '<svg viewBox="0 0 24 24"></svg>'}Only show in this app</button>
    </div>
    <input class="field" id="sc-name" value="${esc(shortcut)}" placeholder="Shortcut name" style="margin-top:8px">
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
    $("#ig-save", sh)?.addEventListener("click", async () => {
      try { const res = await api("/settings", { method: "POST", body: { instagram_cookies: $("#ig", sh).value } }); toast(res.instagram_cookies ? "Cookies saved" : "Cookies removed"); }
      catch (err) { toast(err.message, 4000); }
    });
    $("#copy-hook", sh)?.addEventListener("click", () => navigator.clipboard.writeText(location.origin + info.webhook_path).then(() => toast("Copied")));
    $("#logout", sh).onclick = () => { Auth.save(null); location.reload(); };
  });
}

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
  await render();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/recipes/sw.js", { scope: "/recipes/" }).catch(() => {});
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && route().name === "library") renderLibrary(true);
  });
}

boot();
