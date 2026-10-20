# Old-film pass over the reel's ending (23.50 to the end, the fade-out, jersey and profile), measured against the
# original in analysis/flicker. Each layer is one function; a preset picks layers and strengths.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/film/film.py [preset ...]
#   ... shots/film/film.py --final [preset] [30,60]   the finished reel at 30 and 60 fps (master/out/final-*)
# Reads master/out/reel-30-master.mp4, writes shots/film/out/film-<preset>.mp4 (with the mix) and original.mp4.
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys, numpy as np, cv2

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(R, 'shots', 'film', 'out')
W, H, T0, F0 = 1920, 1080, 23.5, 705
os.makedirs(OUT, exist_ok=True)

def frames(path, t0):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', path, '-vf', f'scale={W}:{H}', '-f', 'rawvideo',
                          '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def borrowed_flicker(n):
    # The original's own frame-to-frame exposure wobble: each frame's mean luma over a 5-frame running median, so the
    # fades stay ours and only the flicker transfers. Frames near black carry no reading and get 1.
    m = np.array([r['mean'] for r in json.load(open(f'{R}/analysis/flicker/original.json'))])
    med = np.array([np.median(m[max(0, i - 2):i + 3]) for i in range(len(m))])
    g = np.where(med > 12, m / np.maximum(med, 1e-3), 1.0)
    return np.clip(np.pad(g, (0, max(0, n - len(g))), constant_values=1.0)[:n], 0.8, 1.2)

def random_flicker(n, rng, amp):
    # Projector-style: a slow drift plus independent per-frame jumps, the odd frame dipping harder.
    slow = np.convolve(rng.normal(0, 1, n + 8), np.ones(8) / 8, 'valid')[:n]
    jump = rng.normal(0, 1, n) + (rng.random(n) < 0.08) * -2.5
    return 1 + amp * (0.5 * slow + 0.5 * jump)

def lift(x, floor, contrast):
    # The original crushes contrast first (an S curve on the print) and then sits its blacks on a flat dark grey, so
    # the mids stay hard while nothing reaches true black.
    u = x / 255
    u = u + contrast * (u * u * (3 - 2 * u) - u)
    return floor + 255 * u * (1 - floor / 255)

def grain(rng, amp):
    g = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.8)
    return g * (amp / g.std())

def weave_offsets(n, rng, px):
    k = np.ones(4) / 4
    return [np.convolve(rng.normal(0, 1, n + 3), k, 'valid')[:n] * px * 2 for _ in range(2)]

def halation(x, strength):
    hi = np.clip((x.max(2) - 190) / 65, 0, 1)[..., None] * x
    glow = cv2.GaussianBlur(hi, (0, 0), 18)
    return x + strength * glow * np.array([0.25, 0.45, 1.0], np.float32)  # BGR, red-orange

def vignette(amount):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / np.sqrt(2)
    return (1 - amount * np.clip(r - 0.3, 0, 1) ** 1.6 / 0.7 ** 1.6)[..., None]

class Damage:
    # Dust lives one frame. Scratches persist a few frames and drift sideways, like a scratch on the print running
    # past the gate.
    def __init__(self, rng, dust, scratches):
        self.rng, self.dust, self.rate, self.live = rng, dust, scratches, []

    def apply(self, x):
        return x + self.layer()[..., None]

    def layer(self):
        rng = self.rng
        layer = np.zeros((H, W), np.float32)
        for _ in range(rng.poisson(self.dust)):
            c = (int(rng.integers(0, W)), int(rng.integers(0, H)))
            v = rng.choice([-1, 1], p=[0.6, 0.4]) * rng.uniform(80, 200)
            if rng.random() < 0.12:  # a hair
                pts = np.cumsum(rng.normal(0, 3, (12, 2)), 0).astype(np.int32) + c
                cv2.polylines(layer, [pts], False, float(v), 1, cv2.LINE_AA)
            else:
                cv2.ellipse(layer, c, (int(rng.integers(1, 4)), int(rng.integers(1, 4))), float(rng.uniform(0, 180)), 0, 360, float(v), -1, cv2.LINE_AA)
        if rng.random() < self.rate:
            self.live.append({'x': rng.uniform(0.05, 0.95) * W, 'dx': rng.normal(0, 2), 'life': int(rng.integers(3, 14)),
                              'v': rng.choice([-1, 1], p=[0.35, 0.65]) * rng.uniform(40, 110), 'w': int(rng.integers(1, 3)),
                              'y0': int(rng.integers(-H // 2, H // 3)), 'y1': int(rng.integers(H * 2 // 3, H * 3 // 2))})
        for s in self.live:
            xs = int(s['x'] + rng.normal(0, 0.6))
            cv2.line(layer, (xs, s['y0']), (xs + int(rng.normal(0, 2)), s['y1']), float(s['v'] * rng.uniform(0.6, 1)), s['w'], cv2.LINE_AA)
            s['x'] += s['dx']; s['life'] -= 1
        self.live = [s for s in self.live if s['life'] > 0]
        return cv2.GaussianBlur(layer, (0, 0), 0.6)

CLEAN_TAIL = 3   # (2026-10-17) no scratch or dust on the last frames, so the final frame is clean

PRESETS = {
    # Closest to the original: its own flicker, lifted blacks, scratches and dust, nothing it doesn't have.
    'match': dict(flicker='borrowed', floor=22, dust=8, scratches=0.35),
    # Classic print: the match layers plus grain, gate weave, red halation on the highlights and a soft vignette.
    'classic': dict(flicker='borrowed', floor=20, dust=10, scratches=0.35, grain=7, weave=1.0, halation=0.35, vignette=0.35),
    # Worn 16 mm: harder random flicker on top of the borrowed one, heavier grain and damage, more weave.
    'worn': dict(flicker='both', amp=0.05, floor=26, dust=22, scratches=0.6, grain=12, weave=2.0, halation=0.5, vignette=0.5),
}

def render(name, f, rng):
    p = PRESETS[name]
    n = len(f)
    gain = np.ones(n)
    if p['flicker'] in ('borrowed', 'both'):
        gain *= borrowed_flicker(n)
    if p['flicker'] == 'both':
        gain *= random_flicker(n, rng, p['amp'])
    wx, wy = weave_offsets(n, rng, p.get('weave', 0))
    vig = vignette(p['vignette']) if p.get('vignette') else 1
    dmg = Damage(rng, p['dust'], p['scratches'])
    path = os.path.join(OUT, f'film-{name}-video.mp4')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    for i, src in enumerate(f):
        x = src.astype(np.float32)
        if p.get('weave'):
            x = cv2.warpAffine(x, np.float32([[1, 0, wx[i]], [0, 1, wy[i]]]), (W, H), borderMode=cv2.BORDER_REFLECT)
        if p.get('halation'):
            x = halation(x, p['halation'])
        x = x * gain[i]
        if i < n - CLEAN_TAIL:
            x = dmg.apply(x)
        if p.get('grain'):
            x = x + grain(rng, p['grain'])[..., None] * (0.4 + 0.6 * np.sin(np.pi * np.clip(x.mean(2, keepdims=True) / 255, 0, 1)))
        x = lift(np.clip(x, 0, 255), p['floor'], p.get('contrast', 1)) * vig
        enc.stdin.write(np.clip(x, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait()
    mux(path, os.path.join(OUT, f'film-{name}.mp4'))
    os.remove(path)

def mux(video, out):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-ss', str(T0), '-i', f'{R}/master/work/mix-final-patel3-5-outro3-limited.wav', '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out], check=True)

def final(name, fps):
    # The whole reel with the film pass from 23.50 s on, streamed frame by frame. At 60 fps each film frame (the
    # flicker, the damage, the grain) holds for two output frames, so the film keeps its 30 fps cadence over the
    # smoother motion. Writes master/out/final-<fps>-master.mp4 (match) or final-<preset>-<fps>-master.mp4, with
    # -upload.mp4 and -master-pcm.mov.
    # BASE=<tag> reads master/out/reel-<tag>-<fps>-master.mp4 (a render.py --tag candidate) and writes
    # final-<tag>-<preset>-<fps>; MIX=<path from R> muxes an already-mastered mix instead of the limited default.
    p, k = PRESETS[name], fps // 30
    base = os.environ.get('BASE', '')
    tag = f'final-{fps}' if name == 'match' and not base else f'final-{base + "-" if base else ""}{name}-{fps}'
    rng = np.random.default_rng(7)
    src = f'{R}/master/out/reel-{base + "-" if base else ""}{fps}-master.mp4'
    total = int(subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_packets',
                                '-of', 'csv=p=0', src], capture_output=True, text=True, check=True).stdout)
    n = total // k - F0                                   # film frames after the start
    gain = borrowed_flicker(n)
    if p['flicker'] == 'both': gain *= random_flicker(n, rng, p['amp'])
    wx, wy = weave_offsets(n, rng, p.get('weave', 0))
    vig = vignette(p['vignette']) if p.get('vignette') else 1
    dmg = Damage(rng, p['dust'], p['scratches'])
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    video = f'{R}/master/work/{tag}-video.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '8', '-pix_fmt', 'yuv420p', video], stdin=subprocess.PIPE)
    layer, gr = None, None
    for j in range(total):
        x = np.frombuffer(dec.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
        i = j // k - F0
        if i >= 0:
            if j % k == 0:                               # a new film frame
                layer = dmg.layer() if i < n - CLEAN_TAIL else None
                gr = grain(rng, p['grain']) if p.get('grain') else None
            x = x.astype(np.float32)
            if p.get('weave'):
                x = cv2.warpAffine(x, np.float32([[1, 0, wx[i]], [0, 1, wy[i]]]), (W, H), borderMode=cv2.BORDER_REFLECT)
            if p.get('halation'): x = halation(x, p['halation'])
            x = x * gain[i]
            if layer is not None: x = x + layer[..., None]
            if gr is not None: x = x + gr[..., None] * (0.4 + 0.6 * np.sin(np.pi * np.clip(x.mean(2, keepdims=True) / 255, 0, 1)))
            x = np.clip(lift(np.clip(x, 0, 255), p['floor'], p.get('contrast', 1)) * vig, 0, 255).astype(np.uint8)
        enc.stdin.write(np.ascontiguousarray(x).tobytes())
    enc.stdin.close(); enc.wait(); dec.wait()
    mix = os.path.join(R, os.environ.get('MIX', 'master/work/mix-final-patel3-5-outro3-limited.wav'))
    o = f'{R}/master/out/{tag}'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k',
                    '-ar', '48000', '-shortest', '-movflags', '+faststart', f'{o}-master.mp4'], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'pcm_s24le',
                    '-shortest', f'{o}-master-pcm.mov'], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow',
                    '-profile:v', 'high', '-level', '4.2', '-b:v', '24M', '-maxrate', '30M', '-bufsize', '60M', '-pix_fmt', 'yuv420p', '-g', str(fps),
                    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-shortest', '-movflags', '+faststart', f'{o}-upload.mp4'], check=True)
    print('wrote', o, flush=True)

if sys.argv[1:2] == ['--final']:
    for fps in map(int, sys.argv[3].split(',') if len(sys.argv) > 3 else (30, 60)): final(sys.argv[2] if len(sys.argv) > 2 else 'match', fps)
    sys.exit()
f = frames(f'{R}/master/out/reel-30-master.mp4', F0 / 30)
for name in sys.argv[1:] or PRESETS:
    render(name, f, np.random.default_rng(7))
    print('wrote', name, flush=True)
if not os.path.exists(os.path.join(OUT, 'original.mp4')):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(T0), '-i', f'{R}/src/clip.mp4', '-c:v', 'libx264', '-crf', '14', '-c:a', 'aac',
                    '-movflags', '+faststart', os.path.join(OUT, 'original.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(F0 / 30), '-i', f'{R}/master/out/reel-30-master.mp4', '-c:v', 'libx264', '-crf', '12', '-c:a', 'aac', '-movflags', '+faststart',
                    os.path.join(OUT, 'clean.mp4')], check=True)
