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
  ok(errors.length === 0, `no page errors ${errors}`);
  await browser.close();
  console.log('Screenshots in', out);
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
