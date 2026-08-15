import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const m = await p.evaluate(() => {
  const markers = [...document.querySelectorAll('[data-state]')];
  const labels = markers.map(s => s.textContent?.trim()).filter(Boolean);
  return { count: markers.length, labels: labels.slice(0, 20), html: markers[0]?.parentElement?.parentElement?.outerHTML?.slice(0, 300) };
});
console.log(JSON.stringify(m, null, 1));
await b.close();
