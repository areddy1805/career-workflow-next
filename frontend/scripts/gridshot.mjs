import { chromium } from 'playwright';
const BASE = 'http://localhost:5173';
const OUT = '../.impeccable/review';
const browser = await chromium.launch();
const shot = async (file, w, h, theme) => {
  const p = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: theme });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.evaluate((t) => {
    const r = document.documentElement; r.classList.remove('light', 'dark'); r.classList.add(t);
  }, theme);
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${OUT}/${file}`, fullPage: true });
  await p.close();
  console.log('saved', file);
};
await shot('desktop.png', 1440, 900, 'dark');
await shot('desktop-light.png', 1440, 900, 'light');
await shot('mobile.png', 375, 812, 'dark');
await shot('mobile-light.png', 375, 812, 'light');
await browser.close();
