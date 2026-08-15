// PASS 5 — network audit: capture all requests across all routes, classify READ/WRITE.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const requests = [];
p.on('request', r => {
  const m = r.method();
  const url = r.url();
  if (url.includes('/api/') || url.includes(':5173/api')) {
    requests.push({ method: m, path: url.split(':5173')[1]?.split('?')[0] || url.split('/api/')[1], });
  }
});
const ROUTES = ['/', '/pipeline', '/runs', '/jobs', '/applications', '/ledger', '/intelligence', '/explorer',
  '/metrics', '/providers', '/system', '/logs', '/audit', '/developer', '/config', '/about',
  '/copilot/inbox', '/copilot/history', '/copilot/analytics', '/copilot/learning', '/copilot/settings'];
for (const path of ROUTES) {
  await p.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(1400);
}
// classify
const byMethod = {};
const writePaths = new Set();
const readPaths = new Set();
for (const r of requests) {
  const m = r.method;
  byMethod[m] = (byMethod[m] || 0) + 1;
  if (['POST','PUT','PATCH','DELETE'].includes(m)) writePaths.add(r.path);
  else readPaths.add(r.path);
}
console.log('=== METHOD COUNTS ===');
console.log(JSON.stringify(byMethod, null, 1));
console.log('=== WRITE (POST/PUT/PATCH/DELETE) paths hit during pure route smoke ===');
console.log([...writePaths].join('\n') || '(none)');
console.log('=== total API requests:', requests.length);
await b.close();
