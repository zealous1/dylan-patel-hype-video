# Measures the original, today's mix and every candidate with the same rulers, and writes the plots and data.js
# that index.html reads.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/audit/measure.py
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
sys.path.insert(0, os.path.dirname(__file__))
from lib import R, AUDIT, SR, DUR, SECTIONS, BANDS, db, load, loudness, lufs_span, true_peak, per_second_rms, bands_per_second, stereo, ltas
from build import SPANS

# id, label, limited file (what plays), unlimited mix (for voice-to-music), voice tracks in that mix
MIXES = [
    ('original', 'Original LeBron edit', 'src/clip.mp4', None, None),
    ('current', 'Current final', 'master/work/mix-final-patel3-5-outro3-limited.wav', 'audio/mix-final-patel3-5-outro3.wav',
     ('audio/audit/work/voice-intro-current.wav', 'audio/audit/work/voice-outro-current.wav')),
    ('a-full-bed', 'A. Full bed', 'audio/audit/out/a-full-bed.wav', 'audio/audit/out/a-full-bed-mix.wav',
     ('audio/audit/work/voice-intro-current.wav', 'audio/audit/work/voice-outro-current.wav')),
    ('b-matched-voices', 'B. A + matched voices', 'audio/audit/out/b-matched-voices.wav', 'audio/audit/out/b-matched-voices-mix.wav',
     ('audio/audit/work/voice-intro-matched.wav', 'audio/audit/work/voice-outro-matched.wav')),
    ('c-matched-master', 'C. B + matched master', 'audio/audit/out/c-matched-master.wav', 'audio/audit/out/c-matched-master-mix.wav',
     ('audio/audit/work/voice-intro-matched.wav', 'audio/audit/work/voice-outro-matched.wav')),
    ('d-hotter-voices', 'D. C with voices +2 dB', 'audio/audit/out/d-hotter-voices.wav', 'audio/audit/out/d-hotter-voices-mix.wav',
     ('audio/audit/work/voice-intro-matched.wav', 'audio/audit/work/voice-outro-matched.wav')),
]
VOICE_GAIN = {'d-hotter-voices': 10 ** (2 / 20)}
PLOTTED = ['original', 'current', 'c-matched-master']
INK, INK2, SURFACE, GRID = '#0b0b0b', '#52514e', '#fcfcfb', '#e4e3df'
COLOR = {'original': '#2a78d6', 'current': '#eb6834', 'a-full-bed': '#6250d6', 'b-matched-voices': '#eda100',
         'c-matched-master': '#1baf7a', 'd-hotter-voices': '#e87ba4', 'announcer': '#2a78d6'}
P = f'{AUDIT}/plots'


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def shade(ax, label=True):
    for name, (a, b) in SECTIONS.items():
        ax.axvspan(a, b, color='#f0efec', zorder=0)
        if label:
            ax.text((a + b) / 2, 1.0, name, transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=8, color=INK2)


def envelope_range(x, a, b):
    """90th minus 10th percentile of the 20 ms 300 Hz to 5 kHz envelope over a line, in dB: how choppy it is."""
    bb, aa = signal.butter(4, [300, 5000], 'bandpass', fs=SR)
    y = signal.lfilter(bb, aa, x.mean(1))[int(a * SR):int(b * SR)]
    h = int(0.02 * SR)
    e = np.array([10 * np.log10(np.mean(y[i:i + h] ** 2) + 1e-20) for i in range(0, len(y) - h, h)])
    e = e[e > e.max() - 40]
    return float(np.percentile(e, 90) - np.percentile(e, 10)), e


def main():
    os.makedirs(P, exist_ok=True)
    sig = {m[0]: load(f'{R}/{m[2]}') for m in MIXES}
    video_aac = load(f'{R}/master/out/final-worn-30-master.mp4')
    ann = load(f'{AUDIT}/work/vocals-announcer.wav')
    o = sig['original']
    res = {}
    for mid, label, path, mixp, voices in MIXES:
        x = sig[mid]
        L = loudness(x)
        rms = per_second_rms(x)
        bands = bands_per_second(x)
        st_t, r, w = stereo(x)
        res[mid] = {'label': label, 'path': path, 'L': L, 'tp': true_peak(x), 'rms': rms, 'bands': bands, 'r': r, 'w': w, 'st_t': st_t}
    ref = res['original']
    rows = []
    for mid, label, path, mixp, voices in MIXES:
        m = res[mid]
        valid = m['L']['s_t'] >= 3.0
        ds = m['L']['s'] - ref['L']['s']
        dm = m['L']['m'] - ref['L']['m']
        row = {'id': mid, 'label': label, 'file': path,
               'integrated': round(m['L']['integrated'], 2), 'lra': round(m['L']['lra'], 2), 'tp': round(m['tp'], 2),
               'max_s': round(float(m['L']['s'].max()), 2),
               'mean_abs_ds': round(float(np.abs(ds[valid]).mean()), 2),
               'rms_dev': round(float(np.abs(m['rms'] - ref['rms']).mean()), 2),
               'corr': round(float(np.nanmean(m['r'])), 3), 'width_db': round(float(np.nanmean(m['w'])), 2),
               'bands_dev': {b[0]: round(float(db(m['bands'][k].sum()) - db(ref['bands'][k].sum())), 2) for k, b in enumerate(BANDS)},
               'sections': {}}
        for name, (a, b) in SECTIONS.items():
            km = (m['L']['m_t'] >= a) & (m['L']['m_t'] < b)
            ks = (m['L']['s_t'] >= max(a, 3.0)) & (m['L']['s_t'] < b + 1.5)
            secb = slice(int(a), int(np.ceil(b)))
            row['sections'][name] = {'lufs': round(lufs_span(sig[mid], a, b), 2),
                                     'd_lufs': round(lufs_span(sig[mid], a, b) - lufs_span(o, a, b), 2),
                                     'd_m': round(float(dm[km].mean()), 2),
                                     'd_s': round(float(ds[ks].mean()), 2) if ks.any() else None,
                                     'bands': {bb[0]: round(float(db(m['bands'][k][secb].sum()) - db(ref['bands'][k][secb].sum())), 2) for k, bb in enumerate(BANDS)}}
        if mixp:
            mix = load(f'{R}/{mixp}')
            g = VOICE_GAIN.get(mid, 1.0)
            vi, vo = (load(f'{R}/{p}') * g for p in voices)
            rest = mix - vi - vo
            row['voices'] = {}
            for name, v in [('intro', vi), ('outro', vo)]:
                a, b = SPANS[name]['ours']
                row['voices'][name] = {'voice_lufs': round(lufs_span(v, a, b), 2), 'music_lufs': round(lufs_span(rest, a, b), 2),
                                       'vmr': round(lufs_span(v, a, b) - lufs_span(rest, a, b), 2),
                                       'envelope_range_db': round(envelope_range(v, a, b)[0], 1)}
        else:
            rest = o - ann
            row['voices'] = {}
            for name in ['intro', 'outro']:
                a, b = SPANS[name]['announcer']
                row['voices'][name] = {'voice_lufs': round(lufs_span(ann, a, b), 2), 'music_lufs': round(lufs_span(rest, a, b), 2),
                                       'vmr': round(lufs_span(ann, a, b) - lufs_span(rest, a, b), 2),
                                       'envelope_range_db': round(envelope_range(ann, a, b)[0], 1)}
        rows.append(row)
    Lv = loudness(video_aac)
    video_row = {'integrated': round(Lv['integrated'], 2), 'lra': round(Lv['lra'], 2), 'tp': round(true_peak(video_aac), 2)}
    tail = {k: round(float(10 * np.log10(np.mean(sig[k][int(29.0 * SR):] ** 2) + 1e-20)), 1) for k in sig}

    fig, ax = plt.subplots(3, 1, figsize=(14, 9), sharex=True, facecolor=SURFACE)
    for k in PLOTTED:
        m = res[k]
        ax[0].plot(m['L']['s_t'], m['L']['s'], color=COLOR[k], lw=2, label=m['label'])
        ax[1].plot(m['L']['m_t'], m['L']['m'], color=COLOR[k], lw=1.5, label=m['label'])
        ax[2].step(np.arange(int(DUR)) + 0.5, m['rms'], where='mid', color=COLOR[k], lw=2, label=m['label'])
    for a_, t in zip(ax, ['Short-term loudness, 3 s window (LUFS)', 'Momentary loudness, 400 ms window (LUFS)', 'RMS per second (dBFS)']):
        style(a_); shade(a_, a_ is ax[0]); a_.set_title(t, loc='left', fontsize=10, color=INK, pad=14 if a_ is ax[0] else 6)
    ax[0].set_ylim(-30, -5); ax[1].set_ylim(-35, -2); ax[2].set_ylim(-40, -5)
    ax[0].legend(loc='lower left', fontsize=8, frameon=False, ncol=3)
    ax[2].set_xlabel('seconds', color=INK2); ax[2].set_xlim(0, DUR)
    plt.tight_layout(); plt.savefig(f'{P}/loudness.png', dpi=110); plt.close()

    others = [m[0] for m in MIXES if m[0] != 'original']
    fig, ax = plt.subplots(len(others) + 1, 1, figsize=(14, 2.0 * (len(others) + 1)), sharex=True, facecolor=SURFACE)
    names = [b[0] for b in BANDS]
    im0 = ax[0].imshow(db(ref['bands']), aspect='auto', cmap='Blues', origin='lower', extent=[0, int(DUR), -0.5, len(BANDS) - 0.5])
    ax[0].set_title('Original: energy per band per second (dB)', loc='left', fontsize=10, color=INK)
    plt.colorbar(im0, ax=ax[0], pad=0.01)
    from matplotlib.colors import LinearSegmentedColormap
    div = LinearSegmentedColormap.from_list('div', ['#2a78d6', '#f0efec', '#e34948'])
    for a_, k in zip(ax[1:], others):
        d = np.clip(db(res[k]['bands']) - db(ref['bands']), -8, 8)
        im = a_.imshow(d, aspect='auto', cmap=div, vmin=-8, vmax=8, origin='lower', extent=[0, int(DUR), -0.5, len(BANDS) - 0.5])
        a_.set_title(f"{res[k]['label']} minus original (dB): red is louder, blue is missing", loc='left', fontsize=10, color=INK)
        plt.colorbar(im, ax=a_, pad=0.01)
    for a_ in ax:
        a_.set_yticks(range(len(BANDS))); a_.set_yticklabels(names, fontsize=8); a_.tick_params(colors=INK2, labelsize=8)
        for name, (a, b) in SECTIONS.items():
            a_.axvline(a, color=INK2, lw=0.5, ls=':'); a_.axvline(b, color=INK2, lw=0.5, ls=':')
    ax[-1].set_xlabel('seconds', color=INK2)
    plt.tight_layout(); plt.savefig(f'{P}/bands.png', dpi=110); plt.close()

    fig, ax = plt.subplots(len(PLOTTED), 1, figsize=(14, 3.0 * len(PLOTTED)), sharex=True, facecolor=SURFACE)
    for a_, k in zip(ax, PLOTTED):
        f, t, Z = signal.stft(sig[k].mean(1), SR, nperseg=4096, noverlap=4096 - 1024)
        a_.pcolormesh(t, f, 20 * np.log10(np.abs(Z) + 1e-9), vmin=-110, vmax=-25, shading='auto', cmap='magma', rasterized=True)
        a_.set_yscale('symlog', linthresh=200); a_.set_ylim(20, 20000); a_.set_ylabel('Hz', color=INK2)
        a_.set_title(res[k]['label'], loc='left', fontsize=10, color=INK); a_.tick_params(colors=INK2, labelsize=8)
        for name, (a, b) in SECTIONS.items():
            a_.axvline(a, color='w', lw=0.6, ls=':'); a_.axvline(b, color='w', lw=0.6, ls=':')
    ax[-1].set_xlabel('seconds', color=INK2)
    plt.tight_layout(); plt.savefig(f'{P}/spectrograms.png', dpi=100); plt.close()

    fig, ax = plt.subplots(2, 1, figsize=(14, 5.5), sharex=True, facecolor=SURFACE)
    for k in PLOTTED:
        ax[0].plot(res[k]['st_t'], res[k]['r'], color=COLOR[k], lw=2, label=res[k]['label'])
        ax[1].plot(res[k]['st_t'], res[k]['w'], color=COLOR[k], lw=2, label=res[k]['label'])
    for a_, t in zip(ax, ['L/R correlation per 250 ms (1 is mono)', 'Width: side minus mid energy per 250 ms (dB)']):
        style(a_); shade(a_, a_ is ax[0]); a_.set_title(t, loc='left', fontsize=10, color=INK, pad=14 if a_ is ax[0] else 6)
    ax[0].legend(loc='lower left', fontsize=8, frameon=False, ncol=3); ax[1].set_xlabel('seconds', color=INK2); ax[1].set_xlim(0, DUR)
    plt.tight_layout(); plt.savefig(f'{P}/stereo.png', dpi=110); plt.close()

    fig, ax = plt.subplots(3, 1, figsize=(14, 8), facecolor=SURFACE)
    h = SR // 100
    for a_, (lo, hi) in zip(ax, [(0, DUR), (0.5, 4.0), (22.5, DUR)]):
        for k, alpha in [('original', 0.35), ('current', 0.9), ('c-matched-master', 0.9)]:
            x = sig[k].mean(1)[int(lo * SR):int(hi * SR)]
            n = len(x) // h
            pk = np.abs(x[:n * h]).reshape(n, h).max(1)
            tt = lo + (np.arange(n) + 0.5) * h / SR
            if k == 'original':
                a_.fill_between(tt, -pk, pk, color=COLOR[k], alpha=alpha, lw=0, label=res[k]['label'])
            else:
                a_.plot(tt, pk, color=COLOR[k], lw=1, alpha=alpha, label=res[k]['label'])
                a_.plot(tt, -pk, color=COLOR[k], lw=1, alpha=alpha)
        style(a_); a_.set_xlim(lo, hi); a_.set_ylim(-1.05, 1.05)
    ax[0].set_title('Waveform peak envelope (10 ms): original filled, current and C as outlines', loc='left', fontsize=10, color=INK)
    ax[1].set_title('Intro line', loc='left', fontsize=10, color=INK); ax[2].set_title('Outro and end', loc='left', fontsize=10, color=INK)
    ax[0].legend(loc='lower left', fontsize=8, frameon=False, ncol=3); ax[2].set_xlabel('seconds', color=INK2)
    plt.tight_layout(); plt.savefig(f'{P}/waveform.png', dpi=110); plt.close()

    fig, ax = plt.subplots(2, 2, figsize=(14, 7.5), facecolor=SURFACE)
    for j, name in enumerate(['intro', 'outro']):
        tracks = [('Original announcer', ann, SPANS[name]['announcer'], COLOR['original']),
                  ('Current voice', load(f'{AUDIT}/work/voice-{name}-current.wav'), SPANS[name]['ours'], COLOR['current']),
                  ('B to D voice (matched)', load(f'{AUDIT}/work/voice-{name}-matched.wav'), SPANS[name]['ours'], COLOR['c-matched-master'])]
        for lab, x, (a, b), c in tracks:
            g, s = ltas(x[int(a * SR):int(b * SR)])
            ax[0, j].semilogx(g, s - s.max(), color=c, lw=2, label=lab)
            _, e = envelope_range(x, a, b)
            ax[1, j].plot(np.arange(len(e)) * 0.02, e - e.max(), color=c, lw=1.5, label=lab)
        ax[0, j].set_title(f'{name.capitalize()} line: long-term spectrum, 1/3 octave, peak at 0 dB', loc='left', fontsize=10, color=INK)
        ax[1, j].set_title(f'{name.capitalize()} line: 20 ms envelope, 300 Hz to 5 kHz (dB below peak)', loc='left', fontsize=10, color=INK)
        ax[0, j].set_ylim(-50, 3); ax[0, j].set_xlabel('Hz', color=INK2); ax[1, j].set_xlabel('seconds from line start', color=INK2)
        ax[1, j].set_ylim(-40, 2)
        for a_ in ax[:, j]:
            style(a_)
        ax[0, j].legend(fontsize=8, frameon=False, loc='lower left')
    plt.tight_layout(); plt.savefig(f'{P}/voices.png', dpi=110); plt.close()

    build = json.load(open(f'{AUDIT}/build.json'))
    vocals = json.load(open(f'{AUDIT}/vocals.json')) if os.path.exists(f'{AUDIT}/vocals.json') else {}
    data = {'rows': rows, 'video_current': video_row, 'tail_after_29s_db': tail, 'sections': SECTIONS,
            'bands': [b[0] for b in BANDS], 'build': build, 'inventory': vocals.get('inventory', [])}
    with open(f'{AUDIT}/data.js', 'w') as fh:
        fh.write('window.AUDIT = ' + json.dumps(data, indent=1) + ';\n')
    for r in rows:
        print(f"{r['label']:24s} I {r['integrated']:6.2f}  LRA {r['lra']:5.2f}  TP {r['tp']:5.2f}  |dS| {r['mean_abs_ds']:4.2f}  rmsdev {r['rms_dev']:4.2f}  r {r['corr']:.3f}  w {r['width_db']:6.2f}")
        print('    bands', r['bands_dev'])
        print('    sections', {k: (v['d_lufs'], v['d_s']) for k, v in r['sections'].items()})
        print('    voices', r['voices'])
    print('video AAC', video_row, 'tail after 29 s', tail)


if __name__ == '__main__':
    main()
