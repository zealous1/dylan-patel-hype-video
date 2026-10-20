# 2. Open-source libraries, by layer

The open-source libraries that touched a frame or a sample, what each did here, and its licence. Hosted models (Wan 3.0, GPT Image 2.5 Sunburst) and paid services are in [`06-models.md`](06-models.md).

| Layer | Library | What it did in this reel | Licence |
| --- | --- | --- | --- |
| Research | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Downloaded the reference and every podcast span, run through `uvx` with `curl-cffi` | Unlicense |
| Research | [shazamio](https://github.com/shazamio/shazamio) | Named the song in the reference | MIT |
| Research | [librosa](https://github.com/librosa/librosa) | The beat grid (143.6 BPM) and the 9.0 s dropout | ISC |
| Video | [OpenCV](https://opencv.org) | Face tracking for the zoom-through, ECC alignment of the clean plate, Laplacian sharpness, every per-frame measure | Apache-2.0 |
| Video | [MediaPipe](https://github.com/google-ai-edge/mediapipe) | Selfie segmentation mattes for the halation wrap | Apache-2.0 |
| Video | [NumPy](https://numpy.org), [Pillow](https://python-pillow.org), [SciPy](https://scipy.org) | Compositing, grading, the film look, the aura, the type | BSD-3, MIT-CMU, BSD-3 |
| Video | [RIFE](https://github.com/hzwer/ECCV2022-RIFE) through [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) | Eased retimes of the fade-in and the jersey. Tested for 60 fps and rejected | MIT |
| Sound | [Demucs](https://github.com/adefossez/demucs) `htdemucs_ft` | Four stems, so the announcer could be found inside the vocal | MIT |
| Sound | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `medium.en` | Word times in the voice memos and the announcer lines | MIT |
| Finishing | [SeedVR2](https://github.com/ByteDance-Seed/SeedVR) 7B with [PyTorch](https://pytorch.org) | Upscaled the six softest shots at 1440, then Lanczos to 1080 | Apache-2.0, BSD-3 |
| Finishing | [FFmpeg](https://ffmpeg.org) with x264 | Every encode, the mix (`alimiter`, `sidechaincompress`, `amix`), the loudness master | LGPL / GPL |
| Finishing | [Inter](https://rsms.me/inter/) Display, [UnifrakturMaguntia](https://fonts.google.com/specimen/UnifrakturMaguntia) | The type in this repo, and the newspaper masthead | OFL |
| Checks | FFmpeg `scdet`, `signalstats`, `ebur128`, `silencedetect` | Cuts, flashes, loudness, true peak and silent tails, on every candidate | LGPL / GPL |
| Tooling | [uv](https://github.com/astral-sh/uv), [Node.js](https://nodejs.org), Chrome DevTools protocol | Python environments, the API clients, the newspaper render | Apache-2.0 / MIT, MIT, BSD-3 |

Apple Vision made the still mattes for the profile. It ships with macOS and is not open source. MediaPipe or a matting model replaces it elsewhere.

The posted reel's type was a commercial face that is not in this repo. Inter Display is the free substitute the code points at through `FONT_DIR`.

**Next.** [3. Software](03-software.md) shows the scripts written for this reel, and one beat of the edit list explained.
