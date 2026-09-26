// ============================================================
// 12-bookmarks-manager.js — 首頁「我的書籤」跨章節管理區塊
//
// 浮動面板的書籤分頁只能看到清單；這裡在 index 主內容插入一個
// 可收合的管理區塊：按章節分組列出所有書籤（章名＋摘錄＋時間），
// 每筆可「跳轉」（同分頁前往 chapter.html#elementId）或「刪除」，
// 底部可「清空全部書籤」（confirm）。
// 資料來源與 03a 共用 localStorage 鍵（簡/繁分開）。
// ============================================================

;(function () {
  if (typeof isIndexPage !== 'function' || !isIndexPage()) return;
  if (typeof getBookmarks !== 'function') return;

  function tt(sim, trad) {
    return (typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage()) ? trad : sim;
  }

  var section = document.createElement('section');
  section.className = 'w2e-bm-manager';
  section.innerHTML =
    '<h2 class="w2e-bm-title">' +
      '<button type="button" class="w2e-bm-fold" aria-expanded="false">▸</button>' +
      '🔖 ' + tt('我的书签', '我的書籤') + ' <span class="w2e-bm-count"></span>' +
    '</h2>' +
    '<div class="w2e-bm-body" hidden></div>';

  var anchor = document.getElementById('main-toc');
  if (anchor && anchor.parentNode) {
    anchor.parentNode.insertBefore(section, anchor.nextSibling);
  } else {
    var main = document.querySelector('main');
    if (main) main.appendChild(section);
  }

  var body = section.querySelector('.w2e-bm-body');
  var foldBtn = section.querySelector('.w2e-bm-fold');

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function render() {
    var all = getBookmarks();
    section.querySelector('.w2e-bm-count').textContent = '(' + all.length + ')';

    if (!all.length) {
      body.innerHTML = '<p class="w2e-bm-empty">' + tt('尚无书签', '尚無書籤') + '</p>';
      return;
    }

    // 按章節分組（保持原始加入順序）
    var groups = {};
    var order = [];
    all.forEach(function (b) {
      var key = b.chapterFilename || '?';
      if (!groups[key]) { groups[key] = []; order.push(key); }
      groups[key].push(b);
    });

    var html = '';
    order.forEach(function (file) {
      var items = groups[file];
      var title = esc(items[0].chapterTitle || (items[0].chapter && items[0].chapter.title) || file);
      html += '<div class="w2e-bm-group">' +
        '<div class="w2e-bm-chapter">' + title + ' <span>(' + items.length + ')</span></div><ul>';
      items.forEach(function (b) {
        html += '<li class="w2e-bm-item" data-id="' + esc(b.id) + '" ' +
          'data-file="' + esc(b.chapterFilename || '') + '" data-el="' + esc(b.elementId || '') + '">' +
          '<a class="w2e-bm-jump" href="' + esc(b.chapterFilename || '') + '#' + esc(b.elementId || '') + '">' +
            esc(b.preview || '') +
          '</a>' +
          '<div class="w2e-bm-meta">' +
            '<span>' + esc(b.questioner || '') + (b.time ? ' · ' + esc(b.time) : '') + '</span>' +
            '<button type="button" class="w2e-bm-del" title="' + tt('删除', '刪除') + '" aria-label="' + tt('删除书签', '刪除書籤') + '">✕</button>' +
          '</div>' +
        '</li>';
      });
      html += '</ul></div>';
    });
    html += '<button type="button" class="w2e-bm-clearall">' + tt('清空全部书签', '清空全部書籤') + '</button>';
    body.innerHTML = html;
  }

  foldBtn.addEventListener('click', function () {
    var open = body.hidden;
    body.hidden = !open;
    foldBtn.textContent = open ? '▾' : '▸';
    foldBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) render();
  });

  body.addEventListener('click', function (e) {
    var del = e.target.closest('.w2e-bm-del');
    if (del) {
      var li = del.closest('.w2e-bm-item');
      if (li && typeof removeBookmarkById === 'function') {
        removeBookmarkById(li.dataset.id);
        render();
      }
      return;
    }
    if (e.target.closest('.w2e-bm-clearall')) {
      var all = getBookmarks();
      if (!all.length) return;
      if (!confirm(tt('确定要清空全部 ' + all.length + ' 个书签吗？此操作无法撤销。',
                      '確定要清空全部 ' + all.length + ' 個書籤嗎？此操作無法撤銷。'))) return;
      if (typeof saveBookmarks === 'function') saveBookmarks([]);
      render();
    }
  });

  render(); // 只更新標題計數；內容於展開時渲染
})();
