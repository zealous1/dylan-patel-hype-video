#!/bin/sh
# Derived inputs, after setup/fetch.py: the Demucs stems, the reference stills the image edits start from, and the
# source spans for video-to-video. Safe to rerun; finished files are kept. Run from code/.
set -e
cd "$(dirname "$0")/.."
[ -e stems/htdemucs_ft/audio/vocals.wav ] || uv run --no-project --python 3.12 --with-requirements requirements-stems.txt demucs -n htdemucs_ft -o stems src/audio.wav
mkdir -p starts/src
for t in 3.0 7.0 8.7 11.6 22.95 26.0 29.0; do
  [ -e "starts/src/lebron-$t.png" ] || ffmpeg -v error -y -ss "$t" -i src/clip.mp4 -frames:v 1 "starts/src/lebron-$t.png"
done
# The image model refuses an edit of the untouched frame. A flat grey box over the original player's head gets
# through, and it tells the model where Dylan's head goes.
[ -e starts/src/lebron-11.6-nohead.png ] || ffmpeg -v error -y -i starts/src/lebron-11.6.png \
  -vf "drawbox=x=790:y=40:w=270:h=330:color=0x808080:t=fill" starts/src/lebron-11.6-nohead.png
python3 -I setup/spans.py
