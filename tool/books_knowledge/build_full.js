#!/usr/bin/env node
/* 坐禪與講經知識庫全檔生成器（tool/books_knowledge/build_full.js）
 *
 * 單一真相來源：mindmap.html 內嵌、已逐點查證的節點資料（ROOT / BRANCHES / EBOOK_LINKS）
 * 與圖表資料（BOOKS 書序 + TERM_COUNTS 高頻詞全文出現次數）。
 * 比照 wenda2_knowledge_full.html（問答錄2 知識庫全檔）的結構，生成全靜態 books_knowledge_full.html：
 *   全檔快速導航 → 一・六十四名詞全檔（按主幹分組）→ 二・名詞書冊分布總表 → 三・九書書冊概覽 → 四・本檔資料怎麼來的
 *
 * 用法：在 repo 根目錄執行  node tool/books_knowledge/build_full.js
 * 改了 mindmap.html 的名詞／圖表資料後，重跑本腳本即可同步。
 */
'use strict';

var fs = require('fs');
var path = require('path');

var ROOT_DIR = path.resolve(__dirname, '..', '..');
var MM_PATH = path.join(ROOT_DIR, 'mindmap.html');
var OUT_PATH = path.join(ROOT_DIR, 'books_knowledge_full.html');

/* ---------------- 從 mindmap.html 抽取資料 ---------------- */

var MM = fs.readFileSync(MM_PATH, 'utf-8');
var a = MM.indexOf('<script>');
var b = MM.indexOf('</script>', a);
var script = MM.slice(a + 8, b);

var s0 = script.indexOf('var ROOT = {');
var e0 = script.indexOf('/* -------------------------------------------------------- 版面計算');
var s1 = script.indexOf('var BOOKS = [');
var e1 = script.indexOf('];', script.indexOf('var TERM_COUNTS = ['));
if (a < 0 || b < 0 || s0 < 0 || e0 < 0 || s1 < 0 || e1 < 0) {
    console.error('找不到 mindmap.html 的資料區段，中止。');
    process.exit(1);
}
var D = eval('(function(){' + script.slice(s0, e0) +
            '\nreturn {ROOT:ROOT, BRANCHES:BRANCHES, EBOOK_LINKS:EBOOK_LINKS};})()');
var CHART = eval('(function(){' + script.slice(s1, e1 + 2) +
            '\nreturn {BOOKS:BOOKS, TERM_COUNTS:TERM_COUNTS};})()');

var BRANCH_LABEL = {};
var LEAVES = [];
D.BRANCHES.forEach(function (br) {
    BRANCH_LABEL[br.id] = br.label;
    br.leaves.forEach(function (l) {
        LEAVES.push({
            id: l.id, label: l.label, branch: br.label,
            d: l.desc, p: l.points || [], q: l.quote.t, qs: l.quote.s,
            src: l.src, link: D.EBOOK_LINKS[l.id] || ''
        });
    });
});

/* ---------------- 書目標記（與 build.js 同一組規則） ---------------- */

var BOOKS = [
    { n: '01', title: '《坐禪》（坐禪 1）', file: '01_trad.html', chart: '坐禪1',
      intro: '身體工程與禪定次第的教科書：從磕大頭、腹式呼吸、雙盤，經欲界定到四禪，再到阿羅漢；末章講業力與主動消業。',
      marks: ['《坐禪1》'] },
    { n: '02', title: '《坐禪之問答錄》', file: '02_trad.html', chart: '坐禪之問答錄',
      intro: '24 章實修問答：持戒、磕大頭、呼吸、淫慾、幻覺、消業、極樂世界——修行現場的具體問題與解答。',
      marks: ['《坐禪之問答錄》', '《問答錄》'] },
    { n: '03', title: '《坐禪 2》', file: '03_trad.html', chart: '坐禪2',
      intro: '義理總綱：真相、意識、羯磨（業）、起源、設計、職業、其它諸篇——從三大初始設定一路推到業與世界。',
      marks: ['《坐禪2》'] },
    { n: '05', title: '《講金剛經 心經》', file: '05_trad.html', chart: '講金剛經 心經',
      intro: '以《金剛經》《心經》層層破執：照見五蘊皆空，一路破到「無智亦無得」；並列出八苦。',
      marks: ['《講金剛經 心經》', '《講心經》', '《講金剛經》', '《TaiGuangLin禪師講金剛經 心經》'] },
    { n: '06', title: '《講圓覺經》', file: '06_trad.html', chart: '講圓覺經',
      intro: '十二菩薩章。清淨慧菩薩章從佛的視角直說：一切眾生皆有不生不滅的自性。',
      marks: ['《講圓覺經》', '《TaiGuangLin禪師講圓覺經》'] },
    { n: '07', title: '《講四十二章經》', file: '07_trad.html', chart: '講四十二章經',
      intro: '短小直指的做人與修行入門：二十難、十善十惡、空心管子。',
      marks: ['《講四十二章經》', '《TaiGuangLin禪師講四十二章經》'] },
    { n: '08', title: '《講楞伽經》', file: '08_trad.html', chart: '講楞伽經',
      intro: '五法三自性、八識二無我、頓淨非頓——菩薩次第與心識結構的細部攤開。',
      marks: ['《講楞伽經》', '《TaiGuangLin禪師講楞伽經》'] },
    { n: '09', title: '《講六祖壇經》', file: '09_trad.html', chart: '講六祖壇經',
      intro: '自性自度、頓悟漸修：惠能把向外求的「真如佛」變成向內的「心性佛」。',
      marks: ['《講六祖壇經》', '《Tai師父講六祖壇經》'] },
    { n: '10', title: '《講楞嚴經》', file: '10_trad.html', chart: '講楞嚴經',
      intro: '意識構造的解剖圖：七處徵心、十番顯見、二種妄見、四科、五十陰魔。',
      marks: ['《講楞嚴經》', '《Tai師父講楞嚴經》'] }
];

var unmatched = LEAVES.filter(function (l) {
    return !BOOKS.some(function (k) { return k.marks.some(function (m) { return l.src.indexOf(m) !== -1; }); });
});
if (unmatched.length) {
    console.error('以下名詞的 src 對不到任何書，請檢查 BOOKS 標記：');
    unmatched.forEach(function (l) { console.error('  ' + l.id + ' | ' + l.src); });
    process.exit(1);
}

function booksOf(l) {
    return BOOKS.filter(function (k) { return k.marks.some(function (m) { return l.src.indexOf(m) !== -1; }); });
}

/* ---------------- 生成 HTML ---------------- */

function esc(x) {
    return String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                     .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function termCard(l) {
    var pts = l.p.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('');
    var cite = esc(l.qs);
    if (l.link) {
        cite = '<a href="' + esc(l.link) + '" target="_blank" rel="noopener" title="打開電子書原文">' +
               cite + ' <i aria-hidden="true">📖</i></a>';
    }
    var bks = booksOf(l).map(function (k) { return k.title.replace(/[《》]/g, ''); }).join('、');
    return '<details class="mm-ladder-step">' +
           '<summary><span class="mm-ladder-label">' + esc(l.label) + '</span>' +
           '<span class="mm-detail-tag">' + esc(l.branch) + '</span></summary>' +
           '<div class="mm-ladder-body">' +
           '<p class="mm-detail-desc">' + esc(l.d) + '</p>' +
           (pts ? '<div class="mm-detail-block"><h4><i aria-hidden="true">☰</i> 書中要點</h4>' +
                 '<ul class="mm-detail-points">' + pts + '</ul></div>' : '') +
           '<blockquote class="mm-detail-quote">' +
           '<span class="mm-quote-mark" aria-hidden="true">❝</span>' +
           '<p>' + esc(l.q) + '</p><cite>' + cite + '</cite></blockquote>' +
           '<p class="mm-detail-src"><i aria-hidden="true">✦</i> 出處：' + esc(l.src) + '</p>' +
           '<p class="bk-count">相關書冊：' + esc(bks) + '</p>' +
           '</div></details>';
}

/* 一・六十四名詞全檔：按主幹分組 */
var part1 = '';
D.BRANCHES.forEach(function (br) {
    var terms = LEAVES.filter(function (l) { return l.branch === br.label; });
    if (!terms.length) return;
    part1 += '<h3 class="mm-subtitle">' + esc(br.label) + '（' + terms.length + '）</h3>' +
             '<div class="mm-ladder">' +
             terms.map(termCard).join('') +
             '</div>';
});

/* 二・名詞書冊分布總表 */
var tableA = LEAVES.map(function (l) {
    var bks = booksOf(l);
    return '<tr><td>' + esc(l.label) + '</td><td>' + esc(l.branch) + '</td><td>' +
           bks.map(function (k) { return k.title.replace(/[《》]/g, ''); }).join('、') + '</td><td>' +
           bks.length + '</td></tr>';
}).join('');
var tableB = CHART.TERM_COUNTS.map(function (r) {
    var total = r.data.reduce(function (x, y) { return x + y; }, 0);
    return '<tr><td>' + esc(r.term) + '</td><td>' + total.toLocaleString() + '</td><td>' +
           r.data.join('／') + '</td></tr>';
}).join('');

/* 三・九書書冊概覽 */
var termsByBook = BOOKS.map(function (k) {
    return LEAVES.filter(function (l) { return booksOf(l).indexOf(k) !== -1; });
});
var tableC = BOOKS.map(function (k, i) {
    return '<tr><td>' + k.n + '</td><td>' + esc(k.title) + '</td>' +
           '<td><a href="ebook/' + k.file + '" target="_blank" rel="noopener"> ebook/' + k.file + ' ↗</a></td>' +
           '<td>' + termsByBook[i].length + '</td><td>' + esc(k.intro) + '</td></tr>';
}).join('');

var NAV_BEFORE = [
    ['index.html', '首頁'], ['index.html#about', '禪師'], ['index.html#start', '入門路徑'],
    ['index.html#books', '著作'], ['wenda2.html', '問答錄 2']
];
var NAV_AFTER = [
    ['stories.html', '實修故事']
];
var DROPDOWN = [
    ['infographic.html', '名詞圖解', ''],
    ['mindmap.html', '坐禪與講經名詞心智圖', ''],
    ['books_knowledge.html', '坐禪與講經重點知識', ''],
    ['books_knowledge_full.html', '坐禪與講經知識庫全檔', ''],
    ['wenda2_knowledge.html', '問答錄2 重點知識', ''],
    ['wenda2_mindmap.html', '問答錄2 名詞心智圖', ''],
    ['wenda2_knowledge_full.html', '問答錄2 知識庫全檔', '']
];

var html = '<!DOCTYPE html>\n' +
'<html lang="zh-TW">\n' +
'<head>\n' +
'    <meta charset="UTF-8">\n' +
'    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
'    <title>坐禪與講經知識庫全檔｜TaiGuangLin 禪師</title>\n' +
'    <meta name="description" content="TaiGuangLin禪師坐禪與講經九本著作的知識庫全檔：64 個重點名詞全檔（釋義／書中要點／原文摘句＋深連結）、名詞書冊分布總表、高頻詞全文出現次數、九書書冊概覽。">\n' +
'    <meta name="robots" content="index, follow">\n' +
'    <meta property="og:title" content="坐禪與講經知識庫全檔｜TaiGuangLin 禪師">\n' +
'    <meta property="og:description" content="九本著作的完整知識檔：名詞全檔、書冊分布、高頻詞次數，逐句可達電子書原文">\n' +
'    <meta property="og:type" content="website">\n' +
'    <meta property="og:url" content="https://taiguanglin.info/books_knowledge_full.html">\n' +
'    <link rel="canonical" href="https://taiguanglin.info/books_knowledge_full.html">\n' +
'    <link rel="icon" type="image/x-icon" href="images/favicon.ico">\n' +
'    <link rel="shortcut icon" type="image/x-icon" href="images/favicon.ico">\n' +
'    <link rel="stylesheet" href="style.css">\n' +
'    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">\n' +
'<script src="/lang-switch.js" defer></script>\n' +
'</head>\n' +
'<body>\n' +
'    <nav class="navbar" id="navbar">\n' +
'        <div class="nav-container">\n' +
'            <a href="index.html" class="nav-logo">\n' +
'                <span class="logo-name">TaiGuangLin</span>\n' +
'                <span class="logo-sub">次世代終極佛法</span>\n' +
'            </a>\n' +
'            <div class="nav-menu" id="nav-menu">\n' +
NAV_BEFORE.map(function (it) {
    return '                <a href="' + it[0] + '" class="nav-link">' + it[1] + '</a>\n';
}).join('') +
'                <div class="nav-dropdown is-current" id="nav-dropdown">\n' +
'                    <a href="#" class="nav-link nav-dropdown-toggle active" id="dropdown-toggle" aria-current="true">圖解 ▾</a>\n' +
'                    <div class="nav-dropdown-menu">\n' +
DROPDOWN.map(function (it) {
    var act = it[0] === 'books_knowledge_full.html';
    return '                        <a href="' + it[0] + '" class="nav-dropdown-item' + (act ? ' active" aria-current="page' : '') + '">' + it[1] + '</a>\n';
}).join('') +
'                    </div>\n' +
'                </div>\n' +
NAV_AFTER.map(function (it) {
    return '                <a href="' + it[0] + '" class="nav-link">' + it[1] + '</a>\n';
}).join('') +
'                <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>\n' +
'            </div>\n' +
'            <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">\n' +
'                <span></span><span></span><span></span>\n' +
'            </button>\n' +
'        </div>\n' +
'    </nav>\n' +
'    <div class="site-menu-veil" id="site-menu-veil"></div>\n' +
'\n' +
'    <section class="page-hero">\n' +
'        <div class="container">\n' +
'            <nav class="crumbs" aria-label="位置">\n' +
'                <a href="index.html">首頁</a><span class="crumbs-sep">/</span>\n' +
'                <span aria-current="page">坐禪與講經知識庫全檔</span>\n' +
'            </nav>\n' +
'            <span class="kicker">NINE BOOKS · FULL KNOWLEDGE</span>\n' +
'            <h1 class="display">坐禪與講經知識庫全檔</h1>\n' +
'            <p class="lede">比照「問答錄2 知識庫全檔」，把坐禪與講經九本著作的查證成果存成完整檔：64 個重點名詞全檔（按主幹分組）、名詞書冊分布總表、高頻詞全文出現次數、九書書冊概覽。內容全部來自名詞心智圖那套已逐點對照原文查證的節點資料。</p>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">\n' +
'        <div class="container">\n' +
'            <div class="note-ai" style="margin-bottom: 8px;">\n' +
'                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>\n' +
'            </div>\n' +
'            <div class="mm-stats">\n' +
'                <div class="mm-stat"><strong>9</strong><span>本著作</span></div>\n' +
'                <div class="mm-stat"><strong>2,892</strong><span>頁原文</span></div>\n' +
'                <div class="mm-stat"><strong>64</strong><span>個名詞全檔</span></div>\n' +
'                <div class="mm-stat"><strong>' + LEAVES.filter(function (l) { return l.link; }).length + '</strong><span>條原文深連結</span></div>\n' +
'            </div>\n' +
'            <h2 class="mm-subtitle" style="margin-top: 28px;">全檔快速導航</h2>\n' +
'            <div class="wk-quick wk-quick--4">\n' +
'                <a class="wk-quick-item" href="#part1"><strong>一・六十四名詞全檔</strong><span>按主幹分組的完整名詞記錄</span></a>\n' +
'                <a class="wk-quick-item" href="#part2"><strong>二・名詞書冊分布總表</strong><span>相關書冊與高頻詞出現次數</span></a>\n' +
'                <a class="wk-quick-item" href="#part3"><strong>三・九書書冊概覽</strong><span>每本書的定位與收錄詞數</span></a>\n' +
'                <a class="wk-quick-item" href="#part4"><strong>四・本檔資料怎麼來的</strong><span>查證方法與生成器</span></a>\n' +
'            </div>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section">\n' +
'        <div class="container">\n' +
'            <div class="wk-part-title"><h2 id="part1">一・六十四名詞全檔</h2></div>\n' +
'            <p class="mm-lead">每個名詞一張全檔卡：釋義、書中要點、原文摘句（附電子書深連結）、相關書冊。按八大主幹分組——想按「書」而不是按「概念」讀，請看<a href="books_knowledge.html">坐禪與講經重點知識</a>。</p>\n' +
part1 + '\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section bg-light">\n' +
'        <div class="container">\n' +
'            <div class="wk-part-title"><h2 id="part2">二・名詞書冊分布總表</h2></div>\n' +
'            <h3 class="mm-subtitle">2.1　六十四個查證名詞的相關書冊</h3>\n' +
'            <div class="sk-table-wrap"><table class="sk-table"><thead><tr><th>名詞</th><th>主幹</th><th>相關書冊</th><th>書數</th></tr></thead><tbody>' + tableA + '</tbody></table></div>\n' +
'            <h3 class="mm-subtitle">2.2　高頻詞全文出現次數</h3>\n' +
'            <p class="mm-lead">統計自九本電子書全文（原書 PDF 共 2,892 頁）；次數欄依書序：坐禪1／問答錄／坐禪2／金剛經心經／圓覺經／四十二章經／楞伽經／六祖壇經／楞嚴經。</p>\n' +
'            <div class="sk-table-wrap"><table class="sk-table"><thead><tr><th>詞</th><th>九書合計（次）</th><th>各書次數（次）</th></tr></thead><tbody>' + tableB + '</tbody></table></div>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section">\n' +
'        <div class="container">\n' +
'            <div class="wk-part-title"><h2 id="part3">三・九書書冊概覽</h2></div>\n' +
'            <div class="sk-table-wrap"><table class="sk-table"><thead><tr><th>冊</th><th>書名</th><th>電子書</th><th>收錄名詞</th><th>定位</th></tr></thead><tbody>' + tableC + '</tbody></table></div>\n' +
'            <p class="mm-lead">《感恩與講經》（電子書第 04 冊）不在這套名詞查證語料內，故未列入。</p>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section bg-light">\n' +
'        <div class="container">\n' +
'            <div class="wk-part-title"><h2 id="part4">四・本檔資料怎麼來的</h2></div>\n' +
'            <p class="mm-lead">名詞節點、釋義、書中要點與原文摘句全部來自 <a href="mindmap.html">名詞心智圖</a> 內嵌、已逐點對照九本書原文查證的節點資料（2026-09-16～17 四批次查證：A14／B17／C12／D20，共 63 節點；引句前綴審查 30 節點）。高頻詞次數統計自九本電子書全文。</p>\n' +
'            <p class="mm-lead">本頁由 <code>tool/books_knowledge/build_full.js</code> 生成（生成物勿手改，改 mindmap.html 資料後重跑即可同步）。名詞對不到書時生成器會直接失敗——這是資料完整性檢查。回歸驗證：<code>node tool/session_knowledge/mm_harness.js</code>（47 斷言）。</p>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <footer class="footer">\n' +
'        <div class="container">\n' +
'            <div class="footer-top">\n' +
'                <div class="footer-brand">\n' +
'                    <div class="logo-name">TaiGuangLin</div>\n' +
'                    <p>次世代終極版佛法</p>\n' +
'                    <p>用現代通俗易懂的語言，傳承純正佛法智慧。</p>\n' +
'                </div>\n' +
'                <div class="footer-col">\n' +
'                    <h4>著作與電子書</h4>\n' +
'                    <ul>\n' +
'                        <li><a href="index.html#books">全部著作</a></li>\n' +
'                        <li><a href="ebook/index_trad.html" target="_blank" rel="noopener noreferrer">坐禪系列電子書</a></li>\n' +
'                    </ul>\n' +
'                </div>\n' +
'                <div class="footer-col">\n' +
'                    <h4>問答錄2</h4>\n' +
'                    <ul>\n' +
'                        <li><a href="wenda2.html">主題目錄（12 章）</a></li>\n' +
'                        <li><a href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">完整電子書</a></li>\n' +
'                    </ul>\n' +
'                </div>\n' +
'                <div class="footer-col">\n' +
'                    <h4>更多資源</h4>\n' +
'                    <ul>\n' +
'                        <li><a href="infographic.html">名詞圖解</a></li>\n' +
'                        <li><a href="mindmap.html">坐禪與講經名詞心智圖</a></li>\n' +
'                        <li><a href="books_knowledge.html">坐禪與講經重點知識</a></li>\n' +
'                        <li><a href="books_knowledge_full.html">坐禪與講經知識庫全檔（本頁）</a></li>\n' +
'                        <li><a href="review.html">名詞複習（閃卡與測驗）</a></li>\n' +
'                        <li><a href="wenda2_knowledge.html">問答錄2 重點知識</a></li>\n' +
'                        <li><a href="wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>\n' +
'                        <li><a href="wenda2_knowledge_full.html">問答錄2 知識庫全檔</a></li>\n' +
'                        <li><a href="stories.html">實修故事</a></li>\n' +
'                        <li><a href="index.html#downloads">資料下載</a></li>\n' +
'                    </ul>\n' +
'                </div>\n' +
'            </div>\n' +
'            <div class="footer-bottom">\n' +
'                <p>歡迎分享給更多人結法緣</p>\n' +
'                <p>願一切眾生離苦得樂，早證菩提</p>\n' +
'            </div>\n' +
'        </div>\n' +
'    </footer>\n' +
'\n' +
'    <script src="shared.js" defer></script>\n' +
'</body>\n' +
'</html>\n';

fs.writeFileSync(OUT_PATH, html);

/* ---------------- 生成後自檢 ---------------- */

var cardCount = (html.match(/<details class="mm-ladder-step">/g) || []).length;
var checks = [
    ['免責聲明', html.indexOf('本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。') !== -1],
    ['lang-switch.js', html.indexOf('/lang-switch.js') !== -1],
    ['canonical', html.indexOf('https://taiguanglin.info/books_knowledge_full.html"') !== -1],
    ['名詞全檔 64 卡', cardCount === 64],
    ['分布總表 64 列', (tableA.match(/<tr>/g) || []).length === 64],
    ['高頻詞表 12 列', (tableB.match(/<tr>/g) || []).length === 12],
    ['書冊概覽 9 列', (tableC.match(/<tr>/g) || []).length === 9],
    ['四個 part 錨點', (html.match(/id="part\d"/g) || []).length === 4],
    ['八個主幹分組', (part1.match(/<h3 class="mm-subtitle">/g) || []).length === 8]
];
var bad = checks.filter(function (c) { return !c[1]; });
if (bad.length) {
    console.error('自檢失敗：', bad.map(function (c) { return c[0]; }).join(', '));
    process.exit(1);
}
console.log('OK  books_knowledge_full.html 生成：64 名詞全檔、分布表 64 列、高頻詞表 12 列、書冊概覽 9 列');
BOOKS.forEach(function (k, i) {
    console.log('    ' + k.n + ' ' + k.title + '：' + termsByBook[i].length + ' 詞');
});
