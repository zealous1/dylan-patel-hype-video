# 5. Storyboard and timeline

The storyboard lays every take of every shot on the reference's clock, so you can see what was tried for each second and what won. The [storyboard page](storyboard/index.html) loads [`storyboard/storyboard.json`](storyboard/storyboard.json). The clock is the reference's audio, 30.07 s. Each of the slots below it is one shot, with every take tried for it in the order it was made, its model and cost, the verdict, and the pick at each checkpoint in [`04-checkpoints.md`](04-checkpoints.md).

The component is the same one every guide uses. It grew out of the cut player that made the reel (`code/index.html` with `takes.json`), where each scene could swap takes against the mix.

## Reading it

- The top row is the clock, the reference's own audio.
- Twelve slots follow it, one per shot, from the fade-in to the profile end card. The podcast section is one slot, `fastcuts`.
- Each slot lists its takes in the order they were made, with model, cost and verdict.
- The checkpoint selector replays the picks at eight points, from the first cut to the shipped v6-S2 (see [`04-checkpoints.md`](04-checkpoints.md)).

## Media

The page ships data only. No take and no still is in this repo. Most takes are generated from broadcast footage, and the podcast clips belong to their shows. Each take carries its model, prompt, cost, frames, verdict and measurements, and the page links the reference and each source at its second.

The page total is the run's whole logged generation cost, $21.54. It counts each billed request once, including the profile clips and opener stills that sit off the clock.

To open the page, serve the repo over HTTP with the command below. Opened straight from disk, the page asks you to drop in `storyboard.json` instead. To watch the takes, rebuild them with `code/` and point the page at that folder. Every media path in `storyboard.json` starts with `media/`, and `?media=<folder>` maps `media/` onto your folder. `code/` already has that layout, so `media/shots/intro/out/look-v1.mp4` loads `code/shots/intro/out/look-v1.mp4`. From the repo root:

```
python3 -m http.server 8000
```

Then open `http://localhost:8000/guide/storyboard/index.html?media=../../code/`. The **Load my media folder** button does the same with a folder on your disk. Pick `code/`. Takes you have not rebuilt show as placeholders.

**Next.** [6. Models](06-models.md) says which image and video models were tried, which won, and which refused.
