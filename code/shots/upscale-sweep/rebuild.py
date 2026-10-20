# Rebuilds the soft scenes' takes from upscaled generations by re-running each shot's own steps with the source
# swapped. The sped-up takes are re-cut with the exact frame picks trace.py found in the old takes (picks/*.json),
# then each shot's post.sh step runs with the same arguments, reusing the approved take's per-frame blur picks
# (lookmatch --blur-from) so the whips and zoom blurs stay as they were. Nothing an existing take path names is overwritten.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/upscale-sweep/rebuild.py --tag sr \
#     --src rim=shots/upscale-sweep/out/rim-B.mp4,celebrate=...,fadeout=...,alleyoop=... [--root shots/upscale-sweep/takes/B]
# Default root writes beside the old takes, e.g. shots/rim/out/look-v1-sr.mp4.
import argparse, json, os, subprocess
import numpy as np, cv2

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.join(R, 'shots', 'upscale-sweep')
W, H = 1920, 1080
LOOK = ['uv', 'run', '--no-project', '--python', '3.12', '--with-requirements', os.path.join(R, 'requirements.txt'), 'python', '-I', 'shots/lookmatch.py']

def read(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True, cwd=R).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def write(frames, path):
    os.makedirs(os.path.dirname(os.path.join(R, path)), exist_ok=True)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                          '-c:v', 'libx264', '-preset', 'slow', '-crf', '10', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE, cwd=R)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0, path

def recut(gen, pickfile, n_gen, path):
    # The generation's frames at these indices; no pickfile keeps them all.
    assert len(gen) == n_gen, (path, len(gen), n_gen)
    picks = json.load(open(os.path.join(HERE, 'picks', pickfile)))['picks'] if pickfile else list(range(n_gen))
    write(gen[picks], path)
    return len(picks)

def run(cmd):
    subprocess.run(cmd, check=True, cwd=R)

def frames(path):
    return int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                               '-of', 'csv=p=0', path], capture_output=True, text=True, check=True, cwd=R).stdout)

ap = argparse.ArgumentParser()
ap.add_argument('--tag', required=True)
ap.add_argument('--src', required=True, help='shot=path,... upscaled generations')
ap.add_argument('--root', default='', help='write everything under this folder instead of beside the old takes')
a = ap.parse_args()
src = dict(kv.split('=') for kv in a.src.split(','))
t = a.tag
# Where each output goes: beside the old take (shots/<shot>/<sub>/<name>-<tag>.mp4) or flat under --root.
out = lambda shot, sub, name: os.path.join(a.root, f'{shot}-{name}.mp4') if a.root else f'shots/{shot}/{sub}/{name}-{t}.mp4'
rep = lambda shot, name: os.path.join(a.root, f'{shot}-{name}.json') if a.root else f'shots/{shot}/post/{name}-{t}.json'
made = {}

if 'rim' in src:  # shots/rim/post.sh
    take = out('rim', 'out', 'final-realtime')
    recut(read(src['rim']), 'rim.json', 90, take)
    made['rim'] = out('rim', 'out', 'look-v1')
    run(LOOK + ['--start', '10.00', '--end', '10.80', '--size', '1920x1080', '--trim', '0:0.70', '--take', take,
                '--out', made['rim'], '--report', rep('rim', 'look'), '--blur-from', 'shots/rim/post/look.json'])

if 'celebrate' in src:  # shots/celebrate/post-look.sh
    take = out('celebrate', 'out', 'min-realtime')
    recut(read(src['celebrate']), 'celebrate.json', 90, take)
    made['celebrate'] = out('celebrate', 'out', 'look-v1')
    run(LOOK + ['--start', '10.80', '--end', '12.00', '--size', '1920x1080', '--take', take,
                '--out', made['celebrate'], '--report', rep('celebrate', 'look'), '--blur-from', 'shots/celebrate/post/look.json'])

if 'fadeout' in src:  # shots/fadeout/post.sh, the head and then the v3 block
    gen = out('fadeout', 'out', 'wan-3.0-noframes-slow-focus')
    assert recut(read(src['fadeout']), None, 90, gen) == 90
    head = out('fadeout', 'post', 'head')
    run(LOOK + ['--start', '23.17', '--end', '24.17', '--size', '1920x1080', '--take', gen,
                '--out', head, '--report', rep('fadeout', 'look'), '--blur-from', 'shots/fadeout/post/look.json'])
    made['fadeout'] = out('fadeout', 'out', 'splice-v3')
    run(['ffmpeg', '-v', 'error', '-y', '-i', head, '-ss', '24.1033', '-i', 'src/clip.mp4', '-filter_complex',
         '[0:v]fps=30,trim=end_frame=28,format=yuv420p,setsar=1[a];[1:v]fps=30,scale=1920:1080,format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1[v]',
         '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-frames:v', '68', made['fadeout']])

if 'backdown' in src:  # shots/backdown/post.sh
    take = out('backdown', 'out', 'focus-realtime')
    recut(read(src['backdown']), 'backdown.json', 150, take)
    made['backdown'] = out('backdown', 'out', 'look-v1')
    run(LOOK + ['--start', '6.27', '--end', '8.57', '--size', '1920x1080', '--take', take,
                '--out', made['backdown'], '--report', rep('backdown', 'look'), '--blur-from', 'shots/backdown/post/look.json'])

if 'fadeaway' in src:  # shots/fadeaway/post.sh; wafer.py reads the old post/look.json for its grade, a near match
    take = out('fadeaway', 'out', 'final-realtime')
    recut(read(src['fadeaway']), 'fadeaway.json', 90, take)
    look = out('fadeaway', 'post', 'look')
    run(LOOK + ['--start', '8.57', '--end', '10.00', '--size', '1920x1080', '--take', take,
                '--out', look, '--report', rep('fadeaway', 'look'), '--blur-from', 'shots/fadeaway/post/look.json'])
    made['fadeaway'] = out('fadeaway', 'out', 'wafer-v1')
    run(['uv', 'run', '--no-project', '--python', '3.12', '--with-requirements', os.path.join(R, 'requirements.txt'), 'python', '-I',
         'shots/fadeaway/wafer.py', look, made['fadeaway'], rep('fadeaway', 'track')])

if 'alleyoop' in src:  # the take is the generation's frame picks as they are; the slowed generation feeds the 60 fps cut
    # No look-match follows here, so the upscale's colour is matched to the 720p generation in the low frequencies
    # only (the added detail stays). It is matched as read back after encoding, since ffmpeg's rgb24 to yuv420p
    # path alone lowers every channel by about 1.5 levels.
    ref = read('shots/alleyoop/out/wan-3.0-noframes-slow-focus-2.mp4')
    shift = lambda a, b: np.stack([np.clip(x + cv2.GaussianBlur(r.astype(np.float32) - y, (0, 0), 16) + 0.5, 0, 255).astype(np.uint8)
                                   for x, r, y in zip(a, ref, b)])
    gen = read(src['alleyoop'])
    gen = shift(gen, gen)
    probe = out('alleyoop', 'out', 'colour-probe')
    write(gen, probe)
    gen = shift(gen, read(probe))
    os.remove(os.path.join(R, probe))
    made['alleyoop'] = out('alleyoop', 'out', 'final-realtime')
    recut(gen, 'alleyoop.json', 150, made['alleyoop'])
    made['alleyoop-slow'] = out('alleyoop', 'out', 'wan-3.0-noframes-slow-focus-2')
    recut(gen, None, 150, made['alleyoop-slow'])

for k, p in made.items():
    print(k, p, frames(p), 'frames')
