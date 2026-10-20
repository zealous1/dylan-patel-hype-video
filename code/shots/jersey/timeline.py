"""One continuous jersey timeline across the jersey scene and the profile crossfade.

  uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/jersey/timeline.py      (from R; writes out/timeline.json and out/jersey-timeline.mp4)

Reel frames 763 (25.43 s, where the jersey scene starts) to 856 (where the profile build's jersey opacity reaches
zero) each get a fractional position p in the clean take (out/final-realtime-clean.mp4, frames 0..45):

  u = (n - 763) / 93
  p = 45 * ((1 - C) * (1 - (1 - u) ** A) + C * u),   C = 0.12, A = 2.212

That is real speed at 763 (1.00 take frame per reel frame), an eased deceleration through the scene (0.53 at the
cut, 803 to 804), and a slow glide to 0.06 at 856, where it reaches frame 45 as the jersey disappears. It never
holds and never repeats. A and C are set so the start speed is exactly 1.

Every frame at a fractional position is a real in-between frame from RIFE v4.6 (-0/-1/-s on the two take frames
around it); integer positions are the take frame itself. No frame blending. Output: 94 frames, 1280x720, frame
i is reel frame 763 + i. The jersey scene reads 763..803 of it (through lookmatch and fadein.py); the profile
build reads 804..856.
"""
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
TAKE, OUT = HERE / 'out/final-realtime-clean.mp4', HERE / 'out/jersey-timeline.mp4'
RIFE = Path(os.environ.get('RIFE_DIR', 'rife-ncnn-vulkan'))
N0, N1, LAST, C, A = 763, 856, 45, 0.12, 2.212

def pos(n):
    u = (n - N0) / (N1 - N0)
    return LAST * ((1 - C) * (1 - (1 - u) ** A) + C * u)

tmp = Path(tempfile.mkdtemp(dir=HERE / 'post'))
src = tmp / 'src'; src.mkdir()
subprocess.run(['ffmpeg', '-v', 'error', '-i', str(TAKE), str(src / '%03d.png')], check=True)   # 001.png = frame 0
frame = lambda i: src / f'{i + 1:03d}.png'
rows, outs = [], []
for n in range(N0, N1 + 1):
    p = pos(n); i0 = int(np.floor(p)); t = p - i0
    o = tmp / f'o{n}.png'
    if t < 1e-3 or i0 >= LAST:
        shutil.copy(frame(min(i0, LAST)), o)
    elif t > 1 - 1e-3:
        shutil.copy(frame(i0 + 1), o)
    else:
        subprocess.run([str(RIFE / 'rife-ncnn-vulkan'), '-0', str(frame(i0)), '-1', str(frame(i0 + 1)), '-o', str(o),
                        '-s', f'{t:.4f}', '-m', str(RIFE / 'rife-v4.6')], check=True, capture_output=True)
    speed = pos(n + 1) - p if n < N1 else p - pos(n - 1)
    rows.append({'reel_frame': n, 'take_pos': round(p, 4), 'speed': round(speed, 4)})
    outs.append(o)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '1280x720', '-r', '30', '-i', '-',
                        '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '10', '-pix_fmt', 'yuv420p', str(OUT)], stdin=subprocess.PIPE)
for o in outs: enc.stdin.write(cv2.imread(str(o)).tobytes())
enc.stdin.close(); enc.wait()
shutil.rmtree(tmp)
(HERE / 'out/timeline.json').write_text(json.dumps({'take': TAKE.name, 'formula': 'p = 45*((1-C)*(1-(1-u)**A) + C*u), u = (n-763)/93',
                                                    'C': C, 'A': A, 'frames': rows}, indent=1))
for r in rows[::10] + [rows[40], rows[41], rows[-1]]: print(r)
