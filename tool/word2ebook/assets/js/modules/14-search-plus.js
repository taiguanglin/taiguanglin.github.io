// ============================================================
// 14-search-plus.js — 搜尋體驗補強
//
// ① 快捷鍵：index 頁按 「/」 或 Ctrl/Cmd+K 直接啟用並聚焦搜尋框。
// ② 結果鍵盤導覽：在搜尋框或結果區按 ↓/↑ 移動焦點（.kb-focus），
//    Enter 開啟該筆結果，Esc 收合焦點/關閉面板。
// ③ 章節頁關鍵字高亮：章節 URL 帶 ?q=（由「回到搜尋結果」流程附加）
//    且帶 #錨點時，把查詢詞在錨點所在區塊以 <mark class="w2e-hl">
//    標出，並 toast 命中數。只處理錨點區塊，避免全文標記造成卡頓。
// ============================================================

;(function () {
  function tt(sim, trad) {
    return (typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage()) ? trad : sim;
  }
  function isEditable(el) {
    return el && (el.closest('input, textarea, select, [contenteditable="true"]'));
  }

  // ---------- index 頁：快捷鍵 + 結果鍵盤導覽 --------------------------
  var input = document.getElementById('search-input');
  var results = document.getElementById('search-results');
  var resultsList = document.getElementById('search-results-list');

  if (input && results && resultsList) {
    document.addEventListener('keydown', function (e) {
      if (isEditable(e.target)) return;
      var focusHotkey = e.key === '/' ||
        ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K'));
      if (!focusHotkey) return;
      e.preventDefault();
      // 面板未啟用時，先點啟用鈕（沿用既有初始化流程，含進度提示）
      var activateBtn = document.getElementById('search-activate-btn');
      var container = document.getElementById('search-container');
      if (activateBtn && container && container.style.display === 'none') {
        activateBtn.click();
      }
      input.focus();
      input.select();
    });

    var focusIdx = -1;
    function items() {
      return Array.prototype.slice.call(resultsList.querySelectorAll('li, .search-result'));
    }
    function moveFocus(delta) {
      var list = items();
      if (!list.length) return;
      list.forEach(function (el) { el.classList.remove('kb-focus'); });
      focusIdx = (focusIdx + delta + list.length) % list.length;
      var el = list[focusIdx];
      el.classList.add('kb-focus');
      el.scrollIntoView({ block: 'nearest' });
    }
    function clearFocus() {
      focusIdx = -1;
      items().forEach(function (el) { el.classList.remove('kb-focus'); });
    }
    document.addEventListener('keydown', function (e) {
      if (results.style.display === 'none') return;
      if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus(-1); }
      else if (e.key === 'Enter' && focusIdx >= 0 && !isEditable(e.target)) {
        var list = items();
        if (list[focusIdx]) { e.preventDefault(); list[focusIdx].click(); }
      } else if (e.key === 'Escape' && focusIdx >= 0) {
        clearFocus();
      }
    });
    // 換搜尋/換頁後焦點失效
    resultsList.addEventListener('DOMSubtreeModified', clearFocus, { passive: true });
  }

  // ---------- 章節頁：?q= 關鍵字高亮（限錨點區塊） ----------------------
  var q = null;
  try { q = new URLSearchParams(window.location.search).get('q'); } catch (e) {}
  if (!q || !window.location.hash || typeof isIndexPage === 'function' && isIndexPage()) return;

  var terms = q.trim().split(/\s+/).filter(function (t) { return t.length >= 1; });
  if (!terms.length) return;

  var target = null;
  try { target = document.getElementById(decodeURIComponent(window.location.hash.slice(1))); } catch (e) {}
  if (!target) return;
  var block = target.closest('.question, .answer, .para-block') || target;

  // TreeWalker 走文字節點，逐詞包 <mark>（跳過既有互動元件）
  var SKIP = 'SCRIPT,STYLE,MARK,BUTTON,A,TEXTAREA';
  var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {
    acceptNode: function (node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      var p = node.parentNode;
      while (p && p !== block) {
        if (p.nodeType === 1 && SKIP.indexOf(p.tagName) !== -1) return NodeFilter.FILTER_REJECT;
        p = p.parentNode;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  var nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  var hits = 0;
  nodes.forEach(function (node) {
    var text = node.nodeValue;
    var lower = text;
    var matched = terms.filter(function (t) { return lower.indexOf(t) !== -1; });
    if (!matched.length) return;
    var frag = document.createDocumentFragment();
    var cursor = 0;
    // 逐字掃描找最早命中的詞（CJK 多為單字/詞級查詢）
    while (cursor < text.length) {
      var best = -1, bestTerm = null;
      for (var i = 0; i < matched.length; i++) {
        var idx = text.indexOf(matched[i], cursor);
        if (idx !== -1 && (best === -1 || idx < best)) { best = idx; bestTerm = matched[i]; }
      }
      if (best === -1) {
        frag.appendChild(document.createTextNode(text.slice(cursor)));
        break;
      }
      if (best > cursor) frag.appendChild(document.createTextNode(text.slice(cursor, best)));
      var mark = document.createElement('mark');
      mark.className = 'w2e-hl';
      mark.textContent = text.substr(best, bestTerm.length);
      frag.appendChild(mark);
      hits++;
      cursor = best + bestTerm.length;
    }
    node.parentNode.replaceChild(frag, node);
  });

  if (hits && typeof showToast === 'function') {
    showToast(tt('已在结果区块高亮 ', '已在結果區塊高亮 ') + hits + (isTraditionalChinesePage() ? ' 處「%s」'.replace('%s', q) : ' 处「%s」'.replace('%s', q)));
  }
})();
