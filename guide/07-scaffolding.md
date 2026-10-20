# 7. The tools built before the first shot

Before any shot was generated, the reference was measured and the review tools were built. Each answered one question.

| Built | Question it answered | What it changed |
| --- | --- | --- |
| `analysis/transitions/measure.py` with FFmpeg `scdet` and `signalstats` | Where are the cuts, flashes and grey stretches? | 13 cuts and 5 white flashes found in 20 s, so only 10 contact sheets were needed |
| `analysis/flicker/measure.py` | How does the end flicker? | A 15 Hz strobe at ±13%, 2 to 10% end flicker and a black floor of 22 to 25, which the film look borrows |
| librosa beat grid and the 9.0 s dropout | What is everything timed to? | Every slot snaps to the song |
| ASR bake-off | Which word times can be trusted? | faster-whisper for the memos; Whisper invents text over silence, so memos were split at pauses first |
| Cut player with `takes.json` | Does this take work in the video, not alone? | Every swap was heard against the mix |
| `shots/lookmatch.py` | Does a generated take measure like the reference? | Grade, gain and blur matched by numbers |
| The Arcmira search log | Is each on-screen tag literally true? | Three hand-picked beats re-sourced |

## What they made possible

Once the measuring tools existed, each decision became a round of candidates with numbers beside them, and Zeal picked by eye from a short list. [4. Checkpoints](04-checkpoints.md#what-made-the-rounds-fast) lists the rounds. From the first full render to the shipped one took about nine hours and eleven checkpoints.

**Next.** [8. Chat](08-chat.md) sums up the chat that directed it all.
