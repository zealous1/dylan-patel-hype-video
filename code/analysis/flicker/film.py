# Old-film signals in the original's end: black floor, gate weave (frame shift on the static end card), vertical
# scratches (columns far brighter or darker than their neighbours), dust (small isolated specks), and logo tint drift.
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, subprocess, numpy as np, cv2
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
W, H = 1920, 1080
def grab(t0, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', f'{R}/src/clip.mp4', '-frames:v', str(n), '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
for name, t0, n in [('jersey', 25.6, 18), ('end', 25.9, 110)]:
    f = grab(t0, n); g = [cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32) for x in f]
    floor = [float(np.percentile(y, 2)) for y in g]
    shifts = [cv2.phaseCorrelate(g[k], g[k + 1])[0] for k in range(len(g) - 1)]
    scr, dust = [], []
    for y in g:
        col = y[100:-100].mean(0); smooth = cv2.blur(col.reshape(1, -1), (31, 1)).ravel()
        scr.append(int((np.abs(col - smooth) > 6).sum()))
        med = cv2.medianBlur(y.astype(np.uint8), 7).astype(np.float32)
        d = (np.abs(y - med) > 60).astype(np.uint8); dust.append(cv2.connectedComponents(d)[0] - 1)
    sw = f[:, 380:520, 1050:1700].reshape(len(f), -1, 3).astype(np.float32)  # swoosh area
    print(name, 'black floor p2 median', np.median(floor), 'range', min(floor), max(floor))
    print(' weave px dx', np.round(np.std([s[0] for s in shifts]), 2), 'dy', np.round(np.std([s[1] for s in shifts]), 2), 'max', np.round(np.max(np.abs(shifts)), 2))
    print(' scratch columns/frame', scr[:40])
    print(' dust specks/frame', dust[:40])
    if name == 'end':
        m = sw.mean(1); print(' swoosh BGR first/mid/last', m[5].round(), m[50].round(), m[100].round())
