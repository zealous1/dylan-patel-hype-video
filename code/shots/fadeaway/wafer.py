"""Burning wafer for the fadeaway (slot 8.57 to 10.00 s).

The take kept the original's fireball. Its white-hot head is keyed by hand
in ball-keys.json (automatic colour tracking kept locking onto the orange rim
and the yellow jerseys), splined per frame, and this composites
a tumbling silicon wafer on it: dark disc with a flat, an iridescent die grid
that shifts hue as it turns, a white-hot rim, an additive glow, and a fading
trail along the tracked path. The take's own flames stay around it, so it
reads as the wafer burning.

Run from R: uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python -I shots/fadeaway/wafer.py IN OUT [track.json]
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()

import json
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

FPS, W, H = 30, 1920, 1080
R_WAFER = 24.0  # px at 1080, a little larger than the ball
KEYS = "shots/fadeaway/ball-keys.json"
LOOK = "shots/fadeaway/post/look.json"


def read(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}",
                                   "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def keyed_path(n, keys):
    """Catmull-Rom through hand keys [frame, x, y]; held flat outside them."""
    kf = np.array([k[0] for k in keys], np.float32)
    kx = np.array([k[1] for k in keys], np.float32)
    ky = np.array([k[2] for k in keys], np.float32)
    out = []
    for t in range(n):
        if t <= kf[0]:
            out.append((kx[0], ky[0]))
            continue
        if t >= kf[-1]:
            out.append((kx[-1], ky[-1]))
            continue
        j = int(np.searchsorted(kf, t) - 1)
        u = (t - kf[j]) / (kf[j + 1] - kf[j])
        i0, i1, i2, i3 = max(0, j - 1), j, j + 1, min(len(kf) - 1, j + 2)
        def cr(p):
            p0, p1, p2, p3 = p[i0], p[i1], p[i2], p[i3]
            return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
        out.append((float(cr(kx)), float(cr(ky))))
    return np.array(out)


def wafer_sprite(r, phase, spin, ss=4):
    """RGBA wafer, tumbling. phase sets the squash, spin the in-plane angle."""
    size = int(r * 2 + 8) * ss
    c = size / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    x, y = (xx - c) / ss, (yy - c) / ss
    # rotate in plane
    ca, sa = math.cos(spin), math.sin(spin)
    u = x * ca + y * sa
    v = -x * sa + y * ca
    squash = 0.42 + 0.58 * abs(math.cos(phase))
    v = v / squash
    rr = np.hypot(u, v)
    disc = (rr <= r) & (v < r * 0.93)  # the flat
    # die grid on the face
    pitch = r / 4.2
    gu, gv = (u / pitch) % 1, (v / pitch) % 1
    street = (gu < 0.12) | (gv < 0.12)
    inner = rr < r * 0.9
    # iridescent hue from position and turn
    hue = (np.arctan2(v, u) / (2 * math.pi) + phase * 0.35 + (u + v) / (r * 6)) % 1
    k = np.stack([np.cos(2 * math.pi * (hue - o)) for o in (0, 1 / 3, 2 / 3)], -1) * 0.5 + 0.5
    # polished silicon: dark blue-violet with a thin-film rainbow sheen
    base = np.array([38, 40, 70], np.float32)
    face = base + 120 * k ** 2.2
    # specular band across the polished face
    spec = np.exp(-((u * 0.6 + v * 0.8) / r - 0.25 * math.sin(phase * 1.3)) ** 2 / 0.02)
    face = face + spec[..., None] * 90
    face *= (0.75 + 0.25 * np.cos(phase))  # darker when edge-on
    col = np.where(street[..., None], np.array([150, 155, 170], np.float32), face)
    col = np.where(inner[..., None], col, np.array([170, 175, 190], np.float32))
    # hot rim burning in from the edge
    rim = np.clip((rr - r * 0.72) / (r * 0.28), 0, 1) ** 1.5
    fire = np.array([255, 190, 90], np.float32)
    col = col * (1 - rim[..., None] * 0.85) + fire * rim[..., None] * 0.85
    a = disc.astype(np.float32)
    rgba = np.concatenate([col, a[..., None] * 255], -1).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").resize((size // ss, size // ss), Image.LANCZOS)
    return np.asarray(im, np.float32)


def soften(sp, sigma, vx, vy):
    """Match the footage: Gaussian softness plus motion blur along the path."""
    pad = int(abs(vx) * 0.6 + abs(vy) * 0.6 + sigma * 3 + 4)
    sp = np.pad(sp, ((pad, pad), (pad, pad), (0, 0)))
    pm = sp.copy()
    pm[..., :3] *= pm[..., 3:4] / 255  # premultiply
    acc = np.zeros_like(pm)
    taps = 9
    for t in np.linspace(-0.2, 0.2, taps):  # 0.4 of a frame of travel
        dx, dy = int(round(vx * t)), int(round(vy * t))
        acc += np.roll(np.roll(pm, dy, 0), dx, 1)
    acc /= taps
    chans = [np.asarray(Image.fromarray(acc[..., c].clip(0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(max(0.5, sigma * 0.7))), np.float32) for c in range(4)]
    out = np.stack(chans, -1)
    out[..., :3] = out[..., :3] / np.maximum(out[..., 3:4], 1) * 255
    return out


def glow_add(f, x, y, rad, amp, color):
    x0, x1 = max(0, int(x - rad * 3)), min(W, int(x + rad * 3))
    y0, y1 = max(0, int(y - rad * 3)), min(H, int(y + rad * 3))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    g = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * rad ** 2)) * amp
    f[y0:y1, x0:x1] += g[..., None] * np.array(color, np.float32)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    tpath = sys.argv[3] if len(sys.argv) > 3 else None
    fr = read(src)
    n = len(fr)
    flash = [float(f[::8, ::8].mean()) > 140 for f in fr]

    # per-frame softness the look-match applied to the take, so the wafer blurs with it
    look = json.load(open(LOOK))["frames"]

    def blur_sigma(i):
        r = look[i]
        return r.get("sigma", 0) * W / 640 if r["blur"] == "gauss" else (
            r.get("strength", 0) * 60 if r["blur"] == "radial" else 0)

    keys = json.load(open(KEYS))["keys"]
    path = keyed_path(n, keys)
    xs_s, ys_s = path[:, 0], path[:, 1]
    have = np.array([any(k[0] == i for k in keys) for i in range(n)])
    if tpath:
        json.dump([{"f": int(i), "x": round(float(xs_s[i]), 1), "y": round(float(ys_s[i]), 1),
                    "found": bool(have[i]), "flash": flash[i]} for i in range(n)],
                  open(tpath, "w"), indent=1)

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
        "-pix_fmt", "yuv420p", "-frames:v", str(n), dst], stdin=subprocess.PIPE)
    for i in range(n):
        f = fr[i].astype(np.float32).copy()
        x, y = xs_s[i], ys_s[i]
        level = 0.0 if flash[i] else 1.0
        # trail: fading glows back along the path
        for j in range(1, 7):
            if i - j < 0:
                break
            fa = (1 - j / 7) ** 1.5
            glow_add(f, xs_s[i - j], ys_s[i - j], R_WAFER * (0.9 + 0.12 * j), 70 * fa * level,
                     (1.0, 0.55, 0.18))
        glow_add(f, x, y, R_WAFER * 2.2, 90 * level, (1.0, 0.62, 0.25))
        sp = wafer_sprite(R_WAFER, phase=i * 0.38, spin=i * 0.21)
        sp = soften(sp, blur_sigma(i), (xs_s[min(n - 1, i + 1)] - xs_s[max(0, i - 1)]) / 2,
                    (ys_s[min(n - 1, i + 1)] - ys_s[max(0, i - 1)]) / 2)
        sh, sw = sp.shape[:2]
        x0, y0 = int(round(x - sw / 2)), int(round(y - sh / 2))
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(W, x0 + sw), min(H, y0 + sh)
        if xb > xa and yb > ya:
            s = sp[ya - y0:yb - y0, xa - x0:xb - x0]
            a = s[..., 3:4] / 255 * level
            under = fr[i][ya:yb, xa:xb].astype(np.float32) / 255
            comp = f[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a
            # the take's own flames lick back over the wafer (screen at 18%)
            fire = under * np.array([1.0, 0.75, 0.45], np.float32) * 0.18
            comp = 255 - (255 - comp) * (1 - fire * a)
            f[ya:yb, xa:xb] = comp
        # small hot core glow over the rim so it sits inside the fire
        glow_add(f, x, y, R_WAFER * 0.9, 45 * level, (1.0, 0.8, 0.5))
        enc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("encode failed")
    print(dst, n, "frames,", len(keys), "keys")


if __name__ == "__main__":
    main()
