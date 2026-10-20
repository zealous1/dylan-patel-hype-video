#!/bin/sh
# Fade in v2 (slot 0.00 to 1.00 s): the first 0.5 s of the intro take, slowed to half speed (frame-blended) and
# faded up from black ourselves on an ease-in curve. The intro slot then plays the same take from 0.5 s on,
# retimed to fill 1.00 to 6.27, so no motion repeats across the cut.
set -e
cd "$(dirname "$0")/../.."
IN=shots/intro/out/overlay-v2.mp4
ffmpeg -v error -y -i $IN -an -vf "trim=end_frame=16,setpts=2*(PTS-STARTPTS),minterpolate=fps=30:mi_mode=blend,tpad=stop_mode=clone:stop=2,trim=end_frame=30,geq=lum='lum(X,Y)*pow(min(1,T/0.97),1.6)':cb='128+(cb(X,Y)-128)*pow(min(1,T/0.97),1.6)':cr='128+(cr(X,Y)-128)*pow(min(1,T/0.97),1.6)',format=yuv420p" -c:v libx264 -crf 14 shots/fadein/out/fadein-v2.mp4
ffmpeg -v error -y -i $IN -an -vf "trim=start_frame=15,setpts=(PTS-STARTPTS)*158/143,fps=30,trim=end_frame=158,format=yuv420p" -c:v libx264 -crf 14 shots/intro/out/overlay-v2-from05.mp4
