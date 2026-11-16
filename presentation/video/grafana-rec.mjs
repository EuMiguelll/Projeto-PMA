import { chromium } from 'playwright';
const out = process.argv[2] || 'clips';
const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  recordVideo: { dir: out, size: { width: 1920, height: 1080 } },
});
const page = await ctx.newPage();
await ctx.request.post('http://localhost:3000/login', { data: { user: 'admin', password: process.env.GF_PASS || 'admin' } }); // Grafana local do compose
await page.goto('http://localhost:3000/d/store-bottlenecks/?orgId=1&from=now-5m&to=now&refresh=5s&kiosk', { waitUntil: 'networkidle' });
await page.waitForTimeout(25000);
await page.screenshot({ path: `${out}/grafana.png` });
await ctx.close();
await browser.close();
