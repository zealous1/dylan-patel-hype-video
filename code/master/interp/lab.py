# Lab for the 60 fps routes: a frame cache of the 30 fps reel, per-pair features, in-between sources, route assembly,
# the route measures and the strips. Every command skips work whose output already exists, so a rerun resumes.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/interp/lab.py <command> [args]
#   cache | features | rife <tag> [ncnn flags] | prife <tag> <dir> | midfeat <tag> | route <name> | strips | drop <tag>
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys, time
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import render60 as r6

WORK = os.path.join(HERE, 'work')
ROUTES = os.path.join(HERE, 'routes')
F30 = os.path.join(WORK, 'f30.u8')
SC = r6.SCENES
N = sum(s.n for s in SC)
START = {s.name: sum(t.n for t in SC[:i]) for i, s in enumerate(SC)}
TEXT = {'newspaper', 'fastcuts'}  # also the scenes render.py interpolated straight through


def f30():
    return np.memmap(F30, np.uint8, 'r', shape=(N, r6.H, r6.W, 3))


def mids(tag, mode='r'):
    return np.memmap(os.path.join(WORK, f'mid-{tag}.u8'), np.uint8, mode, shape=(N, r6.H, r6.W, 3))


def save(obj, path):
    with open(path + '.tmp', 'w') as fh:
        json.dump(obj, fh)
    os.replace(path + '.tmp', path)


def done(path):
    if os.path.exists(path):
        print('have', os.path.basename(path)); return True
    return False


def cmd_cache():
    if done(os.path.join(WORK, 'scenes.json')):
        return
    m = np.memmap(F30, np.uint8, 'w+', shape=(N, r6.H, r6.W, 3))
    for s in SC:
        m[START[s.name]:START[s.name] + s.n] = r6.frames(s.take, s.n)
    m.flush()
    save([[s.name, s.n] for s in SC], os.path.join(WORK, 'scenes.json'))


def cmd_features():
    if done(os.path.join(WORK, 'pairs.json')):
        return
    f = f30()
    rows = []
    for s in SC:
        i = START[s.name]
        for k in range(s.n - 1):
            rows.append(dict(r6.pair_features(f[i + k], f[i + k + 1]), scene=s.name, k=k, g=i + k))
    save(rows, os.path.join(WORK, 'pairs.json'))


def cmd_rife(tag, *flags):
    meta = os.path.join(WORK, f'mid-{tag}.json')
    if done(meta):
        return
    f, out, t = f30(), mids(tag, 'w+'), time.time()
    for s in SC:
        i = START[s.name]
        out[i:i + s.n] = r6.rife_mids(f[i:i + s.n], flags)
        print(tag, s.name, f'{time.time() - t:.0f}s', flush=True)
    out.flush()
    save(dict(flags=flags, secs=time.time() - t), meta)


def cmd_prife(tag, d):
    """Practical-RIFE's midpoints from modal_prife.py's per-scene files, laid out like the ncnn runs."""
    meta = os.path.join(WORK, f'mid-{tag}.json')
    if done(meta):
        return
    f, out = f30(), mids(tag, 'w+')
    for s in SC:
        i = START[s.name]
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(WORK, d, f'{s.name}.mkv'), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                             capture_output=True, check=True).stdout
        m = np.frombuffer(raw, np.uint8).reshape(-1, r6.H, r6.W, 3)
        assert len(m) == s.n - 1, (s.name, len(m))
        out[i:i + s.n - 1] = m
        out[i + s.n - 1] = f[i + s.n - 1]
    out.flush()
    save(dict(src=d), meta)


def cmd_midfeat(tag):
    path = os.path.join(WORK, f'midfeat-{tag}.json')
    if done(path):
        return
    f = f30()
    m = None if tag == 'blend' else mids(tag)
    rows = []
    for s in SC:
        i = START[s.name]
        for k in range(s.n - 1):
            a, b = f[i + k], f[i + k + 1]
            rows.append(r6.mid_features(a, b, r6.blend(a, b) if m is None else m[i + k]))
    save(rows, path)


def cmd_drop(tag):
    p = os.path.join(WORK, f'mid-{tag}.u8')
    if os.path.exists(p):
        os.remove(p)


# A route: where its in-betweens come from, how each pair is decided, and which scenes it takes natively at 60 fps.
#   src: an in-between tag, or None for doubling. rule: 'rule' (the per-pair rule), 'cuts' (render.py's: RIFE everywhere
#   but its detected cuts), 'blendwhip' (the rule, with whips blended), or 'double'. native/doubled: scene sets.
ROUTE = {
    'r0-current': dict(src='base', rule='cuts', label='Current 60 (v4.6 everywhere but cuts)'),
    'r1-double': dict(src=None, rule='double', label='1 No interpolation'),
    'r2-v46': dict(src='base', rule='rule', label='2 Rule, v4.6'),
    'r2-v46-blendwhip': dict(src='base', rule='blendwhip', label='2b Rule, v4.6, whips blended'),
    'r3-x': dict(src='x', rule='rule', label='3 Rule, v4.6 -x'),
    'r3-z': dict(src='z', rule='rule', label='3 Rule, v4.6 -z'),
    'r3-u': dict(src='u', rule='rule', label='3 Rule, v4.6 -u'),
    'r3-xzu': dict(src='xzu', rule='rule', label='3 Rule, v4.6 -x -z -u'),
    'r4-p425': dict(src='p425', rule='rule', label='4 Rule, Practical-RIFE 4.25'),
    'r4-p426': dict(src='p426', rule='rule', label='4 Rule, Practical-RIFE 4.26'),
    'r5-native': dict(src='base', rule='rule', native=sorted(TEXT), label='Native: text scenes rendered at 60, rest rule v4.6'),
    'r6-hybrid': dict(src='base', rule='rule', doubled=sorted(TEXT), label='Hybrid: text scenes doubled, rest rule v4.6'),
}


def decide(rule, p, m):
    if rule == 'double':
        return 'hold'
    if rule == 'cuts':
        return 'hold' if p['scene'] not in TEXT and p['corr'] < 0.45 and p['diff'] > 18 else 'rife'
    how = r6.choose(p, m)
    return 'blend' if rule == 'blendwhip' and r6.classify(p) == 'whip' else how


def route_frames(cfg):
    """The route's 1804 frames in order, with each in-between's choice."""
    f = f30()
    P = json.load(open(os.path.join(WORK, 'pairs.json')))
    src = cfg['src']
    M = mids(src) if src else None
    MF = json.load(open(os.path.join(WORK, f'midfeat-{src}.json'))) if src else [None] * len(P)
    pi = 0
    for s in SC:
        i = START[s.name]
        if s.name in cfg.get('native', ()):
            nat = r6.frames(r6.NATIVE60[s.name])
            assert len(nat) == 2 * s.n
            for j, x in enumerate(nat):
                yield x, ('real' if j % 2 == 0 else 'native')
            pi += s.n - 1
            continue
        for k in range(s.n):
            yield f[i + k], 'real'
            if k == s.n - 1:
                yield f[i + k], 'end'
                continue
            p, m = P[pi], MF[pi]; pi += 1
            how = 'hold' if s.name in cfg.get('doubled', ()) else decide(cfg['rule'], p, m)
            yield r6.apply(f[i + k], f[i + k + 1], M[i + k] if M is not None else None, how), how


def measure(seq):
    """Per in-between frame: sharpness against its neighbours (log2 of its own over their geometric mean), and how evenly
    it splits the motion between them (0 is an even split, 1 is a held frame)."""
    s = [r6.sharp(x) for x, _ in seq]
    rows = []
    for j in range(1, len(seq) - 1, 2):
        a, m, b = seq[j - 1][0], seq[j][0], seq[j + 1][0]
        dip = float(np.log2((s[j] + 2) / np.sqrt((s[j - 1] + 2) * (s[j + 1] + 2))))
        _, _, fam = r6.flow(a, m)
        _, _, fmb = r6.flow(m, b)
        ma, mb = float(np.median(np.hypot(*fam.transpose(2, 0, 1)))) * r6.FS, float(np.median(np.hypot(*fmb.transpose(2, 0, 1)))) * r6.FS
        cad = abs(ma / (ma + mb) - 0.5) * 2 if ma + mb > 2 else None
        rows.append(dict(j=j, how=seq[j][1], s=s[j], dip=dip, cad=cad, m=ma + mb))
    return s, rows


def encode(seq, mp4):
    # A short GOP keeps the compare page's frame stepping exact and quick.
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{r6.W}x{r6.H}', '-r', '60', '-i', '-',
                            '-c:v', 'libx264', '-preset', 'fast', '-crf', '12', '-g', '12', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4],
                           stdin=subprocess.PIPE)
    for x in seq:
        enc.stdin.write(np.ascontiguousarray(x).tobytes())
    enc.stdin.close(); enc.wait()
    assert enc.returncode == 0


def cmd_route(name, *extra):
    cfg = dict(ROUTE.get(name) or json.loads(extra[0]))
    os.makedirs(ROUTES, exist_ok=True)
    mp4, js = os.path.join(ROUTES, f'{name}.mp4'), os.path.join(ROUTES, f'{name}.json')
    if done(js):
        return
    t = time.time()
    seq = list(route_frames(cfg))
    assert len(seq) == 2 * N, len(seq)
    encode([x for x, _ in seq], mp4)
    sharp, rows = measure(seq)
    strips = {}
    for F in strip_frames():
        strips[F] = [cv2.imencode('.jpg', cv2.resize(seq[j][0], (640, 360), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes().hex()
                     for j in (F - 1, F, F + 1)]
    save(dict(cfg=cfg, sharp=sharp, rows=rows, strips=strips, secs=time.time() - t), js)
    print(name, f'{time.time() - t:.0f}s')


FASTCUT_CUTS = [12, 24, 37, 49, 86, 99, 111, 123, 148, 160]  # fastcuts-v14 clip starts, in 30 fps frames


def strip_frames():
    fc = 2 * START['fastcuts']
    return [745, 1069, 515, 493] + [fc + 2 * c - 1 for c in FASTCUT_CUTS]


if __name__ == '__main__':
    globals()['cmd_' + sys.argv[1]](*sys.argv[2:])
