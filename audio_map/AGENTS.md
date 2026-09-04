# audio_map — Agent / LLM Guide

> Editorial UI for aligning Q&A segments to session audio.  
> Repo-wide rules: [`../AGENTS.md`](../AGENTS.md).  
> Mapping JSON lives under `tool/word2ebook/data/` (not in this folder).

## What this tool is

Browser proofreading UI at `/audio_map/` for setting each PDF segment’s
**play range** (`start` / `end`) against local opus + SRT. Ebook play buttons are
injected from these maps at build time (`tool/word2ebook` → `inject_chapters`);
never hand-edit `wenda2_ebook/` for timings.

> **Word-chapter (01–12) proofreading has moved to `/audio_map2/`** (the
> chronological Word 彙總), driven by `audio_map2/*.json`. The previous
> Word editor (`assets/editor.word.js` +
> `tool/word2ebook/data/audio_map_word/word-*.json`) has been removed.

---

## index.html — PDF month maps proofreading UI（第 13–21 章）

`index.html` 是 **PDF 月份地圖**編輯器（PDF 已全數校對完成）。

## Segment identity (what counts as a new play range)

Judge a new Q&A segment from the **spoken answer opening**, not from PDF card
count alone. PDF consecutive `1、2、` often merge into one HTML question; the
speaker may still start a new spoken unit. Conversely, one PDF card may already
be one spoken unit.

Timing rules below only apply **after** the segment list is correct.

### Primary — new floor / new questioner

The answer **starts** with a floor and/or a new person. These open a new
primary segment (even if the same nickname posted earlier, e.g. later「第二十楼自然」):

| Spoken opening | Examples (2026-02-02 官网) |
|----------------|---------------------------|
| `第N楼` / `N楼` + name | 「第二楼印龙」「第三楼zzx」「8楼明月照我心」「第9楼13020466664」「第十楼牧羊少年」「第十二楼自然」「14楼上官」「第十八楼原油宝宝」「24楼aaa」 |
| `下一个问题` + floor and/or new name | 「下一个问题ming」「下一个问题11楼Wangguangying」「下一个问题13楼caomao123」「下一个问题15楼枫红201九」「下一个问题，26楼qq123」 |
| Floor after ASR noise | 「下一个问题1楼muma吉利」(十七→1)、「下一个问题23楼，两个句号」 |

`第一个问题` right after a floor (「第六楼guangTz，第一个问题」) stays **in that primary** — it is not a split point.

### Follow-up — same person, next numbered / topic unit

Still its **own** segment. Typical openings:

| Spoken opening | Examples |
|----------------|----------|
| `第二个问题` / `第三个问题` / `第N个问题` | zzx Q2；无境 Q2；guangTz 脑梗；枫红 腰塌；幻世浮生 Q2–Q3 |
| `下一个问题` **without** a new floor/name | 无境 Q3「下一个问题，弟子想知道如何分辨…」 |
| `下面的问题` / `下面说…` | 「下面的问题，其次就是地球上…」「下面说你的身体的问题」 |
| `还有下一个问题` / `还有下面…` / `还有第N个问题` | 「还有下一个问题，你忍辱…」「还有第四个问题」「还有第二个问题说往生…」 |
| `最后问` | 「最后问我这种业重凡夫今生能否还有机会往生极乐？」 |
| Topic restatement only (no marker) | 「关于思佛…」「你说巫的传承…」「还有中邪的问题…」 |

When PDF swallowed a later numbered item into the previous answer (Chinese `二、` not parsed as a new card, or Tai reading Q2 inside the previous answer block), **split** at the spoken follow-up opening. Put the swallowed question body on the new segment’s `q_text`; `answer_text` starts at the spoken marker. The PDF parser now emits a matching extra `.question` card (`一、`/`二、` after an answer, `第二个问题是，…`, dumped `第二个问题，…` / `第二个问题 家族…` / `二是关于…` / circled `②…`, and unnumbered dumps `最后一个不是问题…` / `第二件事情…` / `另外想请教师父…` / `还有我现在…` when the next opener is `Taiguanglin：`, digit nicknames including `57`, period nicknames `。`/`。。`, `名字：，` missing-timestamp headers, nameless posts after a separator (`顶礼` / `师父好` / glued `：正文`) with the nickname recovered from Tai’s `下一个问题，名字`, and `名字：正文` glued on one line). Do not treat Tai’s answer enumerators `第一，`/`第二，` or in-answer ①②③ listings as new cards. After a rebuild, refresh map `question_id`s with `align.py --text-only` (keeps times).

### Do not split

- Mid-answer recap of the **same** question.
- The answerer's self-answered continuation「昨天还有人问…？」(also `昨天就有人问` / `昨天有人问`) — the master referencing a past question as part of the **same** answer, **not** a new question. Keep it inside the current answer (2025-07-08 贴吧 咪了个喵xxx).
- Declining a later number in the same breath (「第三个问题就不用回答了」) — stay on the current segment.
- Reading the next question’s body (`二、关于疾病…`) **before** the spoken `第二个问题…` — that body is `q_text` of the **next** segment, not a third range.
- Opening (`今天是…先回答官网/贴吧/微信`) and closing (`官网的答疑就到这里`) are not Q&A segments.

### Opening vs first answer

Opening is only the date/source intro. The first Q&A segment starts at the first primary opening (「第二楼…」/「下一个问题…」), **not** at `00:00:00` if that still contains「今天是…」. Opening **end** = segment 1 **start** (never inverted).

---

## Alignment principles (stable — do not invent alternatives)

When correcting or batch-realigning **already-identified** segment boundaries,
follow these rules **file-by-file** (verify each session against SRT / listening,
do not blind-apply a global offset).

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
