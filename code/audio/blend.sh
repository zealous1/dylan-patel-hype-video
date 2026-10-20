#!/bin/bash
# Sits Zeal's line (memo 3 take 5, +4 dB, from audio/patels) inside the track instead of on top of it: the voice
# loses 3 dB under 300 Hz and gains 2 dB at 3 kHz to match the announcer's low-to-presence balance, and the music
# ducks about 2 dB under the line through a sidechain, as a broadcast mix would.
#   audio/blend.sh   writes audio/mix-patel-memo3-5-blend.wav
set -e
cd "$(dirname "$0")/.."
V=audio/voice/memo3-take5-line-g4.wav
ffmpeg -hide_banner -v error -y -i audio/no-announcer-v2.wav -i $V -filter_complex \
  "[1]lowshelf=f=300:g=-3,equalizer=f=3000:t=q:w=1:g=2,aformat=channel_layouts=stereo,asplit[v][key];\
[0][key]sidechaincompress=threshold=0.05:ratio=3:attack=15:release=250:makeup=1:mix=0.6[m];\
[m][v]amix=inputs=2:normalize=0,atrim=0:30.07" -c:a pcm_s24le audio/mix-patel-memo3-5-blend.wav
echo wrote audio/mix-patel-memo3-5-blend.wav
