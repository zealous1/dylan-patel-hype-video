# Renders the audit's candidate mixes, each a fix stacked on the one before, and a video-copy remux of each onto the
# locked 30 fps master. Never touches an existing file outside audio/audit.
#   A  full bed: the original track minus only the announcer's words (restore.py), same voices, duck and limiter.
#   B  A, with both lines rebuilt from the raw memos: dry, EQ matched to the announcer each replaces, and set to the
#      announcer's level against the music. No extra duck: the original's own bed already carries whatever ducking
#      the editor did.
#   C  B, mastered to the original's integrated loudness with a -1 dBTP ceiling. The limiter releases in 10 ms, not
#      40: the original's peaks are clipped flat, and a 40 ms release pulls the dense newspaper and fast-cut
#      sections down 0.5 to 0.8 LU, while 10 ms tracks the original's short-term loudness within 0.2 LU on average.
#   D  C, with both lines 2 dB hotter than the announcer's, for a louder Patel.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/audit/build.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, sys
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(__file__))
from lib import R, AUDIT, SR, STEMS, DUR, load, save, lufs_span, loudness, true_peak, ltas
from restore import restore, gate_curve, LINES

WORK, OUT = f'{AUDIT}/work', f'{AUDIT}/out'
VIDEO = f'{R}/master/out/final-worn-30-master.mp4'
CURRENT_LIMITER = 'aresample=192000,alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000'
TP_CEILING = -1.0

# The two lines as placed today: patels/build.py line() for memo 3 take 5, and outro/build.py for take 3.
INTRO_SRC = f'{R}/audio/patels/inbox/memo3.m4a'
INTRO_CUT = ('[0]atrim=15.350:16.620,asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st=1.230:d=0.04,adelay=1060:all=1[a];'
             '[0]atrim=16.740:17.440,asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st=0.640:d=0.06,adelay=2270:all=1[b];'
             '[a][b]amix=inputs=2:normalize=0')
OUTRO_SRC = f'{R}/audio/outro/memo.m4a'
OUTRO_CUT = ("[0]atrim=11.840:14.600,asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
             "volume='if(lt(t,2.120),1,max(0,1-(t-2.120)/0.620))':eval=frame")
OUTRO_AT_MS = 22960
# Spans where each voice speaks, for level and spectrum: the announcer's words, and ours as placed.
SPANS = {'intro': {'announcer': LINES['intro']['gate'], 'ours': (1.33, 2.93)},
         'outro': {'announcer': LINES['outro']['gate'], 'ours': (22.96, 25.75)}}
# B's chain before the matched EQ: the old broadcast chain without its 6.8 kHz low-pass (it cut the air the
# announcer has) and without the 45/95 ms slap (the announcer is drier and choppier than ours, see voices in data).
DRY_CHAIN = 'highpass=f=90,acompressor=threshold=-20dB:ratio=4:attack=8:release=100:makeup=4'


def ff(*a):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *a], check=True)


def voice(src, cut, chain, at_ms, path):
    # Placed in numpy: ffmpeg 7.1 drops a long adelay that follows a no-op aresample.
    ff('-i', src, '-filter_complex', f'{cut},aresample={SR},{chain},aformat=channel_layouts=stereo', '-c:a', 'pcm_f32le', path)
    x, k = load(path), int(round(at_ms * SR / 1000))
    y = np.zeros_like(x)
    y[k:] = x[:len(x) - k]
    save(path, y)
    return y


def match_eq(x, target, span_x, span_t):
    """Linear-phase FIR that moves x's 1/3-octave long-term spectrum onto target's, within +-8 dB, 80 Hz to 14 kHz."""
    g, tx = ltas(x[int(span_x[0] * SR):int(span_x[1] * SR)])
    _, tt = ltas(target[int(span_t[0] * SR):int(span_t[1] * SR)])
    d = (tt - tt.max()) - (tx - tx.max())
    d -= np.median(d[(g > 300) & (g < 3000)])
    d = np.clip(d, -8, 8)
    d[(g < 80) | (g > 14000)] = 0
    freqs = np.concatenate([[0], g, [SR / 2]]) / (SR / 2)
    gains = 10 ** (np.concatenate([[d[0]], d, [d[-1]]]) / 20)
    h = signal.firwin2(4095, freqs, gains)
    y = signal.fftconvolve(x, h[:, None], axes=0)[2047:2047 + len(x)]
    return y, dict(zip(np.round(g).astype(int).tolist(), np.round(d, 2).tolist()))


def master(x, path, gain_db, limit):
    tmp = f'{WORK}/premaster.wav'
    save(tmp, x * 10 ** (gain_db / 20))
    ff('-i', tmp, '-af', f'aresample=192000,alimiter=limit={limit:.4f}:attack=0.5:release=10:level=false,aresample={SR}',
       '-c:a', 'pcm_s24le', path)
    return load(path)


def master_to(x, path, target_lufs):
    """Limits at a -1 dBTP ceiling and finds the input gain that lands the limited mix on target_lufs."""
    limit, gain = 10 ** ((TP_CEILING - 0.4) / 20), 0.0
    for _ in range(6):
        y = master(x, path, gain, limit)
        err = target_lufs - loudness(y)['integrated']
        tp = true_peak(y)
        if tp > TP_CEILING:
            limit *= 10 ** ((TP_CEILING - tp - 0.05) / 20)
        if abs(err) < 0.05 and tp <= TP_CEILING:
            break
        gain += err
    return y, {'gain_db': round(gain, 2), 'limit': round(limit, 4)}


def remux(wav, mp4):
    ff('-i', VIDEO, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
       '-shortest', '-movflags', '+faststart', mp4)
    n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                            'stream=nb_read_frames', '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout)
    assert n == 902, (mp4, n)
    return n


def main():
    os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    orig = load(f'{R}/src/clip.mp4')
    stems = {k: load(f'{STEMS}/{k}.wav') for k in ['drums', 'bass', 'other', 'vocals']}
    song, ann, g = restore(stems['vocals'])
    save(f'{WORK}/vocals-song.wav', song); save(f'{WORK}/vocals-announcer.wav', ann)

    # The bed is the original decode wherever the announcer is silent, so the 19 dB of mix that htdemucs left out of
    # its four stems comes back too. Under the words it is the stems with the song-only vocal stem.
    xf = gate_curve(len(orig), [v['gate'] for v in LINES.values()], ramp=0.05)[:, None]
    bed = orig * (1 - xf) + (stems['drums'] + stems['bass'] + stems['other'] + song) * xf
    save(f'{WORK}/bed-full.wav', bed)
    rest_orig = orig - ann

    old_chain = 'highpass=f=140,lowpass=f=6800,acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4,aecho=0.8:0.5:45|95:0.22|0.12'
    line_g4 = voice(INTRO_SRC, INTRO_CUT, f'{old_chain},volume=4dB', 0, f'{WORK}/voice-intro-line-g4.wav')
    d = lufs_span(line_g4, 0, DUR) - lufs_span(load(f'{R}/audio/voice/memo3-take5-line-g4.wav'), 0, DUR)
    print(f'intro line rebuilt from memo 3 at 48 kHz: {d:+.2f} LU against audio/voice/memo3-take5-line-g4.wav')
    save(f'{WORK}/voice-outro-current.wav', load(f'{R}/audio/voice/outro-take3-g0.wav'))
    # blend.sh and the final render: the line at -2 dB, 3 dB off under 300 Hz, 2 dB up at 3 kHz.
    ff('-i', f'{WORK}/voice-intro-line-g4.wav', '-af', 'volume=-2dB,lowshelf=f=300:g=-3,equalizer=f=3000:t=q:w=1:g=2',
       '-c:a', 'pcm_f32le', f'{WORK}/voice-intro-current.wav')

    # A: the current recipe on the full bed (sidechain duck keyed by the intro line, as blend.sh does).
    ff('-i', f'{WORK}/bed-full.wav', '-i', f'{WORK}/voice-intro-current.wav', '-i', f'{WORK}/voice-outro-current.wav',
       # Padded past the end: with the voice split into both the key and amix, ffmpeg ends the ducked bed early,
       # which is what silenced today's final from 28.978 s.
       '-filter_complex', '[0]apad=pad_dur=1[b];[1]apad=pad_dur=1,asplit[v][key];[b][key]sidechaincompress=threshold=0.05:ratio=3:attack=15:release=250:makeup=1:mix=0.6[m];'
       f'[m][v][2]amix=inputs=3:normalize=0,atrim=0:{DUR}', '-c:a', 'pcm_f32le', f'{WORK}/mix-a.wav')
    mix_a = load(f'{WORK}/mix-a.wav')

    lines = {}
    raw = {'intro': voice(INTRO_SRC, INTRO_CUT, DRY_CHAIN, 0, f'{WORK}/voice-intro-dry.wav'),
           'outro': voice(OUTRO_SRC, OUTRO_CUT, DRY_CHAIN, OUTRO_AT_MS, f'{WORK}/voice-outro-dry.wav')}
    matched = {}
    for name, x in raw.items():
        sp = SPANS[name]
        y, curve = match_eq(x, ann, sp['ours'], sp['announcer'])
        vmr_orig = lufs_span(ann, *sp['announcer']) - lufs_span(rest_orig, *sp['announcer'])
        gain = vmr_orig - (lufs_span(y, *sp['ours']) - lufs_span(bed, *sp['ours']))
        matched[name] = y * 10 ** (gain / 20)
        lines[name] = {'vmr_target': round(vmr_orig, 2), 'gain_db': round(gain, 2), 'eq_db': curve}
    mix_b = bed + matched['intro'] + matched['outro']
    mix_d = bed + (matched['intro'] + matched['outro']) * 10 ** (2 / 20)
    save(f'{WORK}/voice-intro-matched.wav', matched['intro']); save(f'{WORK}/voice-outro-matched.wav', matched['outro'])

    target = loudness(orig)['integrated']
    report = {'lines': lines, 'master': {}}
    renders = {'a-full-bed': (mix_a, None), 'b-matched-voices': (mix_b, None),
               'c-matched-master': (mix_b, target), 'd-hotter-voices': (mix_d, target)}
    for cid, (x, tgt) in renders.items():
        save(f'{OUT}/{cid}-mix.wav', x)
        path = f'{OUT}/{cid}.wav'
        if tgt is None:
            ff('-i', f'{OUT}/{cid}-mix.wav', '-af', CURRENT_LIMITER, '-c:a', 'pcm_s24le', path)
            report['master'][cid] = 'current limiter'
        else:
            _, report['master'][cid] = master_to(x, path, tgt)
        if os.path.exists(VIDEO):
            report.setdefault('frames', {})[cid] = remux(path, f'{OUT}/{cid}.mp4')
        print(cid, 'done', report['master'][cid])
    json.dump(report, open(f'{AUDIT}/build.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
