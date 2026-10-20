# Renders the 60 fps reel, before the film pass. Every in-between is chosen pair by pair: RIFE where the two 30 fps
# frames are the same picture moving and RIFE's frame passes a sharpness and error gate, a hold across a cut or a
# whip, and a 50/50 blend across a flash. A scene whose take is already 60 fps (the newspaper and the podcast cut,
# rendered natively) is used frame for frame.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/render60.py [--scenes scenes.json] [--no-native]
# --scenes is a JSON object of scene name to take path (relative to the reel folder), laid over render.py's SCENES,
# e.g. {"rim": "shots/upscale-test/out/rim-seedvr2-7b.mp4"}. A take at 60 fps is used directly; any other must hold
# the scene's 30 fps frame count. Writes master/out/reel-60-v2-master.mp4 (x264 CRF 8, yuv420p, the chosen mix).
import argparse, ast, json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import numpy as np, cv2

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
W, H = 1920, 1080
RIFE = os.environ.get('RIFE_DIR', 'rife-ncnn-vulkan')
MODEL = f'{RIFE}/rife-v4.6'
MIX = 'audio/mix-final-patel3-5-outro3.wav'


@dataclass(frozen=True)
class Scene:
    name: str
    take: str
    n: int
    slow: str | None = None


def render_py_scenes():
    """render.py's SCENES, read from its source so the two never drift (importing it would run its render)."""
    tree = ast.parse(open(os.path.join(R, 'master', 'render.py')).read())
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'SCENES')
    return [Scene(*row) for row in ast.literal_eval(node.value)]


SCENES = render_py_scenes()
NATIVE60 = {'newspaper': 'shots/newspaper/out/paper-v4-60.mp4', 'fastcuts': 'shots/fastcuts/out/fastcuts-v14-60.mp4'}


def take_fps(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0',
                        os.path.join(R, path)], capture_output=True, text=True, check=True).stdout.strip()
    a, b = r.split('/')
    return int(a) / int(b)


def frames(path, n=None):
    cmd = ['ffmpeg', '-v', 'error', '-i', os.path.join(R, path), '-vf', f'scale={W}:{H}:flags=lanczos']
    cmd += ['-frames:v', str(n)] if n else []
    raw = subprocess.run(cmd + ['-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    assert n is None or len(f) == n, (path, len(f), n)
    return f


def gray(x):
    return cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)


def sharp(x):
    return float(cv2.Laplacian(gray(x), cv2.CV_32F).var())


_dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
FS = 4  # flow runs at a quarter of 1080p


def flow(a, b):
    """Flow from a to b at quarter resolution, on grey frames."""
    sa = cv2.resize(gray(a), (W // FS, H // FS), interpolation=cv2.INTER_AREA)
    sb = cv2.resize(gray(b), (W // FS, H // FS), interpolation=cv2.INTER_AREA)
    return sa, sb, _dis.calc(sa, sb, None)


def warp(img, fl):
    h, w = fl.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def pair_features(a, b):
    ta = cv2.resize(gray(a), (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32)
    tb = cv2.resize(gray(b), (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32)
    za, zb = ta - ta.mean(), tb - tb.mean()
    corr = float((za * zb).sum() / (np.sqrt((za * za).sum() * (zb * zb).sum()) + 1e-6))
    sa, sb, fl = flow(a, b)
    raw = float(np.abs(sa.astype(np.float32) - sb).mean())
    res = float(np.abs(sa.astype(np.float32) - warp(sb, fl)).mean())
    mag = np.hypot(fl[..., 0], fl[..., 1]) * FS
    return dict(corr=corr, diff=float(np.abs(ta - tb).mean()), dluma=float(tb.mean() - ta.mean()),
                sa=sharp(a), sb=sharp(b), raw=raw, res=res, m50=float(np.median(mag)), m95=float(np.percentile(mag, 95)))


def mid_features(a, b, m):
    """How well a candidate in-between m is explained by its neighbours: both get warped onto it, and each pixel keeps the
    better of the two, so a disocclusion seen by only one side still counts as explained."""
    sm, sa, fa = flow(m, a)
    _, sb, fb = flow(m, b)
    err = np.minimum(np.abs(sm.astype(np.float32) - warp(sa, fa)), np.abs(sm.astype(np.float32) - warp(sb, fb)))
    return dict(s=sharp(m), err=float(err.mean()), e95=float(np.percentile(err, 95)))


def classify(p):
    """What kind of change a pair of frames is. Thresholds come from the per-pair table in master/interp/index.html."""
    if p['diff'] < 3:
        return 'move'  # near-identical or near-black frames; every in-between looks the same
    if abs(p['dluma']) > 25 and abs(p['dluma']) > 0.6 * p['diff']:
        return 'flash'
    if p['corr'] < 0.45:
        return 'cut'
    if p['m50'] > 80 and p['res'] > 5:
        return 'whip'
    return 'move'


FALLBACK = {'cut': 'hold', 'whip': 'hold', 'flash': 'blend'}


def gate(p, m):
    """RIFE's frame is kept only if it is about as sharp as its neighbours and its neighbours explain it."""
    lo, hi = min(p['sa'], p['sb']), max(p['sa'], p['sb'])
    soft = lo >= 5 and m['s'] < 0.7 * lo
    speckle = m['s'] > 1.6 * hi + 2  # RIFE invents texture on flat, grainy frames
    return not (soft or speckle or m['err'] > max(6.0, 0.5 * p['res']))


def choose(p, m):
    c = classify(p)
    if c != 'move':
        return FALLBACK[c]
    return 'rife' if gate(p, m) else 'hold'


def blend(a, b, t=0.5):
    return cv2.addWeighted(a, 1 - t, b, t, 0)


def apply(a, b, mid, how, t=0.5):
    return {'rife': mid, 'hold': a if t <= 0.5 else b, 'blend': blend(a, b, t)}[how]


def rife_mids(f, flags=()):
    """RIFE's midpoint between each frame and the next, in one batch run; the last entry is a copy of the last frame."""
    with tempfile.TemporaryDirectory(dir=os.path.join(R, 'master')) as d:
        os.makedirs(d + '/in'); os.makedirs(d + '/out')
        for i, x in enumerate(f):
            cv2.imwrite(f'{d}/in/{i + 1:08d}.png', x, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        subprocess.run([f'{RIFE}/rife-ncnn-vulkan', '-i', d + '/in', '-o', d + '/out', '-m', MODEL, '-n', str(2 * len(f)), *flags],
                       check=True, capture_output=True)
        names = sorted(os.listdir(d + '/out'))
        assert len(names) == 2 * len(f), len(names)
        out = np.stack([cv2.imread(f'{d}/out/{nm}') for nm in names[1::2]])
    out[-1] = f[-1]
    return out


def rife_at(f, jobs):
    """RIFE's frame between f[i] and f[i + 1] at time t, for each [i, t] job."""
    with tempfile.TemporaryDirectory(dir=os.path.join(R, 'master')) as d:
        for k in sorted({k for i, _ in jobs for k in (i, i + 1)}):
            cv2.imwrite(f'{d}/{k}.png', f[k], [cv2.IMWRITE_PNG_COMPRESSION, 1])

        def one(j):
            i, t = jobs[j]
            subprocess.run([f'{RIFE}/rife-ncnn-vulkan', '-0', f'{d}/{i}.png', '-1', f'{d}/{i + 1}.png', '-o', f'{d}/m{j}.png',
                            '-m', MODEL, '-s', f'{t:.6f}'], check=True, capture_output=True)
            return cv2.imread(f'{d}/m{j}.png')
        with ThreadPoolExecutor(3) as ex:
            return list(ex.map(one, range(len(jobs))))


def sample(f, positions, fallback='hold'):
    """Frames at fractional positions on f. A position between two frames gets RIFE's frame under the per-pair rule,
    with `fallback` standing in for 'hold' on a move whose RIFE frame fails the gate."""
    split = [(int(q), round(q - int(q), 6)) for q in (round(p, 6) for p in positions)]
    jobs = sorted({(i, t) for i, t in split if t > 1e-3 and i + 1 < len(f)})
    mids = dict(zip(jobs, rife_at(f, jobs))) if jobs else {}
    pairs = {}
    out = []
    for p, (i, t) in zip(positions, split):
        if (i, t) not in mids:
            out.append(f[min(int(round(p)), len(f) - 1)])
            continue
        if i not in pairs:
            pairs[i] = pair_features(f[i], f[i + 1])
        how = choose(pairs[i], mid_features(f[i], f[i + 1], mids[(i, t)]))
        how = fallback if how == 'hold' and classify(pairs[i]) == 'move' else how
        out.append(apply(f[i], f[i + 1], mids[(i, t)], how, t))
    return out


def slow_positions(count, n_out):
    """Where each 60 fps frame sits on a slowed generation, spread over it the way rife-ncnn-vulkan's -n spaces them."""
    return [min(j * count / n_out, count - 1) for j in range(n_out)]


def realtime_positions(count, n):
    """Where each 60 fps frame of a sped-up take sits on its slowed generation. The alley-oop's realtime frame k matches
    generation frame 1 + k * (count - 2) / (n - 1) by pixel difference, so the 60 fps frames take half steps of that."""
    return [min(1 + j * (count - 2) / (2 * (n - 1)), count - 1) for j in range(2 * n)]


def scene60(s, take, log, slow=None):
    if take_fps(take) == 60:
        out = frames(take)
        assert len(out) == 2 * s.n, (s.name, len(out))
        log[s.name] = {'native': len(out)}
        return list(out)
    if slow:
        # Resampling the slowed generation interpolates across half the motion that pairs of the sped-up take span.
        g = frames(slow)
        out = sample(g, realtime_positions(len(g), s.n))
        log[s.name] = {'slow': slow}
        return out
    f = frames(take, s.n)
    mids = rife_mids(f)
    out, how = [], []
    for k in range(s.n):
        out.append(f[k])
        if k == s.n - 1:
            out.append(f[k]); how.append('end')
            continue
        h = choose(pair_features(f[k], f[k + 1]), mid_features(f[k], f[k + 1], mids[k]))
        out.append(apply(f[k], f[k + 1], mids[k], h)); how.append(h)
    log[s.name] = {h: how.count(h) for h in sorted(set(how))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenes', help='JSON file or inline object of scene name to take path, or to {"take", "slow"} for a slowed scene')
    ap.add_argument('--no-native', action='store_true', help="interpolate every scene's render.py take, even where a 60 fps take exists")
    ap.add_argument('--mix', default=MIX)
    ap.add_argument('--out', default='master/out/reel-60-v2-master.mp4')
    args = ap.parse_args()
    takes = {s.name: {'take': s.take, 'slow': s.slow} for s in SCENES}
    if not args.no_native:
        takes.update({k: {'take': v, 'slow': None} for k, v in NATIVE60.items()})
    if args.scenes:
        over = json.load(open(args.scenes)) if os.path.exists(args.scenes) else json.loads(args.scenes)
        unknown = set(over) - set(takes)
        assert not unknown, f'not scenes: {sorted(unknown)}'
        # A new take for a slowed scene replaces its generation too, unless the generation is named with it.
        takes.update({k: dict(take=v, slow=None) if isinstance(v, str) else dict(take=v['take'], slow=v.get('slow')) for k, v in over.items()})
    t0 = time.time()
    work = os.path.join(R, 'master', 'work')
    os.makedirs(work, exist_ok=True)
    video = os.path.join(work, 'video-60-v2.mp4')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '60', '-i', '-',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '8', '-pix_fmt', 'yuv420p', video], stdin=subprocess.PIPE)
    log = {}
    for s in SCENES:
        for x in scene60(s, takes[s.name]['take'], log, takes[s.name]['slow']):
            enc.stdin.write(np.ascontiguousarray(x).tobytes())
        print(s.name, takes[s.name]['slow'] or takes[s.name]['take'], log[s.name], f'{time.time() - t0:.0f}s', flush=True)
    enc.stdin.close(); enc.wait()
    assert enc.returncode == 0
    limited = os.path.join(work, os.path.basename(args.mix).replace('.wav', '-limited.wav'))
    if not os.path.exists(limited):  # the same limiter as render.py
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(R, args.mix), '-af',
                        'aresample=192000,alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000', '-c:a', 'pcm_s24le', limited], check=True)
    out = os.path.join(R, args.out)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', limited, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', out], check=True)
    json.dump(dict(takes=takes, choices=log, secs=round(time.time() - t0)), open(out.replace('.mp4', '.json'), 'w'), indent=1)
    print('wrote', out, f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
