# Final-state mockups of source-tag options on one podcast beat (Dwarkesh bottleneck, q "NVIDIA", speaker Dylan Patel).
#   uv run --no-project --python 3.12 --with-requirements ../../../requirements.txt python -I variants.py   (from this folder)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import numpy as np
W, H = 1920, 1080
GREEN, WHITE = (0, 255, 65), (255, 255, 255)
F = lambda w, s: ImageFont.truetype(os.path.join(os.environ.get('FONT_DIR', 'fonts'), f'InterDisplay-{w}.ttf'), s)
base = Image.open('base.png').convert('RGB').resize((W, H))
a = np.asarray(base).astype(np.float32) / 255
g = a @ [0.299, 0.587, 0.114]; a = a * 0.15 + g[..., None] * 0.85
a = np.clip((a - 0.5) * 1.25 + 0.46, 0, 1)
yy, xx = np.mgrid[0:H, 0:W]; v = 1 - 0.55 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2
graded = Image.fromarray((np.clip(a * v[..., None], 0, 1) * 255).astype(np.uint8))

Q = [('arcmira.search(', WHITE), ('"NVIDIA"', GREEN), (', speaker: "Dylan Patel")', WHITE)]
QUOTE = '"Huawei has cracked software engineers."'
def runs(d, xy, parts, font, alpha=0.8, cursor=True):
    x, y = xy
    for t, c in parts:
        d.text((x, y), t, font=font, fill=c + (int(255 * alpha),)); x += d.textlength(t, font=font)
    if cursor: d.rectangle((x + 6, y + 4, x + 6 + font.size * 0.5, y + font.size * 1.02), fill=GREEN + (int(255 * alpha),))
def tracked(d, xy, text, font, fill, track):
    x, y = xy
    for ch in text: d.text((x, y), ch, font=font, fill=fill); x += d.textlength(ch, font=font) + track
def frame(fn):
    im = graded.copy().convert('RGBA'); ov = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(ov); fn(d)
    sh = ov.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda p: p * 0.5)
    im.alpha_composite(Image.merge('RGBA', (*[Image.new('L', (W, H), 0)] * 3, sh))); im.alpha_composite(ov); return im.convert('RGB')
M = 72
V = {
 '1 query, keyword green': lambda d: runs(d, (M, M), Q, F('Medium', 46)),
 '2 query, all matrix green': lambda d: runs(d, (M, M), [(t, GREEN) for t, _ in Q], F('Medium', 46)),
 '3 query, then title + channel': lambda d: (runs(d, (M, M), Q, F('Medium', 46), cursor=False),
     d.text((M, M + 66), 'Dylan Patel: The Single Biggest Bottleneck to Scaling AI Compute', font=F('Regular', 32), fill=WHITE + (204,)),
     d.text((M, M + 108), 'Dwarkesh Patel · 2:23:01', font=F('Bold', 32), fill=WHITE + (204,))),
 '4 query + kino channel': lambda d: (runs(d, (M, M), Q, F('Medium', 46), cursor=False),
     tracked(d, (M, H - M - 200), 'DWARKESH PATEL', F('ExtraBold', 120), WHITE + (225,), 4),
     d.text((M + 6, H - M - 60), '2:23:01', font=F('Medium', 40), fill=GREEN + (230,))),
 '5 query + quote': lambda d: (runs(d, (M, M), Q, F('Medium', 46), cursor=False),
     d.text((W / 2, H - M - 20), QUOTE, font=F('Bold', 56), fill=WHITE + (230,), anchor='ms')),
 '6 everything': lambda d: (runs(d, (M, M), Q, F('Medium', 40), cursor=False),
     d.text((M, M + 58), 'Dwarkesh Patel · 2:23:01', font=F('Bold', 30), fill=WHITE + (204,)),
     d.text((W / 2, H - M - 20), QUOTE, font=F('Bold', 52), fill=WHITE + (230,), anchor='ms')),
 '7 two-word query': lambda d: runs(d, (M, M), [('arcmira.search(', WHITE), ('"export controls"', GREEN), (', speaker: "Dylan Patel")', WHITE)], F('Medium', 46)),
 '8 query as result row': lambda d: (runs(d, (M, M), Q, F('Medium', 46), cursor=False),
     d.text((M, M + 68), '>  Dwarkesh Patel   2:23:01   "Huawei has cracked software engineers."', font=F('Regular', 32), fill=WHITE + (204,))),
 '9 my pick: broadcast bar': lambda d: (
     d.rectangle((M, H - M - 92, M + 1230, H - M), fill=(14, 14, 16, 225)),
     d.rectangle((M, H - M - 92, M + 12, H - M), fill=GREEN + (255,)),
     d.text((M + 40, H - M - 46), 'ARCMIRA MCP', font=F('ExtraBold', 40), fill=WHITE + (255,), anchor='lm'),
     d.text((M + 345, H - M - 46), 'speaker: Dylan Patel   q: ', font=F('Medium', 38), fill=WHITE + (230,), anchor='lm'),
     d.text((M + 345 + d.textlength('speaker: Dylan Patel   q: ', font=F('Medium', 38)), H - M - 46), '"NVIDIA"', font=F('Bold', 38), fill=GREEN + (255,), anchor='lm'),
     d.rectangle((M + 1230, H - M - 92, M + 1700, H - M), fill=(245, 196, 0, 235)),
     d.text((M + 1465, H - M - 46), 'DWARKESH  2:23:01', font=F('ExtraBold', 38), fill=(14, 14, 16, 255), anchor='mm')),
}
tiles = []
for i, (name, fn) in enumerate(V.items(), 1):
    im = frame(fn); im.save(f'v{i}.png')
    t = im.resize((640, 360)); ImageDraw.Draw(t).text((10, 8), name, font=F('Bold', 18), fill=(255, 80, 80)); tiles.append(t)
grid = Image.new('RGB', (1920, 1080))
for i, t in enumerate(tiles): grid.paste(t, ((i % 3) * 640, (i // 3) * 360))
grid.save('grid.png'); print('ok')
