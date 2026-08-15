import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
for (const path of ['/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about']) {
  await page.goto('http://localhost:5173' + path, { waitUntil: 'networkidle' });
  await page.evaluate(() => { document.documentElement.className = 'dark'; });
  await page.waitForTimeout(200);
  await page.screenshot({ path: `.impeccable/review/dark-${path.replace('/','').replace('/','-')}.png` });
}
await b.close();
console.log('done');
