import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/runs', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const row = p.locator('tbody tr[tabindex="0"]').first();
if (!(await row.count())) { console.log('no rows'); await b.close(); process.exit(0); }
await row.focus();
await p.keyboard.press('Enter');
await p.waitForTimeout(500);
console.log('runs sheet open:', await p.locator('[role="dialog"]').count());
await p.keyboard.press('Escape');
await p.waitForTimeout(500);
const after = await p.evaluate(() => ({
  sheets: document.querySelectorAll('[role="dialog"]').length,
  active: (document.activeElement?.tagName||'') + ' tabindex=' + (document.activeElement?.getAttribute('tabindex')||'null')
}));
console.log('after Esc:', JSON.stringify(after));
await b.close();
