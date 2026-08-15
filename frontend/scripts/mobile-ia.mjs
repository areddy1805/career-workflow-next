// PASS 3 — mobile IA: drawer nav, close-on-navigation, scrim, focus; table scrolls horizontally.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const errs = [];
p.on('pageerror', e => errs.push(String(e)));
await p.setViewportSize({ width: 375, height: 812 });
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);

// open drawer
await p.locator('button[aria-label="Open navigation menu"]').click();
await p.waitForTimeout(400);
const drawer = p.locator('[role="dialog"]');
console.log('[1] drawer open:', await drawer.count() === 1 ? 'PASS' : 'FAIL');

// scrim present
const scrim = await p.evaluate(() => {
  const d = document.querySelector('[role="dialog"]');
  const scrims = d?.parentElement?.querySelectorAll('[data-state="open"]');
  return (scrims?.length || 0);
});
console.log('[2] scrim/overlay open elements:', scrim > 0 ? 'PASS' : 'FAIL');

// nav links reachable in drawer
const links = await drawer.locator('a').count();
console.log('[3] drawer nav links:', links > 15 ? `PASS (${links})` : `FAIL (${links})`);

// close-on-navigation: click a nav link, drawer must close
await drawer.locator('a[href="/pipeline"]').first().click();
await p.waitForTimeout(600);
console.log('[4] drawer closes on navigation:', (await p.locator('[role="dialog"]').count()) === 0 ? 'PASS' : 'FAIL');
console.log('[5] navigated to:', await p.evaluate(() => location.pathname));

// Jobs table horizontal scroll at 375
await p.goto('http://localhost:5173/jobs', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(2000);
const scroll = await p.evaluate(() => {
  const main = document.querySelector('main');
  const doc = document.documentElement;
  return { docOverflow: doc.scrollWidth - doc.clientWidth, mainOverflow: main.scrollWidth - main.clientWidth };
});
console.log('[6] jobs @375 overflow:', scroll.docOverflow <= 0 && scroll.mainOverflow <= 0 ? `PASS ${JSON.stringify(scroll)}` : `FAIL ${JSON.stringify(scroll)}`);
// the inner table region must scroll horizontally (has horizontal scroller)
const hScroll = await p.evaluate(() => {
  const scrollers = [...document.querySelectorAll('div')].filter(d => d.scrollWidth > d.clientWidth && d.clientWidth > 100);
  return scrollers.map(d => Math.round(d.scrollWidth - d.clientWidth)).slice(0, 2);
});
console.log('[7] inner horizontal scrollers:', hScroll.length ? `PASS (${hScroll.join(',')}px overflow scrollable)` : 'no inner scroll (check)');

console.log(`pageerrors=${errs.length}`);
await b.close();
