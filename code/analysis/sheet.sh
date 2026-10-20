#!/bin/bash
# Labelled contact sheet of a span at a given rate: sheet.sh <video> <start> <seconds> <fps> <out.jpg> [cols]
in=$1 ss=$2 len=$3 fps=$4 out=$5 cols=${6:-6}
n=$(echo "($len*$fps+$cols-1)/$cols" | bc)
ffmpeg -hide_banner -v error -y -i "$in" \
  -vf "trim=start=$ss:duration=$len,fps=$fps,scale=400:-2,drawtext=fontfile='${FONT_DIR:-fonts}/Inter-Bold.ttf':text='%{pts\:flt}':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=${cols}x${n}" \
  -frames:v 1 "$out"
