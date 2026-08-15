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
await check('/pipeline', async () => {
  const h1 = await page.locator('h1').textContent();
  const radio = await page.getByRole('radio', { name: 'Dry Run' }).count();
  const log = await page.locator('pre').first().textContent();
  const hasCoord = (await page.locator('h1 span').first().textContent()).includes('01 · 02');
  return `h1=${h1.trim()} radios=${radio} log=${log.slice(0,30).replace(/\n/g,' ')} coord=${hasCoord}`;
});
await check('/runs', async () => {
  const rows = await page.locator('tbody tr').count();
  const h1 = await page.locator('h1').textContent();
  return `h1=${h1.trim()} rows=${rows}`;
});
await check('/applications', async () => {
  const tabs = await page.locator('[role=tab]').count();
  const rows = await page.locator('tbody tr').count();
  const h1 = await page.locator('h1').textContent();
  return `h1=${h1.trim()} tabs=${tabs} rows=${rows}`;
});
await check('/jobs', async () => {
  const h1 = await page.locator('h1').textContent();
  const headerRow = await page.locator('text=COMPANY').count();
  return `h1=${h1.trim()} gridHeader=${headerRow}`;
});
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,300) : ''}`);
await b.close();
