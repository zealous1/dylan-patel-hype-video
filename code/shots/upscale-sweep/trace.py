# Maps each frame of a take back to the frame of the generation it was cut from, so the take can be rebuilt
# from an upscaled generation by picking the same frames. A take frame is a "pick" when one generation frame
# matches it to encode noise; anything else (a blend, a crop, a regrade) shows up as a high residual.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/upscale-sweep/trace.py TAKE GEN [--json OUT]
import argparse, json, subprocess
import numpy as np

def small(path, w=192, h=108):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)

ap = argparse.ArgumentParser()
ap.add_argument('take'); ap.add_argument('gen'); ap.add_argument('--json', default='')
a = ap.parse_args()
t, g = small(a.take), small(a.gen)
d = np.abs(t[:, None] - g[None]).mean((2, 3))
pick = d.argmin(1)
res = d[np.arange(len(t)), pick]
print(f'{a.take}: {len(t)} frames from {len(g)}; residual max {res.max():.2f} mean {res.mean():.2f}')
print('picks', pick.tolist())
print('steps', np.diff(pick).tolist())
if a.json:
    json.dump({'take': a.take, 'gen': a.gen, 'picks': pick.tolist(), 'residual': [round(float(x), 2) for x in res]}, open(a.json, 'w'))
