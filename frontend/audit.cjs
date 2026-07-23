const { chromium } = require('playwright');
const fs = require('fs');

const routes = [
  '/', // Dashboard
  '/runs',
  '/jobs',
  '/jobs?selected=true', // Selected
  '/queues',
  '/queues/manual-review',
  '/queues/external-apply',
  '/queues/other-action', // Rejected / Already Applied might be here
  '/search', // Explorer
  '/analytics', // Metrics
  '/providers', // Providers (will redirect or show 404 since I removed it?) Wait, Providers.tsx is gone, is it in the router?
  '/settings',
  '/artifacts', // Logs
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      errors.push(`[${msg.type()}] ${msg.text()}`);
    }
  });

  page.on('pageerror', error => {
    errors.push(`[uncaught exception] ${error.message}`);
  });
  
  page.on('response', response => {
    if (response.status() >= 400 && response.url().includes('localhost')) {
      errors.push(`[${response.status()}] ${response.url()}`);
    }
  });

  for (const route of routes) {
    console.log(`Checking ${route}...`);
    await page.goto(`http://localhost:5173${route}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500); // give it a moment to render
  }
  
  await browser.close();
  
  if (errors.length > 0) {
    console.error("Errors found:", errors);
    process.exit(1);
  } else {
    console.log("No console errors, warnings, or 404s found across all pages!");
  }
})();
