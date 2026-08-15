// PASS 2 coherence probe — read-only. Route interception only; no backend mutation.
import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const b = await chromium.launch();

const failPage = async (path, routePat, label) => {
  const p = await b.newPage();
  await p.route(routePat, r => r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"probe"}' }));
  const perr = [];
  p.on('pageerror', e => perr.push(String(e)));
  await p.goto(BASE + path, { waitUntil: 'networkidle' });
  await p.waitForTimeout(9000); // retry backoff (1+2+4s) exhausts -> isError
  const alerts = await p.locator('[role="alert"]').count();
  const h1 = await p.locator('h1').first().textContent().catch(() => '');
  console.log(`${label}: alerts=${alerts} h1="${(h1||'').trim().slice(0,40)}" pageerrors=${perr.length}`);
  await p.close();
};

await failPage('/', '**/api/dashboard', 'Overview(dashboard fail)');
await failPage('/', '**/api/runtime', 'Overview(runtime fail)');
await failPage('/providers', '**/api/providers', 'Providers');
await failPage('/ledger', '**/api/ledger/stats', 'Ledger');
await failPage('/ledger', '**/api/ledger/search*', 'Ledger(search)');
await failPage('/jobs', '**/api/jobs', 'Jobs');
await failPage('/applications', '**/api/queues/manual-review', 'Applications(mr)');
await failPage('/runs', '**/api/runs', 'Runs');
await failPage('/explorer', '**/api/artifacts', 'Explorer');
await failPage('/metrics', '**/api/runs', 'Metrics');
await failPage('/pipeline', '**/api/pipeline/state', 'Pipeline');
await b.close();
