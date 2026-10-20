# Per-frame measures for a span of a video: colour (brightness, contrast, chroma, vividness of lit pixels, warmth),
# cuts, global motion between frames (scale and shift from matched features), the largest face, and face versus
# background colour. Writes lab/data/<name>.json.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/fastcuts/lab/measure.py <video> <first frame> <frames> <name>
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
path, f0, n, name = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 1920, 1080
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f"select='between(n\\,{f0}\\,{f0 + n - 1})',scale={W}:{H}",
                      '-vsync', '0', '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
assert len(frames) == n, len(frames)

CASCADES = [cv2.CascadeClassifier(cv2.data.haarcascades + c) for c in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml')]
ORB = cv2.ORB_create(1500)
BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
# Lit pixels: the original is mostly black arena, so a whole-frame chroma mean measures the blacks, not how vivid
# the lit subject is. Vividness is the chroma of pixels brighter than this luma.
LIT = 50

def colour(img, m=None):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * 100 / 255
    a, b = lab[..., 1] - 128, lab[..., 2] - 128
    C = np.hypot(a, b)
    y = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sel = np.ones(y.shape, bool) if m is None else m
    lit = sel & (y > LIT)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    r = lambda v: round(float(v), 2)
    out = {'y': r(y[sel].mean()), 'ystd': r(y[sel].std()), 'p5': r(np.percentile(y[sel], 5)), 'p95': r(np.percentile(y[sel], 95)),
           'chroma': r(C[sel].mean()), 'lit': r(lit.sum() / max(sel.sum(), 1))}
    if lit.sum() > 500:
        out.update(vivid=r(C[lit].mean()), sat=r(hsv[..., 1][lit].mean()), warm=r(b[lit].mean()), tint=r(a[lit].mean()), L=r(L[lit].mean()))
    return out

def face(gray):
    small = cv2.resize(gray, (W // 2, H // 2))
    found = [tuple(int(v) * 2 for v in r) for c in CASCADES for r in c.detectMultiScale(small, 1.1, 5, minSize=(40, 40))]
    found = [r for r in found if r[2] < W * 0.35]
    return max(found, key=lambda r: r[2] * r[3]) if found else None

def motion(a, b):
    """Similarity transform taking frame a to frame b on 960 px greys: scale, dx, dy in output pixels, and inliers."""
    ka, da = ORB.detectAndCompute(a, None)
    kb, db = ORB.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 12 or len(kb) < 12:
        return None
    m = BF.match(da, db)
    if len(m) < 12:
        return None
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3)
    if M is None or inl.sum() < 10:
        return None
    s = float(np.hypot(M[0, 0], M[1, 0]))
    # Shift of the frame centre, so a pure zoom about the centre reads as zero shift.
    c = np.array([480, 270])
    d = M[:, :2] @ c + M[:, 2] - c
    return {'s': round(s, 4), 'dx': round(float(d[0]) * 2, 1), 'dy': round(float(d[1]) * 2, 1), 'n': int(inl.sum())}

rows, prev_small, prev_grey = [], None, None
for i, img in enumerate(frames):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    grey = cv2.resize(g, (960, 540), interpolation=cv2.INTER_AREA)
    small = cv2.resize(g, (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32)
    row = {'f': i, **colour(img)}
    fb = face(g)
    if fb:
        x, y, w, h = fb
        row['face'] = [round(x / W, 4), round(y / H, 4), round(w / W, 4), round(h / H, 4)]
        m = np.zeros((H, W), bool); m[y:y + h, x:x + w] = True
        row['face_c'] = colour(img, m)
        # Person region: the face box widened and run to the bottom of frame; background is everything else.
        p = np.zeros((H, W), bool); p[max(y - h // 2, 0):, max(x - w, 0):x + 2 * w] = True
        if (~p).sum() > 5000:
            row['bg_c'] = colour(img, ~p)
    if prev_small is not None:
        a, b = prev_small - prev_small.mean(), small - small.mean()
        corr = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
        row['corr'] = round(corr, 3)
        row['diff'] = round(float(np.abs(prev_small - small).mean()), 1)
        row['cut'] = corr < 0.45 and row['diff'] > 18
        row['mo'] = motion(prev_grey, grey)
    prev_small, prev_grey = small, grey
    rows.append(row)
os.makedirs(os.path.join(HERE, 'data'), exist_ok=True)
json.dump({'video': os.path.relpath(path), 'first': f0, 'frames': n, 'rows': rows}, open(os.path.join(HERE, 'data', f'{name}.json'), 'w'))
print(name, n, 'frames,', sum(1 for r in rows if r.get('face')), 'with a face,', sum(1 for r in rows if r.get('cut')), 'cuts')
