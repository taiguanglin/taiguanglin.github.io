/* TaiGuangLin — sitewide Traditional/Simplified Chinese switching.
 *
 * Behaviour:
 *  - Preference resolution: localStorage('tgl-lang') > navigator.languages
 *    (zh-Hans / zh-CN / zh-SG / zh-MY → simp; other zh → trad; non-zh → trad).
 *  - Ebook areas (/wenda2_ebook/, /ebook/) already ship dual static pages
 *    (XX.html = simp, XX_trad.html = trad). There we redirect to the page
 *    matching the preference and persist the choice when the built-in
 *    .lang-switch links are clicked.
 *  - All other pages convert in place with OpenCC (opencc-js), in BOTH
 *    directions: authored text may be a mix (site chrome is Traditional, some
 *    article bodies are Simplified), and each text node is converted from its
 *    captured original toward the target script. A floating toggle button
 *    switches back and forth; the choice is remembered.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'tgl-lang';
    /* local first (jsDelivr 在部分網路環境不可達), CDN as fallback */
    var OPENCC_URLS = [
        '/vendor/opencc-full.js',
        'https://cdn.jsdelivr.net/npm/opencc-js@1.0.5/dist/umd/full.js',
        'https://unpkg.com/opencc-js@1.0.5/dist/umd/full.js'
    ];
    var EBOOK_DIRS = ['/wenda2_ebook/', '/ebook/'];

    /* ---------- preference ---------- */
    function getStored() {
        try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
    }
    function setStored(v) {
        try { localStorage.setItem(STORAGE_KEY, v); } catch (e) { /* private mode */ }
    }
    function detect() {
        var langs = navigator.languages || [navigator.language || ''];
        for (var i = 0; i < langs.length; i++) {
            var l = String(langs[i]).toLowerCase();
            if (l.indexOf('zh') !== 0) continue;
            if (l.indexOf('hans') !== -1) return 'simp';
            if (l.indexOf('hant') !== -1) return 'trad';
            if (/(zh-)?(cn|sg|my)/.test(l) || l === 'zh') return 'simp';
            return 'trad'; /* zh-TW / zh-HK / zh-MO ... */
        }
        return 'trad';
    }
    var pref = null;
    /* explicit ?lang=simp|trad wins for the current view (not stored) */
    try {
        var qp = new URLSearchParams(location.search).get('lang');
        if (qp === 'simp' || qp === 'trad') pref = qp;
    } catch (e) { /* very old browsers */ }
    if (!pref) pref = getStored();
    if (pref !== 'trad' && pref !== 'simp') { pref = detect(); }

    var path = location.pathname;
    var isEbook = EBOOK_DIRS.some(function (d) { return path.indexOf(d) === 0; });

    /* ---------- ebook mode: redirect between dual pages ---------- */
    if (isEbook) {
        /* directory URL (/ebook/) serves index.html — normalise first */
        var eff = /\/$/.test(path) ? path + 'index.html' : path;
        var m = eff.match(/^(.*?)(_trad)?\.html?$/i);
        if (m) {
            var base = m[1], isTradPage = !!m[2];
            var wantTrad = pref === 'trad';
            if (wantTrad !== isTradPage) {
                var target = wantTrad ? base + '_trad.html' : base + '.html';
                location.replace(target + location.search + location.hash);
                return;
            }
        }
        /* remember choice when the page's own switch links are used */
        document.addEventListener('click', function (e) {
            var a = e.target && e.target.closest ? e.target.closest('.lang-switch a') : null;
            if (!a) return;
            var t = (a.textContent || '').trim();
            if (t.indexOf('简体') !== -1 || t.indexOf('簡體') !== -1) setStored('simp');
            else if (t.indexOf('繁體') !== -1 || t.indexOf('繁体') !== -1) setStored('trad');
        }, true);
        /* also persist when any link points to a _trad / non-_trad counterpart */
        document.addEventListener('click', function (e) {
            var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
            if (!a) return;
            var href = a.getAttribute('href') || '';
            if (/_trad\.html/.test(href)) setStored('trad');
        }, true);
        return;
    }

    /* ---------- regular pages: in-place conversion ---------- */
    /* Displayed script, defaulting to the page's authored language. */
    var variant = 'trad';
    var working = null;      /* in-flight conversion promise (serialises toggles) */
    var openccLoading = null;
    var observer = null;

    function loadOpenCC() {
        if (openccLoading) return openccLoading;
        openccLoading = new Promise(function (resolve, reject) {
            if (window.OpenCC) { resolve(); return; }
            var i = 0;
            (function tryNext() {
                if (window.OpenCC) { resolve(); return; }
                if (i >= OPENCC_URLS.length) {
                    reject(new Error('OpenCC load failed from all sources'));
                    return;
                }
                var s = document.createElement('script');
                s.src = OPENCC_URLS[i++];
                s.onload = function () { resolve(); };
                s.onerror = function () { s.remove(); tryNext(); };
                document.head.appendChild(s);
            })();
        });
        return openccLoading;
    }

    /* Two directional converters: pages may be a MIX — site chrome is
     * Traditional but some article bodies (e.g. 實修故事 源自簡體原稿) are
     * Simplified. Each text node's original string is captured once, then
     * re-converted from that original in the chosen direction, so switching
     * back and forth is always correct regardless of the authored script. */
    var tw2cn = null, cn2tw = null;
    function ensureConverters() {
        if (!tw2cn) tw2cn = window.OpenCC.Converter({ from: 'tw', to: 'cn' });
        if (!cn2tw) cn2tw = window.OpenCC.Converter({ from: 'cn', to: 'tw' });
    }

    var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1 };
    var origText = new WeakMap();   /* node -> original nodeValue / attr originals */
    var origAttr = new WeakMap();   /* node -> {title, placeholder, alt} */

    function captureText(node) {
        if (!origText.has(node)) origText.set(node, node.nodeValue);
        return origText.get(node);
    }
    function captureAttr(node, name) {
        var map = origAttr.get(node);
        if (!map) { map = {}; origAttr.set(node, map); }
        if (!(name in map)) map[name] = node.getAttribute(name);
        return map[name];
    }

    function convertNode(node, cv) {
        if (node.nodeType === 3) {           /* TEXT_NODE */
            node.nodeValue = cv(captureText(node));
        } else if (node.nodeType === 1) {    /* ELEMENT_NODE */
            var tag = node.tagName;
            if (SKIP_TAGS[tag]) return;
            if (node.classList && node.classList.contains('ignore-opencc')) return;
            if (node.hasAttribute('title')) node.setAttribute('title', cv(captureAttr(node, 'title')));
            if (node.hasAttribute('placeholder')) node.setAttribute('placeholder', cv(captureAttr(node, 'placeholder')));
            if (node.hasAttribute('alt')) node.setAttribute('alt', cv(captureAttr(node, 'alt')));
            var kids = node.childNodes;
            for (var i = 0; i < kids.length; i++) convertNode(kids[i], cv);
        }
    }

    function currentTargetConverter() {
        return variant === 'simp' ? tw2cn : cn2tw;
    }

    /* Apply the given script everywhere. Never short-circuits: the page must
     * always be reconciled to the requested variant on load, because page
     * chrome and article body may be authored in different scripts. */
    function applyVariant(target) {
        if (target !== 'simp' && target !== 'trad') target = 'trad';
        var convert = function () {
            ensureConverters();
            stopObserver();
            convertNode(document.documentElement, target === 'simp' ? tw2cn : cn2tw);
            variant = target;
            document.documentElement.lang = target === 'simp' ? 'zh-CN' : 'zh-TW';
            startObserver();
            updateButton();
            fireReady();
            fireChange();
        };
        // Serialise conversions so a rapid click can't interleave walks.
        var prev = working;
        working = loadOpenCC().then(function () {
            if (prev) return prev.then(convert);
            return convert();
        });
        return working;
    }

    /* dynamic content (e.g. mindmap) re-converts while in target mode */
    var observerTimer = null;
    var converting = false;   /* reentrancy guard: our own writes must not re-trigger */
    function startObserver() {
        if (observer || !window.MutationObserver) return;
        observer = new MutationObserver(function (muts) {
            if (converting) return;
            var relevant = false;
            for (var i = 0; i < muts.length; i++) {
                if (muts[i].addedNodes && muts[i].addedNodes.length) { relevant = true; break; }
                if (muts[i].type === 'characterData') { relevant = true; break; }
            }
            if (!relevant) return;
            clearTimeout(observerTimer);
            observerTimer = setTimeout(function () {
                var cv = currentTargetConverter();
                converting = true;
                try {
                    for (var i = 0; i < muts.length; i++) {
                        var m = muts[i];
                        if (m.addedNodes && m.addedNodes.length) {
                            for (var j = 0; j < m.addedNodes.length; j++) {
                                var n = m.addedNodes[j];
                                /* 元素與文字節點都要轉（textContent= 會新增 TEXT_NODE） */
                                if (n.nodeType === 1 || n.nodeType === 3) convertNode(n, cv);
                            }
                        } else if (m.type === 'characterData' && m.target && m.target.nodeType === 3) {
                            var p = m.target.parentNode;
                            if (p && p.tagName && !SKIP_TAGS[p.tagName]) convertNode(m.target, cv);
                        }
                    }
                } finally {
                    converting = false;
                }
            }, 50);
        });
        observer.observe(document.body, {
            childList: true, subtree: true, characterData: true
        });
    }
    function stopObserver() {
        if (observer) { observer.disconnect(); observer = null; }
        clearTimeout(observerTimer);
    }

    /* ---------- floating toggle button ---------- */
    var BTN_ID = 'tgl-lang-toggle';
    var btnStyle = document.createElement('style');
    btnStyle.textContent =
        '#' + BTN_ID + '{position:fixed;right:18px;bottom:18px;z-index:9990;' +
        'display:inline-flex;align-items:center;gap:6px;padding:9px 16px;' +
        'border:none;border-radius:999px;cursor:pointer;font-size:14px;' +
        'font-family:inherit;line-height:1;color:#fff;' +
        'background:linear-gradient(135deg,#e978a7,#c93672);' +
        'box-shadow:0 6px 18px rgba(201,54,114,.35);transition:transform .15s ease,box-shadow .15s ease;}' +
        '#' + BTN_ID + ':hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(201,54,114,.45);}' +
        '#' + BTN_ID + ':focus-visible{outline:2px solid #a82a5d;outline-offset:2px;}';
    document.head.appendChild(btnStyle);

    var btn = null;
    function ensureButton() {
        if (btn || !document.body) return;
        btn = document.createElement('button');
        btn.id = BTN_ID;
        btn.type = 'button';
        btn.addEventListener('click', function () {
            var target = variant === 'simp' ? 'trad' : 'simp';
            pref = target; setStored(target);
            applyVariant(target).catch(function () { /* CDN failure: keep current */ });
        });
        document.body.appendChild(btn);
        updateButton();
    }
    function updateButton() {
        if (!btn) return;
        var isSimp = variant === 'simp';
        btn.textContent = isSimp ? '繁體' : '简体';
        btn.setAttribute('aria-label', isSimp ? '切換為繁體中文' : '切换为简体中文');
        btn.title = isSimp ? '切換為繁體中文' : '切换为简体中文';
    }

    /* ---------- 對外 API：供「每日精選」等自行管控轉換的區塊使用 ----------
     * 該類區塊加 class="ignore-opencc"（lang-switch 不代為轉換），改由 JS 呼叫
     * convertTW() 自行轉換，好掌握「內容已轉換才顯示」的時機。 */
    var readyHandlers = [];
    var changeHandlers = [];
    window.tgl_lang = {
        /* 目前顯示的 variant（'simp' | 'trad'） */
        getVariant: function () { return variant; },
        /* 將一份「繁體」字串轉成目前 variant；OpenCC 尚未載入時回 null */
        convertTW: function (s) {
            if (!window.OpenCC) return null;
            ensureConverters();
            return (variant === 'simp' ? tw2cn : cn2tw)(s);
        },
        /* 註冊「載入完成」「語系變更」回呼（可多次） */
        onReady: function (cb) { readyHandlers.push(cb); if (window.OpenCC) cb(); },
        onChange: function (cb) { changeHandlers.push(cb); }
    };
    function fireReady() { for (var i = 0; i < readyHandlers.length; i++) { try { readyHandlers[i](); } catch (e) {} } }
    function fireChange() { for (var i = 0; i < changeHandlers.length; i++) { try { changeHandlers[i](); } catch (e) {} } }

    function init() {
        ensureButton();
        /* Reconcile to the preferred variant in BOTH directions — a trad pref
         * must also convert (e.g. story bodies that are natively Simplified). */
        applyVariant(pref).catch(function () { /* CDN failure: keep as-authored */ });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
