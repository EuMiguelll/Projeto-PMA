import { chromium } from 'playwright';
import path from 'node:path';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + path.resolve('slides.html'), { waitUntil: 'networkidle' });
await page.evaluate(() => { document.fonts.ready; document.getElementById('hpa-title').remove(); });
await page.pdf({ path: 'out/slides.pdf', width: '1920px', height: '1080px', printBackground: true });
await browser.close();
