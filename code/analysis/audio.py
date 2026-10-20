# Beat grid, onsets and loudness of a reel's mix and its stems, at 0.1 s.
#   uv run --no-project --python 3.12 --with-requirements ../requirements.txt python -I audio.py <mix.wav> <vocals.wav> <music.wav> <out.json>
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json
import sys

import librosa
import numpy as np

mix_path, voc_path, mus_path, out = sys.argv[1:5]
y, sr = librosa.load(mix_path, sr=22050, mono=True)
dur = len(y) / sr
hop = 512

tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, units="time")
onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")
# Strong hits: onsets whose strength is in the top fifth, the moments an edit would cut on.
strength = {round(float(t), 2): float(onset_env[librosa.time_to_frames(t, sr=sr, hop_length=hop)]) for t in onsets}
cut = np.percentile(list(strength.values()), 80)
hits = [t for t, s in strength.items() if s >= cut]


def rms_db(path):
    a, _ = librosa.load(path, sr=22050, mono=True, duration=dur)
    frame = int(sr * 0.1)
    n = len(a) // frame
    r = np.sqrt(np.mean(a[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    return [round(float(v), 1) for v in 20 * np.log10(r)]


mix, voc, mus = rms_db(mix_path), rms_db(voc_path), rms_db(mus_path)
low = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=int(sr * 0.1))[0]
# Sections: where the music's loudness changes by more than 6 dB between 1 s windows (drops, cuts to silence).
sec = [np.mean(mus[i : i + 10]) for i in range(0, len(mus) - 10, 10)]
changes = [{"t": i + 1, "from_db": round(float(sec[i]), 1), "to_db": round(float(sec[i + 1]), 1)}
           for i in range(len(sec) - 1) if abs(sec[i + 1] - sec[i]) > 6]

json.dump({
    "duration": round(dur, 2), "tempo_bpm": round(float(np.atleast_1d(tempo)[0]), 2),
    "beats": [round(float(b), 2) for b in beats], "strong_hits": hits,
    "rms_db_per_100ms": {"mix": mix, "vocals": voc, "music": mus},
    "centroid_hz_per_100ms": [int(c) for c in low],
    "section_changes": changes,
}, open(out, "w"))
print(f"tempo {float(np.atleast_1d(tempo)[0]):.1f} BPM, {len(beats)} beats, {len(hits)} strong hits, changes {changes}")
