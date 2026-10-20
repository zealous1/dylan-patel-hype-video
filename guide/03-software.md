# 3. Purpose-built software

Everything written for this video, by job. Paths are under `code/`. The clever part is small. One edit list carries each clip's search, and the tag on screen is printed from that record.

## By kind

| Kind | Files | What it decided or made | Reusable as is |
| --- | --- | --- | --- |
| Render scripts | `master/render.py`, `shots/opener/build.py`, `shots/fastcuts/build.py`, `shots/fastcuts/lab/splice.sh` | Assembles takes into a master and a share copy, adds the film look and the opener, splices in the podcast section | `render.py` and `splice.sh` yes; the rest are this video's look |
| Generation clients | `starts/gen.mjs`, `shots/vid.mjs`, `shots/<shot>/job.json` | Image and video calls with references, polling, resume and a cost log per run | yes |
| Cut player | `index.html`, `player.js`, `takes.json` | One take per scene, the mix as the clock, so a swap is heard in context | yes; it became the storyboard component |
| Look and film pass | `shots/lookmatch.py`, `shots/film/film.py`, `analysis/flicker/measure.py` | Grades a generated take until it measures like the reference, then borrows the reference's own flicker | `lookmatch.py` yes |
| Lab pages | `shots/fastcuts/lab/index.html`, `shots/upscale-sweep/index.html`, `audio/audit/index.html`, `master/fps-pick/index.html`, `master/film-pick/index.html` | Side-by-side candidates with their numbers, one page per decision | the pattern, yes |
| Check tools | `analysis/transitions/measure.py`, `audio/audit/lib.py`, the frame-count asserts in `splice.sh` | Every candidate measured before anyone watched it | see the `check-video-render` skill |

## Every script, in run order

Every script, with its command, is in [`code/README.md`](../code/README.md), in run order. [`../RECIPE.md`](../RECIPE.md) says why each step was done that way.

## One beat of the edit list, explained

The podcast section is built from one file, `shots/fastcuts/edl-v18-s2.json`. This is its seventh beat, the Dwarkesh Patel clip at 17.14 s on the video, with the passage text trimmed.

```json
{
  "slot_in": 3.3, "slot_out": 3.69,
  "src": "labs-credit", "src_in": 10.3,
  "cx": 0.38, "cy": 0.42, "zoom": 1.35,
  "provenance": {
    "method": "arcmira.search",
    "input": { "limit": 10, "query": "trillion", "speakerIds": ["ent_140776"],
               "channelIds": ["UCXl4i9dYBrFOabk0xGmbkRA"], "after": "2024-01-01" },
    "result": { "id": "aV26V1UvkJw@3282", "channel_name": "Dwarkesh Patel",
                "text": "... you still end up with north of $5 trillion of credit. ..." }
  },
  "quote": "...north of $5 trillion of credit.",
  "youtube_seconds": 3286.3
}
```

`slot_in` and `slot_out` place the clip 3.3 s into the section, and `cx`, `cy` and `zoom` frame Dylan's face so it lands where the last clip's face was. `build.py` prints the tag on screen from `provenance`, the query and speaker from `input` and the show from `result`, so no tag is typed by hand. `result` is the passage the search returned at 3282 s, four seconds before the line the cut plays.

## Labs and review pages

These made the decisions. They are not needed to rerun the cut.

| Script or page | Decision it made |
| --- | --- |
| `index.html`, `player.js` | The cut player: one take per scene, the mix as the clock |
| `analysis/transitions/measure.py`, `analysis/audio.py`, `analysis/flicker/film.py`, `analysis/sheet.sh` | How the reference moves, flickers and hits |
| `audio/audit/measure.py`, `audio/audit/vocals.py`, `audio/audit/index.html` | Mix D over A, B and C |
| `shots/fastcuts/lab/index.html`, `audit.py`, `measure.py`, `stats.py` | Zoom-through B and halation wrap P2 over the other rounds |
| `shots/upscale-sweep/index.html`, `judge.py`, `metrics.py`, `page.py` | SeedVR2 7B at 1440 over 3B and Lanczos |
| `master/interp/*`, `master/render60.py`, `master/fps-pick/index.html`, `master/sharpness/*` | 30 fps over 60 |
| `master/film-pick/index.html`, `shots/film/index.html` | Worn over Classic and Match |
| `shots/opener/broadcast.py` | The broadcast intro opener, which lost to the name burn |
| `shots/fastcuts/tags/variants.py` | The search-tag style |

## Environment

Names only. The values go in `.env.example`.

| Variable | Used by |
| --- | --- |
| `OPENROUTER_API_KEY` | image and video generation |
| `SOURCE_BASE_URL` | the HTTPS folder where you host source spans for video-to-video |
| `MODAL_PROFILE` | the SeedVR2 upscale |
| `RIFE_DIR` | the unpacked rife-ncnn-vulkan release folder, which holds the binary and the RIFE v4.6 model |
| `CHROME_BIN` | Google Chrome for the newspaper render |
| `FONT_DIR` | the folder holding Inter Display and the other open fonts |
| `OUT`, `MODEL`, `SIZE`, `QUALITY`, `BASE`, `MIX`, `OPENER_BASE`, `OPENER_OUT`, `TAKE`, `TAG`, `FPS` | per-run switches, documented at the top of each script |

**Next.** [4. Checkpoints](04-checkpoints.md) tells the story, version by version, with every call Zeal made by eye.
