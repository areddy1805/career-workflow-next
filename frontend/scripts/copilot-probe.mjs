import { chromium } from 'playwright';
const opp = process.env.OPP;
const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
const check = async (path, test) => {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' });
  const out = await test();
  console.log(`${out ? 'PASS' : 'FAIL'}  ${path} — ${out}`);
};
await check('/copilot/inbox', async () => {
  const rows = await page.locator('[role=row]').count();
  const selects = await page.locator('button[aria-label*="Filter by"]').count();
  const h1 = await page.locator('h1').textContent();
  return `h1=${h1.trim()} rows=${rows} selects=${selects}`;
});
await check('/copilot/history', async () => {
  const rows = await page.locator('tbody tr').count();
  return `h1=${(await page.locator('h1').textContent()).trim()} rows=${rows}`;
});
await check('/copilot/analytics', async () => {
  const h1 = await page.locator('h1').textContent();
  return `h1=${h1.trim()}`;
});
await check('/copilot/learning', async () => {
  const h1 = await page.locator('h1').textContent();
  const panels = await page.locator('section').count();
  return `h1=${h1.trim()} panels=${panels}`;
});
await check('/copilot/settings', async () => {
  const h1 = await page.locator('h1').textContent();
  const switches = await page.locator('[role=switch]').count();
  return `h1=${h1.trim()} switches=${switches}`;
});
if (opp) {
  await check(`/copilot/brief/${opp}`, async () => {
    const h1 = await page.locator('h1').textContent();
    const applyBtn = await page.getByRole('button', { name: /Apply/ }).count();
    return `h1=${h1.trim()} applyBtn=${applyBtn}`;
  });
}
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,300) : ''}`);
await b.close();
