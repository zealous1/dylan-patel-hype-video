# Zeal's "Whoa... DYLAN with the gigawatt" outro takes (memo.m4a, the last two of four) in place of the original's
# fade-out yell ("LeBron, make doin' it, kid!", vocal stem 23.3 to 26.4 s, already muted in the current mix).
# "Dylan" lands on "LeBron" (reel 24.16 s). The voice fades out across its last word: from where "gigawatt"
# starts to where its waveform ends. Same broadcast chain as the Patel line, then the level is matched to the
# original yell (and +4 dB).
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I audio/outro/build.py   (from R)
import itertools, sys
if sys.argv[1:2] in (['-h'], ['--help']):
    print(__doc__ or ''.join(itertools.takewhile(lambda line: line.startswith('#'), open(__file__))), end='')
    sys.exit()
import json, os, subprocess, wave
import numpy as np
from faster_whisper import WhisperModel

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.join(R, 'audio', 'outro')
BASE = f'{R}/audio/mix-patel-memo3-5-blend.wav'
LEBRON, YELL = 24.16, (23.3, 26.4)
TAKES = {'take3': (11.8, 15.2), 'take4': (16.9, 19.9)}
GAINS = [0, 4]
CHAIN = 'highpass=f=140,lowpass=f=6800,acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4,aecho=0.8:0.5:45|95:0.22|0.12'
os.makedirs(f'{HERE}/out', exist_ok=True); os.makedirs(f'{HERE}/work', exist_ok=True)

def ff(*a): subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *a], check=True)
def read(p): return np.frombuffer(wave.open(p).readframes(10 ** 9), np.int16).astype(np.float32) / 32768
def lufs(p, a=0, d=None):
    cmd = ['ffmpeg', '-hide_banner', '-ss', str(a), *(['-t', str(d)] if d else []), '-i', p, '-af', 'ebur128', '-f', 'null', '-']
    out = subprocess.run(cmd, capture_output=True, text=True).stderr
    return float([l for l in out.splitlines() if l.strip().startswith('I:')][-1].split()[1])

def word_end(x, t, sr=16000):
    # where the last word's waveform has died: the first 30 ms window after t under -40 dBFS
    i = int(t * sr)
    for j in range(i, len(x) - 480, 160):
        if np.sqrt((x[j:j + 480] ** 2).mean()) < 10 ** (-40 / 20): return j / sr
    return len(x) / sr

model = WhisperModel('medium.en', device='cpu', compute_type='int8')
x16 = read(f'{HERE}/memo-16k.wav')
ref = lufs(f'{R}/stems/htdemucs_ft/audio/vocals.wav', YELL[0], YELL[1] - YELL[0])
rows = []
for name, (a, b) in TAKES.items():
    seg = x16[int(a * 16000):int(b * 16000)]
    words = [(w.word.strip().lower().strip(',.!'), a + w.start, a + w.end) for s in
             model.transcribe(seg, word_timestamps=True, vad_filter=False, initial_prompt='Whoa, Dylan with the gigawatt!')[0] for w in s.words]
    dylan = next(w for w in words if w[0] == 'dylan')
    last = next(w for w in reversed(words) if w[0].startswith('giga'))
    start = max(a, dylan[1] - 1.2)                     # keep the "whoa" lead-in
    end = word_end(x16, last[1] + 0.15)
    f0, f1 = last[1] - start, end - start                # fade window, relative to the cut
    raw = f'{HERE}/work/{name}.wav'
    ff('-i', f'{HERE}/memo.wav', '-af', f'atrim={start:.3f}:{end + 0.02:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,'
       f"volume='if(lt(t,{f0:.3f}),1,max(0,1-(t-{f0:.3f})/{f1 - f0:.3f}))':eval=frame,aresample=44100,{CHAIN}", raw)
    match = ref - lufs(raw)
    for g in GAINS:
        voice, mp3 = f'{HERE}/work/{name}-g{g}.wav', f'{HERE}/out/{name}-g{g}.mp3'
        ff('-i', raw, '-af', f'volume={match + g:.2f}dB,adelay={round((LEBRON - (dylan[1] - start)) * 1000)}:all=1,aformat=channel_layouts=stereo,apad=whole_dur=30.07,atrim=0:30.07', voice)
        ff('-i', BASE, '-i', voice, '-filter_complex', '[0][1]amix=inputs=2:normalize=0,atrim=0:30.07[m]', '-map', '[m]', '-c:a', 'pcm_s24le', f'{HERE}/work/{name}-g{g}-mix.wav')
        ff('-i', f'{HERE}/work/{name}-g{g}-mix.wav', '-af', 'aresample=192000,alimiter=limit=0.84:attack=1:release=40:level=false,aresample=48000', '-b:a', '320k', mp3)
    rows.append({'name': name, 'words': words, 'cut': [round(start, 3), round(end, 3)], 'dylan_at': LEBRON,
                 'fade': [round(last[1], 3), round(end, 3)], 'match_db': round(match, 2)})
    print(name, 'cut', round(start, 2), round(end, 2), 'dylan', round(dylan[1], 2), 'fade', round(last[1], 2), '->', round(end, 2), 'match', round(match, 1), 'dB')
    cut = (f'[0]atrim={start:.3f}:{end + 0.02:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,'
           f"volume='if(lt(t,{f0:.3f}),1,max(0,1-(t-{f0:.3f})/{f1 - f0:.3f}))':eval=frame")
    print(f'{name} OUTRO_CUT = {cut!r}  OUTRO_AT_MS = {round((LEBRON - (dylan[1] - start)) * 1000)}', flush=True)
json.dump(rows, open(f'{HERE}/takes.json', 'w'), indent=1)
