# Cut the Dingboard SemiAnalysis banner off its grey background: drop the sponsor pill and the subscriber count,
# flood-fill the background from the edges, soften the edge, crop to the logo.
#   uv run --no-project --python 3.12 --with-requirements ../requirements.txt python -I logo_cut.py <in.png> <out.png>
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

src, out = sys.argv[1:3]
im = np.asarray(Image.open(src).convert("RGB")).astype(float)
h, w, _ = im.shape
bg = np.median(np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)]), axis=0)
d = np.linalg.norm(im - bg, axis=2)
near = d < 28
lab, _ = ndimage.label(near)
edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
wordmark = np.zeros_like(near); wordmark[:, int(w * 0.4):] = True
bgmask = np.isin(lab, list(edge)) | (near & wordmark & (ndimage.sum_labels(near, lab, lab) > 20))
fg = ~bgmask
# Drop every foreground blob that is not part of the logo: the sponsor pill (top right) and the count box (bottom).
blobs, n = ndimage.label(ndimage.binary_dilation(fg, iterations=6))
keep = np.zeros_like(fg)
for i in range(1, n + 1):
    ys, xs = np.nonzero(blobs == i)
    cx, cy, area = xs.mean() / w, ys.mean() / h, len(xs)
    sponsor = cx > 0.75 and cy < 0.3
    count = 0.4 < cx < 0.75 and cy > 0.7
    if area > 400 and not sponsor and not count:
        keep |= blobs == i
fg &= keep
dist = ndimage.distance_transform_edt(fg)
alpha = np.clip(dist / 2.0, 0, 1)
# Unmix the grey from edge pixels so the cutout has no halo on dark or gold backgrounds.
a = np.maximum(alpha, 1e-3)[..., None]
rgb = np.clip((im - bg * (1 - a)) / a, 0, 255)
rgba = np.dstack([rgb, alpha * 255]).astype(np.uint8)
ys, xs = np.nonzero(alpha > 0)
pad = 8
crop = rgba[max(ys.min() - pad, 0): ys.max() + pad, max(xs.min() - pad, 0): xs.max() + pad]
Image.fromarray(crop, "RGBA").save(out)
print("bg", bg.round(), "size", crop.shape[1], crop.shape[0])
