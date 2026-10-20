# Jersey (slot 25.43 to 26.80 s): the original fades its jersey shot in from 25.43, under the end of the fade out.
# Our look-matched jersey take is retimed to fill the earlier slot and scaled frame by frame by the original's own
# brightness ramp over those first frames, so it fades in exactly where and how the original's does.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/jersey/fadein.py [tag]   (from R; tag v1 by default, v2 reads look-v2)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import subprocess, sys, cv2, numpy as np
TAG = sys.argv[1] if len(sys.argv) > 1 else 'v1'
T0, T1, FPS = 25.43, 26.80, 30
n = round((T1 - T0) * FPS)
def read(p):
    c = cv2.VideoCapture(p); fs = []
    while True:
        ok, f = c.read()
        if not ok: return fs
        fs.append(f)
take = read(f'shots/jersey/out/look-{TAG}.mp4')
src = read('src/clip.mp4')
i0 = round(T0 * FPS)
luma = lambda f: cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean()
ref = luma(src[round(25.70 * FPS)])
w = cv2.VideoWriter('shots/jersey/out/fade.tmp.mp4', cv2.VideoWriter_fourcc(*'mp4v'), FPS, (1920, 1080))
for k in range(n):
    f = cv2.resize(take[min(len(take) - 1, int(k * len(take) / n))], (1920, 1080))
    o = src[i0 + k]
    g = min(1.0, luma(o) / ref) if (i0 + k) < round(25.70 * FPS) else 1.0
    w.write(np.clip(f.astype(np.float32) * g, 0, 255).astype(np.uint8))
    if k < 10: print(k, round(T0 + k / FPS, 3), round(g, 3))
w.release()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'shots/jersey/out/fade.tmp.mp4', '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', f'shots/jersey/out/fadein-{TAG}.mp4'], check=True)
subprocess.run(['rm', 'shots/jersey/out/fade.tmp.mp4'])
