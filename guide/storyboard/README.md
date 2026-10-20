# Reel storyboard

A one-page player for a reel's whole making-of. It lays every slot of the reel on the reel's clock, lists every take made for each slot (the model, prompt, cost, frames, verdict and measurements), and replays the picks of each checkpoint, from the first cut to the shipped one. When the media is present, every take plays in place on the clock. When it is not, the page shows the data and a placeholder for each picture.

The page is filled only from `storyboard.json`. It loads no external scripts, fonts or styles, and works in light and dark mode.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The page. |
| `storyboard.js` | The player, the timeline, the take cards and the checkpoint replay. |
| `storyboard.css` | Styles. Colours are tokens on `:root`, redefined for dark mode. |
| `schema.json` | The data shape, `reel-storyboard/1`. |
| `validate.py` | Checks a `storyboard.json` against the schema and the links between its parts. Standard library only. |
| `storyboard.json` | One reel's data. A builder script writes it. |

## Open it

Serve the folder over HTTP, because browsers block `fetch` on `file://` pages:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html`. If the page cannot load its data, it offers a file picker and a drop zone for a `storyboard.json`.

URL options:

- `?data=<file>` loads another data file beside the page, such as `?data=example.storyboard.json`.
- `?media=<folder>` turns on local mode. Every path that starts with `media/` resolves inside that folder, so `media/shots/intro/take.mp4` loads `<folder>/shots/intro/take.mp4`. The folder can be relative to the page or a full URL.

The **Load my media folder** button does the same as `?media=` with a folder on your disk, and nothing is uploaded. Pick the folder that `media/` paths point into, or its parent if the parent contains a `media` folder.

If your server ignores HTTP Range requests (Python's `http.server` does), the page loads each file under 400 MB whole, so seeking still works. Larger files stream and may not seek on such a server.

## How to use it

- **Checkpoint** chooses a cut. **Play the picks** plays that checkpoint slot by slot from its takes. **Play the render** plays the checkpoint's rendered file, when it has one and you have it.
- **Play** on any take card puts that take into its slot and jumps there, until you reload or change checkpoints. **Back to the checkpoint's picks** undoes your changes.
- **Clock** picks what drives time: the checkpoint's own mix, the clock's audio files, the render's sound, or a silent timer when there is no audio.
- Keys: Space plays and pauses, the left and right arrows move between slots, and 1 to 9 play that take of the current slot.
- **Loop this slot** repeats the current slot, for comparing takes.

## The data

```text
storyboard
  clock         kind (reference | song | voiceover), duration_s, fps, bpm, reference, audio[], landmarks[], sections[]
  slots[]       id, label, t0, t1, verdict, section, source, note
    takes[]     id, label, made_with {model, tool}, cost_usd, status, why, prompt, prompt_file,
                made_at, source, media {still, video, span, link}, frames {count, first, last},
                measurements[], cuts[], public, public_reason
  assets[]      takes that feed a slot without sitting on the clock (sheets, start frames, ranked candidates)
  checkpoints[] id, label, at, picks {slot: take}, bounds {slot: [t0, t1]}, duration_s, sections[],
                audio, render, measurements[], note
```

Rules the page and `validate.py` rely on:

- The last checkpoint is the shipped cut. A take is `picked` when the last checkpoint picks it, `superseded` when only an earlier one did, `rejected` when it was made or found for the cut and never picked, `lab` when it was an experiment off the cut's path, and `failed` when it returned no output.
- A slot's `t0` and `t1` are its edges in the last checkpoint that holds it. A checkpoint whose edges differ says so in `bounds`.
- A checkpoint that rebuilt the clock (an original edit re-cuts its song for each version) carries its own `duration_s`, `sections` and `audio`.
- A checkpoint with no `picks` kept no per-slot record. The page still shows its note, render and measurements, and draws its slots as unrecorded.
- A take plays by the first rule that fits: `plays_reference` plays the reference video at clock time. `cuts` with a `span` play those parts of the take's video. `media.span` stretches that part of the video over the slot. A video without a span stretches whole. A still holds.
- `measurements[].series` draws a strip, such as a per-frame score, as a sparkline under the take.
- Media paths are relative. `media/...` paths are private and never shipped. Any other relative path, such as `stills/intro.jpg` or `../prompts/1-swap.md`, ships beside the page.

Check a file before you ship it:

```sh
python3 validate.py storyboard.json
```

## Shipping the storyboard when the takes can't be published

Most reels are made from footage, music and likenesses that the maker may use in the reel but may not republish as raw takes. Metadata always ships: timings, models, prompts, costs, verdicts and measurements. These are the options for the pictures.

| Option | What ships | Good for | Cost |
| --- | --- | --- | --- |
| Approved stills with no third-party pixels | Stills you made from scratch, such as generated character sheets or code renders, each approved by name, shipped beside the page as plain relative paths | Showing the look of the parts you own | Each still needs a check and an approval. Most remake slots have none. |
| Data only | `storyboard.json` with every `media/` path left unresolved | Every reel. Nothing in it can leak. | No pictures. |
| Local replay | Data only, plus the scripts that rebuild the takes. A reader runs them, then opens the page with `?media=<folder>` | Readers who want to see every take play | The reader downloads the sources and runs the build. Paid takes cost them money again. |
| Measured metric strips instead of pixels | `measurements` with a `series` per take, such as a scene-cut score, face match or loudness over time | Showing why a take won without a frame of it | Only as good as the measure. It shows a number, not the picture. |
| Timestamped links to the posted video | `source` and `checkpoint.render.link` pointing at the posted reel and the original sources at the right second | Letting a reader see each moment where it is already public | Links rot, and a platform can take the post down. |
| Private hosting | The `media/` folder on a host that only invited people can reach, opened with `?media=<private URL>` | Collaborators and reviewers | A host to run and an access list to keep. The files still must never be linked from public text. |

**Recommendation.** Ship data only, with timestamped links, as the default for every public storyboard. Nothing in it can leak, and a reader can still watch each moment in the posted reel and each source at its second. Add local replay for readers who rebuild the takes, since `?media=` costs nothing to ship. Add approved stills only for pixels you made from scratch, and add metric strips wherever a measurement decided a take. Keep private hosting for collaborators, and never link it from the public page.
