#!/usr/bin/env node
/* 九書重點知識頁生成器（tool/books_knowledge/build.js）
 *
 * 單一真相來源：mindmap.html 內嵌、已逐點查證的節點資料（ROOT / BRANCHES / EBOOK_LINKS）。
 * 本腳本抽取該資料，按「書」重新組織，生成全靜態的 books_knowledge.html：
 *   - 每本書一個區塊：書名、電子書連結、一段簡介、該書相關名詞的展開卡（釋義／書中要點／原文摘句＋深連結）。
 *   - 頁面無 inline JS：繁簡轉換交給 lang-switch.js 全頁處理。
 *   - 名詞歸書規則：節點 src 含該書書名（或其完整講經系列書名變體）即列入；一個名詞可同時出現在多本書。
 *
 * 用法：在 repo 根目錄執行  node tool/books_knowledge/build.js
 * 改了 mindmap.html 的名詞資料後，重跑本腳本即可同步本頁。
 */
'use strict';

var fs = require('fs');
var path = require('path');

var ROOT_DIR = path.resolve(__dirname, '..', '..');
var MM_PATH = path.join(ROOT_DIR, 'mindmap.html');
var OUT_PATH = path.join(ROOT_DIR, 'books_knowledge.html');

/* ---------------- 從 mindmap.html 抽取資料 ---------------- */

var MM = fs.readFileSync(MM_PATH, 'utf-8');
var a = MM.indexOf('<script>');                      /* 第一個無屬性 <script> = 內嵌主腳本 */
var b = MM.indexOf('</script>', a);
var script = MM.slice(a + 8, b);
var s0 = script.indexOf('var ROOT = {');
var e0 = script.indexOf('/* -------------------------------------------------------- 版面計算');
if (a < 0 || b < 0 || s0 < 0 || e0 < 0) {
    console.error('找不到 mindmap.html 的資料區段，中止。');
    process.exit(1);
}
var D = eval('(function(){' + script.slice(s0, e0) +
            '\nreturn {ROOT:ROOT, BRANCHES:BRANCHES, EBOOK_LINKS:EBOOK_LINKS};})()');

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

/* ---------------- 書目（標記 = src 內可辨認該書的字串） ---------------- */

var BOOKS = [
    { n: '01', title: '《坐禪》（坐禪 1）', file: '01_trad.html',
      intro: '身體工程與禪定次第的教科書：從磕大頭、腹式呼吸、雙盤，經欲界定到四禪，再到阿羅漢；末章講業力與主動消業。',
      marks: ['《坐禪1》'] },
    { n: '02', title: '《坐禪之問答錄》', file: '02_trad.html',
      intro: '24 章實修問答：持戒、磕大頭、呼吸、淫慾、幻覺、消業、極樂世界——修行現場的具體問題與解答。',
      marks: ['《坐禪之問答錄》', '《問答錄》'] },
    { n: '03', title: '《坐禪 2》', file: '03_trad.html',
      intro: '義理總綱：真相、意識、羯磨（業）、起源、設計、職業、其它諸篇——從三大初始設定一路推到業與世界。',
      marks: ['《坐禪2》'] },
    { n: '05', title: '《講金剛經 心經》', file: '05_trad.html',
      intro: '以《金剛經》《心經》層層破執：照見五蘊皆空，一路破到「無智亦無得」；並列出八苦。',
      marks: ['《講金剛經 心經》', '《講心經》', '《講金剛經》', '《TaiGuangLin禪師講金剛經 心經》'] },
    { n: '06', title: '《講圓覺經》', file: '06_trad.html',
      intro: '十二菩薩章。清淨慧菩薩章從佛的視角直說：一切眾生皆有不生不滅的自性。',
      marks: ['《講圓覺經》', '《TaiGuangLin禪師講圓覺經》'] },
    { n: '07', title: '《講四十二章經》', file: '07_trad.html',
      intro: '短小直指的做人與修行入門：二十難、十善十惡、空心管子。',
      marks: ['《講四十二章經》', '《TaiGuangLin禪師講四十二章經》'] },
    { n: '08', title: '《講楞伽經》', file: '08_trad.html',
      intro: '五法三自性、八識二無我、頓淨非頓——菩薩次第與心識結構的細部攤開。',
      marks: ['《講楞伽經》', '《TaiGuangLin禪師講楞伽經》'] },
    { n: '09', title: '《講六祖壇經》', file: '09_trad.html',
      intro: '自性自度、頓悟漸修：惠能把向外求的「真如佛」變成向內的「心性佛」。',
      marks: ['《講六祖壇經》', '《Tai師父講六祖壇經》'] },
    { n: '10', title: '《講楞嚴經》', file: '10_trad.html',
      intro: '意識構造的解剖圖：七處徵心、十番顯見、二種妄見、四科、五十陰魔。',
      marks: ['《講楞嚴經》', '《Tai師父講楞嚴經》'] }
];

/* 完整性檢查：每個名詞都要對到至少一本書 */
var unmatched = LEAVES.filter(function (l) {
    return !BOOKS.some(function (k) { return k.marks.some(function (m) { return l.src.indexOf(m) !== -1; }); });
});
if (unmatched.length) {
    console.error('以下名詞的 src 對不到任何書，請檢查 BOOKS 標記：');
    unmatched.forEach(function (l) { console.error('  ' + l.id + ' | ' + l.src); });
    process.exit(1);
}

/* ---------------- 生成 HTML ---------------- */

function esc(x) {
    return String(x).replace(/&/g, '&').replace(/</g, '<')
                     .replace(/>/g, '>').replace(/"/g, '"');
}

function termHtml(l) {
    var pts = l.p.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('');
    var cite = esc(l.qs);
    if (l.link) {
        cite = '<a href="' + esc(l.link) + '" target="_blank" rel="noopener" title="打開電子書原文">' +
               cite + ' <i aria-hidden="true">📖</i></a>';
    }
    return '<details class="mm-ladder-step bk-term">' +
           '<summary><span class="bk-term-label">' + esc(l.label) + '</span>' +
           '<span class="mm-detail-tag">' + esc(l.branch) + '</span></summary>' +
           '<div class="mm-ladder-body">' +
           '<p class="mm-detail-desc">' + esc(l.d) + '</p>' +
           (pts ? '<div class="mm-detail-block"><h4><i aria-hidden="true">☰</i> 書中要點</h4>' +
                 '<ul class="mm-detail-points">' + pts + '</ul></div>' : '') +
           '<blockquote class="mm-detail-quote">' +
           '<span class="mm-quote-mark" aria-hidden="true">❝</span>' +
           '<p>' + esc(l.q) + '</p><cite>' + cite + '</cite></blockquote>' +
           '<p class="mm-detail-src"><i aria-hidden="true">✦</i> 出處：' + esc(l.src) + '</p>' +
           '</div></details>';
}

var termsByBook = BOOKS.map(function (k) {
    return LEAVES.filter(function (l) {
        return k.marks.some(function (m) { return l.src.indexOf(m) !== -1; });
    });
});

var navHtml = BOOKS.map(function (k, i) {
    return '<a class="bk-nav-item" href="#bk-' + k.n + '">' +
           '<span class="bk-nav-num">' + k.n + '</span>' + k.title.replace(/[《》]/g, '') +
           '<span class="bk-nav-count">' + termsByBook[i].length + '</span></a>';
}).join('');

var sectionsHtml = BOOKS.map(function (k, i) {
    var terms = termsByBook[i];
    var cls = i % 2 === 0 ? 'section' : 'section bg-light';
    return '    <section class="' + cls + '" id="bk-' + k.n + '">\n' +
           '        <div class="container">\n' +
           '            <h2 class="section-title mm-section-title">\n' +
           '                <span class="mm-section-icon" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="7" y="24" width="9" height="12" rx="2" fill="currentColor" opacity=".4"/><rect x="17" y="16" width="9" height="20" rx="2" fill="currentColor" opacity=".65"/><rect x="27" y="7" width="9" height="29" rx="2" fill="currentColor"/></svg></span>\n' +
           '                ' + k.n + ' ' + esc(k.title) + '\n' +
           '                <a class="bk-ebook-link" href="ebook/' + k.file + '" target="_blank" rel="noopener">進入電子書 ↗</a>\n' +
           '            </h2>\n' +
           '            <p class="mm-lead">' + esc(k.intro) + '</p>\n' +
           '            <p class="bk-count">本書收錄 ' + terms.length + ' 個重點名詞</p>\n' +
           '            <div class="mm-ladder">\n' +
           terms.map(termHtml).join('\n') + '\n' +
           '            </div>\n' +
           '        </div>\n' +
           '    </section>';
}).join('\n\n');

var html = '<!DOCTYPE html>\n' +
'<html lang="zh-TW">\n' +
'<head>\n' +
'    <meta charset="UTF-8">\n' +
'    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
'    <title>九書重點知識｜坐禪與講經系列名詞整理｜TaiGuangLin 禪師</title>\n' +
'    <meta name="description" content="TaiGuangLin禪師坐禪與講經系列九本著作（《坐禪》《坐禪之問答錄》《坐禪2》《講金剛經 心經》《講圓覺經》《講四十二章經》《講楞伽經》《講六祖壇經》《講楞嚴經》）的重點知識：每本書的關鍵名詞、釋義、書中要點與原文摘句，每條引句附電子書原文深連結。">\n' +
'    <meta name="keywords" content="重點知識,坐禪,講經,佛法名詞,禪定,妄想,分別,執著,業力,阿羅漢,菩薩,楞嚴經,楞伽經,六祖壇經,四十二章經,金剛經,心經,圓覺經,TaiGuangLin">\n' +
'    <meta name="author" content="TaiGuangLin">\n' +
'    <meta name="robots" content="index, follow">\n' +
'    <meta property="og:title" content="九書重點知識｜TaiGuangLin 禪師">\n' +
'    <meta property="og:description" content="按書分冊整理九本著作的重點名詞：釋義、書中要點與原文摘句，逐句可達電子書原文">\n' +
'    <meta property="og:type" content="website">\n' +
'    <meta property="og:url" content="https://taiguanglin.info/books_knowledge.html">\n' +
'    <meta property="og:image" content="https://taiguanglin.info/images/taiguanglin.png">\n' +
'    <link rel="canonical" href="https://taiguanglin.info/books_knowledge.html">\n' +
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
'                <a href="index.html" class="nav-link">首頁</a>\n' +
'                <a href="index.html#about" class="nav-link">禪師</a>\n' +
'                <a href="index.html#start" class="nav-link">入門路徑</a>\n' +
'                <a href="index.html#books" class="nav-link">著作</a>\n' +
'                <a href="wenda2.html" class="nav-link">問答錄 2</a>\n' +
'                <a href="stories.html" class="nav-link">實修故事</a>\n' +
'                <div class="nav-dropdown is-current" id="nav-dropdown">\n' +
'                    <a href="#" class="nav-link nav-dropdown-toggle active" id="dropdown-toggle" aria-current="true">圖解 ▾</a>\n' +
'                    <div class="nav-dropdown-menu">\n' +
'                        <a href="infographic.html" class="nav-dropdown-item">名詞圖解</a>\n' +
'                        <a href="mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>\n' +
'                        <a href="books_knowledge.html" class="nav-dropdown-item active" aria-current="page">九書重點知識</a>\n' +
'                        <a href="review.html" class="nav-dropdown-item">名詞複習</a>\n' +
'                        <a href="wenda2_knowledge.html" class="nav-dropdown-item">問答錄2 重點知識</a>\n' +
'                        <a href="wenda2_mindmap.html" class="nav-dropdown-item">問答錄2 名詞心智圖</a>\n' +
'                        <a href="wenda2_knowledge_full.html" class="nav-dropdown-item">問答錄2 知識庫全檔</a>\n' +
'                    </div>\n' +
'                </div>\n' +
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
'                <span aria-current="page">九書重點知識</span>\n' +
'            </nav>\n' +
'            <span class="kicker">NINE BOOKS · KEY KNOWLEDGE</span>\n' +
'            <h1 class="display">九書重點知識</h1>\n' +
'            <p class="lede">坐禪系列與講經系列九本著作，按書分冊整理的重點知識：每本書的關鍵名詞、釋義、書中要點與原文摘句。內容全部來自「名詞關聯心智圖」那套已逐點對照原文查證的節點資料，每條引句都可以直達電子書的原文段落。</p>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' +
'    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">\n' +
'        <div class="container">\n' +
'            <div class="note-ai" style="margin-bottom: 20px;">\n' +
'                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>\n' +
'            </div>\n' +
'            <div class="mm-stats">\n' +
'                <div class="mm-stat"><strong>9</strong><span>本著作</span></div>\n' +
'                <div class="mm-stat"><strong>2,892</strong><span>頁原文</span></div>\n' +
'                <div class="mm-stat"><strong>64</strong><span>個重點名詞</span></div>\n' +
'                <div class="mm-stat"><strong>' + LEAVES.filter(function (l) { return l.link; }).length + '</strong><span>條原文深連結</span></div>\n' +
'            </div>\n' +
'            <h2 class="mm-subtitle" style="margin-top: 28px;">全書快速導航</h2>\n' +
'            <div class="bk-nav">\n' + navHtml + '\n            </div>\n' +
'            <p class="mm-lead" style="margin-top: 16px;">《感恩與講經》（電子書第 04 冊）不在這套名詞查證語料內，故未列入。想按「關聯」而不是按「書」讀，請看<a href="mindmap.html">名詞關聯心智圖</a>；想自我測驗記憶，請看<a href="review.html">名詞複習</a>。</p>\n' +
'        </div>\n' +
'    </section>\n' +
'\n' + sectionsHtml + '\n' +
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
'                        <li><a href="mindmap.html">名詞關聯心智圖</a></li>\n' +
'                        <li><a href="books_knowledge.html">九書重點知識（本頁）</a></li>\n' +
'                        <li><a href="review.html">名詞複習</a></li>\n' +
'                        <li><a href="wenda2_knowledge.html">問答錄2 重點知識</a></li>\n' +
'                        <li><a href="wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>\n' +
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

var out = html;
var cardCount = (out.match(/<details class="mm-ladder-step bk-term">/g) || []).length;
var linkCount = (out.match(/href="ebook\/\d{2}_trad\.html#s[0-9a-f]{8}"/g) || []).length;
var expectCards = termsByBook.reduce(function (n, t) { return n + t.length; }, 0);
var checks = [
    ['免責聲明', out.indexOf('本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。') !== -1],
    ['lang-switch.js', out.indexOf('/lang-switch.js') !== -1],
    ['shared.js', out.indexOf('shared.js') !== -1],
    ['canonical', out.indexOf('https://taiguanglin.info/books_knowledge.html"') !== -1],
    ['名詞卡數', cardCount === expectCards],
    ['深連結 ≥ 64', linkCount >= LEAVES.filter(function (l) { return l.link; }).length],
    ['九個書區塊', (out.match(/id="bk-\d{2}"/g) || []).length === 9]
];
var bad = checks.filter(function (c) { return !c[1]; });
if (bad.length) {
    console.error('自檢失敗：', bad.map(function (c) { return c[0]; }).join(', '));
    process.exit(1);
}
console.log('OK  books_knowledge.html 生成：');
termsByBook.forEach(function (t, i) {
    console.log('    ' + BOOKS[i].n + ' ' + BOOKS[i].title + '：' + t.length + ' 詞');
});
console.log('    名詞卡（含跨書重複）共 ' + expectCards + ' 張、深連結 ' + linkCount + ' 條');
