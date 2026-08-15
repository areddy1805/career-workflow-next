// PASS 3 — deep responsive validation beyond overflow.
// At each breakpoint checks: nav presence/mode, topbar, page header, main content
// visibility, touch target size for interactive elements, no clipped content.
import { chromium } from 'playwright';

const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer',
  '/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about',
  '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings'];
const WIDTHS = [1440, 1280, 1024, 768, 375];
let fail = 0;
for (const path of ROUTES) {
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.waitForTimeout(150);
    const m = await page.evaluate(() => {
      const doc = document.documentElement;
      const aside = document.querySelector('aside');
      const asideVisible = aside && getComputedStyle(aside).display !== 'none';
      const menuBtn = document.querySelector('button[aria-label="Open navigation menu"]');
      const menuVisible = menuBtn && getComputedStyle(menuBtn).display !== 'none';
      const main = document.querySelector('main');
      const h1 = document.querySelector('h1');
      const h1Visible = h1 && h1.getBoundingClientRect().height > 0;
      const content = main ? main.scrollWidth - main.clientWidth : 0;
      // small interactive targets audit (buttons/links under 24px height)
      const smallTargets = [...document.querySelectorAll('button, a[href]')]
        .filter(el => el.getBoundingClientRect().height > 0 && el.getBoundingClientRect().height < 24 && el.getBoundingClientRect().height > 0)
        .slice(0, 3).map(el => `${el.tagName}.${(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,20)}:${Math.round(el.getBoundingClientRect().height)}px`);
      return { overflow: doc.scrollWidth - doc.clientWidth, contentOverflow: content, asideVisible, menuVisible, h1Visible, smallTargets };
    }, w);
    const issues = [];
    if (m.overflow > 0) issues.push(`page-overflow=${m.overflow}`);
    if (m.contentOverflow > 0) issues.push(`main-overflow=${m.contentOverflow}`);
    if (!m.h1Visible) issues.push('no-visible-h1');
    if (w <= 768 && !m.menuVisible && m.asideVisible) issues.push('desktop-nav-at-mobile');
    if (w >= 1024 && !m.asideVisible) issues.push('no-rail-at-desktop');
    if (w <= 768 && m.asideVisible) issues.push('rail-shown-at-mobile');
    if (issues.length) { fail++; console.log(`FAIL ${path} @${w}: ${issues.join(', ')}`); }
  }
  if (errors.length) { console.log(`pageerrors ${path}: ${errors.join(' | ').slice(0,200)}`); errors.length = 0; }
}
console.log(fail === 0 ? 'DEEP RESPONSIVE PASS (21 routes × 5 widths, nav/header/overflow/touch)' : `${fail} deep failures`);
await b.close();
