// ============================================================
// 01e-search-ui.js — 搜索 UI 状态管理、initSearch、事件绑定
// ============================================================

// 获取搜索相关的 DOM 元素
function getSearchElements() {
  return {
    searchContainer:    document.getElementById('search-container'),
    searchActivation:   document.querySelector('.search-activation'),
    searchInput:        document.getElementById('search-input'),
    searchStatus:       document.getElementById('search-status'),
    searchResults:      document.getElementById('search-results'),
    searchResultsList:  document.getElementById('search-results-list'),
    searchResultsCount: document.getElementById('search-results-count'),
    searchClear:        document.getElementById('search-clear'),
    searchCollapse:     document.getElementById('search-collapse'),
    tocHeader:          document.getElementById('toc-header'),
  };
}

// 初始化搜索 UI（显示容器；进度条由下载／建索引阶段自行挂载）
function initializeSearchUI(elements) {
  if (elements.searchActivation) elements.searchActivation.style.display = 'none';
  elements.searchContainer.style.display = 'block';
  elements.searchStatus.innerHTML = '';
  const loadingUI = createLoadingUI(elements.searchStatus);
  if (loadingUI.textElement) {
    loadingUI.textElement.textContent = getI18nText(
      'search.loading',
      isTraditionalChinesePage(),
      '正在載入搜尋功能，請稍候...'
    );
  }
  return loadingUI;
}

// 更新「显示更多」按钮的显示状态
function updateLoadMoreButtons() {
  if (typeof displayedResultsCount === 'undefined' || typeof currentSearchResults === 'undefined') return;
  const shouldShow = displayedResultsCount < currentSearchResults.length;
  ['search-load-more', 'search-load-all', 'search-load-more-bottom', 'search-load-all-bottom'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.style.display = shouldShow ? 'inline-block' : 'none';
  });
}

// 隐藏所有「显示更多」按钮
function hideLoadMoreButtons() {
  ['search-load-more', 'search-load-all', 'search-load-more-bottom', 'search-load-all-bottom'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.style.display = 'none';
  });
}

// 搜索结果列表高度工具函数（预设无限制，保留兼容性）
function initializeSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; }
}
function expandSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; list.setAttribute('data-expanded', 'true'); }
}
function resetSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; list.removeAttribute('data-expanded'); }
}

// 完成搜索初始化设置（更新状态、启用输入框）
function finalizeSearchSetup(elements, segmenterEnabled, indexLength) {
  const isTrad = isTraditionalChinesePage();
  const segStatus = segmenterEnabled
    ? (isTrad ? '智能中文分詞已啟用' : '智能中文分词已启用')
    : (isTrad ? '使用傳統搜尋模式' : '使用传统搜索模式');

  console.timeEnd('🚀 搜索初始化總時間');
  console.log(isTrad ? '🎉 搜尋初始化流程完成！' : '🎉 搜索初始化流程完成！');

  elements.searchStatus.innerHTML = `
    <div class="search-status-success">
      ✅ ${getI18nText('search.indexReady', isTrad, '搜尋準備就緒 (共{count}條記錄)', { count: indexLength })}
      <br><small>🔧 ${segStatus}</small>
    </div>
  `;
  searchInitialized = true;
  initializeSearchResultsHeight();
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.search_placeholder', isTrad, '搜尋全文內容...');
  const activateBtn = document.getElementById('search-activate-btn');
  if (activateBtn) activateBtn.disabled = false;
  setTimeout(() => elements.searchInput.focus(), 100);
}

// 处理搜索初始化错误
function handleSearchInitError(elements, error) {
  const isTrad = isTraditionalChinesePage();
  console.error('搜索初始化失败:', error);
  elements.searchStatus.innerHTML = '';
  createErrorUI(elements.searchStatus, error.message || getI18nText('search.loadingFailed', isTrad, '搜尋索引載入失敗'), async () => {
    await initSearch();
  });
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.searchUnavailable', isTrad, '搜尋功能暫不可用');
  const activateBtn = document.getElementById('search-activate-btn');
  if (activateBtn) activateBtn.disabled = false;
}

// 清除搜索状态（重置输入框、结果、计数）
function clearSearch() {
  const elements = getSearchElements();
  if (elements.searchInput) elements.searchInput.value = '';
  if (elements.searchResults) elements.searchResults.style.display = 'none';
  if (elements.tocHeader) elements.tocHeader.style.display = 'block';
  currentSearchResults = [];
  displayedResultsCount = 0;
  hideLoadMoreButtons();
  resetSearchResultsHeight();
  if (elements.searchStatus) {
    const count = searchIndex ? searchIndex.length : 0;
    elements.searchStatus.innerHTML = getText(`搜索准备就绪 (共${count}条记录)`, `搜尋準備就緒 (共${count}條記錄)`);
  }
}

// 收起搜索面板
function collapseSearch() {
  const searchContainer  = document.getElementById('search-container');
  const searchActivation = document.querySelector('.search-activation');
  if (!searchContainer || !searchActivation) return;

  const searchInput        = document.getElementById('search-input');
  const searchResults      = document.getElementById('search-results');
  const tocHeader          = document.getElementById('toc-header');
  const searchStatus       = document.getElementById('search-status');
  const searchResultsList  = document.getElementById('search-results-list');
  const searchResultsCount = document.getElementById('search-results-count');

  if (searchInput) searchInput.value = '';
  if (searchResults) searchResults.style.display = 'none';
  if (tocHeader) tocHeader.style.display = 'block';
  currentSearchResults = [];
  displayedResultsCount = 0;
  hideLoadMoreButtons();

  if (searchStatus) searchStatus.innerHTML = '';
  if (searchResultsList) { searchResultsList.innerHTML = ''; searchResultsList.style.maxHeight = ''; searchResultsList.style.overflowY = ''; }
  if (searchResultsCount) searchResultsCount.textContent = '';
  if (searchResults) searchResults.style.maxHeight = '';

  searchContainer.style.display = 'none';
  searchActivation.style.display = 'block';
  setTimeout(updateFloatingControlsState, 10);
}

// ============================================================
// initSearch — 搜索功能主入口（async）
// ============================================================
async function initSearch() {
  if (!isIndexPage()) return;

  console.time('🚀 搜索初始化總時間');
  console.log('📊 開始搜索初始化流程...');

  const elements = getSearchElements();
  if (!elements.searchInput || !elements.searchContainer) return;

  // 初始化缓存管理器
  let cacheManager = null;
  try {
    if (window.searchCacheManager) {
      await window.searchCacheManager.init();
      cacheManager = window.searchCacheManager;
      console.log('💾 緩存管理器初始化成功');
    }
  } catch (err) {
    console.warn('緩存管理器初始化失敗，將使用標準流程:', err);
  }

  try {
    initializeSearchUI(elements);

    if (typeof MiniSearch === 'undefined') throw new Error('MiniSearch库未加载');

    const segmenterEnabled = await initChineseSegmenter();
    console.log(isTraditionalChinesePage()
      ? `📝 分詞器狀態: ${segmenterEnabled ? '已啟用' : '未啟用'}`
      : `📝 分词器状态: ${segmenterEnabled ? '已启用' : '未启用'}`);

    const isTraditional = isTraditionalChinesePage();
    const isTrad = isTraditionalChinesePage();

    let needsUpdate = true;
    let hashData = null;
    if (cacheManager) {
      const updateInfo = await cacheManager.checkUpdate(isTraditional);
      needsUpdate = updateInfo.needsUpdate;
      hashData = updateInfo.hashData;
    }

    if (!needsUpdate) {
      elements.searchStatus.innerHTML = '';
      const cacheMsg = document.createElement('div');
      cacheMsg.className = 'search-loading-text';
      cacheMsg.textContent = getI18nText(
        'search.loadingFromCache',
        isTrad,
        '正在從快取載入搜尋索引…'
      );
      elements.searchStatus.appendChild(cacheMsg);
      searchIndex = await cacheManager.getCachedSearchIndex(isTraditional);
      if (!searchIndex) {
        console.log('📡 緩存數據丟失，重新下載...');
        needsUpdate = true;
      } else {
        console.log('⚡ 從緩存加載搜索索引（哈希驗證通過）');
      }
    }

    if (needsUpdate) {
      console.log('📡 從網絡加載搜索索引...');
      if (!hashData && cacheManager) {
        const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
        hashData = await cacheManager.fetchHashFile(`${indexFileName}.hash`);
      } else if (!hashData) {
        try {
          const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
          const hashResp = await fetch(`${indexFileName}.hash`);
          if (hashResp.ok) hashData = await hashResp.json();
        } catch (e) { /* 無 hash 時改顯示位元組進度 */ }
      }
      const expectedSize = hashData && typeof hashData.size === 'number' ? hashData.size : null;
      searchIndex = await loadSearchIndexWithProgress(expectedSize, elements.searchStatus);
      if (cacheManager && searchIndex) {
        await cacheManager.cacheSearchIndex(searchIndex, isTraditional);
        if (hashData) {
          await cacheManager.saveHashMetadata(hashData, isTraditional);
          console.log('🗑️ 清除舊的處理後索引緩存...');
          await cacheManager.clearOldProcessedIndexes(isTraditional, hashData.hash);
        }
      }
    }

    console.log(`📋 索引記錄數: ${searchIndex.length}`);

    const searchConfig = createSearchConfig(segmenterEnabled);
    miniSearch = new MiniSearch(searchConfig);

    await buildSearchIndexInBatchesWithCache(miniSearch, searchIndex, elements.searchStatus, segmenterEnabled, cacheManager, isTraditional);
    finalizeSearchSetup(elements, segmenterEnabled, searchIndex.length);

  } catch (error) {
    handleSearchInitError(elements, error);
    return;
  }

  // 搜索输入防抖
  let searchTimeout;
  elements.searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();
    searchTimeout = setTimeout(() => performSearch(query), 300);
  });

  // 搜尋範圍：問題 / 回答 / 兩者
  document.querySelectorAll('.search-scope-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const scope = btn.getAttribute('data-scope');
      if (!scope || scope === searchScope) return;
      searchScope = scope;
      document.querySelectorAll('.search-scope-btn').forEach((b) => {
        const active = b.getAttribute('data-scope') === searchScope;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      const query = elements.searchInput.value.trim();
      if (query.length >= 2) performSearch(query);
    });
  });

  // 清除 / 收起按钮
  if (elements.searchClear) elements.searchClear.addEventListener('click', clearSearch);
  if (elements.searchCollapse) elements.searchCollapse.addEventListener('click', collapseSearch);

  // 显示更多 / 全部按钮（顶部 + 底部）
  [['search-load-more', loadMoreResults], ['search-load-all', loadAllResults],
   ['search-load-more-bottom', loadMoreResults], ['search-load-all-bottom', loadAllResults],
   ['search-clear-bottom', clearSearch], ['search-collapse-bottom', collapseSearch]
  ].forEach(([id, fn]) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', fn);
  });

  // 结果列表点击（在新标签打开）
  elements.searchResultsList.addEventListener('click', (e) => {
    const item = e.target.closest('.search-result-item');
    if (item && item.dataset.url) {
      window.open(item.dataset.url, '_blank', 'noopener,noreferrer');
    }
  });
}

// ============================================================
// 首页搜索激活按钮监听（模块加载后绑定）
// ============================================================
if (isIndexPage()) {
  const searchActivateBtn = document.getElementById('search-activate-btn');
  if (searchActivateBtn) {
    searchActivateBtn.addEventListener('click', activateSearch);
  }
}
