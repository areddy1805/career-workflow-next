// PASS 5 — navigation audit: rail links navigate without error.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
const links = await p.evaluate(() => [...document.querySelectorAll('nav a')].map(a => ({ href: a.getAttribute('href'), text: a.textContent.trim().slice(0, 20) })));
let ok = 0, bad = 0;
for (const l of links) {
  if (!l.href || l.href.startsWith('http') || l.href === '#') continue;
  await p.click(`nav a[href="${l.href}"]`).catch(() => {});
  await p.waitForTimeout(600);
  const h1 = await p.locator('h1').first().textContent().catch(() => '');
  if (h1.trim()) ok++; else { bad++; console.log(`FAIL nav -> ${l.href}`); }
}
console.log(`nav links: ${links.length} total, ${ok} navigated-with-h1, ${bad} failed`);
console.log(`pageerrors=${errs.length}`);
await b.close();
