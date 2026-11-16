import { chromium } from 'playwright';
import path from 'node:path';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + path.resolve('slides.html'), { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
for (const id of await page.$$eval('section', els => els.map(e => e.id))) {
  const el = await page.$('#' + id);
  const isOverlay = id.startsWith('lt-') || id.startsWith('sp-');
  if (isOverlay) await page.evaluate(() => document.body.style.background = 'transparent');
  await el.screenshot({ path: `slides/${id}.png`, omitBackground: isOverlay });
  if (isOverlay) await page.evaluate(() => document.body.style.background = '#000');
}
await browser.close();
