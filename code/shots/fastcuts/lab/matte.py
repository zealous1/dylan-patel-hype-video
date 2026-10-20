# Person mattes for the podcast lab's treatments: MediaPipe selfie segmentation on each B clip's source frames,
# the same frames build.py decodes, kept to the person whose region holds Dylan's tracked face (a guest or host
# beside him is dropped). Writes lab/data/matte/<src>.npy, uint8 (frames, 270, 480), in source-frame coordinates.
#   uv run --no-project --python 3.12 --with-requirements requirements-matte.txt python -I shots/fastcuts/lab/matte.py [edl]
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np, cv2
import mediapipe as mp

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
W, H, MW, MH = 1920, 1080, 480, 270
edl = json.load(open(os.path.join(HERE, '..', sys.argv[1] if len(sys.argv) > 1 else 'edl-v15b.json')))
tracks = json.load(open(os.path.join(HERE, 'data', 'faces.json')))
os.makedirs(os.path.join(HERE, 'data', 'matte'), exist_ok=True)

def decode(path, t, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', str(n), '-vf', f'fps=30,scale={W}:{H}:flags=lanczos',
                          '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    return np.concatenate([fr, np.repeat(fr[-1:], n - len(fr), 0)]) if len(fr) < n else fr

seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
for c in edl['clips']:
    if c.get('kind') == 'jensen-zoom':
        continue
    s = edl['sources'][c['src']]
    if c.get('kind') == 'hero':
        fr = decode(os.path.join(R, s['file']), 0, 91)
    else:
        fr = decode(os.path.join(R, s['file']), c['src_in'], round(c['slot_out'] * 30) - round(c['slot_in'] * 30))
    boxes = tracks[c['src']]['boxes']
    raw = np.array([seg.process(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).segmentation_mask for f in fr], np.float32)
    raw = np.array([cv2.resize(m, (MW, MH), interpolation=cv2.INTER_AREA) for m in raw])
    # Three-frame mean: the model's edge flickers frame to frame.
    sm = np.array([raw[max(i - 1, 0):i + 2].mean(0) for i in range(len(raw))])
    out, kept = [], []
    for i, m in enumerate(sm):
        b = boxes[min(i, len(boxes) - 1)]
        n, lab = cv2.connectedComponents((m > 0.5).astype(np.uint8))
        fx, fy = int(b[0] * MW), int(min(b[1] + b[3] * 0.3, 0.99) * MH)  # his chin, inside the person even if the box sits high
        win = lab[max(fy - 6, 0):fy + 6, max(fx - 6, 0):fx + 6]
        ids = set(np.unique(win[win > 0]).tolist())
        keep = np.isin(lab, list(ids)) if ids else np.zeros_like(m, bool)
        keep = cv2.dilate(keep.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        out.append(np.clip(m * keep * 255, 0, 255).astype(np.uint8))
        kept.append(float((m > 0.5).sum() and (keep & (m > 0.5)).sum() / (m > 0.5).sum()))
    np.save(os.path.join(HERE, 'data', 'matte', f"{c['src']}.npy"), np.array(out))
    print(c['src'], len(out), 'frames, person area', round(float((np.array(out) > 127).mean()), 3), 'kept of all people', round(float(np.mean(kept)), 2))
