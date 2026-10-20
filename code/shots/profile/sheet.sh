#!/bin/zsh
# Contact sheet: original span (top of each pair) over our take (bottom), every Nth frame.
#   shots/profile/sheet.sh shots/profile/out/<take>.mp4 <start-frame> <step> <out.jpg>
take=$1; start=${2:-814}; step=${3:-6}; out=$4
R=${0:A:h}/../..
ss=$(python3 -c "print($start/30)")
ffmpeg -v error -y -ss $ss -i $R/src/clip.mp4 -i $take -filter_complex \
 "[0:v]trim=start_frame=0:end_frame=88,setpts=PTS-STARTPTS,select='not(mod(n\,$step))',scale=480:270[a];[1:v]select='not(mod(n\,$step))',scale=480:270[b];[a][b]vstack,tile=5x4:padding=4" \
 -frames:v 1 -fps_mode passthrough $out
