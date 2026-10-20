#!/bin/sh
# Fade-in (slot 0.00 to 1.00 s). The intro's look-matched first frame (same
# base as the intro, strong-slow-realtime), moved with the original's camera
# and faded with the original's gain, then the intro's broadcast
# graphics (SA scorebug, rebuilt banner) at the original's level per frame.
# Needs shots/intro/post/look.mp4 (shots/intro/post.sh).
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/fadein/post shots/fadein/out
$PY shots/fadein/build.py shots/intro/post/look.mp4 shots/fadein/post/plate.mkv
$PY shots/intro/graphics.py shots/fadein/post/plate.mkv shots/fadein/out/fadein-v1.mp4 \
  --start 0.00 --end 1.00 --line1 "TO BREAK" --line2 "BOOTSTRAP RECORD" --num '$2M'
