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

## 章節對齊分段（chapter-aligned segmentation）— 已移除

> 舊版 `build_maps.py` 曾用主題式章節地圖
> `tool/word2ebook/data/audio_map_word/word-*.json` 當索引，把時間序彙總裡
> 被併的編號子題（`1、2、3、…`）拆開。該索引與其 `word_audio_map` 對齊器
> 已徹底移除，`_split_chunk_by_chapters()` 也已刪除：現在 `align_part` 每個
> chunk 直接成一整段、**不再拆子題**。現有 `audio_map2/*.json` 已是最終分段，
> 勿再重跑 `build_maps.py --all`（會失去原本的拆分粒度）。
