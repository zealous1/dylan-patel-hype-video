#!/bin/sh
# Jersey (slot 25.60 to 27.13 s). The take's 67 tints purple and gold and
# goes soft from about 1.13 s, so only its clean first 1.10 s is used,
# retimed to fill the slot (0.72x speed), then look-matched to the original
# (posterized curves, duotone shift and light streak come from the per-frame
# curves and gain grid). The grade follows the original frame each take frame
# came from (--ref-timing take), since the retime moves the light streak.
#   v2: TAKE=shots/jersey/out/final-realtime-clean.mp4 TAG=v2 shots/jersey/post.sh   (the deghosted take, deghost.py)
#   v4: TAG=v4 shots/jersey/post.sh   (the continuous timeline, timeline.py; see the end of this file)
set -e
TAKE=${TAKE:-shots/jersey/out/final-realtime.mp4}
TAG=${TAG:-v1}
cd "$(dirname "$0")/../.."
PY="uv run --no-project --python 3.12 --with-requirements requirements.txt python -I"
mkdir -p shots/jersey/post
if [ "$TAG" != v4 ]; then
$PY shots/lookmatch.py --start 25.60 --end 27.13 --size 1920x1080 --trim 0:1.10 --mode luma --ref-timing take \
  --take "$TAKE" \
  --out shots/jersey/out/look-$TAG.mp4 --report shots/jersey/post/look-$TAG.json
fi

# v4: the jersey scene from the continuous timeline (shots/jersey/timeline.py): its first 41 frames (reel 763 to
# 803) are already retimed, so the slot is 25.43 to 26.80 with no retime, and each frame is graded against the
# original frame its content came from (768 + take position, post/refmap-v4.json). Then fadein.py v4.
if [ "$TAG" = v4 ]; then
  $PY shots/lookmatch.py --start 25.43 --end 26.80 --size 1920x1080 --trim 0:1.3667 --mode luma --ref-map shots/jersey/post/refmap-v4.json \
    --take shots/jersey/out/jersey-timeline.mp4 --out shots/jersey/out/look-v4.mp4 --report shots/jersey/post/look-v4.json
fi
