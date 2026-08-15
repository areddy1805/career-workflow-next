// PASS 5 — param routes: verify brief/assistant read-only; inspect apply WITHOUT navigating.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const writes = [];
p.on('request', r => { if (['POST','PUT','PATCH','DELETE'].includes(r.method())) writes.push(r.method() + ' ' + r.url().split(':5173')[1]); });
// get real opp id
const opps = await (await fetch('http://localhost:5173/api/copilot/opportunities')).json();
const items = Array.isArray(opps?.data) ? opps.data : [];
const opp = items[0]?.opportunity_id ?? items[0]?.id;
if (!opp) { console.log('no opp id'); await b.close(); process.exit(0); }
console.log('opp:', opp.slice(0, 50));
for (const path of [`/copilot/brief/${opp}`, `/copilot/assistant/${opp}`]) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1500);
  const h1 = await p.locator('h1').first().textContent().catch(() => '');
  console.log(`${path.split('/')[2]} h1=${(h1||'').trim().slice(0,40)}`);
}
// inspect apply route SOURCE for mutation-on-mount (no navigation)
const applySrc = await (await fetch('http://localhost:5173/src/pages/copilot/Apply.tsx')).text().catch(() => '');
console.log('Apply.tsx createSession call sites (static inspect, NOT executed):',
  (applySrc.match(/createSession/g) || []).length);
console.log('WRITES during brief/assistant smoke:', writes.length ? writes.join(' | ') : '(none)');
await b.close();
