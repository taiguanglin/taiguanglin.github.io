// ============================================================
// 15-mobile-toc.js — 手機版目錄操作
//
// ① 行動裝置（≤768px）開啟浮動目錄時鋪半透明 backdrop，
//    點 backdrop 即關閉（等效點目錄的 ✕）。
// ② 手勢：自螢幕左緣（≤28px 起點）右滑 >70px 開啟目錄；
//    目錄內左滑 >70px 關閉。
//
// 「回到頂端」只保留在右下角功能選單（☰ → ↑，見 02-reader-ux.js
// `data-action="top"`），不再另做常駐懸浮鈕。
// ============================================================

;(function () {
  function isMobileView() { return window.innerWidth <= 768; }

  // ---------- backdrop ----------
  var backdrop = document.createElement('div');
  backdrop.className = 'w2e-toc-backdrop';
  document.body.appendChild(backdrop);

  function tocEl() { return document.querySelector('.floating-toc'); }
  function tocVisible() {
    var toc = tocEl();
    return !!toc && (toc.classList.contains('visible') || toc.classList.contains('is-open'));
  }
  function closeToc() {
    var toc = tocEl();
    if (!toc) return;
    var close = toc.querySelector('.ctrl-btn[data-action="close-toc"], [data-action="close-toc"]');
    if (close) { close.click(); return; }
    toc.classList.remove('visible');
    syncBackdrop();
  }
  function openToc() {
    var btn = document.querySelector('.action-btn[data-action="toc"]');
    if (btn) btn.click();
    setTimeout(syncBackdrop, 50);
  }
  function syncBackdrop() {
    backdrop.classList.toggle('visible', isMobileView() && tocVisible());
  }
  backdrop.addEventListener('click', closeToc);

  // 目錄 class 變化 → 同步 backdrop（也涵蓋電腦版縮放視窗的情形）
  var mo = new MutationObserver(syncBackdrop);
  function observeToc() { var t = tocEl(); if (t) mo.observe(t, { attributes: true, attributeFilter: ['class'] }); }
  observeToc();
  window.addEventListener('resize', syncBackdrop);

  // ---------- 手勢 ----------
  var startX = 0, startY = 0, tracking = false, fromPanel = false;
  document.addEventListener('touchstart', function (e) {
    if (!isMobileView() || e.touches.length !== 1) return;
    var x = e.touches[0].clientX;
    var inToc = !!(e.target.closest && e.target.closest('.floating-toc'));
    if (x <= 28 || inToc) {
      tracking = true;
      fromPanel = inToc;
      startX = x; startY = e.touches[0].clientY;
    }
  }, { passive: true });
  document.addEventListener('touchend', function (e) {
    if (!tracking) return;
    tracking = false;
    var t = e.changedTouches[0];
    var dx = t.clientX - startX, dy = t.clientY - startY;
    if (Math.abs(dy) > 60) return;
    if (!fromPanel && dx > 70 && !tocVisible()) openToc();
    else if (fromPanel && dx < -70 && tocVisible()) closeToc();
  }, { passive: true });
})();
