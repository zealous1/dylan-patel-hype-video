# What the htdemucs_ft vocal stem holds besides the announcer, and which of it today's bed drops.
# Evidence is by analysis: faster-whisper medium.en words on the stem's mid and side channels, per-0.25 s level,
# stereo correlation and spectral centroid, and the spectrogram written to plots/vocals.png.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/audit/vocals.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, sys
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from faster_whisper import WhisperModel
sys.path.insert(0, os.path.dirname(__file__))
from lib import AUDIT, SR, STEMS, DUR, load

# Today's bed (compose.sh v2, no-announcer-v2.wav): the stem is muted 1.15 to 2.95 and 23.6 to 26.4 with 60 ms
# ramps, and the final render's bed stops dead at 28.978 s.
def current_gain(t):
    g = np.clip((np.abs(t - 2.05) - 0.9) / 0.06, 0, 1) * np.clip((np.abs(t - 25.0) - 1.4) / 0.06, 0, 1)
    return np.where(t >= 28.978, 0, g)

# Ranges and labels come from the measurements this script prints; kind is song, announcer or space.
INVENTORY = [
    ('Held sung note under the intro (F0 near 330 Hz, harmonics to 2 kHz, wide, L/R r 0.5 to 0.8)', 0.0, 4.6, 'song'),
    ('Announcer: "Looking for James, he\'s got it!" (mono, L/R r 1.00)', 1.06, 2.90, 'announcer'),
    ('Vocal chop in the quiet build (-27 dB burst, centred)', 6.0, 6.8, 'song'),
    ('Song lead vocal, sung and rapped ("I wasn\'t born a fool...", "for the show", "I thought you must have had proof...")', 9.75, 21.5, 'song'),
    ('"Hey, hey" ad libs over the hook', 21.5, 23.3, 'song'),
    ('Sung hook notes before the yell (steady partials at about 430, 870 and 1300 Hz)', 23.3, 23.95, 'song'),
    ('Announcer yell: "LeBron! LeBron! He\'s doing it again!"', 23.95, 26.0, 'announcer'),
    ('Sung hook continuing under the yell', 23.95, 26.0, 'song'),
    ('Song vocal after the yell (harmonic stack from 26.3 s)', 26.0, 26.9, 'song'),
    ('Rap: "I heard that he died..."', 26.9, 29.6, 'song'),
    ('Stereo side of the stem inside the intro mute (the note\'s width and reverb; no words in it at +18 dB)', 1.06, 3.01, 'space'),
    ('Stereo side of the stem inside the outro mute (hook width and reverb; no words in it at +18 dB)', 23.54, 26.46, 'space'),
]


def words(model, x, a, b, gain=1.0):
    seg = (x[int(a * 16000):int(b * 16000)] * gain).astype(np.float32)
    segs, _ = model.transcribe(seg, word_timestamps=True, vad_filter=False, condition_on_previous_text=False, temperature=0)
    return [(w.word.strip(), round(a + w.start, 2), round(a + w.end, 2), round(w.probability, 2)) for s in segs for w in s.words]


def main():
    v = load(f'{STEMS}/vocals.wav')
    song = load(f'{AUDIT}/work/vocals-song.wav')
    mid, side = v.mean(1), (v[:, 0] - v[:, 1]) / 2
    to16 = lambda x: signal.resample_poly(x, 1, 3)
    model = WhisperModel('medium.en', device='cpu', compute_type='int8')
    asr = {'mid': [], 'side': [], 'song_only': []}
    for a in np.arange(0, 27.5, 2.0):
        asr['mid'] += [{'window': [float(a), float(min(DUR, a + 3.5))], 'words': words(model, to16(mid), a, min(DUR, a + 3.5))}]
    for a, b in [(0.5, 3.5), (23.0, 26.6)]:
        asr['side'] += [{'window': [a, b], 'words': words(model, to16(side), a, b, gain=8.0)}]
        asr['song_only'] += [{'window': [a, b], 'words': words(model, to16(song.mean(1)), a, b)}]

    h = SR // 4
    feats = []
    for i in range(0, len(v) - h + 1, h):
        L, Rr = v[i:i + h, 0], v[i:i + h, 1]
        f, P = signal.welch(mid[i:i + h], SR, nperseg=2048)
        feats.append({'t': i / SR, 'mid_db': 10 * np.log10(np.mean(mid[i:i + h] ** 2) + 1e-20),
                      'side_db': 10 * np.log10(np.mean(side[i:i + h] ** 2) + 1e-20),
                      'r': float(np.sum(L * Rr) / np.sqrt(np.sum(L * L) * np.sum(Rr * Rr) + 1e-30)),
                      'centroid_hz': float(np.sum(f * P) / (np.sum(P) + 1e-30))})

    t = np.arange(len(v)) / SR
    gcur = current_gain(t)
    inv = []
    for label, a, b, kind in INVENTORY:
        k = (t >= a) & (t < b)
        muted = float(np.mean(1 - gcur[k]))
        inv.append({'label': label, 'start': a, 'end': b, 'kind': kind, 'muted_today': round(muted, 2)})
    json.dump({'asr': asr, 'features': feats, 'inventory': inv}, open(f'{AUDIT}/vocals.json', 'w'), indent=1)
    for row in inv:
        print(f"{row['start']:5.2f}-{row['end']:5.2f} {row['kind']:9s} muted today {row['muted_today']:.0%}  {row['label']}")
    for name, rows in asr.items():
        for r in rows:
            print(name, r['window'], ' '.join(f'{w[0]}@{w[1]}' for w in r['words'])[:200])

    os.makedirs(f'{AUDIT}/plots', exist_ok=True)
    fig, ax = plt.subplots(3, 1, figsize=(16, 9.5), sharex=True, facecolor='#fcfcfb')
    for a_, x, title in [(ax[0], mid, 'Vocal stem, mid channel'), (ax[1], song.mean(1), 'Song-only vocal stem after restore.py (the announcer\'s words taken out)')]:
        f, tt, Z = signal.stft(x, SR, nperseg=2048, noverlap=2048 - 512)
        a_.pcolormesh(tt, f, 20 * np.log10(np.abs(Z) + 1e-9), vmin=-105, vmax=-35, shading='auto', cmap='magma', rasterized=True)
        a_.set_yscale('symlog', linthresh=500); a_.set_ylim(80, 12000); a_.set_ylabel('Hz'); a_.set_title(title, loc='left', fontsize=10)
    colors = {'song': '#1baf7a', 'announcer': '#e34948', 'space': '#6250d6'}
    lanes = {}
    for row in inv:
        lane = lanes.setdefault(row['kind'], len(lanes))
        ax[2].barh(lane, row['end'] - row['start'], left=row['start'], height=0.6, color=colors[row['kind']], alpha=0.85)
    ax[2].fill_between(t[::480], 2.6, 2.6 + (1 - gcur[::480]) * 0.6, color='#52514e', step='mid')
    ax[2].set_yticks([0, 1, 2, 2.9]); ax[2].set_yticklabels(['song vocal', 'announcer', 'stereo side', 'muted today'])
    ax[2].set_xlabel('seconds'); ax[2].set_xlim(0, DUR); ax[2].set_ylim(-0.5, 3.4)
    for a_ in ax:
        a_.set_facecolor('#fcfcfb')
        for s in ['top', 'right']:
            a_.spines[s].set_visible(False)
    plt.tight_layout(); plt.savefig(f'{AUDIT}/plots/vocals.png', dpi=110)


if __name__ == '__main__':
    main()
