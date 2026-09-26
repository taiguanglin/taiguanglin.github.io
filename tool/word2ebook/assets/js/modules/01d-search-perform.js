// ============================================================
// 01d-search-perform.js — 搜索执行、结果展示、分页
// ============================================================

// 生成单个搜索结果 item 的 HTML
function generateSearchResultItem(result, index, indexOffset, query) {
  const typeText = {
    heading:  getI18nText('search.resultTypes.heading',  isTraditionalChinesePage(), '標題'),
    question: getI18nText('search.resultTypes.question', isTraditionalChinesePage(), '問題'),
    answer:   getI18nText('search.resultTypes.answer',   isTraditionalChinesePage(), '回答'),
    content:  getI18nText('search.resultTypes.content',  isTraditionalChinesePage(), '內容'),
  }[result.type] || getText('内容', '內容');

  const bestContext = query
    ? getBestContextForHighlight(result, query)
    : (result.context || result.content || '');
  const highlightedContext = query ? highlightSearchTerm(bestContext, query) : bestContext;
  const globalIndex = (indexOffset || 0) + index + 1;
  const total = currentSearchResults.length;

  return `
    <li class="search-result-item" data-url="${result.url}">
      <div class="search-result-header">
        <span class="search-result-number">${globalIndex}/${total}</span>
        <span class="search-result-type">${typeText}</span>
        <div class="search-result-title">${escapeHtml(result.title)}</div>
      </div>
      <div class="search-result-content">${highlightedContext}</div>
    </li>
  `;
}

// ============================================================
// 搜尋狀態 ↔ URL hash（#q=…&scope=…）：返回本頁時可由 hash 還原查詢
// （replaceState 不產生新瀏覽記錄；配對 01e 的自動還原流程）
// ============================================================

// 從 URL hash 讀取搜尋狀態（無則回傳空字串的查詢）
function readSearchStateFromHash() {
  const hash = window.location.hash.replace(/^#/, '');
  const qMatch = /(?:^|&)q=([^&]*)/.exec(hash);
  let q = '';
  if (qMatch) {
    try {
      q = decodeURIComponent(qMatch[1]);
    } catch (e) {
      q = qMatch[1];
    }
  }
  const scopeMatch = /(?:^|&)scope=([^&]*)/.exec(hash);
  let scope = '';
  if (scopeMatch) {
    try {
      scope = decodeURIComponent(scopeMatch[1]);
    } catch (e) {
      scope = scopeMatch[1];
    }
  }
  return { q: q, scope: scope };
}

// 把目前查詢／範圍寫入 URL hash（replaceState：不產生新瀏覽記錄）
function updateSearchQueryHash(query) {
  const q = (query || '').trim();
  // 與 performSearch 相同的門檻：空查詢或 ≥2 字元才寫入，避免打字中途污染 hash
  if (q && q.length < 2) return;
  let parts = [];
  if (q) parts.push('q=' + encodeURIComponent(q));
  if (q && searchScope && searchScope !== 'both') {
    parts.push('scope=' + encodeURIComponent(searchScope));
  }
  const newHash = parts.length ? '#' + parts.join('&') : '';
  const current = window.location.hash;
  if (current === newHash) return;
  try {
    history.replaceState(null, '', window.location.pathname + window.location.search + newHash);
  } catch (e) { /* 部分環境不允許 history 操作，忽略 */ }
}

// 對外（01e / 模組載入順序在後者）提供 hash 讀取
W2E.search = W2E.search || {};
W2E.search.readStateFromHash = readSearchStateFromHash;

// 执行搜索
// targetDisplayedCount：還原情境下欲重現的「已顯示筆數」（一般搜尋傳 undefined → 第一頁）
function performSearch(query, targetDisplayedCount) {
  // 同步查詢到 URL hash：返回本頁時可據此還原結果
  updateSearchQueryHash(query);

  const elements = getSearchElements();
  resetSearchResultsHeight();

  if (!miniSearch || !query || query.trim().length < 2) {
    elements.searchResults.style.display = 'none';
    elements.tocHeader.style.display = 'block';
    currentSearchResults = [];
    displayedResultsCount = 0;
    hideLoadMoreButtons();
    setSearchScopeVisible(false);
    if (query && query.trim().length > 0 && query.trim().length < 2) {
      elements.searchStatus.textContent = getI18nText('search.minCharWarning', isTraditionalChinesePage(), '請輸入至少2個字元進行搜尋');
    } else {
      const count = searchIndex ? searchIndex.length : 0;
      elements.searchStatus.innerHTML = getText(`搜索准备就绪 (共${count}条记录)`, `搜尋準備就緒 (共${count}條記錄)`);
    }
    return;
  }

  const trimmedQuery = query.trim();
  try {
    let searchQuery = trimmedQuery;
    // 「兩者」範圍可由頁面設定擴充（books2ebook 用 w2e-config.js 把 content/heading
    // 一併納入全書搜尋；wenda2_ebook 未設定時維持 question/answer）
    const bothTypes = window.W2E_SEARCH_SCOPE_TYPES || ['question', 'answer'];
    const allowedTypes = searchScope === 'question' ? ['question']
      : searchScope === 'answer' ? ['answer']
      : bothTypes;
    const searchOptions = {
      boost: { processedContent: 1 },
      filter: function (result) {
        return allowedTypes.indexOf(result.type) !== -1;
      }
    };

    if (chineseSegmenter && trimmedQuery.length > 1) {
      const words = segmentWithJieba(trimmedQuery, true);
      if (words.length > 0) searchQuery = words.join(' ');
    }

    const results = miniSearch.search(searchQuery, searchOptions);
    results.sort((a, b) => b.score - a.score);

    currentSearchResults = results;
    displayedResultsCount = 0;

    if (results.length > 0) {
      resetSearchResultsHeight();
      displayPagedResults(trimmedQuery, targetDisplayedCount);
      setSearchScopeVisible(true);
      if (typeof captureSearchSnapshot === 'function') captureSearchSnapshot();
    } else {
      displayNoResults(trimmedQuery, elements);
      elements.searchStatus.textContent = getText('未找到匹配结果', '未找到匹配結果');
      // 若使用者已透過有結果的搜尋打開過範圍選項，保留可見以免切換後無法切回
      const scopeEl = document.querySelector('.search-scope');
      if (!(scopeEl && scopeEl.classList.contains('is-visible'))) {
        setSearchScopeVisible(false);
      }
    }

    elements.searchResults.style.display = 'block';
    elements.tocHeader.style.display = 'none';
    if (typeof captureSearchSnapshot === 'function') captureSearchSnapshot();
    setTimeout(updateFloatingControlsState, 10);
    setTimeout(updateBottomSearchButtonsVisibility, 10);

  } catch (error) {
    console.error('搜索出错:', error);
    elements.searchStatus.textContent = getText('搜索出现错误，请重试', '搜尋出現錯誤，請重試');
    elements.searchResults.style.display = 'none';
    elements.tocHeader.style.display = 'block';
    setSearchScopeVisible(false);
    setTimeout(updateFloatingControlsState, 10);
  }
}

// 展示第一页结果（分页）
// targetDisplayedCount：傳入時一次顯示到該筆數（搜尋狀態還原用）
function displayPagedResults(query, targetDisplayedCount) {
  const elements = getSearchElements();
  const firstPageCount = Math.min(RESULTS_PER_PAGE, currentSearchResults.length);
  displayedResultsCount = (typeof targetDisplayedCount === 'number' && targetDisplayedCount > firstPageCount)
    ? Math.min(targetDisplayedCount, currentSearchResults.length)
    : firstPageCount;
  const resultsToShow = currentSearchResults.slice(0, displayedResultsCount);
  elements.searchResultsList.innerHTML = resultsToShow.map((r, i) =>
    generateSearchResultItem(r, i, 0, query)
  ).join('');
  updateResultsCounter();
  updateLoadMoreButtons();
  const total = currentSearchResults.length;
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${total} 条匹配结果`, `找到 ${total} 條匹配結果`);
}

// 加载更多结果（每次追加 RESULTS_PER_PAGE 条）
function loadMoreResults() {
  const elements = getSearchElements();
  const startIndex = displayedResultsCount;
  const endIndex = Math.min(startIndex + RESULTS_PER_PAGE, currentSearchResults.length);
  const batch = currentSearchResults.slice(startIndex, endIndex);
  if (!batch.length) return;

  displayedResultsCount = endIndex;
  const query = document.getElementById('search-input').value.trim();
  const additionalHTML = batch.map((r, i) =>
    generateSearchResultItem(r, i, startIndex, query)
  ).join('');
  elements.searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);

  expandSearchResultsHeight();
  updateResultsCounter();
  updateLoadMoreButtons();
  if (typeof captureSearchSnapshot === 'function') captureSearchSnapshot();
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${currentSearchResults.length} 条匹配结果`, `找到 ${currentSearchResults.length} 條匹配結果`);
}

// 加载所有剩余结果
function loadAllResults() {
  const elements = getSearchElements();
  const remaining = currentSearchResults.slice(displayedResultsCount);
  if (!remaining.length) return;

  const startIndex = displayedResultsCount;
  displayedResultsCount = currentSearchResults.length;
  const query = document.getElementById('search-input').value.trim();
  const additionalHTML = remaining.map((r, i) =>
    generateSearchResultItem(r, i, startIndex, query)
  ).join('');
  elements.searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);

  expandSearchResultsHeight();
  updateResultsCounter();
  updateLoadMoreButtons();
  if (typeof captureSearchSnapshot === 'function') captureSearchSnapshot();
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${currentSearchResults.length} 条匹配结果`, `找到 ${currentSearchResults.length} 條匹配結果`);
}

// 显示无结果占位符
function displayNoResults(query, elements) {
  const el = elements || getSearchElements();
  el.searchResultsCount.textContent = getText('未找到结果', '未找到結果');
  el.searchResultsList.innerHTML = `
    <li class="search-result-item" style="text-align: center; color: #999;">
      <div>${getText(`未找到包含"${escapeHtml(query)}"的内容`, `未找到包含"${escapeHtml(query)}"的內容`)}</div>
      <div style="font-size: 12px; margin-top: 8px;">${getText('尝试使用不同的关键词', '嘗試使用不同的關鍵詞')}</div>
    </li>
  `;
}

// 更新结果计数器文本
function updateResultsCounter() {
  const elements = getSearchElements();
  if (elements.searchResultsCount) {
    elements.searchResultsCount.textContent = getText(
      `显示 ${displayedResultsCount} / ${currentSearchResults.length} 条结果`,
      `顯示 ${displayedResultsCount} / ${currentSearchResults.length} 條結果`
    );
  }
}
