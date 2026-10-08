  // ============================================================
  // 18-chapter-prefetch.js — 章節頁預取（暖機 Service Worker 快取）
  //
  // 「載入時間特別長」的主因之一：章節頁首訪要整檔下載（楞伽經 1.38MB →
  // gzip 392KB），而 sw.js 對電子書頁面採 stale-while-revalidate——
  // 只快取「造訪過」的頁面，每開一個新章節都重新下載一次。
  //
  // 本模組用兩個入口把章節頁提前塞進 SW 的 PAGES_CACHE：
  //   1. 指標／觸控／鍵盤聚焦即將點擊的連結（pointerenter、touchstart、
  //      focusin 事件代理）——點擊前先抓，使用者意圖明確，不受省流量
  //      設定限制（反正點下去也要下載同一份）。
  //   2. 首頁閒置時逐一預取同語言的全部章節頁（requestIdleCallback、
  //      低優先、逐一序列避免搶頻寬），讓「點任何一章」都近乎瞬開。
  //      受 navigator.connection 守門：saveData 或 2g/3g 不做整批預取。
  //
  // 預取走 fetch() → 經過 sw.js 的 fetch handler（isEbookHtml → swr()）
  // 直接寫入 PAGES_CACHE；同時也暖 HTTP 快取，SW 尚未接管時亦有幫助。
  // 跨語言頁（*_trad.html）刻意不預取，避免資料量翻倍；fetch 皆以
  // priority:'low' 發出（不支援的瀏覽器自動忽略此選項）。
  //
  // 以具名 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中）。
  // ============================================================
  ;(function () {
    // script.js 只在兩套電子書頁面載入，此為雙保險
    var path = window.location.pathname;
    if (!/^\/(wenda2_ebook|ebook)\//.test(path)) return;

    var prefetched = {};   // "pathname?search" -> true（去重；含進行中）
    var isTrad = (typeof isTraditionalChinesePage === 'function')
      && isTraditionalChinesePage();
    var isIndex = (typeof isIndexPage === 'function') ? isIndexPage() : false;

    // 只預取「同目錄、副檔名 .html、同語言、非本頁」的站內連結
    function linkTarget(raw) {
      if (!raw) return null;
      raw = String(raw).trim();
      if (/^(https?:|mailto:|tel:|data:)/i.test(raw)) return null;
      if (!/\.html?(\?|#|$)/i.test(raw)) return null;   // 純錨點/其他副檔名不取
      var url;
      try { url = new URL(raw, window.location.href); } catch (e) { return null; }
      if (url.origin !== window.location.origin) return null;
      if (url.pathname === window.location.pathname) return null;   // 本頁（含錨點）
      // 同目錄：根目錄與其他子站的導覽頁不預取
      var dir = window.location.pathname.replace(/[^/]*$/, '');
      if (url.pathname.indexOf(dir) !== 0) return null;
      // 語言變體：只預取與當前頁同語言的頁面，避免資料量翻倍
      if (/_trad\.html?$/i.test(url.pathname) !== isTrad) return null;
      return url;
    }

    function fetchKey(url) {
      return url.pathname + url.search;
    }

    function prefetch(url) {
      var key = fetchKey(url);
      if (prefetched[key]) return;
      prefetched[key] = true;
      var cached = (window.caches && window.caches.match)
        ? window.caches.match(key).catch(function () { return null; })
        : Promise.resolve(null);
      cached.then(function (hit) {
        // SW 已有此頁（含先前版本快取）→ 不重抓
        if (hit) return null;
        return fetch(key, { priority: 'low' });
      }).catch(function () {
        // 失敗靜默（離線、404、字檔大小寫……），解鎖讓懸停可重試
        delete prefetched[key];
        return null;
      });
    }

    // ---- 1. 指標即將點擊：事件代理預取 -------------------------------
    var onIntent = function (e) {
      var t = e.target;
      var a = (t && t.closest) ? t.closest('a[href]') : null;
      if (!a) return;
      var url = linkTarget(a.getAttribute('href'));
      if (url) prefetch(url);
    };
    document.addEventListener('pointerenter', onIntent, true);
    document.addEventListener('touchstart', onIntent, true);
    document.addEventListener('focusin', onIntent, true);

    // ---- 2. 首頁閒置：整批預取同語言章節頁 ---------------------------
    function bulkTargets() {
      var seen = {};
      var out = [];
      var links = document.querySelectorAll('a[href]');
      for (var i = 0; i < links.length; i++) {
        var url = linkTarget(links[i].getAttribute('href'));
        if (!url) continue;
        var key = fetchKey(url);
        if (seen[key]) continue;
        seen[key] = true;
        out.push(url);
      }
      return out;
    }

    function connectionAllowsBulk() {
      var c = navigator.connection || navigator.webkitConnection || null;
      if (!c) return true;          // 無資訊（多半為桌面/不限制）→ 允許
      if (c.saveData) return false; // 使用者要求省流量
      var t = c.effectiveType;
      if (t === 'slow-2g' || t === '2g' || t === '3g') return false;
      return true;
    }

    function runBulkPrefetch() {
      if (!isIndex || !connectionAllowsBulk()) return;
      var queue = bulkTargets();
      var i = 0;
      var step = function () {
        if (i >= queue.length) return;
        var url = queue[i++];
        var key = fetchKey(url);
        if (prefetched[key]) { step(); return; }
        prefetched[key] = true;
        var cached = (window.caches && window.caches.match)
          ? window.caches.match(key).catch(function () { return null; })
          : Promise.resolve(null);
        cached
          .then(function (hit) { return hit ? null : fetch(key, { priority: 'low' }); })
          .catch(function () { return null; })  // 失敗靜默，續下一個
          .then(step);                          // 逐一序列，不搶點擊的頻寬
      };
      step();
    }

    function idle(fn) {
      if (window.requestIdleCallback) {
        window.requestIdleCallback(fn, { timeout: 3000 });
      } else {
        setTimeout(fn, 1200);   // Safari 等無 rIC：load 後 1.2s 再開始
      }
    }

    if (document.readyState === 'complete') {
      idle(runBulkPrefetch);
    } else {
      window.addEventListener('load', function () { idle(runBulkPrefetch); });
    }
  })();
