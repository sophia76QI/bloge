// Usage: node render.js out.png   (serve repo root: python3 -m http.server 8766)
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: Number(process.argv[3] || 2) });
  p.on('pageerror', e => console.error('pageerror', e.message));
  p.on('console', m => { if (m.type() === 'error') console.error('console', m.text()); });
  await p.goto('http://localhost:8766/livingroom/index.html');
  await p.waitForFunction(() => window.READY === true, null, { timeout: 180000 });
  await p.waitForTimeout(800);
  await p.locator('#poster').screenshot({ path: process.argv[2] });
  await b.close();
})();
