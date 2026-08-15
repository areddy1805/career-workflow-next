// PASS 4 — polish: check for visual debris in rendered DOM + excessive framing.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer', '/metrics', '/providers', '/system', '/logs', '/audit', '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings', '/config', '/about'];
let total = 0;
for (const path of ROUTES) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1000);
  const m = await p.evaluate(() => {
    const out = {};
    // empty divs (render debris)
    out.emptyDivs = [...document.querySelectorAll('div')].filter(d => !d.textContent.trim() && d.children.length === 0 && d.getBoundingClientRect().height > 4).length;
    // horizontal rules count (excessive framing)
    out.hrCount = document.querySelectorAll('hr').length;
    // divs with both border AND shadow (over-framing)
    out.framed = [...document.querySelectorAll('div')].filter(d => {
      const s = getComputedStyle(d);
      return s.borderTopWidth !== '0px' && s.borderTopWidth === s.borderBottomWidth;
    }).length;
    // fixed-position elements (possible dead overlays)
    out.fixed = [...document.querySelectorAll('*')].filter(el => getComputedStyle(el).position === 'fixed' && el.getBoundingClientRect().height > 0).length;
    return out;
  });
  if (m.emptyDivs > 3 || m.framed > 40 || m.fixed > 4) {
    total++;
    console.log(`NOTE ${path}: emptyDivs=${m.emptyDivs} hr=${m.hrCount} framed=${m.framed} fixed=${m.fixed}`);
  }
}
console.log(total === 0 ? 'POLISH AUDIT CLEAN (20 routes)' : `${total} routes need polish review`);
await b.close();
