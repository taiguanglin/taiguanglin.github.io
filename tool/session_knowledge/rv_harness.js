/* review.html inline-script 煙霧測試（自抽取版，可直接在 repo 內跑）：
 *  - 從 ../.. /review.html 抽出內嵌 <script> 直接 eval，不需 /tmp 快取。
 *  - 假 DOM + 假 localStorage + 簡體模式，驗證首渲、SRS 排程核心、評分落地與測驗流程。
 * 用法：在 repo 任何位置執行  node tool/session_knowledge/rv_harness.js
 * 期望輸出：44 條 PASS + ALL ASSERTIONS PASSED（詳見 SESSION_KNOWLEDGE.md 第 9 節）。 */
'use strict';
var fs = require('fs');
var path = require('path');

/* ---------- 抽取待測腳本 ---------- */
var RV_PATH = path.resolve(__dirname, '..', '..', 'review.html');
var src = fs.readFileSync(RV_PATH, 'utf-8');
var a = src.indexOf('<script>');
var b = src.indexOf('</script>', a);
if (a < 0 || b < 0) { console.error('找不到 review.html 內嵌腳本'); process.exit(1); }
var RV_FINAL = src.slice(a + 8, b);

/* ---------- 假簡轉換器（只映射斷言用得到的字） ---------- */
var MAP = { '顯':'显','恆':'恒','複':'复','間':'间','閃':'闪','設':'设','詞':'词','測':'测',
            '驗':'验','對':'对','輪':'轮','數':'数','眾':'众','記':'记','強':'强','題':'题','習':'习' };
function cv(s) { return s.replace(/./g, function (c) { return MAP[c] || c; }); }

var readyHandlers = [], domReadyHandlers = [];
var allHTML = {};

function fakeEl(id) {
    return {
        setAttribute: function () {}, appendChild: function (c) { return c; },
        addEventListener: function () {},
        classList: { add: function () {}, remove: function () {}, contains: function () { return false; } },
        querySelectorAll: function () { return []; },
        contains: function () { return false; },
        getAttribute: function () { return null; },
        get innerHTML() { return this._html || ''; },
        set innerHTML(v) { this._html = v; allHTML[id] = v; }
    };
}
global.document = {
    addEventListener: function (ev, fn) { if (ev === 'DOMContentLoaded') domReadyHandlers.push(fn); },
    getElementById: function (id) { return fakeEl(id); }
};
global.localStorage = {
    _m: {},
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(this._m, k) ? this._m[k] : null; },
    setItem: function (k, v) { this._m[k] = String(v); },
    removeItem: function (k) { delete this._m[k]; }
};
global.window = {
    tgl_lang: {
        getVariant: function () { return 'simp'; },
        convertTW: function (s) { return cv(String(s)); },
        onReady: function (cb) { readyHandlers.push(cb); },
        onChange: function () {}
    }
};
global.setTimeout = function () {};

/* ---------- 載入待測腳本 ---------- */
eval(RV_FINAL);

if (domReadyHandlers.length !== 1) throw new Error('DOMContentLoaded handler 數量不對: ' + domReadyHandlers.length);
domReadyHandlers[0]();
if (readyHandlers.length !== 1) throw new Error('onReady 未註冊: ' + readyHandlers.length);
readyHandlers[0]();

var R = window.tgl_review;
var failed = 0;
function expect(label, cond, extra) {
    if (cond) console.log('PASS  ' + label);
    else { failed++; console.log('FAIL  ' + label + (extra ? '  << ' + extra + ' >>' : '')); }
}

/* ---------- 1. 資料 ---------- */
expect('64 個葉節點', R.leaves.length === 64, String(R.leaves.length));
expect('8 個主幹', R.branches.length === 8, String(R.branches.length));
expect('73 條深連結', Object.keys(R.links).length === 73, String(Object.keys(R.links).length));
expect('連結格式 ebook/XX_trad.html#sXXXXXXXX', /^ebook\/\d{2}_trad\.html#s[0-9a-f]{8}$/.test(R.links['axiom-eternal']), R.links['axiom-eternal']);

/* ---------- 2. 首渲（簡體） ---------- */
var panel = allHTML['rv-panel'] || '';
expect('首卡 axiom-eternal「自性恒常」(簡)', panel.indexOf('自性恒常') !== -1);
expect('面板含「显示答案」(簡)', panel.indexOf('显示答案') !== -1);
expect('面板不含繁體「顯示答案」', panel.indexOf('顯示答案') === -1);
var stats = allHTML['rv-stats'] || '';
expect('統計含「今日待复习」(簡)', stats.indexOf('今日待复习') !== -1);
var tabs = allHTML['rv-tabs'] || '';
expect('分頁含「间隔重复闪卡」(簡)', tabs.indexOf('间隔重复闪卡') !== -1);
expect('分頁含「名词测验」(簡)', tabs.indexOf('名词测验') !== -1);
var scope = allHTML['rv-scope'] || '';
expect('範圍 chips 含「三大初始设定」(簡)', scope.indexOf('三大初始设定') !== -1);
expect('範圍 chips 恰 9 個（全部+8）', (scope.match(/class="mm-chip/g) || []).length === 9, String((scope.match(/class="mm-chip/g) || []).length));

/* ---------- 3. 排程核心（純函式） ---------- */
expect('nextBox：忘了→箱0', R.nextBox(3, 1) === 0);
expect('nextBox：新卡記得→箱1', R.nextBox(-1, 3) === 1);
expect('nextBox：箱3很熟→箱5', R.nextBox(3, 4) === 5);
expect('nextBox：箱4記得→箱5（封頂）', R.nextBox(4, 3) === 5);
expect('nextBox：勉強不低於箱1', R.nextBox(0, 2) === 1);

var now = Date.now();
var srs = {};
R.leaves.forEach(function (l, i) { if (i % 7 === 0) srs[l.id] = { box: 2, due: now + 1000 * (10 - i) }; });
var minDue = Math.min.apply(null, Object.keys(srs).map(function (k) { return srs[k].due; }));
var nxt = R.pickNextCard('all', srs, now + 100000);
expect('pickNextCard 取最小 due 的到期卡', !!nxt && srs[nxt.id] && srs[nxt.id].due === minDue, nxt && nxt.id);

/* ---------- 4. 閃卡翻面與評分落地 ---------- */
R.reveal();
var panel2 = allHTML['rv-panel'] || '';
expect('翻面後含釋義（一切众…簡）', panel2.indexOf('一切众') !== -1);
expect('翻面後含原文深連結', panel2.indexOf('href="ebook/') !== -1);
expect('翻面後含自評按鈕「记得」(簡)', panel2.indexOf('记得') !== -1);
R.rate(3);
var saved = JSON.parse(global.localStorage.getItem('tgl-review-srs-v1') || '{}');
expect('評分後 localStorage 已存檔（箱1）', !!saved['axiom-eternal'] && saved['axiom-eternal'].box === 1);
expect('評分後換下一張卡', R.state.curId && R.state.curId !== 'axiom-eternal', R.state.curId);

/* ---------- 5. 測驗 ---------- */
R.setMode('quiz');
expect('測驗自動建 10 題', R.state.quiz && R.state.quiz.length === 10, R.state.quiz && String(R.state.quiz.length));
var q0 = R.state.quiz[0];
expect('每題 4 個選項', q0.options.length === 4, String(q0.options.length));
expect('選項含正解', q0.options.some(function (o) { return o.id === q0.target.id; }));
expect('選項 id 不重複', new Set(q0.options.map(function (o) { return o.id; })).size === 4);
var samePool = R.leaves.filter(function (l) { return l.b === q0.target.b && l.id !== q0.target.id; });
expect('誘答優先同主幹', q0.options.filter(function (o) { return o.b === q0.target.b && o.id !== q0.target.id; }).length === Math.min(3, samePool.length));

R.pickOption(q0.target.id);
expect('答對計分 1', R.state.qScore === 1, String(R.state.qScore));
expect('回饋含「答对了」(簡)', (allHTML['rv-panel'] || '').indexOf('答对了') !== -1);
R.quizNext();
expect('進入第 2 題', R.state.qi === 1 && R.state.qPicked === null);

var n = R.state.quiz.length;
while (R.state.qi < n) {
    R.pickOption(R.state.quiz[R.state.qi].target.id);
    R.quizNext();
}
var res = allHTML['rv-panel'] || '';
expect('結果頁含「本轮得分」(簡)', res.indexOf('本轮得分') !== -1);
expect('全對顯示「全数答对」(簡)', res.indexOf('全数答对') !== -1);
expect('全對無錯題列表', res.indexOf('rv-result-wrongs') === -1, res.slice(0, 120));

/* ---------- 6. 範圍切換 ---------- */
R.setMode('cards');
R.setScope('b-truth');
expect('b-truth 範圍首卡 axiom-firstthought', R.state.curId === 'axiom-firstthought', R.state.curId);
var sc2 = allHTML['rv-scope'] || '';
expect('b-truth chip 標記 is-active', sc2.indexOf('mm-chip is-active" data-id="b-truth"') !== -1);
R.setMode('quiz');
expect('b-truth 測驗 3 題', R.state.quiz && R.state.quiz.length === 3, R.state.quiz && String(R.state.quiz.length));

/* ---------- 7. 頁面檔案級檢查 ---------- */
expect('含 lang-switch.js', src.indexOf('/lang-switch.js') !== -1);
expect('含 AI 免責聲明', src.indexOf('本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。') !== -1);
expect('含 shared.js', src.indexOf('shared.js') !== -1);
expect('含 canonical review.html', src.indexOf('https://taiguanglin.info/review.html"') !== -1);
expect('無未注入的佔位符', src.indexOf('__BRANCHES__') === -1 && src.indexOf('__LEAVES__') === -1 && src.indexOf('__LINKS__') === -1);
expect('頁面內 73 條 ebook 連結', (src.match(/:"ebook\/\d{2}_trad\.html#s[0-9a-f]{8}"/g) || []).length === 73, String((src.match(/:"ebook\/\d{2}_trad\.html#s[0-9a-f]{8}"/g) || []).length));
expect('導覽含名詞複習連結', src.indexOf('href="review.html"') !== -1);

console.log(failed === 0 ? '\nALL ASSERTIONS PASSED' : '\n' + failed + ' FAILED');
process.exit(failed === 0 ? 0 : 1);
