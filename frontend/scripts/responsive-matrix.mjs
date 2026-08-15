import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer',
  '/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about',
  '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings'];
const WIDTHS = [1440, 1280, 1024, 768, 375];
let fail = 0;
for (const path of ROUTES) {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.waitForTimeout(150);
    const m = await page.evaluate(() => {
      const doc = document.documentElement;
      return { overflow: doc.scrollWidth - doc.clientWidth, h1: !!document.querySelector('h1') };
    });
    const menuBtn = w === 375 ? await page.locator('button[aria-label="Open navigation menu"]').count() : -1;
    if (m.overflow > 0 || (w === 375 && menuBtn !== 1)) {
      fail++;
      console.log(`FAIL ${path} @${w} overflow=${m.overflow} h1=${m.h1} menuBtn=${menuBtn}`);
    }
  }
  if (!errors.length) continue;
  console.log(`pageerrors on ${path}: ${errors.join(' | ').slice(0,200)}`);
  errors.length = 0;
}
console.log(fail === 0 ? 'RESPONSIVE MATRIX PASS (21 routes × 5 widths)' : `${fail} failures`);
await b.close();
