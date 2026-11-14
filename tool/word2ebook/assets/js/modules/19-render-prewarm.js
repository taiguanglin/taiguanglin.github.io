  // ============================================================
  // 19-render-prewarm.js — 向下捲動前的背景預熱（預先渲染）
  //
  // 問題：00-base.css 對 .question/.answer/.para-block/article.qa-pair
  //       設了 `content-visibility: auto`——視窗外的區塊不排版也不繪製，
  //       只用 `contain-intrinsic-size: auto 240px` 的估計高度佔位。
  //       使用者向下捲動時，區塊要等瀏覽器「跑到附近」才渲染 → 捲動中
  //       會看到一列空白／內容慢半拍（章節越長越明顯）。
  //
  // 做法：背景先把「視窗下方一段區間」的區塊渲染好（content-visibility:
  //       visible），使用者捲到那裡時內容已經在畫面上，幾乎不用等待。
  //       - IntersectionObserver 的 rootMargin 向下擴張（預設 8 個視窗高），
  //         進入預熱區 → 加 .w2e-prewarmed；CSS 連帶把內層的 .question/
  //         .answer/.para-block 一起設為 visible（外層不 visible 時，
  //         內層再怎麼 visible 也不會被渲染）。
  //       - 捲到上方、離開預熱區 → 收回 .w2e-prewarmed，交回
  //         content-visibility 的「記憶高度」（contain-intrinsic-size: auto
  //         會記住上次渲染過的真實高度 → 收回不造成捲動位置跳動）。
  //       - 區塊內 loading="lazy" 的圖片一併改為 eager 並 decode()，
  //         免得捲到才開始下載。
  //       - 省流量/慢速網路（navigator.connection.saveData、2g/3g）時
  //         不預熱圖片（本地渲染預熱仍做）。
  //       - 沒有 IntersectionObserver 的瀏覽器 → 略過，維持原行為。
  //         實測（headless Chrome，問答錄2 04 章 2,020 則）：預熱 8 屏 ≈
  //         6,500px 的內文已渲染完成，且無 long task（分批處理的結果）。
  //       - 可用 window.W2E_PREWARM = { below: 2, images: false } 覆寫。
  //
  // 以獨立 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中，
  // 執行時 DOM 已就緒）。
  // ============================================================
  ;(function () {
    'use strict';

    // 首頁沒有長文捲動；只在章節頁運作
    if (typeof isIndexPage === 'function' && isIndexPage()) return;
    // 沒有 IntersectionObserver → 維持原行為
    if (!('IntersectionObserver' in window)) return;

    var CFG = (typeof window.W2E_PREWARM === 'object' && window.W2E_PREWARM) || {};

    function positive(v, fallback) {
      var n = Number(v);
      return (isFinite(n) && n > 0) ? n : fallback;
    }

    var BELOW = positive(CFG.below, 8);        // 預熱視窗倍數（視窗下方）
    var KEEP_ABOVE = positive(CFG.keepAbove, 0.5); // 視窗上方保留（避免剛捲過就重繪）
    var WARM_IMAGES = CFG.images !== false;   // 是否一併預熱圖片
    var BATCH = positive(CFG.batch, 8);       // 每批處理幾個區塊（避免一次掉幀）

    var CLASS = 'w2e-prewarmed';
    var SELECTOR = 'article.qa-pair, .para-block';

    var targets = document.querySelectorAll(SELECTOR);
    if (!targets.length) return;

    // ---- 圖片預熱 ---------------------------------------------------
    function imagesAllowed() {
      if (!WARM_IMAGES) return false;
      var c = navigator.connection || navigator.webkitConnection || null;
      if (!c) return true;              // 無連線資訊（多半桌面）→ 允許
      if (c.saveData) return false;     // 使用者要求省流量
      var t = c.effectiveType;
      return !(t === 'slow-2g' || t === '2g' || t === '3g');
    }

    function warmImages(el) {
      if (!imagesAllowed()) return;
      var imgs = el.querySelectorAll('img[loading="lazy"]');
      for (var i = 0; i < imgs.length; i++) {
        var img = imgs[i];
        // 尚未開始下載時改成 eager → 立即進 fetch 佇列
        img.setAttribute('loading', 'eager');
        // 預先解碼：捲到時不必再等 decode
        if (typeof img.decode === 'function') {
          try { img.decode().catch(function () { }); } catch (e) { /* 忽略 */ }
        }
      }
    }

    // ---- 預熱 / 收回 ------------------------------------------------
    function promote(el) {
      if (!el.classList.contains(CLASS)) el.classList.add(CLASS);
      warmImages(el);
    }

    function release(el) {
      el.classList.remove(CLASS);
    }

    // 進入預熱區的區塊分批處理（requestIdleCallback）：一次全改會讓瀏覽器
    // 在同一幀做完大量排版，反而造成掉幀；分批讓渲染落在閒置時段。
    var queue = [];
    var scheduled = false;

    function flush() {
      scheduled = false;
      var n = 0;
      while (queue.length && n < BATCH) {
        promote(queue.shift());
        n++;
      }
      if (queue.length) schedule();
    }

    function schedule() {
      if (scheduled) return;
      scheduled = true;
      if (window.requestIdleCallback) {
        window.requestIdleCallback(flush, { timeout: 500 });
      } else {
        setTimeout(flush, 32);
      }
    }

    // ---- IntersectionObserver：預熱區 -------------------------------
    var observer = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        if (entry.isIntersecting) {
          // 尚未預熱且未排進佇列 → 排入（避免同一區塊重複入列）
          if (!entry.target.classList.contains(CLASS) &&
              queue.indexOf(entry.target) === -1) queue.push(entry.target);
        } else {
          // 離開預熱區（往回捲）→ 收回；已經排進佇列的也要取消
          var idx = queue.indexOf(entry.target);
          if (idx !== -1) queue.splice(idx, 1);
          release(entry.target);
        }
      }
      if (queue.length) schedule();
    }, {
      // 預熱區＝視窗上方保留 KEEP_ABOVE 屏、視窗下方 BELOW 屏
      rootMargin: (-KEEP_ABOVE * 100) + '% 0px ' + (BELOW * 100) + '% 0px',
      threshold: 0
    });

    for (var j = 0; j < targets.length; j++) observer.observe(targets[j]);

    // 診斷用（除錯時可在 console 看預熱狀態）
    if (window.W2E) {
      window.W2E.prewarm = {
        className: CLASS,
        below: BELOW,
        keepAbove: KEEP_ABOVE,
        images: WARM_IMAGES,
        observer: observer
      };
    }
  })();
