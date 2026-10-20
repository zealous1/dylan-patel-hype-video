#!/bin/sh
# Intro (slot 1.00 to 6.27 s). Look-match the Wan take to the original, then
# rebuild the broadcast graphics. Re-runnable from this dir.
# Base: strong-slow-realtime, the strong prompt slowed 2x. Of the two strong
# takes it keeps the ball-handler's hair even; the 2x-speed strong take shows
# a light band across his crown at frames 24 to 33 and 138 to 147.
set -e
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/intro/post
$PY shots/lookmatch.py --start 1.00 --end 6.27 --size 1920x1080 \
  --take shots/intro/out/strong-slow-realtime.mp4 \
  --out shots/intro/post/look.mp4 --report shots/intro/post/look.json
# Banner, the original's form "PTS TO BREAK / SCORING RECORD | 2": the number
# box holds what remains, $2M.
$PY shots/intro/graphics.py shots/intro/post/look.mp4 shots/intro/out/overlay-v2.mp4 \
  --line1 "TO BREAK" --line2 "BOOTSTRAP RECORD" --num '$2M'
$PY shots/intro/graphics.py shots/intro/post/look.mp4 shots/intro/out/banner-alt-a.mp4 \
  --line1 "TO BREAK" --line2 '$100M RECORD' --num '$2M'
$PY shots/intro/graphics.py shots/intro/post/look.mp4 shots/intro/out/banner-alt-b.mp4 \
  --line1 "TO BREAK BOOTSTRAPPED" --line2 "REVENUE RECORD" --num '$2M'
