#!/bin/sh
# Fadeaway (slot 8.57 to 10.00 s). Look-match the 1.40 s take, retimed to
# 1.43 s, to the original (this brings in the original's white flash frame at
# 8.57 and the zoom blur into the rim), then composite the burning wafer on
# the hand-keyed ball path (ball-keys.json).
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/fadeaway/post
$PY shots/lookmatch.py --start 8.57 --end 10.00 --size 1920x1080 \
  --take shots/fadeaway/out/final-realtime.mp4 \
  --out shots/fadeaway/post/look.mp4 --report shots/fadeaway/post/look.json
$PY shots/fadeaway/wafer.py shots/fadeaway/post/look.mp4 shots/fadeaway/out/wafer-v1.mp4 \
  shots/fadeaway/post/track.json
