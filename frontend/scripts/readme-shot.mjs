// PASS 6 — regenerate README-referenced screenshots from FINAL Grid Control implementation.
// Same filenames, same alt semantics; captures current UI (dark = Grid Control default).
import { chromium } from 'playwright';
const BASE = 'http://localhost:5173';
const OUT = '../assets';
const b = await chromium.launch();
const shot = async (file, path, theme = 'dark') => {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await p.goto(BASE + path, { waitUntil: 'networkidle' });
  await p.evaluate(t => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add(t); }, theme);
  await p.waitForTimeout(1200);
  await p.screenshot({ path: `${OUT}/${file}`, fullPage: false });
  await p.close();
  console.log('saved', file);
};
// map README captions to actual final routes
await shot('screenshot_overview.png', '/');          // Overview Dashboard
await shot('screenshot_jobs.png', '/jobs');          // Jobs Workspace
await shot('screenshot_inbox.png', '/applications'); // Inbox / Manual Review (Applications = 02·02 Inbox)
await shot('screenshot_pipeline.png', '/pipeline');  // Pipeline Control
await shot('screenshot_health.png', '/system');      // System Health
await shot('screenshot_analytics.png', '/metrics');  // Pipeline Intelligence & Analytics (Metrics)
await shot('screenshot_search_intel.png', '/intelligence'); // Providers & Search Intelligence
await shot('screenshot_runs.png', '/explorer');      // Pipeline Explorer & Run Inspector
await shot('screenshot_dark_mode.png', '/ledger');   // Dark Mode across pages (Ledger representative)
await b.close();
