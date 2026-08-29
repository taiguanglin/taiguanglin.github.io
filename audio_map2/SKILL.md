---
name: audio-map2-align
description: >-
  Audit and repair a chronological Word↔audio mapping JSON (audio_map2/<month>.json)
  so every 答疑段落 (Q&A segment) has start/end that match where its content is
  actually spoken in the SRT, raising confidence to >=0.8 where evidence supports,
  fixing reading-order reorders, and honestly flagging the untraceable few.
  Use when asked to 校對/對齊/審核 a 月份 JSON in audio_map2/ (e.g. "處理 2025-06.json").
---

# audio_map2 月份 JSON 校對（Word ↔ SRT 時間對齊）

把某個 `audio_map2/<month>.json` 的音檔播放時間逐一對齊到 SRT 實際念到的位置。
這不是從零產生 mapping —— 是**修復既有 mapping 的時間與信心度**。

## 鐵律（先讀)

1. **文字以 Word 為準，SRT 只取時間。** `q_text / answer_text / questioner / opening / closing`
   全部來自 docx，決不新寫、決不參考 `audio_map_word/*.json` 的時間。
2. **只改 `start / end / confidence / notes / 陣列順序`。** index 是 Word 順序參照，永遠保留；
   其他文字欄位一字不動（改前先 diff 驗證）。
3. **`segments[]` 陣列順序 = 播放（audio）順序**；`index` = Word 順序參照。
   兩者不同時要**重排陣列**（`end[i] == start[i+1]`）。
4. **信心度只給誠實值。** ≥0.8 只在「內容確實出現在 SRT 該窗口」時給；
   空答案／內容併入鄰段／音檔根本沒讀的段 → `start/end = null`、`confidence = 0.0`、notes 寫明原因，**不要杜撰位置**、不要硬塞時間。
5. **不要跑 `build_maps.py --all --apply`** —— 會覆蓋人工成果。手動修完直接覆寫 `<month>.json`。

## 環境與前置

```bash
cd /Users/paul/tai/taiguanglin.github.io/tool/word_audio_map2
# venv 有 opencc；working dir 必須在此，helpers 才 import 得到 build_maps.py / common.py
.venv/bin/python ...
```

### 關鍵 API（`tool/pdf_audio_map/common.py`）

- `parse_srt(path, conv) -> [(start,end,text)]`
- `normalize(text, conv)` —— OpenCC 繁→簡 + 標點/空白正規化
- `get_converter()` —— OpenCC converter
- `question_needles(q_text, conv)` —— 提問者的多種別名（處理貼吧 ID 變體）
- `match_start(cues, cursor_idx, needle, min_len, min_block=6, max_scan=340)` ——
  分段 anchor 定位（僅對**有特徵的 answer-head** 可靠，見下方陷阱）。

SRT 路徑例：`~/Documents/backup_on_2026-07-16_13inch_macbook/2025答疑音頻/2025年5月12日Tai師父貼吧答疑.srt`
（`readspan.py` 的 `source` 參數用簡化字：`贴吧`、`微信公众号`。）

## 標準流程（由粗到細收斂）

### 第 1 步 — 全景盤點（status / 低信心 / 待人工)

```python
# 讀 <month>.json，逐 session 列出：segment 數、null 數、conf<0.8 數、notes 裡的待人工標記
# 抓出「哪些 session 需要重排順序」的線索：低信心比例、題目編號 1/2/3… 錯位
```

先讀 `AGENTS.md` 判斷這個月是「逐題念名」（質量高，抽查即可）還是「主題式講解」
（ASR 差、待人工高，每段都要聽）。

### 第 2 步 — 找 reading-order 重排（最容易漏的結構性錯誤）

**核心發現：某些場次師父念答案的順序 ≠ Word 順序。** 判斷方法：

1. 跑 transition 掃描（`xscan.py`，見 tools/）—— 找所有 `下一个问题` 標記時間。
2. 遇到「此題編號 `3、` 前面沒有對應 `1、2、`」或「同名提問人片段彼此間隔異常」時，
   逐段聽 `readspan` 確認實際念到的題目。
3. 典型模式：同一提問人的多題一起念、或先念後面的題再念前面的題。
   例如 05-12 貼吧曾出現 block 重排 `[31,34,33,32,35,36,37]` 與
   `[39,40,44,9,41,42,43]`（`9/44` 整段在兩個 block 之間遷移）。

**重排後必須**：`end[i]=start[i+1]` 連續、無 overlap、無倒序（見第 6 步校驗）。

### 第 3 步 — content-coverage 定位（可規模化的查錯器）

用 difflib 算「該段 answer_text 開頭 ~180 字」在其窗口 SRT 文本的覆蓋率：

```python
sm = difflib.SequenceMatcher(None, window_text, probe, autojunk=False)
cov = sum(m.size for m in sm.get_matching_blocks()) / max(1, len(probe))
```

- `cov >= 0.4` → 位置大致正確（可能只是 ASR 把問題人名念岔，如「師父→师傅」）。
- `cov < 0.4` → **> 高機率錯位**，進第 4 步收斂。完整腳本見 `tools/audit.py`。

**陷阱**：cov 只看「文字在不在窗口」，同名多題或共享片語會造成誤報。
只把它當**篩選器**，最終都要回 readspan 讀實際 SRT 文字確認。

### 第 4 步 — 低信心段收斂（前後逼近)

對每個 cov<0.4 的段：

1. `readspan.py <date> <source> <t0> <t1>` 印出該時間窗的真實 SRT 文字。
2. 找該段 answer-head 的**獨特字串**（人名、主題詞、問句結尾），
   不是找通配詞（`未来`、`人` 這類會誤報）。
3. 內容若在「隔壁窗口」→ 確認是否應前後平移邊界；若整段根本沒念 → null/0.0。
4. `match_start` 只對**有明確特徵的 answer-head** 有效；對通用起頭（如「下一个问题」）
   會給假陽性 —— **每次移動都要 readspan 實讀驗證**，別盲信 anchor。

### 第 5 步 — 信心度收口

- 內容經 readspan **實讀確認在正確窗口** → 0.85–0.95。
- 結構性重排＋邊界確定、但逐字 ASR 變形大 → 0.8。
- **空的／併入鄰段／音檔未讀** → `null / 0.0` + note（誠實，不硬湊）。

### 第 6 步 — 收尾：notes 合併、stats 重算、結構校驗

```python
# (a) 把誤加的單數 'note' 欄位併回 UI 真正讀的 'notes'（複數），否則 UI 看不到
# (b) 清掉 '待人工確認'/'no-anchor:clamped' pending 標記（已核實 → '已人工校驗'）
# (c) 重算 stats：missing=null數, matched=其餘, low_conf=matched中conf<0.5,
#     pending=notes含'no-anchor:clamped|待人工', interpolated=notes含'interpolated',
#     openings_ok/closings_ok=opening/closing.start is not None（注意 0.0 是合法值！）
# (d) 全檔結構校驗：無 overlap、無倒序、openings/closings intact
```

完整收尾腳本見 `tools/finalize.py`。

## 已知 ASR 變形速查（貼吧/微信常見）

| 正字 | ASR 常誤為 |
|------|-----------|
| 师父 | 师傅 |
| 搭档 | 刀板 / 炸弹 |
| 极乐世界 | 记了世界 |
| 业力 | 夜粒 / 衣粒 |
| 淫欲 | 盈民 / 溢欲 |
| 习气 | 吸气 |
| 弥勒 | 弥若 |
| 慈禧太后 | 残害太后 |
| 须弥山 | 薛弥山 / 虚米三 |
| 千湍盈泰 | 千州银泰 / 金瑞银泰 |
| 郑勇 | 郑雄 |
| 贴吧用户_QUDy8Na | QUD wifi / QUDYYN / qudyya |

技巧：**先讀正常文本推測該 ASR 串對應哪個正字**，再反查 SRT（例如英文用戶名唸成全形拼音＋英文字母混合）。

## 誠實保留的低信心段（不可杜撰）

以下情況**不硬湊高信心**，標 null/0.0 + note：

- `answer_text` 為空（佔位段）。
- 內容已併入鄰段（如 05-15 貼吧 #36 併入 #34）。
- 音檔**根本沒讀**該答案（如 05-17 貼吧 #18「安般數息」全程未出現；#39 業力能力才在 3523s 出現）。
- 提問人只被「口頭確認樓層、翻一翻」但沒念答案體（05-14 貼吧 #16）。

## 交付產出

- `<month>.json`（直接用 `<month>.json.new` 覆寫；git 有原版可回溯）。
- 回報：重排了哪些 block、修正了哪些段、7（或 N）段誠實空缺的理由、最終 stats。

詳細 helper 腳本在 `tools/`（`readspan.py`、`xscan.py`、`audit.py`、`seqloc.py`、`finalize.py`、`merge_done.py`）。