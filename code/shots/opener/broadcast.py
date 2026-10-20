# Opener variant "broadcast intro": a fake pre-game player introduction that the edit cuts off almost at once.
# Frames 0 to 14 are Dylan in the arena spotlight, turned away and rotating, with a TNT-style player-intro lower third
# (a parody logoman badge made from his own silhouette, #67, DYLAN PATEL, SEMIANALYSIS, a stat line) wiping in over
# the last four of them. Frame 15 hard-cuts into the gameplay at full brightness, and from frame 30 on the frames are
# the v2 worn reel's, re-encoded at CRF 8. The audio is mix D (audio/audit/out/d-hotter-voices.wav), stream-copied
# from the D baseline reel so the opener scan sees the same AAC packets, squeaks included.
#
# The gameplay after the cut is the fade-in scene rebuilt without its fade (shots/fadein/v3.sh made it as RIFE
# in-betweens of the intro take's first 16 frames, then faded them up). Gain-matching the faded frames instead would
# multiply frame 15 by about 6.6 and band the 8-bit shadows.
#
# Inputs (each download in its own folder under shots/opener/broadcast):
#   img-intro-1  the arena still, Sunburst through starts/gen.mjs (job bcintro)
#   img-logo-1   Dylan dribbling on chroma green, the logoman silhouette (job bclogo)
#   wan-1/out    Wan 3.0 i2v from the still (job.json there, shots/vid.mjs --no-video --first-only)
#
#   uv run --no-project --python 3.12 --with-requirements requirements.txt \
#     python -I shots/opener/broadcast.py [--sheet]
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, shutil, subprocess, sys, tempfile
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
B = f'{R}/shots/opener/broadcast'
OUT = f'{R}/shots/opener/out'
W, H, FPS, TOTAL, CUT = 1920, 1080, 30, 902, 15
BASE = f'{R}/master/out/final-v2-worn-30-master.mp4'
AUDIO = f'{R}/master/out/final-v2d-worn-30-master.mp4'   # same video as BASE, mix D as AAC 320k
STILL = f'{B}/img-intro-1/bcintro-gpt-image-2.5-sunburst.png'
LOGO = f'{B}/img-logo-1/bclogo-gpt-image-2.5-sunburst.png'
TAKE = f'{B}/wan-1/out/wan-3.0-novideo-first.mp4'
RIFE = os.environ.get('RIFE_DIR', 'rife-ncnn-vulkan')
UNFADED = f'{B}/work/fadein-unfaded.mkv'

DIN = os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'BarlowCondensed-Bold.ttf')
FUT = {0: os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'Barlow-Medium.ttf'), 4: os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'BarlowCondensed-ExtraBold.ttf')}
SS = 4

# The graphic's animation, one row per output frame it is on: badge scale, bar and strip reveal (0..1), the name's
# slide-in offset in px, and the glint's position across the bar (None for none). Broadcast wipes ease out, so
# most of the travel happens in the first frame.
GRAPHIC = {
    11: dict(badge=0.72, bar=0.50, slide=-70, strip=0.00, glint=None),
    12: dict(badge=1.06, bar=0.92, slide=-14, strip=0.45, glint=None),
    13: dict(badge=1.00, bar=1.00, slide=0, strip=0.92, glint=0.30),
    14: dict(badge=1.00, bar=1.00, slide=0, strip=1.00, glint=0.95),
}

def decode(path, n=None, start=0, vf=None, size=(W, H)):
    filt = f'select=gte(n\\,{start}),setpts=PTS-STARTPTS,' if start else ''
    filt += vf or f'scale={W}:{H}:flags=lanczos'
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', filt, *(['-frames:v', str(n)] if n else []),
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, size[1], size[0], 3)

def unfaded():
    # The same RIFE run as shots/fadein/v3.sh, minus the geq fade, kept lossless.
    if os.path.exists(UNFADED):
        return decode(UNFADED)
    os.makedirs(os.path.dirname(UNFADED), exist_ok=True)
    t = tempfile.mkdtemp()
    os.makedirs(f'{t}/a'); os.makedirs(f'{t}/a2')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', f'{R}/shots/intro/out/overlay-v2.mp4', '-vf', 'trim=end_frame=16', f'{t}/a/%08d.png'], check=True)
    subprocess.run([f'{RIFE}/rife-ncnn-vulkan', '-i', f'{t}/a', '-o', f'{t}/a2', '-m', f'{RIFE}/rife-v4.6', '-n', '32'], check=True, capture_output=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '30', '-i', f'{t}/a2/%08d.png', '-vf', 'trim=end_frame=30',
                    '-c:v', 'ffv1', '-pix_fmt', 'bgr0', UNFADED], check=True)
    shutil.rmtree(t)
    return decode(UNFADED)

def master_look():
    # The master renders and the worn pass leave frame 30 about 7% darker and cooler than the intro take they cut
    # from. Fit that as an affine colour map from the take (overlay-v3-from05, frame k) to the base (frame 30 + k),
    # which are the same pixels, so the rebuilt frames 15 to 29 meet frame 30 without a step.
    small = 'scale=480:270:flags=area'
    src = decode(f'{R}/shots/intro/out/overlay-v3-from05.mp4', 10, vf=small, size=(480, 270)).reshape(-1, 3).astype(np.float32)
    dst = decode(BASE, 10, start=30, vf=small, size=(480, 270)).reshape(-1, 3).astype(np.float32)
    X = np.hstack([src, np.ones((len(src), 1), np.float32)])
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)
    print('master look residual', round(float(np.abs(X @ M - dst).mean()), 2), flush=True)
    return M

def gameplay():
    M = master_look()
    return [np.clip(np.concatenate([f.astype(np.float32), np.ones((H, W, 1), np.float32)], 2) @ M + 0.5, 0, 255).astype(np.uint8)
            for f in unfaded()[CUT:30]]

# ---------------------------------------------------------------- the shot

def shot():
    if os.path.exists(TAKE):
        f = decode(TAKE).astype(np.float32)
        idx = np.round(SHOT_T0 + SHOT_SPEED * np.arange(CUT)).astype(int)
        f = f[np.clip(idx, 0, len(f) - 1)]
    else:
        f = np.repeat(np.asarray(Image.open(STILL).convert('RGB').resize((W, H), Image.LANCZOS), np.float32)[None], CUT, 0)
    return [grade(x, n) for n, x in enumerate(f)]

SHOT_T0, SHOT_SPEED = 0, 2.4   # source frame of output frame 0, source frames per output frame

def grade(x, n):
    # The take is cleaner than broadcast: a touch of softness and grain, and a two-frame rise from black so the cut
    # in from the reel's black head reads as the feed switching on.
    x = cv2.GaussianBlur(x, (0, 0), 0.6)
    x = x + np.random.default_rng(n).normal(0, 2.2, x.shape[:2]).astype(np.float32)[..., None]
    return np.clip(x * min(1.0, (n + 1) / 2.5), 0, 255)

# ---------------------------------------------------------------- the graphic

def font(path, px, index=0):
    return ImageFont.truetype(path, px * SS, index=index)

def silhouette(h):
    # Dylan's outline from the chroma-green still, mirrored to face left like the league's logoman, as alpha (h tall).
    im = np.asarray(Image.open(LOGO).convert('RGB'), np.float32)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    fg = ~((g > r + 45) & (g > b + 45))
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    fg = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ys, xs = np.nonzero(fg)
    crop = fg[ys.min():ys.max() + 1, xs.min():xs.max() + 1][:, ::-1] * 255
    s = h / crop.shape[0]
    return Image.fromarray(crop.astype(np.uint8)).resize((round(crop.shape[1] * s), h), Image.LANCZOS)

def badge(w, h):
    # Red, white and blue vertical badge, white keyline, Dylan's silhouette across the split; no league text.
    im = Image.new('RGBA', (w * SS, h * SS), 0)
    d = ImageDraw.Draw(im)
    rad, k = 14 * SS, 5 * SS
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), rad, fill=(255, 255, 255, 255))
    inner = Image.new('RGBA', im.size, 0)
    di = ImageDraw.Draw(inner)
    di.rounded_rectangle((k, k, w * SS - 1 - k, h * SS - 1 - k), rad - k, fill=(200, 16, 46, 255))
    split = Image.new('L', im.size, 0)
    ImageDraw.Draw(split).rectangle((0, 0, round(w * SS * 0.47), h * SS), fill=255)
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((k, k, w * SS - 1 - k, h * SS - 1 - k), rad - k, fill=255)
    blue = Image.new('RGBA', im.size, (23, 64, 139, 255))
    inner.paste(blue, (0, 0), Image.fromarray(np.minimum(np.asarray(split), np.asarray(mask))))
    im.alpha_composite(inner)
    sil = silhouette(round(h * SS * 0.84))
    x = round(w * SS * 0.5 - sil.width * 0.52)
    y = round(h * SS * 0.08)
    sil_mask = Image.new('L', im.size, 0)
    sil_mask.paste(sil, (x, y))
    sil_mask = Image.fromarray(np.minimum(np.asarray(sil_mask), np.asarray(mask)))
    im.paste((255, 255, 255, 255), (0, 0), sil_mask)
    return im.resize((w, h), Image.LANCZOS)

def text(d, xy, s, f, fill, anchor='ls', track=0):
    x, y = xy
    if not track:
        d.text((x * SS, y * SS), s, font=f, fill=fill, anchor=anchor)
        return
    for ch in s:
        d.text((x * SS, y * SS), ch, font=f, fill=fill, anchor=anchor)
        x += f.getlength(ch) / SS + track

# Layout in frame pixels. The lower third sits bottom left, clear of his face (right of centre).
X0, BAR_Y, BAR_H, STRIP_H = 150, 806, 112, 46
BADGE_W, BADGE_H = 96, 196
NUM_W, NAME_W, STAT_W, STAT_NUM = 128, 470, 330, 104
BAR_X = X0 + BADGE_W + 14
BAR_W = NUM_W + NAME_W
GOLD, PURPLE = (247, 182, 32), (85, 37, 131)

def bar_layer(slide):
    im = Image.new('RGBA', (W * SS, H * SS), 0)
    d = ImageDraw.Draw(im)
    s = lambda v: round(v * SS)
    # black glossy bar, a little lift toward the top like the scorebug
    top = np.linspace(34, 8, BAR_H * SS)[:, None, None]
    grad = np.concatenate([np.broadcast_to(top, (BAR_H * SS, BAR_W * SS, 3)), np.full((BAR_H * SS, BAR_W * SS, 1), 242)], 2)
    im.paste(Image.fromarray(grad.astype(np.uint8), 'RGBA'), (s(BAR_X), s(BAR_Y)))
    # gold number cell
    x = BAR_X + slide
    cell = np.zeros((BAR_H * SS, NUM_W * SS, 4), np.float32)
    cell[..., :3] = np.array(GOLD, np.float32) * np.linspace(1.04, 0.80, BAR_H * SS)[:, None, None]
    cell[..., 3] = 255
    im.alpha_composite(Image.fromarray(np.clip(cell, 0, 255).astype(np.uint8), 'RGBA'), (s(x), s(BAR_Y)))
    text(d, (x + NUM_W / 2, BAR_Y + BAR_H / 2 + 2), '#67', font(DIN, 78), (255, 255, 255, 255), anchor='mm')
    nx = x + NUM_W + 26
    text(d, (nx, BAR_Y + 38), 'DYLAN', font(FUT[0], 27), (235, 235, 235, 255), track=3)
    text(d, (nx - 3, BAR_Y + 98), 'PATEL', font(FUT[4], 70), (255, 255, 255, 255), track=2)
    # thin gold rule along the top edge
    d.rectangle((s(BAR_X), s(BAR_Y), s(BAR_X + BAR_W), s(BAR_Y + 4)), fill=GOLD + (255,))
    return im

def strip_layer():
    im = Image.new('RGBA', (W * SS, H * SS), 0)
    d = ImageDraw.Draw(im)
    s = lambda v: round(v * SS)
    y0, y1 = BAR_Y + BAR_H, BAR_Y + BAR_H + STRIP_H
    d.rectangle((s(BAR_X), s(y0), s(BAR_X + BAR_W), s(y1)), fill=PURPLE + (245,))
    text(d, (BAR_X + 18, y1 - 11), 'SEMIANALYSIS', font(DIN, 34), GOLD + (255,), track=2)
    text(d, (BAR_X + BAR_W - 18, y1 - 11), 'ANALYST', font(DIN, 34), (255, 255, 255, 255), anchor='rs', track=0)
    # the stat line, in the reel's $2M banner look: dark grey box, two DIN lines, a number box
    sx = BAR_X + BAR_W + 10
    nx = sx + STAT_W - STAT_NUM
    d.rectangle((s(sx), s(BAR_Y + 30), s(nx), s(y1)), fill=(46, 47, 50, 240))
    d.rectangle((s(nx), s(BAR_Y + 30), s(sx + STAT_W), s(y1)), fill=(18, 19, 21, 245))
    text(d, ((sx + nx) / 2, BAR_Y + 30 + 54), 'TO BREAK', font(DIN, 36), (246, 246, 242, 255), anchor='ms')
    text(d, ((sx + nx) / 2, BAR_Y + 30 + 98), 'BOOTSTRAP RECORD', font(DIN, 36), (246, 246, 242, 255), anchor='ms')
    text(d, ((nx + sx + STAT_W) / 2, BAR_Y + 30 + 96), '$2M', font(DIN, 66), (255, 255, 255, 255), anchor='ms')
    return im

def reveal(layer, x0, x1, p):
    # left-to-right wipe: keep columns up to x0 + p * (x1 - x0), with a 6 px soft edge
    a = np.asarray(layer, np.float32) / 255
    edge = (x0 + p * (x1 - x0)) * SS
    xs = np.arange(a.shape[1], dtype=np.float32)
    a = a.copy()
    a[..., 3] *= np.clip((edge - xs) / (6 * SS), 0, 1)[None]
    return a

def graphic(st, cache):
    if 'badge' not in cache:
        cache['badge'] = badge(BADGE_W, BADGE_H)
        cache['strip'] = strip_layer()
    full = np.zeros((H * SS, W * SS, 4), np.float32)
    x1 = BAR_X + BAR_W + 10 + STAT_W
    bar = reveal(bar_layer(st['slide']), BAR_X, BAR_X + BAR_W, st['bar'])
    full = over(full, bar)
    if st['strip'] > 0:
        full = over(full, reveal(cache['strip'], BAR_X, x1, st['strip']))
    if st['glint'] is not None:
        full = glint(full, BAR_X + st['glint'] * BAR_W)
    im = Image.fromarray((np.clip(full, 0, 1) * 255).astype(np.uint8), 'RGBA').resize((W, H), Image.LANCZOS)
    b = cache['badge']
    sc = st['badge']
    bw, bh = round(BADGE_W * sc), round(BADGE_H * sc)
    by = BAR_Y + BAR_H + STRIP_H - BADGE_H + (BADGE_H - bh) // 2
    im.alpha_composite(b.resize((bw, bh), Image.LANCZOS), (X0 + (BADGE_W - bw) // 2, by))
    return np.asarray(im, np.float32) / 255

def over(dst, src):
    a = src[..., 3:]
    out = dst.copy()
    out[..., :3] = src[..., :3] * a + dst[..., :3] * (1 - a)
    out[..., 3:] = a + dst[..., 3:] * (1 - a)
    return out

def glint(full, cx):
    # a diagonal sheen across the panels, only where they are opaque
    yy, xx = np.mgrid[0:full.shape[0], 0:full.shape[1]].astype(np.float32) / SS
    band = np.exp(-(((xx - cx) + 0.45 * (yy - BAR_Y)) / 26) ** 2) * 0.55
    full = full.copy()
    full[..., :3] = full[..., :3] + (1 - full[..., :3]) * band[..., None] * full[..., 3:]
    return full

def composite(frame, g):
    # A soft drop shadow under the panels, then the panels, slightly softened to sit in the broadcast's resolution.
    a = g[..., 3]
    sh = cv2.GaussianBlur(a, (0, 0), 6) * 0.45
    x = frame * (1 - sh[..., None])
    rgb = cv2.GaussianBlur(g[..., :3] * 255, (0, 0), 0.5)
    aa = cv2.GaussianBlur(a, (0, 0), 0.5)[..., None]
    return x * (1 - aa) + rgb * aa

# ---------------------------------------------------------------- the reel

def head():
    frames = shot()
    cache = {}
    for n, st in GRAPHIC.items():
        frames[n] = composite(frames[n], graphic(st, cache))
    return [np.clip(f + 0.5, 0, 255).astype(np.uint8) for f in frames] + gameplay()

def write(frames):
    os.makedirs(OUT, exist_ok=True)
    out = f'{OUT}/opener-broadcast.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-i', AUDIO, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '8', '-pix_fmt', 'yuv420p',
                            '-c:a', 'copy', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', BASE, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    for n in range(TOTAL):
        x = dec.stdout.read(W * H * 3)
        assert len(x) == W * H * 3, n
        enc.stdin.write(frames[n].tobytes() if n < len(frames) else x)
    enc.stdin.close(); enc.wait(); dec.wait()
    assert enc.returncode == 0
    print('wrote', out, flush=True)
    return out

def sheet(path):
    f = decode(path, 21)
    tiles = [cv2.putText(cv2.resize(x, (640, 360), interpolation=cv2.INTER_AREA).copy(), str(n), (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)
             for n, x in enumerate(f)]
    tiles += [np.zeros_like(tiles[0])] * 3
    grid = np.vstack([np.hstack(tiles[r * 4:r * 4 + 4]) for r in range(6)])
    p = f'{OUT}/opener-broadcast-sheet.jpg'
    Image.fromarray(grid).save(p, quality=90)
    print('wrote', p)

if __name__ == '__main__':
    out = write(head())
    sheet(out)
