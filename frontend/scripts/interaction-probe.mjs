import { chromium } from 'playwright';
const b = await chromium.launch();
const page = await b.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
// Ledger: row click → sheet opens → Escape closes
await page.goto('http://localhost:5173/ledger', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2000);
await page.locator('tbody tr').first().click();
await page.waitForTimeout(600);
const sheetOpen = await page.locator('[role=dialog]').count();
await page.keyboard.press('Escape');
await page.waitForTimeout(400);
const sheetClosed = await page.locator('[role=dialog]').count();
console.log(`ledger sheet open=${sheetOpen} closed-after-esc=${sheetClosed}`);
// Jobs: select row → detail panel, then JSON dialog
await page.goto('http://localhost:5173/jobs', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
const rows = await page.locator('[role=row]').count();
console.log(`jobs rows=${rows}`);
console.log(`pageerrors=${errors.length}${errors.length ? ' :: ' + errors.join(' | ').slice(0,300) : ''}`);
await b.close();
