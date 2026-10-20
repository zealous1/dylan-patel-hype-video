#!/bin/sh
# Back-down (slot 6.27 to 8.57 s). Look-match the take to the original.
# The original cuts in hard at 6.27 (luma 88 to 154 in one frame, no white
# frame), so no flash is added; the one white frame at 8.57 belongs to the
# fadeaway slot.
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/backdown/post
$PY shots/lookmatch.py --start 6.27 --end 8.57 --size 1920x1080 \
  --take shots/backdown/out/focus-realtime.mp4 \
  --out shots/backdown/out/look-v1.mp4 --report shots/backdown/post/look.json
