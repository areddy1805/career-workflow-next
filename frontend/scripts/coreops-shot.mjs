import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
for (const path of ['/pipeline', '/runs', '/applications', '/jobs']) {
  for (const [label, cls] of [['dark', 'dark'], ['light', 'light']]) {
    await page.goto('http://localhost:5173' + path, { waitUntil: 'networkidle' });
    await page.evaluate(c => { document.documentElement.className = c; }, cls);
    await page.waitForTimeout(250);
    await page.screenshot({ path: `.impeccable/review/${label}-${path.replace('/','').replace('/','-')}.png` });
  }
}
await b.close();
console.log('shots done');
