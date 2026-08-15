import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
let fail = 0;
for (const path of ['/', '/jobs', '/ledger', '/copilot/inbox']) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1000);
  await p.keyboard.press('Meta+k');
  await p.waitForTimeout(300);
  const dlg = await p.locator('[cmdk-root], [role="dialog"]').count();
  if (!dlg) { fail++; console.log(`FAIL palette on ${path}`); }
  await p.keyboard.press('Escape');
  await p.waitForTimeout(200);
}
console.log(fail === 0 ? 'PALETTE PASS (4 routes)' : `${fail} failures`);
await b.close();
