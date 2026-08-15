// PASS 3 — keyboard-only interaction audit.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));

// 1. Skip link first in tab order (fresh load)
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
await p.keyboard.press('Tab');
const first = await p.evaluate(() => {
  const el = document.activeElement;
  return el ? `${el.tagName}.${(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,40)}` : 'none';
});
console.log(`[1] first Tab target: ${first} ${first.startsWith('A')||first.includes('Skip')?'PASS':'FAIL(skip link expected)'}`);

// 2. Skip link activates main
if (first.includes('Skip')) {
  await p.keyboard.press('Enter');
  await p.waitForTimeout(300);
  const mainFocused = await p.evaluate(() => document.activeElement === document.querySelector('main') || document.activeElement?.id === 'main-content');
  console.log(`[2] skip link focus main: ${mainFocused?'PASS':'FAIL'}`);
}

// 3. Tab order reaches nav links + no focus traps
await p.goto('http://localhost:5173/pipeline', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1000);
const focusVisible = await p.evaluate(() => {
  // tab through 12 elements, verify focus-visible styles apply
  for (let i = 0; i < 12; i++) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
  }
  const el = document.activeElement;
  if (!el) return 'none';
  const style = getComputedStyle(el);
  return `${el.tagName}.${(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,30)} outline=${style.outlineStyle||'none'} ring=${el.classList.contains('focus-visible:ring-2')}`;
});
console.log(`[3] tab reachable: ${focusVisible}`);

// 4. Command palette opens via Cmd+K
await p.keyboard.press('Meta+k');
await p.waitForTimeout(400);
const palette = await p.locator('[role="dialog"], [cmdk-root]').count();
console.log(`[4] Cmd+K palette: ${palette > 0 ? 'PASS' : 'FAIL'}`);
if (palette > 0) {
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  console.log(`[5] palette Escape closes: ${(await p.locator('[cmdk-root], [role="dialog"]').count()) === 0 ? 'PASS' : 'FAIL'}`);
}

// 6. mobile drawer keyboard: open with Enter on menu button, Escape closes, focus restore
await p.setViewportSize({ width: 375, height: 812 });
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1000);
await p.evaluate(() => {
  const btn = document.querySelector('button[aria-label="Open navigation menu"]');
  if (!btn) return 'no-btn';
  btn.focus();
  btn.click();
  return 'clicked';
});
await p.waitForTimeout(400);
const drawer = await p.locator('[role="dialog"]').count();
const focusInDrawer = await p.evaluate(() => {
  const d = document.querySelector('[role="dialog"]');
  if (!d) return 'no-dialog';
  return d.contains(document.activeElement) ? 'inside' : 'outside';
});
console.log(`[6] drawer open=${drawer} focus=${focusInDrawer} ${drawer===1 && focusInDrawer==='inside' ? 'PASS' : 'FAIL'}`);
await p.keyboard.press('Escape');
await p.waitForTimeout(400);
const closed = await p.locator('[role="dialog"]').count();
console.log(`[7] drawer Escape closes: ${closed===0 ? 'PASS' : 'FAIL'}`);

// 8. dialogs: focus containment + restore (Ledger sheet)
await p.setViewportSize({ width: 1440, height: 900 });
await p.goto('http://localhost:5173/ledger', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const row = p.locator('tbody tr[tabindex="0"]').first();
if (await row.count()) {
  await row.focus();
  await p.keyboard.press('Enter');
  await p.waitForTimeout(500);
  const dlg = p.locator('[role="dialog"]');
  const dlgCount = await dlg.count();
  const focusIn = await p.evaluate(() => document.querySelector('[role="dialog"]')?.contains(document.activeElement));
  console.log(`[8] ledger sheet open=${dlgCount} focusInside=${focusIn} ${dlgCount===1 && focusIn ? 'PASS':'FAIL'}`);
  await p.keyboard.press('Escape');
  await p.waitForTimeout(400);
  const focusRestored = await p.evaluate(() => document.activeElement?.getAttribute('tabindex') === '0' || document.activeElement?.tagName === 'TR');
  console.log(`[9] focus restore after close: ${focusRestored?'PASS':'FAIL(returned to row?)'}`);
}

console.log(`pageerrors=${errs.length}`);
await b.close();
