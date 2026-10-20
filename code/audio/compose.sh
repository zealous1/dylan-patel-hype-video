#!/bin/bash
# Rebuilds the reel's audio from the four htdemucs_ft stems with the announcer muted between A and B seconds
# (60 ms ramps), in three variants, and muxes each over the original video for listening.
#   compose.sh [A=1.15] [B=2.95]
set -e
cd "$(dirname "$0")/.."
A=${1:-1.15} B=${2:-2.95}
S=stems/htdemucs_ft/audio
C=$(echo "($A+$B)/2" | bc -l) H=$(echo "($B-$A)/2" | bc -l)
gate="volume='clip((abs(t-$C)-$H)/0.06,0,1)':eval=frame"
inside="volume='1-clip((abs(t-$C)-$H)/0.06,0,1)':eval=frame"
mix4='[0][1][2][v]amix=inputs=4:normalize=0'
ffmpeg -hide_banner -v error -y -i $S/drums.wav -i $S/bass.wav -i $S/other.wav -i $S/vocals.wav \
  -filter_complex "[3]$gate[v];$mix4,atrim=0:30.07" audio/no-announcer.wav
# Same, but the vocal stem's top end (squeaks, crowd hiss) stays in the gap at -6 dB.
ffmpeg -hide_banner -v error -y -i $S/drums.wav -i $S/bass.wav -i $S/other.wav -i $S/vocals.wav \
  -filter_complex "[3]asplit[a][b];[a]$gate[g];[b]highpass=f=4500,highpass=f=4500,volume=0.5,$inside[hi];[g][hi]amix=inputs=2:normalize=0[v];$mix4,atrim=0:30.07" audio/no-announcer-keep-highs.wav
ffmpeg -hide_banner -v error -y -i $S/vocals.wav -filter_complex "[0]$inside,atrim=$(printf %.2f $(echo "$A-0.3"|bc)):$(printf %.2f $(echo "$B+0.3"|bc))" audio/announcer-only.wav
for f in no-announcer no-announcer-keep-highs; do
  ffmpeg -hide_banner -v error -y -i src/clip.mp4 -i audio/$f.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest audio/$f.mp4
done
ffmpeg -hide_banner -v error -y -i src/clip.mp4 -t 5 -c copy audio/original-first5.mp4
echo "muted $A to $B s"

# v2 (2026-10-17): also mutes the vocal stem from 23.6 to 26.4 s, where the announcer yells "LeBron! LeBron! He's
# trying to get in here!" over the fade out. Whisper on the result hears only the song's own vocal before 23.2.
S=stems/htdemucs_ft/audio
two="volume='clip((abs(t-2.05)-0.9)/0.06,0,1)*clip((abs(t-25.0)-1.4)/0.06,0,1)':eval=frame"
ffmpeg -hide_banner -v error -y -i $S/drums.wav -i $S/bass.wav -i $S/other.wav -i $S/vocals.wav \
  -filter_complex "[3]${two}[v];$mix4,atrim=0:30.07" audio/no-announcer-v2.wav
ffmpeg -hide_banner -v error -y -i $S/vocals.wav -filter_complex "[0]volume='1-clip((abs(t-25.0)-1.4)/0.06,0,1)':eval=frame,atrim=23.3:26.7" audio/fade-announcer-only.wav
