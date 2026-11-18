// (c) 2026 HoopsMatic. All rights reserved.
// No horizontal scroll on any page template, 320 to 1920 px. Run after scripts/build_site.py:
//   node tests/layout.js            (needs Playwright + Chromium; CI installs them)
// Serves the repo root itself (no network) and fails if any page is wider than the viewport.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const PAGES = [
  'index.html', 'how-we-count.html', 'players/a.html',
  'player/michael-jordan.html', 'player/michael-jordan.html?vs=DET&k=4', 'player/james-harden.html', 'player/george-mikan.html',
  'player/bill-russell.html', 'player/lebron-james.html', 'player/aaron-gordon.html',
  'lists/worst-team.html', 'lists/bad-luck.html', 'lists/franchise-winningest.html',
  'lists/winning-without-him.html', 'lists/on-off-movers.html',
  'lists/career-wins.html', 'lists/wins-minus-losses.html?hl=michael-jordan&sort=pct',
  'lists/winning-seasons.html', 'lists/playoff-trips.html', 'lists/deepest-run.html', 'lists/titles.html',
  'lists/average-finish.html?sort=adj', 'lists/gap-career.html?from=1990&ts=20',
  'seasons/index.html', 'seasons/1946-47.html', 'seasons/1997-98.html#t-CHI', 'seasons/2025-26.html',
];
const extra = (process.env.TS_LAYOUT_EXTRA || '').split(',').filter(Boolean);
const WIDTHS = [320, 375, 414, 768, 1024, 1280, 1440, 1920];
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.webp': 'image/webp', '.png': 'image/png', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
server.listen(0, async () => {
  const port = server.address().port;
  const browser = await chromium.launch();
  const bad = [];
  let n = 0;
  for (const rel of PAGES.concat(extra)) {
    const file = path.join(ROOT, rel.split('?')[0].split('#')[0]);
    if (!fs.existsSync(file)) { bad.push(`${rel}: missing`); continue; }
    for (const w of WIDTHS) {
      const page = await browser.newPage({ viewport: { width: w, height: 900 } });
      await page.goto(`http://localhost:${port}/${rel}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(rel.includes('?') ? 400 : 50);
      const sw = await page.evaluate(() => document.documentElement.scrollWidth);
      if (sw > w) bad.push(`${rel} at ${w}px: page is ${sw}px wide`);
      n++;
      await page.close();
    }
  }
  await browser.close();
  server.close();
  console.log(`${n} page/width checks, ${bad.length} too wide`);
  if (bad.length) { console.log(bad.join('\n')); process.exit(1); }
});
