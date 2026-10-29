#!/usr/bin/env node
/* 首頁「每日精選」觸控左右滑動的迴歸測試
 * （tool/site_chrome/daily_quote_swipe_harness.js）
 *
 * 背景：index.html 的每日精選卡片另有 ◀ ▶ 鈕可切換前／後一日；手機、平板等
 * 有觸控的終端另有「左滑＝後一天、右滑＝前一天」的手勢（Pointer Events）。
 * 這支測試不依賴 jsdom：用 vm 跑 index.html 內的inline script，只替掉它會碰到的
 * 少數 DOM 全域（getElementById／classList／事件派送／fetch），驗證：
 *   ① 左滑 → 後一天、右滑 → 前一天；
 *   ② 垂直手勢、短距離手勢、滑鼠拖曳都不會切換日期；
 *   ③ 滑動後緊接著的那一下 click 會被攔截（不會誤觸「前往原文」或切換鈕）；
 *   ④ 原有 ◀ ▶ 鈕仍可切換。
 *
 * 用法：在 repo 根目錄執行  node tool/site_chrome/daily_quote_swipe_harness.js
 */
'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var ROOT = path.resolve(__dirname, '..', '..');
var INDEX = path.join(ROOT, 'index.html');

var failures = [];
function check(label, condition, detail) {
    if (condition) console.log('PASS  ' + label);
    else {
        console.log('FAIL  ' + label + (detail ? '  →  ' + detail : ''));
        failures.push(label);
    }
}

/* ---------- 迷你 DOM ---------- */
function makeStyle() {
    return {
        display: '',
        _props: {},
        setProperty: function (k, v) { this._props[k] = v; },
        removeProperty: function (k) { delete this._props[k]; }
    };
}

function makeEl(id, parent) {
    var el = {
        id: id,
        parent: parent || null,
        textContent: '',
        href: '',
        disabled: false,
        style: makeStyle(),
        attributes: {},
        _classes: [],
        _handlers: {},
        offsetWidth: 0,
        scrollHeight: 0,
        clientHeight: 0,
        setAttribute: function (k, v) { this.attributes[k] = v; },
        getAttribute: function (k) { return this.attributes[k]; },
        addEventListener: function (type, fn, opts) {
            (this._handlers[type] = this._handlers[type] || []).push({
                fn: fn,
                capture: !!(opts && opts.capture)
            });
        },
        classList: {
            add: function (c) { if (el._classes.indexOf(c) < 0) el._classes.push(c); },
            remove: function (c) { var i = el._classes.indexOf(c); if (i >= 0) el._classes.splice(i, 1); },
            contains: function (c) { return el._classes.indexOf(c) >= 0; },
            toggle: function (c, force) {
                if (force === undefined) {
                    if (el.classList.contains(c)) el.classList.remove(c);
                    else el.classList.add(c);
                } else if (force) el.classList.add(c);
                else el.classList.remove(c);
            }
        }
    };
    return el;
}

function dispatch(target, type, props) {
    var ev = {
        type: type,
        target: target,
        defaultPrevented: false,
        _stopped: false,
        preventDefault: function () { this.defaultPrevented = true; },
        stopPropagation: function () { this._stopped = true; }
    };
    Object.keys(props || {}).forEach(function (k) { ev[k] = props[k]; });

    var path = [];
    for (var n = target; n; n = n.parent) path.unshift(n);

    path.forEach(function (node) {                 // capture：root → target
        (node._handlers[type] || []).forEach(function (h) {
            if (h.capture && !ev._stopped) h.fn.call(node, ev);
        });
    });
    for (var i = path.length - 1; i >= 0; i--) {  // bubble：target → root
        if (ev._stopped) break;
        (path[i]._handlers[type] || []).forEach(function (h) {
            if (!h.capture) h.fn.call(path[i], ev);
        });
    }
    return ev;
}

/* ---------- 取出 index.html 內的每日精選 inline script ---------- */
function extractScript(html) {
    var re = /<script>([\s\S]*?)<\/script>/g;
    var m;
    while ((m = re.exec(html)) !== null) {
        if (m[1].indexOf('dailyQuoteCard') >= 0) return m[1];
    }
    throw new Error('index.html 內找不到每日精選的 inline script');
}

/* ---------- 組出 DOM ---------- */
function buildDom() {
    var doc = makeEl('#document');
    doc.readyState = 'complete';
    doc.getElementById = function (id) { return els[id] || null; };

    var section = makeEl('daily-quote', doc);
    var card = makeEl('dailyQuoteCard', section);
    var els = {
        '#document': doc,
        'daily-quote': section,
        dailyQuoteCard: card,
        dailyQuoteSrc: makeEl('dailyQuoteSrc', card),
        dailyQuoteText: makeEl('dailyQuoteText', card),
        dailyQuoteToggle: makeEl('dailyQuoteToggle', card),
        dailyQuoteLink: makeEl('dailyQuoteLink', card),
        dailyQuoteDay: makeEl('dailyQuoteDay', card),
        dailyQuoteHint: makeEl('dailyQuoteHint', card),
        dailyQuotePrev: makeEl('dailyQuotePrev', card),
        dailyQuoteNext: makeEl('dailyQuoteNext', card),
        dailyQuotePrevMonth: makeEl('dailyQuotePrevMonth', card),
        dailyQuoteNextMonth: makeEl('dailyQuoteNextMonth', card),
        dailyQuoteToday: makeEl('dailyQuoteToday', card)
    };
    return els;
}

/* ---------- 模擬手勢 ---------- */
function gesture(els, opts) {
    var pointerType = opts.pointerType || 'touch';
    var startX = opts.x || 300;
    var startY = opts.y || 300;
    var dx = opts.dx || 0;
    var dy = opts.dy || 0;
    var target = opts.target || els.dailyQuoteText;
    var base = {
        pointerType: pointerType,
        pointerId: opts.pointerId || 1,
        isPrimary: true,
        cancelable: true
    };
    dispatch(target, 'pointerdown', Object.assign({}, base, { clientX: startX, clientY: startY }));
    dispatch(target, 'pointermove', Object.assign({}, base, { clientX: startX + dx, clientY: startY + dy }));
    dispatch(target, 'pointerup', Object.assign({}, base, { clientX: startX + dx, clientY: startY + dy }));
}

function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

async function main() {
    var html = fs.readFileSync(INDEX, 'utf8');
    var code = extractScript(html);

    var quotes = [
        { text: '第一則：安住當下。', title: '禪修', url: 'ebook/a.html#p-1' },
        { text: '第二則：照見五蘊。', title: '禪修', url: 'ebook/a.html#p-2' },
        { text: '第三則：放下執著。', title: '禪修', url: 'ebook/a.html#p-3' }
    ];

    var els = buildDom();
    var documentStub = els['#document'];
    var windowStub = makeEl('#window');
    documentStub.parent = windowStub;   // 事件傳遞路徑：target → … → document → window

    var sandbox = {
        document: documentStub,
        console: console,
        Date: Date,
        Math: Math,
        Promise: Promise,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        fetch: function () {
            return Promise.resolve({ ok: true, json: function () { return Promise.resolve({ quotes: quotes }); } });
        }
    };
    sandbox.window = windowStub;

    vm.createContext(sandbox);
    vm.runInContext(code, sandbox, { filename: 'index.html#daily-quote' });

    await sleep(50);   // 等 fetch 回來、首次 render 完成

    var textEl = els.dailyQuoteText;
    var dayEl = els.dailyQuoteDay;
    var initialText = textEl.textContent;

    check('每日精選載入後有內容', !!initialText && initialText !== '載入中…', initialText);
    check('每日精選載入後顯示「今日精選」', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ① 左滑 → 後一天 */
    gesture(els, { dx: -120 });
    await sleep(320);
    check('左滑切到後一天（明日精選）', dayEl.textContent === '明日精選', dayEl.textContent);
    check('左滑後內容確實換成另一則', textEl.textContent !== initialText, textEl.textContent);

    /* ① 右滑 → 前一天（回到今日） */
    gesture(els, { dx: 120 });
    await sleep(320);
    check('右滑切回前一天（今日精選）', dayEl.textContent === '今日精選', dayEl.textContent);
    check('右滑後回到原本那一則', textEl.textContent === initialText, textEl.textContent);

    /* ② 垂直手勢不切換 */
    var beforeVertical = textEl.textContent;
    gesture(els, { dx: -30, dy: -140 });
    await sleep(320);
    check('垂直滑動不會切換日期', dayEl.textContent === '今日精選' && textEl.textContent === beforeVertical,
        dayEl.textContent + ' / ' + textEl.textContent);

    /* ② 位移不足不切換 */
    gesture(els, { dx: -30 });
    await sleep(320);
    check('位移不足不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ② 滑鼠拖曳不切換 */
    gesture(els, { dx: -120, pointerType: 'mouse' });
    await sleep(320);
    check('滑鼠拖曳不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ② 微幅手抖不切換，也不吃掉那一下點擊 */
    gesture(els, { dx: -14 });
    var jitterClick = dispatch(els.dailyQuoteLink, 'click', {});
    check('手抖（位移過小）不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);
    check('手抖不會攔截點擊', jitterClick.defaultPrevented === false);
    await sleep(320);

    /* ③ 滑動後那一下 click 被攔截（不會誤觸「前往原文」） */
    gesture(els, { dx: -120 });
    var clickEv = dispatch(els.dailyQuoteLink, 'click', {});
    check('滑動後的 click 被攔截', clickEv.defaultPrevented === true);
    await sleep(320);

    /* ④ 原有 ◀ ▶ 鈕仍可切換 */
    dispatch(els.dailyQuoteToday, 'click', {});
    await sleep(320);
    check('「今日」鈕仍可切換', dayEl.textContent === '今日精選', dayEl.textContent);
    dispatch(els.dailyQuoteNext, 'click', {});
    await sleep(320);
    check('「後一天」鈕仍可切換', dayEl.textContent === '明日精選', dayEl.textContent);
    dispatch(els.dailyQuotePrev, 'click', {});
    await sleep(320);
    check('「前一天」鈕仍可切換', dayEl.textContent === '今日精選', dayEl.textContent);

    if (failures.length) {
        console.error('\n失敗 ' + failures.length + ' 項：');
        failures.forEach(function (f) { console.error('  - ' + f); });
        process.exit(1);
    }
    console.log('\n全部通過。');
}

main().catch(function (err) {
    console.error(err && err.stack ? err.stack : err);
    process.exit(1);
});
