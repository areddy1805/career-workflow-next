import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer',
  '/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about',
  '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings'];
let totalIssues = 0;
for (const path of ROUTES) {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  const issues = await page.evaluate(() => {
    const out = [];
    // buttons/links with no accessible name
    document.querySelectorAll('button, a').forEach(el => {
      const aria = el.getAttribute('aria-label');
      const title = el.getAttribute('title');
      const text = (el.textContent || '').trim();
      const isIcon = el.querySelector('svg') && !text;
      if (isIcon && !aria && !title) {
        out.push(`icon-control: ${el.tagName}${el.className ? ' .' + String(el.className).split(' ')[0] : ''}`);
      }
    });
    // inputs without label/aria
    document.querySelectorAll('input').forEach(el => {
      const id = el.id;
      const labeled = el.getAttribute('aria-label') || (id && document.querySelector(`label[for="${id}"]`));
      if (!labeled) out.push(`unlabeled-input: ${el.type || 'text'}`);
    });
    // multiple h1
    const h1s = document.querySelectorAll('h1').length;
    if (h1s > 1) out.push(`multi-h1: ${h1s}`);
    return out;
  });
  if (issues.length) {
    totalIssues += issues.length;
    console.log(`${path}: ${issues.slice(0, 6).join(' | ')}${issues.length > 6 ? ` +${issues.length - 6}` : ''}`);
  }
}
console.log(totalIssues === 0 ? 'A11Y SCAN PASS — no unlabeled controls' : `${totalIssues} issues`);
await b.close();
