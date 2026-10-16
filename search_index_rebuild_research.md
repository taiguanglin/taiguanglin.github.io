# 研究報告：為什麼音檔對齊後重建 ebook，search index 會跟著更新？

> 調查日期：2026-10-16（HEAD = 17a21bc）
> 範圍：`audio_map2/`（→ `wenda2_ebook/`，word2ebook）、`audio_map3/`（→ `ebook/`，books2ebook）

## TL;DR

1. **search index 的內容與音檔對齊完全無關**——機器碼審視與 byte 級實測都證實：只改
   `audio_map2/*.json` / `audio_map3/*.json`，用**同一個 Python 環境**重建，
   `search_index*.json` 與 `.hash` **逐 byte 不變**。
2. 你觀察到的索引更新，來自 **17a21bc 那次重建的 ebook/ 半邊用錯了解譯器**：
   `/usr/bin/python3`（PyMuPDF **1.26.5**）而非鎖版 venv（PyMuPDF **1.28.2**）。
   PDF 抽字在兩版間有斷行／空白差異（`18岁` → `18 岁`、`B站` → `B 站`…），
   36 段文字改變、pid（= md5(文字+段序)，規則 13）連帶改變 → 索引 + .hash 更新。
3. 「對齊 → 重建 → 索引也變」是**相關不是因果**：對齊只是「觸發重建」的時機；
   索引差異全部來自環境漂移。tool/AGENTS.md「依賴已鎖版」一節早已記載此風險。
4. **更嚴重的附帶傷害**：錯環境重建讓 `tests/test_follow_along_build.py`
   **7 failed**——部署版四十二章有 **10 段已校對跟播遺失**，另有 **25 個已對齊 pid**
   （楞伽1／六祖12／楞嚴12，講次未 reviewed）在 HTML 上不存在，未來勾 reviewed
   時會整批靜默漏掉。
5. 「有辦法不更新嗎？」——**有，而且已經成立**：只要每次都用鎖版 venv，純音檔
   對齊的重建就不會動索引。需要做的是 (a) 一次性用 venv 重建 `ebook/` 修復現況，
   (b) 給 `gen_all.py` 加 PyMuPDF 版本守門杜絕再犯。

---

## 1. 機制：索引項目從哪來，音檔對齊為何動不到它

### ebook/（books2ebook；audio_map3 對應這邊）

- 搜尋項目在 `html_generator.render_chapter()` 內以
  `add_item(TYPE_CONTENT, b["text"], fname#pid, cur_section)` 建立，
  來源是 `parsers.parse_book()` 解析出的**區塊文字**。
- 音檔對齊只透過 `para_audio_map.para_time_attrs()` 在 `<p>` 上加
  `data-start`/`data-end` **屬性**；只有 `reviewed=true` 講次注入（規則 13）。
  屬性不會進入索引項目的 `content`，pid 在 `annotate()` 階段就由文字決定。

### wenda2_ebook/（word2ebook；audio_map2 對應這邊）

- 索引由 `content_processor.py` 從**渲染後的章節 HTML** 抽取（`get_text()`）。
  注入的 `.qa-play` 播放鈕只含 SVG 圖示、**無文字節點**（`qa_play_markup.py`），
  `get_text()` 結果不變；question/answer 的元素 id 由「人名＋時間＋內容前綴」
  雜湊（`text_utils.IDGenerator`），與播放鈕無關。
- 佐證：17a21bc 中 `wenda2_ebook/01–12*.html` 因 2024-12 對齊更新而注入播放鈕，
  但 `wenda2_ebook/search_index*.json` **完全沒變**（不在該 commit 檔案清單）。

## 2. 實證：四個現場重建的 byte 級比對

| 產物 | 用什麼建 | PyMuPDF | `ebook/search_index.json` MD5 | `wenda2_ebook/search_index.json` MD5 |
|---|---|---|---|---|
| f0763a9 提交版（10-15，訊息明言「鎖版 venv」） | venv | 1.28.2 | `4e5b9867…` | `917f0447…` |
| **17a21bc = 目前 HEAD**（10-16，對齊後重建） | `/usr/bin/python3` | **1.26.5** | `9ab42d79…` | `917f0447…`（不變） |
| 本次重build：venv（含 517649c 楞伽 87 段時間重錨、14d035f 25 個 pid 重配對） | venv | 1.28.2 | **`4e5b9867…`＝f0763a9** | `917f0447…`＝HEAD |
| 本次重build：`/usr/bin/python3` | 系統 | 1.26.5 | `9ab42d79…`＝HEAD | `917f0447…`（不變） |

三個關鍵推論：

- **純音檔變更 → 索引零影響**：自 f0763a9 以來 `books/*.pdf` 與 parser 程式碼
  **零變更**（`git log -- books/ tool/books2ebook/` 僅測試＋sync 工具），
  唯一變的是 audio_map 資料。venv 重重建的索引與 f0763a9 提交版**逐 byte 相同**；
  `08.html` 對 f0763a9 的 diff 只有 174 行 `data-start`/`data-end`（楞伽時間重錨）。
- **HEAD 的索引差異是環境漂移**：36 筆 item 差異 **100% 是空白差異**
  （`18岁`→`18 岁`、`（公元67年）`→`（公元67 年）`、`B站`→`B 站`…），
  且 36 個 pid 全部連帶改變（pid 是文字雜湊）。此即 tool/AGENTS.md「依賴已鎖版」
  警告的「72 段差異」同型事故（36 段 ×簡繁兩語）。
- **只有 books2ebook 對 PyMuPDF 版本敏感**：word2ebook 的 `pdf_parser.py`
  有自己的接段／重排邏輯，`/usr/bin/python3` 與 venv 兩種 build 的
  `wenda2_ebook/search_index*.json` **完全相同（0 筆差異）**。
  敏感點在 books2ebook `parsers._join()` 依賴抽取片段邊界的空白判定。

## 3. 根因鏈（事故怎麼發生的）

1. `tool/books2ebook/gen_all.py` 檔頭註解**仍寫**「確保以倉庫根的
   `/usr/bin/python3`（pymupdf/opencc）執行」。這台機器的 `/usr/bin/python3`
   剛好裝了 pymupdf **1.26.5** + opencc + python-docx，所以「能跑、不會報錯」，
   但不是鎖版的 1.28.2——註解本身就是鎖版政策（requirements.txt `pymupdf==1.28.2`）
   之前的過時遺留。
2. 17a21bc（提交訊息＝word2ebook `gen_all_and_push.py` 的預設訊息，且它
   `git add :/` 掃全 repo）：wenda2_ebook 半邊產物正確（且對版本不敏感），
   ebook/ 半邊用 `/usr/bin/python3` 重建 → 36 段空白+pid 漂移 →
   `ebook/search_index*` 4 檔更新，同時打斷了跟播鏈。
3. 使用者看到的時間順序是「對齊完成 → 重建 → 索引也更新」，因此以為是對齊造成；
   實際上對齊只是觸發重建的時機。

## 4. 附帶傷害（比索引 diff 更需要修）

`cd tool/books2ebook && ../word_audio_map2/.venv/bin/python -m pytest tests/`
目前 **7 failed, 26 passed**（`test_follow_along_build.py`）：

- `07.html` 四十二章（sishierzhang）：HTML 上 `data-start` 970 個，
  正確 venv build 爲 **980** → **10 段已校對（reviewed）跟播遺失**，
  部署版讀者現在看不到這 10 段的跟播（規則 13 的靜默失敗）。
- 另有 **25 個 pid**（楞伽 1／六祖 12／楞嚴 12，屬尚未 reviewed 的講次——
  即 14d035f 早上才用 `sync_para_pids.py` 重配對過的那批）在 HEAD HTML 上
  不存在：這些講次未來勾 `reviewed=true` 時，整段時間會靜默漏掉。
- 楞伽 `08.html` 的 87 段時間重錨（517649c）在 HEAD 有正常生效——遺失的
  只有 pid 漂移的段落。

## 5. 「有辦法做到此情況下不更新嗎？」——有，分兩層

### 5.1 事實層：其實已經成立

同一環境 + 只改 `audio_map2/`／`audio_map3/` ⇒ `search_index*.json`／`.hash`
byte 級不變（本次實測）。要讓它「永遠」成立，只需杜絕環境漂移：

### 5.2 一次性修復（建議立即做）

```sh
cd tool/books2ebook && ../word_audio_map2/.venv/bin/python gen_all.py
```

- 預期恰好改 **14 檔**：`03/07/08/09/10{,_trad}.html` + `search_index*.json{,.hash}`
  （= 17a21bc 那 14 檔的反向修正，內容回到 f0763a9 的 venv 軌道，
  同時保留楞伽時間重錨）。
- 效果：10 段跟播補回、25 個 pid 復活、`pytest tests/` 轉綠；
  `search_index.json` 回到 `4e5b9867…`。**這次更新是必要的一次性修正**，
  之後（同環境）音檔對齊重建就不再動索引。

### 5.3 守門（防止再犯，二選一或都做）

- **版本守門**（最小改動）：兩個 `gen_all.py`（至少 books2ebook）啟動時驗
  `pymupdf.__version__` 是否等於 `tool/word_audio_map2/requirements.txt` 的
  pin（1.28.2），不符即 `exit 1` 並印「請用 `tool/word_audio_map2/.venv`」。
  把「靜默漂移」變成「大聲失敗」——與規則 13 把跟播鏈變成會失敗的測試同一思路。
- **自動切換**（更強）：`gen_all.py` 發現自己不是 venv python 時 `os.execv`
  重啓到 `tool/word_audio_map2/.venv/bin/python`，讓任何 shell 打
  `python3 gen_all.py` 都會落到鎖版環境。
- 同步修正 `tool/books2ebook/gen_all.py` 檔頭「/usr/bin/python3」的過時註解
  與 README 指令文字（它就是這次事故的指引來源）。

### 5.4 不建議的路

- **把索引改成增量／跳過重建**：索引本來就不依賴音檔資料，不需要動；
  改了反而多一個「索引與 HTML 不同步」的風險面。
- **文字正規化求版本無感**（如掃掉 ASCII↔CJK 間空白）：會一次性改 72 段文字
  → pid 全變 → `audio_map3` 需大規模 `sync_para_pids.py --apply`，成本與風險
  遠高於鎖版 venv（規則 13：改文字正規化＝pid 換掉＝已校對時間靜默失效）。

## 6. 後續處理紀錄（2026-10-16，本報告完成後同日執行）

- **一次性修復已執行**：以（故意的）`/usr/bin/python3 gen_all.py` 觸發新守門
  → 自動切換鎖版 venv 重建 → `ebook/` 恰改 **14 檔**（10 章節 HTML + 4 索引檔），
  `search_index.json` 回到 `4e5b9867…`（= f0763a9 軌道），
  `07.html` data-start 970 → **980**（10 段四十二章跟播補回）。
- **守門已上線**（word2ebook／books2ebook 共用 SoT `utils/env_guard.py`）：
  - `gen_all.py`／`gen_all_and_push.py`（兩工具）與 word2ebook `main.py`：
    非鎖版直譯器自動 `os.execv` 切換（pytest 保險絲、`W2E_SKIP_ENV_GUARD=1` 逃生口）。
  - `books2ebook main.build()` 與 word2ebook `gen_all.py`／`main.py`：
    建置前驗 `pymupdf.__version__` == requirements.txt pin（1.28.2），不符 exit 1。
  - 過時的「/usr/bin/python3」指引已從 `tool/books2ebook/gen_all.py` 檔頭、
    README、`dev_verify.py` 清除；OpenSpec `overview/spec.md` 增補
    Locked-Build Environment Guard 需求；`tool/AGENTS.md` 補守門說明。
- **測試**：word2ebook 605 passed（含新增 `test_env_guard.py` 12 條）；
  books2ebook 39 passed / 4 skipped（修復前的 7 red 全數轉綠）。
- **後續可留意**：`ebook/search_index_trad.json` 內容有微幅回復（36 段空白
  反向修正）——`tool/daily_quotes` 管線若要更新候選池需重跑，但既有成品
  `daily_quotes.json` 不受影響（其引用的段落 id 皆未變）。

## 7. 重現指令（本報告所有數據的來源）

```sh
# 四個 build（書源與程式碼在 f0763a9..HEAD 間零變更，只有 audio 資料變）
cd tool/books2ebook
../word_audio_map2/.venv/bin/python main.py --out /tmp/ebook_venv    # → 4e5b9867…
/usr/bin/python3                   main.py --out /tmp/ebook_sys       # → 9ab42d79…＝HEAD

cd ../word2ebook
../word_audio_map2/.venv/bin/python main.py <docx> /tmp/wenda2_venv --pdf <pdf1> --pdf <pdf2>  # → 917f0447…＝HEAD
/usr/bin/python3                   main.py <docx> /tmp/wenda2_sys   --pdf <pdf1> --pdf <pdf2>  # → 917f0447…（版本不敏感）

# 現況契約測試（7 red）
cd tool/books2ebook && ../word_audio_map2/.venv/bin/python -m pytest tests/ -q
```
