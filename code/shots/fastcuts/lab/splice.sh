#!/bin/sh
# Splices each podcast-lab section into the base reel (BASE, default v5): frames 415 to 623 of final-$BASE-worn-30-master.mp4 (no film
# pass there) become the variant's 209 frames; x264 CRF 8; the audio is copied untouched. Each master also gets an
# -upload file in render.py's upload encode (High 4.2, 24M, 30M max rate), which is what the lab page plays: Chrome
# failed to decode the level 6.2 masters partway through.
#   sh shots/fastcuts/lab/splice.sh B2=v16-b2 B2-P1=v16-p1 ...     (run from the reel root; BASE=v3 for round 1's reels)
# A name that starts with final- is the output's own name: final-v6-E1=v17-e1 writes final-v6-E1-master.mp4.
set -e
BASE=${BASE:-v5}
for pair in "$@"; do
  V=${pair%%=*}; sec=${pair#*=}
  case $V in final-*) stem=master/out/$V ;; *) stem=master/out/final-$BASE-pod-$V ;; esac
  out=$stem-master.mp4
  ffmpeg -v error -y -i master/out/final-$BASE-worn-30-master.mp4 -i shots/fastcuts/out/fastcuts-$sec.mp4 -filter_complex \
    "[0:v]trim=end_frame=415,setpts=PTS-STARTPTS[a];[1:v]trim=end_frame=209,setpts=PTS-STARTPTS[b];[0:v]trim=start_frame=624,setpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=1:a=0,format=yuv420p[v]" \
    -map '[v]' -map 0:a -c:v libx264 -preset slow -crf 8 -c:a copy -movflags +faststart "$out"
  up=$stem-upload.mp4
  ffmpeg -v error -y -i "$out" -map 0:v -map 0:a -c:v libx264 -preset slow -profile:v high -level 4.2 -b:v 24M -maxrate 30M -bufsize 60M \
    -pix_fmt yuv420p -g 30 -c:a copy -movflags +faststart "$up"
  for f in "$out" "$up"; do
    n=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$f")
    echo "$f $n frames"
    [ "$n" = 902 ]
  done
done
