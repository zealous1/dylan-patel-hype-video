# 4. Checkpoints and taste calls

This is the story page. It lists every version good enough to post, why each one was not the last, and the calls Zeal made by eye. Times are Pacific, from the render files. The chat turns behind each checkpoint are in [`08-chat.md`](08-chat.md).

## The path to each publishable checkpoint

A checkpoint is a full 902-frame render that passes the automatic checks (902 frames, audio to the last frame, loudness, true peak; see the `check-video-render` skill). The first full render, C0, landed on the morning of 10-17. Everything after it was last-mile direction, eleven checkpoints over nine hours.

| Checkpoint | When | What changed | Why it was not the last |
| --- | --- | --- | --- |
| Swaps | 10-16, 23:35 | First Wan 3.0 take for every swapped shot, at real time | Takes only, no video yet |
| C0 | 10-17, 10:14 | First full render, at 30 and 60 fps. Every scene, with the original audio and the announcer muted. **The first usable cut** | Muting a stem lost music. No film look yet, and the podcast section was still hand-picked |
| C1 | 12:41 | Worn film pass at 30 fps | Soft generated shots |
| C2 | 14:32 | The six softest shots upscaled with SeedVR2 | Audio still muted, not replaced |
| C2d | 15:17 | Audio D. The reference mix everywhere except the announcer's words, which are Zeal's voice | Upscale not yet picked from the sweep |
| C3 | 15:29 | Upscale C (7B at 1440) chosen over A, B and Lanczos | Podcast section needs to be the real searches |
| C3-pod A to D | 17:19 | Four podcast sections, every beat re-sourced through search | B won, then B2 added the Jensen zoom-through |
| C4 | 18:05 | Lowercase searches on the jersey and the profile | Opener |
| C5 | 18:21 | The name2 opener, DYLAN then PATEL, burnt into the first 0.6 s | Dylan does not pop off the podcast clips |
| C5-pod B2 P1 to P4 | 18:33 to 18:40 | Four ways to make him pop | P2 picked |
| C6 | 18:53 | B2 with P2 halation | The hero shot needs a finish |
| **C6-S2, shipped** | 19:21 | A Super Saiyan 2 (SSJ2) cel-shaded aura with lightning on the hero's last 12 frames | |

## What made the rounds fast

Before any shot was generated, the reference was measured and the review tools were built ([7. Scaffolding](07-scaffolding.md)). Once the measuring tools existed, each decision became a round of candidates with numbers beside them on one lab page, and Zeal picked by eye from a short list.

- **Audio.** Four mixes, A to D, measured for loudness, band balance and stereo width.
- **Upscale.** A, B, C and Lanczos across six shots, scored by sharpness.
- **Frame rate.** 30 against 60, with sharpness at whips and cut crossings.
- **Film.** Worn, Classic and Match.
- **Opener.** Four.
- **Podcast section.** A to D, then B2, then P1 to P4, then S1 to S3.

Each round turned in minutes because the render scripts take `--scenes` and `--tag`, so candidates never overwrite each other.

## The reversal that changed the sound

The first plan for the announcer was to mute him. Demucs split the song into four stems, and muting his vocal stem sounded fine on its own. Then an audit summed the stems back and compared them with the original. They did not match. A held sung note, the hook before the outro and the reverb had gone out with the announcer. So mix D keeps the original mix whole and swaps only his two lines for Zeal's phone voice memos. Zeal's verdict was "I love audio D."

## Last-mile creative direction

Zeal's calls, in Zeal's own words where the chat has them.

| Call | Why | Replaced |
| --- | --- | --- |
| "keep most of the basketball (make it dylan)" | The original works; change the person, keep the craft | A from-scratch video |
| Overlays "after the fact with software overlay. we just need to get clip right" | Text and graphics from a model are random; software is exact | Generated scorebugs and banners |
| "rly important to get that light beard right" | The likeness lives in the beard | Full, bushy beards in early takes |
| "all patel frames will be 67" | One jersey number everywhere | Mixed numbers |
| Worn film | Matches the reference's projector feel at its end | Classic and Match looks |
| "30 is goated" | The newspaper reads clearer at 30 fps; RIFE smeared text at 60 | 60 fps |
| "I love audio D." | Keeps the song whole and only swaps the words | Muted vocal stem (mixes A to C) |
| Upscale C | Laplacian sharpness up 2x to 2.6x, no seam | SeedVR2 3B, 7B at 1080, Lanczos |
| name2 opener | "there are other people's names that show up in the clip"; his name has to come first | Face flash, logo burn, broadcast intro |
| Zoom-through B, then B2 | Center his face like the original; the zoom carries into the next shot. "b is better... officially" | A, C and D |
| "b2b p2 is goated" | Halation wraps him without whitening the tags | P1, P3, P4 (Claude's ranking had picked P4) |
| SSJ2 aura, S2 | One finish on the hero, on the kick at 20.4 s | Eye fire, energy eyes, S1, S3 |
| "make all the searches lowercase" | They read as real queries | Title-case tags |
| Speaker first in the tag | "changing query by deleting everything is weird" | Query-first tags |
| Jersey stays video | "way less vibey when they're not both video" | A still under the crossfade |
| 16:9 only | "I don't think we're going to go vertical on this." | A vertical cut |

## Dropped ideas

| Idea | Tried as | Why it was dropped |
| --- | --- | --- |
| Eye fire | An aura pass on the hero | "i see fire and i don't like it" |
| Energy eyes | Glow jets from the eyes | "jets go way too high" |
| 60 fps | RIFE v4.6 in-betweens | Half the detail at whips, morphs across cuts, a doubled tag |
| Muting the announcer's stem | Mixes A to C | The stems do not sum back to the original; a held note, the hook and the reverb went with it |
| Broadcast intro opener | A generated intro ($0.97) | Slower and quieter than the name burn |
| Generated graphics | Model-drawn scorebug and banners | Random each run; drawn in software instead |
| Workers AI FLUX.2 for stills | The first character sheet | "these image edits suck dog"; generic faces |
| Three-line search tags | Clip, source and search on screen | "second line is fuckin ipossible to read" |

**Next.** [5. Storyboard](05-storyboard.md) lays every take of every shot on the reference's clock.
