// Video storyboard: plays every take of every slot on the video's clock, and replays the picks of each checkpoint.
// Everything comes from storyboard.json (see schema.json). Paths under media/ resolve only against a folder the
// viewer supplies (?media=<folder> or "Load my media folder"); without one the page shows data and placeholders.
'use strict';
(() => {
  const params = new URLSearchParams(location.search);
  const $ = (sel) => document.querySelector(sel);
  const VERDICTS = { keep: 'Keep', overlay: 'Overlay', swap: 'Swap', render: 'Render', replace: 'Replace', found: 'Found', filmed: 'Filmed' };
  const STATUS = { picked: 'Picked', superseded: 'Superseded', rejected: 'Rejected', lab: 'Lab', failed: 'Failed' };
  const BLOB_LIMIT = 400 * 1024 * 1024;

  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      node.append(kid instanceof Node ? kid : String(kid));
    }
    return node;
  }
  const fill = (node, ...kids) => node.replaceChildren(...kids.flat(2).filter((k) => k !== null && k !== undefined && k !== false));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
  };
  const fmt = (t) => (t.toFixed(2) + ' s');
  const mmss = (t) => (Math.floor(t / 60) + ':' + (String(Math.floor(t % 60)).padStart(2, '0')));
  const money = (n) => (n >= 1 ? ('$' + n.toFixed(2)) : ('$' + n.toFixed(n >= 0.01 ? 3 : 4)));
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

  function safeUrl(url) {
    try { const u = new URL(url); return u.protocol === 'https:' ? u : null; } catch { return null; }
  }
  function stamp(url, t) {
    const u = safeUrl(url);
    if (!u) return null;
    if (t === undefined || t === null) return u.href;
    const s = Math.max(0, Math.floor(t));
    if (/(^|\.)youtube\.com$|^youtu\.be$/.test(u.hostname)) u.searchParams.set('t', (s + 's'));
    else if (/(^|\.)vimeo\.com$/.test(u.hostname)) u.hash = ('t=' + s + 's');
    return u.href;
  }
  const extLink = (url, t, text) => {
    const href = stamp(url, t);
    return href ? h('a', { href, target: '_blank', rel: 'noopener noreferrer' }, text) : null;
  };

  // Theme: system, light or dark, remembered per viewer.
  const THEMES = ['system', 'light', 'dark'];
  function applyTheme(name) {
    if (name === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = name;
    $('#theme').textContent = ('Theme: ' + name);
    store.set('reel-storyboard-theme', name);
  }
  applyTheme(THEMES.includes(store.get('reel-storyboard-theme')) ? store.get('reel-storyboard-theme') : 'system');
  $('#theme').onclick = () => {
    const cur = document.documentElement.dataset.theme || 'system';
    applyTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
  };

  // Media: private paths resolve against ?media= or a picked folder; shipped paths resolve beside the page.
  const media = {
    base: params.get('media'),
    files: null,
    resolved: new Map(),
    pending: new Map(),
    found: 0,
    missing: 0,
    active() { return Boolean(this.base || this.files); },
    get(path) {
      if (!path) return null;
      if (this.resolved.has(path)) return this.resolved.get(path);
      if (!this.pending.has(path)) this.pending.set(path, this.load(path));
      return undefined;
    },
    when(path) {
      if (this.resolved.has(path)) return Promise.resolve(this.resolved.get(path));
      if (!this.pending.has(path)) this.pending.set(path, this.load(path));
      return this.pending.get(path);
    },
    async load(path) {
      let url = null;
      const priv = path.startsWith('media/');
      const rel = priv ? path.slice(6) : path;
      if (!priv) url = await fetchUrl(path);
      else if (this.files) { const f = this.files.get(rel); url = f ? URL.createObjectURL(f) : null; }
      else if (this.base) url = await fetchUrl(this.base.replace(/\/?$/, '/') + rel.split('/').map(encodeURIComponent).join('/'));
      if (priv && this.active()) { if (url) this.found += 1; else this.missing += 1; }
      this.resolved.set(path, url);
      this.pending.delete(path);
      showMediaStatus();
      return url;
    },
    useFolder(fileList) {
      const files = new Map();
      for (const f of fileList) {
        const rest = (f.webkitRelativePath || f.name).split('/').slice(1).join('/') || f.name;
        files.set(rest, f);
        if (rest.startsWith('media/')) files.set(rest.slice(6), f);
      }
      for (const url of this.resolved.values()) if (url && url.startsWith('blob:')) URL.revokeObjectURL(url);
      Object.assign(this, { files, resolved: new Map(), pending: new Map(), found: 0, missing: 0 });
      stage.reset();
    },
  };
  // A server without Range support cannot seek a streamed video, so small files load whole as blobs.
  async function fetchUrl(url) {
    try {
      const head = await fetch(url, { method: 'HEAD' });
      if (!head.ok) return null;
      const size = Number(head.headers.get('content-length')) || 0;
      if (head.headers.get('accept-ranges') === 'bytes' || size > BLOB_LIMIT) return url;
      const res = await fetch(url);
      return res.ok ? URL.createObjectURL(await res.blob()) : null;
    } catch {
      return null;
    }
  }

  let doc = null;
  let cpIndex = 0;
  let mode = 'picks';
  const overrides = new Map();
  let segs = [];
  let slotOrder = [];
  const slotById = new Map();

  const cp = () => doc.checkpoints[cpIndex];
  const duration = () => cp().duration_s || doc.clock.duration_s;
  const sections = () => cp().sections || doc.clock.sections || [];
  const takeOf = (slot, id) => slot.takes.find((t) => t.id === id) || null;

  function buildSegments() {
    const c = cp();
    const out = [];
    for (const slot of doc.slots) {
      const over = overrides.get(slot.id);
      const recorded = c.picks ? c.picks[slot.id] : undefined;
      if (!c.picks || recorded || over) {
        const [t0, t1] = (c.bounds && c.bounds[slot.id]) || [slot.t0, slot.t1];
        const take = takeOf(slot, over || recorded || '');
        out.push({ slot, t0, t1, take, over: Boolean(over), unrecorded: !c.picks && !over });
      }
    }
    out.sort((a, b) => a.t0 - b.t0 || a.t1 - b.t1);
    segs = out;
    const inCp = new Set(out.map((s) => s.slot.id));
    slotOrder = [...out.map((s) => s.slot), ...doc.slots.filter((s) => !inCp.has(s.id)).sort((a, b) => a.t0 - b.t0)];
  }
  function segAt(t) {
    let best = null;
    for (const s of segs) if (t >= s.t0 && t < s.t1 && (!best || s.over || !best.over)) best = s;
    return best;
  }

  // The clock: an audio file, the render's own sound, or a silent timer.
  const clock = {
    el: null,
    base: 0,
    startedAt: 0,
    playing: false,
    time() {
      if (this.el) return this.el.currentTime;
      return this.playing ? this.base + (performance.now() - this.startedAt) / 1000 : this.base;
    },
    seek(t) {
      t = clamp(t, 0, duration());
      if (this.el) this.el.currentTime = t;
      this.base = t;
      this.startedAt = performance.now();
    },
    play() {
      const t = this.time() >= duration() - 0.01 ? 0 : this.time();
      this.seek(t);
      this.playing = true;
      if (this.el) this.el.play().catch(() => {});
      $('#play').textContent = 'Pause';
    },
    pause() {
      this.base = this.time();
      this.playing = false;
      if (this.el) this.el.pause();
      $('#play').textContent = 'Play';
    },
    use(el) {
      const t = this.time();
      const was = this.playing;
      if (this.el && this.el !== el) this.el.pause();
      this.el = el;
      this.seek(t);
      if (el && el.readyState < 1) el.addEventListener('loadedmetadata', () => { el.currentTime = clamp(t, 0, duration()); }, { once: true });
      if (was) this.play();
    },
  };

  const audioEls = new Map();
  function audioOptions() {
    const c = cp();
    const list = [];
    if (c.audio) list.push({ id: ('cp:' + c.audio.id), label: (c.audio.label + ' (this checkpoint)'), media: c.audio.media });
    for (const a of doc.clock.audio || []) list.push({ id: a.id, label: a.label, media: a.media });
    if (c.render) list.push({ id: 'render', label: "The render's own sound", media: c.render.media, render: true });
    return list;
  }
  function setupAudio() {
    const sel = $('#audio');
    const list = audioOptions();
    sel.replaceChildren(...list.map((a) => h('option', { value: a.id, disabled: true }, a.label)), h('option', { value: 'silent' }, 'Silent clock'));
    sel.value = 'silent';
    clock.use(null);
    // The render loads only once someone plays it, since it is the largest file.
    const reachable = list.map((a) => (a.render ? Promise.resolve(media.resolved.get(a.media) || null)
      : !media.active() && a.media.startsWith('media/') ? Promise.resolve(null) : media.when(a.media)));
    const forCp = cpIndex;
    Promise.all(reachable).then((urls) => {
      if (forCp !== cpIndex) return;
      urls.forEach((url, i) => { sel.options[i].disabled = !url; });
      const first = urls.findIndex(Boolean);
      if (first >= 0) { sel.value = list[first].id; sel.onchange(); }
    });
    sel.onchange = () => {
      const a = list.find((x) => x.id === sel.value);
      if (!a) { clock.use(null); return; }
      const url = media.get(a.media);
      if (!url) { clock.use(null); return; }
      if (a.render) { clock.use(stage.video(url, false)); return; }
      if (!audioEls.has(url)) audioEls.set(url, Object.assign(new Audio(), { src: url, preload: 'auto' }));
      clock.use(audioEls.get(url));
    };
  }

  // The stage shows one video, one still, or a placeholder card.
  const stage = {
    root: $('#stage'),
    videos: new Map(),
    img: null,
    shown: null,
    video(url, muted = true) {
      if (!this.videos.has(url)) {
        const v = h('video', { playsinline: true, preload: 'auto' });
        v.muted = muted;
        v.src = url;
        this.root.prepend(v);
        this.videos.set(url, v);
      }
      const v = this.videos.get(url);
      if (!muted) v.muted = false;
      return v;
    },
    still(url) {
      if (!this.img) { this.img = h('img', { alt: '' }); this.root.prepend(this.img); }
      if (this.img.dataset.src !== url) { this.img.src = url; this.img.dataset.src = url; }
      return this.img;
    },
    show(node) {
      if (this.shown === node) return;
      if (this.shown) {
        this.shown.classList.remove('on');
        if (this.shown.tagName === 'VIDEO' && this.shown !== clock.el) this.shown.pause();
      }
      if (node) node.classList.add('on');
      this.shown = node;
      $('#card').hidden = Boolean(node);
    },
    reset() {
      for (const v of this.videos.values()) { v.pause(); v.remove(); }
      this.videos.clear();
      if (this.img) { this.img.remove(); this.img = null; }
      this.shown = null;
    },
  };

  let cardKey = '';
  function card(key, title, chips, why) {
    stage.show(null);
    if (cardKey === key) return;
    cardKey = key;
    fill($('#card'), h('div', { class: 'big' }, title), h('div', { class: 'row' }, chips), why ? h('div', { class: 'why' }, why) : null);
  }
  const statusChip = (s) => h('span', { class: ('chip s-' + s) }, STATUS[s] || s);

  // Where a take's picture is at clock time t: a video and its time and rate, a still, or nothing to show.
  function frameAt(seg, t) {
    const take = seg.take;
    const local = t - seg.t0;
    const len = seg.t1 - seg.t0;
    if (take.plays_reference) {
      const path = doc.clock.reference && doc.clock.reference.media;
      return path ? { path, time: (doc.clock.reference.offset_s || 0) + t, rate: 1 } : null;
    }
    const m = take.media || {};
    if (m.video) {
      const cut = (take.cuts || []).find((c) => c.span && local >= c.t0 && local < c.t1);
      if (cut) {
        const rate = (cut.span[1] - cut.span[0]) / (cut.t1 - cut.t0);
        return { path: m.video, time: cut.span[0] + (local - cut.t0) * rate, rate };
      }
      if (m.span) {
        const rate = (m.span[1] - m.span[0]) / len;
        return { path: m.video, time: m.span[0] + local * rate, rate };
      }
      return { path: m.video, stretch: len, local };
    }
    if (m.still) return { path: m.still, still: true };
    if (take.frames && take.frames.first) return { path: take.frames.first, still: true };
    return null;
  }

  function sync(v, want, rate) {
    if (v === clock.el) return;
    if (!Number.isFinite(want)) return;
    v.playbackRate = clamp(rate || 1, 0.0625, 16);
    const drift = Math.abs(v.currentTime - want);
    if (clock.playing) {
      if (drift > 0.25) v.currentTime = want;
      if (v.paused) v.play().catch(() => {});
    } else {
      if (!v.paused) v.pause();
      if (drift > 0.5 / doc.clock.fps) v.currentTime = want;
    }
  }

  function placeholder(seg, why) {
    const take = seg.take;
    const reason = why || (media.active() ? 'This file is not in your media folder.' : 'No media loaded. Open with ?media=<folder> or load your folder to play it.');
    card((seg.slot.id + '/' + take.id + '/' + reason), take.label, [statusChip(take.status), take.public ? null : h('span', { class: 'chip' }, 'media private')], ((take.why || '') + ' ' + reason).trim());
  }

  function paint(t, seg) {
    if (mode === 'render') {
      const r = cp().render;
      if (!r) return card('no-render', 'No render at this checkpoint', [], 'Switch to the picks to play this checkpoint slot by slot.');
      const url = media.get(r.media);
      if (!url) return card(('render-' + url), r.label || 'Render', [], url === null ? 'The render is not in your media folder.' : 'Loading the render.');
      const v = stage.video(url);
      stage.show(v);
      return sync(v, t, 1);
    }
    if (!seg) {
      const gap = sections().find((s) => t >= s.t0 && t < s.t1);
      return card(('gap-' + (gap ? gap.label : '')), 'Between slots', [], gap ? (gap.label + '. ' + (gap.note || '')) : 'No slot covers this time at this checkpoint.');
    }
    if (!seg.take) {
      return card(('unrec-' + seg.slot.id), seg.slot.label, [h('span', { class: 'chip' }, VERDICTS[seg.slot.verdict])],
        seg.unrecorded ? 'This checkpoint kept no per-slot record. Pick a take below to play one here.' : 'No take is picked for this slot.');
    }
    const f = frameAt(seg, t);
    if (!f) return placeholder(seg, seg.take.status === 'failed' ? 'The request returned no output.' : 'This take has no media file.');
    if (!media.active() && f.path.startsWith('media/')) return placeholder(seg);
    const url = media.get(f.path);
    if (url === undefined) return placeholder(seg, 'Loading.');
    if (url === null) return placeholder(seg);
    if (f.still) return stage.show(stage.still(url));
    const v = stage.video(url);
    stage.show(v);
    if (f.stretch) {
      const rate = v.duration ? v.duration / f.stretch : 1;
      return sync(v, f.local * rate, rate);
    }
    return sync(v, f.time, f.rate);
  }

  let curSeg = null;
  function tick() {
    if (doc) {
      let t = clock.time();
      const seg = segAt(t);
      if ($('#loop').checked && clock.playing && curSeg && (t >= curSeg.t1 - 0.02 || t < curSeg.t0)) {
        clock.seek(curSeg.t0 + 0.001);
        t = clock.time();
      } else if (t >= duration()) {
        clock.pause();
        clock.seek(duration());
        t = duration();
      }
      const now = $('#loop').checked && clock.playing && curSeg ? curSeg : segAt(t);
      paint(t, now);
      if (now !== curSeg) { curSeg = now; markCurrent(); }
      $('#playhead').style.left = (((t / duration()) * 100) + '%');
      $('#timeline').setAttribute('aria-valuenow', t.toFixed(2));
      $('#readout').textContent = (fmt(t) + ' / ' + (fmt(duration())) + (seg ? ('  ' + seg.slot.label) : ''));
    }
    requestAnimationFrame(tick);
  }

  function markCurrent() {
    document.querySelectorAll('.seg.cur, .slot.cur, .take.playing').forEach((n) => n.classList.remove('cur', 'playing'));
    if (curSeg) {
      const i = segs.indexOf(curSeg);
      const segEl = document.querySelector(('.seg[data-i="' + i + '"]'));
      if (segEl) segEl.classList.add('cur');
      const slotEl = document.getElementById(('slot-' + curSeg.slot.id));
      if (slotEl) slotEl.classList.add('cur');
      if (curSeg.take) {
        const takeEl = document.getElementById(('take-' + curSeg.slot.id + '-' + curSeg.take.id));
        if (takeEl) takeEl.classList.add('playing');
      }
    }
    drawNow();
  }

  function measurementsEl(list) {
    if (!list || !list.length) return null;
    return h('div', { class: 'meas' }, list.flatMap((m) => [
      h('span', { title: m.note || null }, m.label),
      h('span', null, ('' + m.value + (m.unit ? (' ' + m.unit) : ''))),
      m.series ? spark(m.series) : null,
    ]));
  }
  function spark(s) {
    const ns = 'http://www.w3.org/2000/svg';
    const vals = s.values;
    const lo = Math.min(...vals, s.threshold ?? Infinity);
    const hi = Math.max(...vals, s.threshold ?? -Infinity);
    const y = (v) => (hi === lo ? 14 : 26 - ((v - lo) / (hi - lo)) * 24);
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'spark');
    svg.setAttribute('viewBox', ('0 0 ' + (vals.length - 1) + ' 28'));
    svg.setAttribute('preserveAspectRatio', 'none');
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', vals.map((v, i) => ('' + (i ? 'L' : 'M') + i + ' ' + y(v).toFixed(2))).join(''));
    p.setAttribute('vector-effect', 'non-scaling-stroke');
    svg.append(p);
    if (s.threshold !== undefined) {
      const l = document.createElementNS(ns, 'line');
      Object.entries({ x1: 0, x2: vals.length - 1, y1: y(s.threshold), y2: y(s.threshold), 'vector-effect': 'non-scaling-stroke' }).forEach(([k, v]) => l.setAttribute(k, v));
      svg.append(l);
    }
    return svg;
  }

  function madeWith(t) {
    const bits = [t.made_with.model, t.made_with.tool].filter(Boolean);
    if (typeof t.cost_usd === 'number') bits.push(money(t.cost_usd));
    if (t.made_at) bits.push(t.made_at.replace('T', ' ').replace(/:\d\dZ$|Z$/, ' UTC'));
    if (t.frames && Number.isInteger(t.frames.count)) bits.push((t.frames.count + ' frames'));
    return bits.join(' · ');
  }

  function thumb(t) {
    const path = (t.media && t.media.still) || (t.frames && t.frames.first) || null;
    const box = h('div', { class: 'thumb' });
    const text = t.status === 'failed' ? 'No output'
      : !path && !(t.media && t.media.video) && !t.plays_reference ? 'No media file'
        : t.public ? 'Media not loaded' : ('Media not shipped. ' + t.public_reason);
    box.append(text);
    if (path && (media.active() || !path.startsWith('media/'))) {
      media.when(path).then((url) => { if (url) box.replaceChildren(h('img', { src: url, alt: t.label, loading: 'lazy' })); });
    }
    return box;
  }

  function picksOf(slotId, takeId) {
    return doc.checkpoints.filter((c) => c.picks && c.picks[slotId] === takeId).map((c) => c.id);
  }

  function takeCard(t, slot) {
    const picks = slot ? picksOf(slot.id, t.id) : [];
    const src = t.source ? extLink(t.source.url, t.source.t, t.source.title ? ('Source: ' + t.source.title + (t.source.t !== undefined ? (' at ' + mmss(t.source.t)) : '')) : ('Source' + (t.source.t !== undefined ? (' at ' + mmss(t.source.t)) : ''))) : null;
    const cuts = t.cuts && t.cuts.length ? h('details', null, h('summary', null, (t.cuts.length + ' cuts inside')),
      h('ol', { class: 'cuts' }, t.cuts.map((c) => h('li', null, (c.t0.toFixed(2) + ' to ' + c.t1.toFixed(2) + ' s '), c.label, ' ',
        c.source ? extLink(c.source.url, c.source.t, c.source.t !== undefined ? ('watch at ' + mmss(c.source.t)) : 'watch') : null)))) : null;
    const node = h('article', { class: ('take' + (slot && cp().picks && cp().picks[slot.id] === t.id ? ' pick' : '')), id: slot ? ('take-' + slot.id + '-' + t.id) : null },
      thumb(t),
      h('div', { class: 'head' }, h('span', { class: 'label' }, t.label), statusChip(t.status)),
      h('div', { class: 'meta' }, madeWith(t) || null),
      picks.length ? h('div', { class: 'meta' }, ('Picked at ' + picks.join(', '))) : null,
      t.used_by && t.used_by.length ? h('div', { class: 'meta' }, ('Feeds ' + (t.used_by.map((id) => (slotById.get(id) || { label: id }).label).join(', ')))) : null,
      t.why ? h('p', { class: 'why' }, t.why) : null,
      measurementsEl(t.measurements),
      cuts,
      t.prompt ? h('details', null, h('summary', null, 'Prompt'), h('pre', null, t.prompt)) : null,
      h('div', { class: 'actions' },
        slot ? h('button', { type: 'button', onclick: () => playTake(slot, t) }, 'Play') : null,
        t.prompt_file && !t.prompt_file.startsWith('media/') ? h('a', { href: t.prompt_file, class: 'small' }, 'Prompt file') : null,
        src ? h('span', { class: 'small' }, src) : null,
        t.media && t.media.link ? extLink(t.media.link, undefined, 'Link') : null,
        h('span', { class: 'small muted', title: t.public_reason }, t.public ? 'media may ship' : 'media private')));
    return node;
  }

  function renderSlots() {
    const inCp = new Map(segs.map((s) => [s.slot.id, s]));
    $('#slots').replaceChildren(...slotOrder.map((slot) => {
      const seg = inCp.get(slot.id);
      const [t0, t1] = seg ? [seg.t0, seg.t1] : [slot.t0, slot.t1];
      const cost = slot.takes.reduce((a, t) => a + (t.cost_usd || 0), 0);
      const ref = doc.clock.kind === 'reference' && doc.clock.reference && doc.clock.reference.url;
      const src = slot.source ? extLink(slot.source.url, slot.source.t, 'Watch the reference here') : ref ? extLink(ref, (doc.clock.reference.offset_s || 0) + t0, 'Watch the reference here') : null;
      return h('details', { class: ('slot' + (seg ? '' : ' absent')), id: ('slot-' + slot.id), open: true },
        h('summary', null,
          h('span', { class: 't' }, (t0.toFixed(2) + ' to ' + t1.toFixed(2) + ' s')),
          h('span', { class: 'name' }, slot.label),
          h('span', { class: ('v v-' + slot.verdict) }, VERDICTS[slot.verdict]),
          slot.section ? h('span', { class: 'muted small' }, slot.section) : null,
          h('span', { class: 'muted small' }, (slot.takes.length + ' take' + (slot.takes.length === 1 ? '' : 's') + (cost ? (', ' + money(cost) + ' logged') : ''))),
          seg ? null : h('span', { class: 'muted small' }, 'not in this checkpoint')),
        h('div', { class: 'slot-body' },
          slot.note || src ? h('p', { class: 'small' }, slot.note || '', slot.note && src ? ' ' : '', src) : null,
          h('div', { class: 'takes' }, slot.takes.map((t) => takeCard(t, slot)))));
    }));
    const assets = doc.assets || [];
    $('#assets-wrap').hidden = !assets.length;
    $('#assets').replaceChildren(...assets.map((a) => takeCard(a, null)));
  }

  function renderTimeline() {
    const d = duration();
    const pct = (t) => (((t / d) * 100) + '%');
    $('#sections').replaceChildren(...sections().map((s) => h('span', { style: ('left:' + pct(s.t0) + ';width:' + pct(s.t1 - s.t0)), title: s.note || s.label }, s.label)));
    const grid = [];
    const { bpm, beat_offset_s: off = 0, beats_per_bar: per = 4 } = doc.clock;
    if (bpm) {
      const bar = (60 / bpm) * per;
      const first = off - Math.floor(off / bar) * bar;
      if (d / bar < 160) for (let t = first; t < d; t += bar) grid.push(h('i', { style: ('left:' + pct(t)) }));
    }
    $('#grid').replaceChildren(...grid);
    $('#segments').replaceChildren(...segs.map((s, i) => h('div', {
      class: ('seg v-' + s.slot.verdict + (s.over ? ' over' : '') + (s.take ? '' : ' none')),
      'data-i': i,
      style: ('left:' + pct(s.t0) + ';width:' + pct(s.t1 - s.t0)),
      title: (s.slot.label + ': ' + (s.take ? s.take.label : 'no record') + ' (' + fmt(s.t0) + ' to ' + fmt(s.t1) + ')'),
    }, s.slot.label)));
    $('#landmarks').replaceChildren(...(doc.clock.landmarks || []).map((l) => h('i', { style: ('left:' + pct(l.t)), title: (l.label + ' at ' + fmt(l.t)) }, l.label)));
    $('#timeline').setAttribute('aria-valuemax', d.toFixed(2));
    const used = [...new Set(doc.slots.map((s) => s.verdict))];
    $('#legend').replaceChildren(...used.map((v) => h('span', null, h('b', { class: ('v-' + v) }), VERDICTS[v])));
  }

  function drawNow() {
    const box = $('#now');
    const seg = curSeg;
    if (!seg) { box.replaceChildren(h('h3', null, 'Between slots'), h('p', { class: 'muted' }, 'Nothing is placed here at this checkpoint.')); return; }
    const t = seg.take;
    const ref = doc.clock.reference;
    const refLink = doc.clock.kind === 'reference' && ref && ref.url ? extLink(ref.url, (ref.offset_s || 0) + seg.t0, 'Watch this moment in the reference') : null;
    const others = seg.slot.takes.length;
    fill(box, 
      h('h3', null, seg.slot.label),
      h('div', { class: 'muted small' }, (fmt(seg.t0) + ' to ' + fmt(seg.t1) + ' · ' + (VERDICTS[seg.slot.verdict]) + ' · ' + others + ' take' + (others === 1 ? '' : 's'))),
      t ? h('dl', null,
        h('dt', null, 'Take'), h('dd', null, t.label, ' ', statusChip(t.status), seg.over ? h('span', { class: 'muted small' }, ' (your pick)') : null),
        madeWith(t) ? [h('dt', null, 'Made with'), h('dd', null, madeWith(t))] : null,
        t.why ? [h('dt', null, 'Why'), h('dd', null, t.why)] : null,
        t.source ? [h('dt', null, 'Source'), h('dd', null, extLink(t.source.url, t.source.t, t.source.title || 'Watch'))] : null)
        : h('p', { class: 'muted' }, seg.unrecorded ? 'This checkpoint kept no per-slot record.' : 'No take picked.'),
      t ? measurementsEl(t.measurements) : null,
      seg.slot.note ? h('p', { class: 'small' }, seg.slot.note) : null,
      refLink ? h('p', { class: 'small' }, refLink) : null,
      h('p', null, h('a', { href: ('#slot-' + seg.slot.id), class: 'small' }, 'Every take for this slot')));
  }

  function renderCheckpoints() {
    $('#cp').replaceChildren(...doc.checkpoints.map((c, i) => h('option', { value: i }, ('' + c.label + (i === doc.checkpoints.length - 1 && !/shipped/i.test(c.label) ? ' (shipped)' : '')))));
    $('#cps').replaceChildren(
      h('thead', null, h('tr', null, h('th', null, 'Checkpoint'), h('th', null, 'When'), h('th', null, 'Picks'), h('th', null, 'Notes'))),
      h('tbody', null, doc.checkpoints.map((c, i) => h('tr', { class: i === cpIndex ? 'cur' : '' },
        h('td', null, h('button', { type: 'button', onclick: () => selectCheckpoint(i) }, c.label)),
        h('td', { class: 'small' }, c.at || ''),
        h('td', { class: 'small' }, c.picks ? (Object.keys(c.picks).length + ' slots') : 'not recorded per slot'),
        h('td', { class: 'small' }, c.note, c.render && c.render.link ? [' ', extLink(c.render.link, undefined, 'Watch it')] : null,
          c.measurements ? measurementsEl(c.measurements) : null)))));
  }

  function selectCheckpoint(i) {
    cpIndex = clamp(i, 0, doc.checkpoints.length - 1);
    overrides.clear();
    const c = cp();
    $('#cp-when').textContent = c.at || '';
    $('#cp-note').textContent = c.note;
    const facts = [];
    if (!c.picks) facts.push('This checkpoint kept no per-slot record, so its slots show placeholders until you pick takes.');
    if (c.duration_s) facts.push(('Runs ' + fmt(c.duration_s) + ' on its own clock.'));
    if (c.render) facts.push(('Render: ' + (c.render.label || c.render.media) + '.'));
    fill($('#cp-meta'), facts.join(' '), c.render && c.render.link ? [' ', extLink(c.render.link, undefined, 'Watch the posted cut')] : '');
    $('#mode-render').disabled = !c.render;
    if (!c.render && mode === 'render') setMode('picks');
    if (clock.time() > duration()) clock.seek(0);
    refresh();
    setupAudio();
    renderCheckpoints();
    $('#cp').value = String(cpIndex);
  }
  function refresh() {
    buildSegments();
    renderTimeline();
    renderSlots();
    curSeg = undefined;
    $('#clear').hidden = overrides.size === 0;
  }
  function setMode(m) {
    mode = m;
    $('#mode-picks').classList.toggle('on', m === 'picks');
    $('#mode-render').classList.toggle('on', m === 'render');
    const r = cp().render;
    if (m === 'render' && r && (media.active() || !r.media.startsWith('media/'))) {
      media.when(r.media).then((url) => {
        const opt = [...$('#audio').options].find((o) => o.value === 'render');
        if (opt) opt.disabled = !url;
      });
    }
  }
  function playTake(slot, take) {
    const c = cp();
    if (c.picks && c.picks[slot.id] === take.id) overrides.delete(slot.id);
    else overrides.set(slot.id, take.id);
    setMode('picks');
    refresh();
    const seg = segs.find((s) => s.slot.id === slot.id);
    if (seg) clock.seek(seg.t0 + 0.001);
    $('#stage').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function showTotals() {
    const takes = doc.slots.flatMap((s) => s.takes);
    const by = {};
    for (const t of takes) by[t.status] = (by[t.status] || 0) + 1;
    const cost = [...takes, ...(doc.assets || [])].reduce((a, t) => a + (t.cost_usd || 0), 0);
    const parts = [(doc.slots.length + ' slots'), (takes.length + ' takes (' + (Object.entries(by).map(([k, n]) => (n + ' ' + k)).join(', ')) + ')')];
    if (doc.assets && doc.assets.length) parts.push((doc.assets.length + ' off-clock takes'));
    parts.push((doc.checkpoints.length + ' checkpoints'));
    if (cost) parts.push((money(cost) + ' generation cost logged'));
    const ref = doc.clock.reference;
    const clockText = { reference: 'the reference edit', song: 'the song', voiceover: 'the voiceover' }[doc.clock.kind];
    const about = [ref ? ref.title + (ref.artist ? ' by ' + ref.artist : '') : '', doc.clock.bpm ? doc.clock.bpm + ' BPM' : ''].filter(Boolean).join(', ');
    parts.push('clock: ' + clockText + (about ? ' (' + about + ')' : ''));
    fill($('#totals'), parts.join(' · '), ref && ref.url ? [' · ', extLink(ref.url, ref.offset_s, 'listen')] : '');
  }
  function showMediaStatus() {
    const s = $('#media-status');
    if (!media.active()) { s.textContent = 'No media loaded: the page shows data and placeholders. Open it with ?media=<folder> beside the page, or load your own folder, to play the takes you rebuilt.'; return; }
    const from = media.files ? 'your folder' : ('?media=' + media.base);
    s.textContent = ('Media from ' + from + ': ' + media.found + ' found, ' + media.missing + ' missing so far.');
  }

  function seekFromPointer(e) {
    const r = $('#timeline').getBoundingClientRect();
    clock.seek(((e.clientX - r.left) / r.width) * duration());
  }
  function wire() {
    $('#play').onclick = () => (clock.playing ? clock.pause() : clock.play());
    $('#cp').onchange = (e) => selectCheckpoint(Number(e.target.value));
    $('#mode-picks').onclick = () => { setMode('picks'); clock.play(); };
    $('#mode-render').onclick = () => { setMode('render'); clock.play(); };
    $('#clear').onclick = () => { overrides.clear(); refresh(); };
    const tl = $('#timeline');
    tl.addEventListener('pointerdown', (e) => { tl.setPointerCapture(e.pointerId); seekFromPointer(e); });
    tl.addEventListener('pointermove', (e) => { if (e.buttons) seekFromPointer(e); });
    $('#open-media').onchange = (e) => {
      if (!e.target.files.length) return;
      media.useFolder(e.target.files);
      showMediaStatus();
      refresh();
      setupAudio();
    };
    document.addEventListener('keydown', (e) => {
      if (e.target.closest('input, select, textarea, button, summary')) return;
      if (e.key === ' ') { e.preventDefault(); $('#play').click(); return; }
      const t = clock.time();
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const i = segs.findIndex((s) => t >= s.t0 && t < s.t1);
        const n = e.key === 'ArrowRight' ? segs.findIndex((s) => s.t0 > t + 0.002) : Math.max(0, (i < 0 ? segs.filter((s) => s.t1 <= t).length : i) - 1);
        if (n >= 0 && segs[n]) clock.seek(segs[n].t0 + 0.001);
      } else if (/^[1-9]$/.test(e.key) && curSeg) {
        const take = curSeg.slot.takes[Number(e.key) - 1];
        if (take) playTake(curSeg.slot, take);
      }
    });
  }

  function start(data) {
    doc = data;
    if (!doc || doc.schema !== 'reel-storyboard/1' || !Array.isArray(doc.slots) || !Array.isArray(doc.checkpoints)) {
      throw new Error('This file is not a reel-storyboard/1 document.');
    }
    document.title = doc.title;
    $('#title').textContent = doc.title;
    $('#summary').textContent = doc.summary || '';
    if (doc.aspect) $('#stage').style.aspectRatio = doc.aspect.replace(':', ' / ');
    if (doc.aspect && /^\d+:\d+$/.test(doc.aspect)) {
      const [w, hgt] = doc.aspect.split(':').map(Number);
      if (hgt > w) $('#stage').style.maxWidth = ((Math.round((70 * w) / hgt)) + 'vh');
    }
    slotById.clear();
    doc.slots.forEach((s) => slotById.set(s.id, s));
    const warnings = [];
    for (const c of doc.checkpoints) {
      for (const [sid, tid] of Object.entries(c.picks || {})) {
        const slot = slotById.get(sid);
        if (!slot || !takeOf(slot, tid)) { warnings.push((c.label + ' picks ' + sid + '/' + tid + ', which is not in the data.')); delete c.picks[sid]; }
      }
    }
    $('#warnings').textContent = warnings.join(' ');
    $('#app').hidden = false;
    $('#drop').hidden = true;
    showTotals();
    showMediaStatus();
    selectCheckpoint(doc.checkpoints.length - 1);
  }
  function fail(msg) {
    $('#error').hidden = false;
    $('#error').textContent = msg;
  }
  function offerOpen(msg) {
    $('#drop').hidden = false;
    $('#drop-msg').textContent = msg;
    const read = (file) => file.text().then((s) => start(JSON.parse(s))).catch((e) => fail(('Could not read ' + file.name + ': ' + e.message)));
    $('#open-data').onchange = (e) => e.target.files[0] && read(e.target.files[0]);
    const zone = $('#drop');
    zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('over'); };
    zone.ondragleave = () => zone.classList.remove('over');
    zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove('over'); if (e.dataTransfer.files[0]) read(e.dataTransfer.files[0]); };
  }

  wire();
  requestAnimationFrame(tick);
  const dataPath = params.get('data') || 'storyboard.json';
  if (/^[a-z]+:|^\/\/|\.\./i.test(dataPath)) {
    offerOpen('The data path must be relative to this page. Open a storyboard.json instead.');
  } else {
    fetch(dataPath, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error((dataPath + ' returned ' + r.status)))))
      .then((d) => { try { start(d); } catch (e) { fail(e.message); } })
      .catch((e) => offerOpen(('Could not load ' + dataPath + ' (' + e.message + '). Serve this folder over HTTP, or open the file here.')));
  }
})();
