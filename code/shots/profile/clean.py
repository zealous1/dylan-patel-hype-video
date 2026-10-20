"""v11: take LeBron out of every layer the profile scene uses, keeping the stadium behind him.

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/clean.py

1. src/clip.mp4 frames 804..899: Apple Vision foreground matte (matte.swift) of each frame, kept left of x 1000
   where LeBron is (the swoosh and flare are foreground too). Writes clean/lebron/NNN.png (1920x1080 masks).
   build.py dilates them and uses them for the plate (858 on) and to keep him out of the lifted flare.
2. shots/jersey/out/final-realtime.mp4 frames 36..45 (the take's tail, which build.py plays at 804..813 and then
   holds): the take carries a ghost of LeBron's profile there, top left of the player. The clean plate is the
   take's own frame 33, the last one before the ghost shows. It is aligned to each later frame with a similarity
   fitted to phase-correlated background patches (ECC on this dark, sparse stadium diverged), gain-matched on a ring around the area, and replaces the ghost area minus both players. Writes clean/jersey/NNN.png
   (1280x720). The jersey shot itself is not touched.
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import subprocess, tempfile
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
OUT = HERE / 'clean'
(OUT / 'lebron').mkdir(parents=True, exist_ok=True); (OUT / 'jersey').mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp())
MATTE = tmp / 'matte'
subprocess.run(['swiftc', '-O', str(HERE / 'matte.swift'), '-o', str(MATTE)], check=True)

def vision(img):
    p, m = tmp / 'in.png', tmp / 'm.png'
    cv2.imwrite(str(p), img)
    r = subprocess.run([str(MATTE), str(p), str(m)], capture_output=True)
    if r.returncode != 0: return np.zeros(img.shape[:2], np.uint8)
    return cv2.imread(str(m), cv2.IMREAD_GRAYSCALE)

def decode(path, w, h, first=0, count=None):
    vf = f'trim=start_frame={first}' + (f':end_frame={first + count}' if count else '') + ',setpts=PTS-STARTPTS'
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', vf, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)

# 1. LeBron in the original
W, H = 1920, 1080
xx = np.arange(W)[None, :]
orig = [] if (OUT / 'lebron/899.png').exists() else decode(R / 'src/clip.mp4', W, H, 804)
for i, f in enumerate(orig):
    m = vision(f); m[:, 1000:] = 0
    cv2.imwrite(str(OUT / 'lebron' / f'{804 + i}.png'), m)
print('lebron masks', len(orig))
del orig

# 2. the ghost in the jersey take's tail
w, h = 1280, 720
jr = decode(R / 'shots/jersey/out/final-realtime.mp4', w, h)
GHOST = np.zeros((h, w), np.uint8)
GHOST[:, :640] = 255   # the left half: the ghost reaches the player's shoulder, past build.py's deghost polygon
REF = 33   # last take frame before the ghost shows
players = {i: vision(jr[i]) for i in range(REF, len(jr))}
# camera drift: phase correlation of background patches against the reference gives point pairs, a similarity
# (scale, rotation, shift) is fitted to them; the last frames, where the ghost and the take's brighten hide the
# background, continue the drift of the three frames before (it is a slow, steady push)
win = cv2.createHanningWindow((200, 200), cv2.CV_32F)
G0 = cv2.cvtColor(jr[REF], cv2.COLOR_BGR2GRAY).astype(np.float32)
PATCHES = [(x, y) for x in (840, 1060) for y in (40, 260, 480)] + [(20, 500), (220, 500)]
warps = {}
for i in range(REF + 1, len(jr)):
    gi = cv2.cvtColor(jr[i], cv2.COLOR_BGR2GRAY).astype(np.float32)
    src, dst = [], []
    for x, y in PATCHES:
        (dx, dy), r = cv2.phaseCorrelate(G0[y:y + 200, x:x + 200], gi[y:y + 200, x:x + 200], win)
        if r > 0.12: src.append((x + 100, y + 100)); dst.append((x + 100 + dx, y + 100 + dy))
    M = cv2.estimateAffinePartial2D(np.float32(src), np.float32(dst), method=cv2.RANSAC, ransacReprojThreshold=3)[0] if len(src) >= 4 else None
    prev = warps.get(i - 1, np.eye(2, 3))
    # a fit that jumps more than the drift allows (8 px, 1% scale) is a bad match, not camera motion
    if M is not None and np.abs(M[:, 2] - prev[:, 2]).max() < 8 and np.abs(M[:, :2] - prev[:, :2]).max() < 0.01:
        warps[i] = M
    else:
        ks = sorted(warps)[-3:]
        warps[i] = warps[ks[-1]] + (warps[ks[-1]] - warps[ks[0]]) / (ks[-1] - ks[0]) * (i - ks[-1])
        print('extrapolated', i)
refp = cv2.dilate(players[REF], np.ones((9, 9), np.uint8)) > 40
for i in range(36, len(jr)):
    f = jr[i]; wk = warps[i]
    clean = cv2.warpAffine(jr[REF], wk, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    rp = cv2.warpAffine(refp.astype(np.uint8), wk, (w, h), flags=cv2.INTER_NEAREST) > 0
    # Vision joins the ghost face to the player, so the player is only what lies near where he stood in frame 33
    player = (cv2.dilate(players[i], np.ones((9, 9), np.uint8)) > 40) & (cv2.dilate(rp.astype(np.uint8), np.ones((21, 21), np.uint8)) > 0)
    # one brightness gain from the background outside the ghost area (the take brightens toward its end)
    bgr = (GHOST == 0) & ~player & ~rp
    gain = np.clip((f[bgr].astype(np.float32).mean(0) + 1) / (clean[bgr].mean(0) + 1), 0.8, 1.25)
    clean *= gain
    # the bottom rows keep the take: the warped reference brings its dark bottom margin up there, and the
    # player's matte stops short of the frame edge
    keep_bottom = np.arange(h)[:, None] >= 640
    rep = cv2.GaussianBlur(((GHOST > 0) & ~player & ~rp & ~keep_bottom).astype(np.float32), (0, 0), 6)[..., None]
    out = f * (1 - rep) + clean * rep
    cv2.imwrite(str(OUT / 'jersey' / f'{i:03d}.png'), np.clip(out, 0, 255).astype(np.uint8))
    print('jersey', i, 'warp', np.round(wk, 3).tolist(), 'gain', np.round(gain, 2).tolist())
