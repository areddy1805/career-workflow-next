// PASS 3 — semantic a11y audit across representative routes.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const ROUTES = ['/', '/pipeline', '/jobs', '/applications', '/ledger', '/intelligence', '/metrics', '/copilot/inbox', '/copilot/analytics', '/system'];
let fail = 0;
for (const path of ROUTES) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1200);
  const m = await p.evaluate(() => {
    const issues = [];
    if (!document.querySelector('main')) issues.push('no-main-landmark');
    if (!document.querySelector('h1')) issues.push('no-h1');
    const h1s = document.querySelectorAll('h1').length;
    if (h1s > 1) issues.push(`${h1s}-h1s`);
    // heading order: no h3 before h2, no h2 before h1 etc (hierarchy jumps)
    const heads = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => +h.tagName[1]);
    for (let i = 1; i < heads.length; i++) {
      if (heads[i] - heads[i-1] > 1) { issues.push(`heading-jump h${heads[i-1]}->h${heads[i]}`); break; }
    }
    // buttons must have accessible name
    const unlabeled = [...document.querySelectorAll('button')].filter(btn => {
      const lbl = btn.getAttribute('aria-label') || btn.getAttribute('title') || (btn.textContent||'').trim();
      return !lbl;
    }).length;
    if (unlabeled) issues.push(`${unlabeled}-unlabeled-buttons`);
    // inputs need label
    const unlabeledInputs = [...document.querySelectorAll('input:not([type=hidden])')].filter(i => {
      const id = i.id;
      return !i.getAttribute('aria-label') && !(id && document.querySelector(`label[for="${id}"]`));
    }).length;
    if (unlabeledInputs) issues.push(`${unlabeledInputs}-unlabeled-inputs`);
    // nav landmarks
    const navs = document.querySelectorAll('nav').length;
    return { issues, navs, h1: (document.querySelector('h1')||{}).textContent?.slice(0,30) };
  });
  if (m.issues.length) { fail++; console.log(`FAIL ${path}: ${m.issues.join(', ')} (navs=${m.navs})`); }
  else console.log(`PASS ${path} (navs=${m.navs})`);
}
console.log(fail === 0 ? 'SEMANTIC AUDIT PASS (10 routes)' : `${fail} semantic failures`);
await b.close();
