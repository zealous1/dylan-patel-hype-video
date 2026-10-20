# Eye and smile landmarks for the hero clip's eye fire (build.py, eye_fire): MediaPipe Face Mesh with iris refinement
# on each of the hero's 91 source frames, decoded as build.py decodes them, then smoothed over time so nothing jitters.
# Writes lab/data/eyes-<src>.json: per source frame, both iris centres and radii, the eye line, the face height (brow
# to chin) and a smile measure (mouth-corner width over face width).
#   uv run --no-project --python 3.12 --with-requirements requirements-matte.txt python -I shots/fastcuts/lab/eyes.py [edl]
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np, cv2
import mediapipe as mp

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
W, H = 1920, 1080
edl = json.load(open(os.path.join(HERE, '..', sys.argv[1] if len(sys.argv) > 1 else 'edl-v16-p2.json')))
c = next(x for x in edl['clips'] if x.get('kind') == 'hero')
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0', '-i', os.path.join(R, edl['sources'][c['src']]['file']), '-frames:v', '91', '-vf',
                      f'fps=30,scale={W}:{H}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

# Face Mesh indices: iris centres 468 and 473 with rims 469 to 472 and 474 to 477; eye corners 33, 133, 362, 263;
# mouth corners 61 and 291; brow top 10, chin 152; cheeks 234 and 454.
# His face is about 200 px tall in the full frame, too small for the mesh's short-range detector, so each frame is
# cropped to a 640 px square around his tracked face (lab/data/faces.json) and scaled up to 768.
mesh = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.3)
track = json.load(open(os.path.join(HERE, 'data', 'faces.json')))[c['src']]['boxes']
CS, UP = 640, 768
rows = []
for i, f in enumerate(frames):
    b = track[min(i, len(track) - 1)]
    x0 = int(min(max(b[0] * W - CS / 2, 0), W - CS)); y0 = int(min(max(b[1] * H - CS / 2, 0), H - CS))
    crop = cv2.resize(f[y0:y0 + CS, x0:x0 + CS], (UP, UP), interpolation=cv2.INTER_CUBIC)
    res = mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    if not res.multi_face_landmarks:
        rows.append(None)
        continue
    p = np.array([[x0 + l.x * CS, y0 + l.y * CS] for l in res.multi_face_landmarks[0].landmark])
    rows.append(np.concatenate([p[468], p[473],
                                [np.mean(np.linalg.norm(p[469:473] - p[468], axis=1)), np.mean(np.linalg.norm(p[474:478] - p[473], axis=1))],
                                p[33], p[263], p[10], p[152], p[61], p[291], p[234], p[454]]))
ok = [i for i, r in enumerate(rows) if r is not None]
assert len(ok) > len(rows) * 0.8, f'face found in {len(ok)} of {len(rows)} frames'
A = np.array([np.interp(range(len(rows)), ok, [rows[i][k] for i in ok]) for k in range(len(rows[ok[0]]))]).T
# Gaussian over time (sigma 1.2 frames): landmark noise is a pixel or two a frame, more than a flame base can hide.
k = np.exp(-0.5 * (np.arange(-4, 5) / 1.2) ** 2); k /= k.sum()
S = np.array([np.convolve(np.pad(A[:, j], 4, mode='edge'), k, 'valid') for j in range(A.shape[1])]).T
out = []
for r in S:
    li, ri, (lr, rr) = r[0:2], r[2:4], r[4:6]
    e0, e1, top, chin, m0, m1, ch0, ch1 = r[6:8], r[8:10], r[10:12], r[12:14], r[14:16], r[16:18], r[18:20], r[20:22]
    out.append({'iris': [[round(float(v), 2) for v in li], [round(float(v), 2) for v in ri]], 'iris_r': [round(float(lr), 2), round(float(rr), 2)],
                'eye_line': [[round(float(v), 2) for v in e0], [round(float(v), 2) for v in e1]],
                'face_h': round(float(np.linalg.norm(chin - top)), 2),
                'smile': round(float(np.linalg.norm(m1 - m0) / np.linalg.norm(ch1 - ch0)), 4)})
json.dump({'src': c['src'], 'found': len(ok), 'frames': out}, open(os.path.join(HERE, 'data', f"eyes-{c['src']}.json"), 'w'))
sm = [o['smile'] for o in out]
print(c['src'], f'face in {len(ok)}/{len(rows)} frames; smile peaks at source frame {int(np.argmax(sm))}', [round(x, 3) for x in sm[::5]])
