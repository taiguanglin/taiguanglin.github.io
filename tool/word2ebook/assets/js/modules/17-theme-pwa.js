// ============================================================
// 17-theme-pwa.js — 深色面板配色（粉夜/墨夜）＋ PWA 註冊
//
// ① 深色模式第二套配色「墨夜」（中性深灰＋暖金，適合長時間夜讀）：
//    偏好存 localStorage('w2e:darkPalette')，'neutral' 時於
//    body 掛 .dark-neutral（防閃爍由模板 prepaint 腳本掛到 <html>）。
//    工具欄主題列由 02-reader-ux.js 產生第三顆鈕，事件在 04-events.js。
// ② PWA：/wenda2_ebook/ 與 /ebook/ 下註冊 /sw.js，離線可開曾讀頁面；
//    音檔刻意不快取（避免佔滿裝置儲存）。
// ============================================================

;(function () {
  // ---- 深色面板配色 ----
  function applyPalette() {
    var dark = document.body.classList.contains('dark-mode');
    var neutral = false;
    try { neutral = localStorage.getItem('w2e:darkPalette') === 'neutral'; } catch (e) {}
    document.body.classList.toggle('dark-neutral', dark && neutral);
    document.documentElement.classList.remove('dark-neutral');
  }
  applyPalette();

  // 主題切換（04-events.js 點 theme-* 鈕改 body.dark-mode）後跟隨重評估
  var mo = new MutationObserver(function (muts) {
    for (var i = 0; i < muts.length; i++) {
      if (muts[i].type === 'attributes') { applyPalette(); break; }
    }
  });
  mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });

  window.W2E = window.W2E || {};
  W2E.darkPalette = function (name) {
    try {
      if (name === 'neutral' || name === 'pink') localStorage.setItem('w2e:darkPalette', name);
      else localStorage.removeItem('w2e:darkPalette');
    } catch (e) {}
    applyPalette();
  };

  // 更新工具欄按鈕狀態（供 04-events.js 的 theme 事件呼叫）
  W2E.updateDarkPaletteButtons = function () {
    var neutral = false;
    try { neutral = localStorage.getItem('w2e:darkPalette') === 'neutral'; } catch (e) {}
    var btn = document.querySelector('[data-action="theme-dark-neutral"]');
    if (btn) btn.classList.toggle('active', neutral);
  };
  W2E.updateDarkPaletteButtons();

  // ---- PWA ----
  var inEbook = /^\/(wenda2_ebook|ebook)(\/|$)/.test(window.location.pathname);
  if (inEbook && 'serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  }
})();
