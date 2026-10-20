# Every "Patel" take, swapped into the original announcer line at several gains, as full-reel mp3s for the switcher
# page beside this script. Takes are audio/voice/take*.wav plus anything dropped into audio/patels/inbox (any format
# ffmpeg reads; a file can hold several takes). Whisper finds each "Patel"; the swap is the same as patel-swap.sh.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/patels/build.py
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import glob, json, os, subprocess, wave
import numpy as np
from faster_whisper import WhisperModel

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.join(R, 'audio', 'patels')
WORK = os.path.join(HERE, 'work')
GAINS = [4, 8, 12]  # word swap; 4 dB is the current mix
LINE_GAINS = [0, 4, 8]  # full line; 0 dB is mix-patel-v1
S = f'{R}/stems/htdemucs_ft/audio'
GATE = "volume='clip((abs(t-2.02)-0.20)/0.03,0,1)*clip((abs(t-25.0)-1.4)/0.06,0,1)':eval=frame"
CHAIN = 'highpass=f=140,lowpass=f=6800,acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4,aecho=0.8:0.5:45|95:0.22|0.12'
os.makedirs(WORK, exist_ok=True); os.makedirs(f'{HERE}/inbox', exist_ok=True); os.makedirs(f'{HERE}/out', exist_ok=True)

def ff(*a):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *a], check=True)

def takes_in(pcm):
    # Each take is one full line between pauses; Whisper only reliably hears the first line of a long memo, so it
    # gets one take at a time.
    frame = 160  # 10 ms at 16 kHz
    rms = np.sqrt(np.convolve(pcm ** 2, np.ones(frame) / frame, 'same'))[::frame]
    loud = rms > 10 ** (-35 / 20)
    spans, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            start = i if start is None else start; quiet = 0
        elif start is not None:
            quiet += 1
            if quiet > 80:  # 0.8 s of quiet ends a take; a pause inside a line runs about 0.5 s
                spans.append((start, i - quiet)); start = None
    if start is not None:
        spans.append((start, len(loud)))
    return [(max(0, a * frame - 4000), min(len(pcm), b * frame + 4000)) for a, b in spans if b - a > 50]

def patels(wav):
    model = patels.model = getattr(patels, 'model', None) or WhisperModel('medium.en', device='cpu', compute_type='int8')
    # Decoded here: the PyAV that faster-whisper pulls in rejects its own open() arguments.
    pcm = np.frombuffer(wave.open(wav).readframes(10 ** 8), np.int16).astype(np.float32) / 32768
    sr = 16000
    out = []
    for a, b in takes_in(pcm):
        segs, _ = model.transcribe(pcm[a:b], word_timestamps=True, vad_filter=False, initial_prompt='Looking for Patel, he has got it.')
        words = [(w.word.strip().lower().strip(',.!'), a / sr + w.start, a / sr + w.end) for s in segs for w in s.words]
        k = next((i for i, w in enumerate(words) if w[0] == 'patel'), None)
        if k is None or k + 1 >= len(words):
            continue
        out.append({'start': words[0][1], 'patel': (words[k][1], tail(pcm, words[k][2])), 'hes': words[k + 1][1], 'end': tail(pcm, words[-1][2])})
    return out

def tail(pcm, t, sr=16000):
    # Whisper's word end can land inside the "tel"; run on until 30 ms of quiet, at most 0.3 s further.
    i = int(t * sr)
    for j in range(i, min(len(pcm), i + int(0.3 * sr)), 160):
        if np.sqrt((pcm[j:j + 480] ** 2).mean()) < 10 ** (-32 / 20):
            return j / sr
    return t + 0.3

def swap(name, wav, a, b, gain):
    word, mp3 = f'{WORK}/{name}-g{gain}.wav', f'{HERE}/out/{name}-g{gain}.mp3'
    d = b - a
    # The word lands where take 4's did: its onset at 1.76 + the 0.03 s lead.
    ff('-i', wav, '-filter_complex', f'[0]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={d - 0.08:.3f}:d=0.08,'
       f'adelay=1760:all=1,aresample=44100,{CHAIN},volume={gain}dB,aformat=channel_layouts=stereo,apad=whole_dur=30.07,atrim=0:30.07', word)
    ff('-i', f'{S}/drums.wav', '-i', f'{S}/bass.wav', '-i', f'{S}/other.wav', '-i', f'{S}/vocals.wav', '-i', word, '-filter_complex',
       f'[3]{GATE}[v];[0][1][2][v][4]amix=inputs=5:normalize=0,atrim=0:30.07,aresample=192000,'
       'alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000', '-c:a', 'libmp3lame', '-b:a', '320k', mp3)
    return os.path.relpath(mp3, HERE)

def line(name, wav, w, gain):
    # The whole take replaces the announcer, cut into its two phrases like patel-voice.sh: the onset of "Patel" lands
    # on "James" (reel 1.81 s) and "he's" on "he's" (reel 2.33 s).
    p0, p1 = w['patel']
    a0 = max(w['start'] - 0.05, p0 - 1.81)
    a1 = min(p1 + 0.04, w['hes'] - 0.02)
    b0, b1 = w['hes'] - 0.06, w['end'] + 0.06
    if gain == LINE_GAINS[0]:
        # The same two cuts as the ffmpeg call below, written as audio/audit/build.py's INTRO_CUT. Paste it there for the take you pick.
        cut = (f'[0]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={a1 - a0 - 0.04:.3f}:d=0.04,'
               f'adelay={round((1.81 - (p0 - a0)) * 1000)}:all=1[a];'
               f'[0]atrim={b0:.3f}:{b1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={b1 - b0 - 0.06:.3f}:d=0.06,'
               f'adelay={round((2.33 - 0.06) * 1000)}:all=1[b];[a][b]amix=inputs=2:normalize=0')
        print(f'{name} INTRO_CUT = {cut!r}', flush=True)
    voice, mp3 = f'{WORK}/{name}-line-g{gain}.wav', f'{HERE}/out/{name}-line-g{gain}.mp3'
    ff('-i', wav, '-filter_complex',
       f'[0]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={a1 - a0 - 0.04:.3f}:d=0.04,adelay={round((1.81 - (p0 - a0)) * 1000)}:all=1[a];'
       f'[0]atrim={b0:.3f}:{b1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={b1 - b0 - 0.06:.3f}:d=0.06,adelay={round((2.33 - 0.06) * 1000)}:all=1[b];'
       f'[a][b]amix=inputs=2:normalize=0,aresample=44100,{CHAIN},volume={gain}dB,aformat=channel_layouts=stereo,apad=whole_dur=30.07,atrim=0:30.07', voice)
    ff('-i', f'{R}/audio/no-announcer-v2.wav', '-i', voice, '-filter_complex',
       '[0][1]amix=inputs=2:normalize=0,atrim=0:30.07,aresample=192000,alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000',
       '-c:a', 'libmp3lame', '-b:a', '320k', mp3)
    return os.path.relpath(mp3, HERE)

takes = []
for src in sorted(glob.glob(f'{R}/audio/voice/take*.wav')) + sorted(glob.glob(f'{HERE}/inbox/*')):
    base = os.path.splitext(os.path.basename(src))[0].replace(' ', '-')
    wav = f'{WORK}/{base}-16k.wav'
    ff('-i', src, '-ac', '1', '-ar', '16000', wav)
    full = f'{WORK}/{base}-full.wav'
    ff('-i', src, '-ac', '1', '-ar', '44100', full)
    for k, w in enumerate(patels(wav)):
        name = base if k == 0 else f'{base}-{k + 1}'
        a, b = max(0, w['patel'][0] - 0.03), w['patel'][1] + 0.04
        takes.append({'name': name, 'source': os.path.relpath(src, R), 'words': w,
                      'swap': {str(g): swap(name, full, a, b, g) for g in GAINS},
                      'line': {str(g): line(name, full, w, g) for g in LINE_GAINS}})
        print(name, {k: (round(v, 2) if isinstance(v, float) else [round(x, 2) for x in v]) for k, v in w.items()}, flush=True)
json.dump({'gains': {'swap': GAINS, 'line': LINE_GAINS}, 'takes': takes}, open(f'{HERE}/takes.json', 'w'), indent=1)
