import { chromium } from 'playwright';
const b = await chromium.launch();
for (const [path, pat] of [['/logs', '**/api/logs/pipeline*'], ['/audit', '**/api/audit/pipeline']]) {
  const p2 = await b.newPage();
  await p2.route(pat, r => r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"probe"}' }));
  await p2.goto(`http://localhost:5173${path}`, { waitUntil: 'domcontentloaded' });
  await p2.waitForTimeout(9000);
  const alert = p2.locator('[role="alert"]');
  const n = await alert.count();
  const retry = n ? await alert.locator('button').count() : 0;
  console.log(`${path}: alert=${n} retryBtn=${retry} ${n===1 && retry===1 ? 'PASS' : 'FAIL'}`);
  await p2.close();
}
await b.close();
