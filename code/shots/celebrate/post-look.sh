#!/bin/sh
# Celebration (slot 10.80 to 12.00 s). Look-match only: the min-realtime take
# keeps its content and gets the original's per-frame grade and blur.
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/celebrate/post
$PY shots/lookmatch.py --start 10.80 --end 12.00 --size 1920x1080 \
  --take shots/celebrate/out/min-realtime.mp4 \
  --out shots/celebrate/out/look-v1.mp4 --report shots/celebrate/post/look.json
