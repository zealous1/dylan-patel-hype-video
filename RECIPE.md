# Recipe: Dylan Patel hype video

| | |
| --- | --- |
| Video | https://x.com/zealcaiden/status/2112239444040499475, 30.07 s, 16:9, 1920x1080, 30 fps, 902 frames |
| Artist | Zeal Caiden |
| Kind | hype-edit |
| Method | hybrid: generated shots, code-rendered graphics, edited footage |
| Agent | Claude Code (Claude Opus 5.5) |
| Models | Wan 3.0, GPT Image 2.5 Sunburst, SeedVR2 7B |
| Tools | Arcmira MCP, yt-dlp, FFmpeg, Demucs, faster-whisper, OpenCV, MediaPipe, OpenRouter, Modal, headless Chrome |
| Time | 2026-10-16 to 2026-10-17 Pacific, two days, 167 messages from Zeal |
| Cost | $21.54 of logged image and video generation (Wan 3.0 $18.24, GPT Image 2.5 Sunburst $2.45, and in tests Hailuo 3 $0.65 and GPT Image 2 $0.20), plus $11.95 of Modal GPU time (SeedVR2 $11.24, RIFE $0.71). The half-second fix-up passes have no log rows. Details in `guide/06-models.md` |
| People | Dylan Patel. Jensen Huang appears in one keynote clip |

The reference is a 30 s basketball hype video (see `sources.json`). Its cuts, timing, camera moves, flicker and audio bed are the spec. Everything that named or showed the original player was swapped or redrawn, and everything else was kept.

## Steps

Commands run from `code/`. `python -I` is short for `uv run --no-project --with-requirements requirements.txt python -I`, as `code/README.md` explains.

### 1. Measure the reference

**With FFmpeg and Claude Code.** Measured the reference before looking at it: hard cuts, white flashes and grayscale stretches with FFmpeg `scdet` and `signalstats` over all 900 frames, then contact sheets only around flagged moments.

`setup/fetch.py` keeps YouTube's 1080p H.264 stream as downloaded, which has the run's 900 frames. A converted fallback format can come out at 899 frames and 29.97 s. The fetch stops unless the clip has 900 frames, because the ending reads the reference up to frame 899.

`analysis/transitions/measure.py` and `analysis/flicker/measure.py` record per-frame luma, sharpness, shift and the film flicker that the last stage borrows. Beats came from librosa (143.6 BPM). The reference has a one-second music dropout at 9.0 s that everything else is timed around.

### 2. Find every podcast beat by search

**With the Arcmira MCP.** Found each podcast beat with one `arcmira.search`, most of them filtered to Dylan's speaker id, one episode per beat, and printed each search on screen.

Resolve the name once (`arcmira.resolve("Dylan Patel", { context: "SemiAnalysis" })`), then search one word per call: nvidia, trillion, stargate, huawei, insane. `arcmira.transcript` with a 30-second window gives the lines around each hit. Transcript times are not cut points; the cut lands in a silence that `silencedetect` reports. The Jensen beat came from a web search for SemiAnalysis news, done for the newspaper headlines. Zeal builds Arcmira, so Zeal added the keynote to the index with a Premium transcript that labels Jensen. Its search on screen, Jensen Huang's speaker id and the query "semianalysis", ran after that and returns another upload of the keynote. The video cuts NVIDIA's own upload, which has captions only. If a video you need is not in the index, have your agent ask for it with `arcmira_feedback`. `arcmira.mentions` on Dylan gives the closing line. The exact inputs are in `sources.json`. A tag has to be literally true, so three early beats picked by hand were re-sourced through search.

### 3. Swap only the announcer's words

**With Demucs.** Kept the reference mix everywhere except the announcer's two lines, and replaced only his words with Zeal's own voice.

Demucs `htdemucs_ft` splits the stems. `audio/audit/restore.py` separates the announcer from the song's vocal using the mono announcer's empty side channel. Muting the vocal stem instead lost a held note, the hook before the outro, and the reverb, because the four stems do not sum back to the original. The new lines were recorded as phone voice memos, split at pauses of 0.8 s or more, placed by cross-correlation against the lines they replace, EQ'd toward the announcer and raised 2 dB. `audio/audit/build.py` renders mix D, which lands at the reference's own -10.4 LUFS.

### 4. Draw the character sheet and the start frames

**With GPT Image 2.5 Sunburst.** Built a six-view character sheet first, then the jersey, the numbers and the face, then one start and end frame per swapped shot.

`starts/gen.mjs` calls OpenRouter `POST /api/v1/images` with `input_references`, about $0.06 an image. Sizes must divide by 16; 16:9 is 1792x1008. Every jersey is number 67. Workers AI FLUX.2 was tried first. It gave generic faces and refused the reference frames.

### 5. Swap Dylan in, shot by shot

**With Wan 3.0.** Swapped Dylan into each shot by video-to-video, with the source span, the sheet and the start and end frames as references.

Wan 3.0 copies the source clip only when `frame_images` is empty. Pin frames and it drops the clip without an error. The bill gave it away. The same intro cost $0.43 with frames and $0.88 with the clip, and Zeal asked "why is it $0.88 vs $0.43?"

`shots/vid.mjs <shot>` sends `input_references` = the span as an HTTPS `video_url`, the sheet and headshots, and the start and end frames as images, with `frame_images` empty. The span is slowed 2x to a whole number of seconds first and sped back up after, because Wan fills its duration and invents motion past the end of the source. About $0.50 to $0.90 a shot. The flags differ by shot, and `code/README.md` lists them. On the celebration, frames-only image-to-video won, because the clip-driven run copied the scoreboard digits. Seedance 2.5 refused broadcast footage on output, and Hailuo 3 cannot take frames and references together.

### 6. Grade every take to the reference

**With OpenCV.** Graded and blurred every generated take frame by frame to measure like the reference, and redrew the scorebug (the broadcast's score box) and the banners in software.

`shots/lookmatch.py` matches quantile colour curves, a spatial gain grid and the blur type. `shots/intro/graphics.py` draws the scorebug and banner. Where bits of the original player survived, a second video-to-video pass over about half a second fixed them, about $0.50 each. The datacenter sign was painted out with one clean plate aligned to every frame by OpenCV ECC and matted around Dylan (`shots/datacenter/post/designify.py`).

### 7. Render the newspaper

**With headless Chrome.** Rendered the newspaper as an HTML canvas page, frame by frame over the DevTools protocol, starting on the celebration's last frame.

`node shots/newspaper/render.mjs paper-v4` captures `paper.html` layers at 3840x2160 in four horizontal strips (one multi-megabyte screenshot stalled the socket) and composites the whip in `compose.html`. Every fact on the page was checked against a public source.

### 8. Cut the podcast section

**With OpenCV and MediaPipe.** Cut ten clips from ten videos, nine of Dylan and one of Jensen Huang, into 7 seconds. A face-matched zoom-through carries each into the next, a halation wrap (a soft glow bleeding around his outline) makes Dylan pop, and each clip carries its search as a lowercase tag.

`python -I shots/fastcuts/build.py edl-v18-s2.json`. The edit list is named relative to `shots/fastcuts/`. Faces are tracked with OpenCV, and each clip is placed so the face lands where the last one was; face wander across cuts fell from 6 to 9% of the frame to 2%. The wrap rides a MediaPipe selfie-segmentation matte. Tags read the channel name, then `arcmira.search(speaker: "dylan patel", query: "nvidia")`, in white at about 85%. The section ends on the generated datacenter hero, with a cel-shaded Super Saiyan aura and lightning on its last 12 frames.

### 9. Build the ending

**With Wan 3.0 and Apple Vision.** Built the ending: the jersey from behind, a breathing side profile cut out by a Vision matte, and the SemiAnalysis logo where the original's logo was.

The face and logo pulse with opacity curves measured from the reference (`shots/profile/build.py`). `arcmira.mentions(entity: "dylan patel")` rides above the jersey and is gone 0.1 s before it. The ending takes thirteen commands, listed in order in `code/README.md`.

### 10. Upscale the soft shots

**With SeedVR2.** Upscaled the six softest shots with SeedVR2 7B at 1440 and Lanczos down to 1080 on a Modal H100.

`modal run shots/upscale-sweep/modal_seedvr2.py --variants C --shots rim,celebrate,fadeout,alleyoop,backdown,fadeaway`, then `sh shots/upscale-sweep/collect.sh` and `python -I shots/upscale-sweep/rebuild.py --tag sr --src <shot>=shots/upscale-sweep/out/<shot>-C.mp4,...`. `code/README.md` gives the full command. At 1080 the model pads to 1088 and leaves a seam on the bottom row, so render at 1440. Laplacian sharpness rose 2x to 2.6x per shot. A local Apple-silicon run ran out of memory.

### 11. Assemble, add the film look and the opener

**With FFmpeg.** Assembled the takes at 30 fps, added the Worn film look (one of three film passes tested, see `guide/04-checkpoints.md`), burned DYLAN and PATEL into the first 0.6 s, and spliced in the podcast section.

```
python -I master/render.py --scenes master/scenes-v4.json --tag v4 --fps 30 --mix audio/audit/out/d-hotter-voices.wav
BASE=v4 MIX=audio/audit/out/d-hotter-voices.wav python -I shots/film/film.py --final worn 30
OPENER_BASE=master/out/final-v4-worn-30-master.mp4 python -I shots/opener/build.py face2 name2
cp shots/opener/out/opener-name2.mp4 master/out/final-v5-worn-30-master.mp4
BASE=v5 sh shots/fastcuts/lab/splice.sh final-v6-S2=v18-s2
```

Run the opener as `face2 name2` so the random burn pattern matches. Its `face2` reads a SeedVR2 upscale of the datacenter take, which `code/README.md` step 11 makes first. 60 fps was rendered with RIFE and dropped. The in-betweens smeared the newspaper, the cuts and the tags. The film look borrows the reference's measured flicker. Do not use `-shortest`; it cut 3 frames once.

### 12. Check every candidate

**With FFmpeg and the `check-video-render` skill.** Checked every candidate before anyone watched it, for 902 frames, audio to the last frame, loudness, true peak, and a share copy that plays in a browser.

The splice asserts 902 frames. The other checks come from the `check-video-render` skill in [claude-video-editing-skills](https://github.com/aimvgg/claude-video-editing-skills). The CRF 8 master is H.264 level 6.2, which Chrome cannot decode, so the share copy is level 4.2. An earlier mix went silent for its last second; the silent-tail check catches that now.

## Taste calls that shaped it

- Keep most of the original and change the person. Draw text and graphics in software instead of generating them.
- Get the light beard right in every face match.
- 30 fps, because the newspaper reads clearer at 30.
- Searches on screen are the real searches, lowercase, speaker first.
- Open on Dylan's name, because other names appear in the source.
- One aura on the hero's last frames, not eye fire.
- 16:9 only.

The full list, in Zeal's own words with what each call replaced, is in `guide/04-checkpoints.md`.

## Rights

The reference edit, its song, the broadcast footage, the podcast clips and the keynote belong to their owners and are not in this repo. Generated shots made from broadcast footage are left out too.
