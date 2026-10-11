// Renders cuts to MP4 by calling the page's seek(t) once per frame in headless
// Chrome and piping each frame into ffmpeg. Nothing depends on a timer, so the
// render is identical every run.
//
//   node render.mjs --cut 15 --format 9x16 [--fps 30] [--from 0 --to 15]
//   node render.mjs --all
//
// Uses the Chrome already installed (channel "chrome"), so no browser download.

import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FORMATS } from './src/layout.js';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const FPS = Number(arg('fps', 30));
const jobs = process.argv.includes('--all')
  ? ['15', '30', '60'].flatMap((cut) => ['9x16', '4x5', '1x1', '16x9'].map((format) => ({ cut, format })))
  : [{ cut: arg('cut', '15'), format: arg('format', '9x16') }];

if (!existsSync(join(HERE, 'build', 'data.json'))) {
  console.error('no build/; run: python3 docs/video/studio/prepare.py');
  process.exit(1);
}

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json',
                '.png': 'image/png', '.woff2': 'font/woff2' };
const server = createServer((req, res) => {
  const path = normalize(join(HERE, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
  if (!path.startsWith(HERE) || !existsSync(path)) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'content-type': TYPES[extname(path)] || 'application/octet-stream' });
  res.end(readFileSync(path));
}).listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ channel: 'chrome' });
mkdirSync(join(HERE, 'out'), { recursive: true });

for (const { cut, format } of jobs) {
  // The viewport must be the format's own size: the page's preview CSS shrinks the
  // canvas to fit the window, and an element screenshot captures it as displayed.
  const page = await browser.newPage({ viewport: FORMATS[format] && { ...FORMATS[format] }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => { console.error(`page error: ${e.message}`); process.exitCode = 1; });
  await page.goto(`${origin}/index.html?cut=${cut}&format=${format}`);
  await page.evaluate(() => window.ready);
  const { duration, srt, timeline } = await page.evaluate(() => window.studio);
  const from = Number(arg('from', 0));
  const to = Math.min(duration, Number(arg('to', duration)));
  const name = `cut-${cut}-${format}`;
  const out = join(HERE, 'out', `${name}.mp4`);

  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-crf', '16', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const canvas = page.locator('#c');
  const size = await canvas.boundingBox();
  if (Math.round(size.width) !== FORMATS[format].width || Math.round(size.height) !== FORMATS[format].height) {
    throw new Error(`canvas displays at ${size.width}x${size.height}, not ${FORMATS[format].width}x${FORMATS[format].height}`);
  }
  // The cover: frame 0, which a test pins as the hook. LinkedIn uses the first
  // frame as the thumbnail unless a cover is uploaded, so upload this one.
  await page.evaluate(() => window.seek(0));
  await canvas.screenshot({ path: join(HERE, 'out', `${name}-cover.png`) });
  const total = Math.round((to - from) * FPS);
  const started = Date.now();
  for (let i = 0; i < total; i++) {
    await page.evaluate((t) => window.seek(t), from + i / FPS);
    const png = await canvas.screenshot({ type: 'png' });
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  const code = await new Promise((r) => ff.on('close', r));
  if (code !== 0) { console.error(`ffmpeg exited ${code} for ${name}`); process.exitCode = 1; }
  writeFileSync(join(HERE, 'out', `${name}.srt`), srt);
  writeFileSync(join(HERE, 'out', `${name}.timeline.json`), JSON.stringify(timeline, null, 1));
  console.log(`${name}: ${total} frames, ${(to - from).toFixed(2)}s, rendered in ${((Date.now() - started) / 1000).toFixed(0)}s -> out/${name}.mp4`);
  await page.close();
}

await browser.close();
server.close();
