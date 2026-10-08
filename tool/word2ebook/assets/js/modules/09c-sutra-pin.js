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
  //      2026-10 起講經系列由 books2ebook 在建置期直接輸出 host/group
  //      包層；本模組偵測到既有包層即沿用（host 偵測見程式碼、group 偵測
  //      見「包 sticky 群」段落），runtime 包法僅作為未包層頁面的後備。
  //   2. 再以「經文 → 邊界元素」為範圍包 .sutra-pin-group：邊界 = 下一段
  //      經文、任何 h1–h6（章節名/品名小節名）、任何圖片（figure/img），
  //      取文件順序最先者；章節尾（下一個 h2）之前若無這些邊界就到章節尾
  //      為止。sticky 的移動範圍被限制在 group 內，因此停留中的經文天生
  //      不可能蓋住下一段經文、章節名或圖片——會遮住之前就先讓位（歸位
  //      隨畫面捲走），正好呈現「永遠是最後看到的一段經文停留」。
  //   3. 過長（> 45% 視窗高，接近滿版）的經文整段不停留（.sutra-pin-tall
  //      → position: static）：停留中的經文會蓋住其後講解，經文若高到
  //      接近或超過整個畫面，就沒空間讀講解，該段一律放棄置頂。
  //   4. 「經文置頂」toggle（講次 h2 旁，localStorage sutraPinEnabled，
  //      預設 ON；關閉時 body.sutra-pin-off → 全部照常捲動）。
  //   5. 錨點跳轉讓位：把「本群經文停留時的高度 + 間隙」寫成群的
  //      --w2e-pin-reserve（04c-qa-audio.css 據此設 .para-block/標題的
  //      scroll-margin-top），使所有把目標對齊視窗頂的跳轉（外部連結、
  //      章節錨點、浮動目錄、書籤、.toc-count 直跳、?q= 搜尋結果）都會
  //      停在停留經文「下方」，不會被蓋住。經文高度隨字級/版面變化，
  //      故與過長判定一起在 scheduleTallCheck 重算。
  //   6. 另以 body.sutra-pin-suppress 在 hashchange／帶 hash 載入／
  //      程式化 scrollIntoView 時短路暫停停留，避免蓋住跳轉目標；
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
    // 經文高 > 55% 視窗高 → 不停留（至少留 45% 畫面讀講解）
    // 2026-09 由 0.45 提高：閱讀設定的預設字級 16→20px 後，同一段經文的行高
    // 多了 25%，45% 門檻等於把「可停留的經文長度」從約 16 行砍到 13 行，
    // 常見的段落長度會突然不再置頂。55% 讓原本的停留體驗回來。
    var TALL_RATIO = 0.55;
    // 錨點讓位時，目標段落頂端與停留經文底端之間留的白（避免緊貼）
    var RESERVE_GAP = 16;

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
    // 2026-10 起講經系列頁面由 books2ebook 在建置期直接輸出
    // .sutra-pin-group / .sutra-pin-host（結構靜態已知）；此處偵測到既有
    // 包層即沿用、跳過 DOM 手術——長文啟動不再插入/搬移近全頁的節點
    // （楞伽經 1482 群 ≈ 3000 次節點移動）。runtime 包法保留作為
    // 未包層頁面（舊產物/其他來源）的後備。
    var BOUNDARY_SEL = 'h1,h2,h3,h4,h5,h6,img,figure';
    var boundaries = Array.prototype.slice.call(
      document.body.querySelectorAll(BOUNDARY_SEL)
    );
    var bPtr = 0;
    var groups = [];
    sutras.forEach(function (s, i) {
      var host = hosts[i];
      var parent = host.parentNode;
      // 建置期包層：host 的父層已是群 → 直接採用，本段免手術
      if (parent.classList && parent.classList.contains('sutra-pin-group')) {
        groups.push(parent);
        return;
      }
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

    // ---- 過長經文不停留 + 錨點讓位高度 ----------------------------------
    // 停留中的經文天生會蓋住其後講解（sticky 本質）；經文若高到接近或超過
    // 整個畫面，停留後幾乎沒有空間讀講解，該段就放棄置頂。
    // 同時把「經文高 + 間隙」寫進群的 --w2e-pin-reserve：CSS 用它當群內
    // 目標（段落 / 標題 / label）的 scroll-margin-top，讓所有把目標對齊
    // 視窗頂的跳轉都停在停留經文下方。停用置頂（.sutra-pin-tall）或用
    // toggle 關閉置頂時歸零（此值為 inline style，樣式表覆寫無效，故
    // syncToggleUI 會觸發重算）。
    //
    // 長文啟動效能（2026-10）：量測改為「接近視窗才量」——
    //   · measuredGroups 記錄已量過的群；resize／字型／閱讀設定變化與
    //     toggle 重算只掃這些群，不再每次全頁（楞伽經 1482 群）掃一遍。
    //   · 未量過的群交 IntersectionObserver：進入視窗前緣（rootMargin
    //     100px）時量一次即退訂。此時經文已被 content-visibility 真實
    //     render，量到的是實際高度——舊版啟動即全量掃，視窗外群量到的
    //     全是 contain-intrinsic-size 的 240px 佔位值，讓位高度初始
    //     並不準；量過後 `contain-intrinsic-size: auto` 會記住實際高度，
    //     之後的觸發重算即使該群已捻出視窗也能量到正確值。
    //   · 未量群維持 CSS 預設 --w2e-pin-reserve: 0px（04c-qa-audio.css），
    //     行為與無經文置頂的頁面一致；錨點跳轉的路徑由 reserveFor()
    //     即時量測（目標必然已在視窗內、經文已 render）。
    //   · 讀寫分批：先讀完本批所有高度、再一次寫 class/inline style，
    //     避免逐群 read→write 交錯連續觸發 reflow（layout thrashing）。
    var measuredGroups = [];

    function measureGroups(list) {
      if (!list || !list.length) return;
      var vh = window.innerHeight;
      if (!vh) return;
      var heights = [];
      for (var i = 0; i < list.length; i++) {
        var st = list[i].firstElementChild && list[i].firstElementChild.firstElementChild;
        heights.push(st && st.classList.contains('sutra-text') ? st.offsetHeight : null);
      }
      for (var j = 0; j < list.length; j++) {
        var h = heights[j];
        if (h == null) continue;
        var g = list[j];
        var tall = h > vh * TALL_RATIO;
        g.classList.toggle('sutra-pin-tall', tall);
        g.style.setProperty('--w2e-pin-reserve',
                            (!pinOn || tall) ? '0px' : (h + RESERVE_GAP) + 'px');
        if (measuredGroups.indexOf(g) === -1) measuredGroups.push(g);
      }
    }

    function applyTallClasses() {
      measureGroups(measuredGroups);
    }

    // 未量群：進入視窗前緣量一次即退訂（尺寸其後的變化由下方
    // ResizeObserver / resize / style 觸發 applyTallClasses 重算）
    if (window.IntersectionObserver) {
      var groupObserver = new IntersectionObserver(function (entries) {
        var pending = [];
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          groupObserver.unobserve(en.target);
          pending.push(en.target);
        });
        measureGroups(pending);
      }, { rootMargin: '100px 0px' });
      groups.forEach(function (g) { groupObserver.observe(g); });
    } else {
      // 無 IO 支援：退回全量（行為同舊版）
      measureGroups(groups);
    }

    // 經文高度會隨閱讀設定（字級／行距／版面寬）、視窗縮放、字型或圖片載入
    // 而改變。若只在載入時量一次，使用者把字級調大後，原本不算高的經文可能
    // 變成接近滿版卻仍卡在置頂狀態（蓋住講解）；因此任何尺寸變化都重新量測
    // （重算範圍＝已量過的群，見 measureGroups 註解）。
    var tallScheduled = false;
    function scheduleTallCheck() {
      if (tallScheduled) return;
      tallScheduled = true;
      var run = function () { tallScheduled = false; applyTallClasses(); };
      if (window.requestAnimationFrame) window.requestAnimationFrame(run);
      else setTimeout(run, 50);
    }

    window.addEventListener('resize', scheduleTallCheck);
    window.addEventListener('orientationchange', scheduleTallCheck);
    window.addEventListener('load', scheduleTallCheck);
    if (window.ResizeObserver) {
      var tallObserver = new ResizeObserver(scheduleTallCheck);
      sutras.forEach(function (s) { tallObserver.observe(s); });
    }
    // 閱讀設定以 inline style 套在 <html>/<body> 上（--line-height、font-size、
    // max-width）：一起監看，變化時補一次量測。
    if (window.MutationObserver) {
      var tallStyleObserver = new MutationObserver(scheduleTallCheck);
      [document.documentElement, document.body].forEach(function (el) {
        if (el) tallStyleObserver.observe(el, {
          attributes: true, attributeFilter: ['style']
        });
      });
    }
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(scheduleTallCheck);
    }

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
      // 讓位高度是 inline style（優先級高於樣式表），關閉置頂時必須重算
      scheduleTallCheck();
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

    // 視窗頂 → 目標之間要留的高度（= 停留經文高度 + 間隙）。
    // 逐群寫在群的 --w2e-pin-reserve（CSS 端轉成 scroll-margin-top）；
    // 09b 跟播與 03d 錨點讓位直接呼叫本函式，兩者用同一個數字。
    // 置頂關閉或該經文過長（不會停留）時回 0。
    function reserveFor(el) {
      if (!pinOn || !el || !el.closest) return 0;
      var g = el.closest('.sutra-pin-group');
      if (!g || g.classList.contains('sutra-pin-tall')) return 0;
      var sutra = g.firstElementChild && g.firstElementChild.firstElementChild;
      return sutra && sutra.classList.contains('sutra-text')
        ? sutra.offsetHeight + RESERVE_GAP : 0;
    }

    // ---- 對外介面 ------------------------------------------------------
    window.W2E = window.W2E || {};
    window.W2E.sutraPin = {
      // 09b 跟播捲動前呼叫；03d 帶錨點載入時據此決定對齊方式
      reserveFor: reserveFor,
      isEnabled: function () { return pinOn; }
    };
  })();
