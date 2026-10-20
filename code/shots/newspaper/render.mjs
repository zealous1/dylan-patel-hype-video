// Newspaper transition (12.00 to 13.40 s, frame count set by NF in compose.html). Re-run from this folder:  node render.mjs [label]
// FPS=60 node render.mjs paper-v4-60 renders every 60 fps frame from the same camera path, into build/frames-60.
// 1. Pulls the last frame of the locked celebration take.
// 2. Renders paper.html layers at 3840x2160 in headless Chrome (CDP, no npm deps).
// 3. Loads compose.html, which builds each of the 36 frames on a canvas with sub-frame motion blur.
// 4. Encodes out/<label>.mp4 (1920x1080, 30 fps, no audio) and out/page.png.
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const R = path.resolve(HERE, '../..');
const FONTS = path.resolve(R, process.env.FONT_DIR || 'fonts');
const BUILD = path.join(HERE, 'build');
const OUT = path.join(HERE, 'out');
const LABEL = process.argv[2] || 'paper';
const ONLY = process.env.ONLY_FRAMES; // e.g. "0,1,20" for quick looks
const FPS = Number(process.env.FPS || 30);
const CHROME = process.env.CHROME_BIN ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sh = (cmd, args) => execFileSync(cmd, args, { stdio: ['ignore', 'pipe', 'inherit'] });

await mkdir(path.join(BUILD, 'layers'), { recursive: true });
await mkdir(OUT, { recursive: true });

// 1. Celebration hand-off frame (35 frames, last index 34). CELEBRATE=<path from R> swaps the source, e.g. an upscaled take.
sh('ffmpeg', ['-v', 'error', '-y', '-i', path.join(R, process.env.CELEBRATE || 'shots/celebrate/out/min-realtime.mp4'),
  '-vf', "select='eq(n,34)'", '-vframes', '1', path.join(BUILD, 'celebrate-last.png')]);

// Static server rooted at R so the canvas never gets tainted.
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.png': 'image/png', '.json': 'application/json', '.jpg': 'image/jpeg' };
const server = createServer(async (req, res) => {
  const u = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const p = u.startsWith('/fonts/') ? path.join(FONTS, u.slice(7)) : path.join(R, u);
  if (!p.startsWith(R) && !p.startsWith(FONTS)) { res.writeHead(403).end(); return; }
  try { const b = await readFile(p); res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream', 'cache-control': 'no-store' }).end(b); }
  catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}/shots/newspaper`;

// Chrome over the DevTools protocol.
const profile = path.join(BUILD, 'chrome-profile');
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  '--hide-scrollbars', '--force-color-profile=srgb', '--disable-gpu-vsync', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
const wsUrl = await new Promise((res, rej) => {
  let buf = '';
  chrome.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) res(m[1]); });
  chrome.on('exit', () => rej(new Error('chrome exited: ' + buf)));
});
const targets = await (await fetch(wsUrl.replace('ws://', 'http://').replace(/\/devtools\/.*/, '/json'))).json();
const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let seq = 0; const pending = new Map(); const waiters = [];
ws.addEventListener('message', e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  else if (m.method) {
    if (m.method === 'Runtime.consoleAPICalled') console.log('[page]', m.params.args.map(a => a.value ?? a.description).join(' '));
    if (m.method === 'Runtime.exceptionThrown') console.log('[page error]', JSON.stringify(m.params.exceptionDetails).slice(0, 500));
    if (m.method === 'Inspector.targetCrashed') { console.log('[page crashed]'); process.exit(1); }
    for (const w of waiters.splice(0)) w(m);
  }
});
const send = (method, params = {}) => new Promise((res, rej) => { const id = ++seq; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
};
// Big strings come back in 1 MB slices; one multi-MB CDP reply stalls the socket.
const fetchBig = async expr => {
  const len = await evaluate(`(window.__big = ${expr}).length`);
  let s = ''; for (let i = 0; i < len; i += 1 << 20) s += await evaluate(`window.__big.slice(${i}, ${i + (1 << 20)})`);
  return s;
};
const loadPage = async url => {
  await send('Page.enable');
  const loaded = new Promise(r => { const w = m => m.method === 'Page.loadEventFired' ? r() : waiters.push(w); waiters.push(w); });
  await send('Page.navigate', { url }); await loaded;
};

await send('Runtime.enable'); await send('Inspector.enable');
// 2. Layers.
await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 2, mobile: false });
await send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
const shot = async (query, file) => {
  await loadPage(`${BASE}/paper.html?${query}`);
  const layout = await evaluate('window.layout()');
  // Four strips, stitched: a full 3840x2160 capture with a detailed photo is a multi-MB reply that stalls the socket.
  const strips = [];
  for (let i = 0; i < 4; i++) {
    const { data } = await send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: i * 270, width: 1920, height: 270, scale: 1 } });
    strips.push(path.join(BUILD, 'layers', `strip${i}.png`)); await writeFile(strips[i], Buffer.from(data, 'base64'));
  }
  sh('ffmpeg', ['-v', 'error', '-y', ...strips.flatMap(s => ['-i', s]), '-filter_complex', 'vstack=inputs=4', '-pix_fmt', 'rgba',
    path.join(BUILD, 'layers', file)]);
  await Promise.all(strips.map(s => rm(s)));
  return layout;
};
const layout = {
  main: await shot('body=no-banner,no-photo', 'main.png'),
  banner: await shot('body=layer-banner', 'banner.png'),
  full: await shot('', 'full.png'),
  blitz: await shot('v=blitz', 'blitz.png'),
  billy: await shot('v=billy', 'billy.png'),
  ding: await shot('v=ding', 'ding.png'),
};
// The left column again at 4x, sharp enough for the punch-ins on its headlines.
await loadPage(`${BASE}/paper.html?body=no-banner,no-photo`); await evaluate('window.layout()');
{ const { data } = await send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 190, width: 400, height: 890, scale: 2 } });
  await writeFile(path.join(BUILD, 'layers', 'leftcol4x.png'), Buffer.from(data, 'base64')); }
await writeFile(path.join(BUILD, 'layout.json'), JSON.stringify(layout, null, 1));
sh('cp', [path.join(BUILD, 'layers/full.png'), path.join(OUT, 'page.png')]);

// 3. Frames.
await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await loadPage(`${BASE}/compose.html?fps=${FPS}`);
if (process.env.DEBUG) await evaluate('window.DEBUG = 1'); await evaluate('window.ready');
const NF = await evaluate('window.NF');
if (process.env.OVERVIEW) { // debug: world map with camera frames, e.g. OVERVIEW=1,11,21,27,33
  const u = await fetchBig(`window.overview([${process.env.OVERVIEW}])`);
  await writeFile(path.join(BUILD, 'overview.png'), Buffer.from(u.split(',')[1], 'base64'));
}
const FR = path.join(BUILD, FPS === 30 ? 'frames' : `frames-${FPS}`);
if (!ONLY) await rm(FR, { recursive: true, force: true });
await mkdir(FR, { recursive: true });
const list = ONLY ? ONLY.split(',').map(Number) : [...Array(NF).keys()];
for (const k of list) {
  const T0 = Date.now(); const url = await fetchBig(`window.renderFrame(${k})`);
  await writeFile(path.join(FR, `f${String(k).padStart(3, '0')}.png`), Buffer.from(url.split(',')[1], 'base64'));
  process.stdout.write(`${k}:${((Date.now() - T0) / 1000).toFixed(1)}s `);
}
console.log();
ws.close(); chrome.kill(); server.close();

// 4. Encode. Untagged, ffmpeg default matrix, same as the celebration take, so the seam decodes alike.
if (!ONLY) {
  sh('ffmpeg', ['-v', 'error', '-y', '-framerate', String(FPS), '-i', path.join(FR, 'f%03d.png'), '-frames:v', String(NF),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', path.join(OUT, `${LABEL}.mp4`)]);
  console.log('wrote', path.join(OUT, `${LABEL}.mp4`));
}
