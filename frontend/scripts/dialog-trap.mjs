import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/applications', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const row = p.locator('tbody tr[tabindex="0"]').first();
if (!(await row.count())) { console.log('no rows'); await b.close(); process.exit(0); }
await row.focus();
await p.keyboard.press('Enter');
await p.waitForTimeout(700);
console.log('drawer open:', await p.locator('[role="dialog"]').count());
let escaped = false;
for (let i = 0; i < 25; i++) {
  await p.keyboard.press('Tab');
  const inD = await p.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    return d ? d.contains(document.activeElement) : 'gone';
  });
  if (inD === false) { escaped = true; break; }
  if (inD === 'gone') break;
}
const cnt = await p.locator('[role="dialog"]').count();
console.log(`Tab x25: ${escaped ? 'FAIL escaped' : 'PASS stayed inside'} dialogOpen=${cnt}`);
await p.keyboard.press('Escape');
await p.waitForTimeout(400);
console.log('Escape closes:', (await p.locator('[role="dialog"]').count()) === 0 ? 'PASS' : 'FAIL');
await b.close();
