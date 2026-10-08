// ============================================================
// 10-search-return.js — 搜尋狀態快照/還原 + 簡繁切換原位恢復
//
// 兩端配合（都在本 bundle 內）：
//   ① index 頁：搜尋／分頁／捲動時把 {q, scope, displayed, scrollY}
//      存進 sessionStorage（per-tab），restoreSearchFromHash（01e）回來時
//      一併還原「已顯示筆數」與「捲動位置」。
//   ② 簡繁切換原位恢復：/lang-switch.js 在 ebook 雙頁跳轉前寫入
//      sessionStorage('w2e:langjump') = {id, frac}；本模組偵測到後直接
//      還原（優先同 id 錨點，其次比例），讀完即清。
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
// 「回到搜尋結果」浮動按鈕已於 2026-09 移除（行為依賴 sessionStorage
// 快照跨分頁複製，在 noopener 新分頁下多數情況拿不到快照、出現時機不穩）。
// 保留 index 頁的搜尋狀態快照：使用者直接用瀏覽器返回/回到 index 時
// 仍由 01e 的 restoreSearchFromHash 還原查詢與捲動位置。
// ------------------------------------------------------------

// ------------------------------------------------------------
// 簡繁切換原位恢復（原 11-reading-resume.js 的 ②；該模組已移除）
//
// /lang-switch.js 在 ebook 雙頁跳轉前寫入 sessionStorage('w2e:langjump')
// = {id, frac}：本端偵測到後直接還原（優先同 id 錨點，其次比例），讀完即清。
// 總目錄頁只有目錄沒有正文，也照樣消化（避免標記外溢到下一頁）。
// ------------------------------------------------------------
function scrollToFraction(frac) {
  var doc = document.documentElement;
  var total = doc.scrollHeight - window.innerHeight;
  if (total <= 0) return;
  window.scrollTo(0, Math.round(frac * total));
}

function tryLangJumpRestore() {
  var raw = null;
  try { raw = sessionStorage.getItem('w2e:langjump'); } catch (e) { return false; }
  if (!raw) return false;
  try { sessionStorage.removeItem('w2e:langjump'); } catch (e) {}
  var info = null;
  try { info = JSON.parse(raw); } catch (e) { return false; }
  if (!info) return false;
  setTimeout(function () {
    var el = info.id && document.getElementById(info.id);
    if (el) {
      el.scrollIntoView({ block: 'start' });
    } else if (typeof info.frac === 'number' && info.frac > 0) {
      scrollToFraction(info.frac);
    }
  }, 60);
  return true;
}

tryLangJumpRestore();

initSearchSnapshotCapture();
