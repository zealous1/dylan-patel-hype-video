#!/bin/bash
# Fade in v3 and intro v3: v2's two retimes redone with RIFE v4.6 (rife-ncnn-vulkan, the release folder in RIFE_DIR) instead of
# frame blending and frame duplication. The fade-in is the intro take's first 16 frames made into 32 real in-between
# frames (half speed), cut to 30 and faded up on the same curve. The intro plays the take from frame 15 on, its 143
# frames retimed to the slot's 158 by interpolation rather than by repeating 15 frames.
set -e
cd "$(dirname "$0")/../.."
RIFE=${RIFE_DIR:?set RIFE_DIR to the rife-ncnn-vulkan release folder}
IN=shots/intro/out/overlay-v2.mp4
W=$(mktemp -d)
mkdir -p $W/a $W/a2 $W/b $W/b2
ffmpeg -v error -i $IN -vf "trim=end_frame=16" $W/a/%08d.png
ffmpeg -v error -i $IN -vf "trim=start_frame=15:end_frame=158" $W/b/%08d.png
$RIFE/rife-ncnn-vulkan -i $W/a -o $W/a2 -m $RIFE/rife-v4.6 -n 32 >/dev/null 2>&1
$RIFE/rife-ncnn-vulkan -i $W/b -o $W/b2 -m $RIFE/rife-v4.6 -n 158 >/dev/null 2>&1
ffmpeg -v error -y -framerate 30 -i $W/a2/%08d.png -vf "trim=end_frame=30,geq=lum='lum(X,Y)*pow(min(1,T/0.97),1.6)':cb='128+(cb(X,Y)-128)*pow(min(1,T/0.97),1.6)':cr='128+(cr(X,Y)-128)*pow(min(1,T/0.97),1.6)',format=yuv420p" -c:v libx264 -crf 12 shots/fadein/out/fadein-v3.mp4
ffmpeg -v error -y -framerate 30 -i $W/b2/%08d.png -vf "format=yuv420p" -c:v libx264 -crf 12 shots/intro/out/overlay-v3-from05.mp4
rm -rf $W
