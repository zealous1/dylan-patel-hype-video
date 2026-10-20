# Opener split-test variants: each is the full v2 reel with only the first 0.6 s changed, all done before the fade-in
# finishes. Only frames under the overlay change; the rest are the v2 frames re-encoded at CRF 8.
#   face2  shoulders-up from the data center shot as he looks up and smiles, cross-dissolved over the fade-in with
#          the ending's film light (warm print tone, flicker, halation)
#   name2  DYLAN then PATEL, both set to the same width, huge, flickering frame by frame, burnt in: the letters are a
#          window onto the un-faded court, overexposed and warm, with an orange glow bleeding off the edges
#   logo   the SemiAnalysis mark flashing three or four times as the court fades in, low opacity, burnt the same way
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/opener/build.py face2 name2 logo
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.environ.get('OPENER_OUT', os.path.join(R, 'shots', 'opener', 'out'))   # a draft folder keeps half-checked files away from the scanner
W, H, FPS = 1920, 1080, 30
BASE = os.path.join(R, os.environ.get('OPENER_BASE', 'master/out/final-v2-worn-30-master.mp4'))   # OPENER_BASE (from R) swaps the reel the opener goes on
AUDIO = BASE   # carries mix D from film.py's MIX, copied so every variant's track matches the base bit for bit
SPAN = 32                                                   # frames decoded and re-rendered
rng = np.random.default_rng(11)

def decode(path, n=None):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, *(['-frames:v', str(n)] if n else []), '-f', 'rawvideo',
                          '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def grain(amp):
    g = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.8)
    return (g / g.std() * amp)[..., None]

def unfaded(frames):
    # the fade-in is a brightness ramp over frames 0 to 29; gain each frame back to frame 30's level
    ref = frames[30].mean()
    return [np.clip(f * min(8.0, ref / max(f.mean(), 1.0)), 0, 255) for f in frames]

def burn(base, reveal, mask, a):
    # inside the shape, the overexposed warm court plus a white core; an orange glow and a red/blue fringe off the edges
    m = mask[..., None] * a
    hot = np.clip(reveal * 1.35 + 70, 0, 255) * np.array([0.82, 0.95, 1.08], np.float32)
    fill = 0.55 * hot + 0.45 * 255
    glow = cv2.GaussianBlur(mask, (0, 0), 26)[..., None] * np.array([30, 110, 255], np.float32) * 0.9 * a
    fr = np.zeros_like(base)
    fr[..., 2] = np.roll(mask, 4, 1) * 120 * a
    fr[..., 0] = np.roll(mask, -4, 1) * 90 * a
    x = base * (1 - m) + fill * m + glow + fr * (1 - mask[..., None])
    return np.clip(x + grain(9) * m, 0, 255)

def face2(frames):
    dc = decode(f'{R}/shots/upscale-test/out/datacenter-seedvr2-7b.mp4')
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    x, y, w, h = max(det.detectMultiScale(cv2.cvtColor(dc[40], cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(60, 60)), key=lambda b: b[2])
    cx, cy = x + w / 2, y + h / 2
    s = 0.36 * H / h                                        # face about a third of the frame, shoulders and room around it
    M = np.float32([[s, 0, W / 2 - s * cx], [0, s, H * 0.40 - s * cy]])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (0.42 * W), (yy - H * 0.45) / (0.62 * H))
    mask = np.clip((1.0 - r) / 0.5, 0, 1) ** 1.2
    src = np.linspace(22, 46, 15)                           # looks down, looks up, smiles, in 0.5 s
    env = [0.25, 0.45, 0.6, 0.68, 0.72, 0.72, 0.72, 0.7, 0.66, 0.58, 0.48, 0.36, 0.24, 0.12, 0.05]
    for n, (k, a) in enumerate(zip(src, env)):
        img = cv2.warpAffine(dc[int(round(k))], M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        grey = cv2.cvtColor(cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR).astype(np.float32)
        img = (grey * 0.55 + img * 0.45) * np.array([0.8, 0.94, 1.1], np.float32) * 1.3 * rng.uniform(0.88, 1.08)  # warm print, lit, flicker
        img = img + 0.5 * cv2.GaussianBlur(np.clip(img - 175, 0, None), (0, 0), 16) * np.array([0.25, 0.45, 1.0], np.float32)
        m = (mask * a)[..., None]
        frames[n] = np.clip(frames[n] * (1 - m) + (img + grain(10)) * m, 0, 255)
    return frames

def word_mask(word, width):
    path = os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-ExtraBold.ttf')
    l, t, r, b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), word, font=ImageFont.truetype(path, 400))
    font = ImageFont.truetype(path, int(400 * width / (r - l)))
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), word, font=font)
    d.text(((W - (r - l)) / 2 - l, (H - (b - t)) / 2 - t), word, font=font, fill=255)
    return cv2.GaussianBlur(np.asarray(im, np.float32) / 255, (0, 0), 0.8)

def jitter(m, px):
    return cv2.warpAffine(m, np.float32([[1, 0, rng.normal(0, px)], [0, 1, rng.normal(0, px * 0.7)]]), (W, H))

def name2(frames):
    words = {w: word_mask(w, 1720) for w in ('DYLAN', 'PATEL')}
    reveal = unfaded(frames)
    seq = [None, 'DYLAN', None, 'DYLAN', 'DYLAN', None, 'DYLAN', 'DYLAN',
           'PATEL', None, 'PATEL', None, 'PATEL', 'PATEL', 'PATEL']
    for n, w in enumerate(seq):
        if w: frames[n] = burn(frames[n], reveal[n], jitter(words[w], 3), rng.uniform(0.75, 1.0))
    return frames

def logo(frames):
    size = 560
    mark = cv2.resize(cv2.imread(f'{R}/refs/logo/mark-504.png', cv2.IMREAD_UNCHANGED), (size, size), interpolation=cv2.INTER_LANCZOS4)
    alpha = np.zeros((H, W), np.float32); art = np.zeros((H, W, 3), np.float32)
    sl = (slice((H - size) // 2, (H + size) // 2), slice((W - size) // 2, (W + size) // 2))
    alpha[sl] = mark[..., 3] / 255
    # the mark in the reel's warm print grade: its orange goes amber, its blue goes to a burnt brown, the lines stay hot
    rgb = mark[..., :3].astype(np.float32)
    grey = cv2.cvtColor(mark[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)[..., None]
    art[sl] = np.clip((0.6 * grey + 0.4 * rgb) * np.array([0.62, 0.9, 1.25], np.float32) * 1.15, 0, 255)
    for n, a in {8: 0.5, 9: 0.3, 11: 0.55, 12: 0.45, 14: 0.6, 16: 0.4}.items():   # 0.27 to 0.57 s
        M = np.float32([[1, 0, rng.normal(0, 3)], [0, 1, rng.normal(0, 2)]])
        m, img = cv2.warpAffine(alpha, M, (W, H)), cv2.warpAffine(art, M, (W, H))
        glow = cv2.GaussianBlur(m * (img.mean(2) / 255), (0, 0), 24)[..., None] * np.array([30, 110, 255], np.float32) * a
        x = frames[n] * (1 - (m * a)[..., None]) + (img + grain(10)) * (m * a)[..., None] + glow
        frames[n] = np.clip(x, 0, 255)
    return frames

def write(tag, edit):
    head = edit([f.astype(np.float32) for f in decode(BASE, SPAN)])
    total = int(subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_packets',
                                '-of', 'csv=p=0', BASE], capture_output=True, text=True, check=True).stdout)
    out = f'{OUT}/opener-{tag}.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-i', AUDIO, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '8', '-pix_fmt', 'yuv420p',
                            '-c:a', 'copy', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', BASE, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    for n in range(total):
        x = dec.stdout.read(W * H * 3)
        enc.stdin.write(np.clip(head[n], 0, 255).astype(np.uint8).tobytes() if n < SPAN else x)
    enc.stdin.close(); enc.wait(); dec.wait()
    assert enc.returncode == 0
    print('wrote', out, flush=True)

os.makedirs(OUT, exist_ok=True)
for tag in sys.argv[1:] or ('face2', 'name2', 'logo'):
    write(tag, {'face2': face2, 'name2': name2, 'logo': logo}[tag])
