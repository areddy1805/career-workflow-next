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
if (opp) {
  await check(`/copilot/brief/${opp}`, async () => {
    const h1 = await page.locator('h1').textContent();
    return `h1=${h1.trim()}`;
  });
  await check(`/copilot/apply/${opp}`, async () => {
    const h1 = await page.locator('h1').textContent();
    return `h1=${h1.trim()}`;
  });
  await check(`/copilot/assistant/${opp}`, async () => {
    const h1 = await page.locator('h1').textContent();
    return `h1=${h1.trim()}`;
  });
}
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,300) : ''}`);
await b.close();
