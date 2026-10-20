# Runs inside the Modal container, in a Practical-RIFE checkout whose train_log/ holds one model version.
#   python prife_worker.py <frames.u8> <n> <jobs.json> <out.u8> <scale>
# jobs.json is a list of [i, t]: the frame between input i and i + 1 at time t.
import json, sys
import numpy as np, torch
import torch.nn.functional as F

sys.path.insert(0, '.')
from train_log.RIFE_HDv3 import Model

W, H = 1920, 1080
src, n, jobs, dst, scale = sys.argv[1], int(sys.argv[2]), json.load(open(sys.argv[3])), sys.argv[4], float(sys.argv[5])
f = np.memmap(src, np.uint8, 'r', shape=(n, H, W, 3))
torch.set_grad_enabled(False)
torch.backends.cudnn.benchmark = True
model = Model()
model.load_model('train_log', -1)
model.eval()
model.device()
pad = max(128, int(128 / scale))
ph, pw = (H - 1) // pad * pad + pad, (W - 1) // pad * pad + pad


def tensor(x):
    t = torch.from_numpy(np.ascontiguousarray(x[..., ::-1])).cuda().permute(2, 0, 1)[None].float() / 255
    return F.pad(t, (0, pw - W, 0, ph - H))


out = np.memmap(dst, np.uint8, 'w+', shape=(len(jobs), H, W, 3))
for j, (i, t) in enumerate(jobs):
    y = model.inference(tensor(f[i]), tensor(f[i + 1]), t, scale)
    out[j] = (y[0, :, :H, :W].clamp(0, 1) * 255).round().byte().permute(1, 2, 0).cpu().numpy()[..., ::-1]
out.flush()
