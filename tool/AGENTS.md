# tool/ — 工具與產生器目錄指南

> 每個工具的詳細規則、指令與資料流，以**該工具自己的 README / AGENTS.md** 為準（見下方表格「Docs」欄）。
> 這份文件只記錄「還有哪些工具、各自做什麼、誰依賴誰」，避免與各工具文件重複。

---

## 目錄總覽

| 工具 | 做什麼 | 輸入 → 輸出 | Docs |
|------|--------|-------------|------|
| `tool/word2ebook/` | 問答錄 2 電子書產生器（Word + 月 PDF）。前 12 章（Word 分類）播放鈕由 `audio_map2/*.json` 注入；13–21 章（PDF）播放鈕由 `data/audio_map/*.json` 注入。 | `問答錄2/*.docx` + `*.pdf` → `wenda2_ebook/` | **`AGENTS.md`**, `README.md`, `openspec/` |
| `tool/books2ebook/` | 坐禅系列 + 講經系列共十本原書 → 靜態電子書（簡/繁、全量搜尋、每講播放鈕）。 | `books/*.pdf` → `ebook/` | `README.md` |
| `tool/pdf_audio_map/` | 對齊 PDF 章節（13–21）↔ 音檔時間 → 音訊映射 JSON（SoT：`tool/word2ebook/data/audio_map/`）。 | SRT/opus → `data/audio_map/*.json` | `README.md` |
| `tool/word_audio_map2/` | 對齊**時間序** Word 彙總（2024-02…2025-05）↔ SRT → `audio_map2/*.json`（`build_maps.py`）。段上的 `chapter_question_ids` 供前 12 章注入；**分段會隨 `build_maps.py` 的 Q&A 偵測調整**，重分段後以 `link_chapters.py` 重新寫回章節對應（詳見「分段與章節對應」）。 | docx + SRT → `audio_map2/*.json` | `README.md` |
| `tool/sense_voice/` | FunASR 中文 ASR → `.srt`/`.txt`（被 `pdf_audio_map/fill_misses.py` 呼叫做補漏）。 | mp3/wav → srt/txt | `README.md` |
| `tool/audio_denoiser/` | Facebook Denoiser 語音去雜音（ASR 前處理）。 | mp3/wav → mp3/wav | `README.md` |
| `tool/stories2html/` | 實修故事原始檔 → HTML 閱讀頁 + index/sitemap 補丁。 | `stories/<原始檔>` → `stories/<slug>.html` | `README.md`（metadata SoT：`docs.py`） |
| `tool/build_jiangjing_pdfs.py` | 【一次性已完成】組裝講經系列 PDF：合併（六祖壇經 2 PDF、楞嚴 docx→PDF）、四十二章/楞伽直接複製原檔（已含目錄）、其餘補檔首可點擊 TOC（含頁數）。**講經 5 本 PDF 已產出且驗證無誤，若未來不再新增/修改講經 PDF，此工具與下方兩個音檔工具可一併刪除。** | 來源 PDF/docx → `books/06…09*.pdf` + 感恩 | 檔首 docstring |
| `tool/jiangjing2audio.py` | 【一次性已完成】講經系列 mp3 → opus（16kbps / mono / 48kHz / voip），檔名含錄音日期，輸出到 `audio/jiangjing/<日期>Tai师父讲经·<系列>(<N>).opus`（平放）。**105 支 opus 已轉檔、正規化完畢；若講經音檔不再新增，可刪除。** | mp3 → `audio/jiangjing/*.opus` | 檔首 docstring |
| `tool/normalize_jiangjing_audio.py` | 【一次性已完成】對齊既有答疑 opus 的平均音量（mean_volume ≈ -11 dB）：`volumedetect` 量平均音量 → `volume` + `alimiter` 補增益並重新編碼 opus。**原地更新** `audio/jiangjing/`。**已完成；若講經音檔不再新增，可刪除。** | `audio/jiangjing/*.opus`（原位） | 檔首 docstring |

### 已移除（不再保留）

以下工具為**一次性／已完成**流程，輸入或產生器已移除，故整包刪除（git 歷史仍可回溯）：

- ~~`tool/qa_resplit/`~~ — 對 `qa/*.txt`（校對轉錄稿，2025-11~2026-03）做 resplit/realign/TW-normalize；`qa/` 已刪，不再使用。
- ~~`tool/word_audio_map/`~~ — 主題式對齊器（舊 `data/audio_map_word/` 流程），源碼已刪。其 `.venv` 已搬至 `tool/word_audio_map2/`（供 `build_maps.py` 與 word2ebook 生成使用）。
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
        │                            (由 link_chapters.py 寫回；分段調整後需重跑)
        ▼
wenda2_ebook/  ← 建構產物，勿手改

books/*.pdf ── tool/books2ebook/gen_all.py ──► ebook/

講經系列（工具鏈，皆為**一次性組裝流程，已完成**）：
來源 PDF / docx ── tool/build_jiangjing_pdfs.py ──► books/06…09*.pdf（+ 感恩）【可刪除】
mp3 ── tool/jiangjing2audio.py ──► audio/jiangjing/<日期>Tai师父讲经·<系列>(<N>).opus（平放）【可刪除】
                                        │
                                        ▼ tool/normalize_jiangjing_audio.py（對齊答疑響度）【可刪除】
                                （原地更新 audio/jiangjing/）

SRT / opus ── tool/pdf_audio_map/ ──► tool/word2ebook/data/audio_map/*.json
                                        (補漏時經 tool/sense_voice/ 重新轉寫)

audio_map2/*.json 的產生：問答錄2 docx + SRT ── tool/word_audio_map2/build_maps.py ──► audio_map2/*.json
                                       └── 重分段後：link_chapters.py ──► 寫回 chapter_question_ids / chapter_indexes
```

### 分段與章節對應（word_audio_map2）

`build_maps.py` 把 Word 彙總切成「問答段」時，段數會隨 Q&A／後續題偵測邏輯調整；例如跨多個 `Taiguanglin：` 標記的同一作者貼文，可能被拆成多個子問答段。**過去假設「`audio_map2/*.json` 的分段不會再調整、`chapter_question_ids` 一次凍結即可」已不成立** —— 拆分邏輯會持續修正，所以：

- 重分段（`build_maps.py` 調整後）應以 `link_chapters.py` **為主**重新寫回每段的 `chapter_question_ids` / `chapter_indexes`（內容比對 `build/questions.json`）。預設 `--apply` 為 **fill-empty-only**——只補「缺章節」的段、絕不改已有人工校對連結的段、且只補尚未被任何段認領的 qid；`--apply --overwrite` 才整份重導（會丟掉未重新比到的既有 qid，慎用）。
- `link_chapters.py` 因過去假定「分段不再變」而被移除，現已**自 git 歷史恢復**（`tool/word_audio_map2/link_chapters.py`），供未來重跑。對帳驗證用 `validate_relink.py`（凍結 qid 零遺失 + 無新增跨 session 重複 qid）。
- 已人工校對的 `start`/`end`、`meta.lastPlayed` 等欄位在重分段時應**按內容比對搬移保留**，不要整份重建而遺失。

> 註：若未來不再新增/修改講經 PDF 或音檔，**上述標記【可刪除】的三個講經工具（`build_jiangjing_pdfs.py`、`jiangjing2audio.py`、`normalize_jiangjing_audio.py`）可整包移除**；`gen_all.py` 重建電子書時只需：讀 `books/*.pdf` → 解析/分段 → 產生 HTML → 依 `audio_map.py` 映射插入播放鈕，不再涉及 PDF 組裝與音檔轉檔。

> 註：`.venv`（`tool/word_audio_map2/.venv`）是唯一裝有 docx / opencc / slugify /
> yaml / jieba / pymupdf 的環境，`gen_all.py`（word2ebook）與 `build_maps.py`、
> `audio_map2/tools/*.py` 都以它為 python。

---

## 概略原則

1. **Generated 目錄勿手改**：`wenda2_ebook/`、`ebook/` 皆為建構產物；改產生器或來源後重跑對應 `gen_all.py`。
2. **音訊播放鈕只在注入器產生**：`tool/word2ebook/core/audio_map_injector.py`（PDF 13–21）與 `inject_word_chapters()`（Word 01–12）。別手改章節 HTML。
3. **離線媒體工具（sense_voice / audio_denoiser）為輔助流程**，不參與 Pages 佈署；只有在新音檔需要 ASR 時才用。
4. 每個工具的尖細規則放它自己的 README/AGENTS.md；跨工具／站台級慣例放根 `AGENTS.md`。
