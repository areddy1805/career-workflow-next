import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
const check = async (path, test) => {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' });
  const out = await test();
  console.log(`${out ? 'PASS' : 'FAIL'}  ${path} — ${out}`);
};
await check('/ledger', async () => {
  const rows = await page.locator('tbody tr').count();
  const selects = await page.locator('button[aria-label*="Filter by"]').count();
  return `h1=${(await page.locator('h1').textContent()).trim()} rows=${rows} selects=${selects}`;
});
await check('/intelligence', async () => {
  const h1 = await page.locator('h1').textContent();
  const providers = await page.locator('text=Providers').count();
  return `h1=${h1.trim()} providersLabel=${providers}`;
});
await check('/explorer', async () => {
  const h1 = await page.locator('h1').textContent();
  const runs = await page.locator('button').count();
  return `h1=${h1.trim()} buttons=${runs}`;
});
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,300) : ''}`);
await b.close();
