# word_audio_map2 — 時間序 Word → 音檔 mapping 產生器

依據**時間順序版** Word 彙總
`問答錄2/2024-2025 TAI师父答疑汇总 - 截止2025年7月12日.docx`
與 AI 轉出的 `.srt`，產出 `audio_map2/YYYY-MM.json`（2024-02 … 2025-05）
供 `/audio_map2/index.html` 審核播放段落。

## 原則

- **文字以 Word 為準**：`q_text` / `answer_text` / `questioner` / `question_time` /
  opening / closing 文字全部取自 docx。
- **SRT 只用於時間**：`start` / `end` / `srt_preview`（僅供對照，不是校對稿）。
- 不參考過往併入電子書的音檔時間；所有時間皆由 SRT 重新推導。

## 指令

```bash
cd tool/word_audio_map2

# 全範圍產出並寫檔
.venv/bin/python build_maps.py --all --apply

# 單一月份 dry-run（只印報表）
.venv/bin/python build_maps.py --month 2024-12
```

首次安裝：`python3 -m venv .venv && .venv/bin/pip install opencc-python-reimplemented`
（OpenCC 做 繁↔簡 normalize，比對 SRT 用）。

## Word 解析規則

| 元素 | 判斷 |
|------|------|
| session 標題 | `Tai师父YYYY年M月D日答疑（文字版）`；`2024年2月16日…微信记录完整版` 無音檔，跳過 |
| 區塊起點 | 分隔線（`———`）、`师父说：` 標記、或嚴格的「短暱稱＋冒號」行 |
| 提問人列 | `Name：[時間戳]`；名稱 ≤15 字、非黑名單（Taiguanglin/师父说…）；含師父＋有內容 → 引語不拆塊 |
| 回答起點 | `Taiguanglin：` 行；**黏在問題段落尾端**（「…嗎？Taiguanglin：」）也會正確切開（全檔 126 處）；同答後再現 = 同人追問，各自成段 |
| 來源分段 | `师父说：…先回答贴吧的问题。` / `…回答微信公众号的问题。` 等 4 類標記 |

只有當天**實際存在多個音檔**（貼吧＋微信公眾號）才依標記拆 sub-session；
單音檔日（2024-02 … 2024-11）維持單一 session，`师父说` 變開場／收場文字。

特例：

- `2024-12-09` 公眾號音檔分（上）（下）→ 合併時間軸（下段時間 += 上段 SRT 末尾估計長度），
  JSON `media_kind:"split"`、`media_parts[]` 帶每檔資訊。
- Word 漏掉來源轉換標記但當天有雙音檔（如 `2025-03-12`）→ 自動以
  貼吧→微信 合併時間軸對齊，`resolved_source:"貼吧＋微信公眾號（文字檔未分段）"`。

## 對齊策略（沿用 tool/pdf_audio_map）

1. 提問人口語名變體命中（最強 anchor，如 掌南飛→张南飞、无为心内起悲心→微信内起背心）
2. 問題內文 needle（去頂禮等客套話）＋ **罕見 4/3-gram shingle 掃描**（對抗重 ASR 錯字）
3. 回答開頭 needle
4. 全域重新錨定 → 單調內插補洞

### 時長感知修復（duration-aware repair）

初步對齊後，比對每段「文字量 ÷ 語速」與實際分配到的音檔秒數：
明顯不足（<45% 預期時長）或信心 <0.5 的段落進入修復：

- **候選**：全 session 範圍內的名字命中／needle／shingle，加上
  bigram 模糊定位（容忍「往生極樂世界→出院往盛肌肉」級別的錯字）
- **共識**：多探針指向同一 ±45s 區域即可採信；精確候選需覆蓋率
  領先 60s 外亞軍 ≥0.08（或絕對值 ≥0.62）
- **順序寬容**：朗讀順序可能與 Word 排序不同（2025-05-17 即發生），
  修復後依時間重排播放順序
- **找不到逐字對應時**：先做 **fuzzy-mid 最後救援**——用答案的頭段＋
  中段各做一次 bigram 模糊定位（窗口按探針長度而非預期時長計算，
  避免長答案稀釋相似度），單一強命中 r≥0.52 或雙叢集共識
  （r≥0.33×2、相距 <90s）即採用，conf 封頂 ~0.63；仍無證據才依前後段
  比例夾入，標 `no-anchor:clamped`＋「待人工確認」（黃色，UI 有
  「待人工」過濾鍵）——常見於主題式講解月份，或問題以圖片提交／
  隔日才回答者

### 終局一致性（layout passes）

修復後依時間重排播放順序，再做三道收尾：

1. **squeeze-fix**：錨點堆疊（多個高信心段落在同一秒）時，避開其他段的
   佔用視窗重找位置；仍失敗則夾入並標「錨點擠壓，待人工確認」。
2. **layout-spread**：相鄰起點過近的叢集（gap < max(3s, 15%預期)）按
   文字量比例在可用區間內嚴格分配（不越過下一段）；空間不足時向後
   吸收軟錨點成員擴大區間。全部標待人工。
3. **donate**：單段被夾到 <10% 預期時長，而相鄰段擁有 >125% 餘裕時，
   向其借尾部時間（多輪迭代，上限 240s/輪）。
4. **name-refine**：常用詞暱稱（慢慢／松／醒…）會誤中较早的普通用詞；
   同名多次出現時，以「後續窗口內容覆蓋度」擇優重選名讀位置。
5. **boundary-probe**：軟錨段的口頭回答溢出到下一段窗口時，用下一段
   自己的問題開頭／點名證據重切邊界（`+bcut`）。
6. **evidence-chain**：連續軟錨段的真答案成串落在更後面時，以移動
   游標逐一錨到各自的問題關鍵詞／點名首中（`+echain`），再交給
   layout 重分配時長。
7. **誠實標記掃描**：時長 <45% 預期、或窗口開頭疑似前段內容者，
   一律標「待人工確認」並封頂 conf——機器無法重切的（ASR 把名字都
   念歪的）至少要讓校對者看見。

**收場假命中防護**：`closing_start` 若早於任何段落起點即視為誤報，
退回音檔結尾——否則會把後段真音檔全截掉（2025-03-14 即此案例）。

段 end = 下一段 start；末段 end = 收場 start 或音檔結尾。
confidence < 0.5 → 低信心（審核 UI 紅卡提示）；stats 的 `pending`
即待人工確認段數。

## 各月品質概況

- **2024-09 … 2025-05**：結構化標記完整，低信心 0、無亂序、無 <25% 預期
  時長的切片；待人工 5~13 段/月（多為問題以圖片提交、隔日回答或
  合併時間軸日）。2025-01 的多問題大區塊（3365 字→604s）已由
  layout/donate 正確展開。
- **2024-02 … 2024-08**：音檔為**主題式講解**（未逐題念問題）且 ASR 品質差，
  約兩成段落仍需人工聽檔（pending 21~241/月）；其餘多由 fuzzy-mid
  以答案內容定位（notes 帶 `fuzzy-mid`，conf≤0.63 可辨識）。
- 全域保證：段落起點單調遞增；「幾秒」級荒謬切片僅剩主題式月份中
  音檔確實無該內容者（皆已標記待人工）。

> 工程註記：layout/donate 的期望時長曾誤用 Word 序文字配時間序位置
> （`e_all` 未經 `perm` 映射），導致大區塊被鄰居擠壓——已修正為
> `expected_dur(perm[i])`。boundary-probe 同類索引錯誤已一併修正。
> 另：上下檔合併日的音檔預覽曾因 raw cues 未加偏移而全空白
> （下半檔段落無法目視校對）——已同偏移修正。

## 輸出 JSON schema

同 `tool/word2ebook/data/audio_map/*.json`（month/version/stats/sessions，
session 內 opening/segments/closing），另加：

- `docx_heading`：來源 Word 標題
- `media_kind`: `single` | `split` | `none`
- `media_parts[]`: `{stem, audio_file, srt_file, mp3_path, opus_path, duration_est}`

segment 欄位：`index / question_id / stable_key / questioner / question_time /
q_text / q_preview / answer_text / answer_preview / start / end / start_label /
end_label / confidence / status / notes / srt_preview`。

## 審核 UI

`/audio_map2/index.html`：選月份 → session → 卡片式段落審核；
▶ 播放此段（串流 `../audio/*.opus`，支援 split 合併時間軸）、低信心紅框、
插補/缺時間過濾、SRT 對照摺疊區。鍵盤：`P` 播放/暫停、`↑↓` 上/下一段。
本機瀏覽需走 http server（fetch 相對路徑），例如：

```bash
python3 -m http.server -d /Users/paul/tai/taiguanglin.github.io 8000
# → http://localhost:8000/audio_map2/
```

## 重分段 → 重對應章節（resplit + relink）

> **先講結論**：過去曾假定「`audio_map2/*.json` 的分段已是最終版、不再調整，
> `chapter_question_ids` 凍結一次即可」。這個假定**已不成立** ——
> `build_maps.py` 的 Q&A／後續題偵測（`_is_followup_question`）會持續修正；
> 每次改了分段邏輯，就必須重分段，並以 `link_chapters.py` **為主**重寫回
> 每段的 `chapter_question_ids` / `chapter_indexes`。

### 背景

舊版 parser 只看「問題」不看「回答」，跨多個 `Taiguanglin：` 標記的同一作者
貼文（例：`2025-05-17 極樂是我家`）的四組子問答會被黏成一團。`build_maps.py`
現在會把後續子題拆成獨立段。拆分邏輯屬長期演進，因此需要一套「重分段不遺失
已校對資料」的流程。

### 兩個層面

| 層面 | 工具 | 做什麼 |
|------|------|--------|
| 保留已校對時間/對應 | `apply_resplit.py` | 用**新的** `_block_to_chunk` 重跑 parser 產出文字分段，再**按內容比對**（q_text 精確 → answer_text 包含 → 模糊）把舊段的 `start/end`、`meta.lastPlayed`、`status/confidence/notes`、`chapter_question_ids` 搬過去 |
| 重新建立章節對應 | `link_chapters.py` | 內容比對 `build/questions.json`，把每段的 `chapter_question_ids` / `chapter_indexes` 寫回（來源見檔首 docstring） |

**推薦順序**（以 `link_chapters.py` 為章節對應之主；`apply_resplit.py` 只負責
「拆文字 + 搬已校對欄位」，而新拆出的子題章節對應統一交給 `link_chapters.py`）：

```bash
cd tool/word_audio_map2

# 1) dry-run 先看每月段數變化與 match 統計
.venv/bin/python apply_resplit.py

# 2) 重分段 + 搬移已校對欄位（只寫有變動的月份）
.venv/bin/python apply_resplit.py --apply

# 3) 以 link_chapters.py 為主，補齊章節對應
.venv/bin/python link_chapters.py                    # dry-run（報表 → build/link_report.json）
.venv/bin/python link_chapters.py --apply            # 填「缺章節」的段（預設 fill-empty-only）
# 若真要整份重導章節對應（會用內容比對取代凍結對應，慎用）：
# .venv/bin/python link_chapters.py --apply --overwrite

# 4) 驗證（段數/章節覆蓋/時間單調/index 連續/凍結 qid 零遺失/無跨月誤填）
.venv/bin/python validate_resplit.py
.venv/bin/python validate_relink.py
```

> **`link_chapters.py` 寫回語意**（重要）：
> - 預設 `--apply` 是 **fill-empty-only**——只對「完全沒有 `chapter_question_ids`」
>   的段做內容比對補章節；已有人工校對連結的段**絕不更動**，且只補「尚未被任何
>   段認領」的 qid（避免同一問題在兩天各問一次時，把同一 qid 誤掛到兩段、造成
>   跨 session 重複）。
> - `--apply --overwrite` 才做**整份重導**：以內容比對結果取代每段既有 qid，
>   未重新比到的既有 qid 會被丟掉。除非你確定要相信內容比對、放棄凍結對應，
>   否則不要用。
> - `link_chapters.py` 只加 join key（`chapter_question_ids`/`chapter_indexes`），
>   不改任何文字/時間/狀態。

> 只改某個月：`apply_resplit.py --month 2025-05`（可重複）；
> `link_chapters.py` 對全部月份比對（它不改文字/時間/狀態，預設只補缺章節的段）。
> 驗證時把 `validate_relink.py` 一併跑：它會對 git `HEAD` 逐月比對，強制
> 「凍結 qid 零遺失」與「無新增跨 session 重複 qid」（即誤填訊號）。

### 輔助腳本（`apply_resplit.py` 與 `link_chapters.py` 之間的墊補）

如果你**不想整份重跑 `link_chapters.py`**，而只想保留原有凍結章節對應、只把
「新拆出的子題」補上章節，可用以下三支（依序、各帶 `--apply` 才寫檔，皆
dry-run 預設）：

1. `fill_orphan_chapters.py` —— 為 `notes` 帶 `resplit` 且缺章節的新子題，
   依 q_text（再 fallback answer_text）比對 `build/questions.json` 補上
   `chapter_question_ids`。
2. `redistribute_chapters.py` —— 舊段若把多個子題凍結在同一段
   （`chapter_question_ids=[A,B,…]`），重分段後同一份清單會被複製到每個子段；
   此腳本把清單**按內容重新分配**回各子段（保證任一 frozen qid 都不丟）。
3. `reconcile_qids.py` —— 最終對帳：比對 git `HEAD` 與重分段後結果，任何
   在原始凍結映射裡出現、但重分段後消失的 qid，掛回最匹配的段。

三者加上 `validate_resplit.py` 就是我前次「只重拆文字、保留已校對時間與對應」
所採用的流程；若未來改成分段邏輯為主，直接以 `link_chapters.py --apply` 取代
第 2、3 步即可。

另有兩支**針對剩餘缺口／分段錯誤**的腳本（皆帶 `--apply` 才寫檔、dry-run 預設、
列印每筆待人工複核）：

4. `fill_resolvable.py` —— 為「有實質問答、但分類檔找不到對應」的段，以
   **q_text**（包含關係優先、再 fuzzy ratio ≥ 0.6，並有最短字數護欄，避免
   「感恩师父！」這類問候被誤掛多題）補上最相近的分類題。其**故意不用
   answer_text**——那正是先前把 57 個 qid 誤掛到一個問候段的來源。適合人工
   審核後再 `--apply`。
5. `merge_split_artifacts.py` —— 一次性修正「單一問答塊被拆成『問題 stub＋
   答案殘片』」的 split-artifact（典型：`2025-05-17` 業力/能力、`2024-11-15`
   求財等 4 案），合併後依 `build_maps.py` 的公式重排 index 並重生
   `stable_key`/`question_id`（`sha1(sid#index#q[:80])`）。

### 注意

- **絕對不要**整份重建 `audio_map2/*.json` 而丟掉人工校對的 `start/end` 與
  `meta.lastPlayed`；重分段一律走內容比對遷移（`apply_resplit.py`）。
- 有「最後播放」(`meta.lastPlayed`) 紀錄的段**任何腳本都不應改動**——那是
  音檔時間人工校對的完成判定；前述 merge/fill 都只處理 `lastPlayed` 為空的段。
- `build/questions.json` 為 `link_chapters.py` 的內容比對來源；它是從
  `wenda2_ebook/01.html…12.html` 重建的（5746 題）。目前有極少數（39 筆）
  frozen qid 不在其中，`reconcile_qids.py` 即以凍結段的 `chapter_indexes`
  兜底，不因缺題目而遺失對應。
- 重分段後務必跑 `validate_resplit.py` + `validate_relink.py`；前者回報 index
  非連續（`2025-03-12` 合併時間軸為已知既有）等告警，後者強制「凍結 qid 零
  遺失」與「`meta.lastPlayed` 不變」，並把跨 session qid 區分為**逐字重複／
  合併題子段（合理）**與**q 與答案皆不同（誤填）**兩類。
