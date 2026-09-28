# ebook_knowledge —《坐禪與講經十書》的兩本「複習用」電子書

> 給**已經讀完** `ebook/`（坐禪系列＋講經系列十本書）的人。這兩本書不是原書的摘要，
> 是把同一批文字**重新編排**之後的第二讀。

---

## 產出

| 目錄 | 書名 | 組織 | 用途 |
|------|------|------|------|
| `hidden/ebook_keypoints/` | 坐禪與講經十書・**重點知識** | 四部多章 / 每節附引文＋自測 | 查閱式複習：同一個道理集中在一處，散在十本書裡的說法互相對照 |
| `hidden/ebook_lens/` | 坐禪與講經十書・**另一個讀法** | 六卷多場 | 敘事式複習：把十本書走成一條十年的參學路，附閱讀路線 |

兩本都是靜態頁：繁簡雙頁（`XX.html` 簡 / `XX_trad.html` 繁）、全文檢索、
每條引文可深連結回 `ebook/` 原書的那一段。

## 這套工具的硬性原則

**引文必須逐字等於原書。** 複習書的全部價值在於「引的是原話」，所以這件事
用三層機制守住，任何一層不過就 `exit 1`：

1. **作者不手抄引文。** `src/*.py` 裡只寫「哪一段原文的第幾句」（`P()`）
   或直接貼一段繁體原文（`PT()`），文字在建置時才從 `data/corpus.json` 取。
   簡體版不是轉換出來的，而是直接取語料裡對應的 `s` 欄位。
2. **逐字比對。** `common.verify_book()` 確認每一條引文的繁體版是 `t` 的
   子字串、簡體版是 `s` 的子字串。
3. **不連續就擋掉。** 跳句拼出來的「引文」在原文裡根本不存在，
   `quotepick.Quote.resolve()` 會直接報錯並指出漏掉哪幾句。

## 資料流

```
books/*.pdf  ── tool/books2ebook/gen_all.py ──►  ebook/   （十本書，1,254,369 字）
      │
      ▼ tool/ebook_knowledge/extract_corpus.py
data/corpus.json                  ← 語料（書／章節標題／引用單位層級，繁簡各一份）
      │                                 引用單位：段落書＝<p id>；02 問答錄＝<article> 的回答
      │ src/keypoints_*.py、src/lens.py   ← 作者寫的編輯內容（只寫繁體）
      │ quotepick.py 解析 P()/PT()
      ▼
build_all.py ──► hidden/ebook_keypoints/、hidden/ebook_lens/
```

`data/corpus.json` 是**生成物**（`extract_corpus.py` 的輸出，已 gitignore），
`src/*.py` 才是 SoT。

## 指令

```bash
V=tool/word_audio_map2/.venv/bin/python     # 簡繁轉換需要 venv 裡的 opencc

python3 tool/ebook_knowledge/extract_corpus.py            # ebook/ → data/corpus.json
python3 tool/ebook_knowledge/extract_corpus.py --stats    # 只看統計
python3 tool/ebook_knowledge/dump_text.py --book 1        # 傾印書 01 純文字（閱讀用）

$V tool/ebook_knowledge/audit.py                        # 一次列出所有引文定位的問題
$V tool/ebook_knowledge/audit.py --short                # 只印錯誤
$V tool/ebook_knowledge/audit.py keypoints              # 只查某一本

$V tool/ebook_knowledge/build_all.py                     # 兩本一起建
$V tool/ebook_knowledge/build_all.py --only lens         # 只建其中一本
$V tool/ebook_knowledge/build_all.py --check             # 只驗證不寫檔
```

改電子書文字（重建 `ebook/`）之後，**一定要**重跑 `extract_corpus.py`
再重建兩本書——引文是原書的快照，原書動了就得重新對齊。

## 撰寫引文

```python
from quotepick import P, PT

# P()：指定句號（1-based）。必須是連續的，否則報錯。
P("01/p-se5fc701c", 4, topic="從樹根講起")
P("01/p-se5fc701c", 4, until="雲裡霧裡", topic="同義但更長")

# PT()：直接貼繁體原文，簡體版自動按字元對齊取出。適合整段引用。
PT("04/p-s633888ac", "義理當中最核心的內容是什麼？…")
```

先寫草稿再驗證：

```bash
python3 tool/ebook_knowledge/find_quote.py 耳根圓通 --book 1 --n 5   # 跨全書找
python3 tool/ebook_knowledge/find_quote.py --pid 01/p-s87b4b470        # 印出帶編號的句子
python3 tool/ebook_knowledge/find_quote.py --pid 01/p-s87b4b470 --sent 2,3
```

## 兩本書的分工

**《重點知識》** ＝ 查字典＋對照表。十本書按主題重組：三大設定 → 意識構造 →
三界 → 業 → 起源與創世 → 實修次第（下段→四禪→之後）→ 法門 → 神通 →
淨土 → 發心與菩薩職業 → 讀經方法 → 各部經的心要。同一個道理在不同書裡的
說法放在一起看；凡有「新說法修正舊說法」之處，以較新版本為準並標註。

**《另一個讀法》** ＝ 讀小說。第二人稱，把十本書編排成一條「十年的參學路」：
2014 年你在貼吧遇到一位樓主 → 十年後他把整張地圖攤開 → 他決定討一頓飯錢、
開始講經 → 一部一部經跟你講下去 → 講到楞嚴「未完」的地方，把書還給你。
每一場結尾給一件「今天可以做」的事。

## 檔案

| 檔案 | 角色 |
|------|------|
| `extract_corpus.py` | `ebook/*.html` → `data/corpus.json`（段落體＋02 問答體） |
| `dump_text.py` | 語料 → `data/dumps/book_NN.txt`（閱讀用純文字，含 pid） |
| `common.py` | 語料查詢、逐字驗證、繁簡轉換、深連結、出處標籤、HTML 小工具 |
| `quotepick.py` | `P()` / `PT()` 兩種引文定位器 ＋ 連續性守門 |
| `src/keypoints_*.py` | 《重點知識》內容（拆檔只是讓 diff 好讀） |
| `src/keypoints.py` | 組裝成完整的 `BOOK` |
| `src/lens.py` | 《另一個讀法》內容（敘事 ＋ voices ＋ practice ＋ 閱讀路線） |
| `render.py` | 資料 → 靜態 HTML ＋ 檢索索引 ＋ 落地自檢 |
| `build_all.py` | 兩本一起建，含逐字驗證與落地檢查 |
| `audit.py` | 一次列出所有引文定位的問題（改稿時最常跑） |
| `find_quote.py` | 檢索工具（找段落／印帶編號句子） |
| `notes2pt.py` | 閱讀筆記 → `pt_bank_*.md`：把 `pid ＋ 模式` 還原成完整 `PT(...)` 行（文字取自語料，零轉錄風險） |
| `check_notes.py` | **整合前必跑**：驗筆記的 pid 存在、`mid::` 關鍵字落在同一段、段落 ≥10 字、條數 == bank 條數 |
| `assets/book.css` / `assets/book.js` | 版面與互動（自測展開、全文檢索、錨點高亮） |
| `data/corpus.json` | 生成物（快取，勿手改、不進版控） |
| `data/dumps/` | 閱讀傾印（生成物） |
| `data/notes/` | 逐書閱讀筆記（寫作素材，生成物） |

## 站點整合（已部署，不索引）

- 輸出在 **`hidden/`** 下，入口是 **`hidden/index.html`**（四本複習書的入口）。
- **`hidden/` 已進版控並部署**，但定位是「不索引的未公開頁」：有網址就能讀，
  搜尋引擎不收錄、也不掛全站導覽。⚠️ 靜態 Pages 沒有存取控制。
- 三重守門（缺一不可）：
  1. 每頁自帶 `<meta name="robots" content="noindex, nofollow, noarchive">`
     （`render.py` 的 `head()` 統一注入）；
  2. 不列入 `sitemap.xml`；
  3. `robots.txt` 有 `Disallow: /hidden/`。
  由 `tool/site_chrome/check_site.py` 守門；該檢查對不存在的 hidden 頁面會略過。
- 全站導覽與 landing 頁（`index.html`、`wenda2.html`）**刻意不放**這些入口；
  `lang-switch.js` 的 `EBOOK_DIRS` 也**刻意不含** `/hidden/`（避免在公開 JS 裡
  留下路徑線索）——因此 hidden 內是以 OpenCC 即時轉換，而非雙頁跳轉。
- 兩本複習書與 `/ebook/` 十書原典、以及 hidden 內的問答錄2 複習對
  互相交叉連結（頁尾「相關閱讀」）。
- ⚠️ 要**正式公開**（讓搜尋引擎收錄、首頁加入口）才需要動守門：移除各頁 noindex、
  加進 `sitemap.xml`、拿掉 `robots.txt` 的 `Disallow: /hidden/`，並同步
  `check_site.py` 與 `lang-switch.js` 的 `EBOOK_DIRS`。
- 語料快取（`data/`）維持 gitignore；`hidden/` 產出物要 commit。
- 頁面用公開的 `/fonts/fonts.css`；原書頁面本身不載入自架字型，故**不為 hidden
  重建字型子集**（罕用字走系統字型回退）。

## 免責

兩本書都是**整理**不是**著作**。書內每條引文都標了出處並可點回原書；
頁面頂端與每章開頭都有 AI 整理聲明。內容以 Tai 師父原文為準。
