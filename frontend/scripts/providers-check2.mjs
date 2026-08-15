import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/providers', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1800);
const m = await p.evaluate(() => {
  const cards = [...document.querySelectorAll('[class*="bg-surface"][class*="border"]')].filter(d => {
    const t = d.textContent||'';
    return /Google|Indeed|LinkedIn|Naukri|Boundary|Glassdoor|ZipRecruiter/.test(t) && t.length < 400;
  });
  return cards.slice(0, 8).map(c => c.textContent.replace(/\s+/g,' ').trim().slice(0, 130));
});
console.log(JSON.stringify(m, null, 1));
await b.close();
