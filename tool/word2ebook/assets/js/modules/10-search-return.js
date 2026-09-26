// ============================================================
// 10-search-return.js — 「回到搜尋結果」浮動按鈕 + 搜尋狀態快照/還原
//
// 兩端配合（都在本 bundle 內）：
//   ① 章節頁：URL 帶 ?q=（由 index 的 buildSearchReturnUrl 附加）時，
//      顯示「回到搜尋結果」浮動按鈕，點擊返回 index.html?q=…#q=…；
//      離開前再把 TOC 展開快照寫一次（saveTocExpandSnapshot 定義於 06）。
//   ② index 頁：搜尋／分頁／捲動時把 {q, scope, displayed, scrollY}
//      存進 sessionStorage（per-tab），restoreSearchFromHash（01e）回來時
//      一併還原「已顯示筆數」與「捲動位置」。
// ============================================================

// 搜尋狀態快照鍵（sessionStorage：關閉分頁即失效，不同分頁互不干擾）
var W2E_SEARCH_SNAPSHOT_KEY = 'w2eSearchSnapshot';

// 讀取快照；解析失敗視同無快照
function readSearchSnapshot() {
  try {
    var raw = sessionStorage.getItem(W2E_SEARCH_SNAPSHOT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

// 寫入快照（q 為空字串時直接移除鍵）
function writeSearchSnapshot(state) {
  try {
    if (state && state.q && String(state.q).trim()) {
      sessionStorage.setItem(W2E_SEARCH_SNAPSHOT_KEY, JSON.stringify(state));
    } else {
      sessionStorage.removeItem(W2E_SEARCH_SNAPSHOT_KEY);
    }
  } catch (e) { /* 隱私模式等；忽略 */ }
}

// ------------------------------------------------------------
// index 頁：持續記錄 {q, scope, displayed, scrollY}
// ------------------------------------------------------------

// 由目前 UI 狀態組快照並寫入 sessionStorage
function captureSearchSnapshot() {
  if (!isIndexPage()) return;
  var input = document.getElementById('search-input');
  if (!input) return;
  var q = (input.value || '').trim();
  if (!q || q.length < 2) return; // 無有效查詢就不留快照
  writeSearchSnapshot({
    q: q,
    scope: (typeof searchScope !== 'undefined' && searchScope) || 'both',
    displayed: (typeof displayedResultsCount !== 'undefined') ? displayedResultsCount : 0,
    scrollY: Math.round(window.scrollY || 0)
  });
}

// index 頁啟動：接上持續快照（節流）
function initSearchSnapshotCapture() {
  if (!isIndexPage()) return;

  var lastWrite = 0;
  function throttledCapture() {
    var now = Date.now();
    if (now - lastWrite < 400) return;
    lastWrite = now;
    captureSearchSnapshot();
  }

  window.addEventListener('scroll', throttledCapture, { passive: true });
  window.addEventListener('pagehide', captureSearchSnapshot);

  // 分頁「顯示更多／全部」改變 displayedResultsCount → 立即快照
  ['search-load-more', 'search-load-all', 'search-load-more-bottom', 'search-load-all-bottom'].forEach(function (id) {
    var btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', function () { setTimeout(captureSearchSnapshot, 0); });
  });
}

// ------------------------------------------------------------
// index 頁：還原捲動位置（01e 的 restoreSearchFromHash 呼叫）
// ------------------------------------------------------------

// 還原上次離開時的捲動位置；targetY 明確傳入，不重讀快照（避免還原途中
// 自己的 scroll 快照蓋寫目標值造成追逐迴圈）
function restoreSearchScroll(targetY) {
  if (typeof targetY !== 'number' || targetY <= 0) {
    var snap = readSearchSnapshot();
    if (!snap || typeof snap.scrollY !== 'number' || snap.scrollY <= 0) return;
    targetY = snap.scrollY;
  }

  var tries = 0;
  var maxTries = 20; // 最多約 2 秒；版面（字型/圖片）就緒後停
  var timer = setInterval(function () {
    tries++;
    // 查詢已變更（使用者自己改了關鍵字）→ 放棄舊位置
    var input = document.getElementById('search-input');
    var q = input ? (input.value || '').trim() : '';
    if (!q || q.length < 2) {
      clearInterval(timer);
      return;
    }
    window.scrollTo(0, targetY);
    var settled = (Math.abs(window.scrollY - targetY) < 4) || tries >= maxTries;
    if (settled) clearInterval(timer);
  }, 100);
}

// ------------------------------------------------------------
// 章節頁：「回到搜尋結果」浮動按鈕
// ------------------------------------------------------------

function getSearchReturnUrl() {
  var snap = readSearchSnapshot();
  if (!snap || !snap.q) return null;
  var isTrad = isTraditionalChinesePage();
  var indexPage = isTrad ? 'index_trad.html' : 'index.html';
  // pathname 可能是 …/wenda2_ebook/01.html 或 …/ebook/05.html；
  // scope 同時放 query 與 hash（hash 是 restoreSearchFromHash 的主要來源）
  var scopePart = (snap.scope && snap.scope !== 'both') ? '&scope=' + encodeURIComponent(snap.scope) : '';
  return indexPage +
    '?q=' + encodeURIComponent(snap.q) + scopePart +
    '#q=' + encodeURIComponent(snap.q) + scopePart;
}

// 按鈕定位：避開浮動層級控制（桌面右下 120px 起）與 QA 播放器
function applySearchReturnBtnPosition(btn) {
  var isMobile = window.innerWidth <= 600;
  var bottomPx = isMobile ? 130 : 120;
  var floatingControls = document.getElementById('floating-level-controls');
  if (floatingControls && floatingControls.style.display === 'block') {
    // 浮動層級控制顯示中 → 再往上讓位
    bottomPx += (isMobile ? 160 : 120);
  }
  // QA 底部播放器顯示中 → 讓位到播放器上方
  var qaPlayer = document.querySelector('.qa-player.visible');
  if (qaPlayer) bottomPx += 100;
  btn.style.bottom = bottomPx + 'px';
}

// 在章節頁建立/顯示「回到搜尋結果」按鈕
function initSearchReturnButton() {
  if (isIndexPage()) return;
  if (document.getElementById('search-return-btn')) return;
  if (!getSearchReturnUrl()) return; // 沒有快照 → 不顯示

  var isTrad = isTraditionalChinesePage();
  var btn = document.createElement('button');
  btn.id = 'search-return-btn';
  btn.className = 'search-return-btn';
  btn.type = 'button';
  btn.innerHTML = '🔍 ' + getI18nText('search.returnToResults', isTrad, '回到搜尋結果');
  btn.title = getI18nText('search.returnToResultsTitle', isTrad, '返回首頁並還原上次的搜尋結果');
  btn.setAttribute('aria-label', btn.title);

  btn.addEventListener('click', function () {
    // 離開前補寫 TOC 展開快照（saveTocExpandSnapshot 定義於 06-toc-collapse.js）
    if (typeof saveTocExpandSnapshot === 'function') {
      try { saveTocExpandSnapshot(); } catch (e) { /* 非致命 */ }
    }
    var url = getSearchReturnUrl();
    if (url) window.location.href = url;
  });

  document.body.appendChild(btn);
  applySearchReturnBtnPosition(btn);

  // 浮動層級控制顯示/隱藏時重新定位（07 的 handleScroll 會改它的 display）
  window.addEventListener('scroll', function () {
    applySearchReturnBtnPosition(btn);
  }, { passive: true });
  window.addEventListener('resize', function () {
    applySearchReturnBtnPosition(btn);
  }, { passive: true });
}

initSearchSnapshotCapture();
initSearchReturnButton();
