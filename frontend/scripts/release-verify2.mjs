import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/intelligence', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(2000);
const m = await p.evaluate(() => {
  // find cards with 'Success' label
  const cards = [...document.querySelectorAll('div')].filter(d => {
    const t = d.textContent||'';
    return /Success/.test(t) && /\d+%|—/.test(t) && d.querySelectorAll('div').length > 5 && d.querySelectorAll('div').length < 40;
  });
  return cards.slice(0, 8).map(c => c.textContent.replace(/\s+/g,' ').trim().slice(0, 90));
});
console.log(JSON.stringify(m, null, 1));
await b.close();
