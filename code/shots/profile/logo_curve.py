"""Measure the Nike swoosh's brightness in src/clip.mp4, frames 836..899, and write out/logo-curve-original.json.

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/logo_curve.py

Mask: the swoosh body, every pixel right of LeBron (x > 1000, 380 < y < 700) brighter than 70 on all of frames
866..883, eroded 5 px, so no background or jersey edge is counted. Per frame: mean luma over the body (mean), over
its tail beyond x 1550 (tail; the only part with no white jersey under it while it wipes in), the 99th percentile
(peak), the brightest 5% (core), mean saturation max-min of RGB (sat; low while it is white-hot), and halo =
mean luma of a ring 7 to 30 px outside the body minus the clean background below it (bloom). face is build.py's
cheek patch, for comparison: the swoosh pulses with the whole picture.
gain is mean over the settle level (mean of 880..887); build.py reads it.
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, subprocess
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
W, H, FIRST, LAST = 1920, 1080, 836, 899
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(R / 'src/clip.mp4'), '-vf', f'trim=start_frame={FIRST},setpts=PTS-STARTPTS',
                      '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
L = fr.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
yy, xx = np.mgrid[0:H, 0:W]
box = (xx > 1000) & (yy > 380) & (yy < 700)
body = box.copy()
for n in range(866, 884): body &= L[n - FIRST] > 70
body = cv2.erode(body.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
tail = body & (xx > 1550)
d = lambda k: cv2.dilate(body.astype(np.uint8), np.ones((k, k), np.uint8)) > 0
ring = d(61) & ~d(15) & (xx > 1550) & box
clean = (xx > 1500) & (yy > 720) & (yy < 1000)
rows = []
for n in range(FIRST, LAST + 1):
    f = fr[n - FIRST].astype(np.float32); l = L[n - FIRST]; v = l[body]; c = f[body]
    rows.append({'frame': n, 'mean': round(float(v.mean()), 2), 'tail': round(float(l[tail].mean()), 2),
                 'peak': round(float(np.percentile(v, 99)), 2), 'core': round(float(np.sort(v)[-len(v) // 20:].mean()), 2),
                 'sat': round(float((c.max(1) - c.min(1)).mean()), 2), 'halo': round(float(l[ring].mean() - l[clean].mean()), 2),
                 'face': round(float(fr[n - FIRST, 200:300, 560:700].mean()), 2)})
m = {r['frame']: r['mean'] for r in rows}
settle = float(np.mean([m[n] for n in range(880, 888)]))
for r in rows: r['gain'] = round(r['mean'] / settle, 4)
peak = max(range(858, 888), key=lambda n: m[n])
summary = {'peak_frame': peak, 'peak_mean': m[peak], 'settle_mean_880_887': round(settle, 2), 'peak_over_settle': round(m[peak] / settle, 3),
           'body_px': int(body.sum()), 'body_box': list(cv2.boundingRect(body.astype(np.uint8))),
           'max_halo': max(r['halo'] for r in rows if r['frame'] <= 887),
           'reading': ('The hook is white-hot and the tail wipes in from 838 to 858 (sat under 90). Colour comes in by 866. '
                       'Brightness climbs in pulses to the peak, then settles about a fifth lower and keeps flickering with '
                       'the whole picture (dips at 874, 875, 884, 885). The original has no measurable halo around the swoosh. '
                       'Frames 888 to 899 are its fade to black, which the build does not use (v9 hold).')}
out = HERE / 'out/logo-curve-original.json'
out.write_text(json.dumps({'summary': summary, 'frames': rows}, indent=1))
print(json.dumps(summary))
