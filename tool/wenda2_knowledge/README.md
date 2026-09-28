# wenda2_knowledge —《坐禪之問答錄2》的兩本「複習用」電子書

> 給**已經讀完** `wenda2_ebook/`（9,207 則問答）的人。這兩本書不是原書的摘要，
> 是把同一批問答**重新編排**之後的第二讀：一本按主題收攏，一本按敘事重走。

---

## 產出

| 目錄 | 書名 | 組織 | 用途 |
|------|------|------|------|
| `hidden/wenda2_keypoints/` | 坐禪之問答錄2・**重點知識** | 18 章 / 117 節，每節引文＋自測 | 查閱式複習：同一個道理集中在一處；2025-06 之後的新說法與修正單獨成章（ch16–18），新舊並列時以新為準 |
| `hidden/wenda2_lens/` | 坐禪之問答錄2・**另一個讀法** | 六卷十八場，第二人稱敘事 | 敘事式複習：從「你還不知道」走到「你開始給出去」，附三條閱讀路線（一日速讀／七夜跟讀／完整旅程），每場一件「今天可以做」的事 |

兩本都是靜態頁：繁簡雙頁（`XX.html` 簡 / `XX_trad.html` 繁）、全文檢索、
每條引文可深連結回 `wenda2_ebook/` 原書的那一則問答。

## 這套工具的硬性原則

**引文必須逐字等於原書。** 複習書的全部價值在於「引的是原話」，所以這件事
用三層機制守住，任何一層不過就 `exit 1`：

1. **作者不手抄引文。** `src/*.py` 裡只寫「哪一則問答的第幾句」（`Q()`）
   或直接貼一段繁體原文（`QT()`），文字在建置時才從 `data/corpus.json` 取。
   簡體版不是轉換出來的，而是直接取語料裡對應的 `a` 欄位。
2. **逐字比對。** `common.verify_book()` 確認每一條引文的繁體版是 `at` 的
   子字串、簡體版是 `a` 的子字串。
3. **不連續就擋掉。** 跳句拼出來的「引文」在原文裡根本不存在，
   `quotepick.Quote.resolve()` 會直接報錯並指出漏掉哪幾句。

## 資料流

```
問答錄2/*.docx + *.pdf  ── tool/word2ebook/gen_all.py ──►  wenda2_ebook/
        │
        ▼ tool/wenda2_knowledge/extract_corpus.py
data/corpus.json      ← 語料（21 章 / 428 小節 / 9,207 則問答，繁簡各一份）
        │               每則：qid、提問人、時間、問題、回答首段（回答多段只取末段首段）
        │ src/keypoints_[a-e].py、src/lens.py   ← 作者寫的編輯內容（只寫繁體）
        │ quotepick.py 解析 Q()/QT()
        ▼
build_all.py ──► hidden/wenda2_keypoints/、hidden/wenda2_lens/
```

`data/corpus.json` 是**生成物**（`extract_corpus.py` 的輸出，已 gitignore），
`src/*.py` 才是 SoT。

## 指令

```bash
V=tool/word_audio_map2/.venv/bin/python     # 簡繁轉換需要 venv 裡的 opencc

python3 tool/wenda2_knowledge/extract_corpus.py            # wenda2_ebook/ → data/corpus.json
python3 tool/wenda2_knowledge/dump_text.py --ch 3          # 傾印第 03 章純文字（閱讀用）

$V tool/wenda2_knowledge/audit.py                        # 一次列出所有引文定位的問題
$V tool/wenda2_knowledge/audit.py --short                # 只印錯誤
$V tool/wenda2_knowledge/audit.py lens                   # 只查某一本

$V tool/wenda2_knowledge/build_all.py                     # 兩本一起建
$V tool/wenda2_knowledge/build_all.py --only keypoints    # 只建其中一本
$V tool/wenda2_knowledge/build_all.py --check             # 只驗證不寫檔
```

改電子書文字（重建 `wenda2_ebook/`）之後，**一定要**重跑 `extract_corpus.py`
再重建兩本書——引文是原書的快照，原書動了就得重新對齊。
語料萃取規則（問答切分、回答只取末段首段、`Taiguanglin` 署名處理）
以 `extract_corpus.py` 檔首 docstring 為準，**不要**放寬取文範圍：
引文的句號是按這個範圍數的。

## 撰寫引文

```python
from quotepick import Q, QT

# Q()：指定句號（1-based）。必須連續。句 1 是回答開頭的作者名（Taiguanglin）。
Q("04/question-87b79b27591e", 3, topic="佛法只講意識，不講能量")
Q("01/question-1589e9ddd419", 4, until="叫四念處", topic="觀察自己的意識即四念處")

# QT()：直接貼繁體原文，簡體版自動按字元對齊取出。適合整段引用。
QT("21/question-57aeb73131a7", "還有道家的內容…", topic="只賣自己的貨")
```

先寫草稿再驗證：

```bash
python3 tool/wenda2_knowledge/find_quote.py 迴向 --ch 3,6 --n 5   # 跨全書找
python3 tool/wenda2_knowledge/find_quote.py --qid 04/question-f6fd885db29a     # 印帶編號的句子
python3 tool/wenda2_knowledge/find_quote.py --qid 04/question-f6fd885db29a --sent 2,3
```

## 兩本書的分工

**《重點知識》** ＝ 地圖＋對照表。原書 21 章按時間與提問順序收錄，這裡改按
主題重組：地基三設定 → 意識層次 → 業 → 加持 → 消業 → 發心持戒 → 善法算法 →
世界 → 終點 → 極樂 → 入門功課 → 禪定次第 → 唸誦 → 生活 → 辨法（ch1–15）；
ch16「2025-06 之後的新說法（含修正）」、ch17「2025-11 之後的最後一批教導」、
ch18「2026-01～03 補齊」把月度章節裡的**修正與補充**單獨抽出——
凡「新說法修正舊說法」之處，以較新版本為準並標註（引文 topic 帶
「【第N章原話】」「【早期說法】」等前綴作對照）。

**《另一個讀法》** ＝ 讀小說。第二人稱，把整本問答錄走成一條路：
你刷到一個帖子 → 你開始做功課 → 身體開始變 → 你開始懷疑 → 你見到一點光 →
你開始給出去 → 終點不是一個人。每一場只掛 2–7 條師父原話當「聲音」，
場與場之間用敘事接起來；卷一～卷六對應這條路的六段。

## 檔案

| 檔案 | 角色 |
|------|------|
| `extract_corpus.py` | `wenda2_ebook/*.html` → `data/corpus.json`（問答體；規則見檔首 docstring） |
| `dump_text.py` | 語料 → `data/dumps/ch_NN.txt`（閱讀用純文字，含 qid） |
| `common.py` | 語料查詢、逐字驗證、繁簡轉換、深連結、出處標籤、HTML 小工具 |
| `quotepick.py` | `Q()` / `QT()` 兩種引文定位器 ＋ 連續性守門 |
| `src/keypoints_[a-e].py` | 《重點知識》內容（拆五檔只是讓 diff 好讀） |
| `src/keypoints.py` | 組裝成完整的 `BOOK` |
| `src/lens.py` | 《另一個讀法》內容（敘事 ＋ voices ＋ practice ＋ 閱讀路線） |
| `render.py` | 資料 → 靜態 HTML ＋ 檢索索引 ＋ 落地自檢 |
| `build_all.py` | 兩本一起建，含逐字驗證與落地檢查 |
| `audit.py` | 一次列出所有引文定位的問題（改稿時最常跑） |
| `find_quote.py` | 檢索工具（找問答／印帶編號句子） |
| `assets/book.css` / `assets/book.js` | 版面與互動（自測展開、全文檢索、錨點高亮） |
| `data/corpus.json` | 生成物（快取，勿手改、不進版控） |
| `data/dumps/` | 閱讀傾印（生成物） |

## 站點整合（已部署，不索引）

- 輸出在 **`hidden/`** 下，入口是 **`hidden/index.html`**（四本複習書的入口）。
- **`hidden/` 已進版控並部署**，定位是「不索引的未公開頁」：有網址就能讀，
  搜尋引擎不收錄、也不掛全站導覽。⚠️ 靜態 Pages 沒有存取控制。
- 三重守門（由 `tool/site_chrome/check_site.py` 守門，缺檔會略過）：
  1. 每頁自帶 `<meta name="robots" content="noindex, nofollow, noarchive">`；
  2. 不列入 `sitemap.xml`；
  3. `robots.txt` 有 `Disallow: /hidden/`。
- 全站導覽與 landing 頁（`index.html`、`wenda2.html`）**刻意不放**這些入口；
  `lang-switch.js` 的 `EBOOK_DIRS` 也**刻意不含** `/hidden/`。
- 兩本複習書與 `/wenda2_ebook/` 原書、與 hidden 內的十書複習對
  互相交叉連結（頁尾「相關閱讀」）。
- 頁面用公開的 `/fonts/fonts.css`；原書頁面本身不載入自架字型，故**不為 hidden
  重建字型子集**（罕用字走系統字型回退）。要改成自架字型覆蓋率 100% 再重跑
  `tool/word_audio_map2/.venv/bin/python tool/fonts/build_fonts.py` 即可。
- 語料快取（`data/corpus.json`）維持 gitignore；`hidden/` 產出物要 commit。

## 免責

兩本書都是**整理**不是**著作**。書內每條引文都標了出處並可點回原書；
頁面頂端與每章開頭都有 AI 整理聲明。內容以 Tai 師父原文為準。
