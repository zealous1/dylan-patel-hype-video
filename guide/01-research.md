# 1. Research: direction and findings

## The brief

[Arcmira](https://arcmira.com) is a search engine for what people say in podcasts and videos. It knows who is speaking, so a search can ask for one person's own words, and it returns the second each line starts. This page is every Arcmira call behind the reel's podcast section.

Seven seconds in the middle of the reel (13.84 to 20.80 s) had to prove that Dylan Patel is everywhere the AI hardware story is told. The brief was his biggest appearances, cut "fast as fuck", one episode per beat, and every on-screen tag had to be the real search that found the clip. So the research was not "find good Dylan clips". It was "find a clip for each beat with one search a viewer can read and rerun". A tag must be literally true. Late in the edit, an audit found three beats that had been picked by hand at round timestamps. Their tags were not true, so all three were re-sourced through search before the reel shipped.

The full call log is [`research-calls.json`](research-calls.json). The tag on each shot comes from the `found_with` field of that beat in [`../sources.json`](../sources.json), which the edit list (`code/shots/fastcuts/edl-v18-s2.json`) carries into the render.

## The searches

Every call ran on the Arcmira MCP's `arcmira_execute_read` tool. Each person has one id, so a search can be filtered to what they said and not to what others said about them. Dylan is `ent_140776` and Jensen Huang is `ent_122115`. To run these yourself, connect the MCP as the [README](../README.md#run-one-yourself) shows. A Free account works.

| Reel slot (s) | Program | Inputs | Why this filter | What came back | Used |
| --- | --- | --- | --- | --- | --- |
| setup | `arcmira.resolve("Dylan Patel", { context: "SemiAnalysis" })` | name plus context | one id for every later call, so a namesake never leaks in | `ent_140776` | yes |
| setup | `arcmira.mentions` with `is_appearance` | Dylan's id | where he speaks, not where he is mentioned | 38 appearances of 188 mentions, ranked by views with yt-dlp metadata | the episode pool |
| 0.00 to 1.62 | `arcmira.search` | `query: "nvidia"`, `speakerIds: [ent_140776]`, `after: 2024-01-01`, `limit: 20` | his own words only, recent shows | 20 passages over a16z, Matthew Berman, Dwarkesh Patel, TBPN and more | four beats from four episodes |
| 1.62 to 2.88 | `arcmira.search` | `query: "semianalysis"`, `speakerIds: [ent_122115]`, `limit: 3` | the other side of the story, Jensen talking about Dylan | found on the web first, then added to the index (see below). Call 34 returned another upload of the GTC 2026 keynote at 3804 s | the zoom-through beat |
| 2.88 to 3.30 | `arcmira.search` | same as the first row | the same search, for one more show, so no episode repeats | the TBPN passage | yes |
| 3.30 to 3.69 | `arcmira.search` | `query: "trillion"`, Dwarkesh's channel id, `limit: 10` | a channel id pins the episode when one word hits many shows | the Dwarkesh passage | yes |
| 3.69 to 4.11 | `arcmira.search` | `query: "stargate"`, Lex Fridman's channel id, `limit: 5` | that show has no speaker labels, so the channel replaces the speaker filter | the Lex Fridman passage | yes |
| 4.11 to 4.92 | `arcmira.search` | `query: "huawei"`, Dwarkesh's channel id | a channel id pins the episode when one word hits many shows | the Dwarkesh Patel episode with Asianometry and Dylan, "How the semiconductor industry actually works", at 2038 s | yes |
| 4.92 to 5.34 | `arcmira.search` | `query: "insane"`, Matthew Berman's channel id | a reaction word for the last beat | the Berman passage at 5202 s | yes |
| ending | `arcmira.mentions(entity: "dylan patel")` | his id | the closing line counts the coverage | 156 videos over 37 channels | the line above the jersey |

Other words were tried and not used, among them gigawatt, China, TSMC, cooked and power. The log holds 51 searches in 34 calls, an estimated 1,000 credits in all. The estimate leaves out the Premium transcript of the keynote.

## How a hit became a shot

1. Read 30 s either side of the passage with `arcmira.transcript` and pick the line that lands on the beat.
2. Build the YouTube URL from `video_id`, because yt-dlp downloads from YouTube. The `watch_url` field opens the passage on Arcmira, for reading.
3. Download the span with yt-dlp (`uvx --from "yt-dlp[default,curl-cffi]"`). An older yt-dlp failed on YouTube with a 403.
4. Run FFmpeg `silencedetect` over the span and cut in a silence. Transcript times mark words, not cut points.
5. Track the face with OpenCV so the next clip lands where this one left off (see `04-checkpoints.md`, zoom-through B).
6. Write the call into the edit list. `build.py` prints the channel name over `arcmira.search(speaker: "dylan patel", query: "nvidia")`, lowercase.

## For agents

- Resolve once, then filter by speaker id. A name in the query matches people talking about him.
- One idea per search. A single word with a speaker filter beats a sentence.
- When a show has no speaker labels, filter by channel id and check the voice by ear.
- Never repeat an episode inside one section.
- A tag must be literally true. An audit found three beats that had been picked by hand at round timestamps. Every one was re-sourced through search before the section shipped.
- Search returns at most 20 passages and needs a query of two or more characters; there is no speaker-only search. Use `mentions` to list appearances instead.

## Not found by search

The reference edit, its song, and the basketball footage under the swapped shots came from the reference itself (see `sources.json`). Jensen's keynote needed a Premium transcript, which names each speaker, before a search could filter to Jensen's own words with `speakerIds: [ent_122115]`.

The Jensen beat came from the web, not from a search. While researching SemiAnalysis news for the newspaper headlines, Claude Code found coverage of the GTC 2026 keynote, where Jensen talks about SemiAnalysis on stage. Zeal asked for that moment as an impact zoom. Claude Code pulled NVIDIA's own upload and read its captions and frames to find it (call 30), where Jensen says "And then SemiAnalysis came out and Dylan Patel had a quote. He accused me of sandbagging." That upload has captions only, so no speaker search could return it. Zeal builds Arcmira, so Zeal added the keynote to the index with a Premium transcript of another upload, with Jensen labelled as the speaker. Call 34 then ran the search on screen, Jensen's id and `semianalysis`, and returned that upload at 3804 s. The tag shows the NVIDIA channel name above the search, as every tag shows its show, but the logged search had no channel filter. A rerun with `limit: 3` uses no credits.

**Arcmira is missing a video or a channel, and you are not an Arcmira admin?** Ask for it. Have your agent send `arcmira_feedback` with the link and what you need from it, for example "Please index NVIDIA's channel. I need Jensen Huang's GTC 2026 keynote searchable by speaker." The more specific the ask, the better, and a whole channel is the most useful thing to ask for.

**Next.** [2. Libraries](02-libraries.md) lists the open-source code under every layer.
