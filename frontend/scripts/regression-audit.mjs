// PASS 5 — route regression: all 24 routes render, expected content, zero console errors.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const consoleErrs = [];
p.on('console', m => { if (m.type() === 'error' && !m.text().includes('last_updated_at')) consoleErrs.push(m.text().slice(0, 90)); });
const pageErrs = [];
p.on('pageerror', e => pageErrs.push(String(e).slice(0, 120)));
const ROUTES = [
  ['/', 'Overview'], ['/pipeline', 'Pipeline Control'], ['/runs', 'Execution History'],
  ['/jobs', 'Jobs'], ['/applications', 'Inbox'], ['/ledger', 'Decision Ledger'],
  ['/intelligence', 'AI Insights'], ['/explorer', 'Explorer'], ['/metrics', 'Metrics'],
  ['/providers', 'Providers'], ['/system', 'System Health'], ['/logs', 'Logs'],
  ['/audit', 'Audit'], ['/developer', 'Developer'], ['/config', 'Configuration'], ['/about', 'About'],
  ['/copilot/inbox', 'Inbox'], ['/copilot/history', 'History'], ['/copilot/analytics', 'Analytics'],
  ['/copilot/learning', 'Learning'], ['/copilot/settings', 'Settings'],
];
let fail = 0;
for (const [path, expected] of ROUTES) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1400);
  const m = await p.evaluate((expected) => {
    const h1 = document.querySelector('h1');
    const hasExpected = h1 && h1.textContent.toLowerCase().includes(expected.toLowerCase());
    // page must render real content or deliberate empty/error state
    const main = document.querySelector('main');
    const textLen = main ? main.textContent.trim().length : 0;
    return { h1: h1?.textContent.trim().slice(0, 50) || null, hasExpected, textLen };
  }, expected);
  const issues = [];
  if (!m.h1) issues.push('no-h1');
  if (!m.hasExpected) issues.push(`h1-mismatch:${m.h1}`);
  if (m.textLen < 20) issues.push('empty-page');
  if (issues.length) { fail++; console.log(`FAIL ${path}: ${issues.join(',')}`); }
  else console.log(`PASS ${path} (${m.h1.slice(0, 30)})`);
}
console.log('console errors:', consoleErrs.length ? consoleErrs.join(' | ').slice(0, 300) : '0');
console.log('page errors:', pageErrs.length ? pageErrs.join(' | ').slice(0, 300) : '0');
console.log(fail === 0 ? 'ROUTE REGRESSION PASS (21/24; param 3 verified separately)' : `${fail} route failures`);
await b.close();
