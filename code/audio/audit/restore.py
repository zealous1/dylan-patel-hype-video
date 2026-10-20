# Splits the htdemucs_ft vocal stem into the song's own vocal content and the two announcer lines, so the bed can
# lose only the announcer's words.
#
# Two facts from vocals.py make this possible. The announcer is a mono broadcast feed (L/R correlation 1.00 inside
# both lines), so the stem's side channel holds none of it: Whisper hears no words in the side even at +18 dB. And
# the song content under the announcer (a held sung note under the intro, the sung hook under the outro) repeats
# its own timbre just before and after each line, so a non-negative matrix factorisation (NMF) dictionary learned
# there can pull it back out of the mid channel while the announcer lands in the free components.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/audit/restore.py   writes work/vocals-*.wav
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import os, sys
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(__file__))
from lib import SR, STEMS, AUDIT, load, save

# Announcer word spans in the vocal stem (s), from faster-whisper medium.en word times on the stem's mid channel,
# widened to the onset and the last decay seen in the spectrogram. The current bed mutes 1.15 to 2.95 and 23.6 to 26.4.
LINES = {
    'intro': {'gate': (1.06, 2.90), 'train': [(0.15, 1.05), (2.92, 4.6)]},
    'outro': {'gate': (23.95, 26.0), 'train': [(21.0, 23.95), (26.0, 28.4)]},
}
RAMP = 0.03
NFFT, HOP = 4096, 512
K_SONG, K_FREE = 24, 24


def gate_curve(n, spans, ramp=RAMP):
    """1 inside any span, 0 outside, with linear ramps of `ramp` seconds just outside each span."""
    t = np.arange(n) / SR
    g = np.zeros(n)
    for a, b in spans:
        g = np.maximum(g, np.clip(1 - np.maximum(a - t, t - b) / ramp, 0, 1))
    return g


def nmf_kl(V, W=None, H=None, k=None, fixed_w=0, iters=300, seed=0):
    """KL-divergence NMF with multiplicative updates; the first `fixed_w` columns of W stay as given."""
    rng = np.random.default_rng(seed)
    F, T = V.shape
    if W is None:
        W = rng.random((F, k)) + 1e-3
    if H is None:
        H = rng.random((W.shape[1], T)) + 1e-3
    ones = np.ones_like(V)
    for _ in range(iters):
        WH = W @ H + 1e-12
        H *= (W.T @ (V / WH)) / (W.T @ ones + 1e-12)
        WH = W @ H + 1e-12
        Wn = W * ((V / WH) @ H.T) / (ones @ H.T + 1e-12)
        W[:, fixed_w:] = Wn[:, fixed_w:]
        W /= W.sum(0, keepdims=True) + 1e-12
    return W, H


def split_line(mid, gate, train):
    """Returns (song, announcer) estimates of `mid` over the whole timeline; both are zero outside the line's window."""
    f, t, Z = signal.stft(mid, SR, nperseg=NFFT, noverlap=NFFT - HOP)
    V = np.abs(Z)
    tr = np.zeros(len(t), bool)
    for a, b in train:
        tr |= (t >= a) & (t < b)
    win = (t >= gate[0] - 0.3) & (t <= gate[1] + 0.3)
    Ws, _ = nmf_kl(V[:, tr], k=K_SONG, iters=400)
    rng = np.random.default_rng(1)
    W = np.hstack([Ws, rng.random((len(f), K_FREE)) + 1e-3])
    W, H = nmf_kl(V[:, win], W=W, fixed_w=K_SONG, iters=400)
    S = Ws @ H[:K_SONG]
    A = W[:, K_SONG:] @ H[K_SONG:]
    mask = S ** 2 / (S ** 2 + A ** 2 + 1e-20)
    Zs = np.zeros_like(Z)
    Zs[:, win] = Z[:, win] * mask
    Za = np.zeros_like(Z)
    Za[:, win] = Z[:, win] * (1 - mask)
    song = signal.istft(Zs, SR, nperseg=NFFT, noverlap=NFFT - HOP)[1][:len(mid)]
    ann = signal.istft(Za, SR, nperseg=NFFT, noverlap=NFFT - HOP)[1][:len(mid)]
    return np.pad(song, (0, len(mid) - len(song))), np.pad(ann, (0, len(mid) - len(ann)))


def restore(vocals):
    """vocals [n,2] -> (song-only vocal stem, announcer-only stem, gate curve). The gate is 1 on the announcer's words."""
    n = len(vocals)
    mid, side = vocals.mean(1), (vocals[:, 0] - vocals[:, 1]) / 2
    g = gate_curve(n, [v['gate'] for v in LINES.values()])
    song_mid = mid * (1 - g)
    ann_mid = np.zeros(n)
    for name, v in LINES.items():
        gl = gate_curve(n, [v['gate']])
        s, a = split_line(mid, v['gate'], v['train'])
        song_mid += s * gl
        ann_mid += mid * gl - s * gl
    song = np.stack([song_mid + side, song_mid - side], 1)
    ann = np.stack([ann_mid, ann_mid], 1)
    return song, ann, g


if __name__ == '__main__':
    os.makedirs(f'{AUDIT}/work', exist_ok=True)
    v = load(f'{STEMS}/vocals.wav')
    song, ann, g = restore(v)
    save(f'{AUDIT}/work/vocals-song.wav', song)
    save(f'{AUDIT}/work/vocals-announcer.wav', ann)
    np.save(f'{AUDIT}/work/announcer-gate.npy', g)
    print('song-only and announcer-only vocal stems written')
