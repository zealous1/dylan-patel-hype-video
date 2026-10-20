# Tracks Dylan's face through each clip's source span at 30 fps, in source pixels of the 1920x1080 decode that
# build.py uses. Writes lab/data/faces.json: {src: {"src_in", "boxes": [[cx, cy, w, h] normalised, per frame]}}.
# The track starts from the face nearest v14's framing centre and follows the nearest detection; misses are
# filled by interpolation and the track is smoothed, since Haar boxes jitter by a few percent frame to frame.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/fastcuts/lab/faces.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
W, H = 1920, 1080
edl = json.load(open(os.path.join(HERE, '..', 'edl-v14.json')))
CASC = [cv2.CascadeClassifier(cv2.data.haarcascades + c) for c in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml')]
SPAN = 1.0  # seconds decoded per clip: longer than any slot, so variants can stretch a clip
# Hand-marked where Haar loses him (a raised hand, a three-quarter profile, a tilted head), from 10% grids of each
# clip at 0, 0.5 and 1.0 s, sized like a Haar box (1.25 times brow to chin): {src: [(frame, cx, cy, w, h)]},
# interpolated between keys.
MANUAL = {
    'nv-1999': [(0, 0.445, 0.30, 0.13, 0.23), (30, 0.455, 0.29, 0.13, 0.23)],
    'nv-1940': [(0, 0.34, 0.53, 0.2, 0.35), (15, 0.38, 0.52, 0.2, 0.35), (30, 0.35, 0.51, 0.2, 0.35)],
    'lex-schizo': [(0, 0.535, 0.24, 0.16, 0.28), (15, 0.55, 0.23, 0.16, 0.28), (30, 0.53, 0.24, 0.16, 0.28)],
}

def decode(path, t, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', str(n), '-vf', f'fps=30,scale={W}:{H}:flags=lanczos',
                          '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def detect(img, min_px):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (W // 2, H // 2))
    out = []
    for c in CASC:
        for x, y, w, h in c.detectMultiScale(small, 1.08, 4, minSize=(min_px // 2, min_px // 2)):
            out.append(np.array([(x + w / 2) * 2, (y + h / 2) * 2, w * 2, h * 2], float))
    # Profile cascade only finds left-facing profiles; run it on the mirror too.
    flip = cv2.flip(small, 1)
    for x, y, w, h in CASC[1].detectMultiScale(flip, 1.08, 4, minSize=(min_px // 2, min_px // 2)):
        out.append(np.array([W - (x + w / 2) * 2, (y + h / 2) * 2, w * 2, h * 2], float))
    return out

def track(frames, seed, min_px=80):
    det = [detect(f, min_px) for f in frames]
    boxes, prev = [], np.array(seed, float)
    for ds in det:
        best = min(ds, key=lambda d: np.hypot(*(d[:2] - prev[:2])) + 0.5 * abs(d[2] - prev[2])) if ds else None
        ok = best is not None and np.hypot(*(best[:2] - prev[:2])) < max(prev[2], 120) * 0.8
        boxes.append(best if ok else None)
        if ok:
            prev = best
    idx = [i for i, b in enumerate(boxes) if b is not None]
    assert idx, 'no face found'
    arr = np.array([np.interp(range(len(boxes)), idx, [boxes[i][k] for i in idx]) for k in range(4)]).T
    k = np.ones(5) / 5
    sm = np.array([np.convolve(np.pad(arr[:, j], 2, mode='edge'), k, 'valid') for j in range(4)]).T
    # Face size changes slowly in a sit-down interview; a steadier size keeps the match cuts from pumping.
    sm[:, 2:] = np.median(arr[:, 2:], 0) * 0.5 + sm[:, 2:] * 0.5
    return sm, len(idx) / len(boxes)

out = {}
for c in edl['clips']:
    s = edl['sources'][c['src']]
    if c.get('kind') == 'jensen-zoom':
        # Jensen is small in the 4K stage shot, so track him in a native-resolution window around the stage centre.
        cw, ch, x0, y0 = 1920, 1080, 960, 160
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f"{c['src_in']:.3f}", '-i', os.path.join(R, s['file']), '-frames:v', str(int(SPAN * 30)),
                              '-vf', f'fps=30,crop={cw}:{ch}:{x0}:{y0}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, ch, cw, 3)
        sm, hit = track(fr, (1854 - x0, 684 - y0, 140, 140), 60)
        out[c['src']] = {'src_in': c['src_in'], 'hit': round(hit, 2), 'frame': [3840, 2160],
                         'boxes': [[round((b[0] + x0) / 3840, 4), round((b[1] + y0) / 2160, 4), round(b[2] / 3840, 4), round(b[3] / 2160, 4)] for b in sm]}
        print(c['src'], f'hit {hit:.0%}', 'first', out[c['src']]['boxes'][0], 'size px (4K)', round(float(np.median(sm[:, 3]))))
        continue
    if c['src'] in MANUAL:
        keys = np.array(MANUAL[c['src']])
        boxes = [[round(float(np.interp(i, keys[:, 0], keys[:, k])), 4) for k in range(1, 5)] for i in range(int(SPAN * 30))]
        out[c['src']] = {'src_in': c['src_in'], 'hit': 'hand-marked', 'boxes': boxes}
        print(c['src'], 'hand-marked')
        continue
    if c.get('kind') == 'hero':
        fr = decode(os.path.join(R, s['file']), 0, 91)
        seed, min_px = (0.5 * W, 0.3 * H, 90, 90), 40
    else:
        fr = decode(os.path.join(R, s['file']), c['src_in'], int(SPAN * 30))
        # Seed at v14's framing centre, a little above it, where the face sits in a push-in.
        seed, min_px = (c['cx'] * W, c['cy'] * H, 200, 200), 80
    sm, hit = track(fr, seed, min_px)
    out[c['src']] = {'src_in': 0 if c.get('kind') == 'hero' else c['src_in'], 'hit': round(hit, 2),
                     'boxes': [[round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)] for b in sm]}
    print(c['src'], f'hit {hit:.0%}', 'first', out[c['src']]['boxes'][0], 'size px', round(float(np.median(sm[:, 3]))))
json.dump(out, open(os.path.join(HERE, 'data', 'faces.json'), 'w'))
