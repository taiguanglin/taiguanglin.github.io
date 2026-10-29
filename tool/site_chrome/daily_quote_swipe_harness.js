#!/usr/bin/env node
/* 首頁「每日精選」觸控左右滑動的迴歸測試
 * （tool/site_chrome/daily_quote_swipe_harness.js）
 *
 * 背景：index.html 的每日精選卡片另有 ◀ ▶ 鈕可切換前／後一日；手機、平板等
 * 有觸控的終端另有「左滑＝後一天、右滑＝前一天」的手勢。
 *
 * ⚠️ 觸控走的是 **Touch Events**（不是 Pointer Events）：Android Chrome 的
 * pointer 事件串流常被 compositor 攔截而發 pointercancel，用 Pointer Events
 * 實作會在手機上完全滑不動。故觸控在 touchmove 內 preventDefault（listener
 * 必須 passive:false）把捲動擋掉；觸控筆（pen）才走 Pointer。
 *
 * 這支測試不依賴 jsdom：用 vm 跑 index.html 內的inline script，只替掉它會碰到的
 * 少數 DOM 全域（getElementById／classList／事件派送／fetch），驗證：
 *   ① 左滑 → 後一天、右滑 → 前一天；
 *   ② 水平 touchmove 有 preventDefault（Android 不會被當成捲動）；
 *   ③ 垂直手勢、短距離手勢、畫面邊緣手勢、滑鼠拖曳都不會切換日期；
 *   ④ 滑動後緊接著的那一下 click 會被攔截（不會誤觸「前往原文」或切換鈕）；
 *   ⑤ 觸控筆（pen）走 Pointer Events 也可切換；原有 ◀ ▶ 鈕仍可切換。
 *
 * 用法：在 repo 根目錄執行  node tool/site_chrome/daily_quote_swipe_harness.js
 */
'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var ROOT = path.resolve(__dirname, '..', '..');
var INDEX = path.join(ROOT, 'index.html');
var VIEWPORT_W = 390;   // 模擬手機寬度（畫面邊緣保留給系統手勢）

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
                capture: !!(opts && opts.capture),
                passive: !!(opts && opts.passive)
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
        dailyQuotePrev: makeEl('dailyQuotePrev', card),
        dailyQuoteNext: makeEl('dailyQuoteNext', card),
        dailyQuotePrevMonth: makeEl('dailyQuotePrevMonth', card),
        dailyQuoteNextMonth: makeEl('dailyQuoteNextMonth', card),
        dailyQuoteToday: makeEl('dailyQuoteToday', card)
    };
    doc.getElementById = function (id) { return els[id] || null; };
    return els;
}

/* ---------- 模擬手勢 ---------- */
function touchPoint(x, y, id) {
    return { identifier: id, clientX: x, clientY: y };
}

/* 觸控手勢（Touch Events）：回傳 touchmove 事件（檢查 preventDefault） */
function touchGesture(els, opts) {
    var x = opts.x != null ? opts.x : 200;
    var y = opts.y != null ? opts.y : 300;
    var dx = opts.dx || 0;
    var dy = opts.dy || 0;
    var target = opts.target || els.dailyQuoteText;
    var id = opts.id || 1;
    var p0 = touchPoint(x, y, id);
    var p1 = touchPoint(x + dx, y + dy, id);

    dispatch(target, 'touchstart', {
        touches: [p0], changedTouches: [p0], targetTouches: [p0], cancelable: false
    });
    var moveEv = dispatch(target, 'touchmove', {
        touches: [p1], changedTouches: [p1], targetTouches: [p1], cancelable: true
    });
    dispatch(target, 'touchend', {
        touches: [], changedTouches: [p1], targetTouches: [], cancelable: false
    });
    return moveEv;
}

/* 觸控筆／滑鼠手勢（Pointer Events） */
function pointerGesture(els, opts) {
    var pointerType = opts.pointerType || 'pen';
    var x = opts.x != null ? opts.x : 200;
    var y = opts.y != null ? opts.y : 300;
    var dx = opts.dx || 0;
    var dy = opts.dy || 0;
    var target = opts.target || els.dailyQuoteText;
    var base = {
        pointerType: pointerType,
        pointerId: opts.pointerId || 1,
        isPrimary: true,
        cancelable: true
    };
    dispatch(target, 'pointerdown', Object.assign({}, base, { clientX: x, clientY: y }));
    dispatch(target, 'pointermove', Object.assign({}, base, { clientX: x + dx, clientY: y + dy }));
    dispatch(target, 'pointerup', Object.assign({}, base, { clientX: x + dx, clientY: y + dy }));
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
    windowStub.innerWidth = VIEWPORT_W;
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

    /* ① 左滑 → 後一天（觸控走 Touch Events） */
    var moveEv = touchGesture(els, { dx: -120 });
    await sleep(320);
    check('左滑切到後一天（明日精選）', dayEl.textContent === '明日精選', dayEl.textContent);
    check('左滑後內容確實換成另一則', textEl.textContent !== initialText, textEl.textContent);
    check('水平 touchmove 有 preventDefault（Android 不會被當成捲動）',
        moveEv.defaultPrevented === true);

    /* ① 右滑 → 前一天（回到今日） */
    touchGesture(els, { dx: 120 });
    await sleep(320);
    check('右滑切回前一天（今日精選）', dayEl.textContent === '今日精選', dayEl.textContent);
    check('右滑後回到原本那一則', textEl.textContent === initialText, textEl.textContent);

    /* ② 垂直手勢不切換，且不 preventDefault（頁面照常捲動） */
    var beforeVertical = textEl.textContent;
    var vMove = touchGesture(els, { dx: -30, dy: -140 });
    await sleep(320);
    check('垂直滑動不會切換日期', dayEl.textContent === '今日精選' && textEl.textContent === beforeVertical,
        dayEl.textContent + ' / ' + textEl.textContent);
    check('垂直滑動不 preventDefault（頁面仍可捲動）', vMove.defaultPrevented === false);

    /* ③ 位移不足不切換 */
    touchGesture(els, { dx: -30 });
    await sleep(320);
    check('位移不足不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ③ 畫面左右邊緣的手勢留給系統（Android 返回／縮放） */
    touchGesture(els, { dx: -120, x: 8 });
    await sleep(320);
    check('畫面邊緣的滑動不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ③ 滑鼠拖曳不切換 */
    pointerGesture(els, { dx: -120, pointerType: 'mouse' });
    await sleep(320);
    check('滑鼠拖曳不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ③ 觸控筆（Pointer Events）可切換 */
    pointerGesture(els, { dx: -120, pointerType: 'pen' });
    await sleep(320);
    check('觸控筆滑動可切換日期', dayEl.textContent === '明日精選', dayEl.textContent);
    pointerGesture(els, { dx: 120, pointerType: 'pen' });
    await sleep(320);
    check('觸控筆右滑可切回前一天', dayEl.textContent === '今日精選', dayEl.textContent);

    /* ④ 滑動後那一下 click 被攔截（不會誤觸「前往原文」） */
    touchGesture(els, { dx: -120 });
    var clickEv = dispatch(els.dailyQuoteLink, 'click', {});
    check('滑動後的 click 被攔截', clickEv.defaultPrevented === true);
    await sleep(320);

    /* ⑤ 微幅手抖不切換，也不吃掉那一下點擊（先回到今日再測） */
    dispatch(els.dailyQuoteToday, 'click', {});
    await sleep(320);
    touchGesture(els, { dx: -14 });
    var jitterClick = dispatch(els.dailyQuoteLink, 'click', {});
    check('手抖（位移過小）不會切換日期', dayEl.textContent === '今日精選', dayEl.textContent);
    check('手抖不會攔截點擊', jitterClick.defaultPrevented === false);
    await sleep(320);

    /* ⑥ 原有 ◀ ▶ 鈕仍可切換 */
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
