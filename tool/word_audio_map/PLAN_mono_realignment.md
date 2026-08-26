# 計劃：以時間序 docx 重對齊 Word 章節音頻映射（mono realignment）

> 執行者：AI agent。開工前先讀 `AGENTS.md`（repo 根）、`audio_map/AGENTS.md`（對齊原則）、
> `tool/word_audio_map/README.md`。本文件是唯一任務書；與上述文件衝突時，
> 對齊語意以 `audio_map/AGENTS.md` 為準，範圍以本文件為準。
> 狀態：待執行。完成後請在本檔頭加一行「狀態：已完成於 <date>，驗收數據見 build/mono_acceptance.md」。

---

## 0. 背景與現況（已核實，勿重查）

### 0.1 問題
`audio_map/index.html` 校稿的 Word 章節映射
`tool/word2ebook/data/audio_map_word/word-*.json`（第 01–12 章，鍵=`question_id`）
是由舊演算法 `word_align.py` **逐題獨立**在全部 session 拼音流中模糊搜尋出來的，
無順序約束，信心普遍偏低。實測分佈（5,796 段）：

| 等級 | 段數 | 佔比 |
|---|---|---|
| auto 且 conf ≥0.8 | 1,737 | 30% |
| auto 0.5–0.8 | 2,249 | 39% |
| auto <0.5（UI 紅 ⚠） | 1,621 | 28% |
| review | 173 | 3% |
| missing | 16 | <1% |

git 內 12 個 json 的 `locked`/`manual`/`meta.confirmed` 目前**全為 0 筆**
→ 現在整批重算不會覆蓋任何人工校訂成果（程式仍須保留防護邏輯，見 §5）。

### 0.2 新證據來源（本計劃的立論）
`問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx`：
- **128 個日期章節**（`Tai师父2024年2月11日答疑` … `Tai师父2025年7月12日答疑`），章節順序＝音頻順序；
- 章節內問答塊按口述順序排列（已抽樣 2024-03-01 與 SRT 比對：順序完全一致；
  docx 是同一音頻的校對文字版，相似度 bigram≈0.81，差異幾全為 ASR 同音字＋語氣詞清理）；
- 問答塊模式：`昵称：[YYYY-MM-DD HH:MM]` → 問題段 → `Taiguanglin：` → 回答 →
  27×U+2014 分隔線（變體多、前段章節常缺，**不可靠，只當弱訊號**）；全檔估計 ≈6,200 塊；
- 已知陷阱（解析器必處理）：幽靈重複標題（body#13589 的 2024-04-26 無書籤副本，須丟棄）、
  回答標記變體（`Taiguanglin：（2021年2月12日）`、`（29.47）`、偽標記`頂禮Tai師父：`）、
  多問題合併塊、nbsp/tab/w:br 髒格式、外鏈圖片（INCLUDEPICTURE）、
  非問答體裁章（2024-02-16 微信記錄完整版＝聊天記錄，整章排除）、
  整月缺席 2024-10 與 2025-04、雙來源日（公眾號＋貼吧內容串在同一章，
  唯一邊界是口播過場句「好了，贴吧的问题就回答到这里…」）。

### 0.3 音頻/SRT/opus 對應（已核實）
- SRT：`~/Documents/backup_on_2026-07-16_13inch_macbook/{2024,2025}答疑音頻/*.srt`
  （機器轉譯、未校稿；2024 年 98 檔＋2025 年 1–7 月約 72 檔，皆在）。
  注意：**2025 年的檔在 `2025答疑音頻/`**，不只使用者提到的 2024 目錄。
- `inventory_sessions()`（wcommon.py）掃兩目錄 → `session_id = YYYY-MM-DD-{main|wechat|tieba}`；
  同日同源多檔按 sorted 檔名序加 `-2/-3`（例：2024-12-09 公眾號（上）=`2024-12-09-wechat`、
  （下）=`-wechat-2`）。opus 扁平放在 `~/tai/audio/`，檔名＝SRT stem＋`.opus`。

---

## 1. 目標 / 非目標

**目標**：用時間序 docx 把 word-*.json 的每段 start/end 重算為「同 session 內單調序列對齊」的結果，
大幅提升正確率與信心分佈，並保持 schema／注入管線／校稿 UI 完全相容。

**非目標（明確不做）**：
- 不改電子書章節結構、不把時間序 docx 變成電子書來源（主題版
  `wenda2_250810_截止25年5月17日答疑_含图版.docx` 仍是唯一題目來源）；
- 不動 PDF 章 13–21 的 `data/audio_map/*.json`（已全數校對完成）；
- 不改 `question_id`（內容雜湊，是注入端主鑰）；
- 不做需要聽音檔的人工判斷（AI 只做文字/SRT 層驗證，聽檔留給人類校稿流程）。

**成功指標（驗收閘，Phase 8）**：
1. 每 session 內 starts 嚴格遞增、end_i=start_{i+1} 鏈成立，違例=0；
2. auto<0.5 人口從 1,621 降到 <300（其餘升級或誠實降為 review/none）；
3. auto 且 conf≥0.8 升至 ≥70%；
4. locked/manual/confirmed 段零改動（本期應為 0 筆，防護邏輯照寫）;
5. 抽樣 40 段人工聽檔，≥95% 邊界可用（±1 cue 內）——由人類執行，AI 準備抽樣清單；
6. `gen_all.py` 後 `verify_build.py` 通過、PDF 章 baseline 零回歸。

---

## 2. 總體策略

舊法：一題在「提交日後 14 場/45 天」窗內逐場全流搜尋 → 早錯一格處處漂移。
新法：docx 已給出「該日期章節的題目清單與口述順序」，問題變成
**同 session 內的單調序列對齊**（needle 清單 vs 一條拼音流），交叉誤配在結構上不可能：

```
chrono docx 日期章節 ──(日期+來源)──▶ session(s)：SRT+opus
      │                                     │
      ▼                                     ▼
 blocks[]（有序）───match_ordered＋單調約束───▶ 每塊 char_pos → start/end
      │                                     │
      └── qid_bridge（question_id ↔ block）─┴──▶ 寫回 word-*.json（schema 不變）
                                               └▶ calibrate.py 收斂精修
```

四個新構件（全部放 `tool/word_audio_map/`，共用 `.venv` 與既有模組）：
`parse_chrono_docx.py` → `build/chrono_sessions.json`
`map_sessions.py`      → `build/session_assignment.json`
`mono_align.py`        → `build/session_alignment.json` ＋ `build/mono_review_report.md`
`qid_bridge.py` ＋ `apply_mono_maps.py` → 更新 `data/audio_map_word/word-*.json`

---

## 3. 可復用資產（不要重新發明）

| 能力 | 位置 | 用法 |
|---|---|---|
| 有序貪婪模糊匹配＋drift 重錨 | `tool/pdf_audio_map/common.py::match_ordered` | 序列對齊原型，直接用或包一層 |
| OpenCC→strip→pypinyin 正規化、拼音流、char↔cue↔秒、子cue內插 | `tool/word_audio_map/wcommon.py::py_norm / SessionStream / frac_time / inventory_sessions` | 全程跑在無聲調拼音流上 |
| 姓名/答案/問題三種 needle、LCB、便宜預濾 | `tool/word_audio_map/word_align.py::annotate_questions / lcb / usable_name / _cheap_prefilter` | 匹配打分原語 |
| 「下一個問題」字內插、自適應 lead-in、不切前句 | `tool/pdf_audio_map/realign_half_second.py::find_xia_time_in_cue / adaptive_lead / prev_cue_end_before` | 邊界 onset |
| 有界精修（--limit 30s、冪等收斂、跳過 locked/manual） | `tool/word_audio_map/calibrate.py` | mono 給粗 onset 後交給它收斂，重複跑到 dry-run≈0 |
| 安全合併（locked/manual/meta 保留）、busy 區禁入 | `word_align.py::_merge_locked / _load_busy / apply_near_patches` | 寫回時套用 |
| 題目萃取（走真 DocumentParser，id 與 build 時一致） | `extract_questions.py::extract_questions()` | 產生橋接用的 questions.json |
| 驗證 | `verify_build.py`；PDF baseline `build/pdf_button_baseline.json` | 最終閘 |

---

## 4. 階段計劃

> 每階段結束：commit（獨立 commit，訊息前綴 `[mono-realigh P<n>]`）、跑該階段驗收閘、
> 未過閘不得進下一階段。所有 build/* 產物寫進 `tool/word_audio_map/build/`（已 gitignore？若否，加入）。

### Phase 0 — 基線與安全網（半天）
1. `git checkout -b mono-realign`。
2. 寫 `build/baseline_stats.json`：現況各章 matched/review/missing、conf 分桶、
   各段 (start,end,status,confidence) 快照（供事後 diff 報告）。
3. 確認防護前提：統計 `locked`/`manual`/`meta.confirmed` 數量並記錄（預期 0；非 0 時列出清單且寫回階段必須跳過）。
4. 環境檢查：`.venv`（`python3 -m venv .venv && .venv/bin/pip install pypinyin opencc-python-reimplemented`）；
   repo 根 `audio` symlink 若不存在且需要本地播放測試，重建 `ln -s ~/tai/audio audio`（gitignored，勿 commit blob）。
5. 驗收閘：baseline_stats.json 存在且總段數=5,796。

### Phase 1 — 解析時間序 docx（1 天）
新檔 `parse_chrono_docx.py`：
- 正文標題判定：段落含 `_Toc20832xxxx` 書籤起點 且 文字符合
  `^Tai师父20\d{2}年\d{1,2}月\d{1,2}日答疑`（126/128 是純文字+rStyle「标题 2 字符」，
  2024-02-15/16 兩章是 pStyle a4——勿依賴 pStyle）。TOC 頁碼是寫死的快取，**只有 anchor↔書籤可信**。
  **切章規則：書籤段為主切點；另掃「標題樣式（rStyle=20+粗體+sz≥28）卻無書籤」的段落
  作為追加切章邊界**——現僅 body#13589 的 2024-04-26 一處：只認書籤會把 4/26 開頭錯併進 4/25 章，
  只認文字會切出 129 章；追加邊界產生的偽章須用其日期對回 SRT 清單驗證後才收編。
- 塊切分主錨=`Taiguanglin：`家族變體（含帶括注日期/數字的），向前吸附最近的`昵称：[ts]?`行
  與其後問題段；分隔線僅作 sanity 弱訊號；清洗 nbsp/tab/w:br、剔除圖片 run。
- 每塊記：`{seq, asker_raw, asker_clean(usable_name), ask_time, q_text, a_text}`。
- 特例：`Taiguanglin：（2021年2月12日）`這類**歷史補充**不算新塊（併入前一塊 a_text 尾注）；
  2024-02-16 章標 `genre:"chat-log"`，不產生 blocks。
- 輸出 `build/chrono_sessions.json`：
  `[{session_date, toc_anchor, title, genre, blocks:[…]}]`（128 章，按日期排序）。
- 驗收閘：章數=128；塊數落 6,200±5%；抽 3 章（2024-03-01、2024-12-10、2025-06-13）
  人工核對首末塊文字與 docx 原文一致；異常清單寫 `build/chrono_parse_anomalies.md`。

### Phase 2 — 章節→session(s) 映射（0.5 天）
新檔 `map_sessions.py`：
- `session_date` 精確對到 `inventory_sessions()` 條目；缺席月（2024-10、2025-04）與
  無 SRT 日記 `missing_audio:true`（後續該章塊全數 `status:"review"`＋reason=no-audio，**不猜日期**）。
- 雙來源日（公眾號+貼吧同日）：先用口播過場句
  「贴吧的问题就回答到这里」「公众号」等在兩條 SRT 流中定位切點
  （注意「师父说：」也會出現在提問正文中，過場候選須以「出現在兩塊之間＋被分隔線夾住」限定；
  全檔約 50 章有中途過場、56 章有開場引言、ch86 有上下半場）；再對每塊以
  match_ordered 分別在兩流試配，取「兩側皆單調且總分最高」的分配。12-09（上/下）視為
  接續流（跨 `-wechat`→`-wechat-2`，時間各自落在所屬檔）。
- 輸出 `build/session_assignment.json`：
  `{session_date → [{session_id, srt_file, audio_file, block_seq_range:[lo,hi]}]}`＋未決報告。
- 驗收閘：128 章中 ≥124 章有 assignment 或明確 missing_audio 標記；未決清單=空。

### Phase 3 — 單調對齊核心（2 天，本計劃心臟）
新檔 `mono_align.py`：
1. 對每個 session 載入 `SessionStream`；blocks 造 needle：
   asker 拼音（含 spoken 變體）＋ a_text 首/尾 60 字拼音針。
2. 以 `match_ordered` 在**單一 session 流**上求有序錨點；強制 `char_pos` 嚴格遞增；
   每塊再用 `lcb` 於命中窗口驗證（沿用 T_ACCEPT=16 思路，問題針 ×0.9）。
   新信心模型：`conf = clamp(score/60)` 保持與舊值可比。
3. onset：優先口述姓名位置，次選 a_text 塊起點；「下一个问题」過場按
   `audio_map/AGENTS.md` §Alignment 1–3 處理（此階段只求 ±2 cue 粗界即可）。
   `end_i=start_{i+1}`；末塊 end=音檔長（或偵測收場「就到这里」則止於其起點）。
4. 失敗階梯（逐級放寬，仍單調）：a_text-only LCB → 鄰居間隙內局部搜尋 →
   放棄：`status:"review"`（reason 記檔）。多問題合併塊：以「下一个问题」探測器切音頻側，
   兩個 docx 問題共享/細分範圍，第二題問題全文掛 `q_text`（遵循 AGENTS 的 split 語意）。
5. 輸出 `build/session_alignment.json`（session 為單位、block.seq 有序、含 method/score/notes）
   ＋ `build/mono_review_report.md`（低分/未中/缺音頻清單）。
6. 接著跑 `calibrate.py --apply`（預設 limit 30s），反覆至 dry-run≈0。
- 驗收閘：單調違例=0；每 session 至少 60% 塊取得 auto 級錨點；calibrate 收斂（dry-run 移動總和 <5s）。

### Phase 4 — question_id 橋接（0.5–1 天）
新檔 `qid_bridge.py`：
- 跑 `extract_questions.py` 取得**主題版** questions.json（id 與 build 完全一致）。
- 每題 → chrono block 配對：候選限 `question_date ≤ session_date`（容忍 +1 天），
  打分＝asker 清洗後相等(強)＋q_text/a_text 拼音 LCB／bigram 相似度；
  一對一貪婪（高分先佔、互斥），低分懸案進 `build/bridge_conflicts.md`。
- 主題版有而時間序無的題（如純文字開示）：列 `no_counterpart`，寫回階段**不動**它們的舊值。
- 輸出 `build/qid_bridge.json`：`question_id → {session_id, session_date, block_seq, score}`。
- 驗收閘：主題版 5,796+ 題中 ≥92% 有唯一橋接；衝突清單每筆有人工可讀原因。

### Phase 5 — 寫回 word-*.json（0.5 天）
新檔 `apply_mono_maps.py`：
- 只更新橋接成功的段：`start/end/start_label/end_label/confidence/status/notes/
  session_id/audio_file/srt_file/srt_preview`；`notes` 追加 `method=mono(seq=…,score=…)`。
- **不變更**：`question_id`、`stable_key`、`index`、章節歸屬、`q_text/a_text`（電子書文字
  以主題版為準，絕不被 chrono docx 覆蓋）。
- 跳過並原樣保留：`locked`、`status∈{manual,none}`、`meta.confirmed` 段（本期 0 筆，防禦性）。
- `version+=1`、重算 stats；另存 `build/diff_report.md`：新舊 conf 分桶對照、
  |Δstart|>120s 的段清單（人工抽查優先名單）。
- 驗收閘：json schema 與舊欄位集合完全一致（diff 只允許值變化）；stats 加總=段數。

### Phase 6 — 機器驗證（0.5 天）
1. 自檢腳本（可併入 apply 的 `--check`）：單調鏈、end_i=start_{i+1}、時間在音檔時長內、
   跨 session 無重疊、audio_file 存在於 `~/tai/audio/`。
2. `cd tool/word2ebook && python3 gen_all.py`，再 `tool/word_audio_map/verify_build.py`。
   注意：未確認（無 meta.confirmed/lastPlayed）的段本來就不出鈕——這是設計；
   本階段只驗「不出錯鈕」，出鈕量在 Phase 7 之後才會成長。
3. 產出 `build/mono_acceptance.md`：§1 成功指標 1–4、6 的實測值。

### Phase 7 — 校稿交接（人類 + UI）
1. 產生抽樣清單：分層抽 40 段（每章 ≥2、含 10 段 Δstart 最大者、10 段最低 conf 者），
   每段給 session_id+時間碼+SRT 預覽，寫 `build/spot_check_list.md`，交人類聽檔。
2. 高分批次確認建議：conf≥0.85 且 SRT 預覽與 a_text bigram≥0.75 的段，可在
   `/audio_map/` 用既有一鍵批次確認（auto 且 conf≥門檻）——是否執行由人類決定，
   AI 不得自行批量寫 `meta.confirmed`。
3. （選做，另開小任務）editor.word.js 增加「按 session 分組」檢視，利用順序校稿。

### Phase 8 — 合併與收尾
1. 人類抽樣通過（指標 5）後：`git checkout main`、merge、push
   （UI 從 raw.githubusercontent main 讀取，push 即生效）。
2. 更新 `tool/word_audio_map/README.md`：新增 mono_align 段落（用法＋新 build 產物）；
   順手修正 README 過時常數（T_NONAME 26→20）。
3. 本計劃檔頭加完成狀態行。

---

## 5. 不變式（任何階段違反即停手回報）

1. `data/audio_map_word/word-*.json` 的 schema 欄位集合不變；`question_id` 永不改。
2. `locked`/`manual`/`meta.confirmed`/`status:"none"` 段永不自動改寫。
3. 電子書文字欄位（q_text/a_text）只來自主題版 docx。
4. 不編輯 `wenda2_ebook/`（一切經 gen_all 注入）；不動 PDF 月地圖。
5. 所有破壞性寫入必先有 dry-run 輸出且 diff 可審。
6. 音檔/SRT 只讀；opus 不入 git。

## 6. 風險與緩解（摘要）

| 風險 | 緩解 |
|---|---|
| docx 幽靈標題/髒格式導致章切錯 | 書籤 1:1 校驗＋TOC 順序核對（Phase 1 閘） |
| 分隔線缺失/多餘 | 只以回答標記為主錨，分隔線降為弱訊號 |
| 雙來源日分配錯置 | 過場句定位＋雙流試配取總分最高；未決不上報 auto |
| ASR 同音噪聲 | 一律拼音流＋LCB，門檻沿舊值起步，用 baseline 子集校準後再全量 |
| docx 文字與口述差異大（刪修飾） | 塊尾針＋順序約束兜底；失敗階梯最終落 review，不硬湊 |
| 缺音頻月（2024-10、2025-04） | 明確 missing_audio，不跨月猜測 |
| 換 docx 造成 id 漂移 | 本計劃不換題目來源；chrono docx 僅作對齊證據 |

## 7. 決策點（已採預設，人類可覆寫）

| 決策 | 預設 | 替代 |
|---|---|---|
| 是否直接改寫 word-*.json | 是（橋接成功者） | 另立 session-centric 新 SoT（工程大，暫緩） |
| 低信賴段處置 | review（無鈕，待人類） | 直接 none |
| 高分批次確認 | 建議清單，由人類按鈕 | AI 批量寫 confirmed（禁止） |

---

## 附錄 A：現況快照指令（Phase 0 用）

```bash
cd tool/word_audio_map && .venv/bin/python extract_questions.py
python3 - <<'EOF'
import json,glob,collections
b=collections.Counter()
for f in glob.glob('../word2ebook/data/audio_map_word/word-*.json'):
    d=json.load(open(f))
    for s in d['segments']:
        c=s.get('confidence'); st=s.get('status')
        k=st if st!='auto' else ('>=0.8' if (c or 0)>=.8 else '0.5-0.8' if (c or 0)>=.5 else '<0.5')
        b[k]+=1
print(dict(b))
EOF
```

附錄 B：輔助研究產物（一次性，位於 /tmp，可能已被清理；結論已併入本文）
`/tmp/docx_structure_report.md`、`/tmp/toolchain_report.md`、`/tmp/chapters.json`、`/tmp/parse_docx.py`。
