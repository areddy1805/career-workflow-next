import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/ledger', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const row = p.locator('tbody tr[tabindex="0"]').first();
await row.focus();
await p.keyboard.press('Enter');
await p.waitForTimeout(500);
console.log('sheet open:', await p.locator('[role="dialog"]').count());
await p.keyboard.press('Escape');
await p.waitForTimeout(500);
const after = await p.evaluate(() => {
  const el = document.activeElement;
  return el ? `${el.tagName}#${el.id}.${(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,30)} tabindex=${el.getAttribute('tabindex')}` : 'body';
});
console.log('focus after Esc:', after);
await b.close();
