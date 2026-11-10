// Playwright check of the app on an emulated iPhone 15 Pro: screenshots in dev/shots/
// and assertions for filters, tap-to-play and the full screen video.
// Needs the dev HA with recipes from e2e.py (at least one with a video).
const { chromium, devices } = require('playwright');
const fs = require('fs');
const path = require('path');
const BASE = process.env.HA_URL || `http://127.0.0.1:${process.env.HA_PORT || 8123}`;
const refresh = JSON.parse(fs.readFileSync(path.join(__dirname, '.tokens.json'), 'utf8')).refresh_token;
const out = path.join(__dirname, 'shots');
fs.mkdirSync(out, { recursive: true });
const fails = [];
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails.push(m); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 15 Pro'], colorScheme: 'dark', baseURL: BASE });
  await ctx.addInitScript((r) => localStorage.setItem('recipes.auth', JSON.stringify({ access: 'x', refresh: r, exp: 0 })), refresh);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const shot = (n) => page.screenshot({ path: path.join(out, n + '.png') });

  await page.goto('/recipes/');
  await page.waitForSelector('.grid .card');
  await page.waitForTimeout(600);
  await shot('1-library');

  // top right: + first, then ••• (settings)
  const order = await page.$$eval('.lib-top .icon-btn', (b) => b.map((x) => x.dataset.act));
  ok(order.join() === 'add,settings', `top buttons: ${order}`);

  // sheets: reach the bottom edge, the page behind does not scroll, position is kept
  await page.evaluate(() => window.scrollTo(0, 200));
  await page.click('[data-act="add"]');
  await page.waitForTimeout(700);
  const sheet = await page.$eval('.sheet', (s) => [Math.round(s.getBoundingClientRect().bottom), innerHeight]);
  ok(sheet[0] >= sheet[1], `sheet reaches the bottom edge ${sheet}`);
  await shot('1b-add-sheet');
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(200);
  const behind = await page.evaluate(() => [Math.round(document.querySelector('.large-title').getBoundingClientRect().top), scrollY]);
  await page.mouse.click(200, 60);
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => [Math.round(document.querySelector('.large-title').getBoundingClientRect().top), scrollY]);
  ok(behind[0] === after[0] && after[1] === 200, `page locked behind the sheet, position restored ${behind} ${after}`);

  // settings: integration options (admin)
  await page.click('[data-act="settings"]');
  await page.waitForSelector('[data-opt="language"]');
  await page.waitForTimeout(600);
  await shot('1c-settings-top');
  await page.$eval('.sheet', (s) => s.scrollTo(0, 330));
  await page.waitForTimeout(200);
  await shot('1d-settings-options');
  ok(await page.$eval('[data-opt="extraction_mode"]', (e) => [...e.options].map((o) => o.value).join()) === 'classic,lean', 'settings: extraction mode choice');
  await page.selectOption('[data-opt="extraction_mode"]', 'lean');
  await page.waitForTimeout(400);
  ok((await page.evaluate(async () => {
    const t = JSON.parse(localStorage.getItem('recipes.auth')).access;
    return (await (await fetch('/api/recipes/settings', { headers: { Authorization: 'Bearer ' + t } })).json()).options.extraction_mode;
  })) === 'lean', 'extraction mode saved from the app');
  await page.selectOption('[data-opt="extraction_mode"]', 'classic');
  await page.waitForTimeout(400);
  await page.selectOption('[data-opt="language"]', 'nl');
  await page.click('[data-opt-toggle="transcribe"]');
  await page.waitForTimeout(500);
  const saved = await page.evaluate(async () => {
    const t = JSON.parse(localStorage.getItem('recipes.auth')).access;
    return (await (await fetch('/api/recipes/settings', { headers: { Authorization: 'Bearer ' + t } })).json()).options;
  });
  ok(saved.language === 'nl' && saved.transcribe === false, `options saved from the app ${JSON.stringify(saved)}`);
  await page.selectOption('[data-opt="language"]', 'en');
  await page.click('[data-opt-toggle="transcribe"]');
  await page.waitForTimeout(500);
  await page.mouse.click(12, 66); // the backdrop, next to the toast
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo(0, 0));

  // filters: multi-select, All clears
  const chips = await page.$$eval('[data-chip]', (b) => b.map((x) => x.dataset.chip).filter(Boolean));
  if (chips.length >= 2) {
    await page.click(`[data-chip="${chips[0]}"]`);
    await page.click(`[data-chip="${chips[1]}"]`);
    const pressed = await page.$$eval('[aria-pressed="true"]', (b) => b.map((x) => x.dataset.chip));
    ok(pressed.length === 2, `two filters active ${pressed}`);
    await shot('2-filters');
    await page.click('[data-chip=""]');
    ok((await page.$$eval('[aria-pressed="true"]', (b) => b.map((x) => x.dataset.chip))).join() === '', 'All clears filters');
  }
  await page.evaluate(() => window.scrollTo(0, 260));
  await page.waitForTimeout(400);
  await shot('3-library-scrolled');
  await page.evaluate(() => window.scrollTo(0, 0));

  // recipe with video
  await page.locator('.card:has(.badge)').first().click();
  await page.waitForSelector('#hero');
  await page.waitForTimeout(800);
  await shot('4-detail');
  await page.mouse.click(200, 150);
  await page.waitForTimeout(1000);
  ok(await page.$eval('#vid', (v) => !v.paused), 'tap on video plays');
  await page.mouse.click(200, 150);
  ok(await page.$eval('#vid', (v) => v.paused), 'second tap pauses');

  // pull down at the top -> full screen (touch events through CDP; start above the scrub bar)
  const cdp = await ctx.newCDPSession(page);
  const touch = (type, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x: 200, y }] });
  await touch('touchStart', 150);
  for (let y = 150; y <= 400; y += 20) { await touch('touchMove', y); await page.waitForTimeout(16); }
  await shot('5-pulling');
  await touch('touchEnd');
  await page.waitForTimeout(800);
  const tall = await page.$eval('#hero', (h) => [h.classList.contains('tall'), h.offsetHeight, innerHeight]);
  ok(tall[0] && tall[1] === tall[2], `pull opens full screen ${tall}`);
  await shot('6-full-screen');

  // scroll away -> folds back once at rest, content stays in place
  await page.evaluate(() => window.scrollTo(0, 1200));
  await page.waitForTimeout(100);
  const anchor = () => page.evaluate(() => Math.round(document.querySelector('.head').getBoundingClientRect().top));
  const before = await anchor();
  await page.waitForTimeout(700);
  ok(!(await page.$eval('#hero', (h) => h.classList.contains('tall'))), 'folds back after scrolling away');
  ok(Math.abs((await anchor()) - before) <= 1, 'no jump when folding back');

  // tags on a recipe open the filtered library
  await page.evaluate(() => window.scrollTo(0, 0));
  const tag = await page.$('.tags [data-tag]');
  if (tag) {
    const name = await tag.getAttribute('data-tag');
    await tag.click();
    await page.waitForSelector('.grid');
    ok((await page.$$eval('[aria-pressed="true"]', (b) => b.map((x) => x.dataset.chip))).join() === name, `tag ${name} filters library`);
  }
  // developer view on the phone: ••• -> Developer, full screen; re-run the AI and compare
  await page.locator('.card:has(.badge)').first().click();
  await page.waitForSelector('#hero');
  await page.click('[data-act="more"]');
  await page.click('[data-m="dev"]');
  await page.waitForSelector('#dev-run');
  await page.waitForTimeout(500);
  await shot('7-developer');
  await page.fill('#dev-instr', 'Make it spicier');
  await page.selectOption('#dev-mode', 'lean');
  await page.click('#dev-run');
  await page.waitForSelector('#dev-save');
  await page.waitForTimeout(1500);
  ok((await page.textContent('#dev-result .sub-h')).startsWith('Result · Lean'), 'developer view re-runs in lean mode');
  ok((await page.$$eval('#dev-result .cmp div', (d) => d.map((x) => x.textContent).join(' '))).includes('200 °C (400 °F)'), 'lean result shows the converted temperature');
  ok((await page.$$('.cmp-k')).length >= 5, 'experiment shows current next to new');
  await shot('8-developer-result');
  await page.click('#dev-save');
  await page.waitForTimeout(800);
  await page.click('[data-dev="close"]');
  ok(!(await page.$('.dev-panel')), 'developer view closes');

  // playlists row: three tiles between the chips and the grid, scrolls sideways, placeholders inactive
  await page.evaluate(() => { location.hash = '#/'; });
  await page.waitForSelector('.pl-row');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(600);
  const pl = await page.evaluate(() => {
    const y = (s) => document.querySelector(s).getBoundingClientRect();
    const row = document.querySelector('.pl-row');
    return { n: row.children.length, ord: y('.chips').bottom <= y('.pl-row').top + 1 && y('.pl-row').bottom <= y('.grid').top + 1,
      snap: getComputedStyle(row).scrollSnapType,
      titles: [...row.querySelectorAll('.card-title')].map((e) => e.textContent), dis: row.querySelectorAll('[aria-disabled="true"]').length };
  });
  ok(pl.n === 3 && pl.titles.join() === 'Shuffle,Bonus,Playlist 3' && pl.dis === 2, `three playlist tiles ${pl.titles}`);
  ok(pl.ord, 'row sits between chips and grid');
  ok(pl.snap.startsWith('x'), `row snaps horizontally (${pl.snap})`);
  await shot('12-playlists');
  await page.click('.pl-card.disabled');
  ok(!page.url().includes('#/r/'), 'placeholder tile does nothing');
  const x0 = await page.$eval('.pl-row', (r) => { r.style.paddingRight = '300px'; r.scrollLeft = 120; return r.scrollLeft; });
  ok(x0 > 0, `row scrolls horizontally (${x0})`);
  await page.$eval('.pl-row', (r) => { r.style.paddingRight = ''; r.scrollLeft = 0; });

  // shuffle: tile starts a session, right-to-left swipe goes to another random recipe
  const idOf = () => page.evaluate(() => (location.hash.match(/#\/r\/([\w-]+)/) || [])[1]);
  const swipe = async (x1, x2, y1, y2, steps = 12) => {
    const pt = (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
    await pt('touchStart', x1, y1);
    for (let i = 1; i <= steps; i++) { await pt('touchMove', x1 + ((x2 - x1) * i) / steps, y1 + ((y2 - y1) * i) / steps); await page.waitForTimeout(16); }
    await pt('touchEnd');
  };
  const total = await page.$$eval('.grid .card', (c) => c.length);
  await page.click('[data-pl="shuffle"]');
  await page.waitForSelector('.detail.shuffling');
  await page.waitForTimeout(900);
  const seen = [await idOf()];
  await shot('13-shuffle-start');
  await swipe(340, 60, 500, 510);
  await page.waitForTimeout(1200);
  const second = await idOf();
  if (total > 1) {
    ok(second && second !== seen[0], `swipe left goes to another recipe ${seen[0]} -> ${second}`);
    ok(await page.$('.detail.shuffling'), 'still a shuffle session after the swipe');
    seen.push(second);
    for (let i = 0; i < Math.min(total, 4); i++) {
      await swipe(340, 60, 500, 505);
      await page.waitForTimeout(1000);
      const id = await idOf();
      ok(id !== seen[seen.length - 1], 'no back-to-back repeat');
      seen.push(id);
    }
    await shot('14-shuffle-next');
    // history: model of the last 5 (hist[0..n], pos); swipe right = back, left = forward / new
    const hist = [seen[seen.length - 1]]; let pos = 0;
    const step = async (dir) => {
      const before = await idOf();
      if (dir > 0) await swipe(340, 60, 500, 505); else await swipe(60, 340, 500, 505);
      await page.waitForTimeout(1000);
      const id = await idOf();
      if (dir < 0) { if (pos > 0) { pos--; return id === hist[pos] ? '' : `back expected ${hist[pos]} got ${id}`; } return id === before ? '' : 'back at the start must stay'; }
      if (pos < hist.length - 1) { pos++; return id === hist[pos] ? '' : `forward expected ${hist[pos]} got ${id}`; }
      hist.push(id); pos++; if (hist.length > 6) { hist.shift(); pos--; }
      return id !== before ? '' : 'new recipe equals the one before';
    };
    const errs = [];
    for (const dir of [1, 1, 1, 1, 1, 1, 1, -1, -1, 1, -1, -1, -1, -1, -1, -1, -1, 1, 1, 1]) { const e = await step(dir); if (e) errs.push(e); }
    ok(errs.length === 0, `swipe history back/forward over the last 5 ${errs.join('; ')}`);
    ok(total < 3 || new Set(hist).size > 1, 'history holds several recipes');
    await shot('14b-shuffle-history');
    // a vertical drag does not change the recipe
    const before = await idOf();
    await swipe(200, 200, 600, 300);
    await page.waitForTimeout(700);
    ok((await idOf()) === before, 'vertical drag keeps the recipe');
    // Back leaves the session for the library
    await page.evaluate(() => history.back());
    await page.waitForSelector('.pl-row');
    await page.locator('.card').first().click();
    await page.waitForSelector('.detail');
    await page.waitForTimeout(700);
    const plain = await idOf();
    await swipe(340, 60, 500, 505);
    await page.waitForTimeout(900);
    ok((await idOf()) === plain && !(await page.$('.detail.shuffling')), 'no swipe outside a shuffle session');
  }
  await page.evaluate(() => { location.hash = '#/'; });
  await page.waitForSelector('.pl-row');

  // Bonus playlist + highlights (invented discounts, fed through the admin API)
  ok(await page.$eval('[data-pl-off="bonus"] .card-sub', (e) => e.textContent) === 'No offers yet', 'Bonus is disabled without offers');
  await shot('15-bonus-disabled');
  const feed = (store, items) => page.evaluate(async ([store, items]) => {
    const t = JSON.parse(localStorage.getItem('recipes.auth')).access;
    const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
    const r = await fetch('/api/recipes/discounts/' + store, { method: 'PUT', headers: { Authorization: 'Bearer ' + t, 'Content-Type': 'application/json' },
      body: JSON.stringify({ valid_from: day(-1), valid_to: day(6), items }) });
    return r.status;
  }, [store, items]);
  ok(await feed('ah', [{ name: 'Kippendij', terms: ['kippendij', 'chicken thigh'], price: '€5.49', was: '€6.99', note: 'invented offer' }]) === 200, 'discounts fed (ah)');
  ok(await feed('jumbo', [{ name: 'Chicken thigh fillet', terms: ['chicken thigh'], price: '€4.89' }]) === 200, 'discounts fed (jumbo)');
  ok(await feed('lidl', [{ name: 'Kippendij', terms: ['chicken thigh'], price: '€5.99' }]) === 200, 'discounts fed (lidl)');
  ok(await feed('dirk', [{ name: 'Kippendij', terms: ['chicken thigh'], price: '€6.19' }]) === 200, 'discounts fed (dirk)');
  await page.reload();
  await page.waitForSelector('.pl-row');
  const onOffer = await page.evaluate(async () => {
    const t = JSON.parse(localStorage.getItem('recipes.auth')).access;
    const d = await (await fetch('/api/recipes/discounts', { headers: { Authorization: 'Bearer ' + t } })).json();
    return Object.keys(d.recipes).length;
  });
  const bsub = await page.$eval('[data-pl="bonus"] .card-sub', (e) => e.textContent);
  ok(onOffer > 0 && bsub === `${onOffer} recipe${onOffer === 1 ? '' : 's'} on offer`, `Bonus card count: ${bsub}`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await shot('16-bonus-enabled');
  await page.click('[data-pl="bonus"]');
  await page.waitForSelector('.detail.shuffling .deal');
  await page.waitForTimeout(800);
  const glow = await page.evaluate(() => {
    const li = document.querySelector('.ing.deal');
    return { cls: li.className, bg: getComputedStyle(li).backgroundImage, shadow: getComputedStyle(li.querySelector('.txt')).textShadow,
      pills: [...li.querySelectorAll('.deal-pill')].map((p) => p.textContent.trim()), dots: [...li.querySelectorAll('.deal-pill i')].map((i) => getComputedStyle(i).backgroundColor) };
  });
  ok(glow.cls.includes('deal-jumbo'), `glow in the cheapest store (${glow.cls})`);
  ok(glow.bg !== 'none' && glow.shadow !== 'none', 'ingredient has a glow');
  ok(glow.pills.length === 4 && glow.pills[0].startsWith('AH') && glow.pills[1].startsWith('Jumbo') && glow.pills[2].startsWith('Lidl') && glow.pills[3].startsWith('Dirk'), `store names next to the dots ${glow.pills.map((p) => p.slice(0, 14))}`);
  ok(new Set(glow.dots).size === 4, `four store colours ${glow.dots}`);
  await page.locator('.ing.deal').first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await shot('17-ingredient-highlight');
  await page.evaluate(() => { location.hash = '#/'; });
  await page.waitForSelector('.pl-row');

  // shuffle respects the filter chips
  const fchip = (await page.$$eval('[data-chip]', (b) => b.map((x) => x.dataset.chip).filter(Boolean)))[0];
  if (fchip) {
    await page.click(`[data-chip="${fchip}"]`);
    const allowed = await page.$$eval('.grid .card', (c) => c.map((x) => x.getAttribute('href').split('/').pop()));
    await page.click('[data-pl="shuffle"]');
    await page.waitForSelector('.detail.shuffling');
    await page.waitForTimeout(700);
    ok(allowed.includes(await idOf()), `shuffle stays inside the ${fchip} filter`);
    await page.evaluate(() => history.back());
    await page.waitForSelector('.pl-row');
    await page.click('[data-chip=""]');
  }

  // wide screen: developer sidebar next to the recipe
  const wide = await browser.newContext({ viewport: { width: 1280, height: 860 }, colorScheme: 'dark', baseURL: BASE });
  await wide.addInitScript((r) => localStorage.setItem('recipes.auth', JSON.stringify({ access: 'x', refresh: r, exp: 0 })), refresh);
  const wp = await wide.newPage();
  wp.on('pageerror', (e) => errors.push(String(e)));
  await wp.goto('/recipes/');
  await wp.waitForSelector('.grid .card');
  ok((await wp.$$('.pl-row .pl-card')).length === 3, 'playlist row on the wide screen');
  await wp.screenshot({ path: path.join(out, '9-wide-library.png') });
  await wp.locator('.card:has(.badge)').first().click();
  await wp.waitForSelector('.dev-panel #dev-run');
  await wp.waitForTimeout(600);
  const side = await wp.evaluate(() => [Math.round(document.querySelector('.detail').getBoundingClientRect().right), Math.round(document.querySelector('.dev-panel').getBoundingClientRect().left)]);
  ok(side[0] <= side[1], `sidebar sits next to the recipe ${side}`);
  await wp.screenshot({ path: path.join(out, '10-wide-developer.png') });
  await wp.click('[data-act="more"]');
  await wp.waitForTimeout(600);
  await wp.screenshot({ path: path.join(out, '11-wide-sheet.png') });

  await page.evaluate(async () => {
    const t = JSON.parse(localStorage.getItem('recipes.auth')).access;
    for (const k of ['ah', 'jumbo', 'lidl', 'dirk']) await fetch('/api/recipes/discounts/' + k, { method: 'DELETE', headers: { Authorization: 'Bearer ' + t } });
  });
  ok(errors.length === 0, `no page errors ${errors}`);
  await browser.close();
  console.log('Screenshots in', out);
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
