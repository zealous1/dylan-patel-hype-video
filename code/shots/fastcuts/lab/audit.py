# Direction audit: measures which way the picture travels across every transition, and sweeps every frame pair for
# rightward travel, which Zeal's rule forbids (it reads as the camera going back). Writes lab/data/audit-<name>.json.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/fastcuts/lab/audit.py <video> <first frame> <name> <edl json | frames,comma,list>
# With an EDL the transitions are its clip boundaries; otherwise the listed section frames (the original's, marked
# from its contact sheet).
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, math, os, subprocess, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
path, f0, name, spec = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
N, W, H = 209, 480, 270
SCALE = 1920 / W
RIGHT_PX = 8  # px a frame at 1920 wide; head drift and shake stay under it

if spec.endswith('.json'):
    edl = json.load(open(spec))
    cuts = [round(c['slot_in'] * 30) for c in edl['clips'][1:]]
    named = edl['section'].get('lab', {}).get('moves')
else:
    cuts, named = [int(x) for x in spec.split(',')], None

raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f"select='between(n\\,{f0}\\,{f0 + N - 1})',scale={W}:{H}",
                      '-vsync', '0', '-frames:v', str(N), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
R = math.hypot(W, H) / 2

def logpolar(img):
    return cv2.warpPolar(img, (W, H), (W / 2, H / 2), R, cv2.WARP_POLAR_LOG + cv2.INTER_LINEAR)

ORB = cv2.ORB_create(1500)
BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
U8 = fr.astype(np.uint8)

def orb(a, b):
    """The dominant similarity motion (RANSAC over matched corners): the room, not a waving hand. None when blurred."""
    ka, da = ORB.detectAndCompute(U8[a], None)
    kb, db = ORB.detectAndCompute(U8[b], None)
    if da is None or db is None or len(ka) < 30 or len(kb) < 30:
        return None
    m = BF.match(da, db)
    if len(m) < 30:
        return None
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=2)
    if M is None or inl.sum() < 40:
        return None
    c = np.array([W / 2, H / 2])
    d = M[:, :2] @ c + M[:, 2] - c
    return float(d[0]) * SCALE, float(d[1]) * SCALE, float(np.hypot(M[0, 0], M[1, 0])), int(inl.sum())

def shift1d(pa, pb, reach):
    """Shift of profile pb against pa by cross-correlation, within +-reach samples."""
    pa, pb = pa - pa.mean(), pb - pb.mean()
    cc = np.correlate(pb, pa, 'full')[len(pa) - 1 - reach:len(pa) + reach]
    return int(cc.argmax()) - reach, float(cc.max() / (np.sqrt((pa * pa).sum() * (pb * pb).sum()) + 1e-6))

def step(a, b):
    """Travel from frame a to frame b: the shift of the frame centre in 1920 px and the zoom factor. Matched corners
    when there are enough; otherwise the column and row brightness profiles, whose shift a motion blur leaves alone
    (phase correlation between a sharp and a smeared frame reported landings as rightward jumps)."""
    o = orb(a, b)
    if o:
        return {'dx': round(o[0], 1), 'dy': round(o[1], 1), 'r': 1.0, 'z': round(o[2], 4), 'how': 'orb'}
    dx, rx = shift1d(fr[a].mean(0), fr[b].mean(0), W // 4)
    dy, ry = shift1d(fr[a].mean(1), fr[b].mean(1), H // 4)
    (lr, _), rz = cv2.phaseCorrelate(logpolar(fr[a]), logpolar(fr[b]))
    z = math.exp(lr * math.log(R) / W) if math.isfinite(lr) and rz > 0.05 else 1.0
    return {'dx': round(dx * SCALE, 1), 'dy': round(dy * SCALE, 1), 'r': round(min(rx, ry), 3), 'z': round(z, 4), 'how': 'profile'}

def side(pairs):
    """The dominant travel over a few frame pairs on one side of a transition."""
    ms = [step(a, b) for a, b in pairs if 0 <= a < N and 0 <= b < N]
    if not ms:
        return None
    w = np.array([max(m['r'], 0.02) for m in ms])
    dx, dy = float(np.average([m['dx'] for m in ms], weights=w)), float(np.average([m['dy'] for m in ms], weights=w))
    lz = float(np.mean([math.log(m['z']) for m in ms]))
    shift = max(abs(dx), abs(dy))
    if abs(lz) * 900 > shift and abs(lz) > 0.012:
        d = 'zoom in' if lz > 0 else 'zoom out'
    elif shift < 4:
        d = 'still'
    elif abs(dx) >= abs(dy):
        d = 'left' if dx < 0 else 'right'
    else:
        d = 'up' if dy < 0 else 'down'
    return {'dx': round(dx, 1), 'dy': round(dy, 1), 'zoom': round(math.exp(lz), 4), 'dir': d}

trans = []
for k, c in enumerate(cuts):
    out = side([(c - 4, c - 3), (c - 3, c - 2), (c - 2, c - 1)])
    inn = side([(c, c + 1), (c + 1, c + 2), (c + 2, c + 3)])
    bad = [s['dir'] for s in (out, inn) if s and s['dir'] == 'right' and s['dx'] > RIGHT_PX]
    trans.append({'frame': c, 'move': named[k] if named else None, 'out': out, 'in': inn, 'ok': not bad})

edges = set()
for c in cuts:
    edges.update({c - 1})
sweep = []
for a in range(N - 1):
    if a in edges:
        continue
    m = step(a, a + 1)
    if m['dx'] > RIGHT_PX and abs(m['dx']) > abs(m['dy']) and m['r'] > 0.5 and abs(math.log(m['z'])) * 900 < m['dx']:
        sweep.append({'frame': a + 1, **m})
os.makedirs(os.path.join(HERE, 'data'), exist_ok=True)
json.dump({'name': name, 'video': os.path.relpath(path), 'first': f0, 'transitions': trans, 'right_frames': sweep},
          open(os.path.join(HERE, 'data', f'audit-{name}.json'), 'w'), indent=1)
print(name, 'transitions:', ' '.join(f"{t['frame']}:{t['out']['dir'] if t['out'] else '-'}>{t['in']['dir'] if t['in'] else '-'}{'' if t['ok'] else '!'}" for t in trans))
print(name, 'rightward frames:', [s['frame'] for s in sweep])
