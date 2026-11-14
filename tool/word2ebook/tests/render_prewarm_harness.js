#!/usr/bin/env node
/* 19-render-prewarm.js（背景預熱）的回歸測試
 * （tool/word2book/tests/render_prewarm_harness.js）
 *
 * 背景：電子書頁面對 .question/.answer/.para-block/article.qa-pair 設了
 *       `content-visibility: auto`，視窗外的區塊不排版也不繪製——使用者
 *       向下捲動時要等瀏覽器「跑到附近」才渲染，會看到空白／慢半拍。
 *       19-render-prewarm.js 在背景把視窗下方一段區間的區塊提前渲染好。
 *
 * 本測試不依賴 jsdom：用 vm 跑真正的模組，只替掉它會碰到的少數全域
 * （window / document / IntersectionObserver / navigator / isIndexPage）。
 *
 * 用法：在 repo 根目錄執行
 *     node tool/word2ebook/tests/render_prewarm_harness.js
 */
'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var ROOT = path.resolve(__dirname, '..', '..', '..');
var SRC = path.join(ROOT, 'tool', 'word2ebook', 'assets', 'js', 'modules',
    '19-render-prewarm.js');

var failures = [];
function check(label, condition, detail) {
    if (condition) console.log('PASS  ' + label);
    else {
        console.log('FAIL  ' + label + (detail ? '  →  ' + detail : ''));
        failures.push(label);
    }
}

// ---------------------------------------------------------------- 假 DOM --
function makeImg() {
    return {
        attrs: { loading: 'lazy' },
        decoded: 0,
        setAttribute: function (k, v) { this.attrs[k] = v; },
        decode: function () { this.decoded++; return Promise.resolve(); }
    };
}

function makeEl(images) {
    var el = {
        classes: {},
        images: images || [],
        classList: {
            add: function (c) { el.classes[c] = true; },
            remove: function (c) { delete el.classes[c]; },
            contains: function (c) { return !!el.classes[c]; }
        },
        querySelectorAll: function (sel) {
            if (sel === 'img[loading="lazy"]') {
                return el.images.filter(function (i) { return i.attrs.loading === 'lazy'; });
            }
            return [];
        }
    };
    return el;
}

// 載入模組並回傳可操作的環境
function load(opts) {
    opts = opts || {};
    var store = { observed: [], ioOptions: null, io: null, idle: [] };
    var targets = opts.targets || [];

    var sandbox = {
        console: console,
        setTimeout: setTimeout,
        Promise: Promise,
        navigator: opts.navigator || {},
        document: {
            querySelectorAll: function (sel) {
                sandbox.lastSelector = sel;
                return targets;
            }
        },
        isIndexPage: function () { return !!opts.isIndex; },
        requestIdleCallback: function (cb) { store.idle.push(cb); }
    };
    if (!opts.noIO) {
        sandbox.IntersectionObserver = function (cb, options) {
            this.cb = cb;
            this.options = options;
            this.observe = function (t) { store.observed.push(t); };
            this.unobserve = function () { };
            store.io = this;
            store.ioOptions = options;
        };
    }
    if (opts.prewarmConfig) sandbox.W2E_PREWARM = opts.prewarmConfig;
    if (opts.withW2E) sandbox.W2E = {};
    sandbox.window = sandbox;

    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(SRC, 'utf8'), sandbox, { filename: SRC });

    return {
        store: store,
        sandbox: sandbox,
        fire: function (entries) { store.io.cb(entries); },
        flushIdle: function () {
            var jobs = store.idle.slice();
            store.idle.length = 0;
            jobs.forEach(function (job) { job(); });
        }
    };
}

function entry(target, isIntersecting) {
    return { target: target, isIntersecting: isIntersecting };
}

// ------------------------------------------------------------------ 測試 --
(function () {
    // 1. 預熱區的 rootMargin：上方保留半屏、下方八屏（預設）
    var img = makeImg();
    var block = makeEl([img]);
    var env = load({ targets: [block] });
    check('建立 IntersectionObserver', !!env.store.io);
    check('rootMargin 預設為「上方 -50%、下方 800%」',
        env.store.ioOptions && env.store.ioOptions.rootMargin === '-50% 0px 800% 0px',
        env.store.ioOptions && env.store.ioOptions.rootMargin);
    check('所有區塊都被 observe', env.store.observed.length === 1);

    // 2. 進入預熱區 → 加 .w2e-prewarmed（並預熱圖片）
    env.fire([entry(block, true)]);
    env.flushIdle();
    check('進入預熱區後加上 .w2e-prewarmed', block.classList.contains('w2e-prewarmed'));
    check('區塊內的 lazy 圖片改為 eager', img.attrs.loading === 'eager', img.attrs.loading);
    check('區塊內的圖片被預先 decode', img.decoded === 1, String(img.decoded));

    // 3. 離開預熱區 → 收回
    env.fire([entry(block, false)]);
    check('離開預熱區後收回 .w2e-prewarmed', !block.classList.contains('w2e-prewarmed'));

    // 4. 首頁不啟動（沒有長文捲動）
    var indexEnv = load({ targets: [makeEl()], isIndex: true });
    check('首頁不建立 IntersectionObserver', !indexEnv.store.io);

    // 5. 沒有 IntersectionObserver 的瀏覽器 → 略過、不報錯
    var noIoEnv = load({ targets: [makeEl()], noIO: true });
    check('無 IntersectionObserver 時安全略過', !noIoEnv.store.io);

    // 6. 可用 window.W2E_PREWARM 覆寫區間大小與圖片預熱
    var cfgImg = makeImg();
    var cfgBlock = makeEl([cfgImg]);
    var cfgEnv = load({
        targets: [cfgBlock],
        prewarmConfig: { below: 2, images: false },
        withW2E: true
    });
    check('W2E_PREWARM 可覆寫預熱區間',
        cfgEnv.store.ioOptions.rootMargin === '-50% 0px 200% 0px',
        cfgEnv.store.ioOptions.rootMargin);
    cfgEnv.fire([entry(cfgBlock, true)]);
    cfgEnv.flushIdle();
    check('W2E_PREWARM.images=false 時不動圖片',
        cfgImg.attrs.loading === 'lazy', cfgImg.attrs.loading);
    check('診斷資訊掛在 W2E.prewarm',
        !!(cfgEnv.sandbox.W2E && cfgEnv.sandbox.W2E.prewarm));

    // 7. 分批處理：一次只處理 BATCH 個，剩餘留到下一批
    var many = [];
    for (var i = 0; i < 12; i++) many.push(makeEl());
    var batchEnv = load({ targets: many });
    var entries = many.map(function (el) { return entry(el, true); });
    batchEnv.fire(entries);
    batchEnv.flushIdle();
    var promoted = many.filter(function (el) { return el.classList.contains('w2e-prewarmed'); });
    check('分批預熱（首批 8 個）', promoted.length === 8, String(promoted.length));
    batchEnv.flushIdle();
    var promoted2 = many.filter(function (el) { return el.classList.contains('w2e-prewarmed'); });
    check('下一批補完剩下的', promoted2.length === 12, String(promoted2.length));

    if (failures.length) {
        console.error('\n' + failures.length + ' 項失敗');
        process.exit(1);
    }
    console.log('\n全部通過');
})();
