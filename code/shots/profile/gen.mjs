// Dylan side-profile stills for the profile scene, through GPT Image 2.5 Sunburst on OpenRouter (same pattern as
// starts/gen.mjs). Saves shots/profile/gen/<name>.png and logs cost to shots/profile/gen/log.json.
// The key comes from OPENROUTER_API_KEY in the environment.
//   node shots/profile/gen.mjs profile [take]
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.dirname(new URL(import.meta.url).pathname);
const R = path.resolve(DIR, '../..');
const OUT = path.join(DIR, 'gen');
const MODEL = process.env.MODEL ?? 'openai/gpt-image-2.5-sunburst';
const key = process.env.OPENROUTER_API_KEY;
if (!key) throw new Error('set OPENROUTER_API_KEY (see .env.example)');
const img = (p) => ({ type: 'image_url', image_url: { url: `data:image/png;base64,${fs.readFileSync(path.join(R, p)).toString('base64')}` } });

const REFS = ['starts/out/sheet-gpt-image-2.5-sunburst.png', 'refs/dylan/headshot-suit-768.png', 'refs/dylan/side-c.png', 'refs/dylan/threequarter-a.png'];
const JOBS = {
  up: {
    inputs: REFS,
    prompt: 'Photoreal tight close-up portrait of the man in these images (the character sheet first, then real photos of him): exactly the same face, nose, hairline, short dark hair, trimmed beard and skin tone. Strict side profile facing to the right, his nose pointing at the right edge of the image. His head is tilted back about fifteen degrees and he looks upward, calm and determined, like an athlete in a sneaker poster standing on the court before the game. His shoulders are raised and broad so the top of his near shoulder sits just below his jaw and fills the lower left of the image. He wears the yellow basketball jersey from the character sheet: only the neckline and the top of the shoulder show, yellow with purple and white trim, no lettering visible. Hard key light from in front of his face and above lights the face, nose, lips, ear rim and the top of the shoulder; the back of the head and neck fall off into warm shadow; crisp high contrast, sharp detail in the skin, beard and ear. The whole head, hair, ear, chin and the near shoulder are inside the frame with a margin on the top, left and right. Plain flat uniform light grey seamless studio background with no gradient, no shadow and no objects. No text, no logo.',
  },
  profile: {
    inputs: REFS,
    prompt: 'Photoreal close-up portrait of the man in these images (the character sheet first, then real photos of him): exactly the same face, nose, hairline, short dark hair, trimmed beard and skin tone. Face and shoulders only, in a strict side profile facing to the right, his nose pointing at the right edge of the image. He stands still with his chin slightly raised, looking slightly upward and ahead, calm and determined, like an athlete in a sneaker poster before the game. He wears the yellow basketball jersey from the character sheet: only the neckline and the top of the shoulder show, yellow with purple and white trim, no lettering visible. Strong hard key light from in front of his face and above, so the face, nose, lips and the top of the shoulder are brightly lit and the back of the head falls into shadow; crisp high contrast, sharp detail in the skin, beard and ear. The whole head, hair, ear, chin, neck and both shoulders are fully inside the frame with a clear margin on every side. Plain flat uniform light grey seamless studio background with no gradient, no shadow and no objects. No text, no logo.',
  },
  // v10: pinned first and last frames for the Wan i2v clip (16:9, flat mid grey that keys cleanly)
  'vid-end': {
    inputs: ['shots/profile/gen/up-b.png', ...REFS.slice(0, 3)],
    prompt: 'Recompose the first image as a wide 16:9 photo, keeping exactly the same man, face, beard, hair, skin tone, yellow jersey with purple and white trim, hard key light and high contrast. Strict side profile facing right, nose pointing at the right edge. His head is tilted back about fifteen degrees and he looks upward, tough and focused, mouth closed. Face and shoulders only: his head sits in the left-centre of the frame, the top of his hair about one tenth of the height below the top edge, the back of his head well inside the left edge, his near shoulder and the jersey neckline filling the lower left and running off the bottom edge. The rest of the frame to the right of his face is empty. Background: one solid flat uniform mid grey (#808080) everywhere, perfectly even, no gradient, no vignette, no texture, no shadow on it, no objects. No text, no logo, no lettering on the jersey.',
  },
  'vid-start': {
    inputs: ['shots/profile/gen/vid-end.png', ...REFS.slice(0, 3)],
    prompt: 'The same photo as the first image, identical in every way: same man, same framing and camera, same yellow jersey, same hard key light and contrast, same solid flat mid grey (#808080) background with no gradient or texture. Change only his pose a little: his head is about twelve degrees lower than in the first image, chin level, and he looks straight ahead toward the right edge rather than upward, tough and focused, mouth closed, shoulders slightly lower and relaxed as if just before a breath in. Still a strict side profile facing right. His head stays in the same place in the frame, the top of his hair a little lower. No text, no logo, no lettering on the jersey.',
  },
  // v11: first frame for the turn. He starts turned away from camera (three-quarter back) and turns into the
  // vid-end profile, so the same vid-end.png stays the last frame.
  'vid-start-away': {
    inputs: ['shots/profile/gen/vid-end.png', ...REFS.slice(0, 3)],
    prompt: 'The same photo as the first image, identical in every way: same man, same short dark hair, same yellow basketball jersey with purple and white trim, same camera, same hard key light and contrast, same solid flat mid grey (#808080) background with no gradient or texture. Change only his pose: he has turned his head and shoulders away from the camera, a three-quarter back view. We see mostly the back and the left side of his head, his left ear, the back of his neck and the back of his left shoulder; his face is turned away toward the right and into the depth of the frame, so only the edge of his left cheek, the line of his beard along the jaw and the tip of his eyebrow show, no eye, nose or mouth visible. His head is level. His head stays in the same place and at the same size in the frame as in the first image, in the left-centre, the top of his hair about one tenth of the height below the top edge, the jersey shoulder running off the bottom edge. The rest of the frame to the right is empty grey. No text, no logo, no lettering or number on the jersey.',
  },
  // v12: the end still with a level gaze. Same framing, light and jersey as vid-end.png, chin and eyes level.
  'vid-end-level': {
    inputs: ['shots/profile/gen/vid-end.png', ...REFS.slice(0, 3)],
    prompt: 'The same photo as the first image, identical in every way: same man, same face, beard, hair and skin tone, same framing and camera, same position and size of his head in the frame, same yellow jersey with purple and white trim, same hard key light and contrast, same solid flat mid grey (#808080) background with no gradient or texture. Change only where he looks: his chin is level and his head is not tilted back at all, and his eyes look straight ahead, level and sideways toward the right edge of the image, not upward. Strict side profile facing right, nose pointing at the right edge, tough and focused, mouth closed. No text, no logo, no lettering on the jersey.',
  },
};

async function run(name, take) {
  const job = JOBS[name];
  const t0 = Date.now();
  const res = await fetch('https://openrouter.ai/api/v1/images', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: MODEL, prompt: job.prompt, input_references: job.inputs.map(img), size: process.env.SIZE ?? '1008x1792', quality: process.env.QUALITY ?? 'high' }),
  });
  const body = await res.json();
  const pic = body.data?.[0];
  const url = pic?.b64_json ? `data:image/png;base64,${pic.b64_json}` : pic?.url;
  const row = { name, take, model: MODEL, status: res.status, seconds: (Date.now() - t0) / 1000, cost: body.usage?.cost ?? body.usage?.total_cost ?? null, error: body.error?.message?.slice(0, 300) ?? null };
  if (url) {
    const file = path.join(OUT, `${name}${take ? '-' + take : ''}.png`);
    fs.writeFileSync(file, url.startsWith('data:') ? Buffer.from(url.split(',')[1], 'base64') : Buffer.from(await (await fetch(url)).arrayBuffer()));
    row.file = path.relative(DIR, file);
  }
  const log = path.join(OUT, 'log.json');
  fs.writeFileSync(log, JSON.stringify([...(fs.existsSync(log) ? JSON.parse(fs.readFileSync(log, 'utf8')) : []), { ...row, at: new Date().toISOString() }], null, 2));
  console.log(JSON.stringify(row));
  if (res.status === 402) process.exit(2);
  return Boolean(url) || !/safety system/.test(row.error ?? '');
}

fs.mkdirSync(OUT, { recursive: true });
const [name = 'profile', take = ''] = process.argv.slice(2);
for (let i = 0; i < 2 && !(await run(name, take)); i++);   // two tries at most
