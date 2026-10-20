// Image edits through OpenRouter for the Dylan reel: the character sheet, then one start frame per swapped shot.
// Each job sends its input images plus a prompt and saves the first image returned to starts/out/<name>.png,
// logging model, cost and time to starts/out/log.json. The key comes from
// OPENROUTER_API_KEY in the environment.
//   MODEL=google/gemini-nano-banana-2.1 node starts/gen.mjs sheet   # the comparison model
//   node starts/gen.mjs sheet            # character sheet from refs/dylan
//   node starts/gen.mjs frames [names]   # the reel's start and end frames (REEL below), or only the named ones
//   node starts/gen.mjs frames dcplate   # after step 5: the clean plate that paints out the datacenter sign
//   node starts/gen.mjs frames cel1jersey cel2money cel3face   # the celebration, one edit per step
//   OUT=shots/opener/broadcast/img-1 node starts/gen.mjs frames bcintro bclogo   # the broadcast player-intro opener
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.dirname(new URL(import.meta.url).pathname);
// OUT=<dir> sends one run's downloads (and its log) to a fresh folder
const OUT = process.env.OUT ? path.resolve(process.env.OUT) : path.join(DIR, 'out');
const MODEL = process.env.MODEL ?? 'openai/gpt-image-2.5-sunburst';
const key = process.env.OPENROUTER_API_KEY;
if (!key) throw new Error('set OPENROUTER_API_KEY (see .env.example)');
const SUFFIX = '-' + MODEL.split('/')[1];
const img = (p) => ({ type: 'image_url', image_url: { url: `data:image/png;base64,${fs.readFileSync(path.join(DIR, p.replace('{m}', SUFFIX))).toString('base64')}` } });

const DYLAN = 'Dylan Patel: a South Asian man in his late twenties, short dark hair, trimmed beard, slim build';
const SHEET = 'out/sheet{m}.png';
const JERSEY = 'a yellow basketball home jersey with purple trim, the SemiAnalysis wordmark across the chest in purple and the number 67 below it in purple, matching purple shorts';
const HEADSHOTS = ['../refs/dylan/headshot-suit.png', '../refs/dylan/headshot-smile.png', '../refs/dylan/crops/front-a.png', '../refs/dylan/crops/threequarter-a.png'].filter((p) => fs.existsSync(path.join(DIR, p)));
const JOBS = {
  sheet: {
    inputs: HEADSHOTS,
    prompt: `Character reference sheet of the man in these photos (${DYLAN}). One wide image on a plain light grey background with six views in a row, evenly spaced, each fully inside its own panel with margin on every side: front face close-up; side profile face close-up facing left, the whole head in frame with clear empty space in front of the nose and chin, nothing cropped; back of the head; three-quarter view from the waist up; full-body standing view from the front, head to shoes; full-body standing view from directly behind, head to shoes, showing PATEL above a large 67 on the back of the jersey. Exactly the same face, hairline, beard and skin tone as the photos in every view, photoreal, even studio light. He wears ${JERSEY}; the back of the jersey reads PATEL and 67 in purple. No text labels.`,
  },
  wide: {
    inputs: ['src/lebron-3.0.png', SHEET],
    prompt: `Edit the first image only: replace the player in the yellow number 6 jersey dribbling at the top of the key with the man from the character sheet (second image), same pose, same size, same jersey with the number changed to 67. Change the scorebug banner text to "DYLAN PATEL · GW TO BREAK COMPUTE RECORD". Keep every other player, the crowd, the court and the broadcast graphics exactly as they are.`,
  },
  backdown: {
    inputs: ['src/lebron-7.0.png', SHEET],
    prompt: 'Edit the first image only: replace the player in the yellow number 6 jersey with the man from the character sheet (second image), keeping his exact pose, dribble, framing and lighting. Change the jersey number 6 to 67. Keep the defender, the court and the crowd unchanged.',
  },
  fadeaway: {
    inputs: ['src/lebron-8.7.png', SHEET],
    prompt: 'Edit the first image only: replace the shooter in the yellow number 6 jersey with the man from the character sheet (second image), same jump-shot pose, jersey number changed to 67. Replace the flaming basketball with a glowing silicon wafer on fire, same size and position. Keep everything else unchanged.',
  },
  celebrate: {
    inputs: ['src/lebron-11.6-nohead.png', SHEET, '../refs/logo/wordmark.png'],
    prompt: `Edit the first image only. The grey box is where the celebrating player's head goes: fill it with the head of the man from the character sheet (second image), looking up in celebration, and give the arms his skin tone, keeping the player's exact large build, arms-up pose and framing. On the yellow jersey replace "LAKERS" with the SemiAnalysis wordmark from the third image and change 6 to 67 in the same purple lettering. Replace the gold 3D digits "38,388" with chunky shiny gold 3D block characters reading "$100,000,000", partly hidden behind his head and arms. Keep the blurred crowd, lighting and gold grade.`,
  },
  cel1jersey: {
    inputs: ['src/lebron-11.6-nohead.png', '../refs/logo/wordmark.png'],
    prompt: 'Edit the first image only: on the front of the yellow jersey replace the purple "LAKERS" lettering with the SemiAnalysis wordmark from the second image, rendered in the same purple jersey lettering style, and change the number 6 to 67 in the same purple numbers. Leave the grey box exactly as it is. Change nothing else: same body, pose, crowd, framing and gold grade.',
  },
  cel2money: {
    inputs: ['out/cel1jersey{m}.png'],
    prompt: 'Edit this image: replace the gold 3D digits "38,388" floating behind the player with big chunky shiny gold 3D block characters reading "$100,000,000", partly hidden behind the grey box and his raised arms, same glow and perspective. Leave the grey box as it is. Change nothing else.',
  },
  cel3face: {
    inputs: ['out/cel2money{m}.png', SHEET],
    prompt: `Edit the first image only: the grey box is where the celebrating player's head goes. Fill it with the head of the man from the character sheet (second image, ${DYLAN}), looking up in celebration, matching his face, hairline, beard and skin tone, and give the arms the same skin tone. The gold numbers stay partly behind his head. Keep the player's large build, arms-up pose, the SemiAnalysis 67 jersey, the gold $100,000,000 numbers, the blurred crowd and the gold grade exactly as they are.`,
  },
  cel4jersey: {
    inputs: ['out/cel3face{m}.png', SHEET],
    prompt: 'Edit the first image only: make the jersey match the character sheet (second image) exactly. The chest reads "SemiAnalysis" in the same purple athletic lettering as the sheet, with the large purple 67 below it, same yellow jersey with purple trim. Make his arms the same medium-brown skin tone as his face. Keep his face, the arms-up pose, his size, the gold $100,000,000 numbers partly behind his head, the blurred crowd, the framing and the gold grade exactly as they are.',
  },
  introstart: {
    inputs: ['../shots/intro/start-box.png', SHEET],
    prompt: `Edit the first image only. Replace the basketball player inside the red box with the man from the character sheet (second image, ${DYLAN}): his face, hair, beard and skin tone, in the yellow jersey with SemiAnalysis and 67 in purple as on the sheet. Keep that player's exact pose, size, position and the ball. Remove the red box completely. In the broadcast graphic at the top right change LEBRON JAMES to DYLAN PATEL in the same font. Keep every other player, the crowd, the court, the camera framing, the lighting and every other graphic exactly as they are. Photoreal broadcast still.`,
  },
  introend: {
    inputs: ['../shots/intro/end-box.png', SHEET],
    prompt: `Edit the first image only. Replace the basketball player inside the red box with the man from the character sheet (second image, ${DYLAN}): his face, hair, beard and skin tone, in the yellow jersey with SemiAnalysis and 67 in purple as on the sheet. Keep that player's exact pose, size, position and the ball. Remove the red box completely. In the broadcast graphic at the top right change LEBRON JAMES to DYLAN PATEL in the same font. Keep every other player, the crowd, the court, the camera framing, the lighting and every other graphic exactly as they are. Photoreal broadcast still.`,
  },
  bdstart: {
    inputs: ['../shots/backdown/start-box.png', SHEET],
    prompt: `Edit the first image only. Replace the basketball player inside the red box with the man from the character sheet (second image, ${DYLAN}): his short dark hair with no headband, the back and side of his head as on the sheet, his skin tone, in the yellow jersey with PATEL above 67 in purple on the back and SemiAnalysis 67 on the front, as on the sheet. Keep that player's exact pose, size, position, dribble and the ball. Remove the red box completely. Keep every other player, the crowd, the court, the camera framing, the motion blur, the lighting and the colour grade exactly as they are. Photoreal broadcast still.`,
  },
  bdend: {
    inputs: ['../shots/backdown/end-box.png', SHEET],
    prompt: `Edit the first image only. Replace the basketball player inside the red box with the man from the character sheet (second image, ${DYLAN}): his short dark hair with no headband, the back and side of his head as on the sheet, his skin tone, in the yellow jersey with PATEL above 67 in purple on the back and SemiAnalysis 67 on the front, as on the sheet. Keep that player's exact jump-shot pose, size, position and the ball above his head. Remove the red box completely. Keep every other player, the crowd, the court, the camera framing, the motion blur, the lighting and the colour grade exactly as they are. Photoreal broadcast still.`,
  },
  alleyoop: {
    inputs: ['src/lebron-22.95.png', SHEET],
    prompt: 'Edit the first image only: the overhead view of the player in the yellow number 6 jersey going up for the alley-oop dunk. Make that player the man from the character sheet (second image), seen from above, same pose, jersey number changed to 67. Keep the court, the other players and the camera angle unchanged.',
  },
  jersey: {
    inputs: ['src/lebron-26.0.png'],
    prompt: 'Edit this image: change the name on the back of the white jersey from "JAMES" to "PATEL" in the same lettering, size, curve and colour, and the number 6 to 67 in the same style. Keep the posterized high-contrast look and everything else exactly the same.',
  },
  profile: {
    inputs: ['src/lebron-29.0.png', SHEET],
    prompt: 'Edit the first image only: replace the man in side profile with the side profile from the character sheet (second image), same angle, same posterized orange-and-black high-contrast grade. Replace the yellow Nike swoosh with the text "SemiAnalysis" in a clean bold sans serif, the same yellow-green colour and position. Keep the dark background.',
  },
};

const DC = 'Inside a vast, spotless, futuristic AI datacenter hall like xAI Colossus in Memphis: endless symmetrical rows of tall black NVIDIA GB300 NVL72 GPU racks stretching into the distance on both sides, cool white and blue light, glossy polished floor with reflections, cable trays overhead, faint haze, a spacey sci-fi feel but photoreal.';
JOBS.dcend = { inputs: [SHEET, '../refs/dylan/headshot-smile.png', '../refs/dylan/headshot-suit.png'], prompt: `Photoreal cinematic still, 16:9. ${DC} Standing in the centre aisle, framed from the knees up, is the man from the character sheet (first image, ${DYLAN}), his face exactly as in the two headshots (second and third images), with a short, neatly trimmed beard, never a full beard. He wears ${JERSEY}, exactly as on the sheet. Arms crossed, looking straight into the camera with a big wide smile, confident. The racks recede behind him to a vanishing point. Sharp focus on him, shallow depth of field on the far racks.` };
JOBS.dcplate = { inputs: ['../shots/datacenter/post/f01.png'], prompt: 'Edit this image: remove the large hanging dark sign with the xAI logo and the word COLOSSUS at the end of the hall completely. Where it was, continue what is behind it: the ceiling trusses, the rows of ceiling lights receding to the vanishing point and the far end of the hall, matching the perspective and lighting of the rest of the ceiling. Change nothing else at all: same man, same pose, same racks, same framing, same colours.' };
JOBS.dcstart = { inputs: ['out/dcend{m}.png', SHEET], prompt: 'Edit the first image only: the same man in the same place, same arms-crossed pose, same jersey, framing, lighting and background, but his head is tilted down, looking at the floor, with a calm neutral face and no smile. Change nothing else.' };
JOBS.bcintro = { inputs: [SHEET, '../refs/dylan/headshot-smile.png', '../refs/dylan/headshot-suit.png'], prompt: `Photoreal still from a live pro basketball TV broadcast, the pre-game starting-lineup player introduction, 16:9. A dark arena before tip-off: the crowd and the upper bowl in near darkness, one hard white spotlight from high above cutting through thick haze, faint purple and gold glow from LED ribbon boards far behind, the glossy dark court floor lit in a pool around him. Standing a little right of centre, framed from the waist up, is the man from the character sheet (first image, ${DYLAN}), his face exactly as in the two headshots (second and third images), with a short, neatly trimmed beard, never a full beard. He wears ${JERSEY}, exactly as on the sheet. His body is turned about 45 degrees away from the camera, shoulders angled away to the right of frame, and his head is turned back over his left shoulder toward the camera with a calm, serious, confident look, chin slightly down. Hard rim light from the spotlight on his hair, shoulders and arms; his face is clearly lit and sharp. Long broadcast lens, shallow depth of field, haze bloom around the spotlight. No text, no logos and no graphics anywhere on screen.` };
JOBS.bclogo = { inputs: [SHEET], prompt: `Photoreal full-body photo of the man from the character sheet (${DYLAN}) in the same yellow SemiAnalysis 67 jersey and purple shorts, dribbling a basketball low with his left hand, leaning forward in a driving stride, right arm bent out in front for balance, seen exactly from the side so his outline is clear, the whole body head to shoes inside the frame with margin all round. Plain flat pure chroma green background, even studio light, no shadow on the background, nothing else in frame.` };
const SWAP = (extra) => `Edit the first image only. Replace the basketball player inside the red box with the man from the character sheet (second image, ${DYLAN}): his face, short dark hair with no headband, short trimmed beard and skin tone, in the jersey from the sheet with SemiAnalysis and 67 on the front and PATEL above 67 on the back, in purple. ${extra} Remove the red box completely. Keep every other player, the crowd, the court, the camera framing, the motion blur, the lighting and the colour grade exactly as they are. Photoreal broadcast still.`;
const SHOTS = path.join(DIR, '../shots');
for (const shot of fs.readdirSync(SHOTS)) {
  const f = path.join(SHOTS, shot, 'edit.json');
  if (!fs.existsSync(f)) continue;
  const e = JSON.parse(fs.readFileSync(f, 'utf8'));
  for (const side of ['start', 'end']) {
    if (!e[side]) continue;
    JOBS[`${shot}-${side}`] = { inputs: [`../shots/${shot}/${side}-box.png`, SHEET], prompt: e[side].prompt ?? SWAP(e[side].extra ?? '') };
  }
}

async function run(name) {
  const job = JOBS[name];
  const t0 = Date.now();
  const imagesApi = MODEL.startsWith('openai/gpt-image');
  const res = await fetch(`https://openrouter.ai/api/v1/${imagesApi ? 'images' : 'chat/completions'}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(imagesApi
      ? { model: MODEL, prompt: job.prompt, input_references: job.inputs.map(img), size: process.env.SIZE ?? '1792x1008', quality: process.env.QUALITY ?? 'high' }
      : { model: MODEL, modalities: ['image', 'text'], messages: [{ role: 'user', content: [{ type: 'text', text: job.prompt }, ...job.inputs.map(img)] }], usage: { include: true } }),
  });
  const body = await res.json();
  if (process.env.DEBUG) console.error(JSON.stringify(body, (k, v) => (typeof v === 'string' && v.length > 200 ? v.slice(0, 80) + '...' : v)));
  const pic = body.data?.[0];
  const url = pic?.b64_json ? `data:image/png;base64,${pic.b64_json}` : pic?.url ?? body.choices?.[0]?.message?.images?.[0]?.image_url?.url;
  const row = { name, model: MODEL, status: res.status, seconds: (Date.now() - t0) / 1000, cost: body.usage?.cost ?? body.usage?.total_cost ?? null, error: body.error?.message?.slice(0, 300) ?? null };
  if (url) {
    const file = path.join(OUT, `${name}${SUFFIX}.png`);
    fs.writeFileSync(file, url.startsWith('data:') ? Buffer.from(url.split(',')[1], 'base64') : Buffer.from(await (await fetch(url)).arrayBuffer()));
    row.file = path.relative(DIR, file);
  }
  const log = path.join(OUT, 'log.json');
  fs.writeFileSync(log, JSON.stringify([...(fs.existsSync(log) ? JSON.parse(fs.readFileSync(log, 'utf8')) : []), { ...row, at: new Date().toISOString() }], null, 2));
  console.log(JSON.stringify(row));
  return Boolean(url) || !/safety system/.test(row.error ?? '');
}

fs.mkdirSync(OUT, { recursive: true });
const [mode, ...names] = process.argv.slice(2);
// The frames the reel's job.json files read, in an order where each edit's input exists first. The other jobs
// (wide, backdown, fadeaway, celebrate, alleyoop, jersey, profile, bcintro, bclogo) were tried and not used.
const REEL = ['cel1jersey', 'cel2money', 'cel3face', 'cel4jersey', 'celebrate-start', 'introstart', 'introend', 'bdstart', 'bdend',
  'fadeaway-start', 'fadeaway-end', 'alleyoop-start', 'alleyoop-end', 'jersey-start', 'dcend', 'dcstart'];
const todo = mode === 'sheet' ? ['sheet'] : names.length ? names : REEL;
for (const n of todo) {
  for (let i = 0; i < 4 && !(await run(n)); i++);
}
