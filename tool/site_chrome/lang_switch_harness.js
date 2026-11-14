#!/usr/bin/env node
/* lang-switch.js「前往原文」錨點跳轉的迴歸測試（tool/site_chrome/lang_switch_harness.js）
 *
 * 背景：首頁「每日精選」的「前往原文」永遠連到 *_trad.html#<段落 id>。偏好
 * 簡體的讀者會被 lang-switch.js 轉到對應的簡體頁 —— 舊版轉址時只帶
 * `location.search`、**漏掉 hash**，再加上它用 defer 執行、量到的捲動位置
 * 還是 0，於是整段跳轉機制退化成「跳到這本書的目錄」。繁簡雙頁的段落 id
 * 由同一份來源產生、完全相同，所以正確做法是把 hash 一起帶過去。
 *
 * 不依賴 jsdom：用 vm 跑真正的 lang-switch.js，只替掉它會碰到的少數全域
 * （location / localStorage / sessionStorage / navigator / document）。
 *
 * 用法：在 repo 根目錄執行  node tool/site_chrome/lang_switch_harness.js
 */
'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var ROOT = path.resolve(__dirname, '..', '..');
var SRC = path.join(ROOT, 'lang-switch.js');

var failures = [];
function check(label, condition, detail) {
    if (condition) console.log('PASS  ' + label);
    else {
        console.log('FAIL  ' + label + (detail ? '  →  ' + detail : ''));
        failures.push(label);
    }
}

function makeStorage() {
    var map = {};
    return {
        getItem: function (k) { return Object.prototype.hasOwnProperty.call(map, k) ? map[k] : null; },
        setItem: function (k, v) { map[k] = String(v); },
        removeItem: function (k) { delete map[k]; },
        _map: map
    };
}

/* 跑一次 lang-switch.js，回傳它呼叫 location.replace 的目標與副作用 */
function run(href, storedPref) {
    var u = new URL(href, 'https://taiguanglin.info/');
    var local = makeStorage();
    if (storedPref) local.setItem('tgl-lang', storedPref);
    var session = makeStorage();
    var replaced = null;

    var location = {
        pathname: u.pathname,
        search: u.search,
        hash: u.hash,
        href: u.href,
        replace: function (to) { replaced = to; }
    };
    var documentStub = {
        documentElement: { scrollHeight: 100, classList: { add: function () {} } },
        addEventListener: function () {},
        querySelectorAll: function () { return []; },
        querySelector: function () { return null; },
        createElement: function () { return { style: {}, classList: { add: function () {} }, setAttribute: function () {} }; },
        body: { appendChild: function () {} },
        readyState: 'complete'
    };
    var sandbox = {
        location: location,
        localStorage: local,
        sessionStorage: session,
        navigator: { languages: ['zh-CN', 'zh'], language: 'zh-CN' },
        document: documentStub,
        URLSearchParams: URLSearchParams,
        console: console,
        setTimeout: function () {},
        clearTimeout: function () {},
        requestAnimationFrame: function (fn) { fn(); },
        Promise: Promise
    };
    sandbox.window = sandbox;
    sandbox.globalThis = sandbox;

    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(SRC, 'utf8'), sandbox, { filename: 'lang-switch.js' });

    return { replaced: replaced, session: session, local: local };
}

console.log('lang-switch.js —— 前往原文錨點跳轉\n');

// 1) 簡體偏好 + 繁體頁帶錨點（首頁「前往原文」最常見的情境）
var r1 = run('/ebook/09_trad.html#p-s0bf8dfc2', 'simp');
check(
    '簡體偏好：ebook/09_trad.html#p-x → 轉到簡體頁且保留錨點',
    r1.replaced === '/ebook/09.html#p-s0bf8dfc2',
    'got: ' + r1.replaced
);
check(
    '簡體偏好：不再寫入估算的 langjump（否則會覆蓋錨點位置）',
    r1.session._map['w2e:langjump'] === undefined,
    'got: ' + JSON.stringify(r1.session._map['w2e:langjump'])
);

// 2) 反向：繁體偏好 + 簡體頁帶錨點
var r2 = run('/wenda2_ebook/07.html#answer-1c3841356716', 'trad');
check(
    '繁體偏好：wenda2_ebook/07.html#answer-x → 轉到繁體頁且保留錨點',
    r2.replaced === '/wenda2_ebook/07_trad.html#answer-1c3841356716',
    'got: ' + r2.replaced
);

// 3) 沒有錨點時，維持原本的 U10 閱讀位置保留機制（不可回歸）
var r3 = run('/ebook/09_trad.html', 'simp');
check(
    '無錨點：仍轉到對應語系頁（不帶 hash）',
    r3.replaced === '/ebook/09.html',
    'got: ' + r3.replaced
);
check(
    '無錨點：仍寫入 langjump 供 10-search-return.js 原位恢復',
    typeof r3.session._map['w2e:langjump'] === 'string',
    'got: ' + JSON.stringify(r3.session._map['w2e:langjump'])
);

// 4) 已經是目標語系 → 完全不轉址
var r4 = run('/ebook/09_trad.html#p-s0bf8dfc2', 'trad');
check(
    '繁體偏好 + 繁體頁：完全不轉址（原生錨點跳轉）',
    r4.replaced === null,
    'got: ' + r4.replaced
);
var r5 = run('/ebook/09.html#p-s0bf8dfc2', 'simp');
check(
    '簡體偏好 + 簡體頁：完全不轉址（原生錨點跳轉）',
    r5.replaced === null,
    'got: ' + r5.replaced
);

// 6) 目錄頁（/ebook/）正規化後仍正確處理
var r6 = run('/ebook/', 'trad');
check('目錄頁 /ebook/ + 繁體偏好：轉到 /ebook/index_trad.html', r6.replaced === '/ebook/index_trad.html', 'got: ' + r6.replaced);
var r7 = run('/ebook/#p-s0bf8dfc2', 'simp');
check('目錄頁 /ebook/ + 簡體偏好：index.html 已是簡體頁，不轉址', r7.replaced === null, 'got: ' + r7.replaced);
var r8 = run('/ebook/#p-s0bf8dfc2', 'trad');
check('目錄頁帶錨點 + 繁體偏好：錨點保留下來', r8.replaced === '/ebook/index_trad.html#p-s0bf8dfc2', 'got: ' + r8.replaced);

// 7) 搜尋狀態 hash（#q=…&scope=…）也要原樣帶過去
var r9 = run('/ebook/09_trad.html#q=%E5%8D%9A%E6%81%AF&scope=answer', 'simp');
check(
    '搜尋狀態 hash 跨語系保留',
    r9.replaced === '/ebook/09.html#q=%E5%8D%9A%E6%81%AF&scope=answer',
    'got: ' + r9.replaced
);

// 8) PHRASE_PROTECT 必須保留「用户／用戶」（不可被 OpenCC 改成「使用者」）
var langSwitchSrc = fs.readFileSync(SRC, 'utf8');
check(
    "lang-switch.js 的 PHRASE_PROTECT 含「用户→用戶」「用戶→用戶」",
    langSwitchSrc.indexOf("['用户', '用戶']") !== -1 &&
        langSwitchSrc.indexOf("['用戶', '用戶']") !== -1
);

// 8.5) 台灣慣用詞字典的改寫 → 維持原用詞（2026-11 使用者指示）
check(
    "lang-switch.js 的 PHRASE_PROTECT 含「概率／信息／網絡／視頻／軟件」等原用詞保護",
    langSwitchSrc.indexOf("['概率', '概率']") !== -1 &&
        langSwitchSrc.indexOf("['信息', '信息']") !== -1 &&
        langSwitchSrc.indexOf("['网络', '網絡']") !== -1 &&
        langSwitchSrc.indexOf("['视频', '視頻']") !== -1 &&
        langSwitchSrc.indexOf("['软件', '軟件']") !== -1
);
check(
    "例外五個詞（老撾／硅／新西蘭／納米／津巴布韋）不列入保護：維持台灣用語",
    langSwitchSrc.indexOf("['老撾', '寮國']") === -1 &&
        langSwitchSrc.indexOf("['硅', '矽']") === -1 &&
        langSwitchSrc.indexOf("['新西兰', '紐西蘭']") === -1 &&
        langSwitchSrc.indexOf("['纳米', '奈米']") === -1 &&
        langSwitchSrc.indexOf("['津巴布韦', '津巴布韋']") === -1
);

// 9) OpenCC cn→tw 把「干」（做）誤轉成「乾」的修正層（與 i18n_utils 同步）
//    fixGan 作用在「轉換後」的繁體文字；此處直接抽出函式驗證規則本身。
var langSrc = fs.readFileSync(SRC, 'utf8');
var ganFn = langSrc.match(/var GAN_DRY_NEXT[\s\S]*?\n    function fixGan\(text\) \{[\s\S]*?\n    \}/);
check('lang-switch.js 含 fixGan 修正函式', !!ganFn);
if (ganFn) {
    /* 以 Function 建構式取出函式（strict mode 下 eval 不會洩漏到外層作用域） */
    var fixGan = new Function(ganFn[0] + '\nreturn fixGan;')();
    var ganCases = [
        ['如果你乾的就是你想幹的事', '如果你幹的就是你想幹的事'],
        ['該乾的事都幹了', '該幹的事都幹了'],
        ['但是乾的精神上很累', '但是幹的精神上很累'],
        ['那就是乾的事最後都會', '那就是幹的事最後都會'],
        ['他們自己乾的，又不是你逼著他們乾的', '他們自己幹的，又不是你逼著他們幹的'],
        ['非得乾死一方', '非得幹死一方'],
        ['四千萬給乾沒了', '四千萬給幹沒了'],
        ['乾完了再繼續打', '幹完了再繼續打'],
        ['乾點事', '幹點事'],
        ['外邪不可乾的角度', '外邪不可干的角度'],
        // OpenCC 片語字典漏轉的做義固定詞
        ['提水乾活洗尿布', '提水幹活洗尿布'],
        ['少乾沒用的事', '少幹沒用的事'],
        ['別乾等著', '別幹等著'],
        ['都乾得很好，甚至超過', '都幹得很好，甚至超過'],
        // 乾燥義不動
        ['如果鼻子一直是乾的', '如果鼻子一直是乾的'],
        ['吃不下主食乾的米飯', '吃不下主食乾的米飯'],
        ['不吃乾的', '不吃乾的'],
        ['媽媽在快乾的河裡', '媽媽在快乾的河裡'],
        ['乾淨的米飯', '乾淨的米飯'],
        ['乾脆就放下', '乾脆就放下'],
        ['乾坐著', '乾坐著'],
        ['乾隆大藏經', '乾隆大藏經'],
        ['乾闥婆城', '乾闥婆城']
    ];
    for (var g = 0; g < ganCases.length; g++) {
        var got = fixGan(ganCases[g][0]);
        check(
            'fixGan：' + ganCases[g][0] + ' → ' + ganCases[g][1],
            got === ganCases[g][1],
            'got: ' + got
        );
    }
}

console.log('');
if (failures.length) {
    console.log('lang_switch_harness: ' + failures.length + ' 項失敗');
    process.exit(1);
}
console.log('lang_switch_harness: 全部通過');
