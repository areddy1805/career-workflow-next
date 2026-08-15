import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/providers', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1800);
const m = await p.evaluate(() => {
  const cards = [...document.querySelectorAll('div')].filter(d => /Queries|Latency|Success/.test(d.textContent||'') && d.querySelectorAll('div').length < 30 && d.children.length > 3);
  return cards.slice(0, 6).map(c => c.textContent.replace(/\s+/g,' ').trim().slice(0, 100));
});
console.log(JSON.stringify(m, null, 1));
await b.close();
