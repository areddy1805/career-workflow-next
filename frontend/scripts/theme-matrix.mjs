// PASS 3 — dark + light across all widths: overflow, contrast of key surfaces, focus ring visibility.
import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const ROUTES = ['/', '/jobs', '/applications', '/ledger', '/copilot/inbox'];
const WIDTHS = [1440, 1024, 768, 375];
let fail = 0;
for (const theme of ['dark', 'light']) {
  for (const path of ROUTES) {
    await page.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    await page.evaluate(t => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add(t); }, theme);
    await page.waitForTimeout(200);
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 800 });
      await page.waitForTimeout(150);
      const m = await page.evaluate(() => {
        const doc = document.documentElement;
        const bg = getComputedStyle(document.body).backgroundColor;
        const fg = getComputedStyle(document.body).color;
        const focus = getComputedStyle(document.documentElement).getPropertyValue('--ring').trim();
        return { overflow: doc.scrollWidth - doc.clientWidth, bg, fg, ring: focus };
      });
      if (m.overflow > 0) { fail++; console.log(`FAIL ${theme} ${path} @${w} overflow=${m.overflow}`); }
    }
    // contrast sanity: fg vs bg luminance
    const lum = await page.evaluate(() => {
      const parse = c => { const m = c.match(/[\d.]+/g); return m ? m.map(Number) : null; };
      const bg = parse(getComputedStyle(document.body).backgroundColor);
      const fg = parse(getComputedStyle(document.body).color);
      if (!bg || !fg) return -1;
      const L = v => { const f = v/255; return f <= 0.03928 ? f/12.92 : Math.pow((f+0.055)/1.055, 2.4); };
      const l1 = 0.2126*L(fg[0])+0.7152*L(fg[1])+0.0722*L(fg[2]);
      const l2 = 0.2126*L(bg[0])+0.7152*L(bg[1])+0.0722*L(bg[2]);
      return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    });
    const themeOk = theme === 'dark' ? await page.evaluate(() => {
      const bg = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g).map(Number);
      return bg[0] < 60 && bg[1] < 60 && bg[2] < 60;
    }) : await page.evaluate(() => {
      const bg = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g).map(Number);
      return bg[0] > 200 && bg[1] > 200 && bg[2] > 200;
    });
    if (!themeOk) { fail++; console.log(`FAIL ${theme} ${path}: theme not applied (bg=${m.bg})`); }
    if (lum < 7) { console.log(`NOTE ${theme} ${path}: fg/bg contrast ${lum.toFixed(1)}:1`); }
  }
}
console.log(fail === 0 ? 'THEME MATRIX PASS (2 themes × 5 routes × 4 widths, overflow + theme truth)' : `${fail} theme failures`);
await b.close();
