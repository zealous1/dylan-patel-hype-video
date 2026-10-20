# Sharpness and temporal stability of upscale variants of one shot, all read at 1920x1080.
#   sharp    mean Laplacian variance per frame (the master/sharpness/sharp.py measure)
#   hf       mean |high-pass| per pixel, the detail an upscaler adds
#   flicker  mean |change of the high-pass| between consecutive frames, only on static 64 px tiles
#   flicker/hf  the same normalised by that tile's detail: a sharper variant with stable detail keeps this at the
#            baseline's level, while shimmer or boiling texture pushes it up
# Static tiles are picked once from the first video (the Lanczos baseline): tiles whose low-pass hardly changes
# between the two frames, so any high-frequency change there is the upscaler's, not the motion's.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/upscale-sweep/metrics.py --json OUT label=path ...
import argparse, json, subprocess
import numpy as np, cv2

W, H, T = 1920, 1080, 64

def gray(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)

def tiles(a):
    return a.reshape(a.shape[0] // T, T, a.shape[1] // T, T).mean((1, 3))

ap = argparse.ArgumentParser()
ap.add_argument('--json', default='')
ap.add_argument('--frames', default='', help='a:b, only this frame range')
ap.add_argument('videos', nargs='+')
a = ap.parse_args()
vids = [v.split('=', 1) for v in a.videos]
data = {k: gray(p) for k, p in vids}
n = min(len(v) for v in data.values())
lo, hi = map(int, a.frames.split(':')) if a.frames else (0, n)
crop = lambda x: x[:, :H // T * T, :]
base = crop(data[vids[0][0]][lo:hi])
lp = np.stack([cv2.GaussianBlur(f, (0, 0), 4) for f in base])
motion = np.stack([tiles(np.abs(lp[i + 1] - lp[i])) for i in range(len(lp) - 1)])
static = motion < np.quantile(motion, 0.2)
out = {}
for k, _ in vids:
    v = crop(data[k][lo:hi])
    hp = np.stack([f - cv2.GaussianBlur(f, (0, 0), 1.5) for f in v])
    hf_t = np.stack([tiles(np.abs(h)) for h in hp])
    fl_t = np.stack([tiles(np.abs(hp[i + 1] - hp[i])) for i in range(len(hp) - 1)])
    lap = float(np.mean([cv2.Laplacian(f.astype(np.uint8), cv2.CV_32F).var() for f in v]))
    hf_s = (hf_t[1:] + hf_t[:-1]) / 2
    out[k] = {'sharp': round(lap, 1), 'hf': round(float(hf_t.mean()), 3),
              'flicker': round(float(fl_t[static].mean()), 3),
              'flicker_per_hf': round(float((fl_t[static] / (hf_s[static] + 0.05)).mean()), 3)}
    print(f'{k:24s} sharp {out[k]["sharp"]:8.1f}  hf {out[k]["hf"]:6.3f}  flicker {out[k]["flicker"]:6.3f}  flicker/hf {out[k]["flicker_per_hf"]:5.3f}')
print(f'static tiles: {int(static.sum())} of {static.size} tile-pairs')
if a.json:
    json.dump(out, open(a.json, 'w'), indent=1)
