// ============================================================
// 03a-bookmark-data.js — 书签存储、CRUD、章节检测、视觉标识
// ============================================================

// 当前文件章节信息（在 DOMContentLoaded 后设置）
let currentChapter;

// 获取当前语言版本的 localStorage 键
function getBookmarkStorageKey() {
  return isTraditionalChinesePage() ? 'ebook-bookmarks-traditional' : 'ebook-bookmarks-simplified';
}

// 迁移旧版统一书签到按语言分离的结构（只执行一次）
function migrateOldBookmarks() {
  if (localStorage.getItem('bookmarks-migrated')) return;

  const oldData = localStorage.getItem('ebook-bookmarks');
  if (!oldData) { localStorage.setItem('bookmarks-migrated', 'true'); return; }

  try {
    const all = JSON.parse(oldData);
    const simplified = all.filter(b => !(b.chapterFilename && b.chapterFilename.includes('_trad.html')));
    const traditional = all.filter(b => b.chapterFilename && b.chapterFilename.includes('_trad.html'));
    if (simplified.length) localStorage.setItem('ebook-bookmarks-simplified', JSON.stringify(simplified));
    if (traditional.length) localStorage.setItem('ebook-bookmarks-traditional', JSON.stringify(traditional));
    localStorage.removeItem('ebook-bookmarks');
    localStorage.setItem('bookmarks-migrated', 'true');
    console.log(`书签迁移完成: 简体 ${simplified.length} 个, 繁体 ${traditional.length} 个`);
  } catch (e) {
    console.error('书签迁移失败:', e);
    localStorage.setItem('bookmarks-migrated', 'true');
  }
}

// 读取书签列表（可选按章节 ID 过滤）
function getBookmarks(chapterId = null) {
  migrateOldBookmarks();
  const raw = localStorage.getItem(getBookmarkStorageKey());
  const all = raw ? JSON.parse(raw) : [];
  return chapterId ? all.filter(b => b.chapter && b.chapter.id === chapterId) : all;
}

function getCurrentChapterBookmarks() {
  return getBookmarks(currentChapter.id);
}

// 持久化书签列表并更新计数显示
function saveBookmarks(bookmarks) {
  localStorage.setItem(getBookmarkStorageKey(), JSON.stringify(bookmarks));
  updateBookmarkCount();
}

// 根据当前页面 URL 和 h1 构建章节信息对象
function getCurrentChapter() {
  const filename = (window.location.pathname.split('/').pop()) || 'index.html';
  if (filename === 'index.html' || filename === 'index_trad.html') {
    return {
      title: getI18nText('navigation.homepage', isTraditionalChinesePage(), '首頁'),
      id: 'homepage',
      isHomepage: true,
    };
  }
  const h1 = document.querySelector('h1');
  const title = (h1 ? h1.textContent.trim() : document.title) || '未知章節';
  return { title, id: filename.replace('.html', ''), filename, isHomepage: false };
}

// 为元素查找所属章节（直接使用 currentChapter）
function findChapterForElement(_element) {
  return { title: currentChapter.title, id: currentChapter.id, filename: currentChapter.filename };
}

// ------------------------------------------------------------------ //
// 视觉标识                                                            //
// ------------------------------------------------------------------ //

function addBookmarkVisualIndicator(element) {
  if (element.classList.contains('bookmarked')) return;
  element.classList.add('bookmarked');
  if (!element.querySelector('.bookmark-indicator')) {
    const span = document.createElement('span');
    span.className = 'bookmark-indicator';
    span.textContent = '🔖';
    span.title = getI18nText('bookmark.removeBookmark', isTraditionalChinesePage(), '點擊移除書籤');
    element.appendChild(span);
  }
}

function removeBookmarkVisualIndicator(element) {
  element.classList.remove('bookmarked');
  const indicator = element.querySelector('.bookmark-indicator');
  if (indicator) element.removeChild(indicator);
}

function restoreBookmarkVisualStates() {
  getBookmarks().forEach(bookmark => {
    const el = document.getElementById(bookmark.elementId);
    if (!el) return;
    addBookmarkVisualIndicator(el);
    if (bookmark.type === 'qa-pair') {
      if (el.classList.contains('question')) {
        const ans = findAnswerForQuestion(el);
        if (ans) addBookmarkVisualIndicator(ans);
      } else if (el.classList.contains('answer')) {
        const q = findQuestionForAnswer(el);
        if (q) addBookmarkVisualIndicator(q);
      }
    }
  });
}

// ------------------------------------------------------------------ //
// CRUD 操作                                                           //
// ------------------------------------------------------------------ //

function toggleBookmark(element) {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }

  const bookmarks = getBookmarks();
  const isQuestion = element.classList.contains('question');
  const isAnswer = element.classList.contains('answer');
  if (!isQuestion && !isAnswer) return;

  element.id = element.id || ('bookmark-' + Date.now());
  const id = element.id;
  const existing = bookmarks.find(b => b.elementId === id);

  if (existing) {
    removeBookmarkVisualIndicator(element);
    saveBookmarks(bookmarks.filter(b => b.elementId !== id));
    renderBookmarks();
    showToast('已從書籤移除');
    return;
  }

  let questioner = '', time = '', preview = '';
  if (isQuestion) {
    questioner = element.querySelector('.questioner')?.textContent || '匿名';
    time = element.querySelector('.question-time')?.textContent || '';
    preview = (element.querySelector('.question-text')?.textContent || '').substring(0, 100) + '...';
  } else {
    questioner = element.querySelector('.answerer')?.textContent || 'Taiguanglin';
    preview = (element.querySelector('.answer-text')?.textContent || '').substring(0, 100) + '...';
  }

  bookmarks.push({
    id: 'bookmark-' + Date.now(),
    elementId: id,
    type: isQuestion ? 'question' : 'answer',
    questioner, time, preview,
    chapter: findChapterForElement(element),
    chapterTitle: currentChapter.title,
    chapterFilename: currentChapter.filename,
    timestamp: new Date().toLocaleString(),
  });
  saveBookmarks(bookmarks);
  addBookmarkVisualIndicator(element);
  renderBookmarks();
  showBookmarkAddedFeedback();
}

function toggleQAPairBookmark(answerElement) {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }

  const bookmarks = getBookmarks();
  const questionElement = findQuestionForAnswer(answerElement);

  const targetEl = questionElement || answerElement;
  targetEl.id = targetEl.id || ('qa-question-' + Date.now());
  if (!answerElement.id) answerElement.id = 'qa-answer-' + Date.now();
  const targetId = targetEl.id;

  const existing = bookmarks.find(b => b.elementId === targetId);
  if (existing) {
    removeBookmarkVisualIndicator(answerElement);
    if (questionElement) removeBookmarkVisualIndicator(questionElement);
    saveBookmarks(bookmarks.filter(b => b.elementId !== targetId));
    renderBookmarks();
    showToast('已從書籤移除問答');
    return;
  }

  let questioner = '匿名', time = '', preview = '';
  if (questionElement) {
    questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
    time = questionElement.querySelector('.question-time')?.textContent || '';
    const qText = questionElement.querySelector('.question-text')?.textContent || '';
    const aText = answerElement.querySelector('.answer-text')?.textContent || '';
    preview = `問：${qText.substring(0, 50)}... 答：${aText.substring(0, 50)}...`;
  } else {
    questioner = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
    const aText = answerElement.querySelector('.answer-text')?.textContent || '';
    preview = `答：${aText.substring(0, 100)}...`;
  }

  bookmarks.push({
    id: 'qa-bookmark-' + Date.now(),
    elementId: targetId,
    type: 'qa-pair',
    questioner, time, preview,
    chapter: findChapterForElement(answerElement),
    chapterTitle: currentChapter.title,
    chapterFilename: currentChapter.filename,
    timestamp: new Date().toLocaleString(),
  });
  saveBookmarks(bookmarks);
  addBookmarkVisualIndicator(answerElement);
  if (questionElement) addBookmarkVisualIndicator(questionElement);
  renderBookmarks();
  showBookmarkAddedFeedback();
}

function removeBookmark(bookmarkId) {
  const bookmarks = getBookmarks();
  const bookmark = bookmarks.find(b => b.id === bookmarkId);
  if (bookmark) {
    const el = document.getElementById(bookmark.elementId);
    if (el) {
      removeBookmarkVisualIndicator(el);
      if (bookmark.type === 'qa-pair') {
        const other = el.classList.contains('question')
          ? findAnswerForQuestion(el)
          : findQuestionForAnswer(el);
        if (other) removeBookmarkVisualIndicator(other);
      }
    }
  }
  saveBookmarks(bookmarks.filter(b => b.id !== bookmarkId));
  renderBookmarks();
  showToast('已從書籤移除');
}

function removeBookmarkById(bookmarkId) {
  saveBookmarks(getBookmarks().filter(b => b.id !== bookmarkId));
  showToast(getI18nText('bookmark.bookmarkDeleted', isTraditionalChinesePage(), '書籤已刪除'));
}

function clearCurrentChapterBookmarks() {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }
  const current = getCurrentChapterBookmarks();
  if (!current.length) { showToast('本文件暫無書籤'); return; }
  if (!confirm(`確定要清空本文件的所有 ${current.length} 個書籤嗎？此操作無法撤銷。`)) return;

  current.forEach(b => {
    const el = document.getElementById(b.elementId);
    if (el) {
      removeBookmarkVisualIndicator(el);
      if (b.type === 'qa-pair' && el.classList.contains('answer')) {
        const q = findQuestionForAnswer(el);
        if (q) removeBookmarkVisualIndicator(q);
      }
    }
  });

  const all = getBookmarks();
  saveBookmarks(all.filter(b => !b.chapter || b.chapter.id !== currentChapter.id));
  renderBookmarks();
  showToast(`已清空本文件的 ${current.length} 個書籤`);
}

// 跳转到指定书签（新标签页）
function jumpToBookmark(bookmarkId) {
  const bm = getBookmarks().find(b => b.id === bookmarkId);
  if (bm && bm.chapterFilename) {
    window.open(`${bm.chapterFilename}#${bm.elementId}`, '_blank');
  }
}
