import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
for (const path of ['/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings']) {
  await page.goto('http://localhost:5173' + path, { waitUntil: 'networkidle' });
  await page.evaluate(() => { document.documentElement.className = 'dark'; });
  await page.waitForTimeout(250);
  await page.screenshot({ path: `.impeccable/review/dark-${path.replace('/copilot/','copilot-')}.png` });
}
await b.close();
console.log('copilot shots done');
