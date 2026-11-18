// (c) 2026 HoopsMatic. All rights reserved.
// Pre-render the share PNG of every suggested comparison (compare/*.html -> compare/img/*.png)
// with the same canvas code as the "Download image" button (assets/compare.js). Local only:
// needs Playwright + Chromium. Skips images that already exist unless --force.
//   node scripts/render_cards.js [--force] [--limit N]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const force = process.argv.includes('--force');
const li = process.argv.indexOf('--limit');
const limit = li > 0 ? +process.argv[li + 1] : Infinity;
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.webp': 'image/webp', '.png': 'image/png', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
server.listen(0, async () => {
  const port = server.address().port;
  const outDir = path.join(ROOT, 'compare', 'img');
  fs.mkdirSync(outDir, { recursive: true });
  const pages = fs.readdirSync(path.join(ROOT, 'compare')).filter(f => f.endsWith('.html')).sort();
  const browser = await chromium.launch();
  const page = await browser.newPage();
  let n = 0;
  for (const f of pages) {
    const out = path.join(outDir, f.replace(/\.html$/, '.png'));
    if (!force && fs.existsSync(out)) continue;
    if (n >= limit) break;
    await page.goto(`http://localhost:${port}/compare/${f}`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.TSCompare && window.TSCompare.draw);
    const data = await page.evaluate(async () => {
      const b = document.getElementById('card-dl');
      const cv = await window.TSCompare.draw(JSON.parse(b.getAttribute('data-card')), b.getAttribute('data-up'));
      return cv.toDataURL('image/png');
    });
    fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
    n++;
  }
  await browser.close();
  server.close();
  console.log(`rendered ${n} share images`);
});
