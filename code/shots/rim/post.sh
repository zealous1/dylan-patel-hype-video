#!/bin/sh
# Rim (slot 10.00 to 10.80 s). Look-match the Dylan take to the original,
# frame by frame, including the radial zoom blurs on the whips at 10.0 and
# 10.7 and the flash at 10.77. The take cuts to the celebration 3 frames
# early (from 0.70 s), so only its wide shot (0 to 0.70 s) is used, retimed
# to 0.80 s; the whip then lands on the wide shot as in the original.
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/rim/post
$PY shots/lookmatch.py --start 10.00 --end 10.80 --size 1920x1080 \
  --trim 0:0.70 --take shots/rim/out/final-realtime.mp4 \
  --out shots/rim/out/look-v1.mp4 --report shots/rim/post/look.json
