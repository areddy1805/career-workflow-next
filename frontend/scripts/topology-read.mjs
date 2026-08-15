import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const m = await p.evaluate(() => {
  const svgs = document.querySelectorAll('svg[data-state]');
  const states = [...svgs].map(s => s.getAttribute('data-state'));
  const markers = [...document.querySelectorAll('[data-state]')].map(s => s.getAttribute('data-state'));
  // topology labels
  const stationLabels = [...document.querySelectorAll('span')].filter(s => /preflight|acquisition|classification|selection|application|reconciliation|strategy|report/i.test(s.textContent || '')).map(s => s.textContent.trim());
  return { svgStates: states.slice(0, 10), stationLabels: stationLabels.slice(0, 10), totalMarkers: markers.length };
});
console.log(JSON.stringify(m, null, 1));
await b.close();
