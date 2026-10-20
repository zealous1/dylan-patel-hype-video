"""Take the ghost of LeBron's profile out of the jersey take itself.

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/jersey/deghost.py            (from R; writes out/final-realtime-clean.mp4 and post/deghost.json)

The Wan take (out/final-realtime.mp4, 46 frames, 1280x720) carries a translucent ghost of the original's LeBron
profile in its tail, left of and over the player, down onto his left arm. Frame 33 is the last frame without it.
For every frame after it:
  1. frame 33 is aligned to the frame with a similarity (scale, rotation, shift) fitted to phase-correlated
     background patches; a fit that jumps more than the slow camera drift allows is replaced by the drift of the
     frames before (ECC diverges on this dark, sparse stadium);
  2. the aligned frame 33 is gain-matched to the frame on the background outside the ghost zone;
  3. the ghost matte is the difference between the frame and that clean frame, blurred, thresholded low (5
     levels: the ghost's inside is barely darker than the stadium), closed, and feathered, inside the ghost zone (left of x 560, above the bottom 80 rows: the 67's late purple tint and the
     reference's bottom margin stay out of it). No player matte is used, so the ghost's chin on the player's left
     arm is caught too;
  4. the clean frame replaces the frame under the matte, so the stadium behind stays real.
Frames before 34 are copied unchanged. The ghost score per frame (matte area and mean difference) goes to
post/deghost.json so frames where it starts can be read off.
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, subprocess
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / 'out/final-realtime.mp4', HERE / 'out/final-realtime-clean.mp4'
W, H, REF = 1280, 720, 33
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(SRC), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
jr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
ZONE = np.zeros((H, W), bool); ZONE[:640, :560] = True

win = cv2.createHanningWindow((200, 200), cv2.CV_32F)
gray = lambda a: cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
G0 = gray(jr[REF])
PATCHES = [(x, y) for x in (840, 1060) for y in (40, 260, 480)] + [(20, 500), (220, 500)]
warps = {REF: np.eye(2, 3)}
for i in list(range(REF + 1, len(jr))) + list(range(REF - 1, 23, -1)):
    gi = gray(jr[i]); src, dst = [], []
    for x, y in PATCHES:
        (dx, dy), r = cv2.phaseCorrelate(G0[y:y + 200, x:x + 200], gi[y:y + 200, x:x + 200], win)
        if r > 0.12: src.append((x + 100, y + 100)); dst.append((x + 100 + dx, y + 100 + dy))
    M = cv2.estimateAffinePartial2D(np.float32(src), np.float32(dst), method=cv2.RANSAC, ransacReprojThreshold=3)[0] if len(src) >= 4 else None
    step = 1 if i > REF else -1
    prev = warps[i - step]
    if M is not None and np.abs(M[:, 2] - prev[:, 2]).max() < 8 and np.abs(M[:, :2] - prev[:, :2]).max() < 0.01:
        warps[i] = M
    else:   # continue the drift of the three frames before
        ks = [i - step * k for k in (3, 2, 1)]
        warps[i] = warps[ks[-1]] + (warps[ks[-1]] - warps[ks[0]]) / 2
        print('extrapolated', i)

bgr = ~ZONE; bgr[640:] = False
report, out = [], []
for i in range(len(jr)):
    f = jr[i].astype(np.float32)
    if i not in warps or i == REF:
        out.append(jr[i]); continue
    clean = cv2.warpAffine(jr[REF], warps[i], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    clean *= np.clip((f[bgr].mean(0) + 1) / (clean[bgr].mean(0) + 1), 0.8, 1.25)
    d = np.abs(cv2.GaussianBlur(f, (0, 0), 3) - cv2.GaussianBlur(clean, (0, 0), 3)).max(2)
    # the ghost's dark inside is only a few levels under the dark stadium, so the threshold is low and the
    # closing is wide enough to fill the head between its brighter edges
    m = np.clip((d - 5) / 12, 0, 1) * ZONE
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    m = cv2.GaussianBlur(cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))), (0, 0), 4)
    m = np.clip(m * 1.5, 0, 1) * cv2.GaussianBlur(ZONE.astype(np.float32), (0, 0), 6)
    area = int((m > 0.5).sum()); score = round(float(d[ZONE].mean()), 2)
    report.append({'frame': i, 'ghost_px': area, 'mean_diff': score})
    print(i, area, score)
    if i > REF:
        out.append(np.clip(f * (1 - m[..., None]) + clean * m[..., None], 0, 255).astype(np.uint8))
    else:
        out.append(jr[i])
(HERE / 'post/deghost.json').write_text(json.dumps({'ref': REF, 'frames': report}, indent=1))
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', str(OUT)], stdin=subprocess.PIPE)
for o in out: enc.stdin.write(o.tobytes())
enc.stdin.close(); enc.wait()
print('wrote', OUT.name, len(out))
