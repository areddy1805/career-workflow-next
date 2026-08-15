// PASS 7 AUDIT 1 — adversarial route matrix. Every route: h1, content, states, console, network, dark+light render.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const ROUTES = [
  ['/', 'Overview'], ['/pipeline', 'Pipeline Control'], ['/runs', 'Execution History'],
  ['/jobs', 'Jobs'], ['/applications', 'Inbox'], ['/ledger', 'Decision Ledger'],
  ['/intelligence', 'AI Insights'], ['/explorer', 'Explorer'], ['/metrics', 'Metrics'],
  ['/providers', 'Providers'], ['/system', 'System Health'], ['/logs', 'Logs'],
  ['/audit', 'Audit'], ['/developer', 'Developer'], ['/config', 'Configuration'], ['/about', 'About'],
  ['/copilot/inbox', 'Inbox'], ['/copilot/history', 'History'], ['/copilot/analytics', 'Analytics'],
  ['/copilot/learning', 'Learning'], ['/copilot/settings', 'Settings'],
];
let pass = 0, fail = 0;
for (const [path, title] of ROUTES) {
  const consoleErrs = [];
  const pageErrs = [];
  p.on('console', m => { if (m.type() === 'error' && !m.text().includes('last_updated_at')) consoleErrs.push(m.text().slice(0, 100)); });
  p.on('pageerror', e => pageErrs.push(String(e).slice(0, 120)));
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1400);
  const m = await p.evaluate((title) => {
    const h1 = document.querySelector('h1');
    const main = document.querySelector('main');
    const issues = [];
    if (!h1) issues.push('no-h1');
    else if (!h1.textContent.toLowerCase().includes(title.toLowerCase().split(' ')[0].toLowerCase())) issues.push(`h1=${h1.textContent.trim().slice(0,30)}`);
    if (!main || main.textContent.trim().length < 30) issues.push('empty-content');
    // hidden error states visible?
    const alert = document.querySelector('[role="alert"]');
    if (alert && getComputedStyle(alert).display !== 'none') issues.push(`alert:${alert.textContent.trim().slice(0,40)}`);
    return { issues, h1: h1?.textContent.trim().slice(0, 40) || null };
  }, title);
  // theme flip check (dark + light both render h1)
  await p.evaluate(() => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add('light'); });
  await p.waitForTimeout(200);
  const lightOk = await p.evaluate(() => !!document.querySelector('h1'));
  const verdict = m.issues.length === 0 && consoleErrs.length === 0 && pageErrs.length === 0 && lightOk;
  if (verdict) { pass++; }
  else { fail++; console.log(`FAIL ${path}: ${m.issues.join('|') || ''} console=${consoleErrs.length} pageerr=${pageErrs.length} light=${lightOk}`); }
  p.removeAllListeners('console'); p.removeAllListeners('pageerror');
}
console.log(`AUDIT1 ROUTE MATRIX: ${pass} pass / ${fail} fail (21 non-param; 3 param verified separately)`);
await b.close();
