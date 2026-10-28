# tool/ — 工具與產生器目錄指南

> 每個工具的詳細規則、指令與資料流，以**該工具自己的 README / AGENTS.md** 為準（見下方表格「Docs」欄）。
> 這份文件只記錄「還有哪些工具、各自做什麼、誰依賴誰」，避免與各工具文件重複。

---

## 目錄總覽

| 工具 | 做什麼 | 輸入 → 輸出 | Docs |
|------|--------|-------------|------|
| `tool/word2ebook/` | 問答錄 2 電子書產生器（Word + 月 PDF）。前 12 章（Word 分類）播放鈕由 `audio_map2/*.json` 注入；PDF 分類條目播放鈕由站台根目錄 `audio_map/*.json`（單一 SoT）注入。 | `問答錄2/*.docx` + `*.pdf` → `wenda2_ebook/` | **`AGENTS.md`**, `README.md`, `openspec/` |
| `tool/site_chrome/` | 全站共用導覽的單一真相來源：把「圖解」下拉 3 入口（名詞圖解／坐禪與講經心智圖／問答錄2心智圖）、圖解頁 JSON-LD 寫回所有共用 chrome 頁；`sitemap.py` 產生 `sitemap.xml`（唯一 SoT，`--check` 可驗）；`indexnow.py` 送變更通知（Bing 等參與者立刻重抓）；並附站台一致性檢查（AI 免責聲明、canonical、連結／錨點、sitemap、圖片屬性、`b-truth` 三節點、**電子書 SEO／JSON-LD**）＋免 jsdom 的下拉互動測試。 | `sync.py` 定義 → root／`wenda2/`／`stories/` HTML；`dropdown_harness.js` 驗互動 | `README.md` |
| `tool/books2ebook/` | 坐禅系列 + 講經系列九本著作（＋卷首《感恩與講經》一篇）→ 靜態電子書（簡/繁、全量搜尋、每講播放鈕、講經段落跟播）。`sync_para_pids.py` 修 pid 漂移；`pytest tests/` 守門「已校對講次真的能跟播」。 | `books/*.pdf` + `audio_map3/*.json` → `ebook/` | `README.md` |
| `tool/pdf_audio_map/` | 對齊 PDF 分類條目 ↔ 音檔時間 → 音訊映射 JSON（單一 SoT：站台根目錄 `audio_map/`，2026-10-26 起；與校對 UI 同一份）。 | SRT/opus → `audio_map/*.json` | `README.md` |
| `tool/word_audio_map2/` | 對齊**時間序** Word 彙總（2024-02…2025-05）↔ SRT → `audio_map2/*.json`（`build_maps.py`）。段上的 `chapter_question_ids` 供前 12 章注入；**分段會隨 `build_maps.py` 的 Q&A 偵測調整**，重分段後以 `link_chapters.py` 重新寫回章節對應（詳見「分段與章節對應」）。 | docx + SRT → `audio_map2/*.json` | `README.md` |
| `tool/sense_voice/` | FunASR 中文 ASR → `.srt`/`.txt`（被 `pdf_audio_map/fill_misses.py` 呼叫做補漏）。 | mp3/wav → srt/txt | `README.md` |
| `tool/audio_denoiser/` | Facebook Denoiser 語音去雜音（ASR 前處理）。 | mp3/wav → mp3/wav | `README.md` |
| `tool/stories2html/` | 實修故事原始檔 → HTML 閱讀頁 + index/sitemap 補丁。 | `stories/<原始檔>` → `stories/<slug>.html` | `README.md`（metadata SoT：`docs.py`） |
| `tool/fonts/` | 全站字型自架子集管線：掃站用頁面語料（含 OpenCC 簡體聯集）→ pyftsubset 產十字重 woff2＋`fonts.css`，取代 Google Fonts 外鏈（大陸連不上）。 | root/`wenda2/`/`stories/` 頁面語料 → `fonts/` | `README.md`（執行用 word_audio_map2 的 venv；fonttools 在 `.pylibs`） |
| `tool/daily_quotes/` | 首頁「每日精選」語料管線：從兩套電子書索引抽候選（長度 60–400、黑名單、CJK 比例 ≥60%、**排除經文**（`scripture_filter.py` 三道防線）、md5 去重）→ `candidates.json`（15,299 條）；固定種子抽 2,400 條交 AI 評分（0–10）→ `select_1095.py` 以 score≥7 為骨架、其餘按可讀性啟發式補足→ repo 根目錄 `daily_quotes.json`（1,095 條，單一來源 ≤70%），由 `index.html` 依日期播種輪播；`audit_quotes.py` 稽核成品（有經文／斷鏈即 exit 1）；**`refresh_sample.py` 把凍結的 `candidates_sample.json` 的文字／網址對齊現況電子書**（條數與順序不可動 → AI 評分的 idx 對應關係不變），`select_1095.py` 另會以「文字」重新定位樣本裡過期的 pid（pid＝段落文字雜湊，區塊切分一改就換）。 | `{wenda2_ebook,ebook}/search_index_trad.json` → `build_quotes.py` → `candidates.json`；＋`candidates_sample.json`／`scores/batch_*.json` → `select_1095.py` → `daily_quotes.json` → `audit_quotes.py` | **`README.md`** |
| `tool/jiangjing_para_map/` | 講經系列「段落 ↔ SRT 字元時間流」對齊 → `audio_map3/<series>.json`；重跑保留已 confirmed 段落與 reviewed 講次。books2ebook 只注入 reviewed 講次的段落時間。 | ebook HTML 段落 + `audio/srt/jiangjing/*.srt` → `audio_map3/*.json` | `README.md` |
| `tool/qa_curation/` | 問答錄2「拆分＋分類」準則 SoT：把第 1–12 章（5,789 則人工分類）逐一實證檢驗後，整理成供 LLM 對第 13–21 章（未分類月度答疑）執行「問題拆分＋12 章主題分類」的操作準則——主準則（鐵律/拆分統計/分類總綱/輸出 schema）＋12 個逐章準則檔＋skill 檔。分類母體＝分類精選工作表「答疑汇总」A–D 欄。 | 13–21 章問答串 → JSONL（`section_path`＋信心＋依據） | **`README.md`**, `wenda2_split_classify_criteria.md`, `SKILL.md`, `chapters/` |
| `tool/world_model/` | 三千大千世界模型圖素材：把兩套電子書的**生成產物**抽成純文字語料，再依 16 個主題章（宇宙總綱／三千大千世界／須彌山／**世界的基本構造**／三界二十八天／人間／地獄／六道／佛國／光子物理／六根複眼／時間劫／神通）逐字彙整，供餵大模型畫世界模型圖。讀電子書而非 PDF/Word，是為了拿到全量段落索引（可驗證無遺漏）、穩定錨點（可回溯）、並免寫第二套 PDF 解析器。`verify.py` 逐行回比原始 HTML。 | `wenda2_ebook/*_trad.html` + `ebook/*_trad.html` → `build/world_model_{source,core}.md` + `.jsonl`（`build/` 已 gitignore） | `README.md` |
| `tool/series2audio.py` | 新錄音系列（義理／圓覺經／心經／金剛經）mp3·m4a → **去雜音（DNS64）+ 音量正規化** → opus（16kbps / mono / 48kHz / voip），輸出 `audio/yili/` 與 `audio/jiangjing/`。整合已移除的一次性三步（`jiangjing2audio.py`＋`normalize_jiangjing_audio.py`，加上 `audio_denoiser/denoise_jiangjing.py`）為一步（模型每個 worker 只載入一次）。 | `~/Downloads/Tai师父*/音頻/*.mp3`／`*.m4a` → `audio/{yili,jiangjing}/*.opus` | 檔首 docstring |
| `tool/audio_index/` | 掃描整個 `audio/` 目錄產生入口頁 `audio/index.html`（粉色系、置頂大悲咒、類別下拉篩選）；新增任何 `*.opus` 都會自動進清單。 | `audio/**/*.opus` → `audio/index.html` | **`README.md`** + `index_template.html` |

### 已移除（不再保留）

以下工具為**一次性／已完成**流程，輸入或產生器已移除，故整包刪除（git 歷史仍可回溯）：

- ~~`tool/qa_resplit/`~~ — 對 `qa/*.txt`（校對轉錄稿，2025-11~2026-03）做 resplit/realign/TW-normalize；`qa/` 已刪，不再使用。
- ~~`tool/wenda2_curation/`~~ — 問答錄 2 心智圖的資料 SoT（57 名詞結構、逐字引句、名詞統計）與產生器（`build_mm.py`／`build_mm2.py`、`data/*.json`、`mm_data.js`）。發布頁 `wenda2_mindmap.html` **自包含且保持不動**，往後不再重新生成，來源與產生器已於 2026-09-28 整包移除（更早的知識頁部分已於 2026-09 移除）。
- ~~`tool/word_audio_map/`~~ — 主題式對齊器（舊 `data/audio_map_word/` 流程），源碼已刪。其 `.venv` 已搬至 `tool/word_audio_map2/`（供 `build_maps.py` 與 word2ebook 生成使用）。
- ~~`tool/video_creator/`~~ — 離線 ffmpeg（聲音 + `animation.mp4` → 影片），站外獨立用途，已移除。
- ~~`tool/session_knowledge/`~~ — 查證工程 session 紀錄生成器（`SESSION_KNOWLEDGE.md` → `session_knowledge.html`，內部 noindex 頁）。連同 `SESSION_KNOWLEDGE.md`、生成物、`.sk-*` CSS、`mm_harness.js` 於 2026-09 徹底移除，git 歷史可回溯。
- ~~`tool/wenda2_knowledge/`~~、~~`tool/ebook_knowledge/`~~ — 兩套「複習用」電子書產生器（輸出＝`hidden/` 四本複習書＋入口，noindex 未公開頁）。`hidden/` 輸出於 2026-10-11 從部署移除（commit `15bbfd7`）；產生器連同內容 SoT（`src/*.py`）、語料快取與 README 同日整包刪除——git 歷史（`3c40066` 及更早）可完整回溯。
- ~~`tool/fix_yuanjue_sutra_numbers.py`~~、~~`tool/build_jiangjing_pdfs.py`~~、~~`tool/jiangjing2audio.py`~~、~~`tool/normalize_jiangjing_audio.py`~~ — 四支已完成的一次性工具（2026-10-26 移除）：《圓覺經》PDF 條目編號粗體化（188 處）、講經 5 本 PDF 組裝、講經 105 支 mp3→opus 轉檔、opus 響度正規化。產物（`books/`、`audio/jiangjing/`）已落地且驗證，不需要工具本體；日後新增講經 PDF/音檔改用 `tool/series2audio.py`（音檔）並以 git 歷史回溯舊工具。
- ~~一次性音頻對齊修正腳本~~（2026-10-26 移除）— `tool/fix_20250901_sunhong_merge.py`、`tool/fix_20250712_suxiaoya_remove.py`、`tool/pdf_audio_map/merge_20250901_sunhong.py`、`tool/pdf_audio_map/apply_audit_fixes_20261025.py`、`tool/pdf_audio_map/apply_20261026_fixes.py`、`tool/qa_split_ebook/realign_classified_seq.py`，連同兩份稽核報告 `audio_map_alignment_audit_20261025/26.md`。修正都已寫進映射 SoT（`audio_map/`）與版控產物，git 歷史（`aff3286`）可完整回溯。

---

## 依賴關係（誰讀誰）

```
問答錄2/*.docx + *.pdf
        │
        ▼
tool/word2ebook/  (gen_all.py —— stage 1：就地重建 wenda2_ebook/ 為 21 章時間序底稿)
   ├─ inject_chapters():           讀 audio_map/*.json（站台根目錄單一 SoT，← tool/pdf_audio_map/ 與校對 UI）
   └─ inject_word_chapters():      讀 audio_map2/*.json 的 chapter_question_ids
        │                            (由 link_chapters.py 寫回；分段調整後需重跑)
        ▼
wenda2_ebook/  ← stage 1 底稿（01–12 Word ＋ 13–21 PDF 月度章）
        │
        ▼ tool/qa_split_ebook/  extract.py（stage 2：抽 13–21 → build/items.jsonl）
        │                        gen_classified.py（stage 3：就地轉成 12 章分類合併版，
        │                                              13–21 換成跳轉頁）
        ▼
wenda2_ebook/  ← 發布成品（分類合併版），勿手改
   （wenda2_ebook_word/ 中繼目錄已於 2026-10-26 移除，不再存在）

books/*.pdf ── tool/books2ebook/gen_all.py ──► ebook/

講經 PDF/音檔的一次性組裝工具已移除（見上「已移除」；日後新音檔走 series2audio.py）：

新錄音（義理／圓覺經／心經／金剛經…）：
~/Downloads/Tai师父*/音頻/*.mp3|m4a
        │
        ▼ tool/series2audio.py（DNS64 去雜音 + 音量對齊 -11 dB + opus 16kbps）
   audio/yili/*.opus（義理系列）、audio/jiangjing/*.opus（圓覺經／心經／金剛經…）
        │
        ▼ tool/audio_index/build_index.py（掃描全部 *.opus）
   audio/index.html（入口頁；audio/ 本身不在本 repo git 內）

SRT / opus ── tool/pdf_audio_map/ ──► audio_map/*.json（站台根目錄單一 SoT）
                                        (補漏時經 tool/sense_voice/ 重新轉寫)

audio_map2/*.json 的產生：問答錄2 docx + SRT ── tool/word_audio_map2/build_maps.py ──► audio_map2/*.json
                                       └── 重分段後：link_chapters.py ──► 寫回 chapter_question_ids / chapter_indexes
```

### 首頁「每日精選」（tool/daily_quotes）

```
wenda2_ebook/search_index_trad.json（只取 answer 條目）┐
ebook/search_index_trad.json（content + answer 條目）  ┘
        │ tool/daily_quotes/build_quotes.py
        │   規則過濾：長度 60–400、黑名單（敷衍回答／亂碼問號／URL／時間戳行…）、
        │   CJK 比例 ≥60%、**排除經文**（見下）、md5 去重；
        │   clean() 會去掉開頭署名「Taiguanglin」與前導時間段
        ▼
   tool/daily_quotes/candidates.json            15,299 條（完整候選池，已進版控）
        │ 固定種子抽樣 2,400 條 → candidates_sample.json → 分批交 AI 評分 0–10
        ▼
   tool/daily_quotes/scores/batch_00..23.json   2,400 筆
        │   ⚠️ 每筆的 `idx` 是**索引進 candidates_sample.json 的位置**，不是 candidates.json
        ▼
   tool/daily_quotes/select_1095.py
        │   骨架：score ≥ 7（341 條，按分數降冪）
        │   補足：candidates.json 中未被評分過的候選，按 heuristic() 可讀性啟發排序（754 條）
        │          （長度窗、結尾標點、教學詞加分；前導時間戳／暱稱／英文代號、連續問號、
        │            括號不配對、數字比例過高、提問句罰分）
        │   來源上限：單一來源（ebook）≤ 70%（其餘靠 wenda2 平衡）
        │   ⚠️ 骨架與補足**都**要再過一次 scripture_filter（經文不得進入成品）
        ▼
   daily_quotes.json（repo 根目錄，1,095 條）
        │ tool/daily_quotes/audit_quotes.py：經文／斷鏈／重複／條數／來源配額，
        │   有問題 exit 1。重跑管線後務必跑一次再提交（--strict 連放寬掃描也擋）
        ├─ index.html：fetch 後以本地日期播種（day*2654435761+97 取正模）輪播；
        │  同日同機一致，清單長度變動會重洗順序；附前一天／後一天／前後一個月跳轉
        └─ tool/fonts/build_fonts.py：把整個 daily_quotes.json 納入字型子集語料
           （動態注入的文字也必須有自架字型覆蓋）
```

> 註：`candidates.json`、`candidates_sample.json`、`scores/` **皆納入版控**（可重用的候選池與既有 AI 分數）；只有 `batches/`（評分前的暫存分批）在 `tool/daily_quotes/.gitignore` 內被忽略。
> 註：`candidates_sample.json` 沒有產生腳本（當初以固定種子人工抽樣）。要提升品質時：從 `candidates.json` 抽更多樣本評分 → 擴充／覆蓋 `scores/` → 調整 `select_1095.py` 的 `TARGET`（目前 1095＝三年份）後重跑；分數與啟發式比例可能隨過濾規則微調而變動，重跑後請更新 README 的數字。

#### 經文不得進入每日精選（`scripture_filter.py`）

**經文判定只有這一個來源**，`build_quotes.py`／`select_1095.py` 都 import 它——不要再
在各腳本裡另寫一份（過去正是兩份弱規則各自漂移，導致經文漏進成品，例如六祖壇經
「師示眾云：善知識！本來正教，無有頓漸……」）。三道防線：

- **A. 結構錨點（權威）**：`tool/books2ebook` 用兩種結構標出經文——
  ① 講經系列以楷體排的**原經文** `<div class="sutra-text para-block" id="p-x">`；
  ② 《金剛經 心經》《圓覺經》每章的**白話譯文**，即落在
  `<div class="label-heading">譯文</div>` 與下一個 label 之間的段落
  （`解析`／`註解`／`本章大義` 才是老師的講解，保留）。這些 id 與
  `search_index*.json` 的 url 一一對應（實測 sutra-text 4,231/4,231 全中）。
  2026-10 起《金剛經 心經》《圓覺經》「解析」裡**重引的經文條目**（粗體、
  前面帶數字編號）也改以經文區塊輸出 → 同樣由 ① 涵蓋。
  **不要用文字規則取代它**——很多經文沒有 `佛告`／`善知識` 之類的對話標記。
- **B. 文言啟發式（補漏）**：古典對話／稱謂標記 **且** 現代語助詞 ≤ 3。抓的是不在
  上述區塊的經文（書末附錄等），實測精確率 100%。
- **C. 人工複查清單**（`exclude.json`）：講經書「解析」區段裡偶爾整段其實是經文
  白話譯文，A/B 分不出來，由人工複查後列名排除（附判斷依據）。

⚠️ 不要改成「現代助詞密度低就排除」：講經講解本身就是書面語，會大量誤殺。
⚠️ **引用 ≠ 經文**：師父講解時引一兩句經文是正常的，只要師父自己的話是主體就保留。

新增講經電子書或改 `books2ebook` 的楷體判定後，務必重跑
`build_quotes.py` → `select_1095.py` → `audit_quotes.py`；規則涵蓋不到「解析區段
裡夾帶的整段譯文」，重建後仍應把成品再送一次人工複查。

### 分段與章節對應（word_audio_map2）

`build_maps.py` 把 Word 彙總切成「問答段」時，段數會隨 Q&A／後續題偵測邏輯調整；例如跨多個 `Taiguanglin：` 標記的同一作者貼文，可能被拆成多個子問答段。**過去假設「`audio_map2/*.json` 的分段不會再調整、`chapter_question_ids` 一次凍結即可」已不成立** —— 拆分邏輯會持續修正，所以：

- 重分段（`build_maps.py` 調整後）應以 `link_chapters.py` **為主**重新寫回每段的 `chapter_question_ids` / `chapter_indexes`（內容比對 `build/questions.json`）。預設 `--apply` 為 **fill-empty-only**——只補「缺章節」的段、絕不改已有人工校對連結的段、且只補尚未被任何段認領的 qid；`--apply --overwrite` 才整份重導（會丟掉未重新比到的既有 qid，慎用）。
- `link_chapters.py` 因過去假定「分段不再變」而被移除，現已**自 git 歷史恢復**（`tool/word_audio_map2/link_chapters.py`），供未來重跑。

`tool/word_audio_map2/` 內的腳本分工（詳見該目錄 `README.md`）：

| 腳本 | 用途 |
|------|------|
| `build_maps.py` | 主產生器：時間序 Word 彙總 → `audio_map2/*.json`（問答分段）。 |
| `link_chapters.py` | 章節對應之主：以內容比對把 `chapter_question_ids`/`chapter_indexes` 寫回；預設 fill-empty-only。 |
| `apply_resplit.py` | 用改過的分段邏輯重跑 parser，並按內容比對搬移舊段 `start/end`、`meta.lastPlayed` 等已校對欄位。 |
| `validate_resplit.py` | 結構驗證：index 連續、`stable_key`/`question_id` 唯一、章節覆蓋、時間單調。 |
| `validate_relink.py` | 對帳驗證：比對 git `HEAD`，強制「凍結 qid 零遺失」+「無新增 spurious 跨 session qid」+「`meta.lastPlayed` 不變」。 |
| `fill_orphan_chapters.py` / `redistribute_chapters.py` / `reconcile_qids.py` | 重分段與重對應之間的墊補（補孤兒章節 / 重分配多 qid 清單 / 掛回遺失 qid）。 |
| `fill_resolvable.py` | 為「有實質問答卻未對應」的段，以 q_text（include/ratio，並有最短字數護欄）補上分類題；列印每筆待人工複核。 |

> 有「最後播放」(`meta.lastPlayed`) 紀錄的段**任何腳本都不應改動**——人工校對音檔時間的完成判定以此為準。

> 註：講經 PDF 組裝與音檔轉檔的一次性工具（`build_jiangjing_pdfs.py`、`jiangjing2audio.py`、`normalize_jiangjing_audio.py`）已於 2026-10-26 整包移除（git 歷史可回溯，見上「已移除」）。`gen_all.py` 重建電子書時只需：讀 `books/*.pdf` → 解析/分段 → 產生 HTML → 依映射插入播放鈕，不再涉及 PDF 組裝與音檔轉檔；日後新增講經音檔走 `tool/series2audio.py`。

> 註：`.venv`（`tool/word_audio_map2/.venv`）是唯一裝有 docx / opencc / slugify /
> yaml / jieba / pymupdf 的環境，`gen_all.py`（word2ebook）、`gen_all.py`（books2ebook）
> 與 `build_maps.py`、`audio_map2/tools/*.py` 都以它為 python。
>
> ⚠️ **依賴已鎖版**：安裝依 `tool/word_audio_map2/requirements.txt`（全部 `==`），
> 重建電子書一律用該 venv，**不要用系統 python**。原因：PDF 文字抽取在斷行處
> 怎麼補空格會隨 PyMuPDF 版本改變，`books2ebook` 的 `_join()` 依賴「上段結尾 +
> 下段開頭」判斷是否插空格，換版本會讓 `ebook/*.html` 的**文字**（不只是空白）
> 產生大量與內容無關的差異，連帶 `search_index` 的 MD5 也變——等於版控中的產物
> 無法由新環境重現。實測（2026-09，PyMuPDF 1.28.2）重建 `ebook/` 就有 72 段差異。
> 升版**必須與重建產物同一個提交**，且事先 review 文字 diff 以區分「預期內容差異」
> 與「抽取層雜訊」。細節見 `requirements.txt` 檔頭與兩份工具 README。
>
> 🔒 **2026-10 起由 `utils/env_guard.py` 自動把關**（word2ebook／books2ebook 共用
> SoT）：兩工具的 `gen_all.py`／`gen_all_and_push.py` 與 word2ebook `main.py`
> 偵測到非鎖版直譯器會自動 `os.execv` 切換到該 venv，且建置前驗
> `pymupdf.__version__` 與 pin 一致、不符即 exit 1（pytest 環境與
> `W2E_SKIP_ENV_GUARD=1` 不切換、不檢查）。背景事故：2026-10-16 的 17a21bc 以
> `/usr/bin/python3`（1.26.5）重建 `ebook/`，36 段空白漂移、10 段已校對跟播
> 靜默遺失——完整調查見 repo 根目錄 `search_index_rebuild_research.md`。

---

## 概略原則

1. **Generated 目錄勿手改**：`wenda2_ebook/`、`ebook/` 皆為建構產物；改產生器或來源後重跑對應 `gen_all.py`。
2. **音訊播放鈕只在注入器產生**：`tool/word2ebook/core/audio_map_injector.py`（PDF 條目）與 `inject_word_chapters()`（Word 01–12）。別手改章節 HTML。
3. **離線媒體工具（sense_voice / audio_denoiser）為輔助流程**，不參與 Pages 佈署；只有在新音檔需要 ASR 時才用。
4. 每個工具的尖細規則放它自己的 README/AGENTS.md；跨工具／站台級慣例放根 `AGENTS.md`。
