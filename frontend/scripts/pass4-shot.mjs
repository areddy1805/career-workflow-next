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
const routes = [['overview','/'],['pipeline','/pipeline'],['runs','/runs'],['jobs','/jobs'],['apps','/applications'],
  ['inbox','/copilot/inbox'],['ledger','/ledger'],['intelligence','/intelligence'],['explorer','/explorer'],
  ['metrics','/metrics'],['providers','/providers'],['system','/system'],['settings','/copilot/settings'],['about','/about']];
for (const [name, path] of routes) {
  await shot(`pass4-${name}-dark.png`, path, 1440, 900, 'dark');
  await shot(`pass4-${name}-light.png`, path, 1440, 900, 'light');
}
await shot('pass4-overview-mobile-dark.png', '/', 375, 812, 'dark');
await shot('pass4-overview-mobile-light.png', '/', 375, 812, 'light');
await shot('pass4-jobs-mobile-dark.png', '/jobs', 375, 812, 'dark');
await b.close();
