// ============================================================
// 03b-bookmark-render.js — 书签渲染、首页书签、Toast 反馈
// ============================================================

// ------------------------------------------------------------------ //
// 书签添加反馈                                                        //
// ------------------------------------------------------------------ //

function showBookmarkAddedFeedback() {
  if (currentChapter.isHomepage) {
    showToast(getI18nText('bookmark.viewInSidebar', isTraditionalChinesePage(), '已添加到書籤，可在側邊欄查看'));
    _highlightBookmarkTab();
  } else {
    showEnhancedBookmarkToast();
  }
}

function _highlightBookmarkTab() {
  const floatingTOC = document.getElementById('floating-toc');
  const bookmarkTab = document.querySelector('.floating-toc-tab[data-tab="bookmarks"]');
  if (!floatingTOC || !bookmarkTab) return;

  const wasHidden = !floatingTOC.classList.contains('visible');
  if (wasHidden) floatingTOC.classList.add('visible');

  Object.assign(bookmarkTab.style, {
    background: '#ff69b4', color: 'white',
    transform: 'scale(1.1)', transition: 'all 0.3s ease',
    boxShadow: '0 2px 8px rgba(255, 105, 180, 0.5)',
  });
  setTimeout(() => {
    Object.assign(bookmarkTab.style, { background: '', color: '', transform: '', boxShadow: '' });
    if (wasHidden) setTimeout(() => floatingTOC.classList.remove('visible'), 1500);
  }, 1200);
}

// 章节页专用的增强 Toast
function showEnhancedBookmarkToast() {
  const toast = document.createElement('div');
  toast.className = 'bookmark-success-toast';
  toast.innerHTML = `
    <div class="toast-icon">🔖</div>
    <div class="toast-content">
      <div class="toast-title">書籤已添加！</div>
      <div class="toast-subtitle">點擊右下角 📖 查看所有書籤</div>
    </div>
  `;
  Object.assign(toast.style, {
    position: 'fixed', top: '20px', right: '20px',
    background: 'linear-gradient(135deg, #ff69b4, #e75480)',
    color: 'white', padding: '16px 20px', borderRadius: '12px',
    boxShadow: '0 8px 25px rgba(231, 84, 128, 0.3)',
    zIndex: '10000', transform: 'translateX(400px)',
    transition: 'all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    display: 'flex', alignItems: 'center', gap: '12px',
    maxWidth: '300px', fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
  });

  const style = document.createElement('style');
  style.textContent = `@keyframes bounce { 0% { transform:translateY(0); } 100% { transform:translateY(-6px); } }`;
  document.head.appendChild(style);
  document.body.appendChild(toast);

  setTimeout(() => { toast.style.transform = 'translateX(0)'; }, 100);
  setTimeout(() => {
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    setTimeout(() => {
      if (toast.parentNode) document.body.removeChild(toast);
      if (style.parentNode) document.head.removeChild(style);
    }, 400);
  }, 3500);
}

// ------------------------------------------------------------------ //
// 首页书签渲染                                                        //
// ------------------------------------------------------------------ //

function initializeHomepageTOC() {
  const tocList = document.getElementById('toc-list');
  const mainTOC = document.querySelector('.toc ul');
  if (tocList && mainTOC) {
    tocList.innerHTML = mainTOC.innerHTML;
    tocList.addEventListener('click', (e) => {
      if (e.target.tagName !== 'A') return;
      e.preventDefault();
      const href = e.target.getAttribute('href');
      if (href && href.startsWith('#')) {
        document.querySelector(href)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else if (href) {
        window.location.href = href;
      }
    });
  }
  refreshHomepageBookmarks();
  updateBookmarkCount();
}

function refreshHomepageBookmarks() {
  if (!currentChapter.isHomepage) return;
  const bookmarksList = document.getElementById('bookmarks-list');
  if (!bookmarksList) return;

  setTimeout(() => {
    const all = getBookmarks();
    if (!all.length) {
      bookmarksList.innerHTML = '<li class="bookmarks-empty">' +
        getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>';
      return;
    }
    if (all.length > 50) showBookmarkProcessingIndicator(all.length);
    processHomepageBookmarks(all);
  }, 10);
}

function showBookmarkProcessingIndicator(totalCount) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;
  el.innerHTML = `
    <div class="bookmark-loading-container">
      <div class="bookmark-loading-spinner">
        <div class="loading-text">處理 ${totalCount} 個書籤...</div>
      </div>
    </div>
  `;
}

function processHomepageBookmarks(allBookmarks) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;
  requestAnimationFrame(() => {
    const byChapter = {};
    allBookmarks.forEach(b => {
      const key = b.chapterTitle || '未知章節';
      (byChapter[key] = byChapter[key] || []).push(b);
    });
    const sorted = Object.keys(byChapter).sort((a, b) => {
      const num = t => { const m = t.match(/^(\d{1,2})/); return m ? parseInt(m[1], 10) : 999; };
      return num(a) - num(b);
    });
    renderBookmarkChaptersBatch(sorted, byChapter, 0);
  });
}

function renderBookmarkChaptersBatch(titles, byChapter, startIndex) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;

  const BATCH = 3;
  const end = Math.min(startIndex + BATCH, titles.length);
  if (startIndex === 0) el.innerHTML = '';

  for (let i = startIndex; i < end; i++) {
    const title = titles[i];
    const bookmarks = byChapter[title];
    const group = document.createElement('li');
    group.className = 'bookmark-chapter-group';

    let html = `<div class="bookmark-chapter-title">${title}</div><ul class="bookmark-chapter-list">`;
    bookmarks.forEach(b => {
      const isQA = b.type === 'qa-pair';
      const icon = isQA ? '💬' : '📝';
      const cls = isQA ? ' qa-pair-bookmark' : '';
      const link = (b.chapterFilename && b.elementId) ? `${b.chapterFilename}#${b.elementId}` : '#';
      html += `
        <li class="bookmark-item${cls}" data-bookmark-id="${b.id}">
          <div class="bookmark-meta">
            <span class="bookmark-type">${icon}</span>
            <span class="bookmark-questioner">${b.questioner || '匿名'}</span>
            <span class="bookmark-time">${b.time || ''}</span>
          </div>
          <div class="bookmark-preview">
            <a href="${link}" target="_blank" title="點擊跳轉到原問答">${b.preview || ''}</a>
          </div>
          <button class="bookmark-delete" data-bookmark-id="${b.id}" title="刪除書籤">✕</button>
        </li>
      `;
    });
    html += '</ul>';
    group.innerHTML = html;
    el.appendChild(group);
  }

  if (end < titles.length) {
    requestAnimationFrame(() => renderBookmarkChaptersBatch(titles, byChapter, end));
  } else {
    addHomepageBookmarkEventListeners();
  }
}

function addHomepageBookmarkEventListeners() {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;

  if (el.bookmarkClickHandler) el.removeEventListener('click', el.bookmarkClickHandler);

  const handler = (e) => {
    if (e.target.classList.contains('bookmark-delete')) {
      e.stopPropagation();
      removeBookmarkById(e.target.getAttribute('data-bookmark-id'));
      refreshHomepageBookmarks();
      updateBookmarkCount();
    } else if (!e.target.closest('a')) {
      const item = e.target.closest('.bookmark-item');
      if (item) jumpToBookmark(item.getAttribute('data-bookmark-id'));
    }
  };

  el.addEventListener('click', handler);
  el.bookmarkClickHandler = handler;
}
