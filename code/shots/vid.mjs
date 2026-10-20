// One shot through OpenRouter's video API: the source clip and character sheet as references, the approved
// start and end frames pinned, a prompt that names only what changes. Saves shots/<shot>/out/<model>.mp4 and
// appends model, cost, time and the request (minus media) to shots/<shot>/out/log.json.
//   node shots/vid.mjs <shot> <model> [--no-video] [--no-frames] [--first-only] [--no-refs] [--clean] [--strong] [--slow] [--focus] [--min] [--take n] [--duration 5]
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.dirname(new URL(import.meta.url).pathname);
const [shot, model, ...flags] = process.argv.slice(2);
const flag = (f) => flags.includes(f);
const opt = (f, d) => (flags.includes(f) ? flags[flags.indexOf(f) + 1] : d);
const S = path.join(DIR, shot);
const job = JSON.parse(fs.readFileSync(path.join(S, 'job.json'), 'utf8'));
if (flag('--slow')) Object.assign(job, { video_url: job.video_url_slow, duration: job.duration_slow });
if (flag('--min')) Object.assign(job, { refs: job.refs_min, prompt: job.prompt_min });
if (flag('--focus')) Object.assign(job, { refs: job.refs_focus, prompt: job.prompt_focus });
if (flag('--strong')) Object.assign(job, { refs: job.refs_strong, prompt: job.prompt_strong });
if (flag('--clean')) Object.assign(job, { first: job.first_clean, last: job.last_clean, prompt: job.prompt_clean });
for (const k of ['video_url', 'video_url_slow']) {
  if (job[k]?.includes('${SOURCE_BASE_URL}')) {
    if (!process.env.SOURCE_BASE_URL) throw new Error('set SOURCE_BASE_URL to the HTTPS folder holding <shot>/src-720.mp4 (see .env.example)');
    job[k] = job[k].replace('${SOURCE_BASE_URL}', process.env.SOURCE_BASE_URL.replace(/\/$/, ''));
  }
}
const key = process.env.OPENROUTER_API_KEY;
if (!key) throw new Error('set OPENROUTER_API_KEY (see .env.example)');
const data = (p, mime) => `data:${mime};base64,${fs.readFileSync(path.resolve(S, p)).toString('base64')}`;
const imageRef = (p) => ({ type: 'image_url', image_url: { url: data(p, 'image/png') } });

const body = {
  model,
  prompt: job.prompt,
  duration: Number(opt('--duration', job.duration)),
  resolution: opt('--resolution', job.resolution?.[model] ?? '720p'),
  aspect_ratio: '16:9',
  generate_audio: false,
  ...(flag('--no-refs') ? {} : { input_references: [...(flag('--no-video') ? [] : [{ type: 'video_url', video_url: { url: job.video_url ?? data(job.video, 'video/mp4') } }]), ...job.refs.map(imageRef)] }),
  // --first-only pins the first frame alone (plain i2v, no end frame)
  ...(flag('--no-frames') ? {} : { frame_images: [{ ...imageRef(job.first), frame_type: 'first_frame' }, ...(flag('--first-only') ? [] : [{ ...imageRef(job.last), frame_type: 'last_frame' }])] }),
};
const H = { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' };
const t0 = Date.now();
// --resume <id> picks up a job whose polling dropped, without submitting (and paying for) a new one.
const resume = opt('--resume', '');
const res = resume ? { status: 'resumed' } : await fetch('https://openrouter.ai/api/v1/videos', { method: 'POST', headers: H, body: JSON.stringify(body) });
let job0 = resume ? { id: resume, polling_url: `https://openrouter.ai/api/v1/videos/${resume}`, status: 'pending' } : await res.json();
const short = (o) => JSON.stringify(o, (k, v) => (typeof v === 'string' && v.length > 200 ? v.slice(0, 60) + '...' : v));
console.error(res.status, short(job0));
const id = job0.id ?? job0.data?.id;
let final = job0;
while (id && !['completed', 'failed', 'cancelled', 'succeeded', 'error'].includes(String(final.status ?? final.data?.status).toLowerCase())) {
  await new Promise((r) => setTimeout(r, 10000));
  try { final = await (await fetch(job0.polling_url ?? `https://openrouter.ai/api/v1/videos/${id}`, { headers: H })).json(); } catch (e) { process.stderr.write(`poll failed, retrying: ${e.cause?.code ?? e.message}\n`); }
  process.stderr.write(`${Math.round((Date.now() - t0) / 1000)}s ${final.status ?? final.data?.status}\n`);
}
const url = final.unsigned_urls?.[0] ?? final.data?.unsigned_urls?.[0] ?? final.output?.[0]?.url ?? final.video_url ?? final.url;
const tag = `${model.split('/')[1]}${flag('--no-refs') ? '-framesonly' : ''}${flag('--no-video') ? '-novideo' : ''}${flag('--no-frames') ? '-noframes' : ''}${flag('--first-only') ? '-first' : ''}${flag('--clean') ? '-clean' : ''}${flag('--strong') ? '-strong' : ''}${flag('--slow') ? '-slow' : ''}${flag('--focus') ? '-focus' : ''}${flag('--min') ? '-min' : ''}${opt('--take', '') ? '-' + opt('--take', '') : ''}`;
const row = { shot, model, tag, status: final.status ?? final.data?.status ?? res.status, seconds: (Date.now() - t0) / 1000, cost: final.usage?.cost ?? final.cost ?? null, error: final.error?.message ?? final.error ?? null, prompt: job.prompt, at: new Date().toISOString() };
fs.mkdirSync(path.join(S, 'out'), { recursive: true });
if (url) {
  const r = await fetch(url, { headers: url.includes('openrouter.ai') ? H : {} });
  row.file = `out/${tag}.mp4`;
  fs.writeFileSync(path.join(S, row.file), Buffer.from(await r.arrayBuffer()));
} else console.error(short(final));
const log = path.join(S, 'out/log.json');
fs.writeFileSync(log, JSON.stringify([...(fs.existsSync(log) ? JSON.parse(fs.readFileSync(log, 'utf8')) : []), row], null, 2));
console.log(JSON.stringify({ ...row, prompt: undefined }));
