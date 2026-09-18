# Session 知識庫：九書名詞查證與圖解工程

> 本頁由 `tool/session_knowledge/build.py` 從 `SESSION_KNOWLEDGE.md` 生成（生成物勿手改，改 md 再重跑）。
> 所有查證以 Tai 師父九本書原文為準；本頁整理本身由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。

這份知識庫完整保存 2026-09-16 至 2026-09-17「mindmap.html 名詞查證與圖解工程」session 的可復用知識：查證方法、逐批發現與修正、證據行號、禁用術語、關鍵節點定稿、腳本與回歸基準。與本知識庫相關的產出：`review.html`（閃卡與測驗）、`books_knowledge.html`（坐禪與講經重點知識）、`books_knowledge_full.html`（坐禪與講經知識庫全檔）、`mindmap.html`（修行次第線區塊）。

---

## 0. 一頁總覽

### 0.1 任務鏈

1. mindmap.html 73 節點逐點對照九本書原文查證（四批次 A／B／C／D）
2. 73 條電子書深連結嵌入（每節點唯一引句處，`var EBOOK_LINKS`）
3. `.mm-lead` 寬螢幕換行修正（移除 max-width、加 text-wrap: pretty）
4. 呈現格式調查 → 建議：閃卡＋測驗、修行次第線
5. review.html（間隔重複閃卡＋名詞測驗）
6. mindmap.html 修行次第線（16 級實修＋7 步義理）
7. books_knowledge.html（坐禪與講經重點知識，按書分冊，從 mindmap 資料生成）
8. books_knowledge_full.html（坐禪與講經知識庫全檔：64 名詞全檔按主幹分組＋書冊分布＋高頻詞次數，比照問答錄2 知識庫全檔）
8. 本知識庫（SESSION_KNOWLEDGE.md → session_knowledge.html）

### 0.2 數字總表

| 項目 | 數字 |
|---|---|
| 名詞節點（root＋主幹＋葉） | 73 |
| 葉節點（名詞） | 64 |
| 主幹 | 8 |
| 逐批查證節點 | 63（A14＋B17＋C12＋D20） |
| 引句前綴審查 | 30 節點（6 修正） |
| 電子書深連結 | 73／73 |
| mm_harness 斷言 | 47（全綠） |
| rv_harness 斷言 | 44（全綠） |
| 坐禪與講經重點知識名詞卡 | 91（含跨書重複） |

---

## 1. 語料地圖

### 1.1 語料 dump 與電子書編號對照

| dump | 電子書 | 書名 |
|---|---|---|
| b01.txt | ebook/01 | 《坐禪》（坐禪 1） |
| b02.txt | ebook/02 | 《坐禪之問答錄》（24 章） |
| b03.txt | ebook/03 | 《坐禪 2》 |
| b04.txt | ebook/05 | 《講金剛經 心經》 |
| b05.txt | ebook/06 | 《講圓覺經》 |
| b06.txt | ebook/07 | 《講四十二章經》 |
| b07.txt | ebook/08 | 《講楞伽經》 |
| b08.txt | ebook/09 | 《講六祖壇經》 |
| b09.txt | ebook/10 | 《講楞嚴經》 |

注意：ebook/04《感恩與講經》不在這套查證語料內。

### 1.2 b01《坐禪》章節結構（dump 行號）

| 章 | 行號範圍 | 節位置 |
|---|---|---|
| 第一章 | 208–596 | 211／263／365／378／415／428／508／526／563 |
| 第二章 | 597–730 | 602／618／653／677 |
| 第三章 | 731–1160 | 749／774／948／995／1010／1063 |
| 第四章 | 1161–1188 | — |
| 第五章 | 1189–1504 | — |
| 第六章 人體 | 1505–1895 | — |
| 第七章 神通 | 1896–2017 | — |
| 第八章 業力 | 2018 起 | 第02節 2034、第03節 2041 |

### 1.3 b03《坐禪 2》篇結構（dump 行號）

篇 headers 為裸文字。設計篇 176 起（11 節）、真相篇 400 起（自性恆常 400／初妄無因 405／諸佛同體 412／妄想 449／分別 550／六根 606／初禪 619）、羯磨篇 640 起（業的原理 640／業與世界 708）、其它篇 10 節。

### 1.4 b09《講楞嚴經》關鍵行號

十番顯見 1089 起（1144／1338／1478／1627／1623／1802／1866・1896／1991／2003／2150–2156）、二種妄見 2159、四科五陰總結 2349、卷三起六入 2709–2717。

---

## 2. 逐批查證報告

### 2.1 批次 A（14 節點：11 ✓ ／ 3 修正）

| 節點 | 問題 | 修正（已落地） |
|---|---|---|
| shifan-xianjian（十番顯見） | desc 漏列第十番 | 補齊十番；desc 以「最後以『見性非見』收束」收尾（定稿見 5.3） |
| zhizhuo（執著） | 執著深淺排序有誤 | 修正為「見」是執著中最深層次（定稿見 5.3） |
| wuyun（五蘊） | 車庫喻出處不實 | src 改為《坐禪1》第06節；《坐禪2》意識・第03節；《講心經》 |

### 2.2 批次 B（17 節點：12 ✓ ／ 7 修正）

| 節點 | 問題 | 修正（已落地，現值） |
|---|---|---|
| wucheng（五乘佛法） | desc 缺通式與人天乘例外 | 「上四乘講的都是下位如何升到上位的方法；人天乘福德法則講如何修福、修德，為後來的修行積攢福報。」 |
| dunjiao-dunxiu（頓教） | desc 非經文言 | 「義理當下直指（頓悟），功夫逐層慢慢滅（漸修）。Tai 師父強調沒有『漸漸悟』——理解總在某一刻突然發生；頓漸之分不在法，而在人有利鈍、見有遲疾。」 |
| sutra-xinjing（心經） | points[3] 八苦漏「怨憎恚」 | 「生、老、病、死、怨憎恚、愛別離、求不得、五蘊熾盛。」 |
| sutra-tanjing（六祖壇經） | points[4] 缺「凡愚」引文 | 「疑問品破求生西方之執：凡愚不了自性，不識身中淨土，願東願西；悟人在處一般；Tai 補充極樂世界與娑婆重疊，在阿彌陀佛加持下變換基本粒子頻率，當下即到。」 |
| sutra-lengyan-jiang（講楞嚴經） | points[4] 卷次有誤 | 「十番顯見起於卷一末、延續至卷二；卷二講二種妄見與四科之五陰；卷三起講六入、十二處至十八界。」 |
| sutra-huayan（華嚴經十地品） | desc 非通式 | desc 改為十地遞進通式（發光地→焰慧地→難勝地→現前地→遠行地→不動地→善慧地→法雲地） |
| sutra-huayan points[1] | 代表地有誤 | 「其中難勝地最能代表菩薩境界：菩薩體悟到妄想是世間一切的基本元素，能做到八識轉六識，在六識形成的輪迴世界內展現任何神通。」 |

### 2.3 批次 C（12 節點，4 處修正）

節點：wuse、seijie、yujie、liudao、yujiechanding、chuchan、erchan、sanchan、sichan、sikongding、yangshen、huineng-zuochan。

| 節點 | 修正 |
|---|---|
| yujiechanding（欲界禪定） | 「三到四年」改「兩到三年」（desc＋P0 兩處） |
| sikongding（四空定→阿羅漢） | 四空定次第 rewrite（desc＋P0；定稿見 5.1） |

### 2.4 批次 D（20 節點，18 處修正）

節點：jiexing、xiaoye、miewenzi、huxi、jiafuzuo、canqing、erbgen、danti、ershinan、shishan-shie、yezhang、jiachili、huixiang、script、zhiye、jile、wenming、shanzhishi、kongxinguanzi、erzhong-wangjian。

重點修正：

| 節點 | 修正 |
|---|---|
| jiexing（戒行） | 補「奶製品」細目（b01:718）；夢中持戒判準收窄到淫戒；src 補全 |
| miewenzi（滅文字妄想） | rewrite：移除不存在術語（心念耳聞等） |
| erbgen（耳根圓通） | rewrite：移除不存在術語（都攝六根淨念相繼等）；補《坐禪2》淨土禪 |
| 多個節點 | src 補全（二十節點出處定稿見 5.4） |

### 2.5 引句前綴審查（30 節點，6 修正）

「全書找不到前綴」的 6 個引句，前綴全部修正（引句本文 q 未動 → 錨點有效）：

| 節點 | 修正後前綴（現值） |
|---|---|
| axiom-firstthought | 《坐禪2》真相・第02節 |
| fenbie | 《坐禪2》意識・第02節 |
| wuyun | 《坐禪1》第一章第06節 |
| aluohan | 《坐禪1》第一章第08節 |
| sutra-lengyan | 《坐禪1》第三章第03節 |
| huxi | 《坐禪之問答錄》第02章 磕大頭 |

---

## 3. 證據速查表

| 主張 | 證據 | 位置 |
|---|---|---|
| 戒行細目含奶製品 | 「奶製品」原文 | b01:718 |
| 消業可轉主動；忍辱 | 主動消業、忍辱原文 | b01:2034／2041／2045 |
| 解脫後入世要服從搭檔（躬身入局） | 躬身入局 | b03:529 |
| 一根細絲喻 | 一根細絲 | b02:2583 |
| 唸佛三昧＝參思情 | 唸佛三昧原文 | b01:882／898 |
| 耳根圓通次第 | 次第原文 | b01:837–840／842 |
| 護身咒；穢跡金剛咒 | 咒名原文 | b01:1016／990 |
| 加持力：佛 100%｜等覺 99%｜空心管子喻 | 加持力原文 | b03:682 |

---

## 4. 禁用術語（語料查無，不得寫入內容）

以下詞彙在九本書語料中查無，是查證過程中被移除的常見 AI 杜撰：

- **心念耳聞** — 語料查無此詞
- **都攝六根淨念相繼** — 語料查無（《楞嚴》《圓覺》系列均無）
- **能念之心與所持之咒脫開** — 語料查無
- **抓住意根** — 語料查無
- **辣椒／蛋作為戒行細目** — 原文戒行細目為五辛、奶製品、過午不食；辣椒／蛋不在其中

未來任何改寫 mindmap／review／books_knowledge 內容時，先對照本清單與原文。

---

## 5. 關鍵節點定稿文本

### 5.1 sikongding（四空定→阿羅漢）

- desc：滅喜情成緣覺後，再滅掉那個沒有內容的情緒（我執），便進入空無邊處定成辟支佛；之後依序經識無邊處定、無所有處定，最高到非想非非想處定。
- P0：滅喜情成緣覺；再滅掉那個沒有內容的情緒（我執）進入空無邊處定，這是辟支佛；之後依序經識無邊處定、無所有處定，最高到非想非非想處定。
- P1：佛陀早年隨外道已修到非想非非想處定卻未了生死——所以必須跳過二十八天所有天界，才是真解脫。
- P2：成為阿羅漢有量化門檻：惡業總量要低於某個數值，而這條線會因該世界佛的數量（也就是加持力總量）而大幅變動。
- P3：娑婆世界目前只有釋迦牟尼佛一位佛，加持力有限；極樂世界已出三十六萬億多的佛，門檻低得多。
- P4：成為阿羅漢之前要和人結成搭檔，以便日後修行與消業中互相指導和保護。
- src：《坐禪1》第四章 From 四禪 to 阿羅漢；《坐禪2》羯磨・第01節
- quote：我還是建議大家先去極樂世界……（《坐禪2》羯磨・第01節）

### 5.2 yujiechanding（欲界禪定）

- desc：滅除一切文字妄想，能兩小時以上處在沒有文字妄想的狀態。一般需兩到三年。
- P0：進來之前應該已經做到：戒肉成功、滅八成淫欲、滅八成文字妄想、三氣歸元、打通全身筋脈。一般需兩到三年。
- P1：標準是滅除一切文字妄想，能兩小時以上處在沒有文字妄想的狀態。
- P2：筋脈剛通時會感覺氣在體內奔騰——那還不算數；等筋脈乾淨通暢、內氣充足，反而感覺不到氣在運轉，才是真的絕對健康狀態。
- P3：最大的陷阱是沉浸在忘我的安樂裡：那種舒服感只是身體不再給你痛感，不是好境界，必須守住覺知、繼續修常規法門。
- P4：這時候千萬不要把注意力亂放在眉心、丹田、雙手上玩內力，很容易岔氣傷內臟，而且極難修復。
- src：《坐禪1》第二章、第06節・3
- quote：就像一隻懶貓吃飽了爬到陽臺上……（《坐禪1》第三章第03節）

### 5.3 shifan-xianjian 與 zhizhuo 定稿

- shifan-xianjian desc：卷二主體：佛不直接描述看不見的自性，改用「心的功用」來證明心一直存在——見性是心非眼、不動、不滅、不失、不還、不雜、無礙、不分、超情，最後以「見性非見」收束。Tai 師父提醒：這一切都是按凡夫境界用邏輯推理。
- zhizhuo P1：執著分三個層次：見（我認為）、取（我想要）、執（你必須服從我）；其中「見」是執著中最深層次的執著。

### 5.4 批次 D 二十節點出處定稿

| 節點 | 出處 |
|---|---|
| jiexing | 《問答錄》第07章 五辛菸酒肉、第08章 淫慾煉精化氣、第22章 開光供養持戒；《坐禪1》第二章第02、03節 |
| xiaoye | 《坐禪1》第二章第01節、第八章 業力；《坐禪2》真相・第03節；《問答錄》第06章 消業 |
| miewenzi | 《問答錄》第05章 誦經持咒唸佛；《坐禪1》第三章第05節 |
| huxi | 《問答錄》第02章 磕大頭、第04章 腹式呼吸；《坐禪1》第二章第04節 |
| jiafuzuo | 《坐禪1》第二章第04節；《問答錄》第03章 開胯壓腿、第09章 打坐時的身體反應 |
| canqing | 《坐禪1》第一章第04節、第三章第02節；《問答錄》第05章、第15章 |
| erbgen | 《坐禪1》第三章第02節・2；《坐禪2》其它・第01、08節 |
| danti | 《坐禪1》第二章第04節、第六章 人體；《問答錄》第04章、第09章 |
| ershinan | 《TaiGuangLin禪師講四十二章經》 |
| shishan-shie | 《TaiGuangLin禪師講四十二章經》 |
| yezhang | 《坐禪2》羯磨・第01節、真相・第03節 |
| jiachili | 《坐禪2》羯磨・第01節・3、其它・第02節 |
| huixiang | 《坐禪2》真相・第03節、起源・第06節、其它・第03節 |
| script | 《坐禪2》真相・第03節；羯磨・第01節；設計篇 |
| zhiye | 《坐禪2》起源・第01–04節；職業篇 |
| jile | 《坐禪2》起源・第05節；羯磨・第01節；《問答錄》第16章 |
| wenming | 《坐禪2》設計篇 第01–11節 |
| shanzhishi | 《坐禪2》起源・第06節、羯磨・第01節、其它・第09節；《講圓覺經》普覺菩薩章 |
| kongxinguanzi | 《TaiGuangLin禪師講四十二章經》 |
| erzhong-wangjian | 《Tai師父講楞嚴經》卷二 |

---

## 6. 方法論與腳本

### 6.1 資料抽取手法（從 mindmap.html 抽內嵌資料）

mindmap.html 的腳本資料在 IIFE closure 內。直接 eval 整段會失敗（`ROOT is not defined`——closure scope）；Node stdin 的 `var __D=` eval 也有 scope quirk。正確手法：抽出資料區段（`var ROOT = {` 到「版面計算」橫幅），再以 IIFE 表達式 eval：

```js
var s = script.indexOf('var ROOT = {');
var e = script.indexOf('/* -------------------------------------------------------- 版面計算');
var D = eval('(function(){' + script.slice(s, e) +
             '\nreturn {ROOT:ROOT, BRANCHES:BRANCHES, EBOOK_LINKS:EBOOK_LINKS};})()');
```

注意：`<script>` 字面索引只匹配無屬性標籤（`<script src=` 不會匹配），所以第一個 `<script>` 就是內嵌主腳本。這也是 build.js 與兩個 harness 共用的手法。

### 6.2 假 DOM harness 模式

- fakeEl：innerHTML setter 記錄到 `allHTML[id]`；querySelectorAll 返回 []。
- document：addEventListener 收集 DOMContentLoaded；getElementById 返回 fakeEl。
- window.tgl_lang stub：getVariant／convertTW（假簡轉換器，只映射斷言用字）／onReady／onChange。
- setTimeout no-op（避免 3 秒保底掛起測試）。
- 時序：`domReadyHandlers[0]()` → `readyHandlers[0]()` → 斷言。

### 6.3 回歸用 harness（自抽取版，存於 repo）

| 檔案 | 用法 | 預期 |
|---|---|---|
| tool/session_knowledge/mm_harness.js | node 執行 | 47 PASS＋ALL ASSERTIONS PASSED |
| tool/session_knowledge/rv_harness.js | node 執行 | 44 PASS＋ALL ASSERTIONS PASSED |

兩者直接從 repo 的 mindmap.html／review.html 抽 `<script>` eval，不需 /tmp 快取。mm_harness 斷言盤點：SVG 標籤簡體×8、繁體不出現×5、跏趺坐×2、七處徵心存在×1、aria-label×1、detail 面板×5、深連結×3、EBOOK_LINKS×2、chips×2、axioms×4、b-truth×4、chart×3、ladder×7。rv_harness 斷言盤點：資料×4、首渲×8、排程×6、閃卡×5、測驗×11、範圍×3、檔案×7。

重要：harness 讀的是從 html 抽出的腳本——mindmap.html／review.html 改完後直接重跑即可（自抽取版無此陷阱；舊 /tmp 版必須先重新 extract）。

### 6.4 生成器慣例（books_knowledge／session_knowledge）

- 單一真相來源：mindmap.html（名詞資料）／SESSION_KNOWLEDGE.md（本知識庫）。
- 生成頁勿手改：改來源後重跑生成器。
- 生成後自檢：免責聲明、lang-switch、canonical、卡數／連結數、區塊數；任一失敗即 exit 1。
- 歸書標記：BOOKS[].marks＝src 內可辨認該書的字串；任何名詞對不到書時 build 失敗（資料完整性檢查，不要放寬成 warning）。

### 6.5 防護性引擎設計

mindmap 引擎的 renderLadder 開頭有 `if (!host) return;`——引擎拷貝到無 `#mm-ladder` 區塊的頁面（如 wenda2_mindmap.html）時安全 no-op。任何新增渲染函式都比照：先查元素存在再動作。改 mindmap 引擎後需重跑 `tool/wenda2_curation/build/build_mm.py && build_mm2.py` 同步到 wenda2_mindmap.html。

---

## 7. 工程備忘

### 7.1 AGENTS.md 金律摘錄（本 session 相關）

- 規則 7（AI 免責聲明）：`infographic.html`、`mindmap.html`、`wenda2_knowledge.html`、`wenda2_mindmap.html`、`wenda2_knowledge_full.html` 及本次新增的 `review.html`、`books_knowledge.html`、`books_knowledge_full.html`、`session_knowledge.html` 都必須顯示「本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。」
- 規則 8：共用 chrome CSS 在根 `style.css`；跨頁復用的 class 必須在那裡有規則。
- 規則 9：`b-truth` 主幹永遠恰三條（axiom-eternal／axiom-firstthought／axiom-onebody）；出現第四條即為錯誤。

### 7.2 樣式資產

- 既有 `.mm-*`：mm-lead、mm-notice、mm-stats、mm-stat、mm-chips、mm-chip、mm-detail-block、mm-detail-points、mm-detail-quote、mm-quote-mark、mm-detail-src、mm-detail-tag、mm-detail-desc、mm-detail-rel、mm-rel-chip、mm-subtitle。
- 本次新增：`.mm-ladder-*`（mindmap 修行次第線）、`.rv-*`（review 頁）、`.bk-*`（books_knowledge 頁）。
- 設計語言：sakura 調色盤、--line／--line-deep 邊框、--grad-rose 主色、--r-pill／--r-md 圓角、--font-serif 標題。

### 7.3 boot 模式（mindmap 與 review 相同）

`window.tgl_lang.onReady(boot)` ＋ `setTimeout(boot, 3000)` 保底 ＋ `onChange` 重渲。先等 OpenCC 備妥再首渲，避免簡體閃繁體。

### 7.4 導覽慣例（2026-09-17 定案）

- 「圖解」下拉全站統一 7 項：名詞圖解／坐禪與講經名詞心智圖／坐禪與講經重點知識／坐禪與講經知識庫全檔／問答錄2 重點知識／問答錄2 名詞心智圖／問答錄2 知識庫全檔（22 頁＋books_knowledge_full 已同步，含 wenda2_curation 三個模板）。
- 導覽列頂層邏輯順序：首頁／禪師／入門路徑／著作／問答錄 2／圖解 ▾／實修故事／下載資料——認識（首頁→禪師→入門路徑）、兩大系列（著作→問答錄 2）與共用知識工具（圖解）相連、延伸內容（實修故事）、行動（下載）永遠最後。
- `review.html` 刻意不在下拉：探索入口在 mindmap.html footer（名詞複習（閃卡與測驗））、books_knowledge.html 導言與 footer、review.html 自身 footer。
- nav HTML 逐頁手工複製（shared.js 只加行為）；改導覽要逐頁改或用批次腳本。

### 7.5 語言與繁簡

- 頁面內容以 zh-TW 為 SoT；JS 動態輸出經 `T()`（convertTW）轉換；靜態內容由 lang-switch 全頁 OpenCC 轉換。
- harness 以「假簡轉換器」驗證動態輸出已轉換（只映射斷言用到的字）。

### 7.6 修行次第數字（易錯）

初禪＝可集中四小時；二禪＝一點上集中十小時以上。不是三小時、不是八小時（已對照節點 desc 修正過）。

### 7.7 報表檔案

逐批報告原始 JSON（vA_report.json、vB_report.json、nodes.json）存於 /tmp/tgl9/（ephemeral）；其內容已完整濃縮進本文件第 2、3、5 節。/tmp 清除後以本文件為準。

---

## 8. 呈現格式調查結論

### 8.1 調查要點

- 主動回憶（retrieval practice）的記憶效果優於被動重讀——心智圖與電子書是「讀」，需要「回想」的工具。
- 間隔重複（spaced repetition）：Leitner 六箱制，間隔 0／1／2／4／7／15 天；「忘了」十分鐘後重考。
- 測驗誘答優先取同主幹名詞（區分「概念混淆」而非隨機干擾）。
- 修行次第線＝進度地圖：把攤開的名詞收回成一條路（實修 16 級＋義理 7 步）。
- 按書分冊的知識頁：給「想從某一本書切入」的讀者。

### 8.2 建議 → 落地對照

| 建議 | 產出 | 狀態 |
|---|---|---|
| 閃卡＋測驗同頁 | review.html | 已落地 |
| 修行次第線 | mindmap.html 新區塊 | 已落地 |
| 對比卡／跨書對照 | books_knowledge.html（按書分冊＋跨書名詞重複可見） | 已落地 |
| 未來：wenda2 57 節點接同一引擎 | review.html 的 `window.tgl_review` API 已開放 | 待接入 |

---

## 9. 回歸基準（驗收指令）

```sh
node tool/session_knowledge/mm_harness.js    # 47 PASS + ALL ASSERTIONS PASSED
node tool/session_knowledge/rv_harness.js    # 44 PASS + ALL ASSERTIONS PASSED
node tool/books_knowledge/build.js           # 91 卡、91 深連結、9 書區塊
node tool/books_knowledge/build_full.js      # 64 名詞全檔、分布表 64 列、高頻詞表 12 列、書冊概覽 9 列
node --check（改 mindmap.html／review.html 內嵌腳本後先跑）
```

wenda2 同步（改 mindmap 引擎後）：

```sh
cd tool/wenda2_curation/build && python3 build_mm.py && python3 build_mm2.py
```

檔案級檢查：三個新頁都有 AI 免責聲明與 canonical；sitemap.xml 含四個新 URL；22 頁下拉含「坐禪與講經重點知識」「坐禪與講經知識庫全檔」且不含「名詞複習」。

---

## 10. 落地清單（2026-09-16 至 09-17）

| 檔案 | 內容 | 性質 |
|---|---|---|
| review.html | 間隔重複閃卡＋名詞測驗（SRS localStorage、深連結、繁簡、免責） | 手編（inline 資料 73 節點） |
| mindmap.html | 73 節點查證＋深連結＋修行次第線區塊＋footer 連結 | 手編（已存在檔案） |
| books_knowledge.html | 坐禪與講經重點知識（9 書區塊、91 名詞卡） | 生成（tool/books_knowledge/build.js） |
| style.css | .rv-*、.bk-*、.mm-ladder-* 樣式 | 手編 |
| tool/books_knowledge/ | build.js＋README.md | 新工具 |
| tool/session_knowledge/ | build.py＋mm_harness.js＋rv_harness.js＋本 md | 新工具 |
| tool/wenda2_curation/build/*.py | 三個模板下拉加「坐禪與講經重點知識」 | 模板修補 |
| wenda2_knowledge.html、wenda2_mindmap.html、wenda2_knowledge_full.html | 重跑生成（nav 同步） | 生成 |
| 22 頁導覽下拉 | 「坐禪與講經重點知識」加入、「名詞複習」移除 | 手編批次 |
| sitemap.xml | review／books_knowledge／session_knowledge 三個 URL | 手編 |
| SESSION_KNOWLEDGE.md | 本知識庫（SoT） | 手編 |

全部未 commit：由使用者 review 後 push main 佈署（GitHub Pages 無建置步驟）。
