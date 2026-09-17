/* mindmap.html inline-script 煙霧測試（自抽取版，可直接在 repo 內跑）：
 *  - 從 ../.. /mindmap.html 抽出內嵌 <script> 直接 eval，不需 /tmp 快取。
 *  - 模擬 tgl_lang（簡體模式）+ 假 DOM，驗證 boot 後所有動態輸出已是簡體。
 * 用法：在 repo 任何位置執行  node tool/session_knowledge/mm_harness.js
 * 期望輸出：47 條 PASS + ALL ASSERTIONS PASSED（詳見 SESSION_KNOWLEDGE.md 第 9 節）。 */
'use strict';
var fs = require('fs');
var path = require('path');

/* ---------- 抽取待測腳本 ---------- */
var MM_PATH = path.resolve(__dirname, '..', '..', 'mindmap.html');
var src = fs.readFileSync(MM_PATH, 'utf-8');
var a = src.indexOf('<script>');
var b = src.indexOf('</script>', a);
if (a < 0 || b < 0) { console.error('找不到 mindmap.html 內嵌腳本'); process.exit(1); }
var MM_FINAL = src.slice(a + 8, b);

/* ---------- 假簡轉換器（只映射斷言用得到的字） ---------- */
var MAP = { '設':'设','識':'识','層':'层','經':'经','據':'据','禪':'禅','階':'阶','實':'实',
    '業':'业','與':'与','恆':'恒','無':'无','諸':'诸','體':'体','剛':'刚','計':'计','現':'现',
    '數':'数','書':'书','師':'师','圖':'图','錄':'录','點':'点','雙':'双','盤':'盘','關':'关','開':'开','電':'电',
    '鍵':'键','詞':'词','要':'要','名':'名','相':'相','本':'本','空':'空' };
function cv(s) { return s.replace(/./g, function (c) { return MAP[c] || c; }); }

var readyHandlers = [], changeHandlers = [], domReadyHandlers = [];
var capturedText = [], allInnerHTML = {}, svgAttrs = null;

/* ---------- 假 DOM ---------- */
function fakeEl(tag) {
    return {
        tag: tag, children: [], attributes: {}, childNodes: [],
        nodeType: 1,
        setAttribute: function (k, v) { this.attributes[k] = v; },
        appendChild: function (c) { this.children.push(c); return c; },
        addEventListener: function () {},
        classList: { add: function(){}, remove: function(){}, contains: function(){ return false; } },
        querySelectorAll: function () { return []; },
        contains: function () { return false; },
        getAttribute: function () { return null; },
        get innerHTML() { return this._html || ''; },
        set innerHTML(v) { this._html = v; allInnerHTML[this._id || this.tag] = v; }
    };
}
global.document = {
    addEventListener: function (ev, fn) { if (ev === 'DOMContentLoaded') domReadyHandlers.push(fn); },
    getElementById: function (id) {
        var e = fakeEl('host#' + id); e._id = id;
        e.appendChild = function (c) { this.children.push(c); return c; };
        return e;
    },
    createElementNS: function (ns, name) {
        var e = fakeEl(name);
        if (name === 'svg') svgAttrs = e;   // 記錄根 svg 的屬性（aria-label）
        return e;
    },
    createTextNode: function (v) { capturedText.push(String(v)); return { nodeType: 3, value: v }; },
    importNode: function (n) { return n; }
};
global.DOMParser = function () {
    this.parseFromString = function () { return { documentElement: { childNodes: [] } }; };
};
global.window = {
    tgl_lang: {
        getVariant: function () { return 'simp'; },
        convertTW: function (s) { return cv(String(s)); },
        onReady: function (cb) { readyHandlers.push(cb); },
        onChange: function (cb) { changeHandlers.push(cb); }
    }
};
global.setTimeout = function () { /* 不排程 3 秒保底，避免測試掛起 */ };

/* ---------- 載入待測腳本 ---------- */
eval(MM_FINAL);

/* ---------- 模擬瀏覽器時序 ---------- */
if (domReadyHandlers.length !== 1) throw new Error('DOMContentLoaded handler 數量不對: ' + domReadyHandlers.length);
domReadyHandlers[0]();            // 頁面 DOMContentLoaded → 註冊 onReady(boot)
if (readyHandlers.length !== 1) throw new Error('onReady 未註冊: ' + readyHandlers.length);
readyHandlers[0]();              // lang-switch 轉換完成 → boot 首渲

/* ---------- 斷言 ---------- */
var svgText = capturedText.join('|');
var failed = 0;
function expect(label, cond, extra) {
    if (cond) console.log('PASS  ' + label);
    else { failed++; console.log('FAIL  ' + label + (extra ? '  << ' + extra + ' >>' : '')); }
}

/* 1. SVG 分支標籤全部已是簡體 */
['三大初始设定','意识三层','果位次第','经典依据','三界二十八天','禅定阶梯','实修工程','业与世界']
    .forEach(function (s) { expect('SVG 標籤含「' + s + '」', svgText.indexOf(s) !== -1); });
/* 2. 對應繁體原文不得出現在渲染輸出 */
['三大初始設定','經典依據','禪定階梯','實修工程','業與世界'].forEach(function (s) {
    expect('SVG 標籤不含繁體「' + s + '」', svgText.indexOf(s) === -1);
});
/* 3. 葉節點標籤：跏趺坐（双盘） */
expect('SVG 含「跏趺坐（双盘）」', svgText.indexOf('跏趺坐（双盘）') !== -1);
expect('SVG 不含「跏趺坐（雙盤）」', svgText.indexOf('跏趺坐（雙盤）') === -1);
/* 4. 名相本空已不在三大初始設定（在經典依據），七處徵心仍在 */
expect('SVG 含「七處徵心」→ 位置由分組決定（仍存在）', svgText.indexOf('七處徵心') !== -1);
/* 5. svg 根 aria-label 已轉換 */
expect('svg aria-label 簡體', svgAttrs && /禅师九本著作关键名词心智图/.test(svgAttrs.attributes['aria-label'] || ''), svgAttrs && svgAttrs.attributes['aria-label']);
/* 6. 詳情面板：中心 + 简体文案 */
var det = allInnerHTML['mm-detail'] || '';
expect('detail 含「中心」標籤', det.indexOf('中心') !== -1);
expect('detail 含簡體「书中要点」', det.indexOf('书中要点') !== -1);
expect('detail 不含繁體「書中要點」', det.indexOf('書中要點') === -1);
expect('detail 含 ROOT desc 簡體「九本书」', det.indexOf('九本书') !== -1);
expect('detail 不含繁體「九本書」', det.indexOf('九本書') === -1);
/* 6b. 原文引用深層連結 */
expect('detail 引用含 root 的 ebook 連結', det.indexOf('href="ebook/03_trad.html#s73f07fff"') !== -1, det.slice(0,120));
expect('detail 連結含書籤圖示', det.indexOf('📖') !== -1);
expect('detail 連結 title 已簡轉', det.indexOf('打开电子书原文') !== -1);
(function () {
    var m = MM_FINAL.match(/': 'ebook\/[0-9]{2}_trad\.html#s[0-9a-f]{8}',/g) || [];
    expect('EBOOK_LINKS 恰 73 條且格式正確', m.length === 73, String(m.length));
    expect('EBOOK_LINKS 鍵含連字號節點（axiom-emptyname）', MM_FINAL.indexOf("'axiom-emptyname': 'ebook/") !== -1);
})();
/* 7. chips */
var chips = allInnerHTML['mm-chips'] || '';
expect('chips 含「经典依据」', chips.indexOf('经典依据') !== -1);
expect('chips 不含「經典依據」', chips.indexOf('經典依據') === -1);
/* 8. 公理卡 = 恰好三條初始設定，名相本空不在其中 */
var ax = allInnerHTML['mm-axioms'] || '';
['自性恒常','初妄无因','诸佛同体'].forEach(function (s) { expect('axioms 含「' + s + '」', ax.indexOf(s) !== -1); });
expect('axioms 不含「名相本空」', ax.indexOf('名相本空') === -1);
/* 8b. 三大初始設定固定三條：公理卡不得出現楞嚴內容 */
expect('axioms 不含「七處徵心」', ax.indexOf('七處徵心') === -1);
expect('axioms 不含「十番顯見」', ax.indexOf('十番顯見') === -1);
(function () {
    var seg = MM_FINAL.slice(MM_FINAL.indexOf("id: 'b-truth'"), MM_FINAL.indexOf("id: 'b-mind'"));
    var n = (seg.match(/\{ id: 'axiom-/g) || []).length;
    expect('b-truth 資料恰三條初始設定', n === 3, String(n));
    var pJ = MM_FINAL.indexOf("id: 'sutra-lengyan-jiang'"), pQ = MM_FINAL.indexOf("id: 'qichu-zhengxin'"), pZ = MM_FINAL.indexOf("id: 'sutra-lengyan',");
    expect('七處徵心已移入 b-sutra（楞嚴叢集）', pJ > -1 && pQ > pJ && pZ > pQ, [pJ,pQ,pZ].join(','));
})();
/* 9. 圖表 */
var chart = allInnerHTML['mm-chart'] || '';
expect('chart legend 含「坐禅1」', chart.indexOf('坐禅1') !== -1);
expect('chart 不含「坐禪1」', chart.indexOf('坐禪1') === -1);
expect('chart 軸標簡體', chart.indexOf('九书合计出现次数（次）') !== -1);
/* 10. onChange（切回繁體）重算版面不炸 */
global.window.tgl_lang.getVariant = function () { return 'trad'; };
changeHandlers.forEach(function (fn) { fn(); });
/* 11. 修行次第線（2026-09-17 新增區塊） */
var lad = allInnerHTML['mm-ladder'] || '';
(function () {
    var n = (lad.match(/<details class="mm-ladder-step">/g) || []).length;
    expect('ladder 渲染 23 級（16 實修+7 義理）', n === 23, String(n));
})();
expect('ladder 首級含「戒行」', lad.indexOf('戒行') !== -1);
expect('ladder 義理線含「自性恒常」(簡)', lad.indexOf('自性恒常') !== -1);
expect('ladder 註記簡體「身体工程」(簡)', lad.indexOf('身体工程') !== -1);
expect('ladder 不含繁體「身體工程」', lad.indexOf('身體工程') === -1);
expect('ladder 含原文深連結', lad.indexOf('href="ebook/') !== -1);
expect('ladder 含「在心智图中查看」(簡)', lad.indexOf('在心智图中查看') !== -1);

console.log(failed === 0 ? '\nALL ASSERTIONS PASSED' : '\n' + failed + ' FAILED');
process.exit(failed === 0 ? 0 : 1);
