#!/bin/bash
# The original announcer back in ("Looking for James, he's got it"), with only "James" (reel 1.81 to 2.23 s) cut out
# of the vocal stem and Zeal's "Patel" (take 4, 0.74 to 1.26 s) dropped in its place, through the same broadcast chain.
# The fade-out yell at 23.6 to 26.4 s stays muted as in no-announcer-v2.
#   audio/patel-swap.sh [gain_db=4]   writes audio/mix-patel-swap.wav
set -e
cd "$(dirname "$0")/.."
G=${1:-4}
S=stems/htdemucs_ft/audio
gate="volume='clip((abs(t-2.02)-0.20)/0.03,0,1)*clip((abs(t-25.0)-1.4)/0.06,0,1)':eval=frame"
chain="highpass=f=140,lowpass=f=6800,acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4,aecho=0.8:0.5:45|95:0.22|0.12,volume=${G}dB"
ffmpeg -hide_banner -v error -y -i audio/voice/take4.wav \
  -filter_complex "[0]atrim=0.74:1.26,asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st=0.44:d=0.08,adelay=1760:all=1,aresample=44100,$chain,aformat=channel_layouts=stereo,apad=whole_dur=30.07,atrim=0:30.07" audio/voice/patel-word.wav
ffmpeg -hide_banner -v error -y -i $S/drums.wav -i $S/bass.wav -i $S/other.wav -i $S/vocals.wav -i audio/voice/patel-word.wav \
  -filter_complex "[3]${gate}[v];[0][1][2][v][4]amix=inputs=5:normalize=0,atrim=0:30.07" audio/mix-patel-swap.wav
echo wrote audio/mix-patel-swap.wav
