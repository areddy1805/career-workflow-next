// PASS 3 — focus ring visible in both themes; touch target size at 375.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
for (const theme of ['dark', 'light']) {
  await p.goto('http://localhost:5173/pipeline', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1000);
  await p.evaluate(t => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add(t); }, theme);
  await p.waitForTimeout(200);
  const ring = await p.evaluate(() => {
    // focus a button, check computed outline/box-shadow ring
    const btn = document.querySelector('button');
    if (!btn) return 'no-button';
    btn.focus();
    const s = getComputedStyle(btn);
    const ring = getComputedStyle(btn, '::after');
    return { outline: s.outlineStyle, outlineW: s.outlineWidth, outlineC: s.outlineColor, boxShadow: s.boxShadow.slice(0, 60) };
  });
  console.log(`${theme} focus ring on button: outline=${ring.outline}/${ring.outlineW} shadow=${ring.boxShadow}`);
}
// touch targets at 375: buttons/links under 40x40 (WCAG 2.5.5 AA target)
await p.setViewportSize({ width: 375, height: 812 });
await p.goto('http://localhost:5173/applications', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
const targets = await p.evaluate(() => {
  const small = [...document.querySelectorAll('button, a[href]')]
    .map(el => { const r = el.getBoundingClientRect(); return { el, r }; })
    .filter(({ el, r }) => r.width > 0 && r.height > 0 && (r.width < 32 || r.height < 32) && !el.closest('[role="dialog"]'))
    .slice(0, 8)
    .map(({ el, r }) => `${el.tagName}.${(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,18)} ${Math.round(r.width)}x${Math.round(r.height)}`);
  return small;
});
console.log('small targets @375 (under 32px):', targets.length ? targets.join(' | ') : 'none — PASS');
await b.close();
