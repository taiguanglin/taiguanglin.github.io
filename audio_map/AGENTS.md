# audio_map — Agent / LLM Guide

> Editorial UI for aligning PDF Q&A segments to session audio.  
> Repo-wide rules: [`../AGENTS.md`](../AGENTS.md).  
> Mapping JSON lives in `tool/word2ebook/data/audio_map/*.json` (not under this folder).

---

## What this tool is

Browser proofreading UI at `/audio_map/` for setting each segment’s **play range**
(`start` / `end`) against local opus + SRT. Ebook play buttons are injected from
these maps at build time (`tool/word2ebook` → `inject_chapters`); never hand-edit
`wenda2_ebook/` for timings.

---

## Alignment principles (stable — do not invent alternatives)

When correcting or batch-realigning segment boundaries, follow these rules
**file-by-file** (verify each session against SRT / listening, do not blind-apply
a global offset).

### 1. Prefer spoken「下一个问题」

When the host says「下一个问题」(or close ASR variants such as「下个问题」/
「那下一个问题」), the **new segment starts shortly before the character「下」**
in that phrase (interpolate within the SRT cue if needed).

### 2. No「下一个问题」→ match paragraph onset

If that transition phrase is absent, align to the **spoken start of that
segment’s opening text** (answer / questioner name / first content), then apply
the same lead-in rule below. Inspect these cases individually.

**Always cross-check content:** after choosing an onset (whether from
「下一个问题」or text match), confirm the following SRT window overlaps the
segment’s answer/name. Reject / skip a next_q hit that does not match content —
do not consume anchors in order blindly, or one early miss will shift every later
segment.

### 3. Adaptive lead-in (not a hard −0.5s)

Do **not** always subtract 0.5s. Choose lead-in from the **pause between the
previous spoken cue and the onset** (「下」or content start):

| Pause after previous speech | Lead-in before onset |
|-----------------------------|----------------------|
| Large enough (≥ ~0.55s)     | **0.5s** (normal)    |
| Medium                      | **0.2–0.4s**         |
| Nearly continuous / tiny gap| **0.1–0.15s**        |

Never cut into the previous cue’s spoken audio: clamp start to at least the
previous cue’s end (effective lead may shrink to ~0 when speech is back-to-back).

### 4. Ends and chain

- Segment **end** = next segment’s **start**.
- Opening ends at segment 1 start.
- When a **closing（收場）** exists with a range: last segment end = closing
  start; closing end = audio end. Otherwise last segment end = audio end.
- Preserve user-`locked` / explicitly kept starts when only repairing a suffix
  of a session (e.g. “from segment N onward”).

### 5. Opening vs closing (completion)

- **開場** is optional for session completion (may stay unlistened).
- **收場** is required: it counts toward must-calibrate items together with all
  Q&A segments. A date/session is complete only after every segment **and** the
  closing have been listened (`meta.lastPlayed`).

### 6. Tooling hints

- Helpers: `tool/pdf_audio_map/realign_half_second.py` (`adaptive_lead`,
  `start_from_onset`, `--adjust-leadin`).
- Batch content-aware realign: `tool/pdf_audio_map/realign_content_aware.py`
  (下一个问题 + content score; skips already proofread 2025-06-12 / 06-13-wechat
  by default; scope `2025-06-13-tieba` + `date >= 2025-06-14`).
- Backfill closing ranges: `tool/pdf_audio_map/backfill_closing.py --apply`.
- After map edits that should reach the ebook: rebuild via
  `tool/word2ebook/gen_all.py` (or `--only-pdf` inject), do not patch chapter HTML.

---

## Source of truth

| Path | Role |
|------|------|
| `tool/word2ebook/data/audio_map/YYYY-MM.json` | Month maps (start/end + PDF text fields) |
| `audio_map/` (this dir) | UI only |
| Local SRT under the machine’s 答疑音頻 backup | Reference for「下一个问题」/ onset |
| `audio/` symlink | Local opus playback (gitignored) |
