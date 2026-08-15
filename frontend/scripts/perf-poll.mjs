// AUDIT 12 — Overview request load over 30s (polling patterns, accidental repeats).
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const reqs = [];
p.on('request', r => { if (r.url().includes('/api/')) reqs.push(r.url().split(':5173')[1].split('?')[0]); });
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(30000);
const byPath = {};
reqs.forEach(u => { byPath[u] = (byPath[u]||0)+1; });
console.log('Overview /api requests over 30s:');
for (const [u, n] of Object.entries(byPath).sort((a,b)=>b[1]-a[1])) console.log(`  ${String(n).padStart(3)} ${u}`);
console.log('total:', reqs.length);
await b.close();
