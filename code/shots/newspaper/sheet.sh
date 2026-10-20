#!/bin/sh
# Contact sheet: original (left) next to ours (right) for the frames given. Usage: sh sheet.sh out.jpg 1 2 5 ...
# Needs build/frames from render.mjs. Original frames come from src/clip.mp4 at 12.00 s + k/30.
cd "$(dirname "$0")"; OUTF="$1"; shift; T=build/sheet; rm -rf $T; mkdir -p $T
for k in "$@"; do f=$(printf "%03d" $k)
  ffmpeg -v error -y -ss $(echo "12 + $k/30 + 0.001" | bc -l) -i ../../src/clip.mp4 -i build/frames/f$f.png -filter_complex "[0]scale=480:270[a];[1]scale=480:270[b];[a][b]hstack" -frames:v 1 $T/c$f.png
done
n=$#; rows=$(( (n + 1) / 2 ))
ffmpeg -v error -y -pattern_type glob -i "$T/c*.png" -vf "tile=2x$rows" -frames:v 1 "$OUTF"
