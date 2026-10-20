#!/usr/bin/env python3
"""Cut each swapped shot's source span from the reference, and its slowed copy for video-to-video.

    python3 -I setup/spans.py [shot ...]

Reads setup/spans.json and src/clip.mp4. Writes shots/<shot>/src-720.mp4 (1280x720, 30 fps) and
shots/<shot>/src-720-slow.mp4, the same frames slowed by slow_factor with frame blending and cut to slow_frames.
Wan fills the duration it is given, so the slowed copy keeps it from inventing motion past the end of the source.
Upload both to the folder you name in SOURCE_BASE_URL, as <shot>/src-720.mp4 and <shot>/src-720-slow.mp4, before
running shots/vid.mjs.
"""
import json, os, subprocess, sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spans = {k: v for k, v in json.load(open(os.path.join(CODE, 'setup', 'spans.json'))).items() if k != 'note'}
names = sys.argv[1:] or list(spans)
if '-h' in names or '--help' in names:
    print(__doc__.strip())
    sys.exit(0)
clip = os.path.join(CODE, 'src', 'clip.mp4')
enc = ['-r', '30', '-an', '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p']
for name in names:
    s = spans[name]
    out = os.path.join(CODE, 'shots', name)
    os.makedirs(out, exist_ok=True)
    pick = f"trim=start_frame={s['start']}:end_frame={s['start'] + s['frames']},setpts=PTS-STARTPTS,scale=1280:720:flags=lanczos"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', clip, '-vf', pick, *enc, os.path.join(out, 'src-720.mp4')], check=True)
    slow = f"{pick},setpts={s['slow_factor']}*PTS,minterpolate=fps=30:mi_mode=blend,tpad=stop_mode=clone:stop=30"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', clip, '-vf', slow,
                    '-frames:v', str(s['slow_frames']), *enc, os.path.join(out, 'src-720-slow.mp4')], check=True)
    print(f"{name}: {s['frames']} frames, slowed to {s['slow_frames']}")
