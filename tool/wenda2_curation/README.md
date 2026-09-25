# wenda2_curation —《坐禪之問答錄2》心智圖資料與頁面生成器

> 2026-09-16 session 產出，2026-09 精簡：知識頁（`wenda2_knowledge*.html`）與其生成器、
> 語料（`data/ch01..21.json`、packets）已移除，僅保留心智圖鏈。資料是 SoT；
> 頁面是生成後直接 commit 的產物。

## 這包是什麼

| 內容 | 說明 |
|------|------|
| `data/site_data.json` | 21 章元資料（title/n_qa/date_min/date_max/ebook 檔）；前 12 章全部小節（sub/count/anchor/quote/qid/date）；13–21 章月度精選（highlights）與日期平台小節（sections）。 |
| `data/term_stats.json` | 131 個名詞的出現次數：`terms`（候選）、`totals`、`per_ch`（21 章）、`rank`。繁體語料寫「淫慾」；「發願/幻覺」每章計數已烤入 `build_mm.py` 的 `EXTRA_COUNTS`。 |
| `data/curation_terms.json` | 最終 11 分支 / 57 名詞：`{id, term, desc, points, quote_key, override?, rel}`。 |
| `data/quotes.json` | 57 名詞逐字引句 `{quote, qid, ch}`，全部對電子書原文驗證通過。 |
| `build/build_mm.py` | 資料 → `build/mm_data.js`（頁面內嵌資料段）。EXTRA 統計與根引句為 2026-09 對語料的一次性萃取，**已烤入字面值**，不讀語料。 |
| `build/build_mm2.py` | `mm_data.js` + NAV/頁腳/more-cards 模板 → `wenda2_mindmap.html`，並自動呼叫 `tool/site_chrome/sync.py`。 |
| `NOTES.md` | pipeline 狀態筆記（schema 細節、驗證方法、補丁點）。 |

已移除（git 歷史可回溯）：`data/ch01..21.json` 全語料、`curation_chapters.json`、`term_reps.json`、
`term_packet.txt`/`chapter_packet.txt`、`build_wk.py`/`build_full.py`、`archive/` 中間產物。

## 輸入 → 輸出

```
wenda2_ebook/{NN}_trad.html          mindmap.html（互動引擎來源）
        │                                  │
        ▼（2026-09 萃取，現為資料檔）        ▼（引擎拷貝）
tool/wenda2_curation/data/*.json ── build_mm.py ──► build/mm_data.js
                                                   │
                                              build_mm2.py
                                                   ▼
                                        wenda2_mindmap.html（root）
        ▲
   注意：引句是「萃取當時」電子書的逐字快照。電子書重建後文字若變動，
   引句需重新驗證（見下）並更新 data/，再重跑 build。
```

## 如何重建頁面

```bash
cd tool/wenda2_curation/build
python3 build_mm.py && python3 build_mm2.py   # → wenda2_mindmap.html（root）
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

- `wenda2_mindmap.html` 為生成產物：**改內容改 `data/` 或腳本再重跑**，
  不要手改頁面後又重跑（手改會被覆蓋）。
- 每頁必須顯示 AI 免責聲明（根 `AGENTS.md` 規則 7），`build_mm2.py` 已內建。
- `mindmap.html` 本體的「三大初始設定」`b-truth` 三葉節點鐵律（根 `AGENTS.md` 規則 9）與本包無關，
  本包不讀不寫 `mindmap.html` 的資料段，只拷貝引擎函式區。
