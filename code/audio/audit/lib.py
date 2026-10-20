# Shared IO, loudness (ITU-R BS.1770-4 / EBU R128) and per-second measurements for the audio audit.
# Everything runs at 48 kHz in float64; ffmpeg only decodes and writes.
import os, subprocess
import numpy as np
from scipy import signal

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AUDIT = os.path.join(R, 'audio', 'audit')
SR = 48000
DUR = 30.07
STEMS = f'{R}/stems/htdemucs_ft/audio'

SECTIONS = {  # loop ranges on the page and the per-section rows in the table
    'intro line': (0.9, 3.2),
    'newspaper': (12.0, 13.833),   # scene frames 360 to 415
    'outro': (22.8, 26.6),
    'end': (28.4, 30.07),
}
BANDS = [('sub', 20, 60), ('low', 60, 250), ('low-mid', 250, 500), ('mid', 500, 2000), ('presence', 2000, 6000), ('air', 6000, 20000)]


def load(path, sr=SR):
    native = int(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate',
                                 '-of', 'csv=p=0', path], capture_output=True, text=True, check=True).stdout.split()[0])
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0', '-f', 'f64le', '-ac', '2', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float64).reshape(-1, 2)
    if native != sr:
        g = np.gcd(native, sr)
        x = signal.resample_poly(x, sr // g, native // g, axis=0)
    n = int(round(DUR * sr))
    return np.pad(x, ((0, max(0, n - len(x))), (0, 0)))[:n].copy()


def save(path, x, sr=SR, codec='pcm_f32le'):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f64le', '-ar', str(sr), '-ac', '2', '-i', '-', '-c:a', codec, path],
                   input=np.ascontiguousarray(x, np.float64).tobytes(), check=True)


def kweight(x):
    # BS.1770 stage 1 (head shelf) and stage 2 (RLB high-pass), 48 kHz coefficients
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def _blocks(power, win, hop):
    c = np.concatenate([[0], np.cumsum(power)])
    starts = np.arange(0, len(power) - win + 1, hop)
    return (c[starts + win] - c[starts]) / win, starts


def lufs_of(ms):
    return -0.691 + 10 * np.log10(np.maximum(ms, 1e-20))


def loudness(x):
    p = (kweight(x) ** 2).sum(1)
    hop = SR // 10
    mom, s0 = _blocks(p, int(0.4 * SR), hop)
    st, s1 = _blocks(p, 3 * SR, hop)
    # Integrated: 400 ms blocks at 75 % overlap, absolute gate -70, relative gate -10 LU.
    blk, _ = _blocks(p, int(0.4 * SR), int(0.1 * SR))
    g = blk[lufs_of(blk) > -70]
    integrated = lufs_of(g[lufs_of(g) > lufs_of(g.mean()) - 10].mean())
    sg = st[lufs_of(st) > -70]
    sg = lufs_of(sg[lufs_of(sg) > lufs_of(sg.mean()) - 20])
    lra = np.percentile(sg, 95) - np.percentile(sg, 10)
    return {'integrated': integrated, 'lra': lra,
            'm_t': (s0 + 0.4 * SR) / SR, 'm': lufs_of(mom),
            's_t': (s1 + 3 * SR) / SR, 's': lufs_of(st)}


def lufs_span(x, a, b):
    """Gated loudness of one span, for comparing a voice with what sits under it."""
    p = (kweight(x[int(a * SR):int(b * SR)]) ** 2).sum(1)
    blk, _ = _blocks(p, int(0.4 * SR), int(0.1 * SR))
    if not len(blk):
        return lufs_of(p.mean())
    g = blk[lufs_of(blk) > -70]
    if not len(g):
        return -70.0
    return lufs_of(g[lufs_of(g) > lufs_of(g.mean()) - 10].mean())


def true_peak(x):
    return 20 * np.log10(np.abs(signal.resample_poly(x, 4, 1, axis=0)).max() + 1e-20)


def per_second_rms(x):
    n = int(DUR)
    return np.array([10 * np.log10(np.mean(x[i * SR:(i + 1) * SR] ** 2) + 1e-9) for i in range(n)])  # floor -90 dBFS


def bands_per_second(x):
    """Linear energy per band per second, from a 4096-point STFT of the mid signal. Kept linear so a span's
    balance is the ratio of summed energies, which one silent second cannot swamp."""
    f, t, Z = signal.stft(x.mean(1), SR, nperseg=4096, noverlap=4096 - 1024)
    P = np.abs(Z) ** 2
    out = np.zeros((len(BANDS), int(DUR)))
    for k, (_, lo, hi) in enumerate(BANDS):
        e = P[(f >= lo) & (f < hi)].sum(0)
        for s in range(int(DUR)):
            out[k, s] = e[(t >= s) & (t < s + 1)].mean()
    return out


def db(e):
    return 10 * np.log10(e + 1e-12)


def stereo(x, hop=0.25):
    h = int(hop * SR)
    r, w, t = [], [], []
    for i in range(0, len(x) - h + 1, h):
        L, Rr = x[i:i + h, 0], x[i:i + h, 1]
        m, s = (L + Rr) / 2, (L - Rr) / 2
        em, es = np.mean(m ** 2), np.mean(s ** 2)
        if em < 1e-9:
            r.append(np.nan); w.append(np.nan)
        else:
            r.append(np.sum(L * Rr) / np.sqrt(np.sum(L * L) * np.sum(Rr * Rr) + 1e-30))
            w.append(10 * np.log10(es / em + 1e-12))
        t.append((i + h / 2) / SR)
    return np.array(t), np.array(r), np.array(w)


def ltas(x, smooth_oct=1 / 3, fmin=60, fmax=16000, n=96):
    """Long-term average spectrum on a log grid, smoothed to 1/3 octave, in dB."""
    f, P = signal.welch(x if x.ndim == 1 else x.mean(1), SR, nperseg=4096)
    grid = np.geomspace(fmin, fmax, n)
    out = []
    for g in grid:
        k = (f >= g * 2 ** (-smooth_oct / 2)) & (f < g * 2 ** (smooth_oct / 2))
        out.append(10 * np.log10(P[k].mean() + 1e-30))
    return grid, np.array(out)
