"""Fade-in (slot 0.00 to 1.00 s), graded, before graphics.

The original's first second is the same wide shot as the intro, fading up
from black while the camera pans. We have no take frames before the intro's
first, so this holds the intro take's first frame and moves it with the
original's camera: per-frame pan is measured in src/clip.mp4 by phase
correlation (rows clear of the graphics), integrated back from frame 30, and
applied to the held frame. At 1.00 the offset reaches zero and the pan speed
(about 2.5 px a frame at 1920) is the take's own, so the cut into the intro
slot has no jump.

The held frame is the intro's look-matched first frame, so it already has the
grade the intro opens on. The fade is the original's own. Measured in the
original, it is a pure gain: frame n over frame 30 has the same ratio at the
25th to 97th percentiles (frame 15: 0.43 to 0.50, mean 0.50). So frame n is
the held frame times that per-channel mean ratio, which is 1 at 1.00.
(Running lookmatch.py on these frames crushed the dark end, and a quantile
map put the seam 4% low on our content.)

The take's own AI graphics are filled out first, since they would otherwise
slide with the picture; graphics.py lays the fixed broadcast graphics on
afterwards. Columns uncovered by the shift are mirrored from the edge; they
sit in the darkest frames.

Run from R: uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python -I shots/fadein/build.py INTRO_LOOK OUT
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()

import subprocess
import sys

import numpy as np
from PIL import Image

W, H, FPS, N = 1920, 1080, 30, 30
BUG = (1390, 875, 1856, 1004)
BAN = (1596, 40, 1828, 142)   # stops short of the take's shot clock at x 1835


def gray(path, n, w, h):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-frames:v", str(n), "-vf",
                                   f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def phase_shift(a, b):
    """x, y displacement of b relative to a, subpixel."""
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    A = np.fft.fft2((a - a.mean()) * win)
    B = np.fft.fft2((b - b.mean()) * win)
    R = B * np.conj(A)
    R /= np.abs(R) + 1e-9
    r = np.fft.ifft2(R).real
    y, x = np.unravel_index(r.argmax(), r.shape)

    def sub(v, c, n):
        lo, m, hi = v[(c - 1) % n], v[c], v[(c + 1) % n]
        return c + (lo - hi) / (2 * (lo - 2 * m + hi) + 1e-9)

    xs, ys = sub(r[y], x, w), sub(r[:, x], y, h)
    return (xs - w if xs > w / 2 else xs), (ys - h if ys > h / 2 else ys)


def diffuse_fill(img, mask, iters):
    out = img.copy()
    out[mask] = out[~mask].mean(0)
    for _ in range(iters):
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        out[mask] = ((p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4)[mask]
    return out


def main():
    take_path, out_path = sys.argv[1], sys.argv[2]
    # the original's fade: per-channel gain of frame n against frame 30
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", "src/clip.mp4", "-frames:v", str(N + 1),
                                   "-vf", "scale=960:540", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    o = np.frombuffer(raw, np.uint8).reshape(-1, 540, 960, 3)[:, 60:420].astype(np.float32)
    gain = o.mean((1, 2)) / o[N].mean((0, 1))
    print("gain R at 0, 9, 15, 29:", gain[[0, 9, 15, 29], 0].round(3))
    # camera pan of the original over frames 0..30, at 960 wide, then x2
    g = gray("src/clip.mp4", N + 1, 960, 540)[:, 60:420]
    d = np.zeros((N, 2))
    for k in range(N):
        d[k] = phase_shift(g[k], g[k + 1]) if min(g[k].mean(), g[k + 1].mean()) > 5 else np.nan  # black frames give noise
    first = np.where(~np.isnan(d[:, 0]))[0][0]
    d[:first] = d[first]
    d *= 2
    pos = np.array([-d[n:].sum(0) for n in range(N)])  # content offset vs frame 30
    print("pan px/frame at 0, 15, 29:", d[0].round(2), d[15].round(2), d[29].round(2),
          " offset at 0:", pos[0].round(1))

    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", take_path, "-frames:v", "1", "-vf",
                                   f"scale={W}:{H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    f0 = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
    for x0, y0, x1, y1 in (BUG, BAN):
        reg = f0[y0 - 6:y1 + 6, x0 - 6:x1 + 6]
        m = np.zeros(reg.shape[:2], bool)
        m[6:-6, 6:-6] = True
        f0[y0 - 6:y1 + 6, x0 - 6:x1 + 6] = diffuse_fill(reg, m, 600)
    pad = int(np.ceil(np.abs(pos).max())) + 4
    big = np.pad(f0, ((pad, pad), (pad, pad), (0, 0)), mode="reflect")
    im = Image.fromarray(np.clip(big, 0, 255).astype(np.uint8))

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "ffv1", "-pix_fmt", "bgr0", out_path],
        stdin=subprocess.PIPE)  # lossless: each yuv420p generation darkens by about 1.5 levels
    for n in range(N):
        dx, dy = pos[n]
        # output pixel (x, y) samples big at (x + pad - dx, y + pad - dy)
        fr = np.asarray(im.transform((W, H), Image.AFFINE, (1, 0, pad - dx, 0, 1, pad - dy),
                                     Image.BICUBIC), np.float32)
        fr *= gain[n]
        enc.stdin.write(np.clip(fr + 0.5, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("encode failed")
    print(out_path, N, "frames")


if __name__ == "__main__":
    main()
