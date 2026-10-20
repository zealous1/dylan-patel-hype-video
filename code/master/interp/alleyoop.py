# The alley-oop's 60 fps frames, five ways: resampling the slowed Wan generation (render.py's v4.6 batch, Practical-RIFE
# 4.26 at the same positions, the per-pair rule, or its nearest real frame) against the per-pair rule on the realtime take.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/interp/alleyoop.py
# Writes master/interp/routes/alleyoop-<way>.mp4 and alleyoop.json.
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab
r6 = lab.r6

S = next(s for s in r6.SCENES if s.name == 'alleyoop')
N60 = 2 * S.n


def realtime_rule():
    seq = list(lab.route_frames(lab.ROUTE['r2-v46']))
    a = 2 * lab.START['alleyoop']
    return [x for x, _ in seq[a:a + N60]]


def slow():
    return r6.frames(S.slow)


def positions():
    return r6.realtime_positions(150, S.n)


def resample_batch():
    import tempfile, cv2
    f = slow()
    with tempfile.TemporaryDirectory(dir=os.path.join(r6.R, 'master')) as d:
        os.makedirs(d + '/in'); os.makedirs(d + '/out')
        for i, x in enumerate(f):
            cv2.imwrite(f'{d}/in/{i + 1:08d}.png', x, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        subprocess.run([f'{r6.RIFE}/rife-ncnn-vulkan', '-i', d + '/in', '-o', d + '/out', '-m', r6.MODEL, '-n', str(N60)], check=True, capture_output=True)
        return [cv2.imread(f'{d}/out/{nm}') for nm in sorted(os.listdir(d + '/out'))]


def prife_resample():
    # modal_prife.py's alleyoop-slow.mkv holds the fractional positions of r6.slow_positions(150, 142), in order.
    f = slow()
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(lab.WORK, 'prife-4.26-1', 'alleyoop-slow.mkv'), '-f', 'rawvideo',
                          '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    mids = iter(np.frombuffer(raw, np.uint8).reshape(-1, r6.H, r6.W, 3))
    return [f[int(p)] if p % 1 == 0 else next(mids) for p in r6.slow_positions(len(f), N60)]


WAYS = {
    'realtime-rule': ('Rule on the realtime take (v4.6)', realtime_rule),
    'slow-ncnn': ('Slowed generation, v4.6 batch resample (render.py)', resample_batch),
    'slow-p426': ('Slowed generation, Practical-RIFE 4.26 resample', prife_resample),
    'slow-rule': ('Slowed generation, per-pair rule at each position (v4.6)', lambda: r6.sample(slow(), positions())),
    'slow-nearest': ('Slowed generation, nearest real frame', lambda f=None: [(f := f if f is not None else slow())[int(round(p))] for p in positions()]),
}


def main():
    path = os.path.join(lab.ROUTES, 'alleyoop.json')
    res = json.load(open(path)) if os.path.exists(path) else {}
    for way, (label, make) in WAYS.items():
        if way in res:
            continue
        seq = make()
        assert len(seq) == N60, (way, len(seq))
        lab.encode([np.ascontiguousarray(x) for x in seq], os.path.join(lab.ROUTES, f'alleyoop-{way}.mp4'))
        sharp, rows = lab.measure([(x, 'x') for x in seq])
        res[way] = dict(label=label, sharp=sharp, rows=rows)
        lab.save(res, path)
        print(way, round(float(np.mean(sharp)), 1), flush=True)


if __name__ == '__main__':
    main()
