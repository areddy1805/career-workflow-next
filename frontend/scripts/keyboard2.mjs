// PASS 3 — tab arrow-key roving, select keyboard, skip link target, focus ring on nav.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));
await p.goto('http://localhost:5173/applications', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
// tabs roving: focus tablist, ArrowRight moves
const tabs = await p.evaluate(() => {
  const list = document.querySelector('[role="tablist"]');
  if (!list) return 'no-tablist';
  const first = list.querySelector('[role="tab"]');
  first.focus();
  return 'focused';
});
console.log('[1] tabs:', tabs);
const roving = await p.evaluate(() => {
  const list = document.querySelector('[role="tablist"]');
  const first = list.querySelector('[role="tab"]');
  // Radix tabs use arrow keys; dispatch on the tab
  const before = first.getAttribute('data-state');
  list.querySelector('[role="tab"]').dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  // Radix listens on the tablist (roving) — check aria-selected after real press instead
  return before;
});
// real key press test
const tabsReal = p.locator('[role="tab"]').first();
await tabsReal.focus();
await p.keyboard.press('ArrowRight');
await p.waitForTimeout(200);
const selTab = await p.evaluate(() => document.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.trim());
console.log('[2] ArrowRight roving -> selected tab:', selTab);

// Ledger select keyboard
await p.goto('http://localhost:5173/ledger', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const sel = p.locator('[role="combobox"]').first();
if (await sel.count()) {
  await sel.focus();
  await p.keyboard.press('Enter'); // open
  await p.waitForTimeout(300);
  const open = await p.locator('[role="listbox"]').count();
  await p.keyboard.press('ArrowDown');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(300);
  const closed = await p.locator('[role="listbox"]').count();
  console.log(`[3] select keyboard open=${open} select+close=${closed===0 ? 'PASS' : 'FAIL'}`);
} else console.log('[3] no combobox on ledger');

// skip link to main on jobs (fresh page)
await p.goto('http://localhost:5173/jobs', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1000);
await p.keyboard.press('Tab');
const skip = await p.evaluate(() => document.activeElement?.textContent?.trim().slice(0, 20));
await p.keyboard.press('Enter');
const mainFocused = await p.evaluate(() => {
  const main = document.querySelector('main');
  return document.activeElement === main || main?.contains(document.activeElement);
});
console.log(`[4] jobs skip link: ${skip} -> main focused: ${mainFocused ? 'PASS' : 'FAIL'}`);

console.log(`pageerrors=${errs.length}`);
await b.close();
