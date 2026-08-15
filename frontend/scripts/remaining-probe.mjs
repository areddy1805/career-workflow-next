import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
const paths = ['/metrics','/providers','/system','/logs','/audit','/developer','/config','/about'];
for (const path of paths) {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' });
  const h1 = (await page.locator('h1').textContent()).trim();
  const errs = await page.locator('[role=alert]').count();
  console.log(`${path} — h1=${h1} alerts=${errs}`);
}
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,400) : ''}`);
await b.close();
