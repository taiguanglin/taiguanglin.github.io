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
                /* U10 簡繁切換保留閱讀位置：記下目前最近的標題錨點與捲動比例，
                 * 目標頁的 11-reading-resume.js 據此原位恢復。 */
                try {
                    var jump = { id: null, frac: 0 };
                    var doc = document.documentElement;
                    var total = doc.scrollHeight - window.innerHeight;
                    jump.frac = total > 0 ? (window.pageYOffset || 0) / total : 0;
                    var hs = document.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
                    for (var i = 0; i < hs.length; i++) {
                        if (hs[i].getBoundingClientRect().top <= 120) jump.id = hs[i].id;
                        else break;
                    }
                    sessionStorage.setItem('w2e:langjump', JSON.stringify(jump));
                } catch (e) { /* ignore */ }
                location.replace(target + location.search);
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
    /* ---------- 一對多誤轉修正（與 tool/word2ebook/utils/i18n_utils.py 同源） ----------
     * OpenCC 的 cn→tw 與 Python 的 s2tw/s2twp 一樣，會在某些前綴後把一簡多繁字
     * 誤轉：只→隻（别只坐→別隻坐）、发→髮（乱发愿→亂髮願）、后→後漏轉
     * （东西后→東西后）、里→裡漏轉（剧本里写的→劇本里寫的）。以下四個修正層
     * 與 i18n_utils.py 同源同字集，兩份必須同步維護：
     *   - 副詞「只」後面接動詞／助動詞；量詞「隻」前面是數詞／量詞性指示詞、
     *     後面接名詞 → 「隻」的後一字在副詞後接字集合、且前一字非數量詞時改回
     *     「只」；固定詞（隻字、隻身、隻手、船隻…）自然保留。
     *   - 「髮」後接髮類名詞、或前接毛髮修飾字時保留，其餘改回「發」。
     *   - 「后」前接皇后類字、或後接皇后類名詞時保留，其餘改成「後」。
     *   - 「里」前接「裡面」類前綴時改成「裡」；距離／音譯「里」保留。
     * 用字元迴圈而非 regex lookbehind，避免舊瀏覽器（Safari < 16.4）語法錯誤。 */
    var ZHI_MEASURE =
        '一二三四五六七八九十兩零百千萬億幾數壹貳參肆伍陸柒捌玖拾０１２３４５６７８９0123456789' +
        '多第半每另某各此';
    var ZHI_FOLLOWER =
        '能會要可得想須應該肯願是有好不在知道說講念唸寫認看去下度吃喝給做求等待差欠' +
        '顧管剩怕見為留談聽針受跟提叫過關放思接穿傳夠允動信走用把將顯對供選挑問答' +
        '立覺靠考更授屬坐支取加建消創打向專' +
        '修讓買賣睡站練幫來停存當限許記';
    var FA_FOLLOWER =
        '願現生出音揮作展菩善悶火熱財明動言表射放送芽炎燒洩誓怒愁呆抖達號脾瘋楞起揚緊哮酵汗黃脹';
    var FA_HAIR_PREV = '頭白脫長短掉毛理染燙捲金黑銀假鬚削落洗護美禿鬢結披散束拔';
    var FA_HAIR_NEXT = '際型絲夾膠根量質色梢網飾辮';
    var QUEEN_PREV = '皇太呂武蟻王神褒妲媽';
    var QUEEN_NEXT = '土羿稷冠宮娘妃主座';
    var LI_INSIDE_PREV = '本道會角方場子迴穴識經向梅相包';
    var YUN_SAY_NEXT = '：:';
    var MIAN_FACE_NEXT = '容部對臨向貌目孔色前';
    /* 「云」（說）與「麵」（臉義）修正如上：簡體「云」兼表說／雲，往返後
     * 「師云：」全被寫成「師雲：」——引句冒號前的「雲」改回「云」；簡體
     * 「面」兼表臉／麵，「面貌和面容」被寫成「麵容」——臉義接字前的「麵」
     * 改回「面」。真正的雲（雲朵／虛雲和尚）與麵（麵條／泡麵）不受影響。 */
    function _inSet(set, ch) { return !!ch && set.indexOf(ch) !== -1; }
    function fixOnlyZhi(text) {
        if (text.indexOf('隻') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '隻' && !_inSet(ZHI_MEASURE, i > 0 ? text.charAt(i - 1) : '') &&
                _inSet(ZHI_FOLLOWER, text.charAt(i + 1) || '')) {
                out += '只';
                continue;
            }
            out += ch;
        }
        return out;
    }
    function fixFaHair(text) {
        if (text.indexOf('髮') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '髮') {
                var nxt = text.charAt(i + 1) || '';
                var prev = i > 0 ? text.charAt(i - 1) : '';
                if (_inSet(FA_FOLLOWER, nxt) ||
                    (!_inSet(FA_HAIR_PREV, prev) && !_inSet(FA_HAIR_NEXT, nxt))) {
                    out += '發';
                    continue;
                }
            }
            out += ch;
        }
        return out;
    }
    function fixHou(text) {
        if (text.indexOf('后') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '后' && !_inSet(QUEEN_PREV, i > 0 ? text.charAt(i - 1) : '') &&
                !_inSet(QUEEN_NEXT, text.charAt(i + 1) || '')) {
                out += '後';
                continue;
            }
            out += ch;
        }
        return out;
    }
    function fixLi(text) {
        if (text.indexOf('里') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '里' && _inSet(LI_INSIDE_PREV, i > 0 ? text.charAt(i - 1) : '')) {
                out += '裡';
                continue;
            }
            out += ch;
        }
        return out;
    }
    function fixYun(text) {
        if (text.indexOf('雲') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '雲' && _inSet(YUN_SAY_NEXT, text.charAt(i + 1) || '')) {
                out += '云';
                continue;
            }
            out += ch;
        }
        return out;
    }
    function fixMian(text) {
        if (text.indexOf('麵') === -1) return text;
        var out = '';
        for (var i = 0; i < text.length; i++) {
            var ch = text.charAt(i);
            if (ch === '麵' && _inSet(MIAN_FACE_NEXT, text.charAt(i + 1) || '')) {
                out += '面';
                continue;
            }
            out += ch;
        }
        return out;
    }
    /* 詞層級誤轉／片語劫持殘留（與 i18n_utils.variant_char_map 同源，須同步）。
     * 順序即替換順序：長詞在前。 */
    var PHRASE_FIXES = [
        ['復雜', '複雜'], ['乾擾', '干擾'], ['盡量', '儘量'],
        ['直麵人生', '直面人生'],
        /* 量詞前綴（一／多…）壓住的副詞「只」（與 i18n_utils._CONTEXT_FIXES 同步） */
        ['最多隻能', '最多只能'], ['最多隻是', '最多只是'],
        ['差不多隻有', '差不多只有'], ['業很多隻能', '業很多只能'],
        ['三幹大幹世界', '三千大千世界'], ['幹世界', '千世界'],
    ];
    function fixPhrases(text) {
        for (var i = 0; i < PHRASE_FIXES.length; i++) {
            if (text.indexOf(PHRASE_FIXES[i][0]) !== -1) {
                text = text.split(PHRASE_FIXES[i][0]).join(PHRASE_FIXES[i][1]);
            }
        }
        return text;
    }
    function ensureConverters() {
        if (!tw2cn) tw2cn = window.OpenCC.Converter({ from: 'tw', to: 'cn' });
        if (!cn2tw) {
            var raw = window.OpenCC.Converter({ from: 'cn', to: 'tw' });
            cn2tw = function (s) {
                return fixPhrases(fixMian(fixYun(fixLi(fixHou(fixFaHair(fixOnlyZhi(raw(s))))))));
            };
        }
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
            /* 文字節點本身沒有 class，需看父元素：.ignore-opencc 底下的字一律保留原樣
             * （例如切換鈕上的「繁體／简体」必須永遠顯示目標語系的正確字形）。 */
            var tp = node.parentNode;
            if (tp && tp.classList && tp.classList.contains('ignore-opencc')) return;
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
        /* 按鈕文字刻意「不」隨頁面轉換：在簡體頁面顯示繁體「繁體」，
         * 在繁體頁面顯示簡體「简体」，標示的是「按下去會切到哪一種字」。 */
        btn.className = 'ignore-opencc';
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
