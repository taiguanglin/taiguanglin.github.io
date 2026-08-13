# PDF Audio Map

Align PDF ebook Q&A sections to `audio/*.opus` time ranges, then inject `.qa-play` buttons at build time.

## Commands

```bash
cd tool/pdf_audio_map

# Align all months (write JSON); fail if any segment still missing
python3 align.py --fresh --apply --require-complete

# Fill misses: align → sense_voice retranscribe hard-miss sessions → realign
python3 fill_misses.py --fresh

# Single month
python3 align.py --month 2025-08 --fresh --apply --require-complete
```

SRT / MP3 root (default):

`~/Documents/backup_on_2026-07-16_13inch_macbook/{year}答疑音頻`

Opus playback files: `~/tai/audio/` (linked from the site as `../audio/`).

## Media resolution

`resolve_media()` picks files for each PDF source (`官网` / `微信公众号` / `贴吧`).

If **官网** has no mp3/srt/opus for that day, it falls back to the same day's **贴吧** files (Aug–Sep transition used interchangeable names). The mapping's `audio_file` points at the resolved opus so play buttons work.

## Alignment rules

**Segment identity** (what is a new play range) is decided from the **spoken
answer opening** — floor (`第N楼` / `N楼`), `下一个问题` + new name/floor, or a
same-person follow-up (`第二个问题` / `下面的问题` / `最后问` / …). Full taxonomy:
[`audio_map/AGENTS.md`](../../audio_map/AGENTS.md). Split PDF-merged cards when
the speaker starts a new numbered unit; do not invent a global time offset.

- **2025-11 … 2026-03**: prefer times from `qa/*.txt`, fill gaps via SRT.
- **2025-06 … 2025-09**: SRT ordered fuzzy match against PDF question/answer text.
- Match order per question: **questioner name** (digits → 五七幺/五七一) → question body
  (honorifics stripped) → answer opening → global re-anchor.
- `match_start` returns the cue that *owns* the matched text (not the sliding-window
  start). This avoids ~20s-early starts when the window reaches into later speech
  (e.g. 2025-08-04 贴吧 Q1).
- Unmatched gaps are filled by monotonic interpolation (`notes: interpolated`) so the map has **zero missing** ranges.
- Re-runs skip segments with `locked: true` or `status: "manual"` (unless `--fresh`).
- Hard misses (no SRT at all): `fill_misses.py` retranscribes the session mp3 with [`tool/sense_voice`](../sense_voice/).
- If a session’s SRT is badly out of sync with the opus, force-retranscribe that mp3
  then `align.py --month YYYY-MM --fresh --apply --require-complete`.

## Browser editor

Open [`/audio_map/`](../../audio_map/). Load a month JSON, play ranges, tweak start/end, download or save via GitHub PAT.

## Build integration

**Do not edit `wenda2_ebook/*.html` by hand for play buttons.**

This package only writes `tool/word2ebook/data/audio_map/*.json`.  
At ebook build time, [`main.py`](../word2ebook/main.py) loads those maps via
`inject_chapters()` on in-memory `Chapter` objects, then
`HTMLGenerator` writes `wenda2_ebook/`. Use:

```bash
cd tool/word2ebook && python3 gen_all.py
# or partial: python3 main.py ... --only-pdf --pdf-start-index 12
```

Segments without a range get no play button; with `--require-complete` maps, every question/opening has a button.
