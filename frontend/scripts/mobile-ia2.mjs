import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.setViewportSize({ width: 375, height: 812 });
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
await p.locator('button[aria-label="Open navigation menu"]').click();
await p.waitForTimeout(400);
const m = await p.evaluate(() => {
  const dialog = document.querySelector('[role="dialog"]');
  if (!dialog) return 'no-dialog';
  // scrim = the full-screen close button behind the aside
  const scrim = [...dialog.children].find(c => c.getAttribute('aria-label') === 'Close navigation menu' && c.classList.contains('absolute') && c.classList.contains('inset-0'));
  const aside = dialog.querySelector('aside');
  const asideR = aside.getBoundingClientRect();
  const bg = getComputedStyle(scrim).backgroundColor;
  return {
    scrim: !!scrim,
    scrimBg: bg,
    asideW: Math.round(asideR.width),
    ariaModal: dialog.getAttribute('aria-modal'),
    label: dialog.getAttribute('aria-label'),
  };
});
console.log(JSON.stringify(m, null, 1));
// close-on-navigation via keyboard: focus link, Enter
await p.keyboard.press('Tab');
await p.keyboard.press('Tab');
await p.keyboard.press('Enter');
await p.waitForTimeout(500);
console.log('after Enter nav, dialog count:', await p.locator('[role="dialog"]').count());
await b.close();
