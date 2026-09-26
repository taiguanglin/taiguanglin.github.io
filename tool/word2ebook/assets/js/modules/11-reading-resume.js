// ============================================================
// 11-reading-resume.js — 閱讀位置記憶 + 簡繁切換原位恢復
//
// ① 閱讀位置：捲動時（節流）與離頁前把「頁面 → 捲動比例」存入
//    localStorage('w2e:readpos')（上限 40 頁，LRU 淘汰）。再次進入同頁、
//    且 URL 無錨點時，頂部浮出「回到上次閱讀位置（XX%）」提示條；
//    點「回到位置」平滑捲回，點 ✕ 或 12 秒後自動消失。
//    **總目錄頁（index.html / index_trad.html）只有目錄、沒有正文**，
//    既不記錄也不提示（並清掉舊版留下的殘留紀錄）。
// ② 簡繁切換原位恢復：/lang-switch.js 在 ebook 雙頁跳轉前寫入
//    sessionStorage('w2e:langjump') = {id, frac}；本模組偵測到後直接
//    還原（優先同 id 錨點，其次比例），不顯示提示條。
// ============================================================

;(function () {
  var POS_KEY = 'w2e:readpos';
  var JUMP_KEY = 'w2e:langjump';
  var MAX_ENTRIES = 40;
  var SAVE_THROTTLE_MS = 500;

  function docFraction() {
    var doc = document.documentElement;
    var total = doc.scrollHeight - window.innerHeight;
    if (total <= 0) return 0;
    return Math.max(0, Math.min(1, (window.scrollY || 0) / total));
  }

  function scrollToFraction(frac, smooth) {
    var doc = document.documentElement;
    var total = doc.scrollHeight - window.innerHeight;
    if (total <= 0) return;
    var top = Math.round(frac * total);
    window.scrollTo(0, top);
    void smooth;
  }

  function readPositions() {
    try { return JSON.parse(localStorage.getItem(POS_KEY) || '{}'); } catch (e) { return {}; }
  }

  function writePositions(map) {
    try {
      var keys = Object.keys(map);
      if (keys.length > MAX_ENTRIES) {
        keys.sort(function (a, b) { return (map[a].ts || 0) - (map[b].ts || 0); });
        while (keys.length > MAX_ENTRIES) { delete map[keys.shift()]; }
      }
      localStorage.setItem(POS_KEY, JSON.stringify(map));
    } catch (e) { /* 隱私模式等 */ }
  }

  var pageKey = window.location.pathname;

  // 總目錄頁只有目錄、沒有正文，不適用「回到上次閱讀位置」
  function isTocOnlyPage() {
    return typeof isIndexPage === 'function' && isIndexPage();
  }

  function save() {
    if (isTocOnlyPage()) return;
    var frac = docFraction();
    if (frac <= 0) return;
    var map = readPositions();
    map[pageKey] = { frac: Math.round(frac * 1000) / 1000, ts: Date.now() };
    writePositions(map);
  }

  // 清掉總目錄頁的歷史紀錄（修正前的舊版會寫進來）
  function pruneTocOnlyEntries() {
    var map = readPositions();
    var changed = false;
    Object.keys(map).forEach(function (k) {
      var f = k.split('/').pop() || 'index.html';
      if (f === 'index.html' || f === 'index_trad.html') { delete map[k]; changed = true; }
    });
    if (changed) writePositions(map);
  }

  // ---- 簡繁切換原位恢復（優先於閱讀位置提示） --------------------------
  function tryLangJumpRestore() {
    var raw = null;
    try { raw = sessionStorage.getItem(JUMP_KEY); } catch (e) { return false; }
    if (!raw) return false;
    try { sessionStorage.removeItem(JUMP_KEY); } catch (e) {}
    var info = null;
    try { info = JSON.parse(raw); } catch (e) { return false; }
    if (!info) return false;
    setTimeout(function () {
      var el = info.id && document.getElementById(info.id);
      if (el) {
        el.scrollIntoView({ block: 'start' });
      } else if (typeof info.frac === 'number') {
        scrollToFraction(info.frac, false);
      }
    }, 60);
    return true;
  }

  // ---- 回到上次閱讀位置提示條 ------------------------------------------
  function showResumeBar(entry) {
    var isTrad = typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage();
    var pct = Math.round(entry.frac * 100);

    var bar = document.createElement('div');
    bar.className = 'w2e-resume-bar';
    bar.setAttribute('role', 'status');
    bar.innerHTML =
      '<span class="w2e-resume-text">' +
        (isTrad ? '上次讀到 ' + pct + '%' : '上次读到 ' + pct + '%') +
      '</span>' +
      '<button type="button" class="w2e-resume-go">' +
        (isTrad ? '回到位置' : '回到位置') +
      '</button>' +
      '<button type="button" class="w2e-resume-close" aria-label="' +
        (isTrad ? '關閉' : '关闭') + '">✕</button>';
    document.body.appendChild(bar);

    var dismissTimer = setTimeout(dismiss, 12000);
    requestAnimationFrame(function () { bar.classList.add('visible'); });

    function dismiss() {
      clearTimeout(dismissTimer);
      bar.classList.remove('visible');
      setTimeout(function () { bar.remove(); }, 300);
    }

    bar.querySelector('.w2e-resume-go').addEventListener('click', function () {
      dismiss();
      requestAnimationFrame(function () { scrollToFraction(entry.frac, true); });
    });
    bar.querySelector('.w2e-resume-close').addEventListener('click', dismiss);
  }

  function maybeOfferResume() {
    // 簡繁切換原位恢復優先（順帶清掉 sessionStorage 標記，避免外溢到下一頁）
    var jumped = tryLangJumpRestore();
    // 總目錄頁只有目錄、沒有正文 —— 不提示（並清掉舊版殘留紀錄）
    if (isTocOnlyPage()) { pruneTocOnlyEntries(); return; }
    // 帶錨點／搜尋跳轉進來時不打擾
    if (window.location.hash && window.location.hash.length > 1) return;
    if (jumped) return;
    var entry = readPositions()[pageKey];
    if (!entry) return;
    if (entry.frac < 0.03 || entry.frac > 0.98) return;
    var ageDays = (Date.now() - (entry.ts || 0)) / 86400000;
    if (ageDays > 30) return;
    showResumeBar(entry);
  }

  // ---- 持續記錄 ------------------------------------------------------
  var lastSave = 0;
  window.addEventListener('scroll', function () {
    var now = Date.now();
    if (now - lastSave < SAVE_THROTTLE_MS) return;
    lastSave = now;
    save();
  }, { passive: true });
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') save();
  });

  // 等首屏穩定後再判斷（避免與錨點跳轉、字型載入打架）
  setTimeout(maybeOfferResume, 400);
})();
