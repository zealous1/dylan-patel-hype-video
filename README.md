# Dylan Patel hype video

A remake of a viral 30-second LeBron hype video, with Dylan Patel of SemiAnalysis in LeBron's place. The basketball shots follow the original cut for cut, and the middle is Dylan's own words, found by search. Directed in Claude Code over two days. The image and video generation and the GPU time cost $33.49, on OpenRouter and Modal. Claude Code ran on Zeal's Claude subscription.

<p align="center"><img src="assets/newspaper-to-podcast.gif" width="520" alt="The SemiAnalysis $100 million newspaper cuts into the podcast section, where each clip shows the Arcmira search behind it"></p>

**[Watch the hype video](https://x.com/zealcaiden/status/2112239444040499475)** · [How it was made](#how-it-was-made) · [Recipe](RECIPE.md) · [Get the skills](https://github.com/aimvgg/claude-video-editing-skills)

- Every basketball shot keeps the original's cut, timing and camera move. Wan 3.0 swapped Dylan in by video-to-video.
- The podcast section is ten clips in seven seconds, nine of Dylan and one of Jensen Huang talking about him. [Arcmira](https://arcmira.com) is a search engine for what people say in podcasts and videos. It knows who is speaking, so a search can ask for one person's own words, and it returns the second each line starts. Each clip shows the search behind it.
- Every script, prompt, take and taste call is here. No footage ships. `sources.json` links each clip at its second.

By [Zeal](https://x.com/zealcaiden). One of n videos in [the family](#the-family), with the skills they became.

Zeal builds Arcmira, so the Arcmira parts of this repo are its maker using it. Every Arcmira call is logged in [`guide/research-calls.json`](guide/research-calls.json).

## How it was made

1. **Measure the reference.** FFmpeg found every cut, flash and grayscale stretch in its 900 frames. The original's audio became the clock for everything after.
2. **Swap the player.** GPT Image 2.5 Sunburst drew a six-view character sheet of Dylan and a start and end frame for each shot. Wan 3.0 swapped him into each basketball shot by video-to-video, for about $0.50 to $0.90 a shot. Pinning the frames made Wan quietly drop the clip. The bill gave it away, at $0.43 against $0.88 for the same intro.
3. **Match the look.** OpenCV graded every generated take to measure like the reference. The scorebug (the broadcast's score box) and the banners were redrawn in code, because a model draws them differently every run.
4. **Find the podcast clips.** Each of the ten podcast beats shows an Arcmira search, most of them filtered to Dylan's own words. A face-matched zoom carries each clip into the next.
5. **Replace the announcer.** Muting his stem took a held note, the hook and the reverb with it, because the Demucs stems do not sum back to the song. So the final mix keeps the original and swaps only his two lines for Zeal's phone voice memos.
6. **Finish.** SeedVR2 upscaled the six softest shots on Modal, and a worn film pass matched the reference's projector look.

[RECIPE.md](RECIPE.md) has all twelve steps with commands. The guide below has every search, take and taste call.

## The searches on screen

Every podcast beat in the hype video shows the search behind it. Late in the build, an audit found three beats that had been picked by hand at round timestamps. Their tags were not true, so all three were re-sourced through search before the video shipped.

| Video s | Show | A line from the passage | The search |
| --- | --- | --- | --- |
| 13.84 | a16z | "They got to 2 nanometer before Nvidia." | `nvidia`, speaker Dylan Patel, since 2024 |
| 14.23 | Matthew Berman | "...the solder balls connecting the chip and the board would crack." | same |
| 14.65 | a16z | "Like they're saying, don't buy Nvidia chips." | same |
| 15.07 | Dwarkesh Patel | "Huawei has cracked software engineers." | same |
| 15.46 | NVIDIA GTC 2026 keynote | Jensen Huang: "Dylan Patel had a quote. He accused me of sandbagging." | `semianalysis`, speaker Jensen Huang (see below) |
| 16.72 | TBPN | "...sacks of meat are actually very cheap." | `nvidia`, speaker Dylan Patel, since 2024 |
| 17.14 | Dwarkesh Patel | "...north of $5 trillion of credit." | `trillion`, speaker Dylan Patel, Dwarkesh's channel |
| 17.53 | Lex Fridman | "...could build a power plant and a data center there" | `stargate`, Lex Fridman's channel. That show has no speaker labels |
| 17.95 | Dwarkesh Patel | "I think Huawei is so fucking cracked..." | `huawei`, speaker Dylan Patel, Dwarkesh's channel |
| 18.76 | Matthew Berman | "...adoption is insane." | `insane`, speaker Dylan Patel, Berman's channel |

A search returns a passage of about 30 seconds. The cut takes the line that lands on the beat, so the word searched for is not always the word you hear.

The Jensen clip took a different path. While looking up SemiAnalysis news for the newspaper headlines, Claude Code found coverage of NVIDIA's GTC 2026 keynote, where Jensen talks about SemiAnalysis on stage. It pulled the keynote and read its captions and frames to find the moment. The keynote had no speaker labels in Arcmira yet. Zeal builds Arcmira, so Zeal added it to the index with a Premium transcript and labelled Jensen as the speaker. The search on screen finds the moment after that, in another upload of the same keynote at 3804 s. The video cuts NVIDIA's own upload.

**Arcmira is missing a video or a channel, and you are not an Arcmira admin?** Ask for it. Have your agent send `arcmira_feedback` with the link and what you need from it, for example "Please index NVIDIA's channel. I need Jensen Huang's GTC 2026 keynote searchable by speaker." The more specific the ask, the better, and a whole channel is the most useful thing to ask for.

The exact inputs and the passage each search returned are in [sources.json](sources.json). [guide/01-research.md](guide/01-research.md) says why each filter was chosen.

### Run one yourself

[Ask on arcmira.com](https://arcmira.com/chat?draft=Where%20does%20Dylan%20Patel%20himself%20say%20%22nvidia%22%20on%20podcasts%20since%202024%3F%20Quote%20him%2C%20name%20the%20show%2C%20and%20link%20the%20second.) with the question filled in.

In Claude Code, add the server:

```
claude mcp add --scope user --transport http arcmira https://mcp.arcmira.com/mcp
```

Then run `/mcp` in Claude Code and sign in. A Free account works. Other hosts: https://arcmira.com/docs/mcp-server

Then ask this.

```
Use Arcmira to find where Dylan Patel himself says "nvidia" on podcasts since 2024. Quote him, name the show, and link the second.
```

That is the search behind the first four beats, `arcmira.search({ query: "nvidia", speakerIds: ["ent_140776"], after: "2024-01-01" })`. Results grow with the index, so yours may differ.

## The guide

**Start here.** [RECIPE.md](RECIPE.md) tells the whole build in twelve steps, with commands. Then read [4. Checkpoints](guide/04-checkpoints.md) for the calls Zeal made by eye, and [1. Research](guide/01-research.md) for how each clip was found. The other pages are the evidence behind them.

| | Section | What is in it |
| --- | --- | --- |
| 1 | [Research](guide/01-research.md) | Every Arcmira search behind a clip, why it was filtered that way, and how a hit became a shot |
| 2 | [Libraries](guide/02-libraries.md) | The open-source libraries by layer, what each did, and their licences |
| 3 | [Software](guide/03-software.md) | The scripts, cut player, film pass, lab pages and checks written for this video, with one beat of the edit list explained |
| 4 | [Checkpoints](guide/04-checkpoints.md) | Eleven checkpoints over nine hours, and every taste call with why |
| 5 | [Storyboard](guide/05-storyboard.md) | Every take of every shot on the reference's clock, on a [storyboard page](guide/storyboard/index.html) |
| 6 | [Models](guide/06-models.md) | Which image and video models were tried, which won, and which refused |
| 7 | [Scaffolding](guide/07-scaffolding.md) | The measuring and review tools built first, and what they made possible |
| 8 | [Chat](guide/08-chat.md) | Zeal's asks by theme, the reversals, tokens and cost, turn by turn |
| 9 | [Front page](guide/front-page.md) | The 38 SemiAnalysis moments and 40 headlines the newspaper front page was picked from |

Every guide in [the family](#the-family) has the same eight sections.

## Reuse it

- **On AIMV.** [This video's recipe on AIMV](https://aimv.gg/v/zealcaiden--dylan-patel-hype-reel). AIMV is a public catalog of AI music videos that lists each video with the recipe behind it. This repo is the AIMV recipe for the video, laid out as an AIMV recipe folder (`recipe.yml`, `prompts/`, `code/`).
- **Made with** Claude Code. The workflow then became [claude-video-editing-skills](https://github.com/aimvgg/claude-video-editing-skills), which you can install. One skill finds the second someone said a line and cuts it. One remakes a reference edit shot for shot.

## Rerun it

You need ffmpeg, Python 3.12 with `uv`, Node 22, Google Chrome, [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan/releases) for the retimes, and macOS with `swiftc` for the Apple Vision mattes. You also need an OpenRouter account, a Modal account for the upscale, and a public HTTPS bucket, because Wan reads each source span from a URL. The original run spent $21.54 on OpenRouter and $11.95 on Modal.

Set the variables named in `.env.example`, then follow `code/README.md`. It lists every step with its command, in run order. `RECIPE.md` says why each step was done that way. Before choosing a model, check the current leaders on [aimv.gg/generators](https://aimv.gg/generators); newer ones may beat what this video used.

### Try one step first

Fetch the reference and measure it. This takes about ten minutes and costs nothing.

```
cd code
uv run --no-project --python 3.12 --with-requirements requirements.txt python -I setup/fetch.py --only reference
uv run --no-project --python 3.12 --with-requirements requirements.txt python -I analysis/transitions/measure.py src/clip.mp4 0 900 original
```

You now have the 30-second reference, checked at 900 frames, and `analysis/transitions/original.json` with its per-frame light, sharpness and motion. Every generated shot was matched against that file.

## What is in this repo

No source footage ships here. The original video, its song, the broadcast footage and the podcast clips belong to their owners. `sources.json` links each one at its second. `code/` holds the code that rendered the video, as it ran, with paths made relative and keys read from the environment.

## Built with

Claude Code with Claude Opus 5.5 wrote and ran every script. Clips were found with the [Arcmira MCP](https://arcmira.com/docs/mcp-server) and downloaded with [yt-dlp](https://github.com/yt-dlp/yt-dlp). GPT Image 2.5 Sunburst and Wan 3.0 ran through [OpenRouter](https://openrouter.ai). [SeedVR2](https://github.com/ByteDance-Seed/SeedVR) upscaled on [Modal](https://modal.com). [Demucs](https://github.com/adefossez/demucs), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [OpenCV](https://opencv.org), [MediaPipe](https://github.com/google-ai-edge/mediapipe) and [FFmpeg](https://ffmpeg.org) did the rest. Full credits are in [guide/02-libraries.md](guide/02-libraries.md).

## Why we remix

Zeal is a digital art enthusiast, and the videos in this family are remixes. Remixing and sampling are a lot of the fun of making music and DJing. You flip a sample, cut an edit to someone else's track, or recut a famous clip around a new face. Most of that culture runs on a tacit understanding that it's all good. Sometimes music labels get weird, and in some cases a rights holder can take a video down. We think people should be free to make art out of the culture around them. None of these videos is sold, and the sources are credited by link, not shipped.

## The family

Each video gets the same eight-section guide, and the work turns into Claude skills. More are coming, and each one lands on [aimv.gg/zealcaiden](https://aimv.gg/zealcaiden) with its recipe.

| Repo | What it is |
| --- | --- |
| [dylan-patel-hype-video](https://github.com/zealous1/dylan-patel-hype-video) | A 30-second remake of a viral LeBron hype video, with Dylan Patel of SemiAnalysis swapped in |
| [claude-video-editing-skills](https://github.com/aimvgg/claude-video-editing-skills) | The Claude Code skills these videos became |

## Licence

Code under Apache-2.0 (`code/LICENSE`). The guide, `RECIPE.md` and the prompts under CC BY 4.0.
