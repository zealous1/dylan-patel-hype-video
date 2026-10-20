#!/bin/sh
# Fade out (slot 23.17 to 25.60 s). The first second (LeBron on the rim) is the Dylan V2V take,
# look-matched to the original; the rest is the original fade, where he has left the frame.
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/fadeout/post
$PY shots/lookmatch.py --start 23.17 --end 24.17 --size 1920x1080 \
  --take shots/fadeout/out/wan-3.0-noframes-slow-focus.mp4 \
  --out shots/fadeout/post/head.mp4 --report shots/fadeout/post/look.json
ffmpeg -v error -y -i shots/fadeout/post/head.mp4 -ss 24.17 -to 25.60 -i src/clip.mp4 \
  -filter_complex "[0:v]fps=30,format=yuv420p,setsar=1[a];[1:v]fps=30,scale=1920:1080,format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -an -c:v libx264 -crf 16 -pix_fmt yuv420p -frames:v 73 shots/fadeout/out/splice-v1.mp4

# v3 (2026-10-17): the V2V head's last two frames (28, 29; reel 24.10 to 24.17) are a Wan hallucination of another
# angle (a court logo seen from above), not in the original. The head now stops after frame 27 and the original
# takes over from 24.103, for the scene's 68 frames (23.17 to 25.43).
ffmpeg -v error -y -i shots/fadeout/post/head.mp4 -ss 24.1033 -i src/clip.mp4 \
  -filter_complex "[0:v]fps=30,trim=end_frame=28,format=yuv420p,setsar=1[a];[1:v]fps=30,scale=1920:1080,format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -an -c:v libx264 -crf 16 -pix_fmt yuv420p -frames:v 68 shots/fadeout/out/splice-v3.mp4
