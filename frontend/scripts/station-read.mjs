import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const m = await p.evaluate(() => {
  // StationTopology: stations have data-state svgs in a strip; grab the strip region
  const strip = document.querySelector('[aria-label*="topology" i], [aria-label*="Topology" i]');
  const svgStates = [...document.querySelectorAll('svg[data-state]')].map(s => s.getAttribute('data-state'));
  // Find container with 8+ markers (the topology strip)
  const containers = [...document.querySelectorAll('div')].map(d => {
    const marks = d.querySelectorAll('svg[data-state]');
    return { c: d, n: marks.length };
  }).filter(x => x.n >= 8).sort((a,b) => b.n - a.n).slice(0, 2);
  const detail = containers.map(({ c, n }) => {
    const text = (c.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120);
    const marks = [...c.querySelectorAll('svg[data-state]')].map(s => s.getAttribute('data-state'));
    return { n, text, marks };
  });
  return { strip: !!strip, detail };
});
console.log(JSON.stringify(m, null, 1));
await b.close();
