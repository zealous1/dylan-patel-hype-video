# Per-frame light of the original's last 6.5 s: mean luma, 99th-percentile luma, mean saturation, and the frame-to-frame
# luma ratio, so the flicker can be read as numbers.  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I analysis/flicker/measure.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, numpy as np, cv2
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
W, H = 480, 270
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '23.5', '-i', f'{R}/src/clip.mp4', '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
rows, prev = [], None
for i, x in enumerate(f):
    hsv = cv2.cvtColor(x, cv2.COLOR_BGR2HSV); y = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = float(y.mean()); rows.append({'t': round(23.5 + i / 30, 3), 'mean': round(m, 1), 'p99': float(np.percentile(y, 99)),
        'sat': round(float(hsv[..., 1].mean()), 1), 'ratio': round(m / prev, 3) if prev else 1.0}); prev = m
json.dump(rows, open(f'{R}/analysis/flicker/original.json', 'w'), indent=0)
for r in rows: print(r['t'], r['mean'], r['p99'], r['sat'], r['ratio'])
