"""Matte the Wan i2v clip of Dylan for the profile scene (v10).

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/gen-video/prep.py [clip] [frames-dir]   (defaults out/wan-3.0-novideo.mp4, frames; both relative to this folder)
  v11: uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/gen-video/prep.py ../gen-video-v11/out/wan-3.0-novideo.mp4 ../gen-video-v11/frames

For every frame: Apple Vision's foreground mask (matte.swift, compiled once) marks the subject; on a band around
its edge the alpha comes from distance to the flat grey background instead, which keeps hair and beard strands;
then the alpha is smoothed over neighbouring frames so the edge does not flicker.
Writes frames/NNN.png and frames/NNN-mask.png (1280x720) beside this file.
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
clip = HERE / (sys.argv[1] if len(sys.argv) > 1 else 'out/wan-3.0-novideo.mp4')
OUT = HERE / (sys.argv[2] if len(sys.argv) > 2 else 'frames'); OUT.mkdir(exist_ok=True)
W, H = 1280, 720
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(clip), '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                     capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

tmp = Path(tempfile.mkdtemp())
matte = tmp / 'matte'
subprocess.run(['swiftc', '-O', str(HERE.parent / 'matte.swift'), '-o', str(matte)], check=True)
vis = []
for i, f in enumerate(fr):
    p = tmp / f'{i}.png'; m = tmp / f'{i}-m.png'
    cv2.imwrite(str(p), f[..., ::-1])
    subprocess.run([str(matte), str(p), str(m)], check=True, capture_output=True)
    vis.append(cv2.imread(str(m), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255)
vis = np.stack(vis)

# flat background colour: median of the pixels Vision calls background, over the whole clip
bg = np.median(fr[vis < 0.05].reshape(-1, 3)[::50].astype(np.float32), 0)
print('background', bg.round(1))
k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
alphas = []
for f, v in zip(fr, vis):
    d = np.linalg.norm(cv2.GaussianBlur(f.astype(np.float32), (0, 0), 0.7) - bg, axis=2)
    key = np.clip((d - 10) / 30, 0, 1)
    hard = (v > 0.5).astype(np.uint8)
    core = cv2.erode(hard, k5, iterations=1) > 0
    reach = cv2.dilate(hard, k5, iterations=2) > 0
    a = np.where(core, 1.0, np.where(reach, key, 0.0)).astype(np.float32)
    # keep only the subject's connected region (no stray specks off the background)
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.3).astype(np.uint8))
    keep = np.isin(lab, [1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))])
    a = a * cv2.dilate(keep.astype(np.uint8), k5)
    alphas.append(a)
alphas = np.stack(alphas)
# temporal stabilisation: the head moves only a few pixels a frame, so a short weighted average steadies the edge
wts = np.array([1, 2, 3, 2, 1], np.float32); wts /= wts.sum()
pad = np.concatenate([alphas[:1].repeat(2, 0), alphas, alphas[-1:].repeat(2, 0)])
stab = sum(w * pad[j:j + len(alphas)] for j, w in enumerate(wts))
# where the subject is solid in this frame, keep it solid (averaging only softens the edge band)
stab = np.where(alphas >= 0.999, 1.0, stab)
for i, (f, a) in enumerate(zip(fr, stab)):
    cv2.imwrite(str(OUT / f'{i:03d}.png'), f[..., ::-1])
    cv2.imwrite(str(OUT / f'{i:03d}-mask.png'), np.clip(a * 255, 0, 255).astype(np.uint8))
flick = np.abs(np.diff(stab, axis=0)).mean(axis=(1, 2)); raw_f = np.abs(np.diff(alphas, axis=0)).mean(axis=(1, 2))
print(f'frames {len(fr)}  mean frame-to-frame alpha change: raw {raw_f.mean():.4f}  stabilised {flick.mean():.4f}')
