import { chromium } from 'playwright';
const BASE = 'http://localhost:5173';
const OUT = '../.impeccable/review';
const b = await chromium.launch();
const shot = async (file, path, w, h, theme) => {
  const p = await b.newPage({ viewport: { width: w, height: h }, colorScheme: theme });
  await p.goto(BASE + path, { waitUntil: 'networkidle' });
  await p.evaluate(t => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add(t); }, theme);
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${OUT}/${file}`, fullPage: true });
  await p.close();
  console.log('saved', file);
};
await shot('pass3-jobs-mobile.png', '/jobs', 375, 812, 'dark');
await shot('pass3-inbox-mobile.png', '/applications', 375, 812, 'dark');
await shot('pass3-overview-light.png', '/', 1440, 900, 'light');
await shot('pass3-pipeline.png', '/pipeline', 1440, 900, 'dark');
await shot('pass3-ledger-mobile.png', '/ledger', 375, 812, 'dark');
await b.close();
