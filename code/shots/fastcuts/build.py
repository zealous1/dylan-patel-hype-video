# Builds the podcast hype section from edl.json.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/fastcuts/build.py [edl file] [--fps 60]
# --fps 60 renders every 60 fps frame: the zoom, crops, tags, whips and flashes are computed per output frame, cuts land
# on the 30 fps cut times, and footage frames come from each source at its own rate, with in-betweens only inside one
# clip under master/render60.py's per-pair rule. It writes <output>-60.mp4 and jensen-zoom-60.mp4.
# (OpenCV 5 dropped the Haar face detector that tag placement uses.)
# Writes out/<section.output> and out/jensen-zoom.mp4 (the Jensen slot alone).
# edl-v15a.json to edl-v15d.json are the podcast lab's variants (lab/index.html, written by lab/make_edls.py); they
# write fastcuts-v15<x>.mp4 and lab/data/path-fastcuts-v15<x>.json and leave jensen-zoom.mp4 alone.
# edl-v16-b2.json (B with the Jensen slot face-matched) and edl-v16-p1.json to edl-v16-p4.json (B2 with the pop
# treatments, on mattes from lab/matte.py) write fastcuts-v16-<x>.mp4 the same way.
# edl.json is v14 (fastcuts-v14.mp4: the channel name raised, the query right-aligned under it). edl-v13.json rebuilds
# v13 (the query bottom left, the channel name big bottom right, both desaturated and pinned). edl-v12.json rebuilds v12 (the query line desaturated, placed per shot in its quietest corner; choices in
# out/fastcuts-v12-tags.json). edl-v11.json rebuilds v11 (no source tags). edl-v10.json rebuilds v10 (speaker name in
# SemiAnalysis orange, query in SemiAnalysis blue). edl-v9.json rebuilds v9 (eased pans, query pinned into each shot). edl-v8.json rebuilds v8 (bottom-left HUD, filter first). edl-v7.json rebuilds v7 (query first). edl-v6.json rebuilds v6 (NVIDIA beats
# back to back, query plus result row held top left). edl-v5.json rebuilds v5
# (the typed query pinned into each shot), edl-v4.json rebuilds v4 (three-line tags).
# edl-v3.json, edl-v2.json and edl-v1.json rebuild the older takes.
# ffmpeg decodes each span and encodes the result; numpy and OpenCV do the grade, punch-ins, whips,
# flashes, shake and the zoom blur (each Jensen frame averages 10 crops across its shutter).
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, math, os, re, subprocess, sys
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, '..', '..'))
W, H = 1920, 1080
ARGS = sys.argv[1:]
FPS = int(ARGS.pop(ARGS.index('--fps') + 1)) if '--fps' in ARGS else 30
ARGS = [a for a in ARGS if a != '--fps']
S = FPS // 30  # output frames per 30 fps frame; times written in frames below are 30 fps frames
assert FPS in (30, 60)
edl = json.load(open(os.path.join(HERE, ARGS[0] if ARGS else 'edl.json')))
T0 = edl['section']['t0']
NF = edl['section']['frames'] * S
SRC = edl['sources']
fi30 = lambda s: int(round(s * 30))
fi = lambda s: fi30(s) * S
if S > 1:
    assert edl['section'].get('tag_style') == 'pinned-query' and edl['section'].get('whip') == 'eased' and edl['section'].get('open') == 'hard', \
        '--fps 60 covers the v12 to v14 sections only'
    sys.path.insert(0, os.path.join(R, 'master'))
    import render60

# Target look per frame, sampled from the original over the same span (signalstats, limited range).
orig = {round(f['t'] * 30): f for f in json.load(open(os.path.join(R, 'analysis', 'frames.json')))}
def target(slot_in, slot_out):
    ys, ss = [], []
    for i in range(fi30(T0 + slot_in), fi30(T0 + slot_out)):
        f = orig.get(i)
        if f and f['y'] < 110:  # leave the flash frames out of the average
            ys.append(f['y']); ss.append(f['sat'])
    y = max((np.mean(ys) - 16) * 255 / 219, 52)  # faces need more light than the original's black arena
    s = np.mean(ss) * 255 / 224
    return y, s

def decode(path, t, n, fps=FPS, w=W, h=H):
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', str(n),
           '-vf', f'fps={fps},scale={w}:{h}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    if len(fr) < n:
        fr = np.concatenate([fr, np.repeat(fr[-1:], n - len(fr), 0)])
    return fr

def native_fps(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path],
                       capture_output=True, text=True, check=True).stdout.strip().split('/')
    return int(r[0]) / int(r[1])

def footage(path, t, n):
    """n output frames from t. At 60 fps the source is read at its own rate and resampled under the per-pair rule."""
    if S == 1:
        return decode(path, t, n)
    rate = native_fps(path)
    pos = [i * rate / FPS for i in range(n)]
    src = decode(path, t, int(pos[-1]) + 2, fps=rate)
    return render60.sample(src, pos)

def crop_origin(cx, cy, z):
    cw, ch = W / z, H / z
    return min(max(cx * W - cw / 2, 0), W - cw), min(max(cy * H - ch / 2, 0), H - ch)

def crop_resize(img, cx, cy, z):
    x0, y0 = crop_origin(cx, cy, z)
    M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

# Source tag: three lines of white Inter Display at 80% opacity, lower left. It is pinned into the clip's source
# frame (placed where the lower left of the first framed frame falls), so it punches in with the shot, then
# gets the same whips and flashes. It is drawn once at output size and warped straight to each frame, so it stays
# sharp, and it is composited after the grade so the grade's gamma and vignette do not dim it.
TAG_X, TAG_BOTTOM = 124, 92  # the 7% push-in carries it out to about 60 px by the end of the beat
PUSH = 0.07
def render_tag(lines):
    # Inter Display has no emoji glyphs; a title's leading emoji (TBPN's) is left out of the drawn text only.
    lines = [''.join(ch for ch in t if ord(ch) <= 0xFFFF and ch != '\ufe0f').strip() for t in lines]
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    faces = [ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Medium.ttf'), 30),
             ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Regular.ttf'), 25), ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Regular.ttf'), 23)]
    pad, gap = 12, 9
    sizes = [f.getbbox(t) for f, t in zip(faces, lines)]
    tw = max(b[2] for b in sizes) + 2 * pad
    th = sum(f.size for f in faces) + gap * 2 + 2 * pad
    text = Image.new('L', (tw, th), 0)
    d = ImageDraw.Draw(text)
    y = pad
    for f, t in zip(faces, lines):
        d.text((pad, y), t, font=f, fill=255)
        y += f.size + gap
    a = np.asarray(text, np.float32) / 255
    shadow = np.asarray(text.filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
    alpha = np.clip(a * 0.8 + shadow * 0.45 * (1 - a * 0.8), 0, 1)
    rgb = np.where(alpha > 0, (a * 0.8) / np.maximum(alpha, 1e-4), 0) * 255
    return np.dstack([rgb, rgb, rgb, alpha * 255]).astype(np.float32)

def tag_frame(tag, c, z):
    # Where the tag sits in source pixels, from the first frame's framing.
    z0 = c['zoom']
    x0, y0 = crop_origin(c['cx'], c['cy'], z0)
    sx, sy = x0 + TAG_X / z0, y0 + (H - TAG_BOTTOM - tag.shape[0]) / z0
    xf, yf = crop_origin(c['cx'], c['cy'], z)
    k = z / z0
    M = np.float32([[k, 0, z * (sx - xf)], [0, k, z * (sy - yf)]])
    return cv2.warpAffine(tag, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))

# Query tag (v5): the search types out top left in Inter Display with a matrix green keyword and cursor, then the
# result row lands under it. Each frame's layer is drawn at frame 0's framing and warped with the push-in.
GREEN, WHITE = (0, 255, 65), (255, 255, 255)
# SemiAnalysis orange and blue, sampled from the mark (refs/logo/mark.png).
SA_ORANGE, SA_BLUE = (247, 176, 65), (11, 134, 209)
MONO = (214, 214, 214)
QX, QY = 110, 104
TYPE_FRAMES, ROW_AT = 5, 6
def display_font(weight, size):
    from PIL import ImageFont
    return ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), f'InterDisplay-{weight}.ttf'), size)

def query_parts(c):
    p = c['provenance']
    q, r = p['input']['query'], p['result']
    if p['input'].get('speakerIds'):
        # The speaker's name is the one the provenance's filter names beside the id ("by (speakerIds) = ent_14 Name").
        m = re.search(r'speakerIds\) = \S+ ([^;,]+)', p.get('filter', ''))
        filt = ('speaker', m.group(1).strip() if m else 'Dylan Patel')
    else:
        filt = ('channel', r['channel_name'])
    if HUD.get('lower'):  # Zeal, 2026-10-17: everything inside the on-screen search is lowercase
        q, filt = q.lower(), (filt[0], filt[1].lower())
    if HUD.get('mono'):
        return [(f'arcmira.search({filt[0]}: "{filt[1]}", query: ', MONO, 'Medium'), (f'"{q}"', WHITE, 'Bold'), (')', MONO, 'Medium')]
    if HUD.get('sa_colours'):
        name = SA_ORANGE if filt[0] == 'speaker' else WHITE
        return [(f'arcmira.search({filt[0]}: ', WHITE), (f'"{filt[1]}"', name), (', query: ', WHITE), (f'"{q}"', SA_BLUE), (')', WHITE)]
    if HUD.get('filter_first'):
        return [(f'arcmira.search({filt[0]}: "{filt[1]}", query: ', WHITE), (f'"{q}"', GREEN), (')', WHITE)]
    return [('arcmira.search(', WHITE), (f'"{q}"', GREEN), (f', {filt[0]}: "{filt[1]}")', WHITE)]

def hms(s):
    h, m = divmod(int(s), 3600)
    return f'{h}:{m // 60:02d}:{m % 60:02d}' if h else f'{m // 60}:{m % 60:02d}'

def query_layers(c, n):
    from PIL import Image, ImageDraw, ImageFilter
    fq, fr, fb = display_font('Medium', 46), display_font('Regular', 36), display_font('Bold', 36)
    parts = query_parts(c)
    total = sum(len(t) for t, _ in parts)
    r = c['provenance']['result']
    kw = c['provenance']['input']['query'].lower()
    quote = f'"{c["quote"]}"'
    k = quote.lower().find(kw)
    qparts = [(quote, WHITE)] if k < 0 else [(quote[:k], WHITE), (quote[k:k + len(kw)], GREEN), (quote[k + len(kw):], WHITE)]
    row = [('>   ', GREEN, fr), (r['channel_name'], WHITE, fb), (f'   {hms(r["start_seconds"])}   ', WHITE, fr)] + [(t, col, fr) for t, col in qparts]
    out = []
    for i in range(n):
        ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov)
        shown = total if i >= TYPE_FRAMES - 1 else math.ceil(total * (i + 1) / TYPE_FRAMES)
        x, left = QX, shown
        for t, col in parts:
            t = t[:left]; left -= len(t)
            d.text((x, QY), t, font=fq, fill=col + (204,)); x += d.textlength(t, font=fq)
        if i < TYPE_FRAMES or (i // 3) % 2 == 0:
            d.rectangle((x + 6, QY + 4, x + 6 + fq.size * 0.5, QY + fq.size * 1.02), fill=GREEN + (204,))
        if i >= ROW_AT:
            a = min(1, 0.5 * (i - ROW_AT + 1))
            x, y = QX, QY + 68 + 10 * (1 - a)
            for t, col, f in row:
                d.text((x, y), t, font=f, fill=col + (int(204 * a),)); x += d.textlength(t, font=f)
        sh = ov.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda p: min(255, p * 0.75))
        base = Image.new('RGBA', (W, H)); base.putalpha(sh); base.alpha_composite(ov)
        out.append(np.asarray(base, np.float32)[..., [2, 1, 0, 3]])
    return out

# HUD tag (v6): the same search held still top left over the cuts. On each cut the result row rolls up and out
# while the next rolls in; a changed query backspaces to the shared prefix and retypes.
HUD = edl['section'].get('hud', {})
HX, ROW_DY, ROLL = 80, 70, 3
HY = H - 72 - 50 if HUD.get('at') == 'bottom-left' else 72
def query_chars(c):
    return [(ch, col) for t, col in query_parts(c) for ch in t]

def row_runs(c):
    fr, fb = display_font('Regular', 36), display_font('Bold', 36)
    r = c['provenance']['result']
    kw = c['provenance']['input']['query'].lower()
    quote = f'"{c["quote"]}"'
    k = quote.lower().find(kw)
    qparts = [(quote, WHITE)] if k < 0 else [(quote[:k], WHITE), (quote[k:k + len(kw)], GREEN), (quote[k + len(kw):], WHITE)]
    return [('>   ', GREEN, fr), (r['channel_name'], WHITE, fb), (f'   {hms(r["start_seconds"])}   ', WHITE, fr)] + [(t, col, fr) for t, col in qparts]

def hud_layers(beats):
    from PIL import Image, ImageDraw, ImageFilter
    fq = display_font('Medium', 46)
    # A soft dark corner behind the HUD so white text holds on bright sets.
    SCRIM = 150 * np.clip(1 - np.hypot(xx / 1500, (yy - HY - 25) / 200), 0, 1) ** 1.5
    ease = lambda u: 1 - (1 - min(max(u, 0), 1)) ** 3
    state = {}  # frame -> (chars, [(clip, dy, alpha)])
    for b, (f0, f1, c) in enumerate(beats):
        new = query_chars(c)
        prev = beats[b - 1] if b and beats[b - 1][1] == f0 else None
        old = query_chars(prev[2]) if prev else []
        same = prev and [ch for ch, _ in old] == [ch for ch, _ in new]
        L = 0
        while L < min(len(old), len(new)) and old[L][0] == new[L][0]:
            L += 1
        S = 0
        while S < min(len(old), len(new)) - L and old[-1 - S][0] == new[-1 - S][0]:
            S += 1
        om, nm = old[L:len(old) - S], new[L:len(new) - S]
        back, typ = (0, 0) if same else ((2, 3) if prev else (0, TYPE_FRAMES))
        row_in = 0 if same else back + typ
        for i in range(f1 - f0):
            if not prev and i < typ:
                chars = new[:math.ceil(len(new) * (i + 1) / typ)]
                at = len(chars)
            elif i < back:
                k = len(om) - math.ceil(len(om) * (i + 1) / back)
                chars, at = old[:L + k] + new[len(new) - S:], L + k
            elif i < back + typ:
                k = math.ceil(len(nm) * (i - back + 1) / typ)
                chars, at = new[:L + k] + new[len(new) - S:], L + k
            else:
                chars, at = new, len(new)
            rows = []
            if prev and i < ROLL:
                e = ease((i + 1) / ROLL)
                rows.append((prev[2], -ROW_DY * 0.7 * e, 1 - e))
            if i >= row_in:
                e = ease((i - row_in + 1) / ROLL)
                rows.append((c, ROW_DY * 0.7 * (1 - e), e))
            state[f0 + i] = (chars, at, rows, i < back + typ or (i // 3) % 2 == 0)
    out = {}
    for f, (chars, at, rows, cur) in state.items():
        ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov)
        x, cx = HX, HX
        for j, (ch, col) in enumerate(chars):
            if j == at and cur:
                cx = x; x += fq.size * 0.5 + 12
            d.text((x, HY), ch, font=fq, fill=col + (204,)); x += d.textlength(ch, font=fq)
        if cur:
            cx = x if at >= len(chars) else cx
            d.rectangle((cx + 6, HY + 4, cx + 6 + fq.size * 0.5, HY + fq.size * 1.02), fill=GREEN + (204,))
        band = Image.new('RGBA', (W, ROW_DY)); bd = ImageDraw.Draw(band)
        for c, dy, a in (rows if HUD.get('rows', True) else []):
            x = HX
            for t, col, fnt in row_runs(c):
                bd.text((x, 8 + dy), t, font=fnt, fill=col + (int(204 * a),)); x += bd.textlength(t, font=fnt)
        ov.alpha_composite(band, (0, HY + ROW_DY - 8))
        sh = ov.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda p: min(255, p * 0.75))
        a = np.maximum(np.asarray(sh, np.float32), SCRIM)
        base = Image.new('RGBA', (W, H)); base.putalpha(Image.fromarray(a.astype(np.uint8))); base.alpha_composite(ov)
        out[f] = np.asarray(base, np.float32)[..., [2, 1, 0, 3]]
    return out

# Pinned query (v9): the query line alone, drawn once bottom left at frame 0's framing, wiped in left to right
# over its first frames, then carried by the push-in, pans, flashes and shake like the rest of the shot.
WIPE = 4
def static_query(c, at=None):
    from PIL import Image, ImageDraw, ImageFilter
    x0, y0 = at or (HX, HY)
    ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov)
    x = x0
    for part in query_parts(c):
        t, col, wt = part if len(part) == 3 else (*part, 'Medium')
        f = display_font(wt, 46)
        d.text((x, y0), t, font=f, fill=col + (204,)); x += d.textlength(t, font=f)
    sh = ov.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda p: min(255, p * 0.75))
    base = Image.new('RGBA', (W, H)); base.putalpha(sh); base.alpha_composite(ov)
    return np.asarray(base, np.float32)[..., [2, 1, 0, 3]], x, x0

def query_width(c):
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    return sum(d.textlength(p[0], font=display_font(p[2] if len(p) == 3 else 'Medium', 46)) for p in query_parts(c))

# Per-shot placement (v12): the quietest of six anchors on the shot's first framed frame, never over a face
# and never on a bright patch, unless the clip names its own tag_at [x, y].
FACES = None
PLACED = {}
def place(c, frame):
    global FACES
    if c.get('tag_at'):
        return tuple(c['tag_at']), 'set'
    if FACES is None:
        FACES = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml')]
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (W // 2, H // 2))
    faces = [tuple(int(v) * 2 for v in r) for cas in FACES for r in cas.detectMultiScale(small, 1.1, 5, minSize=(60, 60))]
    mag = np.abs(cv2.Sobel(g.astype(np.float32), cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g.astype(np.float32), cv2.CV_32F, 0, 1))
    w, h, m = int(query_width(c)) + 40, 90, 100
    cands = {'top-left': (m, m), 'top-right': (W - m - w, m), 'bottom-left': (m, H - m - 50), 'bottom-right': (W - m - w, H - m - 50),
             'top-centre': ((W - w) // 2, m), 'bottom-centre': ((W - w) // 2, H - m - 50)}
    best = None
    for name, (x, y) in cands.items():
        bx0, by0, bx1, by1 = x - 20, y - 20, x + w, y + h
        score = float(mag[by0:by1, bx0:bx1].mean()) + 2 * max(0.0, float(g[by0:by1, bx0:bx1].mean()) - 110)
        for fx, fy, fw, fh in faces:
            if bx0 < fx + fw * 1.3 and fx - fw * 0.3 < bx1 and by0 < fy + fh * 1.5 and fy - fh * 0.3 < by1:
                score += 1000
        if best is None or score < best[0]:
            best = (score, (x + 20, y), name)
    return best[1], best[2]

# Split tag (v13, right-aligned in v14): the query small under the show's channel name, both bottom right; the name big in Inter Display
# ExtraBold, both desaturated and pinned into the shot. The name is the result: it shows whose shows we index.
TAG_FILL = (255, 255, 255, 217)  # one white at 85% for both lines
def split_tag(c):
    from PIL import Image, ImageDraw, ImageFilter
    ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov)
    fq, fqb, fc = display_font('Medium', 30), display_font('Bold', 30), display_font('ExtraBold', HUD.get('name_size', 88))
    parts = [part if len(part) == 3 else (*part, 'Medium') for part in query_parts(c)]
    name = c['provenance']['result']['channel_name'].upper()
    track = 3
    wname = sum(d.textlength(ch, font=fc) + track for ch in name) - track
    right = W - HX
    yq = H - HUD.get('query_bottom', 72)                 # query baseline
    yn = yq - HUD.get('name_gap', 46)                    # channel name baseline, above the query
    xn = right - wname
    for ch in name:
        d.text((xn, yn), ch, font=fc, fill=TAG_FILL, anchor='ls'); xn += d.textlength(ch, font=fc) + track
    wq = sum(d.textlength(t, font=fqb if wt == 'Bold' else fq) for t, _, wt in parts)
    x = right - wq
    for t, _, wt in parts:
        f = fqb if wt == 'Bold' else fq
        d.text((x, yq), t, font=f, fill=TAG_FILL, anchor='ls'); x += d.textlength(t, font=f)
    sh = ov.split()[3].filter(ImageFilter.GaussianBlur(8)).point(lambda p: min(255, p * 0.7))
    base = Image.new('RGBA', (W, H)); base.putalpha(sh); base.alpha_composite(ov)
    return np.asarray(base, np.float32)[..., [2, 1, 0, 3]], W - HX, W - HX - max(wname, wq)

def wipe_in(layer, u):
    img, x1, x0 = layer
    if u >= WIPE:
        return img
    e = 1 - (1 - min((u + 1) / WIPE, 1)) ** 2
    edge = x0 - 40 + (x1 - x0 + 80) * e
    m = np.clip((edge - xx) / 40, 0, 1)
    out = img.copy(); out[..., 3] *= m
    return out

def pinned(layer, c, z):
    z0 = c['zoom']
    x0, y0 = crop_origin(c['cx'], c['cy'], z0)
    xf, yf = crop_origin(c['cx'], c['cy'], z)
    M = np.float32([[z / z0, 0, z * (x0 - xf)], [0, z / z0, z * (y0 - yf)]])
    return cv2.warpAffine(layer, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))

def over(img, layer):
    a = layer[..., 3:4] / 255
    return np.clip(img.astype(np.float32) * (1 - a) + layer[..., :3] * a, 0, 255).astype(np.uint8)

def stats(frames):
    yuv = cv2.cvtColor(np.ascontiguousarray(frames[len(frames) // 2]), cv2.COLOR_BGR2YUV).astype(np.float32)
    y = yuv[..., 0].mean()
    s = np.sqrt((yuv[..., 1] - 128) ** 2 + (yuv[..., 2] - 128) ** 2).mean()
    return y, s

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = 1 - 0.38 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2

def grade(img, gamma, k, contrast=1.18):
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV).astype(np.float32)
    y = yuv[..., 0] / 255
    y = np.clip((y - 0.5) * contrast + 0.5, 0, 1) ** gamma
    yuv[..., 0] = np.clip(y * 255 * VIG, 0, 255)
    yuv[..., 1:] = (yuv[..., 1:] - 128) * k + 128
    return cv2.cvtColor(np.clip(yuv, 0, 255).astype(np.uint8), cv2.COLOR_YUV2BGR)

def pop(img, gamma, k):
    # Section grade, but the jersey's yellow and purple keep most of their colour.
    g = grade(img, gamma, k).astype(np.float32)
    full = grade(img, gamma, 0.9).astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, sat = hsv[..., 0], hsv[..., 1]
    m = (((h >= 18) & (h <= 36)) | ((h >= 122) & (h <= 150))) & (sat > 90)
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3)[..., None]
    return np.clip(g * (1 - m) + full * m, 0, 255).astype(np.uint8)

def look(frames, slot_in, slot_out, kmin=0.06, kmax=1.0, contrast=1.18):
    ty, ts = target(slot_in, slot_out)
    my, ms = stats(frames)
    my = min(max(((my / 255 - 0.5) * contrast + 0.5) * 255, 8), 247)
    gamma = float(np.clip(math.log(max(ty, 8) / 255) / math.log(my / 255), 0.75, 1.6))
    k = float(np.clip(ts / max(ms, 1), kmin, kmax))
    return gamma, k

def sharpen(img, a=0.5):
    b = cv2.GaussianBlur(img, (0, 0), 1.6)
    return cv2.addWeighted(img, 1 + a, b, -a, 0)

def podcast(c):
    if LAB:
        return lab_podcast(c)
    s = SRC[c['src']]
    n = fi(c['slot_out']) - fi(c['slot_in'])
    raw = footage(os.path.join(R, s['file']), c['src_in'], n)
    # Keep the crop off the frame edge through the whole push-in, so it zooms about its centre and the tag
    # drifts the same small amount on every clip.
    zmax = c['zoom'] * (1 + PUSH)
    c = dict(c, cx=min(max(c['cx'], 0.5 / zmax), 1 - 0.5 / zmax), cy=min(max(c['cy'], 0.5 / zmax), 1 - 0.5 / zmax))
    out, zs = [], []
    for i, f in enumerate(raw):
        p = i / max(n - 1, 1)
        zs.append(c['zoom'] * (1 + PUSH * p))
        out.append(sharpen(crop_resize(f, c['cx'], c['cy'], zs[-1]), 0.35))
    gamma, k = look(out[:1] + out, c['slot_in'], c['slot_out'])
    out = [grade(f, gamma, k) for f in out]
    if edl['section'].get('tag_style') == 'hud':
        pass
    elif edl['section'].get('tag_style') == 'pinned-query':
        if HUD.get('split'):
            layer = split_tag(c)
            out = [over(f, pinned(wipe_in(layer, i / S), c, z)) for i, (f, z) in enumerate(zip(out, zs))]
            return out
        at, how = place(c, out[0]) if HUD.get('place') else ((HX, HY), 'fixed')
        PLACED[c['src']] = {'tag_at': [int(at[0]), int(at[1])], 'how': how}
        layer = static_query(c, at)
        out = [over(f, pinned(wipe_in(layer, i / S), c, z)) for i, (f, z) in enumerate(zip(out, zs))]
    elif edl['section'].get('tag_style') == 'query':
        out = [over(f, pinned(l, c, z)) for f, l, z in zip(out, query_layers(c, n), zs)]
    elif c.get('tag') and edl['section'].get('tag_style') != 'none':
        tag = render_tag(c['tag'])
        out = [over(f, tag_frame(tag, c, z)) for f, z in zip(out, zs)]
    return out

def hero(c):
    # Speed ramp through the knots, blending the two nearest source frames, with a slow push-in on the face
    # and a short punch on the kick beat.
    s = SRC[c['src']]
    n = fi(c['slot_out']) - fi(c['slot_in'])
    knots = np.array(c['ramp'])
    raw = decode(os.path.join(R, s['file']), 0, 91, fps=30)
    ts = [float(np.interp(i / FPS, knots[:, 0], knots[:, 1])) * 30 for i in range(n)]
    # At 60 fps the ramp's in-betweens follow the per-pair rule; a RIFE frame that fails the gate falls back to the blend.
    src = render60.sample(raw, [min(t, len(raw) - 1) for t in ts], fallback='blend') if S > 1 else None
    out = []
    for i in range(n):
        if S > 1:
            f = src[i]
        else:
            t = ts[i]
            a = min(int(t), len(raw) - 2); w = t - a
            f = cv2.addWeighted(raw[a], 1 - w, raw[a + 1], w, 0)
        z = c['zoom'][0] + (c['zoom'][1] - c['zoom'][0]) * (i / (n - 1)) ** 1.5
        kd = (i - (c['kick'] - c['slot_in']) * FPS) / S
        if 0 <= kd < 8:
            z *= 1 + 0.06 * math.exp(-kd / 2)
        out.append(sharpen(crop_resize(f, c['cx'], c['cy'], z), 0.4))
    if LAB:
        return lab_hero(c, raw, ts)
    gamma, k = look(out, c['slot_in'], c['slot_out'])
    return [pop(f, gamma, k) for f in out]

# Jensen: 4K60 source, zoom about the belt plate. P is the plate centre in the 4K frame.
P = np.array([1905.0, 280.0])
SW, SH = 3840, 2160
def jensen(c):
    s = SRC[c['src']]
    f0, f1 = fi(c['slot_in']), fi(c['slot_out'])
    n = f1 - f0
    uh = c['hit'] - c['slot_in']        # hit time inside the slot
    ub = c.get('beat2', c.get('reveal')) - c['slot_in']
    end = n / FPS
    def cw(u):  # crop width in 4K pixels
        if u < uh:
            e = (u / uh) ** 3
            return 3840 + (820 - 3840) * e
        if u < uh + 0.13:
            e = 1 - (1 - (u - uh) / 0.13) ** 2
            return 820 + (930 - 820) * e
        if u < ub:
            return 930 + (860 - 930) * (u - uh - 0.13) / (ub - uh - 0.13)
        if u < ub + 0.07:
            e = 1 - (1 - (u - ub) / 0.07) ** 2
            return 860 + (720 - 860) * e
        return 720 + (680 - 720) * (u - ub - 0.07) / (end - ub - 0.07)
    def screen(u):  # where the plate sits on screen, in output pixels
        e = min(u / uh, 1) ** 2
        a = np.array([P[0] / 2, P[1] / 2])
        return a + (np.array([W / 2, H * 0.47]) - a) * e
    def crop(u):  # crop origin and width in 4K pixels
        w = cw(u); h = w * 9 / 16
        sx, sy = screen(u)
        return min(max(P[0] - sx * w / W, 0), SW - w), min(max(P[1] - sy * h / H, 0), SH - h), w
    if c.get('reveal') is not None:
        crop, uh, ub = jensen_b2(c)
    # Stream the 4K frames: decode at full res, keep only what the current output frame needs.
    t_src = c['src_in']
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t_src:.3f}', '-i', os.path.join(R, s['file']),
           '-frames:v', str(int(end * 60) + 4), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    buf, nxt = {}, 0
    def src_frame(j):
        nonlocal nxt
        while nxt <= j:
            b = proc.stdout.read(SW * SH * 3)
            if len(b) < SW * SH * 3:
                break
            buf[nxt] = np.frombuffer(b, np.uint8).reshape(SH, SW, 3)
            nxt += 1
        for k in [k for k in buf if k < j - 1]:
            del buf[k]
        return buf[min(j, nxt - 1)]
    SUB = 10
    out = []
    for i in range(n):
        acc = np.zeros((H, W, 3), np.float32)
        for q in range(SUB):
            u = (i + q / SUB) / FPS
            x0, y0, w = crop(u)
            z = W / w
            M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
            img = src_frame(int(round((t_src + u) * 60 - t_src * 60)))
            acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_AREA if z < 1 else cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REFLECT)
        out.append(sharpen(np.clip(acc / SUB, 0, 255).astype(np.uint8), 0.45))
    proc.stdout.close(); proc.wait()
    # Keep the orange plate readable: less desaturation than the podcast cuts.
    gamma, k = look(out[-3:], c['slot_in'], c['slot_out'], kmin=0.5, kmax=0.6, contrast=1.1)
    out = [grade(f, min(gamma, 1.2), LAB['jensen_k'] if LAB else k, contrast=1.1) for f in out]
    if LAB and c.get('provenance'):
        # The tag holds its size here: scaled by a fifth of a zoom this steep, it shrank toward its right edge fast
        # enough to read as sliding right.
        crops = [crop((i + 0.5) / FPS) for i in range(n)]
        layer = split_tag(c)
        ys, xs = np.nonzero(layer[0][..., 3] > 8)
        bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
        # The tag goes on the first frame its box meets the belt plate's disc (radius 240 4K pixels), and a frame before
        # the hit at the latest, so the slam lands on a clean plate.
        stop = fi(uh) - 1
        for i, (x0, y0, w) in enumerate(crops):
            px, py = (P[0] - x0) * W / w, (P[1] - y0) * W / w
            if math.hypot(px - min(max(px, bx0), bx1), py - min(max(py, by0), by1)) < 240 * W / w:
                stop = min(stop, i)
                break
        JENSEN_TAG.update(last=stop - 1, hit=fi(uh))
        out = [zoom_tag(f, layer, i, 1, 1) if i < stop else f for i, f in enumerate(out)]
    # Hit: shake and chromatic split that decay over 9 frames, plus a smaller kick on the second beat.
    hitF, b2F = fi(uh), fi(ub)
    rng = np.random.default_rng(67)
    def amp_at(i):
        amp = 0
        for kf, a0 in ((hitF, 42), (b2F, 20)):
            d = (i - kf) / S
            if 0 <= d < 9:
                amp = max(amp, a0 * math.exp(-d / 2.5))
        return amp
    # Shake directions are drawn once per 30 fps frame, in the 30 fps order, and eased between at 60 fps.
    unit = {i: rng.uniform(-1, 1, 2) for i in range(0, n, S) if amp_at(i) > 0.5}
    for i in range(n):
        amp = amp_at(i)
        if amp > 0.5:
            a, w = i - i % S, (i % S) / S
            dx, dy = (unit.get(a, np.zeros(2)) * (1 - w) + unit.get(a + S, np.zeros(2)) * w) * amp
            if c.get('reveal') is not None:  # B2: a sideways shake settling back reads as travel to the right
                dx = 0
            M = np.float32([[1.03, 0, dx - W * 0.015], [0, 1.03, dy - H * 0.015]])
            f = cv2.warpAffine(out[i], M, (W, H), borderMode=cv2.BORDER_REFLECT)
            sh = int(amp * 0.4)
            if sh:
                f[..., 0] = np.roll(f[..., 0], -sh, 1)
                f[..., 2] = np.roll(f[..., 2], sh, 1)
            out[i] = f
    return out, hitF, b2F

def whip(img, L, shift, axis):
    M = np.float32([[1, 0, shift], [0, 1, 0]]) if axis == 'h' else np.float32([[1, 0, 0], [0, 1, shift]])
    img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    k = (L, 1) if axis == 'h' else (1, L)
    return cv2.blur(img, k)

# Eased pan (v9), measured from the original's cuts: the camera speeds up over the frames before a cut
# (4, 12, 23, 37, 58, 114 px a frame at 13.84 + 1.37 s) and settles over the frames after, with blur that
# follows the speed, and the landing frames jump and punch in. Offsets and speeds are fractions of the pan axis.
PAN_OUT, PAN_IN, VMAX = 3, 4, 0.2
def pan_profile(into_jensen):
    vel_out = {r: VMAX * ((r + PAN_OUT + 1) / PAN_OUT) ** 2 for r in range(-PAN_OUT, 0)}
    vel_in = {r: VMAX * ((PAN_IN - r) / PAN_IN) ** 2 for r in range(PAN_IN)}
    prof, acc = {}, 0
    for r in range(-PAN_OUT, 0):
        acc += vel_out[r]; prof[r] = (-acc, vel_out[r], 0)
    if not into_jensen:
        for r in range(PAN_IN):
            rest = sum(v for q, v in vel_in.items() if q > r)
            prof[r] = (rest, vel_in[r], math.exp(-r / 1.4))
    return prof

def pan_at(prof, jit, d, into_jensen):
    """The eased pan at d 30 fps frames from the cut, as (offset, speed, punch, jitter); between two 30 fps frames each
    side's curve is eased on its own, so the frames before the cut never borrow the landing's values."""
    if d == int(d):
        r = int(d)
        return (*prof[r], jit.get(r, np.zeros(2))) if r in prof and r in jit else None
    a, b = math.floor(d), math.floor(d) + 1
    if d < 0:
        vel0 = VMAX * ((0 + PAN_OUT + 1) / PAN_OUT) ** 2
        pb = prof[b] if b < 0 else (prof[-1][0] - vel0, vel0, 0)
    elif into_jensen:
        return None
    else:
        pb = prof.get(b, (0, 0, 0))
    if a not in prof:
        return None
    w = d - a
    lerp = lambda x, y: x * (1 - w) + y * w
    return (*(lerp(x, y) for x, y in zip(prof[a], pb)), lerp(jit.get(a, np.zeros(2)), jit.get(b, np.zeros(2))))

def pan(img, off, vel, ax, punch, jit):
    z = 1 + 0.06 * punch
    jx, jy = jit * 26 * punch
    dx, dy = (off, 0) if ax == 'h' else (0, off)
    M = np.float32([[z, 0, (1 - z) * W / 2 + dx + jx], [0, z, (1 - z) * H / 2 + dy + jy]])
    img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    L = int(abs(vel)) | 1
    if L > 2:
        img = cv2.blur(img, (L, 1) if ax == 'h' else (1, L))
    return img

def eased_pan(frames, cf, into_jensen, ax, sg, rng, forward=False):
    span = W if ax == 'h' else H
    prof = pan_profile(into_jensen)
    jit = {r: rng.uniform(-1, 1, 2) for r in prof if 0 <= cf // S + r < NF // S}
    if forward:
        # A decaying shake drifts back toward centre, so any sideways shake reads as a nudge to the right somewhere.
        # On a left pan it is drowned by the pan; a vertical landing keeps its vertical shake only.
        jit = {r: np.array([-abs(j[0]) if ax == 'h' else 0, j[1]]) for r, j in jit.items()}
    for r60 in range(-PAN_OUT * S, PAN_IN * S):
        at = pan_at(prof, jit, r60 / S, into_jensen)
        if at and 0 <= cf + r60 < NF:
            off, vel, pk, j = at
            frames[cf + r60] = pan(frames[cf + r60], sg * off * span, vel * span / S, ax, pk, j)

def white(img, a):
    return np.clip(img.astype(np.float32) * (1 - a) + 255 * a, 0, 255).astype(np.uint8)

def encode(frames, path):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                          '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close(); p.wait()
    assert p.returncode == 0

# Podcast lab (lab/index.html; edl-v15a to v15d). A section with a 'lab' block frames every podcast clip on Dylan's
# tracked face (lab/data/faces.json, from lab/faces.py), names each cut's move by the way the picture travels, and
# uses the subject-aware grade below. A section without one renders exactly as before.
LAB = edl['section'].get('lab')
# A move names the direction the picture travels. Zeal's rule: nothing travels right, since that reads as going back.
MOVES = {'left': ('h', 1), 'right': ('h', -1), 'up': ('v', 1), 'down': ('v', -1)}
V14_MOVES = ['left', 'right', 'up', 'left', 'right', 'down']
if LAB:
    assert S == 1, 'the lab variants are 30 fps only'
    assert 'right' not in LAB['moves'], 'a lab variant never moves the picture right'
    TRACKS = json.load(open(os.path.join(HERE, 'lab', 'data', 'faces.json')))
    CAM = LAB['camera']
ZMAX = 2.6
yy4, xx4 = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)

def face_at(c, i):
    """Dylan's tracked face in source frame i of the clip, as (cx, cy, w, h) in 1920x1080 source pixels."""
    b = TRACKS[c['src']]['boxes']
    b = b[min(max(int(i), 0), len(b) - 1)]
    return np.array([b[0] * W, b[1] * H, b[2] * W, b[3] * H])

def zoom_for(f, h):
    return min(max(h * H / f[3], 1.0), ZMAX)

def fit(f, at, z):
    """Crop origin that puts the face centre on screen point `at` at zoom z, kept inside the source frame."""
    return np.array([min(max(f[0] - at[0] / z, 0), W - W / z), min(max(f[1] - at[1] / z, 0), H - H / z)])

def floor(f, at):
    """The least zoom that puts face f on screen point `at` with the crop inside the source frame."""
    return max(at[0] / f[0], (W - at[0]) / (W - f[0]), at[1] / f[1], (H - at[1]) / (H - f[1]), 1.0)

def meet(faces, h, at):
    """The face height for a matched cut: at least h, and big enough that every given face reaches `at`."""
    return max([h] + [min(floor(f, at), ZMAX) * f[3] / H for f in faces])

def hermite(p0, p1, m0, m1, u):
    return (2 * u ** 3 - 3 * u ** 2 + 1) * p0 + (u ** 3 - 2 * u ** 2 + u) * m0 + (-2 * u ** 3 + 3 * u ** 2) * p1 + (u ** 3 - u ** 2) * m1

def still_face(c):
    """One face position per clip, his mean over the clip. The camera frames on it, so it only zooms or pans; following
    each head bob made the room twitch, sometimes to the right. The grade's light still follows the real head."""
    if c.get('kind') == 'hero':
        return face_at(c, hero_src(c, 0))
    return np.mean([face_at(c, i) for i in range(fi(c['slot_out']) - fi(c['slot_in']))], 0)

def boundaries():
    """Zoom-through: the face's screen height, its log-height speed and its screen point at each clip boundary.
    A matched boundary ('in' or 'out') puts both sides' faces on one point at one height, still zooming."""
    clips, A = edl['clips'], np.array(CAM['anchor']) * [W, H]
    out = []
    for k, spec in enumerate(CAM['cuts']):
        if isinstance(spec, list):
            out.append({'h': spec[0], 'v': spec[1], 'at': np.array(spec[2]) * [W, H] if len(spec) > 2 else A})
            continue
        faces = [still_face(c) for c in clips[max(k - 1, 0):k + 1] if c.get('kind') != 'jensen-zoom']
        out.append({'h': meet(faces, CAM['h'], A), 'v': CAM['v'] * (1 if spec == 'in' else -1), 'at': A})
    return out

def camera(c):
    """Per output frame: crop origin, zoom and the real face in source pixels."""
    n = fi(c['slot_out']) - fi(c['slot_in'])
    T = n / FPS
    faces = [face_at(c, i) for i in range(n)]
    sf = still_face(c)
    mode = CAM['mode']
    if mode == 'v14':
        zmax = c['zoom'] * (1 + PUSH)
        cx, cy = min(max(c['cx'], 0.5 / zmax), 1 - 0.5 / zmax), min(max(c['cy'], 0.5 / zmax), 1 - 0.5 / zmax)
        zs = [c['zoom'] * (1 + PUSH * i / max(n - 1, 1)) for i in range(n)]
        return [(np.array(crop_origin(cx, cy, z)), z, f) for z, f in zip(zs, faces)]
    A = np.array(CAM['anchor']) * [W, H]
    if mode == 'zoomthrough':
        k = [x['src'] for x in edl['clips']].index(c['src'])
        a, b = BOUNDS[k], BOUNDS[k + 1]
        path = []
        for i, f in enumerate(faces):
            u = i / n
            h = math.exp(hermite(math.log(a['h']), math.log(b['h']), a['v'] * T, b['v'] * T, u))
            at = a['at'] + (b['at'] - a['at']) * (3 * u ** 2 - 2 * u ** 3)
            # Never so wide that the crop meets the frame edge: the face would slide sideways, maybe to the right.
            z = min(max(zoom_for(sf, h), floor(sf, at)), ZMAX)
            path.append((fit(sf, at, z), z, f))
        return path
    # 'land' (face-aligned landings, then v14's push about the face) and 'travel' (the camera keeps panning right
    # through every clip at one speed). One zoom per clip, raised until every frame's face point fits in the source.
    if mode == 'land':
        ats = [A] * n
        grow = lambda i: 1 + PUSH * i / max(n - 1, 1)
    else:
        ats = [A + [CAM['speed'] * W * (T / 2 - i / FPS), 0] for i in range(n)]
        grow = lambda i: 1 + CAM['creep'] * i / n
    z0 = min(max([zoom_for(sf, CAM['h'])] + [floor(sf, at) for at in ats]), ZMAX)
    return [(fit(sf, at, z0 * grow(i)), z0 * grow(i), f) for i, (f, at) in enumerate(zip(faces, ats))]

def crop_to(img, o, z):
    M = np.float32([[z, 0, -o[0] * z], [0, z, -o[1] * z]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

def zoom_blur(img, at, amount, k=7):
    """Radial blur about `at`: the mean of k scalings from 1 to 1 + amount, as a fast zoom smears."""
    acc = np.zeros(img.shape, np.float32)
    for j in range(k):
        s = 1 + amount * j / (k - 1)
        M = np.float32([[s, 0, (1 - s) * at[0]], [0, s, (1 - s) * at[1]]])
        acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return (acc / k).astype(np.uint8)

def person_mask(box):
    """Head and shoulders from the face box, feathered by half a face width: the lift reads as light falling on him,
    and no edge is sharp enough to halo."""
    cx, cy, w, h = np.asarray(box, np.float32) / 4
    head = ((xx4 - cx) / (0.9 * w)) ** 2 + ((yy4 - cy + 0.1 * h) / (1.05 * h)) ** 2 < 1
    body = ((xx4 - cx) / (2.1 * w)) ** 2 + ((yy4 - cy - 2.0 * h) / (1.6 * h)) ** 2 < 1
    m = cv2.GaussianBlur((head | body).astype(np.float32), (0, 0), max(0.5 * w, 2))
    return cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)

def to_lab(img):
    return cv2.cvtColor(img.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)

def subject_params(img, box):
    """Per-clip grade from its middle frame: lift the face to the original's lit-subject level, pull the room down a
    little, warm the neutrals off the podcasts' green cast, and bring chroma up to the original's lit vividness."""
    col = LAB['colour']
    lab = to_lab(img)
    L = np.clip((lab[..., 0] / 100 - 0.5) * col['contrast'] + 0.5, 1e-3, 1)
    a, b = lab[..., 1], lab[..., 2]
    C = np.hypot(a, b)
    m = person_mask(box) > 0.5
    cx, cy, w, h = box
    face = np.zeros(m.shape, bool)
    face[int(cy - h * 0.35):int(cy + h * 0.35), int(cx - w * 0.3):int(cx + w * 0.3)] = True
    Lf, Lb = float(L[face].mean()), float(L[~m].mean())
    neutral = (C < 10) & (L > 0.2) & (L < 0.95)
    na, nb = (float(a[neutral].mean()), float(b[neutral].mean())) if neutral.sum() > 1000 else (0.0, 0.0)
    Cp = float(C[m & (L > 0.25)].mean()) if (m & (L > 0.25)).sum() > 1000 else 15
    Cb = float(C[~m & (L > 0.25)].mean()) if (~m & (L > 0.25)).sum() > 1000 else 12
    return {'contrast': col['contrast'],
            'g_s': float(np.clip(math.log(col['face_L'] / 100) / math.log(Lf), 0.55, 1.15)),
            'gain_b': float(np.clip(col['room'] * col['face_L'] / 100 / Lb, col['room_min'], 0.97)),
            'da': float(np.clip(col['neutral_a'] - na, -5, 5)), 'db': float(np.clip(col['neutral_b'] - nb, -6, 8)),
            'k_s': float(np.clip(col['subject_C'] / Cp, 1.0, 2.0)), 'k_b': float(np.clip(col['room_C'] / Cb, 0.85, 1.6)),
            'skin_C': col['skin_C']}

def subject_grade(img, box, p):
    lab = to_lab(img)
    m = person_mask(box)
    L = np.clip((lab[..., 0] / 100 - 0.5) * p['contrast'] + 0.5, 1e-4, 1)
    L = L ** (p['g_s'] * m + (1 - m)) * (m + p['gain_b'] * (1 - m)) * VIG
    a, b = lab[..., 1] + p['da'], lab[..., 2] + p['db']
    C = np.hypot(a, b) + 1e-4
    k = p['k_s'] * m + min(p['k_b'], p['k_s']) * (1 - m)
    k = 1 + (k - 1) * np.clip(1.2 - C / 50, 0.25, 1)  # vibrance: muted colours gain most, strong ones least
    Cn = C * k
    skin = np.clip(1 - np.abs(np.degrees(np.arctan2(b, a)) - 52) / 24, 0, 1)
    # Skin hues stop at a chroma ceiling (colour.skin_C); above it a face turns orange.
    Cn = Cn * (1 - skin) + np.minimum(Cn, np.maximum(C, p['skin_C'])) * skin
    s = Cn / C
    out = cv2.cvtColor(np.dstack([L * 100, a * s, b * s]).astype(np.float32), cv2.COLOR_LAB2BGR)
    return np.clip(out * 255, 0, 255).astype(np.uint8)

# Treatments (round 2, P1 to P4): ways to make Dylan pop in the reel's own effects, on a person matte from lab/matte.py
# (MediaPipe selfie segmentation) carried through the same crop as the picture. Each runs after the grade and before
# the tag, so the tag keeps its white.
TREAT = (LAB or {}).get('treat', {})
MATTES = {}
trng = np.random.default_rng(23)

def matte(c, i, o, z):
    """His matte on screen for source frame i (fractional for the hero's ramp), 0 to 1."""
    if c['src'] not in MATTES:
        MATTES[c['src']] = np.load(os.path.join(HERE, 'lab', 'data', 'matte', f"{c['src']}.npy"))
    ms = MATTES[c['src']]
    a = min(int(i), len(ms) - 1); w = i - a
    m = ms[a].astype(np.float32) * (1 - w) + ms[min(a + 1, len(ms) - 1)].astype(np.float32) * w
    return crop_to(cv2.resize(m / 255, (W, H), interpolation=cv2.INTER_LINEAR), o, z)

def grain(amp):
    g = cv2.GaussianBlur(trng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.8)
    return (g / g.std() * amp)[..., None]

def treat(img, m, burn_a=0.0):
    x = img.astype(np.float32)
    m3 = m[..., None]
    if TREAT.get('print'):
        # The opener's and Worn ending's warm monochrome print, on the room only.
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)[..., None]
        prn = (g * 0.55 + x * 0.45) * np.array([0.8, 0.94, 1.1], np.float32)
        a = TREAT['print']
        x = x * m3 + (x * (1 - a) + (prn + grain(5)) * a) * (1 - m3)
    if TREAT.get('halo'):
        # Light off him: his own brightness bled outward in the reel's orange glow, strongest just past his edge, and
        # a softer halation from his highlights over himself.
        a = TREAT['halo']
        lum = x.mean(2) / 255
        wrap = cv2.GaussianBlur(m * lum, (0, 0), 22)[..., None] * np.array([30, 110, 255], np.float32) * 0.75 * a
        hal = cv2.GaussianBlur(np.clip(x - 170, 0, None) * m3, (0, 0), 14) * np.array([0.25, 0.45, 1.0], np.float32) * 0.6 * a
        x = x + wrap * (1 - 0.7 * m3) + hal
    if burn_a:
        # The opener's name2 burn on his silhouette: overexposed warm fill with a white core, orange glow, red/blue fringe.
        a = burn_a
        mb = m3 * a
        hot = np.clip(x * 1.35 + 70, 0, 255) * np.array([0.82, 0.95, 1.08], np.float32)
        fill = 0.55 * hot + 0.45 * 255
        glow = cv2.GaussianBlur(m, (0, 0), 26)[..., None] * np.array([30, 110, 255], np.float32) * 0.9 * a
        fr = np.zeros_like(x)
        fr[..., 2] = np.roll(m, 4, 1) * 120 * a
        fr[..., 0] = np.roll(m, -4, 1) * 90 * a
        x = x * (1 - mb) + fill * mb + glow + fr * (1 - m3) + grain(9) * mb
    return np.clip(x, 0, 255).astype(np.uint8)

def burn_at(f0, n):
    """Burn strength per frame of a clip starting at section frame f0: two frames on each listed beat inside it."""
    out = [0.0] * n
    for t in TREAT.get('burn', []):
        for r, a in ((0, 0.9), (1, 0.5)):
            i = fi(t) + r - f0
            if 0 < fi(t) - f0 < n and i < n:
                out[i] = a
    return out

# Super Saiyan aura (round 4, S1 to S3): a cel-shaded energy shell behind him on the hero's last frames, on at full
# strength in one frame. Distance from his silhouette is measured two ways, straight down to his body (so the shell
# rises tall over his head and shoulders) and in any direction (so it stays tight at his sides), and the shell's edge
# is cut into pointed tongues by triangle waves across the screen that fan outward with height and flow upward.
AURA = (LAB or {}).get('aura')
AURA_TONES = [((235, 250, 255), 0.0), ((30, 212, 255), 0.14), ((10, 140, 250), 0.68)]  # white inner edge, gold, gold-orange rim

def aura(img, m, u, k):
    """Draw the aura behind him on aura frame k (0 on the frame it pops on). m is his matte on screen, u his face height."""
    rng = np.random.default_rng(1000 + k // 2)  # the tongues re-form every two frames
    x = img.astype(np.float32)
    body = (cv2.GaussianBlur(m, (0, 0), 2) > 0.5).astype(np.uint8)
    flood = body.copy(); cv2.floodFill(flood, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 1)
    body |= 1 - flood  # gaps closed off by his crossed arms are him, not room
    ys, xs = np.nonzero(body)
    top = ys.min(); cx = xs[ys < top + 0.3 * u].mean(); hw = (xs.max() - xs.min()) / 2
    rows = np.arange(H, dtype=np.float32)[:, None]
    below = np.minimum.accumulate(np.where(body > 0, rows, 1e6)[::-1], axis=0)[::-1]
    up = AURA['up'] * u * np.clip(1 - ((np.arange(W) - cx) / (hw * 1.2)) ** 2, 0.3, 1)[None, :]
    r_up = (below - rows) / up
    r_side = cv2.distanceTransform(1 - body, cv2.DIST_L2, 5) / (AURA['side'] * u)
    r = cv2.GaussianBlur(np.minimum(r_up, r_side), (0, 0), 0.04 * u)
    above = np.clip((r_side - r_up) * 2, 0, 1)  # 1 where he is below, so tongues stand tall there and stay small at his sides
    h = np.clip((top - rows) / (AURA['up'] * u), 0, 1)
    shimmer = rng.uniform(-3, 3) + 2 * math.sin(k * 2.3)
    xx = np.arange(W, dtype=np.float32)[None, :]
    edge = 1.0
    yf = rows + AURA['flow'] * u * k  # the curves travel up the tongues
    for period, amp in ((0.32, AURA['amp']), (0.13, AURA['amp'] * 0.22)):
        ph, w1, w2 = rng.uniform(0, 1), rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)
        warp = 0.06 * u * np.sin(yf / (0.5 * u) + w1) + 0.03 * u * np.sin(yf / (0.21 * u) + w2)
        heights = rng.uniform(0.55, 1.0, 64)
        # Over him the tongues stand in columns; beside him they are slanted bands that rise slowly and drop sharply,
        # so the side edge throws tongues that lean up and out.
        xp = (cx + (xx - cx) / (1 + 0.6 * h) + warp + shimmer) / (period * u) + ph
        col = (1 - np.abs((xp % 1) * 2 - 1)) * heights[np.floor(xp).astype(int) % 64]
        sp = (yf + 0.7 * np.abs(xx - cx) + warp) / (period * 0.9 * u) + ph
        f = sp % 1
        side = np.where(f < 0.7, f / 0.7, (1 - f) / 0.3) * heights[np.floor(sp).astype(int) % 64]
        edge = edge + amp * ((col - 0.5) * above + (side - 0.5) * 0.7 * (1 - above))
    re = r / np.maximum(edge, 0.2)
    shell = (re < 1).astype(np.float32)
    g = (1.2 if k == 0 else rng.uniform(0.85, 1.15)) * AURA.get('gain', 1.0)  # the pop, then the pulse
    room = (1 - m)[..., None]
    col = np.zeros_like(x)
    for c, lo in AURA_TONES:
        band = cv2.GaussianBlur(((re >= lo) & (re < 1)).astype(np.float32), (0, 0), 0.7)[..., None]
        col = col * (1 - band) + np.array(c, np.float32) * band
    a = cv2.GaussianBlur(shell, (0, 0), 0.7)[..., None] * 0.92 * room
    bloom = (cv2.GaussianBlur(shell, (0, 0), 0.3 * u)[..., None] * np.array([30, 110, 255], np.float32) * 0.7
             + cv2.GaussianBlur(shell, (0, 0), 0.08 * u)[..., None] * np.array([40, 200, 255], np.float32) * 0.25)
    x = x * (1 - a) + np.minimum(col * g, 255) * a + bloom * g * room * (1 - a)
    if AURA.get('arcs'):
        # Super Saiyan 2: thin lightning crackling inside the shell, new every frame.
        arng = np.random.default_rng(5000 + k)
        cand = np.argwhere((re > 0.15) & (re < 0.85) & (body == 0))
        lines = []
        for _ in range(AURA['arcs']):
            p = cand[arng.integers(len(cand))][::-1].astype(np.float32)
            pts, d = [p], np.array([arng.uniform(-0.7, 0.7), -1.0], np.float32)
            for _ in range(int(arng.integers(5, 9))):
                d = d / np.linalg.norm(d)
                p = p + d * arng.uniform(0.06, 0.12) * u + np.array([-d[1], d[0]]) * arng.uniform(-0.05, 0.05) * u
                pts.append(p); d = d + arng.uniform(-0.6, 0.6, 2).astype(np.float32)
            lines.append(pts)
            if arng.random() < 0.5:
                q = pts[len(pts) // 2]
                lines.append([q, q + np.array([arng.uniform(-0.12, 0.12), -0.06]) * u, q + np.array([arng.uniform(-0.2, 0.2), -0.14]) * u])
        lm = np.zeros((H, W), np.float32)
        for pts in lines:
            cv2.polylines(lm, [np.round(np.array(pts) * 4).astype(np.int32)], False, 1.0, 4, cv2.LINE_AA, shift=2)
        lm = lm * (1 - m) * shell  # blue-white, the Super Saiyan 2 colour, which also stands out on the gold
        x = x * (1 - 0.85 * cv2.GaussianBlur(lm, (0, 0), 4)[..., None] * np.array([0, 0.5, 0.9], np.float32))
        x = x * (1 - lm[..., None]) + np.array([255, 240, 215], np.float32) * lm[..., None]
    return np.clip(x, 0, 255).astype(np.uint8)

def screen_box(f, o, z):
    return np.array([(f[0] - o[0]) * z, (f[1] - o[1]) * z, f[2] * z, f[3] * z])

def lab_podcast(c):
    s = SRC[c['src']]
    n = fi(c['slot_out']) - fi(c['slot_in'])
    assert abs(TRACKS[c['src']]['src_in'] - c['src_in']) < 1e-6, 'faces.json was tracked from another src_in'
    raw = footage(os.path.join(R, s['file']), c['src_in'], n)
    path = camera(c)
    out = [sharpen(crop_to(f, o, z), 0.35) for f, (o, z, _) in zip(raw, path)]
    boxes = [screen_box(f, o, z) for o, z, f in path]
    p = subject_params(out[n // 2], boxes[n // 2])
    FACE_PATH[c['src']] = {'f0': fi(c['slot_in']), 'boxes': boxes, 'zoom': [z for _, z, _ in path], 'grade': p}
    out = [subject_grade(f, bx, p) for f, bx in zip(out, boxes)]
    burns = burn_at(fi(c['slot_in']), n)
    if TREAT:
        out = [treat(f, matte(c, i, o, z), burns[i]) for i, (f, (o, z, _)) in enumerate(zip(out, path))]
    if CAM['mode'] == 'zoomthrough':
        # The original's zoom smears at its peak speed across the cut; the same smear rides each fast frame here.
        for i in range(n):
            j = i + 1 if i + 1 < n else i - 1
            d = abs(math.log(path[j][1] / path[i][1]))
            if d > 0.02:
                out[i] = zoom_blur(out[i], boxes[i][:2], d * 0.9)
    if CAM['mode'] == 'travel':
        for i in range(n):
            j = i + 1 if i + 1 < n else i - 1
            L = int(abs(boxes[j][0] - boxes[i][0]) * 0.5) | 1
            if L > 2:
                out[i] = cv2.blur(out[i], (L, 1))
    layer = split_tag(c)
    o0, z0, _ = path[0]
    zref = math.exp(sum(math.log(z) for _, z, _ in path) / n)
    res = []
    for i, (f, (o, z, _)) in enumerate(zip(out, path)):
        if CAM['mode'] == 'zoomthrough':
            res.append(zoom_tag(f, layer, i, z, zref, burns[i] / 0.9))
            continue
        M = np.float32([[z / z0, 0, z * (o0[0] - o[0])], [0, z / z0, z * (o0[1] - o[1])]])
        res.append(over(f, cv2.warpAffine(wipe_in(layer, i), M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))))
    return res

def zoom_tag(f, layer, i, z, zref, shade=0.0):
    # Pinned outright, the tag would swell off screen at the tight end of each zoom; it takes a fifth of it.
    k = (z / zref) ** 0.2
    ax, ay = W - HX, H - HUD.get('query_bottom', 72)
    M = np.float32([[k, 0, (1 - k) * ax], [0, k, (1 - k) * ay]])
    lay = cv2.warpAffine(wipe_in(layer, i), M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    if shade:
        # A burn lifts the picture under the tag to near white; a soft dark bed under the letters keeps them readable.
        bed = cv2.GaussianBlur(cv2.dilate(lay[..., 3] / 255, np.ones((15, 15), np.uint8)), (0, 0), 14)
        f = (f * (1 - np.clip(bed * 1.6, 0, 0.8) * shade)[..., None]).astype(np.uint8)
    return over(f, lay)

def jensen_b2(c):
    """B2's Jensen move, three phases on three beats: the zoom-through lands on Jensen's face at the cut's anchor and
    size and pulls out to the whole stage by `reveal`, then pushes into the belt plate for the slam at `hit` and
    settles to v14's last framing. Returns crop(u) -> (x0, y0, width) in 4K pixels, and the hit and reveal times."""
    k = [x['src'] for x in edl['clips']].index(c['src'])
    b = BOUNDS[k]
    tr = TRACKS[c['src']]
    ur, uh = c['reveal'] - c['slot_in'], c['hit'] - c['slot_in']
    end = (fi(c['slot_out']) - fi(c['slot_in'])) / FPS
    fb = np.mean([tr['boxes'][i] for i in range(int(ur * 30) + 1)], 0) * [SW, SH, SW, SH]
    face = fb[:2]
    z_face = b['h'] * H / fb[3]                      # output pixels per 4K pixel
    WIDE = 3500                                      # the whole stage, belt to feet, with room to centre the plate
    z_wide = W / WIDE
    o_wide = np.array([P[0] - W / 2 / z_wide, 0.0])  # the plate on the centre line, so the push-in only rises
    s_wide = (face - o_wide) * z_wide                # his face's place in the wide; drifting there under the pull-out
                                                     # reads as part of the zoom-out, which travels left about his face
    lz0, lz1 = math.log(z_face), math.log(z_wide)
    def crop(u):
        if u < ur:
            lz = hermite(lz0, lz1, b['v'] * ur, 0.0, u / ur)
            z = math.exp(lz)
            e = (lz0 - lz) / (lz0 - lz1)
            # Front-loaded but never faster than the zoom-out's own leftward travel about his face, so the drift to his
            # place in the wide never moves the picture right.
            e = (1 - math.exp(-1.6 * min(max(e, 0), 1))) / (1 - math.exp(-1.6)) if lz < lz0 else 0
            s = b['at'] + (s_wide - b['at']) * e
            o = face - s / z
        else:
            if u < uh:
                e = ((u - ur) / (uh - ur)) ** 3
                w = WIDE + (820 - WIDE) * e
            elif u < uh + 0.13:
                e = 1 - (1 - (u - uh) / 0.13) ** 2
                w = 820 + (930 - 820) * e
            else:
                e = min((u - uh - 0.13) / (end - uh - 0.13), 1)
                w = 930 + (680 - 930) * (3 * e ** 2 - 2 * e ** 3)
            z = W / w
            s0 = (P - o_wide) * z_wide
            s = s0 + (np.array([W / 2, H * 0.47]) - s0) * min((u - ur) / (uh - ur), 1) ** 2
            o = P - s / z
        w = W / z
        return min(max(o[0], 0), SW - w), min(max(o[1], 0), SH - w * 9 / 16), w
    return crop, uh, ur

def hero_src(c, i):
    knots = np.array(c['ramp'])
    return float(np.interp(i / FPS, knots[:, 0], knots[:, 1])) * 30

def lab_hero(c, raw, ts):
    """The hero's ramp and push-in, entering tight on his face and settling out to v14's framing, as the original's
    zoom carries through the hoop cut into the wide court."""
    n = len(ts)
    ent = LAB.get('hero')  # None keeps v14's framing
    if ent:
        k = [x['src'] for x in edl['clips']].index(c['src'])
        at0 = BOUNDS[k]['at'] if CAM['mode'] == 'zoomthrough' else np.array(ent['at']) * [W, H]
        h0 = BOUNDS[k]['h'] if CAM['mode'] == 'zoomthrough' else ent['h']
    out, boxes, zts, origins = [], [], [], []
    for i in range(n):
        t = ts[i]
        a = min(int(t), len(raw) - 2); w = t - a
        f = cv2.addWeighted(raw[a], 1 - w, raw[a + 1], w, 0)
        fc = face_at(c, t)
        z = c['zoom'][0] + (c['zoom'][1] - c['zoom'][0]) * (i / (n - 1)) ** 1.5
        kd = i - (c['kick'] - c['slot_in']) * FPS
        if 0 <= kd < 8:
            z *= 1 + 0.06 * math.exp(-kd / 2)
        e = math.exp(-i / FPS / ent['tau']) if ent else 0
        zt = z * (max(zoom_for(fc, h0), z) / z) ** e if ent else z
        o = np.array(crop_origin(c['cx'], c['cy'], zt))
        if ent:
            o = fit(fc, at0, zt) * e + o * (1 - e)
        out.append(sharpen(crop_to(f, o, zt), 0.4))
        boxes.append(screen_box(fc, o, zt)); zts.append(zt); origins.append(o)
    p = subject_params(out[n // 2], boxes[n // 2])
    p['k_b'] = min(p['k_b'], 1.0)  # the rack aisle is busy enough
    FACE_PATH[c['src']] = {'f0': fi(c['slot_in']), 'boxes': boxes, 'zoom': zts, 'grade': p}
    out = [subject_grade(f, bx, p) for f, bx in zip(out, boxes)]
    if TREAT:
        burns = burn_at(fi(c['slot_in']), n)
        out = [treat(f, matte(c, t, o, z), burns[i]) for i, (f, t, o, z) in enumerate(zip(out, ts, origins, zts))]
    if AURA:
        for i in range(fi(AURA['on']) - fi(c['slot_in']), n):
            out[i] = aura(out[i], matte(c, ts[i], origins[i], zts[i]), boxes[i][3], i - (fi(AURA['on']) - fi(c['slot_in'])))
    for i in range(n - 1):
        d = abs(math.log(zts[i + 1] / zts[i]))
        if d > 0.02:
            out[i] = zoom_blur(out[i], boxes[i][:2], d * 0.9)
    return out

BOUNDS = boundaries() if LAB and CAM['mode'] == 'zoomthrough' else None
JENSEN_TAG = {}  # B2: the last frame inside the Jensen slot that shows its tag, and the hit frame
FACE_PATH = {}  # src -> where his face sits on screen per frame, and the clip's grade; lab/data/path-<output>.json

def punch(img, a):
    z = 1 + a
    M = np.float32([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def main():
    frames = [None] * NF
    cuts, flashes = [], {}
    jens = None
    for c in edl['clips']:
        f0 = fi(c['slot_in'])
        if c.get('kind') == 'jensen-zoom':
            seg, hitF, b2F = jensen(c)
            jens = (f0, len(seg))
            h, b = (f0 + hitF) // S, (f0 + b2F) // S
            flashes.update({h: 0.92, h + 1: 0.55, h + 2: 0.22, b: 0.35, b + 1: 0.12})
            if c.get('reveal') is not None:  # B2: the reveal of the whole stage takes the music's one strong hit
                flashes.update({b: 0.6, b + 1: 0.3, b + 2: 0.1})
        elif c.get('kind') == 'hero':
            seg = hero(c)
        else:
            seg = podcast(c)
        frames[f0:f0 + len(seg)] = seg
        if f0 > 0:
            cuts.append((f0, c.get('kind') == 'jensen-zoom'))
        print(c['src'], c['slot_in'], len(seg), file=sys.stderr)
    assert all(f is not None for f in frames) and len(frames) == NF
    # Whips on every cut, alternating direction like the original's pans. The cut into Jensen only
    # whips the outgoing side, since the zoom carries its own blur.
    dirs = [MOVES[m] for m in V14_MOVES]
    if LAB:
        rng = np.random.default_rng(6767)
        for n, (cf, into_jensen) in enumerate(cuts):
            mv = LAB['moves'][n]
            if mv in MOVES:
                eased_pan(frames, cf, into_jensen, *MOVES[mv], rng, forward=True)
            elif mv == 'cut':
                for r in range(4):
                    frames[cf + r] = punch(frames[cf + r], 0.06 * math.exp(-r / 1.4))
        for t in LAB.get('punch', []):
            f = fi(t)
            for r in range(5):
                if f + r < NF:
                    frames[f + r] = punch(frames[f + r], 0.05 * math.exp(-r / 1.5))
    elif edl['section'].get('whip') == 'eased':
        rng = np.random.default_rng(6767)
        for n, (cf, into_jensen) in enumerate(cuts):
            ax, sg = dirs[n % len(dirs)]
            eased_pan(frames, cf, into_jensen, ax, sg, rng)
    else:
      for n, (cf, into_jensen) in enumerate(cuts):
        ax, sg = dirs[n % len(dirs)]
        span = W if ax == 'h' else H
        for off, L, sh in ((-2, 61, -0.05), (-1, 181, -0.16)):
            frames[cf + off] = whip(frames[cf + off], L, sg * sh * span, ax)
        if not into_jensen:
            for off, L, sh in ((0, 181, 0.16), (1, 61, 0.05)):
                frames[cf + off] = whip(frames[cf + off], L, sg * sh * span, ax)
    # Whip into the section from the newspaper, matching the bright frame at 13.20 and the blur at 13.27.
    if edl['section'].get('open', 'whip') == 'whip':
        frames[0] = white(whip(frames[0], 201, 0.18 * W, 'h'), 0.55)
        frames[1] = whip(frames[1], 101, 0.07 * W, 'h')
    # The original's white flash around 17.87, and the ramp to white into the alley-oop at 20.73.
    f17 = fi30(17.87 - T0)  # reel time of the original's flash, in 30 fps frames
    n30 = NF // S
    flashes.update({f17: 0.3, f17 + 1: 0.6, f17 + 2: 0.45, f17 + 3: 0.18, n30 - 2: 0.45, n30 - 1: 0.82})
    flashes[0] = 0
    # Flash strengths are set per 30 fps frame; a 60 fps frame between two takes their mean, and the last one holds.
    for i in range(NF):
        k, w = divmod(i, S)
        a = flashes.get(k, 0) if not w else (flashes.get(k, 0) + (flashes.get(k + 1, 0) if k + 1 < n30 else flashes.get(k, 0))) / 2
        if a:
            frames[i] = white(frames[i], a)
    if edl['section'].get('tag_style') == 'hud':
        beats = [(fi(c['slot_in']), fi(c['slot_out']), c) for c in edl['clips'] if not c.get('kind')]
        for f, layer in hud_layers(beats).items():
            frames[f] = over(frames[f], layer)
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    sfx = '' if S == 1 else f'-{FPS}'
    output = edl['section']['output'].replace('.mp4', f'{sfx}.mp4')
    if PLACED:
        json.dump(PLACED, open(os.path.join(HERE, 'out', output.replace('.mp4', '-tags.json')), 'w'), indent=2)
    encode(frames, os.path.join(HERE, 'out', output))
    if LAB:
        rnd = lambda v: [round(float(x), 4) for x in v]
        json.dump({k: {'f0': v['f0'], 'zoom': rnd(v['zoom']), 'grade': {g: round(x, 3) for g, x in v['grade'].items()},
                       'boxes': [rnd(np.asarray(b) / [W, H, W, H]) for b in v['boxes']]} for k, v in FACE_PATH.items()} | ({'gtc-tag': JENSEN_TAG} if JENSEN_TAG else {}),
                  open(os.path.join(HERE, 'lab', 'data', 'path-' + output.replace('.mp4', '.json')), 'w'))
    if not LAB:  # the lab variants leave v14's jensen-zoom.mp4 alone
        j0, jn = jens
        encode(frames[j0:j0 + jn], os.path.join(HERE, 'out', f'jensen-zoom{sfx}.mp4'))

main()
