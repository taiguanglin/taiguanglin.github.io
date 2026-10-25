# RESUME — qa_split_ebook 自制作業續跑說明（session 重啟必讀）

> **用途**：分類作業（第 4 步）跨 session 進行。任何新 session 從這裡讀完即可無縫續做，
> 不依賴先前對話記憶。進度持久化在磁碟，不在對話裡。

## 1. 現在哪裡（怎麼判斷）

- **進度 SoT**：`tool/qa_split_ebook/build/self_classified/progress.json`
  （`done`: 已通過驗證的批號清單；由 `expand_classified.py` 每批自動更新）
- 批次編號 001–47，每批 75 則；批 NNN 涵蓋 `i = (NNN-1)×75 … NNN×75-1`（i=0…3451）
- **下一批** ＝ `done` 缺的最小批號（勿信本檔或對話中的任何「已完成到第 N 批」字樣——
  一律以 progress.json 為準；它是唯一不會過期的進度真相）。
- 每批的原料：`build/self_batches/batch_NNN.slim.jsonl`（q 全文＋a 前 250 字，
  `sc:true`＝含多個編號子問題、答案保留全文）
- 分類依據：`build/self_batches/tree_compact.txt`（**533 節點的 path 對照表**，
  分類時必讀）、`build/classify_guide.md`、`build/criteria_digest/chNN.md`（章定位/R/N）、
  `build/criteria_digest/chNN_sections.md`（逐節準則）；SoT 準則在
  `tool/qa_curation/wenda2_split_classify_criteria.md`。

## 2. 每批作業流程（循環）

1. `read` 該批 `batch_NNN.slim.jsonl`（75 行 JSONL；注意 read 顯示上限，用 offset 讀完全檔）
2. 逐則判定 → 分類（方法見 §3），輸出**緊湊檔**
   `build/self_classified/batch_NNN.compact`，格式（每行一則）：
   ```
   i|ch-L2-L3(-L4)|conf|依據短語[|flags]
   ```
   - `i`：輸入的 i 欄（必須，不可漏）
   - path 編號：L2＝章內序、L3＝L2 內序、L4＝L3 內序（以 tree_compact.txt 為準）
   - `conf`：h／m／l（＝high/medium/low）
   - flags（可多個）：`nr`＝需複查；`d`＝deferred（師父答「以後再講/等我講經」）；
     `ru=章-L2-L3(-L4)`＝灰色地帶第二候選（必須是樹中存在的 path）
   - **路徑筆誤自檢**：不要寫出 `11-03-33-xx` 這種疊字錯（正確 `11-03-03-xx`）。
     expand 會擋下（path 不在樹中），見到錯誤用 sed 修正重跑。
   - **i 編號 off-by-one 自檢（第 18 批教訓）**：批次尾段連續多行編號時容易整段
     疊代（i=1341 寫成 1342 的內容、1342 寫成 1343……）。expand 只查覆蓋不查
     內容對映，這種錯**不會被擋下**。寫完 compact 後，抽驗最後 3 行的 i 值
     與 slim 檔對應條目的內容是否一致（`tail -3 compact` vs `tail -3 slim`）。
3. 若該批有**要拆分**的條目 → 另寫 `build/self_classified/batch_NNN.splits.jsonl`，
   每個子題一行 JSON（原文逐字）：
   ```json
   {"i":N,"sub":1,"path":"…","conf":"h","rule":"…","q":"子問題原文","a":"對應答案段原文"}
   ```
   - `sub` 從 1 連續編號；被拆條目**不**再出現在 compact 裡
   - 拆分準則：編號子問題師父**分段作答**才拆；**合併回答→不拆**，
     compact 單行＋rule 註明 `merged_answer`；某子問**未被回答**＝孤兒片段→該子行 `nr:true`
   - JSON 檔尾要換行；`a` 內換行用 `\n` 轉義
4. 驗證＋展開（批次守恆、path 命中樹，全過才會寫出 `build/classified/batch_NNN.jsonl`）：
   ```
   tool/word_audio_map2/.venv/bin/python tool/qa_split_ebook/expand_classified.py NNN
   ```
   輸出 `in=75 out=… split=… nr=… low=…` 即通過；出現 `✗` 按訊息修正重跑。
5. （週期性）累積約 20 批或全數完成後重跑 `gen_all.py` 更新 `wenda2_ebook_sep/`。

## 3. 分類判定要點（已驗 12 批的實戰規則）

- **先負規則後正規則**；12 是 fallback 優先序最低；多義詞（念佛/消業/身體反應/夢/
  超度/回向/淫欲/疾病/自殺/習氣/劇本/地藏）先查主準則 §3.2 表。
- 分類看「問句主軸＋師父答案主軸」；答案與問題表面衝突時以實際回答為準。
- 常見歸類慣例（維持一致性）：
  - 非問題（感恩/反饋）→ `12-08-02`（+nr）或 `12-08-01`（講經/錄音反饋）
  - 源檔「无回答」→ 該批正常分類 + `l|nr`
  - 師父禪定境界相關判定類 → `11-02-08-04`；陽神/出體 → `11-02-08-06`
  - 打坐翻淫欲/煩躁/昏沉 → `10-02-08-01/02/05`；修復疼 → `10-03-02`
  - 臨終/助念/接引 → `04-07-04-08/09/10`；回向方法/對象/校量 → `06-05-01/02/03`
  - 打坐身體反應冷熱 → `10-02-03`；氣感 → `10-02-06`；五感變化 → `10-02-07`
  - 前世記憶/宿命 → `04-04-03`；劇本注定/隨機 → `04-03-08-03`；文明面 → `04-03-04`
  - 純名相/公案/經文句義 → `12-05-01`；高僧身分 → `12-04-08`
  - 民俗（八字/風水/燒紙/出馬）→ `12-07-02-06`；靈異/附體/壓床 → `12-07-05`
    （被干擾的**應對**→`02-05-06`，現象本身→`12-07-05`）
- 簡繁不轉、原文逐字（splits 的 q/a 從 slim 原文複製，不修正簡體）。

## 4. 全部完成時

1. `expand_classified.py --all` 清點 47 批全綠
2. `gen_all.py` 重組 `wenda2_ebook_sep/`；讀 `build/report.md` 查分布/複查/隔離
3. 驗收：預覽 `wenda2_ebook_sep/index.html`（本地 `python3 -m http.server`）
   抽查 ⚑復查旗標、99 收容章是否清空（未分類殘留）
4. 向使用者報告：分布統計、拆分/複查/deferred 數、需要人工複查的清單位置

## 5. 給新 session 的啟動檢查表

```bash
cd /Users/paul/tai/taiguanglin.github.io
# ① 進度與下一批（動態計算，不依賴任何文字記錄）：
python3 - <<'EOF'
import json
d = json.load(open('tool/qa_split_ebook/build/self_classified/progress.json'))
all_b = {f"{n:03d}" for n in range(1, 48)}
print("已完成批:", len(d["done"]), "→", ",".join(d["done"]))
nxt = min(all_b - set(d["done"]), default="（全部完成）")
print("下一批:", nxt, "｜剩:", len(all_b - set(d["done"])), "批")
EOF
# ② 抽看最新幾批的緊湊檔，確認格式（i|path|conf|rule[|flags]）：
tail -3 tool/qa_split_ebook/build/self_classified/batch_013.compact
# ③ 讀分類對照表（每批作業前必讀）：
head -40 tool/qa_split_ebook/build/self_batches/tree_compact.txt
```

然後依 §2 流程逐批循環（read slim → 判定 → 寫 compact → expand 驗證）。
批次全部完成時：依 §4 收尾（gen_all → report → 預覽驗收）。

⚠️ venv：一律用 `tool/word_audio_map2/.venv/bin/python`（規則見 tool/AGENTS.md 鎖版要求）。

## Step 7：產生全分類合併電子書 wenda2_ebook_classified/

```
../../word_audio_map2/.venv/bin/python gen_classified.py
```

合併 Word 章（01–12，5,789 條）與 PDF 分類條目（3,459 條）→ 12 章主題樹全分類電子書。

- 來源 1：解析 `wenda2_ebook/01–12.html`，用 h2/h3/h4 標題文字映射到樹路徑（`tree_compact.txt` 的 name → path）
- 來源 2：`build/classified/*.jsonl`（已有的 ch/l2/l3/l4 分類）
- HTML 大小控制：`content-visibility: auto` + `contain-intrinsic-size: auto 240px`——離屏內容瀏覽器不渲染，大檔案也能流暢捲動；列印時改回 `visible`
- 每章條數 = Word 既有 + PDF 新分類（report.md 的「既有」+「新」= 此處合計）

### 四套電子書/校對產物的角色

| 目錄 | 用途 |
|---|---|
| `wenda2_ebook/` | 正式上線對外公開（Word 分類 01–12 + PDF 月度 13–21） |
| `wenda2_ebook_sep/` | PDF 分類結果預覽（僅 13–21 章的分類條目，01–12 主題樹） |
| `audio_map1_sep/` | `wenda2_ebook_sep/` 的音頻對齊與校對 UI |
| `wenda2_ebook_classified/` | Word + PDF 全部分類後的完整合併版（看實際效果用） |

## 完整工作流程（音頻校對 → 分類修正 → 電子書產出）

### 日常操作順序

```
Step A：audio_map1_sep/ 音頻校對
  → 瀏覽器開 http://localhost:8084/audio_map1_sep/
  → 選月份 → 選 session → 校對每段音頻對齊（含拆分子題的 pending 段）
  → 校對中發現分類問題 → 記下 question_id

Step B：分類修正（如有）
  cd tool/qa_split_ebook/
  # 1. 修改 compact 檔
  vim build/self_classified/batch_NNN.compact
  # 2. 重跑 expand（驗證 + 產生 classified JSON）
  ../../word_audio_map2/.venv/bin/python expand_classified.py NNN
  # 3. 重建 wenda2_ebook_sep（分類預覽版）
  ../../word_audio_map2/.venv/bin/python gen_all.py

Step C：重建全分類合併電子書
  cd tool/qa_split_ebook/
  ../../word_audio_map2/.venv/bin/python gen_classified.py
  → 產出 wenda2_ebook_classified/（Word + PDF 全分類，格式與 wenda2_ebook 完全一致）
```

### 一鍵跑通（Step B + C 合併）

```bash
cd tool/qa_split_ebook
../../word_audio_map2/.venv/bin/python expand_classified.py --all
../../word_audio_map2/.venv/bin/python gen_all.py
../../word_audio_map2/.venv/bin/python gen_classified.py
```

### 四套產物對照

| 產物 | 內容 | 用途 |
|---|---|---|
| `wenda2_ebook/` | Word 01-12 + PDF 月度 13-21 | 正式上線版 |
| `wenda2_ebook_sep/` | 僅 PDF 分類條目（01-12 主題樹） | 分類結果預覽 |
| `audio_map1_sep/` | 音頻對齊校對 UI | 校對 PDF 條目的音頻時間 |
| `wenda2_ebook_classified/` | Word + PDF 全分類合併 | 看最終分類效果 |

### gen_classified.py 的兩個來源

1. **Word 章**（wenda2_ebook/01-12.html）——解析 `<main>` 內的 h2/h3/h4 標題（用 `text_content()` 取文字、`clean_heading()` 去掉尾部計數括號），把 Q&A 掛到對應的樹路徑
2. **PDF 分類條目**（build/classified/*.jsonl）——已按 ch/l2/l3/l4 分好類
3. 每個樹節點：Word 條目（保持原序）→ PDF 條目（按日期排），合併輸出
4. 渲染走 word2ebook 管線（HTMLGenerator + SearchIndexGenerator + StaticAssetsManager）——輸出格式與 wenda2_ebook 完全一致（簡/繁、搜尋、TOC、閱讀設定、暗色模式）
