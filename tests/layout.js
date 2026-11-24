// (c) 2026 HoopsMatic. All rights reserved.
// No horizontal scroll on any page template, 320 to 1920 px. Run after scripts/build_site.py:
//   node tests/layout.js            (needs Playwright + Chromium; CI installs them)
// Serves the repo root itself (no network) and fails if any page is wider than the viewport.
// At 390 and 1366 px it also fails if a table or card renders a lone ":" "," or "·" on its own line,
// and (both widths) if a team name wraps inside a word or its logo sits on a different line.
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
  'seasons/index.html', 'seasons/2026-27.html', 'lists/no-allstar-teammate.html?sort=pct&self=no', 'player/kawhi-leonard.html', 'player/nikola-jokic.html', 'stories/index.html', 'stories/2026-11-18.html', 'lists/winning-without-him.html?mp=8&mm=8', 'comparison-rules.html', 'lists/low-help-all-stars.html', 'lists/same-help-different-results.html', 'compare/charles-barkley--michael-jordan.html', 'player/michael-jordan.html?peer=kobe-bryant', 'seasons/1946-47.html', 'seasons/1997-98.html#t-CHI', 'seasons/2025-26.html',
  // round 3 components
  'compare/karl-malone--michael-jordan.html', 'lists/sixty-win-pace.html', 'lists/best-team.html',
  'lists/average-finish.html', 'player/chris-paul.html', 'player/tiny-archibald.html', 'player/kevin-durant.html',
  'seasons/1976-77.html', 'seasons/1974-75.html',
  // round 4: compare any two players, the compare block on player pages
  'compare/index.html', 'compare/?a=lebron-james&b=michael-jordan', 'compare/?a=cooper-flagg&b=luka-doncic',
  'player/cooper-flagg.html',
  // with and without his teammates, As teammates, Biggest teammate swings
  'player/draymond-green.html', 'compare/?a=draymond-green&b=stephen-curry', 'lists/teammate-swings.html', 'lists/teammate-swings.html?f=both',
];
const TEXT_CHECK = ['player/michael-jordan.html', 'player/lebron-james.html', 'player/chris-paul.html',
  'player/tiny-archibald.html', 'compare/karl-malone--michael-jordan.html', 'lists/sixty-win-pace.html',
  'lists/average-finish.html', 'seasons/1976-77.html', 'seasons/1974-75.html', 'index.html'];
// runs in the page: returns a list of problems
function textProblems(checkWrap) {
  const bad = [];
  const SCOPE = 'table, .card, .latest, .helprows, .lst, .rows, .cmpcards, .sbt, .h2hrow, .takes, .feat';
  const visible = el => !!(el.offsetParent || el.getClientRects().length);
  const lineOf = r => [r.top, r.bottom];
  const same = (a, b) => Math.min(a[1], b[1]) - Math.max(a[0], b[0]) > 2;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = n.textContent.trim();
    if (!/^[:,\u00b7]$/.test(t)) continue;
    const p = n.parentElement;
    if (!p || !p.closest(SCOPE) || !visible(p)) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const rr = r.getBoundingClientRect();
    if (!rr.width) continue;
    const box = p.closest('td, th, li, .card, .cc, div') || p;
    const w2 = document.createTreeWalker(box, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let ok = false, m;
    while ((m = w2.nextNode()) && !ok) {
      if (m === n) continue;
      if (m.nodeType === 3 && !m.textContent.trim()) continue;
      if (m.nodeType === 1 && m.tagName !== 'IMG') continue;
      const q = document.createRange(); q.selectNodeContents(m);
      for (const x of (m.nodeType === 1 ? [m.getBoundingClientRect()] : q.getClientRects()))
        if (x.width && same(lineOf(x), lineOf(rr))) { ok = true; break; }
    }
    if (!ok) bad.push(`lone "${t}" in ${box.className || box.tagName}: ${box.textContent.trim().slice(0, 60)}`);
  }
  if (checkWrap) {
    document.querySelectorAll('.tmn').forEach(tm => {
      if (!visible(tm)) return;
      const a = tm.querySelector(':scope > a, :scope > .tn');
      if (!a || !a.firstChild || a.firstChild.nodeType !== 3) return;
      const tn = a.firstChild, text = tn.textContent;
      let i = 0;
      for (const part of text.split(/(\s+)/)) {
        if (part.trim()) {
          const r = document.createRange(); r.setStart(tn, i); r.setEnd(tn, i + part.length);
          const tops = new Set([...r.getClientRects()].filter(x => x.width).map(x => Math.round(x.top)));
          if (tops.size > 1) bad.push(`team name wraps inside "${part}" (${text})`);
        }
        i += part.length;
      }
      const lg = tm.querySelector(':scope > img.lg');
      if (lg) {
        const r = document.createRange(); r.selectNodeContents(tn);
        const first = [...r.getClientRects()].filter(x => x.width)[0];
        const L = lg.getBoundingClientRect();
        if (first && !same([L.top, L.bottom], [first.top, first.bottom])) bad.push(`logo not on the name's line (${text})`);
      }
    });
  }
  return bad;
}
const extra = (process.env.TS_LAYOUT_EXTRA || '').split(',').filter(Boolean);
const WIDTHS = [320, 375, 414, 768, 1024, 1280, 1440, 1920];
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.webp': 'image/webp', '.png': 'image/png', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  let p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
  if (p.startsWith(ROOT) && fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, 'index.html');
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
    let file = path.join(ROOT, rel.split('?')[0].split('#')[0]);
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    if (!fs.existsSync(file)) { bad.push(`${rel}: missing`); continue; }
    for (const w of WIDTHS) {
      const page = await browser.newPage({ viewport: { width: w, height: 900 } });
      await page.goto(`http://localhost:${port}/${rel}`, { waitUntil: rel.includes('?') ? 'networkidle' : 'load' });
      await page.waitForTimeout(rel.includes('?') ? 400 : 50);
      const sw = await page.evaluate(() => document.documentElement.scrollWidth);
      if (sw > w) bad.push(`${rel} at ${w}px: page is ${sw}px wide`);
      n++;
      await page.close();
    }
  }
  for (const rel of TEXT_CHECK) {
    for (const w of [390, 1366]) {
      const page = await browser.newPage({ viewport: { width: w, height: 900 } });
      await page.goto(`http://localhost:${port}/${rel}`, { waitUntil: 'load' });
      const probs = await page.evaluate(textProblems, true);
      probs.slice(0, 8).forEach(p => bad.push(`${rel} at ${w}px: ${p}`));
      n++;
      await page.close();
    }
  }
  // the compare page (and old ?peer= links, which redirect to it) draws the same scoreboard and
  // season table as the static page
  {
    const text = async (u, w) => {
      const page = await browser.newPage({ viewport: { width: w, height: 900 } });
      await page.goto(`http://localhost:${port}/${u}`, { waitUntil: 'networkidle' });
      if (u.includes('?')) await page.waitForSelector('#cmp .sbt');
      const out = await page.evaluate(() => {
        const root = document.querySelector('#cmp') || document;
        const t = s => [...root.querySelectorAll(s)].map(x => x.innerText.replace(/\s+/g, ' ').trim()).join(' | ');
        return { sb: t('.sbt'), tally: t('.tally'), tint: t('.sbt td.la, .sbt td.lb'), wide: t('.cmpt tbody'), cards: t('.cmpcards') };
      });
      await page.close();
      return out;
    };
    for (const w of [390, 1366]) {
      const a = await text('compare/karl-malone--michael-jordan.html', w);
      for (const u of ['player/karl-malone.html?peer=michael-jordan', 'compare/?a=karl-malone&b=michael-jordan']) {
        const b = await text(u, w);
        for (const k of Object.keys(a)) if (a[k] !== b[k]) bad.push(`${u} differs from the static page at ${w}px: ${k}`);
      }
      n++;
    }
  }
  // teammate help by season: no text block narrower than 120 px, and on desktop the chips wrap in
  // rows (never one chip per line while the row has room)
  for (const slug of ['keldon-johnson', 'michael-jordan', 'jordan-poole', 'lebron-james']) {
    for (const w of [390, 768, 1024, 1366, 1920]) {
      const page = await browser.newPage({ viewport: { width: w, height: 900 } });
      await page.goto(`http://localhost:${port}/player/${slug}.html`, { waitUntil: 'load' });
      const probs = await page.evaluate(() => {
        const out = [], ul = document.querySelector('ul.helprows');
        if (!ul) return ['no help table'];
        ul.querySelectorAll('details').forEach(d => { d.open = true; });
        const tw = document.createTreeWalker(ul, NodeFilter.SHOW_TEXT);
        while (tw.nextNode()) {
          const n = tw.currentNode, t = n.textContent.trim();
          if (t.length < 12 || !n.parentElement.getClientRects().length) continue;
          const blk = n.parentElement.closest('p, .hnote, .chipsrow, .hbar, summary, li');
          const bw = blk.getBoundingClientRect().width;
          if (bw < 120) out.push(`text "${t.slice(0, 24)}" in a ${Math.round(bw)} px block`);
        }
        if (innerWidth >= 1024) ul.querySelectorAll('.chipsrow').forEach(c => {
          const ch = [...c.children];
          if (ch.length < 2) return;
          const need = ch.reduce((a, x) => a + x.getBoundingClientRect().width, 0);
          const tops = new Set(ch.map(x => Math.round(x.getBoundingClientRect().top)));
          if (tops.size === ch.length && c.getBoundingClientRect().width > need) out.push('chips stack one per line');
        });
        return out;
      });
      probs.slice(0, 4).forEach(x => bad.push(`player/${slug}.html help table at ${w}px: ${x}`));
      n++;
      await page.close();
    }
  }
  await browser.close();
  server.close();
  console.log(`${n} page/width checks, ${bad.length} problems`);
  if (bad.length) { console.log(bad.join('\n')); process.exit(1); }
});
