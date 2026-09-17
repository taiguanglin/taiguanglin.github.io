# wenda2_curation pipeline 狀態（session 完成版）

本目錄 = 《坐禪之問答錄2》知識萃取的完整保存檔 + 三個網頁的生成器。
萃取日期：2026-09-16（對 `wenda2_ebook/` 當時狀態）。

## 資料檔（`data/`，全部已驗證）

- `ch01..21.json`：語料。每筆 `{id, time, q, a, sub, anchor, n_ans}`；9,231 個有回答的 QA。
  - `id`/`anchor` 對應 `wenda2_ebook/{NN}_trad.html` 的 `question-XXXXXXXXXXXX` 錨點；`sub` 為所屬小節（標題對應 pinyin 錨點）；`time` 為回答日期。
- `site_data.json`：`chapters[21]`（title/n_qa/date_min/date_max/ebook 檔名）＋前 12 章每章全部小節（`subs`：sub/count/anchor/quote/qid/date）＋月度章（13–21）精選（`highlights`：date/quote/qid）＋日期平台小節（`sections`）。
  - 引句為逐字摘錄：真實句邊界（。！？；）切片，句首去稱謂/問題回聲加 `……` 前綴，逗號截斷加 `……` 後綴；436/437 通過逐字驗證（例外：ch12 韋陀菩薩小節無引句，只顯示標題＋計數＋連結）。
- `term_stats.json`：131 個名詞的 `terms`（候選列表）、`totals`（全書合計）、`per_ch`（21 章逐章）、`rank`（合計排序）。
  - 注意：繁體語料寫「淫慾」（729 次）不是「淫欲」；「發願」（1,488 次）與「幻覺」不在本檔，由 build 腳本重掃語料補齊。
- `curation_terms.json`：最終 11 分支 / 57 名詞。每詞 `{id, term, desc, points[2–3], quote_key, override?, rel[]}`。
- `curation_chapters.json`：21 章 `{lede, core:[{point, qid, ch}]}`（60 個要點；`ch` 為 qid 實際所在章，跨章連結已解析）。
- `quotes.json`：57 名詞逐字引句 `{quote, qid, ch}`，100% 對電子書原文逐字驗證。
- `term_reps.json`：名詞 → 代表答案 qid（計分＝出現次數×8＋長度獎勵）。
- `term_packet.txt` / `chapter_packet.txt`：session 中人工精讀的選材包（AI 讀過的代表答案全文）。

## 生成器（`build/`）

- `build_mm.py`＋`build_mm2.py` → `wenda2_mindmap.html`（引擎從 `mindmap.html` 程式化拷貝：`var CX = 540` 起、`renderChart` 到 `})();` 止；兩處補丁：chips 中心標籤、圖表 aria-label）。
- `build_wk.py` → `wenda2_knowledge.html`。
- `build_full.py` → `wenda2_knowledge_full.html`（本檔全錄頁）。
- 產出頁為「生成但直接 commit」：改內容請改 `data/` 或腳本再重跑，不要手改頁面後又重跑（會覆蓋）。
- 引擎兩處字串補丁：`renderChips` 的 root 標籤改用 `ROOT.label`；`renderChart` 圖例去 `《》`、軸標籤「全書合計出現次數（次）」。心智圖引擎若在 `mindmap.html` 更新，需兩頁同步（重跑 build_mm.py 即可，它直接讀 mindmap.html）。

## archive/

中間產物（選材草稿 curation_terms2/3、分批閱讀包 batches/chunks 與其 manifest、測試用 data_test.js/page_script.js、一次性整合腳本 integrate.py）。不參與重建，僅存檔。

## 驗證方法（重跑）

- 引句逐字：對 `wenda2_ebook/{ch}_trad.html` 原文與去標籤＋HTML unescape 兩種形式做子字串比對（`……` 前後綴先剝除）。
- 連結：每個 `wenda2_ebook/{NN}_trad.html#anchor` 對目標檔 `id="{anchor}"` 存在性檢查。
- JS：`node --check`；資料完整性用 node eval（NODES/rel/quote/EBOOK_LINKS 全有效）。
