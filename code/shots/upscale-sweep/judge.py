# Judges the sweep: for each shot, every variant in out/ next to the Lanczos baseline (base/<shot>-lanczos.mp4).
# Writes browser-playable 1080 previews (web/), 1:1 crops of faces, jersey text and hands (crops/), and metrics.json
# (metrics.py per shot). Reruns skip previews and crops that exist; metrics always recompute.
#   uv run --no-project --python 3.12 --with-requirements requirements.txt python -I shots/upscale-sweep/judge.py [--shots rim,...]
import argparse, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH = 400, 225
# (label, generation frame, x, y) of each crop's top-left at 1920x1080.
CROPS = {
    'rim': [('shooter', 30, 180, 560), ('backboard', 30, 1360, 0), ('defenders', 30, 1480, 560)],
    'celebrate': [('face', 45, 700, 260), ('jersey', 45, 720, 600), ('hand', 75, 1500, 260)],
    'fadeout': [('player', 30, 260, 400), ('net', 30, 820, 500), ('sponsor', 30, 400, 780)],
    'alleyoop': [('dunker', 135, 760, 300), ('passer', 135, 260, 440), ('court text', 60, 40, 400)],
    'backdown': [('dribbler', 60, 760, 240), ('referee', 60, 1380, 820)],
    'fadeaway': [('shooter', 30, 340, 560), ('backboard', 30, 1300, 100)],
}

def ff(*a):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)

ap = argparse.ArgumentParser()
ap.add_argument('--shots', default='rim,celebrate,fadeout,alleyoop')
a = ap.parse_args()
os.makedirs(f'{HERE}/web', exist_ok=True)
os.makedirs(f'{HERE}/crops', exist_ok=True)
mpath = f'{HERE}/metrics.json'
metrics = json.load(open(mpath)) if os.path.exists(mpath) else {}
for shot in a.shots.split(','):
    vids = {'lanczos': f'{HERE}/base/{shot}-lanczos.mp4'}
    for p in sorted(glob.glob(f'{HERE}/out/{shot}-*.mp4')):
        vids[os.path.basename(p)[len(shot) + 1:-4]] = p
    for v, p in vids.items():
        web = f'{HERE}/web/{shot}-{v}.mp4'
        if not os.path.exists(web):
            ff('-i', p, '-vf', 'scale=1920:1080:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '14', '-preset', 'slow',
               '-movflags', '+faststart', web)
        for label, f, x, y in CROPS[shot]:
            png = f'{HERE}/crops/{shot}-{label.replace(" ", "_")}-{v}.png'
            if not os.path.exists(png):
                ff('-i', p, '-vf', f'scale=1920:1080:flags=lanczos,select=eq(n\\,{f}),crop={CW}:{CH}:{x}:{y}', '-frames:v', '1', png)
    js = f'{HERE}/web/{shot}-metrics.json'
    out = subprocess.run([sys.executable, '-I', f'{HERE}/metrics.py', '--json', js, *[f'{v}={p}' for v, p in vids.items()]],
                         capture_output=True, text=True, check=True).stdout
    print(shot); print(out)
    metrics[shot] = json.load(open(js))
    os.remove(js)
json.dump(metrics, open(mpath, 'w'), indent=1)
