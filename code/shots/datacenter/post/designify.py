# Paint the xAI sign out of the datacenter clip: a clean plate (Sunburst edit of frame 0) is aligned to each
# frame and composited over the sign's rectangle, minus Dylan's matte, so the hall reads unbranded.
#   uv run --no-project --python 3.12 --with-requirements ../../requirements.txt python -I post/designify.py   (from shots/datacenter)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import subprocess, sys, os
import cv2, numpy as np

SRC, PLATE, OUT = 'out/wan-3.0-novideo-min.mp4', '../../starts/out/dcplate-gpt-image-2.5-sunburst.png', 'out/clean-v1.mp4'
RECT = (628, 36, 850, 226)
MATTE = 'post/matte'
if not os.path.exists(MATTE):
    subprocess.run(['swiftc', '-O', '../profile/matte.swift', '-o', MATTE], check=True)
cap = cv2.VideoCapture(SRC); frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
H, W = frames[0].shape[:2]
plate = cv2.resize(cv2.imread(PLATE), (W, H), interpolation=cv2.INTER_AREA)

def matte(img, i):
    p, m = f'post/m{i:03d}.png', f'post/m{i:03d}-mask.png'
    cv2.imwrite(p, img); subprocess.run([MATTE, p, m], check=True, capture_output=True)
    k = cv2.imread(m, cv2.IMREAD_GRAYSCALE); os.remove(p); os.remove(m)
    return cv2.resize(k, (W, H))

def bgmask(person):
    m = np.full((H, W), 255, np.uint8); x0, y0, x1, y1 = RECT
    m[y0 - 10:y1 + 10, x0 - 10:x1 + 10] = 0
    m[cv2.dilate(person, np.ones((25, 25), np.uint8)) > 40] = 0
    return m

def align(src, dst, mask, mode=cv2.MOTION_AFFINE):
    w = np.eye(2, 3, dtype=np.float32)
    g = lambda a: cv2.GaussianBlur(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255, (5, 5), 0)
    _, w = cv2.findTransformECC(g(dst), g(src), w, mode, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), mask, 5)
    return w

m0 = matte(frames[0], 0)
plate = cv2.warpAffine(plate, align(plate, frames[0], bgmask(m0)), (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
x0, y0, x1, y1 = RECT
box = np.zeros((H, W), np.float32); box[y0:y1, x0:x1] = 1; box = cv2.GaussianBlur(box, (0, 0), 6)
ring = np.zeros((H, W), np.uint8); ring[y0 - 14:y1 + 14, x0 - 14:x1 + 14] = 1; ring[y0:y1, x0:x1] = 0

w = cv2.VideoWriter(OUT + '.tmp.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 30, (W, H))
for i, f in enumerate(frames):
    person = m0 if i == 0 else matte(f, i)
    wk = align(frames[0], f, bgmask(person))
    pk = cv2.warpAffine(plate, wk, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    bk = cv2.warpAffine(box, wk, (W, H), flags=cv2.WARP_INVERSE_MAP)
    rk = cv2.warpAffine(ring, wk, (W, H), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP) > 0
    pk *= (f[rk].astype(np.float32).mean(0) + 1) / (pk[rk].mean(0) + 1)
    keep = cv2.GaussianBlur(cv2.dilate(person, np.ones((5, 5), np.uint8)).astype(np.float32) / 255, (0, 0), 1.5)
    a = (bk * (1 - keep))[..., None]
    w.write(np.clip(f * (1 - a) + pk * a, 0, 255).astype(np.uint8))
    if i % 15 == 0: print(i, np.round(wk, 3).tolist(), flush=True)
w.release()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + '.tmp.mp4', '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', OUT], check=True)
os.remove(OUT + '.tmp.mp4')
