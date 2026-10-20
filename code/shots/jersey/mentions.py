# The arcmira.mentions line over the jersey shot: soft white, a little transparent, centred above his head and the
# white bar behind it, fading in from 25.56 s. Writes out/fadein-v3.mp4 from fadein-v2 and out/mentions-layer.png
# (full-frame RGBA at full strength) so the profile crossfade can carry the same layer on.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/jersey/mentions.py [src dst]   (from R)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, subprocess, sys, cv2, numpy as np
# [src dst]: v3 is fadein-v2 -> fadein-v3 (default); v4 is fadein-v4 -> fadein-v4-mentions
SRC, DST = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('shots/jersey/out/fadein-v2.mp4', 'shots/jersey/out/fadein-v3.mp4')
from PIL import Image, ImageDraw, ImageFilter, ImageFont
W, H, FPS, T0 = 1920, 1080, 30, 25.43
TEXT = 'arcmira.mentions(entity: "dylan patel")'
CX, BASE, SIZE, ALPHA = 1125, 140, 40, 0.72
FADE_IN = (25.56, 26.06)
font = ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), 'InterDisplay-Medium.ttf'), SIZE)
ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov)
d.text((CX, BASE), TEXT, font=font, fill=(255, 255, 255, 255), anchor='ms')
a = np.asarray(ov.split()[3], np.float32) / 255
sh = np.asarray(ov.split()[3].filter(ImageFilter.GaussianBlur(7)), np.float32) / 255 * 0.6
alpha = np.clip(a * ALPHA + sh * (1 - a * ALPHA) * ALPHA, 0, 1)
rgb = np.where(alpha > 0, a * ALPHA / np.maximum(alpha, 1e-4), 0) * 255
layer = np.dstack([rgb, rgb, rgb, alpha * 255]).astype(np.uint8)
Image.fromarray(layer, 'RGBA').save('shots/jersey/out/mentions-layer.png')
c = cv2.VideoCapture(SRC); frames = []
while True:
    ok, f = c.read()
    if not ok: break
    frames.append(f)
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                      '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', DST], stdin=subprocess.PIPE)
for k, f in enumerate(frames):
    t = T0 + k / FPS
    u = min(max((t - FADE_IN[0]) / (FADE_IN[1] - FADE_IN[0]), 0), 1)
    e = u * u * (3 - 2 * u)
    m = (layer[..., 3:4].astype(np.float32) / 255) * e
    out = f.astype(np.float32) * (1 - m) + layer[..., 2::-1].astype(np.float32) * m
    p.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
p.stdin.close(); p.wait()
print(len(frames), 'frames')
