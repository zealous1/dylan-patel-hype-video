# Code

The scripts that made the Dylan Patel hype video, in the order they ran. Step numbers match [`../RECIPE.md`](../RECIPE.md), and [`../guide/03-software.md`](../guide/03-software.md) says what each file decided. Run every command from this folder.

There is no media here. You download the reference edit and the podcast clips yourself, and you bring your own photos, logo and voice memos.

## Before you start

A full rerun costs about what the run did. That was $21.54 of OpenRouter generation and $11.95 of Modal GPU time, plus your retries. The first paid call is step 4.

You need these tools:

- ffmpeg 7 or later, with libx264
- Python 3.12 and [uv](https://docs.astral.sh/uv/). Every Python step runs through `uv run` from a hashed lock, described below.
- Node 22 or later. The `.mjs` scripts use only Node built-ins.
- Google Chrome, for the newspaper render
- [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan/releases) 20221029 with the RIFE v4.6 model, for the retimes. The release zip unpacks to `rife-ncnn-vulkan-20221029-macos/` (or the Linux or Windows name). Point `RIFE_DIR` at that folder.
- A [Modal](https://modal.com) account, for the upscale. Sign the CLI in once with `uv run --no-project --python 3.12 --with-requirements requirements.txt modal setup`. Its image unpacks [ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) from the commit the run used (its main branch of 2025-12-24), and the 60 fps lab unpacks [Practical-RIFE](https://github.com/hzwer/Practical-RIFE) from the commit the run recorded. Both commits are named in the scripts, and each image checks its tarball against a sha256 before it unpacks it
- macOS with `swiftc`, for the Apple Vision mattes in the ending and the datacenter shot
- An [OpenRouter](https://openrouter.ai) key with access to the image and video models
- A public HTTPS folder for step 5, such as an R2 or S3 bucket with public reads. Wan 3.0 fetches each source span from it, so it holds short clips of the broadcast footage. Make it private again when the shots are done.

Set up the environment and the inputs:

```
cp ../.env.example ../.env              # fill it in
set -a; . ../.env; set +a
sh setup/fonts.sh                       # Inter, Inter Display, Barlow, Barlow Condensed and UnifrakturMaguntia into fonts/
uv run --no-project --python 3.12 --with-requirements requirements.txt python -I setup/fetch.py   # reference into src/, podcast windows into footage/
sh setup/prep.sh                        # Demucs stems, the reference stills, the source spans
```

Every Python command in this folder runs as `uv run --no-project --python 3.12 --with-requirements <lock> python -I ...`, and each script's header gives its full command. uv builds the environment once from the lock and checks every package against its sha256, so nothing unpinned is fetched at run time. `requirements.txt` serves every script, `requirements-matte.txt` the MediaPipe steps (they need an older NumPy), and `requirements-stems.txt` Demucs. Each lock is made from its `.in` file by `sh setup/lock.sh`, which admits only releases at least a week old. The table below shortens the prefix to `python -I`. Commands written `python3 -I` use only the standard library. To work in a plain venv instead, run `uv venv --python 3.12 && uv pip sync requirements.txt` and activate it.

The Modal images have their own locks in `modal/`. They target the container, which runs Python 3.11 on linux x86_64 with torch from the CUDA 12.8 index. `modal/requirements-seedvr2.txt` serves both SeedVR2 scripts, and `modal/requirements-prife.txt` serves the Practical-RIFE lab. Each image installs its lock with `pip install --require-hashes`, so the build fails if a package does not match its hash. The `.in` files pin the versions the upscale and interpolation builds installed. Three of those releases came after the 2026-10-10 cutoff, so fonttools, transformers and soupsieve resolve to the newest release before it. `sh setup/lock.sh` rebuilds these locks along with the others. Edit a pin in the `.in` file first, then rerun it.

Add your own inputs:

- `refs/dylan/` holds photos of the person you swap in: `headshot-suit.png`, `headshot-smile.png`, their `-768` copies, `side-c.png`, `threequarter-a.png`, and `crops/front-a.png` and `crops/threequarter-a.png`.
- `refs/logo/` holds the logo: `mark.png`, `mark-504.png`, `wordmark.png` and `end-logo.png`.
- Two voice memos replace the announcer, and the scripts find each take by its words. Record the intro line, "Looking for Patel, he's got it!", several times in one memo, and save it as `audio/patels/inbox/memo3.m4a`. Record the outro line, "Whoa, Dylan with the gigawatt!", as `audio/outro/memo.m4a`. `audio/patels/build.py` skips any take where Whisper does not hear "Patel" with a word after it. `audio/outro/build.py` stops if a take has no "Dylan" or no word starting with "giga". For another name, change the word in `patels()` in `audio/patels/build.py` and in `audio/outro/build.py`, and each script's Whisper prompt. Run `mkdir -p audio/voice` once, because step 3 copies the picked takes there.
- `shots/<shot>/start-box.png` and `end-box.png` mark the player to replace for each image edit in step 4. Each is one frame of `src/clip.mp4` with a red rectangle drawn around that player. The run used frames 30 and 186 (intro), 189 and 255 (backdown), 259 and 293 (fadeaway), 325 (celebrate, start only), 630 and 694 (alleyoop), and 769 and 810 (jersey, where the start frame has no box). The run's box sizes are not recorded. To make one, run `ffmpeg -i src/clip.mp4 -vf "select=eq(n\,189),drawbox=x=X:y=Y:w=W:h=H:color=red:t=8" -frames:v 1 shots/backdown/start-box.png` with the box around the player.

## Stages in run order

| Step | Stage | Entry point | Command |
| --- | --- | --- | --- |
| 1 | Measure the reference | `analysis/transitions/measure.py`, `analysis/flicker/measure.py` | `python -I analysis/transitions/measure.py src/clip.mp4 0 900 original`, then `python -I analysis/flicker/measure.py` |
| 2 | Find the podcast beats | `../sources.json`, `shots/fastcuts/edl-v18-s2.json` | The Arcmira searches are listed per beat in `../sources.json`. `setup/fetch.py` downloads what they found |
| 3 | Mute the announcer under the new intro line | `audio/compose.sh` | `bash audio/compose.sh` writes `audio/no-announcer-v2.wav` from the Demucs stems |
| 3 | Place the intro line | `audio/patels/build.py` | `python -I audio/patels/build.py` cuts every take in `audio/patels/inbox/` into `audio/patels/work/<take>-line-g4.wav`. For each take it prints `INTRO_CUT = ...`, the cut mix D uses. Copy the take you pick to `audio/voice/memo3-take5-line-g4.wav`, and keep its `INTRO_CUT` line |
| 3 | Blend the intro line into the track | `audio/blend.sh` | `bash audio/blend.sh` writes `audio/mix-patel-memo3-5-blend.wav`, the track the outro is placed on |
| 3 | Place the outro line | `audio/outro/build.py` | First `ffmpeg -i audio/outro/memo.m4a audio/outro/memo.wav` and `ffmpeg -i audio/outro/memo.m4a -ac 1 -ar 16000 audio/outro/memo-16k.wav`. `TAKES` in the script holds where each take sits in the run's memo, so set it for yours. Then `python -I audio/outro/build.py`. For each take it prints `OUTRO_CUT = ...` and `OUTRO_AT_MS = ...`. Copy `audio/outro/work/take3-g0.wav`, or your pick, to `audio/voice/outro-take3-g0.wav` |
| 3 | Split the announcer from the song | `audio/audit/restore.py` | `python -I audio/audit/restore.py` |
| 3 | Render the final mix (mix D) | `audio/audit/build.py` | Paste the `INTRO_CUT`, `OUTRO_CUT` and `OUTRO_AT_MS` lines the two build scripts printed over the run's values near the top of `audio/audit/build.py`. Then `python -I audio/audit/build.py` writes `audio/audit/out/d-hotter-voices.wav` |
| 4 | Character sheet and start frames | `starts/gen.mjs` | `node starts/gen.mjs sheet`, then `node starts/gen.mjs frames`. With no names, `frames` makes the 16 edits behind the video's start and end frames, in an order where each edit's input exists first. It tries an edit up to four times when the safety filter refuses it. `dcplate` waits for step 5 |
| 5 | Upload the source spans | `setup/spans.py` (run by `setup/prep.sh`) | Upload `shots/<shot>/src-720.mp4` and `src-720-slow.mp4` to `$SOURCE_BASE_URL/<shot>/` |
| 5 | Swap each shot by video-to-video | `shots/vid.mjs`, `shots/<shot>/job.json` | The run used four flag sets. See [the shot table](#the-wan-30-runs) below |
| 5 | The datacenter clean plate | `starts/gen.mjs` | `ffmpeg -i shots/datacenter/out/wan-3.0-novideo-min.mp4 -frames:v 1 shots/datacenter/post/f01.png`, then `node starts/gen.mjs frames dcplate` |
| 5 | Speed a slowed take back up | `setup/realtime.py` | `for s in intro backdown celebrate fadeaway rim jersey alleyoop; do python3 -I setup/realtime.py shots/upscale-sweep/picks/$s.json; done` rebuilds each take from the frames the video used. Skip `jersey-timeline.json`. `shots/jersey/timeline.py` makes that take in step 9, and its picks repeat frames, which `realtime.py` refuses |
| 6 | Grade each take to the reference, redraw the scorebug and banner, add the wafer | `shots/lookmatch.py`, `shots/intro/graphics.py`, `shots/fadeaway/wafer.py`, `shots/<shot>/post.sh` | `sh shots/intro/post.sh`, and the same for backdown, fadeaway, rim and fadeout, plus `sh shots/celebrate/post-look.sh`. The jersey's post runs in step 9 |
| 6 | Retime the fade-in and the intro | `shots/fadein/v3.sh` | `sh shots/fadein/v3.sh`, after `shots/intro/post.sh` |
| 6 | Paint out the datacenter sign | `shots/datacenter/post/designify.py` | `(cd shots/datacenter && uv run --no-project --python 3.12 --with-requirements ../../requirements.txt python -I post/designify.py)`. The parentheses keep the `cd` out of your shell. It writes `shots/datacenter/out/clean-v1.mp4` |
| 7 | The newspaper | `shots/newspaper/render.mjs` | `node shots/newspaper/render.mjs paper-v4` |
| 8 | Track faces and person mattes | `shots/fastcuts/lab/faces.py`, `shots/fastcuts/lab/matte.py` | `python -I shots/fastcuts/lab/faces.py`, then `uv run --no-project --python 3.12 --with-requirements requirements-matte.txt python -I shots/fastcuts/lab/matte.py` |
| 8 | The podcast section | `shots/fastcuts/build.py` | `python -I shots/fastcuts/build.py edl-v18-s2.json`. The edit list is named relative to `shots/fastcuts/`. Also run `python -I shots/fastcuts/build.py` once with no edit list. Its default list writes `fastcuts-v14.mp4`, which step 11 places before the splice replaces it |
| 9 | The ending | `shots/jersey/*.py`, `shots/jersey/post.sh`, `shots/profile/*` | The commands are in [the ending](#the-ending) below |
| 10 | Upscale the soft shots | `shots/upscale-sweep/modal_seedvr2.py`, `collect.sh`, `trace.py`, `rebuild.py` | `uv run --no-project --python 3.12 --with-requirements requirements.txt modal run shots/upscale-sweep/modal_seedvr2.py --variants C --shots rim,celebrate,fadeout,alleyoop,backdown,fadeaway`, then `uv run --no-project --python 3.12 --with-requirements requirements.txt sh shots/upscale-sweep/collect.sh` (it calls `modal` too), then `python -I shots/upscale-sweep/rebuild.py --tag sr --src rim=shots/upscale-sweep/out/rim-C.mp4,celebrate=shots/upscale-sweep/out/celebrate-C.mp4,fadeout=shots/upscale-sweep/out/fadeout-C.mp4,alleyoop=shots/upscale-sweep/out/alleyoop-C.mp4,backdown=shots/upscale-sweep/out/backdown-C.mp4,fadeaway=shots/upscale-sweep/out/fadeaway-C.mp4` |
| 10 | The newspaper from the upscaled celebration | `shots/newspaper/render.mjs` | `CELEBRATE=shots/celebrate/out/min-realtime-sr.mp4 node shots/newspaper/render.mjs paper-v5-sr-30` |
| 11 | Upscale the datacenter shot for the opener | `shots/upscale-test/modal_seedvr2.py` | `mkdir -p shots/upscale-test/in && ffmpeg -i shots/datacenter/out/clean-v1.mp4 -frames:v 60 -an -c:v libx264 -crf 10 -pix_fmt yuv420p shots/upscale-test/in/datacenter.mp4`, then `uv run --no-project --python 3.12 --with-requirements requirements.txt modal run shots/upscale-test/modal_seedvr2.py --model 7b --shots datacenter`. The opener's `face2` reads `shots/upscale-test/out/datacenter-seedvr2-7b.mp4` |
| 11 | Assemble at 30 fps | `master/render.py` | `python -I master/render.py --scenes master/scenes-v4.json --tag v4 --fps 30 --mix audio/audit/out/d-hotter-voices.wav` |
| 11 | Film look | `shots/film/film.py` | `BASE=v4 MIX=audio/audit/out/d-hotter-voices.wav python -I shots/film/film.py --final worn 30` |
| 11 | Name-burn opener | `shots/opener/build.py` | `OPENER_BASE=master/out/final-v4-worn-30-master.mp4 python -I shots/opener/build.py face2 name2`, then `cp shots/opener/out/opener-name2.mp4 master/out/final-v5-worn-30-master.mp4` |
| 11 | Splice in the podcast section | `shots/fastcuts/lab/splice.sh` | `BASE=v5 sh shots/fastcuts/lab/splice.sh final-v6-S2=v18-s2` writes `master/out/final-v6-S2-master.mp4` |
| 12 | Check the candidate | `shots/fastcuts/lab/splice.sh`, the `check-video-render` skill | The splice asserts 902 frames. Then run the `check-video-render` skill on the result, which checks audio to the last frame, loudness and true peak |

Run any Python stage with `--help` to print its header, which lists its options and the file it writes. Outputs land in an `out/` folder beside the script, which the repo's `.gitignore` keeps out of git.

### The Wan 3.0 runs

Each command writes `shots/<shot>/out/<tag>.mp4`, and the tag spells out its flags. The picks files in `shots/upscale-sweep/picks/` name the generation each take was rebuilt from.

| Shot | Command | Writes |
| --- | --- | --- |
| intro | `node shots/vid.mjs intro alibaba/wan-3.0 --no-frames --strong --slow` | `out/wan-3.0-noframes-strong-slow.mp4` |
| backdown, fadeaway, rim, fadeout, jersey | `node shots/vid.mjs <shot> alibaba/wan-3.0 --no-frames --slow --focus` | `out/wan-3.0-noframes-slow-focus.mp4` |
| alleyoop | `node shots/vid.mjs alleyoop alibaba/wan-3.0 --no-frames --slow --focus --take 2` | `out/wan-3.0-noframes-slow-focus-2.mp4` |
| celebrate, datacenter | `node shots/vid.mjs <shot> alibaba/wan-3.0 --no-video --min --duration 3` | `out/wan-3.0-novideo-min.mp4` |

`--take 2` only names the file. The run kept its second alleyoop generation. If a poll drops, `--resume <id>` picks the job up without paying for a new one.

### The ending

The jersey shot and the profile end card build on each other, so run these in order. `RIFE_DIR` must be set for `timeline.py`.

```
python -I shots/jersey/deghost.py
python -I shots/jersey/timeline.py
TAG=v4 sh shots/jersey/post.sh
python -I shots/jersey/fadein.py v4
python -I shots/jersey/mentions.py shots/jersey/out/fadein-v4.mp4 shots/jersey/out/fadein-v5-mentions-lc.mp4
node shots/profile/gen.mjs up b
SIZE=1792x1008 node shots/profile/gen.mjs vid-end
SIZE=1792x1008 node shots/profile/gen.mjs vid-end-level
node shots/vid.mjs profile/gen-video-v13 alibaba/wan-3.0 --no-video --first-only
ffmpeg -i shots/profile/gen-video-v13/out/wan-3.0-novideo-first.mp4 -vf "trim=start_frame=158:end_frame=240,setpts=PTS-STARTPTS" -c:v libx264 -crf 10 -pix_fmt yuv420p shots/profile/gen-video-v13/out/span-158-238.mp4
python -I shots/profile/gen-video/prep.py ../gen-video-v13/out/span-158-238.mp4 ../gen-video-v13/frames
python -I shots/profile/clean.py
python -I shots/profile/build.py --start 784 --tag profile-v16-lc-from784 --video gen-video-v13/frames --still gen-video-v13/frames/080.png --fixed --clean --turn 786,901 --jersey shots/jersey/out/jersey-timeline.mp4 --v12 --v13 --v14 --v15
```

`mentions.py` also rewrites `shots/jersey/out/mentions-layer.png`, which the profile build carries over, so it runs first. `prep.py` resolves its two paths from its own folder. The span keeps generation frames 158 to 239. The name says 238, as the run's file did. The header of `shots/profile/build.py` lists the flags of every earlier version.

## Watch it as you go

The storyboard plays each take you rebuild in its slot on the reference clock. Serve the repo root:

```
python3 -m http.server 8000
```

Then open `http://localhost:8000/guide/storyboard/index.html?media=../../code/`. Takes you have not rebuilt show as placeholders.

`index.html` here, its `player.js` and the lab pages it links (`shots/fastcuts/lab/index.html`, `shots/upscale-sweep/index.html`, `audio/audit/index.html`, `master/fps-pick/index.html`, `master/film-pick/index.html`) are the run's working notebooks, kept as they were. They hold the side-by-side comparisons behind each decision. Some of their buttons point at files only the run made, such as earlier masters and mixes. `audio/audit/index.html` reads `audio/audit/data.js`, which `python -I audio/audit/measure.py` writes.

## Fonts

`setup/fonts.sh` downloads every font from a fixed release or commit and checks its sha256. The video's tags and name burn were set in a commercial font. This code uses Inter Display (SIL OFL 1.1) in the same weights, from `FONT_DIR`. Its widths differ a little from the original, so check the longest channel names on the podcast lab page. The broadcast graphics use Barlow Condensed, Barlow and Inter (all SIL OFL 1.1) in place of the macOS system fonts DIN Condensed, Futura and Arial. The newspaper masthead uses UnifrakturMaguntia (SIL OFL 1.1). To match the original look with a font you licence yourself, put it in `FONT_DIR` under the same file names.

## Environment

`../.env.example` lists every variable the code reads. Each `shots/<shot>/job.json` points its source span at a `SOURCE_BASE_URL` placeholder, and `shots/vid.mjs` fills it in from the environment. Only `OPENROUTER_API_KEY` and `SOURCE_BASE_URL` are needed for the generation steps, and `RIFE_DIR` and `FONT_DIR` for the steps that use those tools.

## Licence

Apache-2.0, in `LICENSE`.
