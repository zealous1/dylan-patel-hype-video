#!/usr/bin/env python3
"""Download the reel's inputs with the yt-dlp pinned in requirements.txt. Nothing here is in the repo; you fetch your own copies.

    uv run --no-project --python 3.12 --with-requirements requirements.txt python -I setup/fetch.py [--edl shots/fastcuts/edl-v18-s2.json] [--only reference|footage]

Writes, under code/:
  src/clip.mp4       the reference edit from ../sources.json (1080p, 30 fps, 900 frames). The run used YouTube's
                     1080p H.264 stream with its AAC audio. When YouTube still serves them, the file is kept as
                     downloaded, frame for frame the run's own. Any other format is converted to 1080p at 30 fps,
                     which can come out at 899 frames. The fetch stops unless the clip has 900, because the ending
                     (shots/profile/build.py) reads the reference up to frame 899
  src/audio.wav      its audio, 44.1 kHz stereo; src/audio16k.wav, 16 kHz mono for the speech models
  footage/<id>/...   every podcast and keynote window the edit list cuts from, video only. Each window starts at the
                     source's source_offset and runs 2 s past the last frame the edit list uses (at least 14 s)
Existing files are kept, so a rerun only fetches what is missing.
"""
import argparse, json, math, os, subprocess, sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(CODE)
YTDLP = (sys.executable, '-m', 'yt_dlp')
VIDEO = 'bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]'
FRAMES = 900


def run(*cmd):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def probe(path, entries, *flags):
    return subprocess.run(['ffprobe', '-v', 'error', *flags, '-select_streams', 'v:0', '-show_entries', f'stream={entries}',
                           '-of', 'csv=p=0', path], capture_output=True, text=True, check=True).stdout.strip()


def reference():
    url = json.load(open(os.path.join(ROOT, 'sources.json')))['reference_edit']['url']
    clip = os.path.join(CODE, 'src', 'clip.mp4')
    os.makedirs(os.path.dirname(clip), exist_ok=True)
    if not os.path.exists(clip):
        raw = clip + '.download.mp4'
        run(*YTDLP, '-f', f'({VIDEO})+ba[ext=m4a]/({VIDEO})+ba/b[height<=1080]', '--merge-output-format', 'mp4', '-o', raw, url)
        if probe(raw, 'codec_name,width,height,r_frame_rate') == 'h264,1920,1080,30/1':
            os.replace(raw, clip)
        else:
            # fps before scale: with scale first, ffmpeg 7.1 drops the last frame of a 900-frame source.
            run('ffmpeg', '-v', 'error', '-y', '-i', raw, '-vf', 'fps=30,scale=1920:1080:flags=lanczos', '-frames:v', str(FRAMES),
                '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k', clip)
            os.remove(raw)
    n = int(probe(clip, 'nb_read_frames', '-count_frames'))
    if n != FRAMES:
        sys.exit(f'src/clip.mp4 has {n} frames, not {FRAMES}. The ending reads the reference up to frame {FRAMES - 1}, '
                 'so delete src/clip.mp4 and fetch again, or convert it to 1080p at 30 fps yourself')
    for name, args in (('audio.wav', ['-ar', '44100', '-ac', '2']), ('audio16k.wav', ['-ar', '16000', '-ac', '1'])):
        out = os.path.join(CODE, 'src', name)
        if not os.path.exists(out):
            run('ffmpeg', '-v', 'error', '-y', '-i', clip, '-vn', *args, '-c:a', 'pcm_s16le', out)


def footage(edl_path):
    edl = json.load(open(os.path.join(CODE, edl_path)))
    used = {}
    for c in edl['clips']:
        used[c['src']] = max(used.get(c['src'], 0), c['src_in'] + (c['slot_out'] - c['slot_in']))
    for name, s in edl['sources'].items():
        if not s.get('url') or name not in used:
            continue
        out = os.path.join(CODE, s['file'])
        if os.path.exists(out):
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        a = s['source_offset']
        b = a + max(14, math.ceil(used[name] + 2))
        run(*YTDLP, '-f', VIDEO, '--download-sections', f'*{a}-{b}', '--force-keyframes-at-cuts',
            '--merge-output-format', 'mp4', '-o', out, s['url'].split('&')[0])


ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--edl', default='shots/fastcuts/edl-v18-s2.json', help='edit list whose sources to fetch, relative to code/')
ap.add_argument('--only', choices=['reference', 'footage'])
args = ap.parse_args()
if args.only != 'footage':
    reference()
if args.only != 'reference':
    footage(args.edl)
