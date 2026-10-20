"""Profile scene (the ending): the jersey take fades out under a cut-out Dylan profile, then the SemiAnalysis
logo comes in where the Nike swoosh did. Every timing curve is measured from src/clip.mp4, frame by frame.

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/build.py --start 804 --tag profile-v12-from804 --video gen-video-v12/frames --fixed --clean --turn 834,915 --jersey shots/jersey/out/final-realtime-clean.mp4 --v12
  v15: --start 784 --tag profile-v15-from784 --video gen-video-v13/frames --still gen-video-v13/frames/080.png --fixed --clean --turn 786,901 --jersey shots/jersey/out/jersey-timeline.mp4 --v12 --v13 --v14 --v15
  v14 (prep as v13): --tag profile-v14-from804 --video gen-video-v13/frames --still gen-video-v13/frames/080.png --fixed --clean --turn 806,901 --jersey shots/jersey/out/jersey-timeline.mp4 --v12 --v13 --v14
  v13 (first: uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/profile/gen-video/prep.py ../gen-video-v13/out/span-158-238.mp4 ../gen-video-v13/frames):
       --tag profile-v13-from804 --video gen-video-v13/frames --still gen-video-v13/frames/080.png --fixed --clean --turn 806,901 --jersey shots/jersey/out/final-realtime-clean.mp4 --v12 --v13
  v11: --tag profile-v11-from804 --video gen-video-v11/frames --logo-curve --fixed --clean --turn 822,892
  v10: --video gen-video/frames --tag profile-v10-from804
  v9: --video '' --v9-logo --still gen/up-b.png --tag profile-v9-from804

Inputs (relative to the reel folder R):
  src/clip.mp4                           original; gives the background plate, flare, timing curves and grade
  shots/jersey/out/final-realtime.mp4    the jersey take, held on its last frame and faded out
  shots/profile/gen/profile-b.png        Sunburst still of Dylan in profile, plus profile-b-mask.png (matte.swift)
  shots/profile/gen-video/frames/        v10 default: the Wan i2v clip of Dylan, matted per frame (gen-video/prep.py)
                                         --video '' uses the still instead (v9)
  refs/logo/end-logo.png                 the end logo
Output: shots/profile/out/<tag>.mp4, 1920x1080, 30 fps, no audio, frames <start>..899 plus 2 tail frames.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np, cv2
from PIL import Image

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
W, H = 1920, 1080
ap = argparse.ArgumentParser()
ap.add_argument('--start', type=int, default=814)   # 27.133 s; the profile layer first shows at frame 806
ap.add_argument('--tag', default='profile-v10')
ap.add_argument('--fade', action='store_true', help='v8 ending: fade everything but the logo to black from 888')
ap.add_argument('--still', default='')                # default: the video's reference frame, or gen/up-b.png
ap.add_argument('--nose', default='815,330')         # where the nose tip sits at frame 857
ap.add_argument('--scale', type=float, default=0)    # 0: from stills.json
ap.add_argument('--video', default='gen-video/frames', help='dir of i2v frames NNN.png + NNN-mask.png (gen-video/prep.py); empty = the still')
ap.add_argument('--v9-logo', action='store_true', help='the v9 logo grade instead of the v10 colour match')
ap.add_argument('--fixed', action='store_true', help='v11: the profile sits at its final position and size from its first frame (no rise, push or drift)')
ap.add_argument('--clean', action='store_true', help='v11: LeBron out of plate, flare and jersey take, from clean/ (shots/profile/clean.py)')
ap.add_argument('--turn', default='', help='v11: a,b = the comp frames the clip runs over (it holds its first and last frame outside); default 806..901')
ap.add_argument('--jersey', default='shots/jersey/out/final-realtime.mp4', help='the jersey take; v12 uses the deghosted final-realtime-clean.mp4 (shots/jersey/deghost.py) as it is')
ap.add_argument('--v12', action='store_true', help='v12 end card: the plain SemiAnalysis mark and wordmark fading in and holding, the arcmira line fading in and out near the bottom, the logo dimmed a little at the end')
ap.add_argument('--v13', action='store_true', help='v13: as v12, but the mentions line is not drawn here; the jersey scene\'s line (shots/jersey/out/mentions-layer.png) carries over from 804 and eases out ahead of the jersey')
ap.add_argument('--v14', action='store_true', help='v14: the jersey is moving video through the whole crossfade (shots/jersey/out/jersey-timeline.mp4, frame i = reel 763 + i), the mentions line follows the jersey opacity curve 2 frames early, and the frames are clean: a static median plate and flare, no added flicker or grain (the film look is a separate pass)')
ap.add_argument('--v15', action='store_true', help='v15 (2026-10-17): as v14 with the slot starting at 784 (--start 784; the jersey scene gives up its last 20 frames), the face fading in slower and earlier (smoothstep 786..846), the arcmira line fading out from 796 to 820, and the logo fading in over 840..866')
ap.add_argument('--logo-curve', action='store_true', help='v11: the logo glows in and settles on the swoosh curve (out/logo-curve-original.json)')
args = ap.parse_args()
if not args.still: args.still = f'{args.video}/089.png' if args.video else 'gen/up-b.png'
END = 899                                           # last frame of the original (black)
TAIL = 2                                            # 30.00 to 30.07, hold the last frame

def decode(path, w, h, first=0):
    vf = f'trim=start_frame={first},setpts=PTS-STARTPTS'
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vf', vf, '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)

FIRST = 780                                          # only the tail of the original is needed (uint8, ~0.7 GB)
_orig = decode(R / 'src/clip.mp4', W, H, FIRST)
class _Orig:
    def __getitem__(self, n): return _orig[n - FIRST].astype(np.float32)
orig = _Orig()
lum = lambda a: a @ np.array([0.299, 0.587, 0.114], np.float32)
ease = lambda t: float(np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1)))

# ---------- timing curves measured from the original ----------
def region_mean(n, y0, y1, x0, x1): return float(_orig[n - FIRST, y0:y1, x0:x1].mean())
J = {n: region_mean(n, 750, 950, 900, 1100) for n in range(780, 900)}   # jersey body, no profile there
F = {n: region_mean(n, 200, 300, 560, 700) for n in range(780, 900)}    # profile cheek/temple
ALL = {n: float(_orig[n - FIRST].mean()) for n in range(780, 900)}
BG = 26.0
V15_FACE, V15_LINE, V15_LOGO = (786, 846), (796, 820), (840, 866)
def pulse(S, n, lo=0.86, hi=1.1):
    # the original's own frame-to-frame flicker in a region: its brightness over its 7-frame running median
    k = look(n)
    med = float(np.median([S[j] for j in range(k - 3, k + 4) if j in S]))
    return float(np.clip(S[k] / max(med, 1e-3), lo, hi)) if k in S else 1.0
def profile_opacity(n):        # 0 before 806, measured ramp and flicker until the jersey is gone, then 1
    if args.v15:
        # (2026-10-17) eased in over 786..846, then pulsing with the original face's flicker, and easing down
        # to 80% by the last frame
        o = ease((n - V15_FACE[0]) / (V15_FACE[1] - V15_FACE[0])) * (1 - 0.2 * ease((n - 860) / (END + TAIL - 860)))
        return float(min(1.0, o * pulse(F, n) ** ease((n - 836) / 10)))
    if n >= 843: return 1.0
    # the cheek patch reads brighter than the layer's real opacity while the jersey is up
    k = 0.22 + 0.78 * np.clip((n - 835) / 8, 0, 1)
    return float(np.clip((F[n] - BG) / (160 - BG), 0, 1) * k)
HOLD_FROM = 888
def look(n):
    # v9 (Zeal 2026-10-17): no fade to black. From 888 the plate, flare and flicker keep cycling through the
    # last full-colour frames (878..887) so the duotone and glow hold to the end; only the motion advances.
    return n if args.fade or n < HOLD_FROM else 878 + (n - 878) % 10
def settle(n):                 # a slight settle instead of the fade: about 6% darker by the end, eased
    if args.fade or n < HOLD_FROM: return 1.0
    t = np.clip((n - HOLD_FROM) / (END + TAIL - HOLD_FROM), 0, 1)
    return float(1 - 0.06 * (t * t * (3 - 2 * t)))
def profile_gain(n):           # brightness flicker of the profile layer once it is alone
    if args.v14: return 1.0    # v14: clean frames, the flicker comes from the film pass
    n = look(n)
    return float(np.clip(F[n] / 160, 0.75, 1.12)) if n >= 843 else 1.0
J0 = J[835]
def jersey_opacity(n):
    if n <= 835: return 1.0
    return float(np.clip((J[n] - BG) / (J0 - BG) / 0.92, 0, 1)) if n < 857 else 0.0
def jersey_yellow(n): return float(np.clip((n - 835) / 4, 0, 1))
def fade(n):                   # global fade to black, from the frame mean (v8 only)
    if not args.fade: return settle(n)
    return float(np.clip(ALL[n] / ALL[887], 0, 1)) if n >= 888 else 1.0

# ---------- inset (rounded picture area the original keeps on every frame) ----------
X0, X1, Y0, Y1, RAD = 98, 1818, 55, 1026, 36
inset = np.zeros((H * 4, W * 4), np.uint8)
cv2.rectangle(inset, ((X0 + RAD) * 4, Y0 * 4), ((X1 - RAD) * 4, Y1 * 4), 255, -1)
cv2.rectangle(inset, (X0 * 4, (Y0 + RAD) * 4), (X1 * 4, (Y1 - RAD) * 4), 255, -1)
for cx, cy in [(X0 + RAD, Y0 + RAD), (X1 - RAD, Y0 + RAD), (X0 + RAD, Y1 - RAD), (X1 - RAD, Y1 - RAD)]:
    cv2.circle(inset, (cx * 4, cy * 4), RAD * 4, 255, -1)
inset = cv2.resize(inset, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255

# ---------- swoosh and LeBron masks, background plate and flare ----------
FLARE = (875, 133, 62)
yy, xx = np.mgrid[0:H, 0:W]
flare_disc = ((xx - FLARE[0]) ** 2 + (yy - FLARE[1]) ** 2 < FLARE[2] ** 2)
sw = np.zeros((H, W), bool)
for n in range(860, 887):
    L = lum(orig[n]); sw |= (L > 70) & (xx > 1000) & (yy > 380) & (yy < 700)
sw = cv2.dilate(sw.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
SW_BOX = cv2.boundingRect(sw.astype(np.uint8))   # x, y, w, h
SWF = {n: float(_orig[n - FIRST][sw].mean()) for n in range(860, 900)}   # the swoosh's own brightness, for v15's logo pulse

def plate_of(n):
    """Original frame n (>= 858) with LeBron, the swoosh and the flare replaced by its own clean background."""
    f = orig[n].copy(); L = lum(f)
    lb = ((L > 31) | (L < 21)) & (xx < 1000)
    lb = cv2.morphologyEx(lb.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    # everything left of the rightmost LeBron pixel in each row belongs to him
    right = np.where(lb.any(1), W - 1 - np.argmax(lb[:, ::-1], 1), -1)
    lbm = xx <= right[:, None] + 14
    if args.clean: lbm = lbm | lebron_mask(n)                 # v11: Apple Vision's matte of him as well, dilated
    m = (lbm | sw | flare_disc).astype(np.uint8)
    m = cv2.GaussianBlur(cv2.dilate(m, np.ones((7, 7), np.uint8)).astype(np.float32), (9, 9), 0)
    tex = f[720:1010, 1020:1790]                              # clean background in the same frame
    tex = np.concatenate([tex, tex[:, ::-1]], 1); tex = np.concatenate([tex, tex[::-1]], 0)
    tile = np.tile(tex, (H // tex.shape[0] + 1, W // tex.shape[1] + 1, 1))[:H, :W]
    tile = np.roll(tile, (n * 37) % 200, 1)                   # grain keeps moving
    if args.clean:                                            # the fill matches the backdrop right around him
        ring = (cv2.dilate((m > 0.01).astype(np.uint8), np.ones((41, 41), np.uint8)) > 0) & (m <= 0.01) & (inset > 0.99) & ~flare_disc
        if ring.sum() > 500: tile = tile * np.clip((f[ring].mean(0) + 1) / (tile[ring].mean(0) + 1), 0.8, 1.25)
    return f * (1 - m[..., None]) + tile * m[..., None]

def lebron_mask(n):
    m = cv2.imread(str(HERE / f'clean/lebron/{n}.png'), cv2.IMREAD_GRAYSCALE)
    return cv2.dilate((m > 40).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0
plates = {n: plate_of(n).astype(np.float16) for n in range(858, 900)}
def _p(n): return plates[n].astype(np.float32)
if args.v14:
    # one clean plate: the median of the held frames, so no grain, scratch or flicker moves in it
    STATIC_PLATE = np.median(np.stack([_p(n) for n in range(858, 888)]), 0).astype(np.float32)
def plate(n):
    if args.v14: return STATIC_PLATE
    n = look(n)
    return _p(n) if n >= 858 else _p(858 + (n - 814) % 30)
FLARE_SOFT = cv2.GaussianBlur(flare_disc.astype(np.float32), (31, 31), 0)[..., None]
if args.v14:
    _fs = [np.clip(orig[n] - _p(n), 0, None) * FLARE_SOFT * (1 - cv2.GaussianBlur(lebron_mask(n).astype(np.float32), (0, 0), 3))[..., None]
           for n in range(858, 888)]
    STATIC_FLARE = np.median(np.stack(_fs), 0).astype(np.float32); del _fs
def flare_add(n):
    """The original's lens flare by his brow, lifted off its own background."""
    if n < 845: return None
    if args.v14: return STATIC_FLARE * ease((n - 844) / 3)   # v14: one steady flare, eased on at 845
    n = look(n)
    ref = _p(n) if n >= 858 else BG
    soft = FLARE_SOFT
    if args.clean:   # v11: what is lifted is the flare only, never LeBron's brow or the original jersey under it
        soft = soft * (1 - cv2.GaussianBlur(lebron_mask(n).astype(np.float32), (0, 0), 3))[..., None]
    return np.clip(orig[n] - ref, 0, None) * soft

# ---------- grade learned from LeBron's profile (frames 860..886) ----------
def lebron_pixels(n):
    L = lum(orig[n]); lb = ((L > 31) | (L < 21)) & (xx < 1000) & ~flare_disc
    lb = cv2.morphologyEx(lb.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8)) > 0
    right = np.where(lb.any(1), W - 1 - np.argmax(lb[:, ::-1], 1), -1)
    m = (xx <= right[:, None]) & (inset > 0.99) & ~flare_disc
    return orig[n][m]
px = np.concatenate([lebron_pixels(n) for n in range(860, 887, 3)])
pl = lum(px)
order = np.argsort(pl); pl_sorted = pl[order]
qs = np.linspace(0, 1, 1025)
lebron_q = np.quantile(pl_sorted, qs)                       # target luminance distribution
lut = np.zeros((256, 3), np.float32)                        # luminance -> mean colour in LeBron's grade
bins = np.clip(pl.astype(int), 0, 255)
for v in range(256):
    sel = px[bins == v]
    lut[v] = sel.mean(0) if len(sel) > 20 else np.nan
idx = np.arange(256); ok = ~np.isnan(lut[:, 0])
for c in range(3): lut[:, c] = np.interp(idx, idx[ok], lut[ok, c])
lut = cv2.GaussianBlur(lut[None], (1, 9), 0)[0]

# ---------- Dylan still: matte, relight, grade ----------
def load_still(p):
    im = np.asarray(Image.open(p).convert('RGB')).astype(np.float32)
    a = np.asarray(Image.open(str(p).replace('.png', '-mask.png')).convert('L')).astype(np.float32) / 255
    return im, a
still_path = HERE / args.still
im0, a0 = load_still(still_path)
bgc = np.median(im0[a0 < 0.02], 0)
LM = json.loads((HERE / 'gen/stills.json').read_text())[args.still]
if not args.scale: args.scale = LM.get('scale', 1.05)
# i2v frames: the clip (90 frames) is stretched over the profile's whole time on screen, 806..901, blending
# neighbouring frames, so his breath and the lift of his gaze span the scene and end as the picture holds
VID = []
if args.video:
    for pth in sorted((HERE / args.video).glob('[0-9][0-9][0-9].png')):
        im, am = load_still(pth); VID.append((im.astype(np.uint8), (am * 255).astype(np.uint8)))
V0, V1 = (806, END + TAIL) if not args.turn else tuple(int(v) for v in args.turn.split(','))
def vid_pos(n): return float(np.clip((n - V0) / (V1 - V0), 0, 1)) * (len(VID) - 1)
def grade_still(im, a, seed, inframe=None, src_q=None):
    sh, sw_ = a.shape
    a = np.clip((a - 0.04) / 0.92, 0, 1)
    au = np.clip(a, 0.08, 1)[..., None]
    fg = np.clip((im - (1 - a[..., None]) * bgc) / au, 0, 255)      # take the grey spill off the edges
    L = lum(fg)
    # key light from in front of the face: the back of the head and neck fall off, the face stays lit
    d = LM['nose'][0] - LM['ear'][0]                                  # head size; the light rig scales with it
    gx = np.clip((np.arange(sw_) - (LM['ear'][0] - 0.11 * d)) / (1.05 * d), 0, 1); gx = gx * gx * (3 - 2 * gx)
    gy = np.clip((np.arange(sh) - (LM['ear'][1] + 0.6 * d)) / (0.52 * d), 0, 1)[:, None]   # top of the shoulder catches light
    gain = 0.68 + 0.5 * np.maximum(gx[None, :], gy)
    L = L * gain
    rng = np.random.default_rng(seed)
    L = cv2.GaussianBlur(L, (0, 0), 1.0) + (0 if args.v14 else rng.normal(0, 4.0, L.shape))
    # match LeBron's luminance distribution inside the silhouette, then colour by his grade
    inside = (a > 0.5) if inframe is None else (a > 0.5) & inframe
    if src_q is None: src_q = np.quantile(L[inside], qs)   # video: one mapping for every frame, so no flicker
    Lm = np.interp(L, src_q, lebron_q)
    rgb = lut[np.clip(Lm, 0, 255).astype(int)]
    grade_still.src_q = src_q
    return rgb, a

# placement: source nose tip (912, 687) lands at the LeBron nose line, slow push like the original
NOSE_SRC = np.array(LM['nose'], float); EAR_SRC = np.array(LM['ear'], float)
NOSE_AT = np.array(LM['nose_at'], float) if 'nose_at' in LM and args.nose == '815,330' else np.array([float(v) for v in args.nose.split(',')])
def placement(n):
    if args.fixed and n != END + TAIL: return placement(END + TAIL)   # v11: final position and size throughout
    # slow push like the original: the nose drifts about 1.6 px a frame to the right (measured 857..887)
    # and before that it rises in from lower left: nose about (730,490) at 814, (790,395) at 844 (read off frames)
    t = n - 857
    s = args.scale * (1.0 + 0.0011 * t)
    dx = 1.6 * t if n >= 844 else 1.6 * (844 - 857) + 2.0 * (n - 844)
    dy = -0.15 * t if n >= 857 else (23.0 * (857 - n) / 13 if n >= 844 else 23.0 + 3.2 * (844 - n))
    nose = NOSE_AT + np.array([dx, dy])
    M = cv2.getRotationMatrix2D(tuple(EAR_SRC), LM.get('rot', 0), s)   # positive = chin up
    p = M @ np.array([*NOSE_SRC, 1.0])
    M[:, 2] += nose - p
    return M

def inframe_mask(n, shape):
    # source pixels that land inside the picture at frame n; LeBron's grade is matched on what we show
    Mi = cv2.invertAffineTransform(placement(n))
    src = cv2.warpAffine(inset, Mi, (shape[1], shape[0]), flags=cv2.INTER_NEAREST, borderValue=0)
    return src > 0.5
graded, alpha = grade_still(im0, a0, 1, inframe_mask(872, a0.shape))
SRC_Q = grade_still.src_q

def profile_layer(n):
    rgb, a = graded, alpha
    if VID:
        k = vid_pos(n); k0 = int(k); k1 = min(k0 + 1, len(VID) - 1); t = k - k0
        im = VID[k0][0] * (1 - t) + VID[k1][0].astype(np.float32) * t
        am = (VID[k0][1] * (1 - t) + VID[k1][1].astype(np.float32) * t) / 255
        rgb, a = grade_still(im, am, n, src_q=SRC_Q)
    M = placement(n)
    pm = cv2.warpAffine(np.dstack([rgb * a[..., None], a]), M, (W, H), flags=cv2.INTER_LANCZOS4, borderValue=0)
    A = np.clip(pm[..., 3], 0, 1) * inset
    C = pm[..., :3] / np.clip(pm[..., 3:4], 1e-3, None)
    C = BG + (C - BG) * profile_gain(n)
    return np.clip(C, 0, 255), A

# ---------- jersey layer: last frame of the jersey take, held with grain, duotone, faded ----------
jr = decode(R / args.jersey, 1280, 720)
CLEAN_TAKE = 'clean' in Path(args.jersey).name or args.v14   # already deghosted at the source (v14's timeline is made from the clean take): no patch, no deghost here
# The take copied LeBron's ghost profile from the source into its last frames. Our Dylan profile replaces it, so
# take the large smooth shapes out of the area left of and above the player and keep the small arena lights.
GHOST = np.zeros((H, W), np.uint8)
cv2.fillPoly(GHOST, [np.array([[0, 0], [880, 0], [880, 420], [700, 430], [640, 520], [620, 1080], [0, 1080]], np.int32)], 255)
GHOST = cv2.GaussianBlur(GHOST, (0, 0), 25).astype(np.float32)[..., None] / 255
def deghost(f):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))
    big = cv2.morphologyEx(f, cv2.MORPH_OPEN, k)
    dark = np.percentile(f[60:400, 1500:1800], 30, axis=(0, 1))
    return f - np.clip(big - dark, 0, None) * GHOST
def jframe(i):
    # v11: the take's tail (36..45) comes from clean/jersey, with the LeBron ghost replaced by the take's own stadium
    cp = HERE / f'clean/jersey/{i:03d}.png'
    if CLEAN_TAKE: return cv2.resize(jr[i], (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    if args.clean and cp.exists():
        return cv2.resize(cv2.imread(str(cp))[..., ::-1], (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    return deghost(cv2.resize(jr[i], (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32))
if args.v14:
    # v14: the jersey scene is look-matched (look-v4, delivered as fadein-v4), this layer reads the raw timeline. One
    # per-channel quantile curve, from the raw timeline frame of reel 803 to the scene's own graded 803, puts every
    # crossfade frame in the scene's look, so 803 to 804 does not jump in colour.
    _cut = args.start - 1   # the jersey scene's last frame in the reel (803; 783 for v15)
    _lk = decode(R / 'shots/jersey/out/fadein-v4.mp4', W, H)[_cut - 763].astype(np.float32)   # the scene as delivered (its encode shifts colour a little from look-v4)
    _rw = cv2.resize(jr[_cut - 763], (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    _q = np.linspace(0, 1, 257)
    JLUT = np.stack([np.interp(np.arange(256), np.quantile(_rw[..., c], _q), np.quantile(_lk[..., c], _q)) for c in range(3)], 1).astype(np.float32)
    _jframe_raw = jframe
    _lut = lambda f: np.stack([JLUT[f[..., c], c] for c in range(3)], -1)
    # and the scene's spatial gain (lookmatch's vignette and streak grid), as one smooth per-channel gain map
    _m = _lut(np.clip(_rw, 0, 255).astype(np.uint8))
    JGAIN = np.clip((cv2.GaussianBlur(_lk, (0, 0), 60) + 4) / (cv2.GaussianBlur(_m, (0, 0), 60) + 4), 0.7, 1.4)
    def jframe(i):
        return _lut(np.clip(_jframe_raw(i), 0, 255).astype(np.uint8)) * JGAIN
jlast = jframe(len(jr) - 1)
J_WHITE = float(np.percentile(lum(jlast), 99.5))
def jersey_layer(n):
    if args.v14: return jersey_duotone(jframe(n - 763), n)   # v14: the continuous timeline, moving to the end
    if n <= 813:   # before 27.13 s the take itself plays (used when the slot starts early, --start 806)
        return jframe(len(jr) - 1 - (813 - n))
    k = n - 813
    s = 1.0 + 0.00035 * k
    M = cv2.getRotationMatrix2D((W / 2, H * 0.45), 0, s)
    j = cv2.warpAffine(jlast, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    rng = np.random.default_rng(1000 + n)
    j = j + rng.normal(0, 5, (H, W, 1)).astype(np.float32)
    j = j * inset[..., None] + jlast * (1 - inset[..., None])   # the take's own margin stays put
    return jersey_duotone(j, n)
def jersey_duotone(j, n):
    y = jersey_yellow(n)
    if y > 0:
        L = np.clip((lum(j) - 20) / (J_WHITE - 20), 0, 1) ** 1.25    # the take's own white maps to full
        duo = BG * (1 - L[..., None]) + np.array([226, 222, 140], np.float32) * L[..., None]
        j = j * (1 - y) + duo * y
    return j

# ---------- logo ----------
def rgba_crop(p):
    a = np.asarray(Image.open(R / p).convert('RGBA')).astype(np.float32)
    x, y, w_, h_ = cv2.boundingRect((a[..., 3] > 8).astype(np.uint8))
    return a[y:y + h_, x:x + w_]
if args.v12:
    # v12: the plain logo, no hand or bag. The mark sits left of the wordmark the way the real logo does: the
    # wordmark (with its slashes) at 0.84 of the mark's height, centred on it, a gap of 0.09 mark heights.
    mk, wm = rgba_crop('refs/logo/mark.png'), rgba_crop('refs/logo/wordmark.png')
    wh = round(mk.shape[0] * 0.84); wm = cv2.resize(wm, (round(wm.shape[1] * wh / wm.shape[0]), wh), interpolation=cv2.INTER_AREA)
    gap = round(mk.shape[0] * 0.09)
    logo = np.zeros((mk.shape[0], mk.shape[1] + gap + wm.shape[1], 4), np.float32)
    logo[:, :mk.shape[1]] = mk
    y0 = (mk.shape[0] - wh) // 2; logo[y0:y0 + wh, mk.shape[1] + gap:] = wm
    WM_X = (mk.shape[1] + gap) / logo.shape[1]                     # where the wordmark starts, as a share of the width
    bh, bw = logo.shape[:2]
    LW = 720; LH = round(bh * LW / bw)
else:
    logo = rgba_crop('refs/logo/end-logo.png'); bh, bw = logo.shape[:2]
    LW = 820; LH = round(bh * LW / bw)
lg = cv2.resize(logo, (LW, LH), interpolation=cv2.INTER_AREA)
LX = int(SW_BOX[0] + SW_BOX[2] / 2 - LW / 2) + 4; LY = int(SW_BOX[1] + SW_BOX[3] / 2 - LH / 2)
LX = min(LX, X1 - 14 - LW)
la = lg[..., 3] / 255; lrgb = lg[..., :3]
# colour balance into the grade: a touch of the warm duotone, lifted contrast, 16-step posterize
def duo_grade(lrgb):
    # v10: pull the logo into the scene's duotone. Its brightness is remapped to the profile's tone curve, the
    # yellows move to the swoosh-and-jersey yellow, the blue keeps its hue (so 'semi' still reads apart from
    # 'analysis') but loses a third of its saturation and warms toward the plate, and the whites go cream.
    warm = lut[np.clip(lum(lrgb), 0, 255).astype(int)]
    Ll = lum(lrgb)[..., None]
    chroma = lrgb - Ll
    blue = np.clip((lrgb[..., 2:3] - lrgb[..., 0:1]) / 80, 0, 1)
    tone = np.clip(Ll * 0.55 + lum(warm)[..., None] * 0.45, 0, 255)
    col = tone + chroma * (0.85 - 0.25 * blue)
    col = col * (1 - 0.35 * (1 - blue)) + warm * (1 - blue) * 0.35 * (tone / np.clip(lum(warm)[..., None], 1, None))
    col = col + np.array([10, 4, -10], np.float32) * blue                       # warm the blue toward the plate
    return np.round(np.clip((col - 128) * 1.1 + 128, 0, 255) / 16) * 16
if args.v9_logo:
    warm = lut[np.clip(lum(lrgb), 0, 255).astype(int)]
    lrgb_g = np.clip(lrgb * 0.86 + warm * 0.14, 0, 255)
    lrgb_g = np.round(np.clip((lrgb_g - 128) * 1.08 + 132, 0, 255) / 16) * 16
else:
    lrgb_g = duo_grade(lrgb)
logo_full = np.zeros((H, W, 3), np.float32); logo_a = np.zeros((H, W), np.float32)
logo_full[LY:LY + LH, LX:LX + LW] = lrgb_g; logo_a[LY:LY + LH, LX:LX + LW] = la
glow_src = logo_full * logo_a[..., None]
glow = cv2.GaussianBlur(glow_src, (0, 0), 18) * 0.55 + cv2.GaussianBlur(glow_src, (0, 0), 5) * 0.25
glow = glow * np.array([1.0, 0.92, 0.6], np.float32)       # warm halation like the original's highlights
def logo_state(n):
    """(reveal 0..1 across the logo left to right, opacity, white heat). Matches the swoosh: the hook shows
    from 838, the tail reaches the tip by 846, white-hot to 857, settled by 863."""
    rev = np.clip((n - 838) / 8, 0, 1)
    op = np.clip((n - 837) / 6, 0, 1)
    heat = 0.0 if n < 840 else float(np.clip(1 - (n - 852) / 11, 0, 1)) * 0.55
    return float(rev), float(op), heat
# v11: brightness follows the swoosh's own curve (shots/profile/logo_curve.py). gain = swoosh body luma over its
# settle level (880..887): it climbs in pulses from 858 to a peak at 877 (1.29x), then settles and flickers with
# the picture. Before 858 the v10 white heat carries the wipe. From 888, where the original fades to black, the
# logo sits at its settle level with a mild flicker in step with the profile (the same held frames, look(n)).
CURVE = {}
if args.logo_curve:
    CURVE = {r['frame']: r['gain'] for r in json.loads((HERE / 'out/logo-curve-original.json').read_text())['frames']}
    F_HOLD = float(np.mean([F[k] for k in range(878, 888)]))
bloom_src = glow_src
bloom = cv2.GaussianBlur(bloom_src, (0, 0), 40) * 0.5 + cv2.GaussianBlur(bloom_src, (0, 0), 12) * 0.5
bloom = bloom * np.array([1.0, 0.95, 0.7], np.float32)
def logo_gain(n):
    if not CURVE or n < 858: return 1.0 if not CURVE else float(CURVE[858])
    if n < HOLD_FROM: return float(np.clip(CURVE[n], 0.8, 1.3))
    return float(np.clip((F[look(n)] / F_HOLD) ** 0.5, 0.9, 1.06))
# v12 (2026-10-17): no glow curve, no pulse, no wipe. The plain logo fades in with an ease-in-out
# (840..856, where the swoosh came in), holds steady, and dims to 65% of that by 901 (from 893). The line
# arcmira.mentions(entity: "dylan patel") fades in once the logo has settled (866..872), sits near the bottom,
# centred a little right of the middle, graded with the logo's duotone, and fades out (886..892), so the last
# frames are Dylan and the dimmed logo.
def v12_logo(n): return (pulse(SWF, n) ** ease((n - 860) / 6) if args.v15 else 1.0) * ease((n - V15_LOGO[0]) / (V15_LOGO[1] - V15_LOGO[0]) if args.v15 else (n - 840) / 16) * (1 - 0.35 * ease((n - 893) / (END + TAIL - 893)))
if args.v12:
    from PIL import ImageFont, ImageDraw
    TYPE_PX = 36
    FONT = ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Medium.ttf'), TYPE_PX)
    LINE = 'arcmira.mentions(entity: "dylan patel")'
    _im = Image.new('L', (W, H), 0)
    tw = FONT.getlength(LINE); TX = int(W / 2 + 110 - tw / 2); TY = 925
    ImageDraw.Draw(_im).text((TX, TY), LINE, font=FONT, fill=255)
    LINE_A = np.asarray(_im, np.float32) / 255
    LINE_C = duo_grade(np.full((1, 1, 3), 255, np.float32))[0, 0]   # white through the logo's grade: cream
def text_layer(n):
    if not args.v12 or args.v13: return None
    o = ease((n - 866) / 6) * (1 - ease((n - 886) / 6))
    return (LINE_A * o, LINE_C) if o > 0 else None
def logo_layer(n):
    if args.v12:
        k = v12_logo(n)
        return (logo_full, logo_a * k, glow * k) if k > 0 else None
    rev, op, heat = logo_state(n)
    if op <= 0: return None
    edge = LX + rev * (LW + 120) - 60
    wipe = np.clip((edge - xx) / 60, 0, 1).astype(np.float32)
    A = logo_a * wipe * op
    g = logo_gain(n)
    over = max(g - 1.0, 0.0)                                   # above the settle level the yellows run toward white
    C = logo_full * g
    C = C + (255 - np.clip(C, 0, 255)) * min(1.0, heat + 0.9 * over)
    G = glow * (1 + 1.5 * over) * min(g, 1.0) + (bloom * (over / 0.29) * 0.7 if CURVE else 0)   # soft bloom at the peak
    return C, A, G * wipe[..., None] * op

# v13: the jersey scene's mentions line (shots/jersey/mentions.py, full-frame RGBA at its final strength) is drawn
# last from 804, so it carries on from the jersey scene with no jump. It eases out (smoothstep) 5 frames ahead of
# the jersey's own opacity curve: it starts dropping 5 frames before the jersey does and is gone 5 frames before
# the jersey is.
MENTIONS = None
LEAD = 2   # v14: frames the line leads the jersey's fade by
if args.v13:
    _m = np.asarray(Image.open(R / 'shots/jersey/out/mentions-layer.png').convert('RGBA')).astype(np.float32)
    MENTIONS = (_m[..., :3], _m[..., 3] / 255)
    _jo = {n: jersey_opacity(n) for n in range(args.start, END + TAIL + 1)}
    J_DROP = min(n for n, v in _jo.items() if v < 0.999)           # first frame the jersey starts to go
    J_GONE = min(n for n, v in _jo.items() if n > J_DROP and v <= 0.01)
    M0, M1 = J_DROP - 5, J_GONE - 5
    if args.v14:   # v14: the jersey's own opacity curve, 2 frames early: same shape and tempo, gone 2 frames before it
        M0, M1 = J_DROP - LEAD, J_GONE - LEAD
    print('jersey opacity drops from', J_DROP, 'gone at', J_GONE, '; mentions line fades', M0, 'to', M1)
def mentions_strength(n):
    if args.v15:
        # (2026-10-17) a quick, soft drop over 796..826 to a faint 15%, which then rides the jersey's own fade
        # out and is gone 3 frames (0.1 s) before the jersey is
        if MENTIONS is None: return 0.0
        return 0.85 * (1.0 - ease((n - V15_LINE[0]) / 30)) + 0.15 * jersey_opacity(n + 3)
    if args.v14: return jersey_opacity(n + LEAD) if MENTIONS is not None else 0.0
    if MENTIONS is None or n >= M1: return 0.0
    return 1.0 - ease((n - M0) / (M1 - M0))

# ---------- composite ----------
out_dir = HERE / 'out'; out_dir.mkdir(exist_ok=True)
frames = list(range(args.start, END + 1)) + ([END] * TAIL if args.fade else list(range(END + 1, END + TAIL + 1)))
out = out_dir / f'{args.tag}.mp4'
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)],
                       stdin=subprocess.PIPE)
for i, n in enumerate(frames):
    base = plate(n)
    jo = jersey_opacity(n)
    if jo > 0: base = base * (1 - jo) + jersey_layer(n) * jo
    po = profile_opacity(n)
    if po > 0:
        C, A = profile_layer(n); A = A * po
        # over the jersey the profile only adds light (its darks sit at the plate's grey), like the original
        if jo > 0:   # screen-like: only the light above the plate grey comes through, the darks stay clear
            lift = np.clip(C - BG, 0, None) * A[..., None]
            solid = A * (1 - jo)                                 # becomes a normal layer as the jersey goes
            base = base * (1 - solid[..., None]) + C * solid[..., None] + lift * jo
        else:
            base = base * (1 - A[..., None]) + C * A[..., None]
    fl = flare_add(n)
    if fl is not None: base = base + fl
    f = fade(n)
    img = base * f
    L_ = logo_layer(n)
    if L_ is not None:
        C, A, G = L_
        img = img + G * (0.6 + 0.4 * f) * (1 - A[..., None])
        img = img * (1 - A[..., None]) + C * A[..., None]
    T_ = text_layer(n)
    if T_ is not None: img = img * (1 - T_[0][..., None]) + T_[1] * T_[0][..., None]
    ms = mentions_strength(n)
    if ms > 0: img = img * (1 - MENTIONS[1][..., None] * ms) + MENTIONS[0] * (MENTIONS[1][..., None] * ms)
    enc.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print(json.dumps({'out': str(out.relative_to(R)), 'frames': len(frames), 'start': args.start, 'logo_box': [LX, LY, LW, LH]}))
