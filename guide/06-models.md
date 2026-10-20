# 6. Model tests

This reel remakes a 30 s basketball edit with Dylan Patel in the player's place. Most of the picture is generated. A still model makes start and end frames and a character sheet, then a video model swaps him into each shot of the original clip. The rest is code and found footage.

Every row below is a model or tool that ran, or one that was weighed and not run. Runs and costs come from the per-run logs the scripts wrote. A run is one request, including the refused and failed ones.

## How the models were picked

The first image model was the convenient one. FLUX.2 on Workers AI gave generic faces, and Zeal said "these image edits suck dog". Zeal then named the two image models to test, GPT Image and Nano Banana. GPT Image 2.5 Sunburst made every frame in the reel after that.

For video, two Artificial Analysis leaderboards read on 2026-10-17 put Wan 3.0 first for video editing and MiniMax H3 first for image to video. Both were tested, plus Seedance 2.5.

Before you pick a model for any type of generation, open [aimv.gg/generators](https://aimv.gg/generators). It lists the current SOTA tools for each type, with the music videos made with them. Start from that list, then test on one shot.

## Every model and tool that ran or was weighed

A row is marked SOTA only when a dated public ranking or a named source backs it. Unmarked means not claimed, not that it is worse.

### Agent

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | Study the reference, write every prompt and script, run the tests, assemble the cut | Anthropic, Claude Code | n/a | not logged | used | no |

- **Claude Opus 5.5.** The agent read frames itself to study the reference, with no video model in the loop. It wrote the image and video prompts, the look-match, the newspaper renderer and the final assembly. Verdict: The agent for the whole reel. Its tokens, and what they would cost at Claude API list prices, are in `08-chat.md`.

### Image generation and edits

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| GPT Image 2.5 Sunburst | Character sheet, start and end frames, clean plates | OpenRouter, openai/gpt-image-2.5-sunburst on POST /api/v1/images with input_references | 51 | $2.45 | won | yes |
| GPT Image 2 | Character sheet | OpenRouter, openai/gpt-image-2 on POST /api/v1/images | 2 | $0.20 | lost | no |
| FLUX.2 dev | Swap the face, jersey and numbers on start frames | Cloudflare Workers AI, @cf/black-forest-labs/flux-2-dev | 6 | not logged | lost | no |
| FLUX.2 klein 9B | Swap the face and jersey on start frames | Cloudflare Workers AI, @cf/black-forest-labs/flux-2-klein-9b | 2 | not logged | refused | no |
| Nano Banana 2.1 | Character sheet | OpenRouter, google/gemini-nano-banana-2.1 | 2 | not logged | blocked | yes |

- **GPT Image 2.5 Sunburst.** 37 of 51 requests returned an image, at about $0.06 an image and $0.04 a plate. The order that worked was a six-view character sheet first, then the jersey, the numbers and the face on each frame. Width and height must both divide by 16, so 16:9 is 1792x1008. The model refused 11 frames that still showed the original player's face. Masking his head with a grey box removed him from the input before the edit, and the frames then went through. The error read `Your request was rejected by the safety system.` SOTA as of 2026-10-17. Zeal named GPT Image as one of the two SOTA image models on 2026-10-17, and the AIMV catalog that day listed GPT Image 2 and 2.5 as the most used keyframe models. Verdict: The image model for every frame in the reel.
- **GPT Image 2.** One character sheet for $0.20, after one request sent to the chat endpoint by mistake. Verdict: Sunburst made the sheet the reel used.
- **FLUX.2 dev.** 5 of 6 edits came back, with generic faces that did not look like Dylan. One was flagged. Zeal said "these image edits suck dog we should not be using workers ai for this". Verdict: Do not use it for likeness edits.
- **FLUX.2 klein 9B.** Both edits were refused on output. The error read `Your output has been flagged. Please choose another prompt / input image combination`. Verdict: Refuses frames of the original player.
- **Nano Banana 2.1.** Both requests were blocked for this account by the provider. SOTA as of 2026-10-17. Zeal named Nano Banana as one of the two SOTA image models on 2026-10-17. Verdict: Not tested. Try it through another provider before you rule it out.

### Video generation

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| Wan 3.0 | Swap Dylan into each shot of the original clip (video to video) | OpenRouter, alibaba/wan-3.0 on POST /api/v1/videos | 29 | $18.24 | won | yes |
| MiniMax Hailuo 3 | Intro shot from start and end frames (the control with no source clip) | OpenRouter, minimax/hailuo-3 on POST /api/v1/videos | 2 | $0.65 | lost | yes |
| Seedance 2.5 | Intro shot from the source clip, the sheet and an end frame | OpenRouter, bytedance/seedance-2.5 on POST /api/v1/videos | 4 | not logged | refused | no |
| Veo 3.1 | Generate between a start and an end frame | OpenRouter, not called | 0 | none | not-tried | no |
| Runway Aleph 2 | Re-skin the original clip from a prompt and a keyframe | OpenRouter, not called | 0 | none | not-tried | no |

- **Wan 3.0.** 27 of 29 runs completed; the other 2 failed before starting and were not billed. The working request sends the source span as an HTTPS video_url plus the character sheet, the headshots and the Sunburst start and end frames as images, with frame_images left empty. Pinning frame_images makes Wan drop the video reference, and the price is the tell. Frames only cost $0.43, against $0.88 for the same intro with the clip. Wan fills its whole duration and invents motion past the end of the source, so each span is slowed 2x to a whole number of seconds and sped back up after. A typical shot cost $0.50 to $0.90. On the celebration, frames only won, because the clip-driven runs copied the gold digits from the source and patched over them. Short video-to-video passes of about half a second fixed leftover pieces of the original player, for about $0.50 each. Zeal said "why is it $0.88 vs $0.43?" SOTA as of 2026-10-17. First on the Artificial Analysis video editing leaderboard, fourth for image to video. Verdict: The video model for every generated shot. Send the clip without frame_images, slow it first, and write the beard into the prompt.
- **MiniMax Hailuo 3.** The first request was rejected because it sent frames and reference images together. The frames-only run completed for $0.65, but the jersey number drifted from 67 to 97. The error read `MiniMax Hailuo video generations do not support frame_images and input_references in the same request`. SOTA as of 2026-10-17. First on the Artificial Analysis image to video leaderboard, as MiniMax H3. Verdict: It cannot take frames and references at once, and without the references the details drift.
- **Seedance 2.5.** One request failed because the video reference was not an HTTPS URL. The other three were refused on output, including a run with no video and one with the broadcast graphics redacted. The error read `The request failed because the output video may be related to copyright restrictions.` Zeal said "seedance is fuckin trippin lmao". Verdict: It refuses sports broadcast footage on output. It stays a good pick for footage you own.
- **Veo 3.1.** Weighed and dropped before the test. It ranked 13th for image to video, and it invents the motion instead of copying the clip. Verdict: Not tested.
- **Runway Aleph 2.** Weighed and dropped before the test. Zeal said "oh nm no aleph". Verdict: Not tested.

### Upscaling

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| SeedVR2 7B | Upscale the 1280x720 Wan shots | Modal, H100, H200 and B200 GPUs | 21 | $10.73 | won | no |
| SeedVR2 3B | Upscale the 1280x720 Wan shots | Modal, one H100 | 3 | $0.50 | lost | no |

- **SeedVR2 7B.** A first test ran 3B and 7B on three shots for $1.51 of GPU time, about $1.01 of it 7B by GPU seconds. 7B kept the beard, skin, piping and lettering and still looked like Dylan. The sweep then ran four variants on the soft shots for $9.72: 7B and the 7B sharp checkpoint at 1080, sharp with input noise, and sharp at 1440. Every 1080 run padded to 1088 and left a seam in the bottom row. Sharp at 1440 with a Lanczos resize to 1080 won every scene, for example Laplacian sharpness 39 to 101 on the alley-oop. Verdict: Use the 7B sharp checkpoint at 1440, then resize to 1080.
- **SeedVR2 3B.** It ran in the same test as 7B, about $0.50 of the $1.51 by GPU seconds. It sharpened, but it pinched Dylan's features on the celebration, smeared the gold numbers, and let the face drift on the datacenter shot. Run locally at 1080p, it ran a Mac out of GPU memory. Verdict: Faster, but it bends faces.

### Retiming and interpolation

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| RIFE | In-between frames for a 60 fps master | rife-ncnn-vulkan locally, Practical-RIFE on Modal, RIFE v4.6 | n/a | $0.71 | lost | no |

- **RIFE.** The in-betweens had half the detail at whip pans, morphed across cuts (a doubled channel tag), and melted the white flashes. The cut detector also read whips as cuts. Zeal said "30 is goated". Verdict: Ship 30 fps. Do not interpolate an edit full of whips, flashes and text.

### Stem separation

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| Demucs | Split the reference audio to mute the announcer | local, htdemucs, then htdemucs_ft four-stem | n/a | $0.00 | used | no |

- **Demucs.** The announcer sat only in the vocal stem, and muting two windows of it removed his words. A later audit found the stems do not sum back to the original. The residual was 19 dB down, the build at 9 to 10 s lost 3 dB, and muting killed a held sung note, the hook, the width and the reverb. Verdict: Use stems to find words, not to rebuild the mix. The reel keeps the original mix everywhere except the announcer's words.

### Speech to text

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| Deepgram Nova-3 | Transcribe the announcer over the music, with word times | Cloudflare Workers AI, @cf/deepgram/nova-3 | 2 | not logged | won | no |
| faster-whisper medium.en | Find the takes in Zeal's voice memos | local CPU, medium.en, vad_filter off | n/a | $0.00 | used | no |
| faster-whisper small.en | Transcribe the announcer over the music | local CPU, small.en, int8 | 1 | $0.00 | lost | no |
| Whisper large-v3 turbo | Transcribe the announcer over the music | Cloudflare Workers AI, @cf/openai/whisper-large-v3-turbo | 2 | not logged | lost | no |

- **Deepgram Nova-3.** Run on the full mix and on the vocal stem. 1.2 s for the 30 s clip, the right line, and clean word times (looking 1.36 s, james 1.84 s). Verdict: Fastest and the only one with no invented text. Use it for spoken lines over music.
- **faster-whisper medium.en.** Whisper transcribed only the first take of a memo, so each memo was split at pauses of 0.8 s or more first (0.5 s split words). Verdict: Split long recordings at pauses before you transcribe them.
- **faster-whisper small.en.** 2.4 s and the right line, then the classic invented "Thanks for watching!" over the silence at the end. Verdict: Good and free, but drop any segment that falls in a quiet stretch.
- **Whisper large-v3 turbo.** 5.9 s, the right line, plus an invented second "He's got it." at 30.0 s. Verdict: Slowest of the three, and it also invents text in silence.

### Mattes and masks

| Model or tool | Job | Provider and endpoint | Runs | Cost | Outcome | SOTA |
| --- | --- | --- | --- | --- | --- | --- |
| MediaPipe person segmentation | Matte the person holding Dylan's face so he pops in the podcast fast cuts | local, Image Segmenter | n/a | $0.00 | used | no |
| Apple Vision foreground mask | Matte the generated profile shot over the original plate in the ending | macOS, VNGenerateForegroundInstanceMaskRequest | n/a | $0.00 | used | no |

- **MediaPipe person segmentation.** The matte drove four pop treatments, a print room, a halation wrap (a soft glow around his outline), burn hits and a mix of the three. The original's face-to-room brightness was 2.18 and the raw podcast frame 1.0; the halation wrap reached 1.89. Claude's ranking picked the mix, and Zeal overruled it. Zeal said "b2b p2 is goated". Verdict: Good enough for a fast cut, where each matte is on screen for a few frames.
- **Apple Vision foreground mask.** The Sunburst side frames were made on a keyable background, which gave Vision an easy edge. Verdict: Clean on a plain background. macOS only.

## Cost

The per-run logs kept with the code add up to $21.54 of image and video generation, the cost each request reported. The short fix-up passes have no log rows, so the real figure is a little higher.

GPU time on Modal came to $11.95 on the billing report. The SeedVR2 sweep was $9.72, the first 3B and 7B test $1.51 (split between the two SeedVR2 rows by GPU seconds), and RIFE $0.71, each rounded to the cent.

One experiment is out of this guide's scope. Zeal ran [TRIBE v2](https://github.com/facebookresearch/tribev2), Meta's model that predicts how a brain responds to video, over some of the cuts on Modal. The signals were weak and it decided no pick. Right now it feels closer to pseudoscience than to a ruler, though with a couple of dollars it is fun to fiddle with. Its GPU time is not in the $11.95. Opus 5.5 and Modal are enough to try it, since few readers have a GPU big enough at home. A write-up is coming, so follow Zeal ([@zealcaiden](https://x.com/zealcaiden) on X, [zealous1](https://github.com/zealous1) on GitHub) and AIMV ([@aimvgg](https://x.com/aimvgg), [aimvgg](https://github.com/aimvgg)) to catch it.

The overlays (scorebug, banner, name, newspaper) are drawn in code, not generated. Zeal's rule was to get the clip right in the video model and add everything else with software, to keep random generated detail to a minimum.

This page is generated from `models.json` by `render_models.py`, which ships in the `aimv-recipe` skill of [claude-video-editing-skills](https://github.com/zealous1/claude-video-editing-skills) (`skills/aimv-recipe/template/tools/`). Edit the JSON and rerun it. The JSON also holds each row's AIMV id.
