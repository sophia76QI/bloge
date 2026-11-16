// Usage: node render.js <outDir> <fps> [workers] [t1,t2,...]
// Serve this folder first: python3 -m http.server 8765
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const outDir = process.argv[2] || 'frames';
const fps = Number(process.argv[3] || 30);
const workers = Number(process.argv[4] || 4);
const only = process.argv[5] ? process.argv[5].split(',').map(Number) : null;
const DURATION = 27;
fs.mkdirSync(outDir, { recursive: true });

const times = only || Array.from({ length: Math.round(DURATION * fps) }, (_, i) => i / fps);

async function worker(idx) {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('pageerror', e.message));
  await page.goto('http://localhost:8765/index.html');
  await page.waitForFunction(() => window.READY === true, null, { timeout: 120000 });
  for (let i = idx; i < times.length; i += workers) {
    const t = times[i];
    await page.evaluate(t => window.renderFrame(t), t);
    const name = only ? `t_${t.toFixed(2)}.jpg` : `f_${String(i).padStart(4, '0')}.jpg`;
    await page.screenshot({ path: path.join(outDir, name), type: 'jpeg', quality: 92 });
    if (!only && i % 60 === 0) console.log(`frame ${i}/${times.length}`);
  }
  await browser.close();
}

(async () => {
  const t0 = Date.now();
  await Promise.all(Array.from({ length: Math.min(workers, times.length) }, (_, i) => worker(i)));
  console.log(`done ${times.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
})();
