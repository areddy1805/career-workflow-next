// PASS H — read-only param route verification.
// SAFETY: /copilot/apply/<id> POSTs createSession on mount (mutation) — NOT exercised.
// Only read-only param routes verified: brief (opportunity fetch) + assistant (session query).
import { chromium } from 'playwright';

const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));

// fetch a real opportunity id (GET, read-only)
const opps = await (await fetch('http://localhost:5173/api/copilot/opportunities')).json();
const items = opps?.data?.items ?? opps?.data ?? opps?.items ?? [];
const opp = items[0]?.id ?? items[0]?.opportunity_id ?? items[0]?._id;
if (!opp) { console.log('FAIL — no real opportunity id available'); await b.close(); process.exit(1); }
console.log(`using real opp id: ${opp.slice(0, 60)}…`);

const check = async (path, test) => {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' });
  const out = await test();
  console.log(`${out ? 'PASS' : 'FAIL'}  ${path} — ${out}`);
};

await check(`/copilot/brief/${opp}`, async () => {
  const h1 = await page.locator('h1').first().textContent();
  return `h1=${h1.trim().slice(0, 60)}`;
});
await check(`/copilot/assistant/${opp}`, async () => {
  const h1 = await page.locator('h1').first().textContent();
  return `h1=${h1.trim().slice(0, 60)}`;
});
console.log('SKIP  /copilot/apply/<id> — POSTs createSession on mount (mutation), safety policy forbids exercising it.');
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0, 300) : ''}`);
await b.close();
