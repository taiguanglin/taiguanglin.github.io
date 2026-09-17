# wenda2_curation —《坐禪之問答錄2》知識萃取檔與圖解頁生成器

> 2026-09-16 session 產出。從 `wenda2_ebook/`（當時狀態）萃取的**完整、未壓縮**知識檔，
> 加上三個網頁的生成器。資料是 SoT；頁面是生成後直接 commit 的產物。

## 這包是什麼

| 內容 | 說明 |
|------|------|
| `data/ch01..21.json` | 全語料：9,231 個有回答的問答。`{id, time, q, a, sub, anchor, n_ans}`。`id`/`anchor` = `wenda2_ebook/{NN}_trad.html` 內 `question-XXXXXXXXXXXX` 錨點。 |
| `data/site_data.json` | 21 章元資料（title/n_qa/date_min/date_max/ebook 檔）；前 12 章全部小節（sub/count/anchor/quote/qid/date）；13–21 章月度精選（highlights）與日期平台小節（sections）。 |
| `data/term_stats.json` | 131 個名詞的出現次數：`terms`（候選）、`totals`、`per_ch`（21 章）、`rank`。繁體語料寫「淫慾」；「發願/幻覺」由 build 腳本重掃補齊。 |
| `data/curation_terms.json` | 最終 11 分支 / 57 名詞：`{id, term, desc, points, quote_key, override?, rel}`。 |
| `data/curation_chapters.json` | 21 章 `{lede, core:[{point, qid, ch}]}`（60 要點；`ch` 已解析為 qid 實際所在章）。 |
| `data/quotes.json` | 57 名詞逐字引句 `{quote, qid, ch}`，全部對電子書原文驗證通過。 |
| `data/term_reps.json` | 名詞 → 代表答案 qid（計分＝出現次數 × 8 ＋長度獎勵）。 |
| `data/term_packet.txt`、`data/chapter_packet.txt` | 選材時人工精讀的代表答案全文包。 |
| `build/build_mm.py` + `build_mm2.py` | → `wenda2_mindmap.html`（互動引擎程式化拷貝自 `mindmap.html`）。 |
| `build/build_wk.py` | → `wenda2_knowledge.html`（21 章重點頁）。 |
| `build/build_full.py` | → `wenda2_knowledge_full.html`（知識庫全檔頁：名詞全檔＋統計總表＋小節引句全錄）。 |
| `archive/` | 中間產物（選材草稿、分批閱讀包、一次性整合腳本、測試抽取）。僅存檔，不參與重建。 |
| `NOTES.md` | pipeline 狀態筆記（schema 細節、驗證方法、補丁點）。 |

## 輸入 → 輸出

```
wenda2_ebook/{NN}_trad.html          mindmap.html（互動引擎來源）
        │                                  │
        ▼（2026-09 session 萃取）           ▼
tool/wenda2_curation/data/*.json ── build/*.py ──► wenda2_knowledge.html
                                                   wenda2_mindmap.html
                                                   wenda2_knowledge_full.html
        ▲
   注意：語料是「萃取當時」的快照。電子書重建後文字若變動，
   引句需重新驗證（見下），再重跑 build 腳本。
```

## 如何重建頁面

```bash
cd tool/wenda2_curation/build
python3 build_mm.py && python3 build_mm2.py   # → wenda2_mindmap.html（root）
python3 build_wk.py                            # → wenda2_knowledge.html
python3 build_full.py                          # → wenda2_knowledge_full.html
```

- 腳本以自身位置推算 repo root 與 `../data`，不依賴 /tmp。
- `build_mm.py` 直接讀 repo 的 `mindmap.html` 拷貝引擎（`var CX = 540` → `})();`），
  並套三個補丁：root chips 標籤改用 `ROOT.label`、svg aria-label、圖表軸標籤去「九書」字樣。
  `mindmap.html` 引擎若有改動，重跑即可同步到 wenda2_mindmap.html。

## 驗證（重跑用）

1. **引句逐字**：把 `……` 前後綴剝除後，對 `wenda2_ebook/{ch}_trad.html` 做子字串比對
   （原文與「去標籤 + HTML unescape」兩種形式）。
2. **連結**：每個 `wenda2_ebook/{NN}_trad.html#anchor` 檢查目標檔含 `id="{anchor}"`。
3. **JS**：`node --check`；名詞資料用 node eval 檢查 NODES/rel/quote/EBOOK_LINKS 有效性。

## 鐵律提醒

- 產出頁（knowledge / mindmap / knowledge_full）為生成產物：**改內容改 `data/` 或腳本再重跑**，
  不要手改頁面後又重跑（手改會被覆蓋）。
- 每頁必須顯示 AI 免責聲明（根 `AGENTS.md` 規則 7），`build_*` 已內建。
- `mindmap.html` 本體的「三大初始設定」`b-truth` 三葉節點鐵律（根 `AGENTS.md` 規則 9）與本包無關，
  本包不讀不寫 `mindmap.html` 的資料段，只拷貝引擎函式區。
