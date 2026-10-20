#!/bin/bash
# Lays Zeal's "Looking for Patel, he's got it!" (voice memo, take 4 of 5) over the muted announcer at 1.15 to 2.95 s.
# The take is cut into its two phrases and each is placed on the original's: the onset of "Patel" (take 0.80 s) on
# "James" (reel 1.81 s), and "He's" (take 1.46 s) on "he's" (reel 2.33 s), per faster-whisper word times of both.
# A broadcast chain (band limit, compression, a short arena slap) and a level match to the original announcer follow.
#   audio/patel-voice.sh [gain_db]
set -e
cd "$(dirname "$0")/.."
G=${1:-0}
T=audio/voice/take4.wav
chain="highpass=f=140,lowpass=f=6800,acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4,aecho=0.8:0.5:45|95:0.22|0.12,volume=${G}dB"
ffmpeg -hide_banner -v error -y -i $T \
  -filter_complex "[0]atrim=0.30:1.33,asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st=0.99:d=0.04,adelay=1310:all=1[a];[0]atrim=1.40:2.30,asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st=0.84:d=0.06,adelay=2270:all=1[b];[a][b]amix=inputs=2:normalize=0,aresample=44100,$chain,apad=whole_dur=30.07,atrim=0:30.07" audio/patel-voice.wav
ffmpeg -hide_banner -v error -y -i audio/no-announcer-v2.wav -i audio/patel-voice.wav -filter_complex "[1]aformat=channel_layouts=stereo[v];[0][v]amix=inputs=2:normalize=0,atrim=0:30.07" audio/mix-patel-v1.wav
echo wrote audio/mix-patel-v1.wav

# v2: the same full line, 8 dB hotter.
if [ "${2:-}" = "all" ]; then
  "$0" 8 && mv audio/mix-patel-v1.wav audio/mix-patel-v2.wav && "$0" 0
fi
