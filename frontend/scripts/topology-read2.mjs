import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const m = await p.evaluate(() => {
  const strip = [...document.querySelectorAll('div')].find(d => /topology/i.test(d.className + ' ' + (d.getAttribute('aria-label')||'')));
  const labels = [...document.querySelectorAll('span')].filter(s => /^(preflight|acquisition|classification|selection|application|reconciliation|strategy|report)$/i.test((s.textContent||'').trim())).map(s => s.textContent.trim());
  const allSmall = [...document.querySelectorAll('span')].map(s => s.textContent.trim()).filter(t => /preflight|acquisition|classification|selection|reconciliation|strategy/i.test(t));
  return { labels: labels.slice(0,10), allSmall: allSmall.slice(0,10) };
});
console.log(JSON.stringify(m, null, 1));
await b.close();
