# Per-frame transition measures for a clip span: mean luma, sharpness, global shift (phase correlation),
# and blur direction (horizontal vs vertical gradient energy). Writes <name>.json beside this script.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I analysis/transitions/measure.py <video> <t0> <frames> <name>
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np, cv2
path, t0, n, name = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 480, 270
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-i', path, '-frames:v', str(n), '-vf', f'fps=30,scale={W}:{H}',
                      '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
win = cv2.createHanningWindow((W, H), cv2.CV_32F)
rows, prev = [], None
for i, f in enumerate(fr):
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0); gy = cv2.Sobel(f, cv2.CV_32F, 0, 1)
    ex, ey = float((gx ** 2).mean()), float((gy ** 2).mean())
    lap = float(cv2.Laplacian(f, cv2.CV_32F).var())
    shift, resp = (0, 0), 0
    if prev is not None:
        (dx, dy), resp = cv2.phaseCorrelate(prev, f, win)
        shift = (dx * 1920 / W, dy * 1080 / H)
    diff = float(np.abs(f - prev).mean()) if prev is not None else 0
    rows.append({'f': i, 't': round(t0 + i / 30, 3), 'y': round(float(f.mean()), 1), 'sharp': round(lap, 1),
                 'hv': round(ex / max(ey, 1e-3), 2), 'dx': round(shift[0], 1), 'dy': round(shift[1], 1),
                 'resp': round(float(resp), 3), 'diff': round(diff, 1)})
    prev = f
json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{name}.json'), 'w'))
