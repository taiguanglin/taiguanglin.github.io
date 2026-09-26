// ============================================================
// 16-jump-share.js — 目錄計數直跳主題第一則問答／標題分享連結／
//                     ebook 無跟播章節提示
//
// ① 章節目錄的 .toc-count「(50)」變成可點：跳到該主題下第一則
//    .question（沒有問題的主題退回原錨點行為）。
// ② h2/h3 帶 id 的標題在 hover/focus 時顯示 🔗 錨點鈕，點擊複製
//    「頁面#錨點」連結（沿用 03d 的 copyText + 02 的穩定 ID）。
// ③ /ebook/ 講經頁（含 .para-block）若全頁無 .qa-play 播放鈕，
//    在 h1 後插一句「本講次尚無音檔跟播」提示，避免使用者以為壞掉。
// ============================================================

;(function () {
  function tt(sim, trad) {
    return (typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage()) ? trad : sim;
  }

  // ---------- ① .toc-count → 主題第一則問答 ---------------------------
  function headingLevel(el) { return parseInt(el.tagName.slice(1), 10); }

  function firstQuestionInSection(heading) {
    var level = headingLevel(heading);
    var cur = heading.nextElementSibling;
    while (cur) {
      if (/^H[2-6]$/.test(cur.tagName) && headingLevel(cur) <= level) break;
      if (cur.classList && cur.classList.contains('question')) return cur;
      var found = cur.querySelector && cur.querySelector('.question');
      if (found) return found;
      cur = cur.nextElementSibling;
    }
    return null;
  }

  document.querySelectorAll('.toc-count').forEach(function (badge) {
    var li = badge.closest('li');
    if (!li) return;
    var link = li.querySelector('a[href^="#"]');
    if (!link) return;
    badge.setAttribute('role', 'button');
    badge.setAttribute('tabindex', '0');
    badge.title = tt('跳到本主题第一则问答', '跳到本主題第一則問答');
    function go(e) {
      e.preventDefault();
      e.stopPropagation();
      var id = link.getAttribute('href').slice(1);
      var heading = document.getElementById(id);
      if (!heading) return;
      var q = firstQuestionInSection(heading);
      var target = q || heading;
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (q) {
        q.classList.remove('anchor-target-highlight');
        void q.offsetWidth;
        q.classList.add('anchor-target-highlight');
        setTimeout(function () { q.classList.remove('anchor-target-highlight'); }, 3000);
      }
      try { history.replaceState(null, '', '#' + target.id); } catch (_) {}
    }
    badge.addEventListener('click', go);
    badge.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') go(e);
    });
  });

  // ---------- ② 標題錨點分享 -------------------------------------------
  if (typeof isIndexPage !== 'function' || !isIndexPage()) {
    document.querySelectorAll('h2[id], h3[id]').forEach(function (h) {
      if (h.querySelector('.anchor-share')) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'anchor-share';
      btn.textContent = '🔗';
      btn.title = tt('复制本节链接', '複製本節連結');
      btn.setAttribute('aria-label', btn.title);
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var url = window.location.origin + window.location.pathname + '#' + h.id;
        if (typeof copyText === 'function') copyText(url);
        else if (navigator.clipboard) navigator.clipboard.writeText(url);
      });
      h.appendChild(btn);
    });
  }

  // ---------- ③ ebook 無跟播章節提示 ------------------------------------
  if (window.location.pathname.indexOf('/ebook/') !== -1 &&
      document.querySelector('.para-block') &&
      !document.querySelector('button.qa-play')) {
    var h1 = document.querySelector('main h1, h1');
    if (h1) {
      var note = document.createElement('p');
      note.className = 'no-audio-note';
      note.textContent = tt(
        '本讲次暂未提供音档跟播（音档校对中，敬请见谅）。',
        '本講次暫未提供音檔跟播（音檔校對中，敬請見諒）。');
      h1.insertAdjacentElement('afterend', note);
    }
  }
})();
