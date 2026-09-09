  // ============================================================
  // 09c-sutra-pin.js — 講經「經文置頂」（原經文原尺寸停留）
  //
  // 適用頁面：章節內含 .sutra-text 原經文（quote 區塊，講經系列與坐禅2）。
  // 向下捲動時，把「即將捲出視窗頂」的那段原經文停在視窗最上方，呈現
  // 「畫面繼續捲動、上方經文段落卻停留」的閱讀效果（Confluence 固定表頭
  // 概念）；不管有沒有開啟段落跟播都會生效。
  //
  // 做法：原生 position: sticky——停留中的經文就是原版經文本身，原尺寸、
  // 原樣式、無白邊；講解段落從它下方滑過。
  //
  //   1. 為每段經文包一層 .sutra-pin-host（只包層、不搬動順序，sticky 的
  //      定位單位），09b-para-track 以 nextElementSibling 掃描段落的邏輯
  //      照常運作（.para-block 節點不變）。
  //   2. 再以「經文 → 邊界元素」為範圍包 .sutra-pin-group：邊界 = 下一段
  //      經文、任何 h1–h6（章節名/品名小節名）、任何圖片（figure/img），
  //      取文件順序最先者；章節尾（下一個 h2）之前若無這些邊界就到章節尾
  //      為止。sticky 的移動範圍被限制在 group 內，因此停留中的經文天生
  //      不可能蓋住下一段經文、章節名或圖片——會遮住之前就先讓位（歸位
  //      隨畫面捲走），正好呈現「永遠是最後看到的一段經文停留」。
  //   3. 過長（> 60% 視窗高，接近滿版）的經文整段不停留（.sutra-pin-tall
  //      → position: static），避免看不到其餘內容。
  //   4. 「經文置頂」toggle（講次 h2 旁，localStorage sutraPinEnabled，
  //      預設 ON；關閉時 body.sutra-pin-off → 全部照常捲動）。    //   5. 錨點跳轉（hashchange／帶 hash 載入／程式化 scrollIntoView）時短暫
    //      body.sutra-pin-suppress 停停留，避免蓋住目錄/搜尋/書籤跳轉目標；
    //      09b 跟播捲動前可呼叫 W2E.sutraPin.reserveFor(el) 取得停留經文
    //      高度作為捲動上限（當前段頂 − 經文高 − 24px），使高亮段落永遠
    //      落在停留經文下方、不被蓋住。
  //
  // 以具名 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中）。
  // ============================================================
  ;(function () {
    if (typeof isIndexPage === 'function' && isIndexPage()) return;

    var sutras = Array.prototype.slice.call(
      document.querySelectorAll('.sutra-text')
    );
    if (!sutras.length || !document.body) return;

    var PIN_KEY = 'sutraPinEnabled';
    var TALL_RATIO = 0.6;            // 經文高 > 60% 視窗高 → 不停留

    function loadState(key, dflt) {
      try {
        var v = localStorage.getItem(key);
        return v == null ? dflt : v === '1';
      } catch (e) {
        return dflt;
      }
    }

    function saveState(key, val) {
      try { localStorage.setItem(key, val ? '1' : '0'); } catch (e) {}
    }

    var pinOn = loadState(PIN_KEY, true);

    function isTrad() {
      return typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage();
    }

    function spText(key, fallback) {
      if (typeof getI18nText === 'function') {
        return getI18nText(key, isTrad(), fallback, {});
      }
      return fallback;
    }

    function isBefore(a, b) {
      return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    }

    // el 在 container 的直接子層祖先（el 位於 container 子樹內時才有值）
    function topLevelWithin(el, container) {
      while (el && el.parentNode !== container) el = el.parentNode;
      return el && el.parentNode === container ? el : null;
    }

    // ---- 為每段經文包 host（只包層，不改變 DOM 順序）-------------------
    var hosts = [];
    sutras.forEach(function (s) {
      var parent = s.parentNode;
      if (!parent) return;
      if (parent.classList && parent.classList.contains('sutra-pin-host')) {
        hosts.push(parent);
        return;
      }
      var host = document.createElement('div');
      host.className = 'sutra-pin-host';
      parent.insertBefore(host, s);
      host.appendChild(s);
      hosts.push(host);
    });
    if (!hosts.length) return;

    // ---- 包 sticky 群：經文 → 下一邊界 ----------------------------------
    // 邊界（文件順序取最先者）：下一段經文的 host、h1–h6 章節名/小節名、
    // figure/img 圖片。sticky 範圍被限制在群內 → 停留中的經文永遠蓋不到
    // 這些元素（群底緣最多貼齊邊界頂緣）。指標依文件順序單向推進，O(n)。
    var BOUNDARY_SEL = 'h1,h2,h3,h4,h5,h6,img,figure';
    var boundaries = Array.prototype.slice.call(
      document.body.querySelectorAll(BOUNDARY_SEL)
    );
    var bPtr = 0;
    var groups = [];
    sutras.forEach(function (s, i) {
      var host = hosts[i];
      var parent = host.parentNode;
      var group = document.createElement('div');
      group.className = 'sutra-pin-group';

      // 推進邊界指標到本經文之後，取第一個 h/img 邊界
      while (bPtr < boundaries.length &&
             !isBefore(s, boundaries[bPtr])) bPtr++;
      var endEl = null;
      for (var k = bPtr; k < boundaries.length; k++) {
        var b = boundaries[k];
        if (!isBefore(s, b)) continue;
        if (host.contains(b)) continue;
        endEl = b;
        break;
      }

      // 候選收尾點（映射到本經文父節點的直接子層）：下一段經文的 host、
      // 第一個 h/img 邊界；取文件順序最前者為群尾。
      var cands = [];
      if (sutras[i + 1]) {
        var nh = topLevelWithin(hosts[i + 1], parent);
        if (nh && nh !== host && isBefore(host, nh)) cands.push(nh);
      }
      if (endEl) {
        var eh = topLevelWithin(endEl, parent);
        if (eh && eh !== host && isBefore(host, eh)) cands.push(eh);
      }
      var endRef = null;
      for (var c = 0; c < cands.length; c++) {
        if (!endRef || isBefore(cands[c], endRef)) endRef = cands[c];
      }

      // 群佔據經文原位（不能插在邊界處，否則經文會被搬到講解後面）；
      // 再把 host 之後、群尾之前的兄弟節點依序搬進群（不改變順序）
      parent.insertBefore(group, host);
      group.appendChild(host);
      while (group.nextElementSibling && group.nextElementSibling !== endRef) {
        group.appendChild(group.nextElementSibling);
      }
      groups.push(group);
    });

    // ---- 章節（h2）→ 群清單（用於 toggle 放置與跨章節自然失效）----------
    var sections = [];          // [{h2, groups: [Element]}]
    var pre = { h2: null, groups: [] };
    var cur = null;
    Array.prototype.slice.call(
      document.body.querySelectorAll('h2, .sutra-pin-group')
    ).forEach(function (el) {
      if (el.tagName === 'H2') {
        cur = { h2: el, groups: [] };
        sections.push(cur);
      } else if (cur) {
        cur.groups.push(el);
      } else {
        pre.groups.push(el);
      }
    });
    if (pre.groups.length) sections.unshift(pre);

    // ---- 過長經文不停留 --------------------------------------------------
    function applyTallClasses() {
      var vh = window.innerHeight;
      if (!vh) return;
      groups.forEach(function (g) {
        var sutra = g.firstElementChild &&
                    g.firstElementChild.firstElementChild;
        if (!sutra || !sutra.classList.contains('sutra-text')) return;
        g.classList.toggle('sutra-pin-tall',
                           sutra.offsetHeight > vh * TALL_RATIO);
      });
    }
    applyTallClasses();
    window.addEventListener('resize', applyTallClasses);
    // 字型/圖片載入後高度可能變化，load 時再量一次
    window.addEventListener('load', applyTallClasses);

    // ---- 「經文置頂」toggle（講次 h2 旁，樣式沿用段落跟播）--------------
    var toggles = [];
    var toggleLabel = spText('sutraPin.toggle', '經文置頂');
    sections.forEach(function (sec) {
      if (!sec.h2 || !sec.groups.length) return;
      var t = document.createElement('label');
      t.className = 'sutra-pin-toggle';
      t.title = toggleLabel;
      var box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = pinOn;
      box.setAttribute('aria-label', toggleLabel);
      var txt = document.createElement('span');
      txt.textContent = toggleLabel;
      t.appendChild(box);
      t.appendChild(txt);
      // 插入順序：排在「段落跟播」toggle 之後（無則排在 .qa-play 之後）
      var play = sec.h2.querySelector('.qa-play');
      var track = sec.h2.querySelector('.para-track-toggle');
      if (track) track.parentNode.insertBefore(t, track.nextSibling);
      else if (play) play.parentNode.insertBefore(t, play.nextSibling);
      else sec.h2.appendChild(t);
      toggles.push(t);
      box.addEventListener('change', function () {
        pinOn = box.checked;
        saveState(PIN_KEY, pinOn);
        syncToggleUI();
      });
    });

    function syncToggleUI() {
      if (document.body) {
        document.body.classList.toggle('sutra-pin-off', !pinOn);
      }
      toggles.forEach(function (t) {
        t.classList.toggle('on', pinOn);
        t.setAttribute('aria-pressed', pinOn ? 'true' : 'false');
        var box = t.querySelector('input[type="checkbox"]');
        if (box && box.checked !== pinOn) box.checked = pinOn;
      });
    }

    syncToggleUI();

    // ---- 錨點跳轉保護：短暫停停留，避免蓋住跳轉目標 ----------------------
    var suppressTimer = null;
    function suppressPin(ms) {
      if (!document.body) return;
      document.body.classList.add('sutra-pin-suppress');
      if (suppressTimer) clearTimeout(suppressTimer);
      suppressTimer = setTimeout(function () {
        document.body.classList.remove('sutra-pin-suppress');
        suppressTimer = null;
      }, ms || 450);
    }

    // 攔截 scrollIntoView：目錄/搜尋/書籤的程式化捲動先停停留再捲
    // （否則捲動目標會被停留中的經文蓋住）
    var origScrollIntoView = Element.prototype.scrollIntoView;
    if (origScrollIntoView) {
      Element.prototype.scrollIntoView = function () {
        suppressPin(600);
        return origScrollIntoView.apply(this, arguments);
      };
    }
    window.addEventListener('hashchange', function () { suppressPin(600); });
    // 帶錨點載入：目標會停在視窗最頂
    if (location.hash) suppressPin(800);

    // ---- 對外介面：供 09b-para-track 讓出停留經文的高度 ------------------
    window.W2E = window.W2E || {};
    window.W2E.sutraPin = {
      // 跟播捲動前呼叫：目標段落若屬於某個 sticky 群，回傳該群經文高度
      // （捲動後這段經文會停在視窗頂；09b 以「段頂 − 此高度 − 24px」為
      // 捲動上限，使高亮段落落在停留經文下方）
      reserveFor: function (el) {
        if (!pinOn || !el || !el.closest) return 0;
        var g = el.closest('.sutra-pin-group');
        if (!g || g.classList.contains('sutra-pin-tall')) return 0;
        var sutra = g.firstElementChild && g.firstElementChild.firstElementChild;
        return sutra && sutra.classList.contains('sutra-text')
          ? sutra.offsetHeight : 0;
      },
      isEnabled: function () { return pinOn; }
    };
  })();
