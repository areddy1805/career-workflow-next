// AUDIT 3/5/6 re-verify after fixes: Intelligence + Providers honest dashes; Logs/Audit retry buttons.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/intelligence', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1800);
const intel = await p.evaluate(() => {
  // acquisition_boundary card should show — (em dash) not 0% / 0.00s
  const cards = [...document.querySelectorAll('div')].filter(d => /acquisition_boundary/i.test(d.textContent||''));
  const boundaryCard = cards.find(d => d.querySelector('[class*="rounded-md border"]') || d.children.length > 10);
  return boundaryCard ? boundaryCard.textContent.slice(0, 200) : 'no-boundary-card';
});
console.log('intelligence boundary card:', intel.replace(/\s+/g,' ').slice(0,160));
await p.goto('http://localhost:5173/providers', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const prov = await p.evaluate(() => {
  const t = document.body.textContent;
  const boundary = t.includes('Acquisition Boundary');
  const zeroMs = /\b0ms\b/.test(t);
  return { boundary, zeroMs };
});
console.log('providers:', JSON.stringify(prov));
await p.goto('http://localhost:5173/logs', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
console.log('logs page renders:', await p.evaluate(() => !!document.querySelector('h1')));
await b.close();
