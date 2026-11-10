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
  await page.click('#dev-run');
  await page.waitForSelector('#dev-save');
  await page.waitForTimeout(1500);
  ok((await page.$$('.cmp-k')).length >= 5, 'experiment shows current next to new');
  await shot('8-developer-result');
  await page.click('#dev-save');
  await page.waitForTimeout(800);
  await page.click('[data-dev="close"]');
  ok(!(await page.$('.dev-panel')), 'developer view closes');

  // wide screen: developer sidebar next to the recipe
  const wide = await browser.newContext({ viewport: { width: 1280, height: 860 }, colorScheme: 'dark', baseURL: BASE });
  await wide.addInitScript((r) => localStorage.setItem('recipes.auth', JSON.stringify({ access: 'x', refresh: r, exp: 0 })), refresh);
  const wp = await wide.newPage();
  wp.on('pageerror', (e) => errors.push(String(e)));
  await wp.goto('/recipes/');
  await wp.waitForSelector('.grid .card');
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

  ok(errors.length === 0, `no page errors ${errors}`);
  await browser.close();
  console.log('Screenshots in', out);
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
