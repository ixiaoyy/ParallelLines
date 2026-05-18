const { chromium } = require('D:/work/ParallelLines/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.screenshot({ path: 'D:/work/ParallelLines/CURRENT_HOME.png', fullPage: true });
  const title = await page.title();
  const text = await page.locator('body').innerText().catch(() => '');
  console.log(JSON.stringify({ title, screenshot: 'D:/work/ParallelLines/CURRENT_HOME.png', text: text.slice(0, 2000) }, null, 2));
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
