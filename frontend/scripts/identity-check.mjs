import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
// light = white diagram ground (schematic print)
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
await p.evaluate(() => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add('light'); });
await p.waitForTimeout(200);
const light = await p.evaluate(() => {
  const bg = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g).map(Number);
  const h1 = document.querySelector('h1');
  const h1Color = h1 ? getComputedStyle(h1).color : null;
  return { bg: bg.slice(0,3), isWhite: bg[0] > 240 && bg[1] > 240 && bg[2] > 240, h1Color };
});
await p.evaluate(() => { const r = document.documentElement; r.classList.remove('light','dark'); r.classList.add('dark'); });
await p.waitForTimeout(200);
const dark = await p.evaluate(() => {
  const bg = getComputedStyle(document.body).backgroundColor.match(/[\d.]+/g).map(Number);
  return { bg: bg.slice(0,3), isCharcoal: bg[0] < 40 && bg[1] < 40 && bg[2] < 40 };
});
console.log('light:', JSON.stringify(light));
console.log('dark:', JSON.stringify(dark));
console.log(`LIGHT=${light.isWhite ? 'SCHEMATIC-PRINT PASS' : 'FAIL'} DARK=${dark.isCharcoal ? 'CONTROL-ROOM PASS' : 'FAIL'}`);
await b.close();
