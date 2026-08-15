// PASS 3 — state must never be color alone. Verify StateMarker (svg glyph + label) 
// used at status sites; scan for color-only dots/chips without adjacent text.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer',
  '/metrics', '/providers', '/system', '/logs', '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning'];
let fail = 0;
for (const path of ROUTES) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1300);
  const m = await p.evaluate(() => {
    const issues = [];
    // 1. colored round dots (status-dot pattern) — must have adjacent text or aria-label
    const dots = [...document.querySelectorAll('span')].filter(s => {
      const cls = s.className || '';
      return /(w-2|w-1\.5|h-2|h-1\.5).*rounded-full/.test(cls) && /bg-(healthy|failed|degraded|running|pending|blocked|manual|terminal)/.test(cls);
    });
    for (const d of dots) {
      const hasLabel = d.getAttribute('aria-label') || (d.parentElement?.textContent || '').trim().length > 0;
      if (!hasLabel) issues.push('color-dot-no-text');
    }
    // 2. StateMarker svg present where status exists
    const markers = document.querySelectorAll('svg[data-state]').length;
    // 3. colored text spans used as status without sibling label — sample check
    const statusTexts = [...document.querySelectorAll('span')].filter(s => {
      const cls = s.className || '';
      return /text-(healthy|failed|degraded|running|pending)/.test(cls) && !/font-mono/.test(cls);
    });
    for (const t of statusTexts.slice(0, 20)) {
      const txt = (t.textContent || '').trim();
      // text itself is the label — hue confirms. Only flag when text is empty/whitespace.
      if (!txt) issues.push('color-only-empty-text');
    }
    return { markers, issues, dots: dots.length };
  });
  if (m.issues.length) { fail++; console.log(`FAIL ${path}: ${m.issues.join(',')} markers=${m.markers}`); }
  else console.log(`PASS ${path} markers=${m.markers}`);
}
console.log(fail === 0 ? 'STATE-COLOR AUDIT PASS (16 routes)' : `${fail} state-color failures`);
await b.close();
