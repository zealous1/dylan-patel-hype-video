"""Match a generated take to the look of the original edit, frame by frame.

For each output frame t (slot time), the original frame at start + t is the
reference. The take frame is graded and blurred until it measures like the
reference:

  1. Curves. Per-channel quantile mapping (levels, curves, tint, saturation
     and flashes all follow from it). --curves sets the blend (default 1).
  2. Spatial gain. A coarse per-channel gain grid (vignette, light streaks,
     glow falloff), smoothed in time, clipped, and blended by --spatial.
  3. Blur. High-frequency energy is measured on a 4x4 tile grid. When the
     reference is softer than the take, the blur that best matches the tile
     profile (detail plus x and y gradient energy) is picked from Gaussian
     blurs, radial zoom blurs at a 3x3 grid of centres, and linear motion
     blurs at four angles. A radial zoom keeps its centre sharp; a whip pan
     kills gradients along one axis only. When the reference is sharper, a mild unsharp mask is applied.

The take is retimed to exactly the slot (frames = round((end-start)*fps)).
Optional --trim a:b uses only that part of the take before retiming.

Run (from R):
  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I \
    shots/lookmatch.py --start 6.27 --end 8.57 --take shots/x/out/a.mp4 \
    --out shots/x/out/a-look.mp4 [--report shots/x/out/a-look.json]
"""

import argparse
import json
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

FPS = 30


def probe_duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", path]).decode().strip()
    return float(out)


def probe_size(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "csv=p=0", path]).decode().strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def read_frames(args_in, vf, w, h, n, passthrough=False):
    cmd = ["ffmpeg", "-v", "error"] + args_in + [
        "-vf", vf] + (["-fps_mode", "passthrough"] if passthrough else []) + ["-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.check_output(cmd)
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    if len(frames) < n:  # pad by holding the last frame
        pad = np.repeat(frames[-1:], n - len(frames), axis=0)
        frames = np.concatenate([frames, pad])
    return frames[:n]


def luma(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def tame_lut(lut):
    """Smooth a LUT and bound its slope so noise is never posterized into bands."""
    k = np.exp(-np.arange(-12, 13) ** 2 / (2 * 4.0 ** 2))
    k /= k.sum()
    sm = np.convolve(np.pad(lut, 12, mode="edge"), k, "valid")
    d = np.clip(np.diff(sm), 0.15, 4.0)
    out = np.concatenate([[0], np.cumsum(d)])
    out += sm.mean() - out.mean()
    return np.clip(out, 0, 255)


def quantile_lut(t, r, strength):
    qs = np.linspace(0, 100, 257)
    tq = np.percentile(t, qs) + np.arange(257) * 1e-4
    rq = np.percentile(r, qs)
    x = np.arange(256, dtype=np.float32)
    lut = np.interp(x, tq, rq)
    return tame_lut(x + (lut - x) * strength)


def chroma(a):
    a = a.astype(np.float32)
    y = luma(a)
    return y, a[..., 2] - y, a[..., 0] - y


def grade_params(take, ref, strength, mode):
    """rgb: one quantile LUT per channel. luma: a LUT on luma (contrast,
    posterize, levels) plus mean/std matching of the two chroma axes (tint,
    saturation), which keeps hues when the content differs from the original."""
    t, r = take[::2, ::2], ref[::2, ::2]
    if mode == "rgb":
        return {"luts": np.stack([quantile_lut(t[..., c], r[..., c], strength) for c in range(3)])}
    ty, tb, tr = chroma(t)
    ry, rb, rr = chroma(r)
    p = {"ylut": quantile_lut(np.clip(ty, 0, 255), np.clip(ry, 0, 255), strength)}
    for name, tc, rc in (("cb", tb, rb), ("cr", tr, rr)):
        gain = np.clip((rc.std() + 1) / (tc.std() + 1), 0.5, 2.0)
        p[name] = np.array([tc.mean(), rc.mean(), 1 + (gain - 1) * strength])
    return p


def apply_grade(img, p):
    img = np.clip(img + 0.5, 0, 255).astype(np.uint8) if img.dtype != np.uint8 else img
    if "luts" in p:
        out = np.empty(img.shape, np.float32)
        for c in range(3):
            out[..., c] = p["luts"][c][img[..., c]]
        return out
    y, cb, cr = chroma(img)
    y2 = p["ylut"][np.clip(y + 0.5, 0, 255).astype(np.uint8)]
    sat = (y2 + 4) / (y + 4)  # chroma follows the luma change, like a curve
    cb = (cb * sat - p["cb"][0]) * p["cb"][2] + p["cb"][1]
    cr = (cr * sat - p["cr"][0]) * p["cr"][2] + p["cr"][1]
    r = y2 + cr
    b = y2 + cb
    g = (y2 - 0.299 * r - 0.114 * b) / 0.587
    return np.stack([r, g, b], -1)


def smooth_params(params, ref_y, cut=12.0):
    """Average each frame's grade with its neighbours, never across a flash or cut."""
    out = []
    n = len(params)
    for i in range(n):
        acc, wsum = None, 0.0
        for j, w in ((i - 1, 1.0), (i, 2.0), (i + 1, 1.0)):
            if 0 <= j < n and abs(ref_y[j] - ref_y[i]) < cut:
                acc = {k: v * w for k, v in params[j].items()} if acc is None else {
                    k: acc[k] + params[j][k] * w for k in acc}
                wsum += w
        out.append({k: v / wsum for k, v in acc.items()})
    return out


def grid_means(a, gw, gh):
    h, w = a.shape[:2]
    a = a[: h - h % gh, : w - w % gw]
    return a.reshape(gh, a.shape[0] // gh, gw, a.shape[1] // gw, 3).mean((1, 3))


def upsample_gain(g, w, h):
    chans = []
    for c in range(3):
        im = Image.fromarray(g[..., c].astype(np.float32), mode="F")
        chans.append(np.asarray(im.resize((w, h), Image.BICUBIC)))
    return np.stack(chans, -1)


def to_img(a):
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))


def gauss(a, sigma):
    if sigma <= 0:
        return a
    return np.asarray(to_img(a).filter(ImageFilter.GaussianBlur(sigma)), np.float32)


def radial(a, strength, cx, cy, samples=10):
    """Zoom blur about (cx, cy) in 0..1 coords, scaling up to 1 + strength."""
    img = to_img(a)
    w, h = img.size
    px, py = cx * w, cy * h
    acc = np.zeros(a.shape, np.float32)
    for i in range(samples):
        s = 1 + strength * i / (samples - 1)
        # output (x,y) samples input at px + (x-px)/s
        inv = 1 / s
        m = (inv, 0, px - px * inv, 0, inv, py - py * inv)
        acc += np.asarray(img.transform((w, h), Image.AFFINE, m, Image.BILINEAR), np.float32)
    return acc / samples


def tile_hf(a, n=4):
    """Per tile: isotropic detail, plus x and y gradient energy (direction of smear)."""
    y = np.clip(luma(a) + 0.5, 0, 255).astype(np.uint8)
    lo = np.asarray(Image.fromarray(y).filter(ImageFilter.GaussianBlur(1.2)), np.float32)
    y = y.astype(np.float32)
    h, w = y.shape
    feats = []
    for d in (np.abs(y - lo), np.abs(np.diff(y, axis=1, append=y[:, -1:])),
              np.abs(np.diff(y, axis=0, append=y[-1:]))):
        d = d[: h - h % n, : w - w % n]
        feats.append(d.reshape(n, d.shape[0] // n, n, d.shape[1] // n).mean((1, 3)).ravel())
    return np.concatenate(feats) + 0.05


def motion(a, length, angle):
    """Linear motion blur: average of copies shifted along a line."""
    if length < 1:
        return a
    taps = max(3, int(length) | 1)
    acc = np.zeros(a.shape, np.float32)
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for t in np.linspace(-length / 2, length / 2, taps):
        acc += np.roll(np.roll(a, int(round(t * sa)), 0), int(round(t * ca)), 1)
    return acc / taps


def hf_err(a, ref_t):
    return float(np.mean(np.abs(np.log(tile_hf(a) / ref_t))))


def pick_blur(take_s, ref_s, allow_radial):
    """Search on a small copy. Returns (kind, params, err)."""
    ref_t = tile_hf(ref_s)
    best = ("none", {}, hf_err(take_s, ref_t))
    take_hf = tile_hf(take_s).mean()
    if ref_t.mean() >= take_hf * 0.97:
        # reference as sharp or sharper: try mild unsharp
        for amt in (0.3, 0.6, 1.0):
            sh = take_s + (take_s - gauss(take_s, 1.0)) * amt
            e = hf_err(sh, ref_t)
            if e < best[2] - 0.01:
                best = ("sharpen", {"amount": amt}, e)
        return best
    for sg in (0.4, 0.7, 1.0, 1.4, 2.0, 2.8, 4.0, 5.5, 7.5):
        e = hf_err(gauss(take_s, sg), ref_t)
        if e < best[2]:
            best = ("gauss", {"sigma": sg}, e)
    if allow_radial and ref_t.mean() < take_hf * 0.75:
        for st in (0.03, 0.06, 0.1, 0.16, 0.24):
            for cx in (0.3, 0.5, 0.7):
                for cy in (0.3, 0.5, 0.7):
                    e = hf_err(radial(take_s, st, cx, cy, 8), ref_t)
                    if e < best[2] - 0.02:
                        best = ("radial", {"strength": st, "cx": cx, "cy": cy}, e)
    if ref_t.mean() < take_hf * 0.8:
        # whip pans smear along one direction
        for ang in (0, 45, 90, 135):
            for ln in (4, 8, 14, 24, 40):
                e = hf_err(motion(take_s, ln, ang), ref_t)
                if e < best[2] - 0.02:
                    best = ("motion", {"length": ln, "angle": ang}, e)
    return best


def apply_blur(a, kind, p, scale):
    if kind == "gauss":
        return gauss(a, p["sigma"] * scale)
    if kind == "radial":
        return radial(a, p["strength"], p["cx"], p["cy"], 14)
    if kind == "sharpen":
        return a + (a - gauss(a, 1.0 * scale)) * p["amount"]
    if kind == "motion":
        return motion(a, p["length"] * scale, p["angle"])
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="src/clip.mp4")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--take", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--trim", default="", help="a:b seconds of the take to use")
    ap.add_argument("--size", default="", help="WxH, default the take's size")
    ap.add_argument("--curves", type=float, default=1.0)
    ap.add_argument("--mode", choices=["rgb", "luma"], default="rgb",
                    help="rgb: per-channel curves; luma: luma curve + chroma match (safer when content differs)")
    ap.add_argument("--spatial", type=float, default=0.8)
    ap.add_argument("--blur", type=float, default=1.0, help="0 disables blur matching")
    ap.add_argument("--no-radial", action="store_true")
    ap.add_argument("--ref-timing", choices=["slot", "take"], default="slot",
                    help="slot: original frame at the same slot time; take: the frame the take's content came from (use after a retime)")
    ap.add_argument("--ref-map", default="", help="JSON list: the original frame number to grade each output frame against (overrides --ref-timing)")
    ap.add_argument("--report", default="")
    ap.add_argument("--blur-from", default="",
                    help="reuse a report's per-frame blur picks, so a take rebuilt from a sharper source keeps the approved take's whips, zoom blurs and softening")
    a = ap.parse_args()

    n = round((a.end - a.start) * FPS)
    tw, th = probe_size(a.take)
    if a.size:
        tw, th = map(int, a.size.lower().split("x"))
    take_in = []
    if a.trim:
        t0, t1 = map(float, a.trim.split(":"))
        take_in = ["-ss", str(t0), "-t", str(t1 - t0)]
        tdur = t1 - t0
    else:
        tdur = probe_duration(a.take)
    k = (n / FPS) / tdur
    scale = f"scale={tw}:{th}:flags=lanczos"
    take = read_frames(take_in + ["-i", a.take],
                       f"setpts=(PTS-STARTPTS)*{k:.6f},fps={FPS},{scale}", tw, th, n)
    # select by frame index (input seeking on this file drops frames)
    k0 = round(a.start * FPS)
    ref = read_frames(["-i", a.src],
                      f"select=gte(n\\,{k0}),setpts=PTS-STARTPTS,{scale}", tw, th, n, True)
    if a.ref_map:
        # an explicit original frame per output frame (a take retimed by a speed ramp, e.g. shots/jersey/timeline.py)
        want = json.load(open(a.ref_map))
        assert len(want) == n, (len(want), n)
        lo = min(want)
        ref = read_frames(["-i", a.src], f"select=gte(n\\,{lo}),setpts=PTS-STARTPTS,{scale}", tw, th, max(want) - lo + 1, True)
        ref = ref[[w - lo for w in want]]
    elif a.ref_timing == "take":
        # the take was made from the original in real time, so after a retime
        # the matching original frame is where the take's content came from
        t0 = float(a.trim.split(":")[0]) if a.trim else 0.0
        idx = [min(n - 1, round((t0 + (i / FPS) / k) * FPS)) for i in range(n)]
        ref = ref[idx]

    gw, gh = 16, 9
    sw, sh = 640, round(640 * th / tw)  # blur search scale; 320 hid mild blur

    # pass 1: curves and gain grids
    graded = []
    gains = []
    rows = []
    ref_y = [float(luma(r[::4, ::4]).mean()) for r in ref]
    params = smooth_params([grade_params(take[i], ref[i], a.curves, a.mode) for i in range(n)], ref_y)
    for i in range(n):
        g = apply_grade(take[i], params[i])
        graded.append(g)
        ratio = (grid_means(ref[i].astype(np.float32), gw, gh) + 8) / (grid_means(g, gw, gh) + 8)
        gains.append(np.log(np.clip(ratio, 0.5, 2.0)))
    gains = np.stack(gains)
    # temporal smoothing (5-frame mean) so content mismatch does not flicker
    sm = np.copy(gains)
    for i in range(n):
        sm[i] = gains[max(0, i - 2): i + 3].mean(0)
    # remove the global part (curves already matched the mean), keep the shape
    sm = sm - sm.mean((1, 2), keepdims=True)
    sm = np.clip(sm, np.log(0.7), np.log(1.4)) * a.spatial

    pipe = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{tw}x{th}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
        "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-frames:v", str(n), a.out], stdin=subprocess.PIPE)

    # pass 2: pick a blur per frame, then smooth the choice in time so the
    # Gaussian/sharpen strength does not flicker. Radial frames keep theirs.
    picks = []
    for i in range(n):
        graded[i] = graded[i] * np.exp(upsample_gain(sm[i], tw, th))
        if a.blur <= 0:
            picks.append(("none", {}, 0.0))
            continue
        gs = np.asarray(to_img(graded[i]).resize((sw, sh), Image.BILINEAR), np.float32)
        rs = np.asarray(Image.fromarray(ref[i]).resize((sw, sh), Image.BILINEAR), np.float32)
        picks.append(pick_blur(gs, rs, not a.no_radial))

    def soft(pk):
        kind, p, _ = pk
        if kind == "gauss":
            return p["sigma"]
        if kind == "sharpen":
            return -p["amount"]
        return 0.0

    raw_picks = [(pk[0], pk[1]) for pk in picks]
    vals = [soft(pk) for pk in picks]
    for i in range(n):
        if picks[i][0] in ("radial", "motion"):
            continue
        win = [vals[j] for j in range(max(0, i - 1), min(n, i + 2)) if picks[j][0] not in ("radial", "motion")]
        v = float(np.median(win)) * a.blur
        if v > 0.15:
            picks[i] = ("gauss", {"sigma": round(v, 2)}, picks[i][2])
        elif v < -0.1:
            picks[i] = ("sharpen", {"amount": round(-v, 2)}, picks[i][2])
        else:
            picks[i] = ("none", {}, picks[i][2])

    if a.blur_from:
        old = json.load(open(a.blur_from))["frames"]
        assert len(old) == n, (a.blur_from, len(old), n)
        names = {"none": (), "gauss": ("sigma",), "sharpen": ("amount",), "radial": ("strength", "cx", "cy"), "motion": ("length", "angle")}
        picks = [(r["blur"], {k: r[k] for k in names[r["blur"]]}, 0.0) for r in old]

    for i in range(n):
        kind, p, err = picks[i]
        g = apply_blur(graded[i], kind, p, tw / sw)
        # re-pin global levels after blur and gain so flashes land exactly
        g8 = np.clip(g + 0.5, 0, 255).astype(np.uint8)
        g = apply_grade(g8, grade_params(g8, ref[i], a.curves, a.mode))
        out = np.clip(g + 0.5, 0, 255).astype(np.uint8)
        pipe.stdin.write(out.tobytes())
        rows.append({
            "f": i, "t": round(a.start + i / FPS, 3),
            "ref_y": round(float(luma(ref[i]).mean()), 1),
            "take_y": round(float(luma(take[i]).mean()), 1),
            "out_y": round(float(luma(out).mean()), 1),
            "ref_sat": round(float((ref[i].max(-1).astype(int) - ref[i].min(-1)).mean()), 1),
            "take_sat": round(float((take[i].max(-1).astype(int) - take[i].min(-1)).mean()), 1),
            "out_sat": round(float((out.max(-1).astype(int) - out.min(-1)).mean()), 1),
            "blur": kind, **p, "raw_blur": raw_picks[i][0], "raw": raw_picks[i][1],
        })
    pipe.stdin.close()
    if pipe.wait() != 0:
        sys.exit("ffmpeg encode failed")
    if a.report:
        with open(a.report, "w") as f:
            json.dump({"start": a.start, "end": a.end, "take": a.take, "frames": rows}, f, indent=1)
    blurs = {}
    for r in rows:
        blurs[r["blur"]] = blurs.get(r["blur"], 0) + 1
    print(f"{a.out}: {n} frames, blur {blurs}")


if __name__ == "__main__":
    main()
