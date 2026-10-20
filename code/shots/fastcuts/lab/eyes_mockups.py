# Energy-eye stills for Zeal to pick from before any video, all bright gold-yellow: anime demon looks first, then
# the other styles, on one B2 P2 hero frame at full glow just after the smile peak. Three-frame strips show the
# slight sideways flicker. Eye openings come from MediaPipe Face Mesh run on the rendered frames themselves, and the
# effects are drawn at close-up resolution so thin strokes stay crisp. Sizes are in screen pixels times `k`.
#   uv run --no-project --python 3.12 --with-requirements requirements-matte.txt python -I shots/fastcuts/lab/eyes_mockups.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, subprocess
import numpy as np, cv2
import mediapipe as mp
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
SRC = os.path.join(HERE, '..', 'out', 'fastcuts-v16-p2.mp4')
F0 = 192  # section 6.40 s; the smile peaks at 6.14 s
FONT = ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Bold.ttf'), 26)
SMALL = ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Bold.ttf'), 22)
# Face Mesh lid contours, each starting at a corner and running along the upper lid first (points 0 to 8).
LIDS = ([33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7],
        [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382])
IRISES, TOP, CHIN = (468, 473), 10, 152
TW, TH = 900, 600

# BGR. Gold-yellow leans yellow, not amber.
WHITE_Y = np.float32([200, 255, 255])
HOT = np.float32([235, 255, 255])
GOLD = np.float32([0, 205, 255])
LEMON = np.float32([0, 236, 255])
DEEP = np.float32([0, 120, 235])

def frames(f0, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', SRC, '-vf', f"select='between(n\\,{f0}\\,{f0 + n - 1})'", '-vsync', '0',
                          '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    return [f.copy() for f in np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)]

mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.3)
haar = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
def landmarks(img):
    x, y, w, h = max(haar.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(80, 80)), key=lambda b: b[2])
    cs = int(w * 3); x0 = int(min(max(x + w / 2 - cs / 2, 0), W - cs)); y0 = int(min(max(y + h / 2 - cs / 2, 0), H - cs))
    crop = cv2.resize(img[y0:y0 + cs, x0:x0 + cs], (768, 768), interpolation=cv2.INTER_CUBIC)
    lm = mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).multi_face_landmarks[0].landmark
    return np.array([[x0 + l.x * cs, y0 + l.y * cs] for l in lm], np.float32)

unit = lambda v: v / (np.linalg.norm(v) + 1e-6)
fx = lambda pts: np.round(np.asarray(pts) * 4).astype(np.int32)  # subpixel coordinates for cv2's shift=2

class Eye:
    def __init__(s, P, idx, shape, k):
        s.poly = P[list(idx)]
        s.cen = s.poly.mean(0)
        s.nrm = np.array([unit(p - s.cen) for p in s.poly])
        ic = min(IRISES, key=lambda i: np.linalg.norm(P[i] - s.cen))
        s.c = P[ic]
        s.r = float(np.mean([np.linalg.norm(P[ic + j] - s.c) for j in (1, 2, 3, 4)]))
        s.w = float(np.ptp(s.poly[:, 0]))
        m = np.zeros(shape, np.float32)
        # One screen pixel wider than the lids, so the eye reads as lit from inside rather than painted on.
        cv2.fillPoly(m, [fx(s.poly + s.nrm * k)], 1.0, cv2.LINE_AA, shift=2)
        s.mask = cv2.GaussianBlur(m, (0, 0), 0.6 * k)
        s.hard = (s.mask > 0.5).astype(np.float32)
        ir = np.zeros(shape, np.float32)
        cv2.circle(ir, tuple(fx(s.c)), int(round(s.r * 1.05 * 4)), 1.0, -1, cv2.LINE_AA, shift=2)
        s.iris = ir * s.mask

class Canvas:
    """One close-up. Fills stay inside the true eye shape; glows and strokes go to layers that jitter sideways together."""
    def __init__(s, img, P, k, jit=(0.0, 0.0, 0.0, 1.0), seed=0):
        s.x = img.astype(np.float32); s.shape = img.shape[:2]
        s.P, s.k = P, k
        s.fh = float(np.linalg.norm(P[CHIN] - P[TOP]))
        s.dx, s.smear, s.slide, s.gain = jit
        s.rng = np.random.default_rng(seed)
        s.eu = unit(P[263] - P[33]); s.up = np.array([s.eu[1], -s.eu[0]])
        mid = (P[IRISES[0]] + P[IRISES[1]]) / 2
        s.eyes = [Eye(P, idx, s.shape, k) for idx in LIDS]
        for e in s.eyes:
            side = np.sign((e.cen - mid) @ s.eu)
            e.out = side * s.eu
            e.outer = e.poly[np.argmax((e.poly - mid) @ s.eu * side)]
        s.add = np.zeros(s.shape + (3,), np.float32)
        s.ova = np.zeros(s.shape, np.float32); s.ovc = np.zeros(s.shape + (3,), np.float32)

    def eyemask(s): return np.maximum(*[e.mask for e in s.eyes])
    def irismask(s): return np.maximum(*[e.iris for e in s.eyes])

    def fill(s, edge, core, where='eye', power=0.35, boost=1.0):
        yy, xx = np.mgrid[0:s.shape[0], 0:s.shape[1]].astype(np.float32)
        for e in s.eyes:
            R = e.mask if where == 'eye' else e.iris
            if where == 'eye':
                d = cv2.distanceTransform((R > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
                g = d / max(float(d.max()), 1e-3)
            else:
                g = np.clip(1 - np.hypot(xx - e.c[0], yy - e.c[1]) / e.r, 0, 1)
            if s.slide:
                g = np.roll(g, int(round(s.slide * e.w)), 1)
            g = cv2.GaussianBlur(g * (R > 0.5), (0, 0), 0.5 * s.k)[..., None] ** power
            col = np.minimum((edge * (1 - g) + core * g) * s.gain * boost, 255)
            s.x = s.x * (1 - R[..., None]) + col * R[..., None]

    def glow(s, mask, sigma, color, amt):
        s.add += cv2.GaussianBlur(mask, (0, 0), sigma * s.k)[..., None] * color * amt

    def edge_glow(s, color=GOLD, width=1.0, amt=1.0, mask=None):
        m = s.eyemask() if mask is None else mask
        s.glow(m, 1.4 * width, color, 0.9 * amt); s.glow(m, 3.4 * width, color, 0.35 * amt)

    def solid(s, m, color):
        s.ovc = s.ovc * (1 - m[..., None]) + color * m[..., None]; s.ova = s.ova + m * (1 - s.ova)

    def lit(s, m, core=HOT, color=GOLD, amt=1.0):
        s.glow(m, 1.2, color, 1.1 * amt); s.glow(m, 3.2, color, 0.4 * amt); s.solid(m, core)

    def stroke(s, lines, thick, closed=False):
        m = np.zeros(s.shape, np.float32)
        for pts in lines:
            cv2.polylines(m, [fx(pts)], closed, 1.0, max(1, int(round(thick * s.k))), cv2.LINE_AA, shift=2)
        return m

    def polys(s, ps):
        m = np.zeros(s.shape, np.float32)
        for pts in ps:
            cv2.fillPoly(m, [fx(pts)], 1.0, cv2.LINE_AA, shift=2)
        return m

    def darken_sclera(s):
        a = (s.eyemask() * (1 - s.irismask()))[..., None]
        s.x = s.x * (1 - a) + (s.x * 0.12 + np.float32([4, 14, 40])) * a

    def slit(s, color=DEEP):
        m = np.zeros(s.shape, np.float32)
        ang = float(np.degrees(np.arctan2(s.up[1], s.up[0]))) + 90
        for e in s.eyes:
            cv2.ellipse(m, ((float(e.c[0]), float(e.c[1])), (e.r * 0.42, e.r * 2.2), ang), 1.0, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 0.35 * s.k) * np.maximum(*[e.hard for e in s.eyes])
        s.x = s.x * (1 - m[..., None]) + color * s.gain * m[..., None]

    def pupil(s):
        m = np.zeros(s.shape, np.float32)
        for e in s.eyes:
            cv2.circle(m, tuple(fx(e.c)), int(round(e.r * 0.26 * 4)), 1.0, -1, cv2.LINE_AA, shift=2)
        s.x = s.x * (1 - m[..., None]) + 255 * m[..., None]
        s.glow(m, 1.0, np.float32([255, 255, 255]), 1.2)

    def ring(s):
        m = np.zeros(s.shape, np.float32)
        for e in s.eyes:
            cv2.circle(m, tuple(fx(e.c)), int(round(e.r * 0.9 * 4)), 1.0, max(1, int(round(e.r * 0.3))), cv2.LINE_AA, shift=2)
        s.lit(m * np.maximum(*[e.hard for e in s.eyes]), WHITE_Y)

    def outline(s, wing=True):
        lines, wings = [], []
        for e in s.eyes:
            lines.append(e.poly + e.nrm * 1.6 * s.k)
            if wing:  # an eyeliner flick off the outer corner
                tip = e.outer + (e.out * 0.09 + s.up * 0.035) * s.fh
                wings.append([e.outer + s.up * 0.9 * s.k, tip, e.outer - s.up * 1.4 * s.k + e.out * 0.6 * s.k])
        s.lit(np.maximum(s.stroke(lines, 0.85, closed=True), s.polys(wings)), WHITE_Y)

    def crackle(s, n=5, reach=0.07):
        lines = []
        perp = lambda v: unit(np.array([-v[1], v[0]]))
        for e in s.eyes:
            P2, N2 = np.vstack([e.poly, e.poly]), np.vstack([e.nrm, e.nrm])
            for _ in range(n):
                i0 = int(s.rng.integers(0, 16)); span = int(s.rng.integers(3, 7))
                seg = P2[i0:i0 + span + 1] + N2[i0:i0 + span + 1] * s.rng.uniform(1.5, 3.5) * s.k
                pts = [seg[0]]
                for a, b in zip(seg[:-1], seg[1:]):
                    for t in (0.33, 0.66, 1.0):
                        p = a + (b - a) * t
                        pts.append(p + unit(p - e.cen) * s.rng.uniform(-1.4, 2.2) * s.k)
                lines.append(pts)
                if s.rng.random() < 0.6:  # a fork that kicks out away from the eye
                    j = int(s.rng.integers(1, len(pts) - 1)); p = pts[j]; nr = unit(p - e.cen)
                    L = s.rng.uniform(0.35, 1.0) * reach * s.fh
                    lines.append([p + nr * L * t + perp(nr) * s.rng.uniform(-2.2, 2.2) * s.k * (t > 0) for t in (0, 0.25, 0.5, 0.75, 1.0)])
        m = s.stroke(lines, 0.55)
        s.lit(np.clip(m * 1.4, 0, 1), HOT, GOLD, 1.2)

    def star(s, at, tips, waist):
        """A sharp sparkle: thin spikes from `at`, given as (angle in degrees, length in face heights)."""
        ps = []
        for ang, L in tips:
            d = np.array([np.cos(np.radians(ang)), -np.sin(np.radians(ang))]); n = np.array([-d[1], d[0]])
            ps.append([at + n * waist * s.k, at + d * L * s.fh, at - n * waist * s.k, at - d * waist * 0.8 * s.k])
        s.lit(s.polys(ps))

    def glint_at(s, e):
        return e.c + e.out * e.r * 0.3 + s.up * e.r * 0.35

    def angular(s, e):
        o = 0 if e.out[0] > 0 else 180
        f = lambda a: (o + a) if o == 0 else (o - a)
        s.star(s.glint_at(e), [(f(20), 0.1), (f(100), 0.05), (f(200), 0.04), (f(280), 0.03)], 1.6)

    def flare(s, L=0.62):
        m = np.zeros(s.shape, np.float32)
        for e in s.eyes:
            xs = np.arange(int(e.c[0] - L * s.fh), int(e.c[0] + L * s.fh)); xs = xs[(xs >= 0) & (xs < s.shape[1])]
            y = int(round(e.c[1]))
            m[y, xs] = np.maximum(m[y, xs], np.exp(-np.abs(xs - e.c[0]) / (0.2 * s.fh)))
        core = cv2.GaussianBlur(m, (0, 0), 0.5 * s.k) * 2.2
        s.glow(m, 1.6, GOLD, 4.0)
        s.add += np.clip(core, 0, 1)[..., None] * WHITE_Y

    def shaft(s, up=0.13, down=0.05):
        yy, xx = np.mgrid[0:s.shape[0], 0:s.shape[1]].astype(np.float32)
        m = np.zeros(s.shape, np.float32)
        for e in s.eyes:
            u = (xx - e.c[0]) * s.eu[0] + (yy - e.c[1]) * s.eu[1]
            v = (xx - e.c[0]) * s.up[0] + (yy - e.c[1]) * s.up[1]
            t = np.clip(np.abs(v) / (np.where(v > 0, up, down) * s.fh), 0, 1)
            m = np.maximum(m, np.exp(-(u / (e.w * 0.16 * (1 - 0.7 * t))) ** 2) * (1 - t) ** 1.4)
        s.glow(m, 0.6, GOLD, 1.1); s.add += np.clip((m - 0.55) * 2.5, 0, 1)[..., None] * WHITE_Y * 0.9

    def wisps(s):
        field = np.full(s.shape, -9.0, np.float32)
        yy, xx = np.mgrid[0:s.shape[0], 0:s.shape[1]].astype(np.float32)
        for e in s.eyes:
            for f in (0.3, 0.5, 0.7):
                base = e.poly[int(round(f * 8))]
                h = s.fh * s.rng.uniform(0.08, 0.13); w = s.fh * s.rng.uniform(0.016, 0.024); bend = s.rng.uniform(-0.7, 0.7)
                u = (xx - base[0]) * s.eu[0] + (yy - base[1]) * s.eu[1]
                v = (xx - base[0]) * s.up[0] + (yy - base[1]) * s.up[1]
                t = np.clip(v / h, 0, 1)
                g = np.where((v >= -w) & (v <= h), (1 - t) - np.abs(u - bend * w * 3 * t ** 2) / (w * (1 - 0.6 * t) + 1e-3), -9)
                field = np.maximum(field, g)
        rim = cv2.GaussianBlur(np.clip(field * 8, 0, 1), (0, 0), 0.3 * s.k)
        core = cv2.GaussianBlur(np.clip((field - 0.4) * 8, 0, 1), (0, 0), 0.3 * s.k)
        s.glow(rim, 2.0, GOLD, 0.6); s.solid(rim, GOLD); s.solid(core, WHITE_Y)

    def sparks(s, n=11):
        lines, m = [], np.zeros(s.shape, np.float32)
        for e in s.eyes:
            for _ in range(n):
                start = e.poly[int(s.rng.integers(0, 9))]
                d = unit(s.up * s.rng.uniform(0.6, 1.0) + e.out * s.rng.uniform(-0.2, 0.9))
                far = s.rng.uniform(0.02, 0.13)
                p = start + d * far * s.fh
                cv2.circle(m, tuple(fx(p)), max(1, int(round((1.1 - far * 5) * s.rng.uniform(0.6, 1.0) * s.k * 4))), 1.0, -1, cv2.LINE_AA, shift=2)
                lines.append([p, p - d * s.rng.uniform(1.5, 4.0) * s.k])
        s.lit(np.maximum(m, s.stroke(lines, 0.45)), WHITE_Y, GOLD, 1.2)

    def afterimage(s):
        lit = s.x * s.eyemask()[..., None]
        for i, a in ((1, 0.55), (2, 0.32), (3, 0.16)):
            for sgn in (-1, 1):
                img = cv2.warpAffine(lit, np.float32([[1, 0, sgn * i * 0.03 * s.fh], [0, 1, 0]]), (s.shape[1], s.shape[0]))
                s.add += cv2.blur(img, (max(1, int(0.02 * s.fh)), 1)) * a * np.float32([0.2, 0.8, 1.0])

    def finish(s, chroma=False):
        M = np.float32([[1, 0, s.dx * s.k], [0, 1, 0]])
        add, ova, ovc = (cv2.warpAffine(a, M, (s.shape[1], s.shape[0])) for a in (s.add, s.ova, s.ovc))
        if s.smear:
            kx = max(1, int(round(s.smear * s.k)))
            add, ova, ovc = cv2.blur(add, (kx, 1)), cv2.blur(ova, (kx, 1)), cv2.blur(ovc, (kx, 1))
        x = s.x + add * s.gain
        x = x * (1 - ova[..., None]) + ovc  # strokes stay at full white so a dim frame never greys them
        if chroma:  # the energy splits into its channels and one band slips sideways
            reg = cv2.GaussianBlur(cv2.dilate(s.eyemask(), np.ones((int(6 * s.k) | 1,) * 2, np.uint8)), (0, 0), 2 * s.k)
            o = int(round(3.5 * s.k))
            r, b = np.roll(x[..., 2], o, 1), np.roll(x[..., 0], -o, 1)
            x[..., 2] = x[..., 2] * (1 - reg) + np.maximum(x[..., 2], r) * reg
            x[..., 0] = x[..., 0] * (1 - reg) + b * reg
            e = s.eyes[0]; band = slice(int(e.c[1] - e.r * 0.2), int(e.c[1] + e.r * 0.5))
            x[band] = x[band] * (1 - reg[band, :, None]) + np.roll(x[band], int(5 * s.k), 1) * reg[band, :, None]
        return np.clip(x, 0, 255).astype(np.uint8)

def solid_fill(c, edge=GOLD, core=WHITE_Y, width=1.0, boost=1.0):
    c.fill(edge, core, boost=boost); c.edge_glow(edge, width)

def demon_iris(c):
    # The sclera goes dark, but the iris is overdriven and blooms over it, so the eye still reads bright.
    c.darken_sclera(); c.fill(GOLD, HOT, 'iris', 0.5, boost=1.15)
    c.glow(c.irismask(), 2.0, GOLD, 1.3); c.glow(c.irismask(), 5.0, GOLD, 0.6)

def pinpoint(c):
    c.darken_sclera(); c.fill(np.float32([0, 150, 255]), GOLD, 'iris', 0.8, 1.1)
    c.glow(c.irismask(), 2.2, GOLD, 1.0); c.pupil()

def gleam(c, L, angles):
    for e in c.eyes:
        c.star(c.glint_at(e), [(a, L) for a in angles], 0.7)

LOOKS = {
    'A1': ('A1. Gold slit pupil in a blazing iris', lambda c: (solid_fill(c), c.slit())),
    'A2': ('A2. Dark sclera, overdriven blooming gold iris', demon_iris),
    'A3': ('A3. Dark sclera, blazing iris, slit pupil', lambda c: (demon_iris(c), c.slit())),
    'A4': ('A4. Energy outline tracing the lids, winged', lambda c: (solid_fill(c), c.outline())),
    'A5': ('A5. Crackle hugging the eye', lambda c: (solid_fill(c), c.crackle())),
    'A6': ('A6. Sharp angular glints', lambda c: (solid_fill(c), [c.angular(e) for e in c.eyes])),
    'A7': ('A7. White pinpoint pupil in a blazing gold iris', pinpoint),
    'A8': ('A8. Slit pupil, outline and crackle', lambda c: (solid_fill(c), c.slit(), c.outline(), c.crackle(4))),
    'A9': ('A9. Dark sclera, slit, outline and crackle', lambda c: (demon_iris(c), c.slit(), c.outline(), c.crackle(4))),
    'B1': ('B1. Solid fill, tight edge glow', solid_fill),
    'B2': ('B2. Brighter, more saturated yellow', lambda c: solid_fill(c, LEMON, np.float32([40, 255, 255]), boost=1.1)),
    'B3': ('B3. Same yellow, slightly wider edge glow', lambda c: solid_fill(c, width=2.6)),
    'B4': ('B4. Overdriven white-hot fill, gold edge', lambda c: (c.fill(np.float32([150, 245, 255]), np.float32([255, 255, 255]), boost=1.2),
                                                                  c.edge_glow(GOLD, 1.5, 1.4))),
    'B5': ('B5. Iris only, sclera natural', lambda c: (c.fill(GOLD, WHITE_Y, 'iris', 0.6, 1.1), c.edge_glow(GOLD, 1.0, 0.9, c.irismask()))),
    'B6': ('B6. Bright ring round the iris', lambda c: (c.fill(np.float32([0, 140, 230]), GOLD, 'iris', 0.9, 0.8), c.ring())),
    'B7': ('B7. Anime gleam, a four-point star', lambda c: (solid_fill(c), gleam(c, 0.06, (0, 90, 180, 270)))),
    'B8': ('B8. Thin horizontal lens flare', lambda c: (solid_fill(c), c.flare())),
    'B9': ('B9. Short vertical light shaft', lambda c: (solid_fill(c), c.shaft())),
    'B10': ('B10. Short cel-shaded wisps', lambda c: (solid_fill(c), c.wisps())),
    'B11': ('B11. Afterimage, a gold trail left and right', lambda c: (solid_fill(c), c.afterimage())),
    'B12': ('B12. Chromatic glitch, gold core, RGB split', solid_fill),
    'B13': ('B13. Tiny sparks drifting off', lambda c: (solid_fill(c), c.sparks())),
    'B14': ('B14. Beat surge frame, fill flashed white', lambda c: (c.fill(np.float32([120, 250, 255]), np.float32([255, 255, 255]), boost=1.5),
                                                                    c.edge_glow(GOLD, 1.8, 1.6))),
    'B15': ('B15. Anime hero, fill, gleam and flare', lambda c: (solid_fill(c), c.flare(0.45), gleam(c, 0.04, (45, 135, 225, 315)))),
}

def render(name, img, P, k, jit=(0.0, 0.0, 0.0, 1.0), seed=3):
    c = Canvas(img, P, k, jit, seed)
    LOOKS[name][1](c)
    return c.finish(chroma=name == 'B12')

base = frames(F0, 3)
pts = [landmarks(f) for f in base]
p0 = pts[0]
mid = (p0[IRISES[0]] + p0[IRISES[1]]) / 2
fh = float(np.linalg.norm(p0[CHIN] - p0[TOP]))
cw = int(fh * 1.15); ch = int(cw * TH / TW)
BOX = (int(min(max(mid[0] - cw / 2, 0), W - cw)), int(min(max(mid[1] - ch * 0.42, 0), H - ch)), cw, ch)
K = TW / cw

def label(t, text, xy=(16, 12), font=FONT):
    d = ImageDraw.Draw(t); l, tp, r, b = d.textbbox(xy, text, font=font)
    d.rectangle((l - 8, tp - 6, r + 8, b + 6), fill=(0, 0, 0)); d.text(xy, text, font=font, fill=(255, 255, 255))
    return t

def tile(name, k=0, jit=(0.0, 0.0, 0.0, 1.0), seed=3, text=None):
    x0, y0, w, h = BOX
    img = cv2.resize(base[k][y0:y0 + h, x0:x0 + w], (TW, TH), interpolation=cv2.INTER_LANCZOS4)
    out = render(name, img, (pts[k] - [x0, y0]) * K, K, jit, seed)
    return label(Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)), text or LOOKS[name][0])

def strip(name, rng):
    """Three frames in a row: the energy slides 1 to 3 px sideways and mostly flickers in brightness."""
    row = Image.new('RGB', (TW * 3, TH))
    for k, gain in enumerate((1.0, 0.86, 1.14)):
        dx = float(rng.choice([-1, 1]) * rng.uniform(1, 3))
        jit = (dx, float(rng.uniform(0.5, 2.0)), float(rng.uniform(-0.1, 0.1)), gain)
        t = tile(name, k, jit, seed=11 + k, text=f'{name} in motion, frame 1 of 3' if k == 0 else f'frame {k + 1} of 3')
        label(t, f'{dx:+.1f} px sideways, brightness {round(gain * 100)}%', (16, TH - 40), SMALL)
        row.paste(t, (k * TW, 0))
    return row

def grid(names):
    g = Image.new('RGB', (TW * 3, TH * ((len(names) + 2) // 3)))
    for i, n in enumerate(names):
        g.paste(tile(n), ((i % 3) * TW, (i // 3) * TH))
    return g

def stack(parts, path):
    sheet = Image.new('RGB', (TW * 3, sum(p.size[1] for p in parts)))
    y = 0
    for p in parts:
        sheet.paste(p, (0, y)); y += p.size[1]
    sheet.save(path, quality=88)
    print(path, sheet.size)

rng = np.random.default_rng(7)
full = Image.fromarray(cv2.cvtColor(render('A8', base[0], p0, 1.0), cv2.COLOR_BGR2RGB)).resize((TW * 3, TW * 3 * 9 // 16), Image.LANCZOS)
SHEETS = os.path.join(HERE, 'sheets')
stack([grid([f'A{i}' for i in range(1, 10)]), strip('A8', rng), strip('A2', rng), strip('B1', rng), label(full, 'A8 at full frame, for scale')],
      os.path.join(SHEETS, 'eyes-mockups.jpg'))
stack([grid([f'B{i}' for i in range(1, 16)])], os.path.join(SHEETS, 'eyes-mockups-2.jpg'))
print('face height', round(fh), 'px on screen, close-ups at', round(K, 2), 'x')
