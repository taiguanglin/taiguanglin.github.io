# tool/ — 工具與產生器目錄指南

> 每個工具的詳細規則、指令與資料流，以**該工具自己的 README / AGENTS.md** 為準（見下方表格「Docs」欄）。
> 這份文件只記錄「還有哪些工具、各自做什麼、誰依賴誰」，避免與各工具文件重複。

---

## 目錄總覽

| 工具 | 做什麼 | 輸入 → 輸出 | Docs |
|------|--------|-------------|------|
| `tool/word2ebook/` | 問答錄 2 電子書產生器（Word + 月 PDF）。前 12 章（Word 分類）播放鈕由 `audio_map2/*.json` 注入；13–21 章（PDF）播放鈕由 `data/audio_map/*.json` 注入。 | `問答錄2/*.docx` + `*.pdf` → `wenda2_ebook/` | **`AGENTS.md`**, `README.md`, `openspec/` |
| `tool/books2ebook/` | 坐禅系列五本原書 → 靜態電子書。 | `books/*.pdf` → `ebook/` | `README.md` |
| `tool/pdf_audio_map/` | 對齊 PDF 章節（13–21）↔ 音檔時間 → 音訊映射 JSON（SoT：`tool/word2ebook/data/audio_map/`）。 | SRT/opus → `data/audio_map/*.json` | `README.md` |
| `tool/word_audio_map2/` | 對齊**時間序** Word 彙總（2024-02…2025-05）↔ SRT → `audio_map2/*.json`；`link_chapters.py` 把 `chapter_question_ids` 寫回段上供前 12 章注入。 | docx + SRT → `audio_map2/*.json` | `README.md` |
| `tool/sense_voice/` | FunASR 中文 ASR → `.srt`/`.txt`（被 `pdf_audio_map/fill_misses.py` 呼叫做補漏）。 | mp3/wav → srt/txt | `README.md` |
| `tool/audio_denoiser/` | Facebook Denoiser 語音去雜音（ASR 前處理）。 | mp3/wav → mp3/wav | `README.md` |
| `tool/stories2html/` | 實修故事原始檔 → HTML 閱讀頁 + index/sitemap 補丁。 | `stories/<原始檔>` → `stories/<slug>.html` | `README.md`（metadata SoT：`docs.py`） |

### 已移除（不再保留）

以下工具為**一次性／已完成**流程，輸入或產生器已移除，故整包刪除（git 歷史仍可回溯）：

- ~~`tool/qa_resplit/`~~ — 對 `qa/*.txt`（校對轉錄稿，2025-11~2026-03）做 resplit/realign/TW-normalize；`qa/` 已刪，不再使用。
- ~~`tool/word_audio_map/`~~ — 主題式對齊器（舊 `data/audio_map_word/` 流程），源碼已刪。其 `.venv` 與三個 frozen 產物（`build/{questions,chrono_sessions,qid_bridge_v2}.json`）已搬至 `tool/word_audio_map2/`（後者供 `link_chapters.py` 讀用）。
- ~~`tool/video_creator/`~~ — 離線 ffmpeg（聲音 + `animation.mp4` → 影片），站外獨立用途，已移除。

---

## 依賴關係（誰讀誰）

```
問答錄2/*.docx + *.pdf
        │
        ▼
tool/word2ebook/  (gen_all.py)
   ├─ inject_chapters():           讀 tool/word2ebook/data/audio_map/*.json  (← tool/pdf_audio_map/)
   └─ inject_word_chapters():      讀 audio_map2/*.json 的 chapter_question_ids
        │                            (← tool/word_audio_map2/link_chapters.py)
        ▼
wenda2_ebook/  ← 建構產物，勿手改

books/*.pdf ── tool/books2ebook/gen_all.py ──► ebook/

SRT / opus ── tool/pdf_audio_map/ ──► tool/word2ebook/data/audio_map/*.json
                                        (補漏時經 tool/sense_voice/ 重新轉寫)
```

link_chapters 的輸入（frozen，不再重新產生，gitignored）：

```
tool/word_audio_map2/build/{questions.json, chrono_sessions.json, qid_bridge_v2.json}
```

---

## 概略原則

1. **Generated 目錄勿手改**：`wenda2_ebook/`、`ebook/` 皆為建構產物；改產生器或來源後重跑對應 `gen_all.py`。
2. **音訊播放鈕只在注入器產生**：`tool/word2ebook/core/audio_map_injector.py`（PDF 13–21）與 `inject_word_chapters()`（Word 01–12）。別手改章節 HTML。
3. **離線媒體工具（sense_voice / audio_denoiser）為輔助流程**，不參與 Pages 佈署；只有在新音檔需要 ASR 時才用。
4. 每個工具的尖細規則放它自己的 README/AGENTS.md；跨工具／站台級慣例放根 `AGENTS.md`。