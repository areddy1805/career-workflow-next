// PASS 3 — motion: reduced-motion kills animation; live polling doesn't re-trigger animations.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ reducedMotion: 'reduce' });
await p.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1500);
const m = await p.evaluate(() => {
  const all = [...document.querySelectorAll('*')];
  const animated = all.filter(el => {
    const s = getComputedStyle(el);
    const d = parseFloat(s.animationDuration) || 0;
    return d > 0.01 && s.animationName !== 'none';
  }).map(el => `${el.tagName}.${String(el.className).slice(0,30)} ${getComputedStyle(el).animationName} ${getComputedStyle(el).animationDuration}`);
  return { animated: animated.slice(0, 6), count: animated.length };
});
console.log(`reduced-motion: animated elements=${m.count} ${m.animated.join(' | ') || '(none — PASS)'}`);

// polling thrash: measure DOM mutation count over a 6s window on Overview (5s polls)
const p2 = await b.newPage();
await p2.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded' });
await p2.waitForTimeout(2000);
const mutations = await p2.evaluate(() => new Promise(resolve => {
  let count = 0;
  const obs = new MutationObserver(muts => { count += muts.length; });
  obs.observe(document.body, { subtree: true, childList: true, attributes: true });
  setTimeout(() => { obs.disconnect(); resolve(count); }, 6000);
}));
console.log(`Overview DOM mutations over 6s: ${mutations}`);
await b.close();
