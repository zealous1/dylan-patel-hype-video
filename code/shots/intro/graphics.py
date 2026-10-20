"""Broadcast graphics for the intro (slot 1.00 to 6.27 s), composited on the
look-matched take.

Measured in src/clip.mp4: both graphics are fixed in screen space for the
whole span (template match at 6.20 s gives NCC 1.0 at the same pixel in every
frame), and they fade in with the whole picture from black, reaching full
level at about 1.9 s.

  Scorebug (OKC vs LAL). Copied per frame from the original inside a feathered
  rectangle, so the game clock and shot clock tick as broadcast and the fade
  is the original's. LAL becomes SA: the letters are filled out of each
  frame's gold cell and SA is set in Arial Bold (best overlap with the
  broadcast LAL and OKC of the system fonts, 0.87), condensed to the
  broadcast's width, left-aligned and at the letters' own brightness that
  frame.
  Banner. Rebuilt. The box background comes from the original frame at 6.20 s
  with its text removed by diffusion fill, then new text is set in the same
  layout (header, two box lines, number). Each frame it is scaled by the
  original's graphics level for that frame. The take's own AI header is
  filled out first so no letters ghost through.

Run from R: uv run --no-project --python 3.12 --with-requirements requirements.txt \
  python -I shots/intro/graphics.py IN OUT [--start S --end E] \
  [--line1 ... --line2 ... --num ...]
"""

import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS, W, H = 30, 1920, 1080
START, END = 1.00, 6.27   # set from the command line in main()
N = round((END - START) * FPS)
REF_T = 6.20              # absolute; the banner plate and SA mask come from here

BUG = (1408, 892, 1838, 987)          # x0 y0 x1 y1
BOX = (1604, 81, 1766, 135)           # grey box with the two text lines
NUM = (1766, 81, 1822, 135)           # box with the number
HEAD = (1630, 54, 1812, 79)           # header text area
TEAM = (1462, 940, 1545, 977)         # LAL letters in the gold cell
TEAM_LEFT, TEAM_BASE, TEAM_CAP, TEAM_X = 1471, 972, 27, 0.87
BAN = (1596, 50, 1830, 140)           # whole banner, for the take's fill

DIN = os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'BarlowCondensed-Bold.ttf')
FUT = os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'Barlow-Bold.ttf')
ARIAL_B = os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'Inter-Bold.ttf')


def frames(path, k0=0):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-frames:v", str(N), "-vf",
           f"select=gte(n\\,{k0}),setpts=PTS-STARTPTS,scale={W}:{H}", "-fps_mode", "passthrough", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-"]
    raw = subprocess.check_output(cmd)
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def diffuse_fill(img, mask, iters=400):
    """Fill mask pixels from their surroundings (harmonic inpaint)."""
    out = img.astype(np.float32).copy()
    m = mask.astype(bool)
    out[m] = out[~m].mean(0) if (~m).any() else 0
    for _ in range(iters):
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        out[m] = avg[m]
    return out


def dilate(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.asarray(im) > 127


def feather_rect(x0, y0, x1, y1, f):
    a = np.zeros((H, W), np.float32)
    a[y0:y1, x0:x1] = 1
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(f)), np.float32) / 255


def text_layer(draw_fn, ss=4):
    """Render white text supersampled, return alpha (H, W) float."""
    big = Image.new("L", (W * ss, H * ss), 0)
    draw_fn(big, ss)
    small = big.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    return np.asarray(small, np.float32) / 255


def fit_font(path, text, cap_px, ss, index=0):
    lo, hi = 4, 400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = ImageFont.truetype(path, mid * ss, index=index)
        b = f.getbbox("H")
        if (b[3] - b[1]) <= cap_px * ss:
            lo = mid
        else:
            hi = mid - 1
    return ImageFont.truetype(path, lo * ss, index=index)


def build_banner(ref, line1, line2, num, head):
    """Return (rgb plate, alpha) for the rebuilt banner at full level."""
    plate = ref.astype(np.float32).copy()
    # remove the old text inside the two boxes
    for (x0, y0, x1, y1) in (BOX, NUM):
        reg = plate[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
        y = reg.mean(-1)
        bg = np.asarray(Image.fromarray(np.clip(y, 0, 255).astype(np.uint8)).filter(
            ImageFilter.MedianFilter(9)), np.float32)
        txt = dilate((y > bg + 25) | (y > 150), 2)
        plate[y0 + 2:y1 - 2, x0 + 2:x1 - 2] = diffuse_fill(reg, txt)
    plate = np.clip(plate, 0, 255)

    def width(txt, font, stroke):
        b = font.getbbox(txt, anchor="ls", stroke_width=stroke)
        return b[2] - b[0]

    def put(canvas, txt, font, cx, base, xscale, ss, stroke=0):
        """Draw txt centred at cx (frame px) on baseline base, stretched in x."""
        b = font.getbbox(txt, anchor="ls", stroke_width=stroke)
        tw, th = b[2] - b[0] + 4 * ss, b[3] - b[1] + 4 * ss
        im = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(im).text((2 * ss - b[0], 2 * ss - b[1]), txt, font=font, fill=255,
                                anchor="ls", stroke_width=stroke, stroke_fill=255)
        im = im.resize((round(tw * xscale), th), Image.LANCZOS)
        x = round(cx * ss - im.width / 2)
        y = round(base * ss + b[1] - 2 * ss)
        canvas.paste(255, (x, y), im)

    def draw(canvas, ss):
        # The broadcast's box text is a heavier cut than DIN Condensed Bold:
        # a quarter-pixel stroke matches its stem width (half a pixel overshot).
        stroke = ss // 4
        cap, xs = 15.5, 1.12
        lim = (BOX[2] - BOX[0]) - 12
        while True:
            f1 = fit_font(DIN, "H", cap, ss)
            wmax = max(width(t, f1, stroke) for t in (line1, line2)) / ss
            if wmax * xs <= lim:
                break
            if xs > 0.9:
                xs = max(0.9, lim / wmax)
            else:
                cap -= 0.5
        cx = (BOX[0] + BOX[2]) / 2
        base1, base2 = 106.5 - (15.5 - cap) * 0.5, 128.5 - (15.5 - cap) * 0.5
        put(canvas, line1, f1, cx, base1, xs, ss, stroke)
        put(canvas, line2, f1, cx, base2, xs, ss, stroke)
        ncap, nxs = 30, 1.15
        nlim = (NUM[2] - NUM[0]) - 8
        while True:
            f2 = fit_font(DIN, "H", ncap, ss)
            w = width(num, f2, stroke) / ss
            if w * nxs <= nlim:
                break
            if nxs > 0.9:
                nxs = max(0.9, nlim / w)
            else:
                ncap -= 1
        put(canvas, num, f2, (NUM[0] + NUM[2]) / 2, 124 - (30 - ncap) / 2, nxs, ss, stroke)
        f3 = fit_font(FUT, "H", 14.5, ss)
        put(canvas, head, f3, 1721, 74.5, 1.0, ss)

    text_a = text_layer(draw)
    # text is slightly warm white in the original
    white = np.array([246, 246, 242], np.float32)
    box_a = np.maximum(feather_rect(*BOX, 0.8), feather_rect(*NUM, 0.8))
    # soft dark shadow under the header, like the broadcast's
    shadow = np.asarray(Image.fromarray((text_a * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2.5)), np.float32) / 255 * 0.55
    return plate, box_a, text_a, shadow, white


def build_team(ref, team):
    """Mask of the LAL letters (to fill out) and alpha of the new letters."""
    x0, y0, x1, y1 = TEAM
    y = ref[y0:y1, x0:x1].astype(np.float32).mean(-1)
    old = np.zeros((H, W), bool)
    old[y0:y1, x0:x1] = dilate(y > 150, 2)

    def draw(canvas, ss):
        f = fit_font(ARIAL_B, "H", TEAM_CAP, ss)
        b = f.getbbox(team, anchor="ls")
        tw, th = b[2] - b[0] + 4 * ss, b[3] - b[1] + 4 * ss
        im = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(im).text((2 * ss - b[0], 2 * ss - b[1]), team, font=f, fill=255, anchor="ls")
        im = im.resize((round(tw * TEAM_X), th), Image.LANCZOS)
        canvas.paste(255, (round(TEAM_LEFT * ss - 2 * ss * TEAM_X), round(TEAM_BASE * ss + b[1] - 2 * ss)), im)

    new_a = text_layer(draw)
    return old, new_a


def patch_team(f, src_f, old, new_a):
    """Fill the old letters out of this frame's gold cell, set the new ones at
    the old letters' brightness in this frame (so they follow the fade)."""
    x0, y0, x1, y1 = TEAM[0] - 4, TEAM[1] - 3, TEAM[2] + 4, TEAM[3] + 3
    reg = f[y0:y1, x0:x1]
    m = old[y0:y1, x0:x1]
    if not m.any():
        return
    col = np.percentile(src_f[y0:y1, x0:x1][m].astype(np.float32), 90, axis=0)
    filled = diffuse_fill(reg, m, 300)
    a = new_a[y0:y1, x0:x1, None]
    f[y0:y1, x0:x1] = filled * (1 - a) + col * a


def level(src_frame, ref_frame):
    """Graphics level of a frame relative to the reference (fade from black)."""
    x0, y0, x1, y1 = 1610, 905, 1670, 965  # white 104/97 boxes in the bug
    a = np.percentile(src_frame[y0:y1, x0:x1].mean(-1), 90)
    b = np.percentile(ref_frame[y0:y1, x0:x1].mean(-1), 90)
    return float(min(1.0, a / b))


def main():
    global START, END, N
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=START)
    ap.add_argument("--end", type=float, default=END)
    ap.add_argument("--head", default="DYLAN PATEL")
    ap.add_argument("--line1", default="TO BREAK")
    ap.add_argument("--line2", default="BOOTSTRAP RECORD")
    ap.add_argument("--num", default="$2M")
    ap.add_argument("--team", default="SA")
    args = ap.parse_args()
    START, END = args.start, args.end
    N = round((END - START) * FPS)
    take_path, out_path = args.take, args.out
    ref = frames("src/clip.mp4", round(REF_T * FPS))[0]
    src = frames("src/clip.mp4", round(START * FPS))
    take = frames(take_path)
    plate, box_a, text_a, shadow, white = build_banner(ref, args.line1, args.line2, args.num, args.head)
    old, new_a = build_team(ref, args.team)
    bug_a = feather_rect(*BUG, 1.2)[..., None]
    x0, y0, x1, y1 = BAN
    hx0, hy0, hx1, hy1 = HEAD

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
        "-pix_fmt", "yuv420p", "-frames:v", str(N), out_path], stdin=subprocess.PIPE)
    for i in range(N):
        f = take[i].astype(np.float32).copy()
        lv = level(src[i], ref)
        # fill out the take's own header letters
        reg = f[hy0:hy1, hx0:hx1]
        y = reg.mean(-1)
        m = dilate(y > np.median(y) + 30, 2)
        f[hy0:hy1, hx0:hx1] = diffuse_fill(reg, m, 150)
        # banner boxes
        ba = box_a[y0:y1, x0:x1, None]
        f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - ba) + plate[y0:y1, x0:x1] * lv * ba
        sa = shadow[y0:y1, x0:x1, None] * (1 - ba)
        f[y0:y1, x0:x1] *= (1 - sa)
        ta = text_a[y0:y1, x0:x1, None]
        f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - ta) + white * lv * ta
        # scorebug straight from the original, LAL set as SA
        bx0, by0, bx1, by1 = BUG[0] - 8, BUG[1] - 8, BUG[2] + 8, BUG[3] + 8
        a = bug_a[by0:by1, bx0:bx1]
        f[by0:by1, bx0:bx1] = f[by0:by1, bx0:bx1] * (1 - a) + src[i, by0:by1, bx0:bx1] * a
        patch_team(f, src[i], old, new_a)
        enc.stdin.write(np.clip(f + 0.5, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("encode failed")
    print(out_path, N, "frames")


if __name__ == "__main__":
    main()
