// AUDIT 1b — param routes with real IDs (read-only: brief/assistant; apply = inspect only)
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));
const opps = await (await fetch('http://localhost:5173/api/copilot/opportunities')).json();
const items = Array.isArray(opps?.data) ? opps.data : [];
const opp = items[0]?.opportunity_id ?? items[0]?.id;
if (!opp) { console.log('no real opp id'); await b.close(); process.exit(0); }
for (const path of [`/copilot/brief/${opp}`, `/copilot/assistant/${opp}`]) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1500);
  const h1 = await p.locator('h1').first().textContent().catch(() => '');
  const content = await p.evaluate(() => document.querySelector('main')?.textContent.trim().length || 0);
  console.log(`${path.split('/')[2]}: h1="${(h1||'').trim().slice(0,35)}" contentLen=${content} ${h1 && content > 30 ? 'PASS' : 'FAIL'}`);
}
console.log('param pageerrors:', errs.length);
await b.close();
