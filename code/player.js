// The cut preview: the audio mix (song minus announcer, plus the Patel voice line) is the clock, and each scene shows its chosen take, time-stretched to fit.
const ORIG = 'src/clip.mp4';
const o = (note) => ({ label: 'Original', src: ORIG, original: true, note });
const SCENES = [
  { name: 'Fade in', dir: 'fadein', t0: 0, t1: 1.0, status: 'keep', takes: [o('Kept as is.')] },
  { name: 'Intro wide', dir: 'intro', t0: 1.0, t1: 6.27, status: 'done', takes: [
    { label: 'Strong prompt', src: 'shots/intro/out/wan-3.0-noframes-strong.mp4', note: 'Best intro. Dylan, no headband, original motion.' },
    { label: 'Focus slowed', src: 'shots/intro/out/focus-slow-realtime.mp4', note: 'Dylan but softer.' },
    { label: 'Focus', src: 'shots/intro/out/wan-3.0-noframes-focus.mp4', note: 'Slid back toward LeBron.' },
    { label: 'Hailuo frames', src: 'shots/intro/out/hailuo-3-framesonly.mp4', note: 'Own motion, number drifts to 97.' },
    o() ] },
  { name: 'Back-down', dir: 'backdown', t0: 6.27, t1: 8.57, status: 'done', takes: [
    { label: 'Focus', src: 'shots/backdown/out/focus-realtime.mp4', note: 'Best. Short beard holds on the turn.' },
    { label: 'v2 slowed', src: 'shots/backdown/out/wan-3.0-slow-realtime.mp4', note: 'Beard goes full on the final turn.' },
    { label: 'Frames only', src: 'shots/backdown/out/wan-3.0-novideo-min.mp4', note: 'Best face, but invents its own play.' },
    o() ] },
  { name: 'Fadeaway', dir: 'fadeaway', t0: 8.57, t1: 10.0, status: 'done', takes: [
    { label: 'Focus', src: 'shots/fadeaway/out/final-realtime.mp4', note: 'Good. PATEL reads PATTI, fix in post. Wafer VFX still to add.' }, o() ] },
  { name: 'Rim explosion', dir: 'rim', t0: 10.0, t1: 10.8, status: 'done', takes: [o('Original. Shows LeBron with the headband.')] },
  { name: 'Celebrate', dir: 'celebrate', t0: 10.8, t1: 12.0, status: 'done', takes: [
    { label: 'Frames only', src: 'shots/celebrate/out/min-realtime.mp4', note: 'Locked by Zeal. Dylan face, clean jersey, $100,000,000 in gold from midway. The newspaper builds out of its last frame.' },
    { label: 'Take 3', src: 'shots/celebrate/out/take3-realtime.mp4', note: 'V2V copies the source digits, so it still reads 38,388 and the patches stay. Only usable with the digits replaced in post.' },
    { label: 'Take 2', src: 'shots/celebrate/out/final-realtime.mp4', note: 'Digits read 388 until the end, patches remain.' },
    o() ] },
  { name: 'Newspaper', dir: 'newspaper', t0: 12.0, t1: 13.84, status: 'todo', takes: [o('To build in our engine from the front page below.')] },
  { name: 'Podcast hype', dir: 'fastcuts', t0: 13.84, t1: 20.8, status: 'todo', takes: [o('Dylan podcast hype cuts on the beat, with the Jensen belt zoom. Being built.')] },
  { name: 'Alley-oop', dir: 'alleyoop', t0: 20.8, t1: 23.17, status: 'done', takes: [
    { label: 'Take 2', src: 'shots/alleyoop/out/final-realtime.mp4', note: 'Matches the overhead play move for move, and the dunker is Dylan, no headband. Small in frame, so it sells.' }, o() ] },
  { name: 'Fade out', dir: 'fadeout', t0: 23.17, t1: 25.43, status: 'done', takes: [o('Original. LeBron hangs on the rim for the first half second.')] },
  { name: 'Jersey', dir: 'jersey', t0: 25.43, t1: 26.8, status: 'done', takes: [
    { label: 'PATEL 67', src: 'shots/jersey/out/final-realtime.mp4', note: 'Good. Cut before the last 0.5 s tint.' }, o() ] },
  { name: 'Profile and logo', dir: 'profile', t0: 26.8, t1: 30.07, status: 'todo', takes: [o('Dylan profile from a podcast plus the end logo, built in our engine.')] },
];
const END = 30.07;
const KEY = 'reel-cut-picks-v2';

const $ = (s) => document.querySelector(s);
const stage = $('#cut-stage'), audio = $('#cut-audio'), bar = $('#cut-bar'), list = $('#cut-list');
let picks = {};
try { picks = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(picks)); } catch {} };

// The preview server ignores Range requests, so media is loaded whole as blobs to make seeking work.
const blob = (src) => fetch(src, { cache: 'no-store' }).then((r) => (r.ok ? r.blob() : Promise.reject(r.status))).then((b) => URL.createObjectURL(b));
blob(audio.dataset.src).then((u) => { audio.src = u; });
const vids = new Map();
function vid(src) {
  if (!vids.has(src)) {
    const v = document.createElement('video');
    Object.assign(v, { muted: true, playsInline: true, preload: 'auto' });
    v.dataset.src = src;
    v.onloadedmetadata = render;
    blob(src).then((u) => { v.src = u; }, () => { v.dataset.missing = '1'; render(); });
    stage.appendChild(v);
    vids.set(src, v);
  }
  return vids.get(src);
}
const ready = (t) => vid(t.src).dataset.missing !== '1';
const pick = (i) => {
  const s = SCENES[i];
  const want = s.takes.find((t) => t.label === picks[i]) ?? s.takes[0];
  return want && ready(want) ? want : s.takes.find(ready) ?? s.takes.at(-1);
};
SCENES.forEach((s) => s.takes.forEach((t) => vid(t.src)));
// Builders publish new takes in shots/<dir>/takes.json as { status?, takes: [{ label, src, note }] }, newest first, with src relative to this page.
Promise.all(SCENES.map((s) => fetch(`shots/${s.dir}/takes.json`, { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null).then((m) => {
  if (!m) return;
  if (m.status) s.status = m.status;
  const have = new Set(s.takes.map((t) => t.label));
  s.takes.unshift(...(m.takes ?? []).filter((t) => !have.has(t.label)));
  s.takes.forEach((t) => vid(t.src));
}))).then(() => { drawBar(); render(); });

const drawBar = () => { bar.innerHTML = SCENES.map((s, i) => `<button class="seg ${s.status}" data-i="${i}" style="flex:${s.t1 - s.t0}" title="${s.name}">${s.name}</button>`).join('') + '<i id="cut-head"></i>'; };
drawBar();
bar.onclick = (e) => {
  const r = bar.getBoundingClientRect();
  audio.currentTime = ((e.clientX - r.left) / r.width) * END;
  tick();
};

function render() {
  list.innerHTML = SCENES.map((s, i) => {
    const cur = pick(i);
    return `<div class="scene ${s.status}" data-i="${i}">
      <div class="sh"><button class="go" data-go="${i}">${s.t0.toFixed(2)} ${s.name}</button><span class="st">${{ keep: 'kept', done: 'generated', work: 'needs work', todo: 'to build' }[s.status]}</span></div>
      <div class="takes">${s.takes.map((t, j) => {
        const miss = !ready(t);
        return `<button data-i="${i}" data-j="${j}" class="${t === cur ? 'on' : ''}" ${miss ? 'disabled title="not generated yet"' : ''}>${t.label}${miss ? ' (pending)' : ''}</button>`;
      }).join('')}</div>
      <div class="note">${cur.note ?? s.takes.find((t) => t.original)?.note ?? ''}</div></div>`;
  }).join('');
}
list.onclick = (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.go) { audio.currentTime = SCENES[b.dataset.go].t0 + 0.001; tick(); return; }
  picks[b.dataset.i] = SCENES[b.dataset.i].takes[b.dataset.j].label;
  save();
  render();
  audio.currentTime = SCENES[b.dataset.i].t0 + 0.001;
  tick();
};

let shown = null;
let held = 0;
function tick() {
  if (audio.dataset.loop === '1' && !audio.paused) {
    const h = SCENES[held];
    if (audio.currentTime >= h.t1 - 0.03 || audio.currentTime < h.t0) audio.currentTime = h.t0 + 0.001;
  }
  const t = audio.currentTime;
  const i = Math.max(0, SCENES.findIndex((s) => t >= s.t0 && t < s.t1));
  if (audio.paused || audio.dataset.loop !== '1') held = i;
  const s = SCENES[i], take = pick(i), v = vid(take.src);
  const rate = take.original || !v.duration ? 1 : v.duration / (s.t1 - s.t0);
  const want = take.original ? t : (t - s.t0) * rate;
  if (shown !== v) { if (shown) { shown.classList.remove('on'); shown.pause(); } v.classList.add('on'); shown = v; }
  v.playbackRate = Math.min(4, Math.max(0.25, rate));
  if (Math.abs(v.currentTime - want) > 0.12) v.currentTime = want;
  if (audio.paused) v.pause(); else if (v.paused) v.play().catch(() => {});
  $('#cut-head').style.left = `${(t / END) * 100}%`;
  $('#cut-time').textContent = `${t.toFixed(2)} s  ${s.name}  (${take.label})`;
  bar.querySelectorAll('.seg').forEach((b) => b.classList.toggle('cur', +b.dataset.i === i));
  list.querySelectorAll('.scene').forEach((d) => d.classList.toggle('cur', +d.dataset.i === i));
}
(function loop() { tick(); requestAnimationFrame(loop); })();

$('#cut-play').onclick = () => (audio.paused ? audio.play() : audio.pause());
audio.onplay = audio.onpause = () => { $('#cut-play').textContent = audio.paused ? 'Play' : 'Pause'; };
const sceneAt = () => Math.max(0, SCENES.findIndex((s) => audio.currentTime >= s.t0 && audio.currentTime < s.t1));
document.addEventListener('keydown', (e) => {
  if (e.target.closest('textarea,input')) return;
  if (e.key === ' ') { e.preventDefault(); $('#cut-play').click(); }
  else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault();
    const n = Math.min(SCENES.length - 1, Math.max(0, sceneAt() + (e.key === 'ArrowRight' ? 1 : -1)));
    audio.currentTime = SCENES[n].t0 + 0.001;
  } else if (/^[1-9]$/.test(e.key)) {
    const i = sceneAt(), j = +e.key - 1;
    if (SCENES[i].takes[j] && ready(SCENES[i].takes[j])) { picks[i] = SCENES[i].takes[j].label; save(); render(); }
  }
});
$('#cut-mix').value = audio.dataset.src;
$('#cut-mix').onchange = (e) => { const t = audio.currentTime, playing = !audio.paused; blob(e.target.value).then((u) => { audio.src = u; audio.onloadedmetadata = () => { audio.currentTime = t; if (playing) audio.play(); }; }); };
$('#cut-loop').onchange = (e) => { audio.dataset.loop = e.target.checked ? '1' : ''; };
render();
