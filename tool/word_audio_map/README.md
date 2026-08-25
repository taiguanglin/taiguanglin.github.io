# word_audio_map

Align **Word-ebook Q&A** (chapters 01–12 of `wenda2_ebook/`, the categorised
Word document) to audio time ranges, then let `word2ebook` inject per-question
`.qa-play` buttons at build time.

Counterpart of [`../pdf_audio_map`](../pdf_audio_map) — that tool covers the
monthly PDF chapters (13–21); this one covers the Word chapters.

## Why a different matcher than pdf_audio_map

In the Word-era recordings the teacher usually speaks the asker's name and
answers in his own words. The written question is often **not read aloud**, the
written answer is an edited version of what was said, and ASR adds homophone
noise (业→夜, 自性→自信). So alignment runs on **toneless pinyin streams**
(OpenCC → strip → pypinyin):

1. locate the asker's name in the session stream
2. verify with the longest common block between the written answer/question
   (pinyin) and the window after that name occurrence
3. accept above threshold; claims inside one session are resolved greedily by
   score with exclusive stream regions
4. no usable name → answer-text search over the whole stream (prefiltered)

Questions are only tried on the first 14 sessions from their submission date
(45-day cap), so "asked during a recording gap, answered when recordings
resume" still matches. A global sweep with a higher bar picks up leftovers.
Segments without a confident match get **no button** — there is deliberately
no interpolation.

## Data sources

- Questions: parsed from the `.docx` through word2ebook's own
  `DocumentParser`, so question ids/texts are identical to build time.
- SRT / MP3: `~/Documents/backup_on_2026-07-16_13inch_macbook/{2024,2025}答疑音頻`
- Opus playback files: `~/tai/audio/` (site serves `/audio/`; all SRT stems
  already have a same-name opus).

## Commands

```bash
cd tool/word_audio_map
python3 -m venv .venv && .venv/bin/pip install pypinyin opencc-python-reimplemented

# 1) extract questions from the docx (build/questions.json)
./.venv/bin/python extract_questions.py

# 2) align (dry run prints coverage; --apply writes the maps)
./.venv/bin/python word_align.py            # dry run + review report
./.venv/bin/python word_align.py --apply    # write data maps
```

Outputs:

- `tool/word2ebook/data/audio_map_word/word-NN.json` — one file per chapter,
  segments keyed by stable `question_id` (+ start/end/confidence/session info)
- `build/review_report.md` — low-confidence matches + missing-by-reason list

Manual fixes: edit a segment in `word-NN.json`, set `"locked": true`
(or `"status": "manual"`); re-runs preserve locked/manual segments.

### Review tier & the near-forward retry

The teacher answers on a few fixed days per month and rests roughly a month
after five months of answering, so answers usually land on the FIRST recording
day at/after the question date (wechat or tieba alike). Two near-pass modes:

```bash
# calendar-day window
./.venv/bin/python word_align.py --near-only --near-days 10

# domain-rule mode: the first N distinct answer days at/after the question
# date, with lowered thresholds (calibrated: true matches score >=10 within
# their own first-date session ~95% of the time)
./.venv/bin/python word_align.py --near-only --mode answer-days \
    --max-answer-dates 2 --t-accept 12 --t-noname 13 --t-review 9
```

Segments whose evidence is borderline (`status: "review"`) are stored **without
a button** — the injector skips `review`. After listening, flip `"status"`
to `"auto"` (add `"locked": true`) and rebuild with `gen_all.py`.
`verify_build.py` treats review as buttonless and reports its count.

Retries never double-book an existing button's opening (~75 s start zone).

### Fine boundary calibration

`calibrate.py` refines every mapped segment's start to the actual spoken onset
(audio_map/AGENTS.md principles): prefer the「下一个问题」transition character,
else the name/answer onset with intra-cue interpolation; adaptive lead-in from
the pause (0.5s…0.1s, never cutting previous speech); `end_i = start_{i+1}`.
Locked/manual segments are untouched; shifts >90 s are rejected as mis-anchors.

```bash
./.venv/bin/python calibrate.py           # dry run + shift statistics
./.venv/bin/python calibrate.py --apply   # write maps
```

Run it again after adding new matches; re-running is idempotent (shifts <50 ms
are skipped). Provenance is recorded per segment as `notes=…;cal(lead=…,…)`.

### Re-transcription note

Re-transcribing an mp3 with `tool/sense_voice` reproduces the backup SRTs
byte-for-byte (same Paraformer pipeline produced them), so it adds no new
information. Pass local model paths to dodge a modelscope/macOS download bug:
`--asr-model ~/.cache/modelscope/hub/models/iic/<asr>` (same for vad/punc).

### Audit reports

- `build/review_report.md` — low-confidence autos + missing by reason
- `build/rule_violations.md` — existing buttons whose session is NOT the
  first recording day after the question date (6% as of writing; sweep-method
  entries deserve listening first)
- `build/evidence_hist.log`, `build/calibrate.log` — threshold calibration

## Build integration

`main.py` calls `inject_word_chapters()` right after the PDF
`inject_chapters()`. The injector scans every chapter for
`<div class="question" id="…">` and inserts a meta bar before each mapped
question; unmapped questions stay buttonless, existing bars are never
duplicated. Rebuild with:

```bash
cd tool/word2ebook && python3 gen_all.py
```

## Tuning knobs (`word_align.py`)

| Flag / constant | Meaning |
|---|---|
| `T_ACCEPT = 16` | min LCB (pinyin chars) for a name-anchored match |
| `T_NONAME = 26` | higher bar when matching without a spoken name |
| `MAX_SESSIONS_PER_QUESTION = 14` | how many sessions after submission to try |
| `WINDOW_DAYS_DEFAULT = 45` | hard date cap on those sessions |
| `--workers` | process pool size (default 6) |
