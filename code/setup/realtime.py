#!/usr/bin/env python3
"""Speed a slowed generation back up to the shot's real length by picking frames from it.

    python3 -I setup/realtime.py shots/upscale-sweep/picks/<shot>.json
    python3 -I setup/realtime.py <generation.mp4> <frames> <out.mp4>

With a picks file, the take is rebuilt from exactly the generation frames the reel used ("gen", "picks", "take").
Without one, output frame k is generation frame round((k + 0.5) * G / frames), where G is the generation's frame
count, which spreads the picks evenly.
"""
import json, os, subprocess, sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
if args[:1] in (['-h'], ['--help']) or len(args) not in (1, 3):
    print(__doc__.strip())
    sys.exit(0 if args[:1] in (['-h'], ['--help']) else 2)
if len(args) == 1:
    spec = json.load(open(args[0]))
    gen, out, picks = os.path.join(CODE, spec['gen']), os.path.join(CODE, spec['take']), spec['picks']
else:
    gen, n, out = args[0], int(args[1]), args[2]
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                            'stream=nb_read_frames', '-of', 'json', gen], capture_output=True, text=True, check=True)
    g = int(json.loads(probe.stdout)['streams'][0]['nb_read_frames'])
    picks = [min(g - 1, round((k + 0.5) * g / n)) for k in range(n)]
assert picks == sorted(set(picks)), 'picks must be distinct and in order'
expr = '+'.join(f'eq(n,{p})' for p in picks)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', gen, '-vf', f"select='{expr}',setpts=N/30/TB", '-r', '30',
                '-frames:v', str(len(picks)), '-an', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', out], check=True)
print(f'{out}: {len(picks)} frames')
