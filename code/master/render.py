# Renders the final reel from each scene's chosen take: a frame-exact 30 fps cut, and a 60 fps cut where RIFE v4.6
# (rife-ncnn-vulkan) invents the in-between frames inside each scene. Scenes are interpolated one at a time, so
# nothing morphs across a scene boundary, and a hard cut inside a scene (the podcast beats, the newspaper whip) holds
# the frame before the cut instead of blending two shots.
# The audio is the chosen mix, limited to -1 dBTP.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I master/render.py [--fps 30|60|both] [--mix audio/...]
# Writes master/out/reel-<fps>-master.mp4 (x264 CRF 10) and master/out/reel-<fps>-upload.mp4 (24 Mbps, for X and IG),
# and master/out/cuts.json with the in-scene cuts it found.
import argparse, json, os, shutil, subprocess
import numpy as np, cv2

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RIFE = os.environ.get('RIFE_DIR', 'rife-ncnn-vulkan')
W, H = 1920, 1080
SCENES = [  # (name, take, frames at 30 fps[, slowed generation]); the takes picked in the player on 2026-10-17.
    # A scene that plays a slowed Wan generation sped up gets its 60 fps frames from that generation's own frames
    # (RIFE only resamples them), not from in-betweens of the sped-up take.
    ('fadein', 'shots/fadein/out/fadein-v3.mp4', 30),
    ('intro', 'shots/intro/out/overlay-v3-from05.mp4', 158),
    ('backdown', 'shots/backdown/out/look-v1.mp4', 69),
    ('fadeaway', 'shots/fadeaway/out/wafer-v1.mp4', 43),
    ('rim', 'shots/rim/out/look-v1.mp4', 24),
    ('celebrate', 'shots/celebrate/out/look-v1.mp4', 36),
    ('newspaper', 'shots/newspaper/out/paper-v4.mp4', 55),
    ('fastcuts', 'shots/fastcuts/out/fastcuts-v14.mp4', 209),
    ('alleyoop', 'shots/alleyoop/out/final-realtime.mp4', 71, 'shots/alleyoop/out/wan-3.0-noframes-slow-focus-2.mp4'),
    ('fadeout', 'shots/fadeout/out/splice-v3.mp4', 68),
    ('jersey', 'shots/jersey/out/fadein-v4-mentions.mp4', 21),   # v15: the profile slot starts 20 frames earlier, at 784
    ('profile', 'shots/profile/out/profile-v15-from784.mp4', 118),
]
SMEARED = {'newspaper', 'fastcuts'}
ap = argparse.ArgumentParser()
ap.add_argument('--fps', default='both')
ap.add_argument('--mix', default='audio/mix-final-patel3-5-outro3.wav')
ap.add_argument('--scenes', help='JSON {scene: take} overrides, e.g. upscaled takes')
ap.add_argument('--tag', default='', help='output name prefix, so a candidate never replaces the current reel')
args = ap.parse_args()
if args.scenes:
    swap = json.load(open(os.path.join(R, args.scenes)))
    assert set(swap) <= {s[0] for s in SCENES}, set(swap) - {s[0] for s in SCENES}
    # a value is a take path, or [take, slowed generation] for a scene that has one
    SCENES = [(n, *([swap[n]] if isinstance(swap[n], str) else swap[n][:1]), k, *(swap[n][1:] if isinstance(swap[n], list) else rest))
              if n in swap else (n, t, k, *rest) for n, t, k, *rest in SCENES]
PRE = f'{args.tag}-' if args.tag else ''
OUT = os.path.join(R, 'master', 'out')
WORK = os.path.join(R, 'master', 'work')
os.makedirs(OUT, exist_ok=True)

def frames(path, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(R, path), '-vf', f'scale={W}:{H}:flags=lanczos',
                          '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    assert len(f) == n, (path, len(f), n)
    return f

def cuts(f):
    # A hard cut: the two frames share little structure (low correlation of small grey thumbnails) and differ a lot.
    small = [cv2.resize(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY), (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32) for x in f]
    out = []
    for k in range(len(f) - 1):
        a, b = small[k] - small[k].mean(), small[k + 1] - small[k + 1].mean()
        corr = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
        diff = float(np.abs(small[k] - small[k + 1]).mean())
        if corr < 0.45 and diff > 18:
            out.append(k)
    return out

def encoder(fps, tag):
    path = os.path.join(WORK, f'video-{PRE}{tag}.mp4')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'slow', '-crf', '8', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    return p, path

def rife(f, scene, n_out):
    d = os.path.join(WORK, scene)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d + '/in'); os.makedirs(d + '/out')
    for i, x in enumerate(f):
        cv2.imwrite(f'{d}/in/{i + 1:08d}.png', x, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    subprocess.run([f'{RIFE}/rife-ncnn-vulkan', '-i', d + '/in', '-o', d + '/out', '-m', f'{RIFE}/rife-v4.6', '-n', str(n_out)],
                   check=True, capture_output=True)
    names = sorted(os.listdir(d + '/out'))
    assert len(names) == n_out, (scene, len(names))
    return d, names

def resample(path, scene, n_out):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(R, path), '-vf', f'scale={W}:{H}:flags=lanczos',
                          '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    d, names = rife(np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3), scene, n_out)
    for nm in names:
        yield cv2.imread(f'{d}/out/{nm}')
    shutil.rmtree(d)

def rife2x(f, cut, scene):
    d, names = rife(f, scene, 2 * len(f))
    for j, nm in enumerate(names):
        k = j // 2
        if j % 2 == 1 and (k in cut or k == len(f) - 1):
            yield f[k]  # hold across a hard cut, and on the scene's last frame
        else:
            yield cv2.imread(f'{d}/out/{nm}')
    shutil.rmtree(d)

def finish(video, fps, tag):
    mix = os.path.join(R, args.mix)
    limited = os.path.join(WORK, os.path.basename(args.mix).replace('.wav', '-limited.wav'))
    if not os.path.exists(limited):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mix, '-af',
                        'aresample=192000,alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000', '-c:a', 'pcm_s24le', limited], check=True)
    master = os.path.join(OUT, f'reel-{PRE}{tag}-master.mp4')
    upload = os.path.join(OUT, f'reel-{PRE}{tag}-upload.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', limited, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', master], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', limited, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-preset', 'slow', '-profile:v', 'high', '-level', '4.2', '-b:v', '24M', '-maxrate', '30M', '-bufsize', '60M',
                    '-pix_fmt', 'yuv420p', '-g', str(fps), '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-shortest', '-movflags', '+faststart', upload], check=True)
    print('wrote', master, upload)

os.makedirs(WORK, exist_ok=True)
want = ['30', '60'] if args.fps == 'both' else [args.fps]
encs = {fps: encoder(int(fps), fps) for fps in want}
found = {}
for name, take, n, *slow in SCENES:
    f = frames(take, n)
    # The newspaper and the podcast hype cut inside their own whips and zooms, where both sides are already smeared;
    # holding a frame there stutters the move, so those two interpolate straight through.
    cut = [] if name in SMEARED else cuts(f)
    found[name] = cut
    print(name, n, 'cuts', cut, flush=True)
    if '30' in encs:
        for x in f:
            encs['30'][0].stdin.write(np.ascontiguousarray(x).tobytes())
    if '60' in encs:
        for x in (resample(slow[0], name, 2 * n) if slow else rife2x(f, set(cut), name)):
            encs['60'][0].stdin.write(np.ascontiguousarray(x).tobytes())
json.dump(found, open(os.path.join(OUT, f'{PRE}cuts.json'), 'w'), indent=1)
for fps, (p, path) in encs.items():
    p.stdin.close(); p.wait()
    assert p.returncode == 0
    finish(path, int(fps), fps)
