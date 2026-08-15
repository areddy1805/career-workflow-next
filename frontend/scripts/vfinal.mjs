import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));
p.on('console', m => { if (m.type() === 'error' && !m.text().includes('last_updated_at')) errs.push(m.text().slice(0, 80)); });
for (const path of ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer', '/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about', '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings']) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(900);
}
// virtualization spot check
await p.goto('http://localhost:5173/jobs', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const rows = await p.evaluate(() => document.querySelectorAll('[role="row"][tabindex="0"]').length);
console.log(`jobs rendered rows (virtualized): ${rows}`);
console.log(`console/page errors across 21 routes: ${errs.length} ${errs.join(' | ').slice(0,200)}`);
await b.close();
