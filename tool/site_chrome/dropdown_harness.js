#!/usr/bin/env node
/* 「圖解」下拉的互動煙霧測試（tool/site_chrome/dropdown_harness.js）
 *
 * 不依賴 jsdom：從真實頁面抽出導覽 HTML、用極簡 DOM stub 解析成節點樹，
 * 再把 shared.js 裡的 dropdown 區塊原封不動抽出來執行，驗證滑鼠／鍵盤／點外關閉的行為。
 *
 * 用法：在 repo 根目錄執行  node tool/site_chrome/dropdown_harness.js [頁面路徑...]
 */
'use strict';

var fs = require('fs');
var path = require('path');

var ROOT = path.resolve(__dirname, '..', '..');
var PAGES = process.argv.slice(2).length
    ? process.argv.slice(2)
    : ['index.html', 'mindmap.html', 'wenda2/chapter-01.html', 'stories/kedatou-jieba-ganwu.html'];

var failures = [];
function check(label, condition) {
    if (condition) console.log('PASS  ' + label);
    else { console.log('FAIL  ' + label); failures.push(label); }
}

/* ---------------- 極簡 DOM stub ---------------- */

function Element(tag, attrs) {
    this.tagName = tag.toUpperCase();
    this.attributes = attrs || {};
    this.children = [];
    this.parent = null;
    this._classes = (this.attributes.class || '').split(/\s+/).filter(Boolean);
    this._listeners = {};
    this.text = '';
}
Element.prototype.appendChild = function (child) {
    child.parent = this;
    this.children.push(child);
    return child;
};
Element.prototype.getAttribute = function (name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
};
Element.prototype.setAttribute = function (name, value) {
    this.attributes[name] = String(value);
};
Element.prototype.addEventListener = function (type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
};
Element.prototype.dispatch = function (type, event) {
    var list = this._listeners[type] || [];
    var ev = event || {};
    ev.preventDefault = ev.preventDefault || function () {};
    ev.stopPropagation = ev.stopPropagation || function () {};
    ev.target = ev.target || this;
    ev.key = ev.key || '';
    // 冒泡到祖先，模擬 addEventListener 在容器上的監聽
    for (var node = this; node; node = node.parent) {
        (node._listeners[type] || []).forEach(function (fn) { fn(ev); });
    }
    return ev;
};
Element.prototype.focus = function () { DOCUMENT.activeElement = this; };
Element.prototype.contains = function (node) {
    for (var n = node; n; n = n.parent) if (n === this) return true;
    return false;
};
Element.prototype._matches = function (selector) {
    if (selector.charAt(0) === '.') {
        return this._classes.indexOf(selector.slice(1)) !== -1;
    }
    return this.tagName === selector.toUpperCase();
};
Element.prototype._descendants = function () {
    var out = [];
    this.children.forEach(function (child) {
        out.push(child);
        out = out.concat(child._descendants());
    });
    return out;
};
Element.prototype.querySelectorAll = function (selector) {
    var parts = selector.trim().split(/\s+/);
    var scope = [this];
    for (var i = 0; i < parts.length; i++) {
        var matches = [];
        scope.forEach(function (node) {
            node._descendants().forEach(function (candidate) {
                if (candidate._matches(parts[i])) matches.push(candidate);
            });
        });
        scope = matches;
    }
    return scope;
};
Element.prototype.querySelector = function (selector) {
    var all = this.querySelectorAll(selector);
    return all.length ? all[0] : null;
};
Element.prototype.closest = function (selector) {
    for (var node = this; node; node = node.parent) {
        if (node._matches(selector)) return node;
    }
    return null;
};
Object.defineProperty(Element.prototype, 'classList', {
    get: function () {
        var self = this;
        return {
            contains: function (name) { return self._classes.indexOf(name) !== -1; },
            add: function (name) { if (!this.contains(name)) self._classes.push(name); },
            remove: function (name) {
                var at = self._classes.indexOf(name);
                if (at !== -1) self._classes.splice(at, 1);
            },
            toggle: function (name, force) {
                var want = force === undefined ? !this.contains(name) : !!force;
                if (want) this.add(name); else this.remove(name);
                return want;
            }
        };
    }
});

var DOCUMENT = { activeElement: null, _listeners: {} };
DOCUMENT.addEventListener = function (type, fn) {
    (DOCUMENT._listeners[type] = DOCUMENT._listeners[type] || []).push(fn);
};
DOCUMENT.dispatch = function (type, event) {
    var ev = event || {};
    ev.preventDefault = ev.preventDefault || function () {};
    ev.target = ev.target || DOCUMENT;
    (DOCUMENT._listeners[type] || []).forEach(function (fn) { fn(ev); });
};

/* ---------------- 解析頁面上的 dropdown HTML ---------------- */

var TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[a-zA-Z-]+="[^"]*")*)\s*(\/?)>/g;
var ATTR_RE = /([a-zA-Z-]+)="([^"]*)"/g;

function parseFragment(html) {
    var roots = [];
    var stack = [];
    var last = 0;
    var match;
    TAG_RE.lastIndex = 0;
    while ((match = TAG_RE.exec(html)) !== null) {
        var text = html.slice(last, match.index).trim();
        if (text && stack.length) stack[stack.length - 1].text += text;
        last = TAG_RE.lastIndex;

        var closing = match[1] === '/';
        var tag = match[2];
        var attrs = {};
        var attrMatch;
        ATTR_RE.lastIndex = 0;
        while ((attrMatch = ATTR_RE.exec(match[3] || '')) !== null) {
            attrs[attrMatch[1]] = attrMatch[2];
        }
        if (closing) { stack.pop(); continue; }
        var node = new Element(tag, attrs);
        if (stack.length) stack[stack.length - 1].appendChild(node);
        else roots.push(node);
        if (match[4] !== '/' && tag.toLowerCase() !== 'img' && tag.toLowerCase() !== 'br') stack.push(node);
    }
    return roots;
}

function extractDropdown(html) {
    var at = html.indexOf('<div class="nav-dropdown');
    if (at === -1) return null;
    // 由已知結構掃到配對的收尾：dropdown > menu 之後再一層
    var slice = html.slice(at);
    var depth = 0;
    TAG_RE.lastIndex = 0;
    var match;
    while ((match = TAG_RE.exec(slice)) !== null) {
        if (match[1] === '/') {
            depth -= 1;
            if (depth === 0) return slice.slice(0, TAG_RE.lastIndex);
        } else if (match[4] !== '/') {
            depth += 1;
        }
    }
    return null;
}

/* ---------------- 抽出 shared.js 的 dropdown 區塊 ---------------- */

function extractDropdownBlock() {
    var source = fs.readFileSync(path.join(ROOT, 'shared.js'), 'utf-8');
    var start = source.indexOf('/* ---------- Dropdown：');
    var end = source.indexOf('/* ---------- Nav active：');
    if (start === -1 || end === -1 || end <= start) {
        throw new Error('shared.js dropdown block not found');
    }
    return source.slice(start, end);
}

var BLOCK = extractDropdownBlock();

/* 抽出 shared.js 的 Mobile menu 區塊（手機滑入面板的開合與 closeMenu 佈線） */

function extractMobileMenuBlock() {
    var source = fs.readFileSync(path.join(ROOT, 'shared.js'), 'utf-8');
    var start = source.indexOf('/* ---------- Mobile menu ---------- */');
    var end = source.indexOf('/* ---------- Dropdown：');
    if (start === -1 || end === -1 || end <= start) {
        throw new Error('shared.js mobile menu block not found');
    }
    return source.slice(start, end);
}

var MOBILE_BLOCK = extractMobileMenuBlock();

/* ---------------- 對每個頁面跑行為測試 ---------------- */

PAGES.forEach(function (rel) {
    var file = path.isAbsolute(rel) ? rel : path.join(ROOT, rel);
    var html = fs.readFileSync(file, 'utf-8');
    var fragment = extractDropdown(html);
    console.log('\n=== ' + rel + ' ===');
    if (!fragment) { check(rel + ' 有 dropdown', false); return; }

    var dd = parseFragment(fragment)[0];
    check(rel + ' dropdown 節點解析成功', !!dd && dd._classes.indexOf('nav-dropdown') !== -1);
    check(rel + ' 有 3 個入口', dd.querySelectorAll('.nav-dropdown-item').length === 3);

    var items = dd.querySelectorAll('.nav-dropdown-item');
    var strongs = dd.querySelectorAll('.nav-dropdown-menu strong');
    check(rel + ' 入口標籤＝名詞圖解／坐禪與講經心智圖／問答錄2心智圖',
        strongs.length === 3
        && strongs[0].text.trim() === '名詞圖解'
        && strongs[1].text.trim() === '坐禪與講經心智圖'
        && strongs[2].text.trim() === '問答錄2心智圖');
    var hrefs = items.map(function (a) { return a.getAttribute('href') || ''; });
    check(rel + ' 入口連結指向三個保留頁',
        hrefs[0].indexOf('infographic.html') !== -1
        && hrefs[1].indexOf('mindmap.html') !== -1 && hrefs[1].indexOf('wenda2_') === -1
        && hrefs[2].indexOf('wenda2_mindmap.html') !== -1);

    DOCUMENT.activeElement = null;
    DOCUMENT._listeners = {};
    var toggle = dd.querySelector('.nav-dropdown-toggle');
    var menu = dd.querySelector('.nav-dropdown-menu');
    check(rel + ' 找得到 toggle 與 menu', !!toggle && !!menu);

    // 以 shared.js 的真實程式碼註冊事件
    var document = {
        querySelectorAll: function (selector) {
            return selector === '.nav-dropdown-toggle' ? [toggle] : [];
        },
        addEventListener: DOCUMENT.addEventListener
    };
    /* eslint-disable no-new-func */
    new Function('document', BLOCK)(document);

    check(rel + ' 初始 aria-expanded=false', toggle.getAttribute('aria-expanded') === 'false');

    toggle.dispatch('click');
    check(rel + ' 點擊後展開', dd._classes.indexOf('active') !== -1
        && toggle.getAttribute('aria-expanded') === 'true');

    toggle.dispatch('click');
    check(rel + ' 再點擊後收合', dd._classes.indexOf('active') === -1
        && toggle.getAttribute('aria-expanded') === 'false');

    toggle.dispatch('keydown', { key: 'ArrowDown' });
    check(rel + ' ArrowDown 展開並聚焦第一個連結',
        dd._classes.indexOf('active') !== -1
        && DOCUMENT.activeElement === menu.querySelector('a'));

    dd.dispatch('keydown', { key: 'Escape' });
    check(rel + ' Escape 收合並把焦點交回 toggle',
        dd._classes.indexOf('active') === -1
        && toggle.getAttribute('aria-expanded') === 'false'
        && DOCUMENT.activeElement === toggle);

    toggle.dispatch('click');
    var outside = new Element('div', {});
    DOCUMENT.dispatch('click', { target: outside });
    check(rel + ' 點擊外部收合', dd._classes.indexOf('active') === -1
        && toggle.getAttribute('aria-expanded') === 'false');

    toggle.dispatch('click');
    DOCUMENT.dispatch('click', { target: menu.querySelector('a') });
    check(rel + ' 點擊選單內部不誤收', dd._classes.indexOf('active') !== -1);

    /* -------- 手機版滑入面板：點「圖解」toggle 只開子選單、不收面板 -------- */

    // 重置全域監聽，只留 Mobile menu 區塊註冊的行為
    DOCUMENT._listeners = {};
    DOCUMENT.activeElement = null;
    dd.classList.remove('active');
    toggle.setAttribute('aria-expanded', 'false');

    var navMenuEl = new Element('div', { class: 'nav-menu', id: 'nav-menu' });
    var plainLink = new Element('a', { class: 'nav-link', href: 'index.html' });
    navMenuEl.appendChild(plainLink);
    navMenuEl.appendChild(dd); // 真實頁面的 dropdown（含 toggle）放進面板
    var hamburgerEl = new Element('button', { id: 'hamburger', class: 'hamburger', 'aria-expanded': 'false' });
    var veilEl = new Element('div', { id: 'site-menu-veil', class: 'site-menu-veil' });
    var bodyEl = new Element('body', {});
    bodyEl.style = {};

    var documentMobile = {
        getElementById: function (id) {
            if (id === 'hamburger') return hamburgerEl;
            if (id === 'nav-menu') return navMenuEl;
            if (id === 'site-menu-veil') return veilEl;
            return null;
        },
        createElement: function (tag) { return new Element(tag, {}); },
        addEventListener: DOCUMENT.addEventListener,
        body: bodyEl
    };
    /* eslint-disable no-new-func */
    new Function('document', 'window', MOBILE_BLOCK)(documentMobile, {
        addEventListener: function () {}
    });

    hamburgerEl.dispatch('click');
    check(rel + ' 手機：漢堡開啟滑入面板',
        navMenuEl._classes.indexOf('active') !== -1
        && hamburgerEl.getAttribute('aria-expanded') === 'true');

    toggle.dispatch('click');
    check(rel + ' 手機：點「圖解」toggle 展開子選單且面板不收',
        dd._classes.indexOf('active') !== -1
        && navMenuEl._classes.indexOf('active') !== -1);

    toggle.dispatch('click');
    check(rel + ' 手機：再點 toggle 收合子選單、面板仍在',
        dd._classes.indexOf('active') === -1
        && navMenuEl._classes.indexOf('active') !== -1);

    plainLink.dispatch('click');
    check(rel + ' 手機：點一般 nav-link 才會收面板',
        navMenuEl._classes.indexOf('active') === -1
        && hamburgerEl.getAttribute('aria-expanded') === 'false');
});

console.log('');
if (failures.length) {
    console.log('FAILED: ' + failures.length + ' assertion(s)');
    process.exit(1);
}
console.log('ALL DROPDOWN ASSERTIONS PASSED');
