  // ============ 搜索功能（延迟加载） ============
  let searchIndex = null;
  let miniSearch = null;
  let searchInitialized = false;
  let currentSearchResults = [];
  let displayedResultsCount = 0;
  const RESULTS_PER_PAGE = 20;
  
  // 检测当前页面类型
  function isIndexPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index.html' || filename === 'index_trad.html';
  }
  
  // 判断是否为繁体版
  function isTraditionalChinesePage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename.includes('_trad.html');
  }
  
  // 获取搜索索引文件名
  function getSearchIndexFile() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index_trad.html' ? 'search_index_trad.json' : 'search_index.json';
  }
  
  // 获取本地化文本
  function getText(simplifiedText, traditionalText) {
    return isTraditionalChinesePage() ? traditionalText : simplifiedText;
  }
  
  // 激活搜索功能
  async function activateSearch() {
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchActivateBtn = document.getElementById('search-activate-btn');
    
    // 立即禁用激活按钮防止重复点击
    if (searchActivateBtn) {
      searchActivateBtn.disabled = true;
    }
    
    if (searchInitialized) {
      // 如果已经初始化，直接显示搜索容器
      if (searchContainer && searchActivation) {
        searchActivation.style.display = 'none';
        searchContainer.style.display = 'block';
        
        // 恢復搜索準備就緒狀態信息
        const searchStatus = document.getElementById('search-status');
        if (searchStatus && searchIndex && searchIndex.length > 0) {
          const isSegmenterEnabled = chineseSegmenter && chineseSegmenter.cut;
          const segmenterStatus = isSegmenterEnabled ? 
            (isTraditionalChinesePage() ? '智能中文分詞已啟用' : '智能中文分词已启用') : 
            (isTraditionalChinesePage() ? '使用傳統搜尋模式' : '使用传统搜索模式');
          
          searchStatus.innerHTML = `
            <div class="search-status-success">
              ✅ ${getI18nText('search.indexReady', isTraditionalChinesePage(), '搜尋準備就緒 (共{count}條記錄)', { count: searchIndex.length })}
              <br><small>🔧 ${segmenterStatus}</small>
            </div>
          `;
        }
        
        // 聚焦搜索框
        if (searchInput) {
          setTimeout(() => searchInput.focus(), 100);
        }
      }
      // 重新启用激活按钮
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
      }
      return;
    }
    
    // 立即禁用搜索输入框并显示加载状态
    if (searchInput) {
      searchInput.disabled = true;
      searchInput.placeholder = getI18nText('search.loading', isTraditionalChinesePage(), '正在載入搜尋功能，請稍候...');
    }
    
    await initSearch();
  }
  
  // 創建載入UI
  function createLoadingUI(container) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'search-loading';
    loadingDiv.innerHTML = `
      <div class="search-loading-spinner"></div>
      <div class="search-loading-text" id="search-loading-text"></div>
    `;
    
    container.appendChild(loadingDiv);
    
    return {
      loadingDiv,
      textElement: loadingDiv.querySelector('#search-loading-text')
    };
  }
  
  // 創建錯誤UI
  function createErrorUI(container, message, onRetry) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'search-error';
    errorDiv.innerHTML = `
      <span>⚠️ ${message}</span>
      <button class="search-retry-btn" id="search-retry-btn">${getI18nText('search.retry', isTraditionalChinesePage(), '重試')}</button>
    `;
    
    container.appendChild(errorDiv);
    
    const retryBtn = errorDiv.querySelector('#search-retry-btn');
    retryBtn.addEventListener('click', () => {
      container.removeChild(errorDiv);
      onRetry();
    });
    
    return errorDiv;
  }
  
  // 載入搜索索引（支援進度追蹤）
  async function loadSearchIndexWithProgress() {
    const indexFile = getSearchIndexFile();
    
    try {
      const response = await fetch(indexFile);
      
      if (!response.ok) {
        throw new Error(getI18nText('search.networkError', isTraditionalChinesePage(), '網路連接失敗，請檢查網路後重試'));
      }
      
      const contentLength = response.headers.get('content-length');
      const total = parseInt(contentLength, 10);
      let loaded = 0;
      
      const reader = response.body.getReader();
      const chunks = [];
      
      // 更新載入文字的函數
      const updateLoadingText = (text) => {
        const loadingText = document.getElementById('search-loading-text');
        
        if (loadingText) {
          loadingText.textContent = text;
        }
      };
      
      // 初始狀態
      updateLoadingText(getI18nText('search.loadingIndex', isTraditionalChinesePage(), '正在載入搜尋索引...'));
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        chunks.push(value);
        loaded += value.length;
        
        // 顯示下載中的提示
        updateLoadingText(getI18nText('search.loadingData', isTraditionalChinesePage(), '正在下載搜尋資料...'));
      }
      
      // 組合所有chunks
      const allChunks = new Uint8Array(loaded);
      let position = 0;
      for (const chunk of chunks) {
        allChunks.set(chunk, position);
        position += chunk.length;
      }
      
      // 更新到處理階段
      updateLoadingText(getI18nText('search.processingIndex', isTraditionalChinesePage(), '正在處理搜尋索引...'));
      
      // 解析JSON
      const text = new TextDecoder().decode(allChunks);
      const searchIndex = JSON.parse(text);
      
      updateLoadingText(getI18nText('search.preparingIndex', isTraditionalChinesePage(), '準備智能搜索索引... 即將完成', '準備智能搜尋索引... 即將完成'));
      
      return searchIndex;
      
    } catch (error) {
      console.error('載入搜索索引失敗:', error);
      throw error;
    }
  }
  
  // 中文分词器（使用 jieba-wasm）
  let chineseSegmenter = null;
  
  // 初始化中文分词器 (jieba-wasm)
  async function initChineseSegmenter() {
    try {
      // 檢查是否已經初始化
      if (chineseSegmenter) {
        console.log(isTraditionalChinesePage() ? 
          '✅ jieba-wasm 已初始化，跳過重複初始化' : 
          '✅ jieba-wasm 已初始化，跳过重复初始化');
        return true;
      }

      // 引入 jieba_rs_wasm.js 模塊
      console.log(isTraditionalChinesePage() ? 
        '⏳ 正在載入 jieba_rs_wasm.js...' : 
        '⏳ 正在载入 jieba_rs_wasm.js...');
      
      const { default: jiebaInit, cut } = await import('./jieba_rs_wasm.js');
      await jiebaInit();
      
      chineseSegmenter = {
        cut: function(text) {
          try {
            return cut(text, true);
          } catch (error) {
            console.error('jieba-wasm 分詞錯誤:', error);
            return [];
          }
        }
      };
      
      console.log(isTraditionalChinesePage() ? 
        '✅ jieba-wasm 已啟用，支持高性能中文分詞' : 
        '✅ jieba-wasm 已启用，支持高性能中文分词');
      return true;
      
    } catch (error) {
      console.error(isTraditionalChinesePage() ? 
        '❌ jieba-wasm 初始化失敗:' : 
        '❌ jieba-wasm 初始化失败:', error);
      return false;
    }
  }
  
  // jieba-wasm 統一分詞功能
  // 分詞統計變數（調試用）
  let segmentationStats = { calls: 0, totalTime: 0 };
  
  /**
   * 使用 jieba-wasm 進行文本分詞
   * @param {string} text - 要分詞的文本
   * @param {boolean} returnArray - 是否返回數組格式（默認返回空格分隔的字符串）
   * @returns {string|Array} 分詞結果
   */
  function segmentWithJieba(text, returnArray = false) {
    if (!text || typeof text !== 'string') {
      return returnArray ? [] : '';
    }
    
    // 統計調用次數和性能
    segmentationStats.calls++;
    const startTime = performance.now();
    
    if (chineseSegmenter && chineseSegmenter.cut) {
      try {
        // 使用 jieba-wasm 分詞
        const words = chineseSegmenter.cut(text);
        
        // 記錄處理時間
        const endTime = performance.now();
        segmentationStats.totalTime += (endTime - startTime);
        
        // 每2000次調用輸出一次統計（避免日誌過多）
        if (segmentationStats.calls % 2000 === 0) {
          console.log(isTraditionalChinesePage() ? 
            `🔤 jieba-wasm 統計: ${segmentationStats.calls} 次調用, 平均耗時: ${(segmentationStats.totalTime / segmentationStats.calls).toFixed(2)}ms` :
            `🔤 jieba-wasm 统计: ${segmentationStats.calls} 次调用, 平均耗时: ${(segmentationStats.totalTime / segmentationStats.calls).toFixed(2)}ms`);
        }
        
        return returnArray ? words : words.join(' ');
      } catch (error) {
        console.error(isTraditionalChinesePage() ? 
          '❌ jieba-wasm 分詞失敗:' : 
          '❌ jieba-wasm 分词失败:', error);
        return returnArray ? [] : '';
      }
    }
    
    // jieba-wasm 不可用時的降級處理
    console.warn(isTraditionalChinesePage() ? 
      '⚠️ jieba-wasm 不可用，返回原文本' : 
      '⚠️ jieba-wasm 不可用，返回原文本');
    return returnArray ? [text] : text;
  }

// 更新加载更多按钮的显示状态（全局函数）
function updateLoadMoreButtons() {
  if (typeof displayedResultsCount === 'undefined' || typeof currentSearchResults === 'undefined') return;
  
  const loadMoreBtn = document.getElementById('search-load-more');
  const loadAllBtn = document.getElementById('search-load-all');
  const loadMoreBtnBottom = document.getElementById('search-load-more-bottom');
  const loadAllBtnBottom = document.getElementById('search-load-all-bottom');
  
  // 判斷是否還有更多內容可以加載
  const shouldShow = displayedResultsCount < currentSearchResults.length;
  
  if (loadMoreBtn) loadMoreBtn.style.display = shouldShow ? 'inline-block' : 'none';
  if (loadAllBtn) loadAllBtn.style.display = shouldShow ? 'inline-block' : 'none';
  if (loadMoreBtnBottom) loadMoreBtnBottom.style.display = shouldShow ? 'inline-block' : 'none';
  if (loadAllBtnBottom) loadAllBtnBottom.style.display = shouldShow ? 'inline-block' : 'none';
}

// 隐藏加载更多按钮（全局函数）
function hideLoadMoreButtons() {
  const loadMoreBtn = document.getElementById('search-load-more');
  const loadAllBtn = document.getElementById('search-load-all');
  const loadMoreBtnBottom = document.getElementById('search-load-more-bottom');
  const loadAllBtnBottom = document.getElementById('search-load-all-bottom');
  
  if (loadMoreBtn) loadMoreBtn.style.display = 'none';
  if (loadAllBtn) loadAllBtn.style.display = 'none';
  if (loadMoreBtnBottom) loadMoreBtnBottom.style.display = 'none';
  if (loadAllBtnBottom) loadAllBtnBottom.style.display = 'none';
}

// 創建搜索配置
function createSearchConfig(segmenterEnabled) {
  if (segmenterEnabled) {
    // 啟用分詞時：只索引 processedContent，title 不參與搜索
    return {
      fields: ['processedContent'], // 移除 title，只索引實際內容
      storeFields: ['id', 'title', 'type', 'content', 'processedContent', 'context', 'url'],
        searchOptions: {
        boost: { processedContent: 1 },
        combineWith: 'AND'
      },
      // 關鍵優化：不使用 processTerm，避免對已分詞內容重複處理
      // 用戶查詢的分詞在搜索時單獨處理
    };
  } else {
    // 未啟用分詞時：只索引 content，title 不參與搜索
    return {
      fields: ['content'], // 移除 title，只索引實際內容
      storeFields: ['id', 'title', 'type', 'content', 'context', 'url'],
      searchOptions: {
        boost: { content: 1 },
        combineWith: 'AND'
      }
    };
  }
}
      

// 獲取搜索相關的 DOM 元素
function getSearchElements() {
  return {
    searchContainer: document.getElementById('search-container'),
    searchActivation: document.querySelector('.search-activation'),
    searchInput: document.getElementById('search-input'),
    searchStatus: document.getElementById('search-status'),
    searchResults: document.getElementById('search-results'),
    searchResultsList: document.getElementById('search-results-list'),
    searchResultsCount: document.getElementById('search-results-count'),
    searchClear: document.getElementById('search-clear'),
    searchCollapse: document.getElementById('search-collapse'),
    tocHeader: document.getElementById('toc-header')
  };
}

// 初始化搜索 UI
function initializeSearchUI(elements) {
  console.time('🎨 UI初始化');
  
  // 显示搜索容器，隐藏激活按钮
  if (elements.searchActivation) elements.searchActivation.style.display = 'none';
  elements.searchContainer.style.display = 'block';
  
  // 清空當前狀態並創建載入UI
  elements.searchStatus.innerHTML = '';
  const loadingUI = createLoadingUI(elements.searchStatus);
  
  console.timeEnd('🎨 UI初始化');
  return loadingUI;
}

// 分批建立搜索索引（包含即時分詞）
async function buildSearchIndexInBatches(miniSearch, searchIndex, searchStatus, segmenterEnabled) {
      console.time('📇 分詞+索引建立時間 (分批處理)');
      console.log(isTraditionalChinesePage() ? 
        `🔄 開始分批分詞並建立索引 ${searchIndex.length} 條記錄...` :
        `🔄 开始分批分词并建立索引 ${searchIndex.length} 条记录...`);
      
      // 分批配置
      const BATCH_SIZE = 300; // 減小批次大小以保持響應性
      const totalBatches = Math.ceil(searchIndex.length / BATCH_SIZE);
      
      // 創建統一的進度條UI
      const progressContainer = document.createElement('div');
      progressContainer.className = 'search-progress-container';
      const initialText = isTraditionalChinesePage() ? 
        `📊 正在分詞並建立搜尋索引...0/${searchIndex.length}` : 
        `📊 正在分词并建立搜索索引...0/${searchIndex.length}`;
      progressContainer.innerHTML = `
        <div class="search-loading-text">${initialText}</div>
        <div class="search-progress-bar">
          <div class="search-progress-fill" style="width: 0%"></div>
        </div>
      `;
      searchStatus.innerHTML = '';
      searchStatus.appendChild(progressContainer);
      
      const progressFill = progressContainer.querySelector('.search-progress-fill');
      const loadingText = progressContainer.querySelector('.search-loading-text');
      
      // 分批處理函數（包含即時分詞）
      async function processBatch(batchIndex) {
        const startIdx = batchIndex * BATCH_SIZE;
        const endIdx = Math.min(startIdx + BATCH_SIZE, searchIndex.length);
        const batch = searchIndex.slice(startIdx, endIdx);
        
        // 更新進度條
        const percentage = Math.round((endIdx / searchIndex.length) * 100);
        
        const progressText = isTraditionalChinesePage() ? 
          `📊 正在分詞並建立搜尋索引...${endIdx}/${searchIndex.length}` :
          `📊 正在分词并建立搜索索引...${endIdx}/${searchIndex.length}`;
        
        progressFill.style.width = `${percentage}%`;
        loadingText.textContent = progressText;
        
        // 對批次進行即時分詞處理
        const processedBatch = batch.map(doc => {
          const processedDoc = { ...doc };
          
          // 如果啟用分詞且有內容，進行分詞處理
          if (segmenterEnabled && doc.content) {
            processedDoc.processedContent = segmentWithJieba(doc.content);
          } else {
            processedDoc.processedContent = doc.content;
          }
          
          return processedDoc;
        });
        
        // 添加當前批次到索引
        miniSearch.addAll(processedBatch);
        
        // 讓瀏覽器有時間更新UI
        await new Promise(resolve => setTimeout(resolve, 15)); // 稍微增加延遲以保持響應性
      }
      
      // 逐批處理
      for (let i = 0; i < totalBatches; i++) {
        await processBatch(i);
      }
      
      // 移除進度顯示
      searchStatus.removeChild(progressContainer);
      
      console.timeEnd('📇 分詞+索引建立時間 (分批處理)');
      console.log(isTraditionalChinesePage() ? 
        '✅ 索引建立完成！' : 
        '✅ 索引建立完成！');
}

// 支持緩存的分批索引建立函數
async function buildSearchIndexInBatchesWithCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, cacheManager, isTraditional) {
  // 獲取當前的哈希值
  let currentHash = null;
  if (cacheManager) {
    const hashKey = `hash_${isTraditional ? 'trad' : 'simp'}`;
    const hashData = await cacheManager.getMetadata(hashKey);
    currentHash = hashData ? hashData.hash : null;
  }
  
  // 嘗試從緩存加載處理後的數據（使用哈希值）
  let processedData = null;
  if (cacheManager && currentHash) {
    processedData = await cacheManager.getCachedProcessedIndex(isTraditional, segmenterEnabled, currentHash);
  }
  
  if (processedData) {
    // 從緩存恢復 MiniSearch 索引
    console.time('📇 從緩存恢復索引');
    console.log('⚡ 從緩存恢復處理後的搜索索引...');
    
    try {
      // 創建進度條UI
      const progressContainer = document.createElement('div');
      progressContainer.className = 'search-progress-container';
      const initialText = isTraditionalChinesePage() ? 
        `⚡ 從緩存恢復處理後的搜索索引...0/${processedData.length}` :
        `⚡ 从缓存恢复处理后的搜索索引...0/${processedData.length}`;
      progressContainer.innerHTML = `
        <div class="search-loading-text">${initialText}</div>
        <div class="search-progress-bar">
          <div class="search-progress-fill" style="width: 0%"></div>
        </div>
      `;
      searchStatus.innerHTML = '';
      searchStatus.appendChild(progressContainer);
      
      const progressFill = progressContainer.querySelector('.search-progress-fill');
      const loadingText = progressContainer.querySelector('.search-loading-text');
      
      // 批量添加到 MiniSearch
      const BATCH_SIZE = 1000;
      const totalItems = processedData.length;
      
      for (let i = 0; i < totalItems; i += BATCH_SIZE) {
        const batch = processedData.slice(i, i + BATCH_SIZE);
        miniSearch.addAll(batch);
        
        // 更新進度
        const progress = Math.min(i + BATCH_SIZE, totalItems);
        const percentage = Math.round((progress / totalItems) * 100);
        
        const progressText = isTraditionalChinesePage() ? 
          `⚡ 從緩存恢復處理後的搜索索引...${progress}/${totalItems}` :
          `⚡ 从缓存恢复处理后的搜索索引...${progress}/${totalItems}`;
        
        progressFill.style.width = `${percentage}%`;
        loadingText.textContent = progressText;
        
        // 讓 UI 有機會更新
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      
      console.timeEnd('📇 從緩存恢復索引');
      console.log(isTraditionalChinesePage() ? 
        '⚡ 從緩存快速恢復索引完成！' : 
        '⚡ 从缓存快速恢复索引完成！');
    } catch (error) {
      console.warn('從緩存恢復失敗，將重新建立索引:', error);
      // 如果緩存恢復失敗，回退到標準流程
      await buildSearchIndexInBatches(miniSearch, searchIndex, searchStatus, segmenterEnabled);
    }
  } else {
    // 標準流程：分詞並建立索引
    console.log('🔄 執行完整的分詞和索引建立流程...');
    
    // 收集處理後的數據以便緩存
    const processedItems = [];
    
    // 修改原始函數以收集處理後的數據
    await buildSearchIndexInBatchesAndCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, processedItems);
    
    // 保存處理後的數據到緩存
    if (cacheManager && processedItems.length > 0) {
      console.log('💾 保存處理後的索引到緩存...');
      await cacheManager.cacheProcessedIndex(processedItems, isTraditional, segmenterEnabled, currentHash);
    }
  }
}

// 修改版的索引建立函數，收集處理後的數據
async function buildSearchIndexInBatchesAndCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, processedItems) {
  console.time('📇 分詞+索引建立時間 (分批處理)');
  console.log(isTraditionalChinesePage() ? 
    `🔄 開始分批分詞並建立索引 ${searchIndex.length} 條記錄...` :
    `🔄 开始分批分词并建立索引 ${searchIndex.length} 条记录...`);

  const BATCH_SIZE = 300;
  const totalItems = searchIndex.length;
  
  // 創建進度條UI
  const progressContainer = document.createElement('div');
  progressContainer.className = 'search-progress-container';
  const initialText = isTraditionalChinesePage() ? 
    `📊 正在分詞並建立搜尋索引...0/${totalItems}` : 
    `📊 正在分词并建立搜索索引...0/${totalItems}`;
  progressContainer.innerHTML = `
    <div class="search-loading-text">${initialText}</div>
    <div class="search-progress-bar">
      <div class="search-progress-fill" style="width: 0%"></div>
    </div>
  `;
  searchStatus.innerHTML = '';
  searchStatus.appendChild(progressContainer);
  
  const progressFill = progressContainer.querySelector('.search-progress-fill');
  const loadingText = progressContainer.querySelector('.search-loading-text');
  
  for (let i = 0; i < totalItems; i += BATCH_SIZE) {
    const batch = searchIndex.slice(i, i + BATCH_SIZE);
    const processedBatch = [];
    
    // 處理批次中的每個項目
    for (const doc of batch) {
      let processedDoc = { ...doc };
      
      // 如果啟用分詞，對內容進行分詞
      if (segmenterEnabled && doc.content) {
        processedDoc.processedContent = segmentWithJieba(doc.content);
      }
      
      processedBatch.push(processedDoc);
      processedItems.push(processedDoc); // 收集到緩存數組
    }
    
    // 添加到 MiniSearch
    miniSearch.addAll(processedBatch);
    
    // 更新進度條
    const progress = Math.min(i + BATCH_SIZE, totalItems);
    const percentage = Math.round((progress / totalItems) * 100);
    
    const progressText = isTraditionalChinesePage() ? 
      `📊 正在分詞並建立搜尋索引...${progress}/${totalItems}` :
      `📊 正在分词并建立搜索索引...${progress}/${totalItems}`;
    
    progressFill.style.width = `${percentage}%`;
    loadingText.textContent = progressText;
    
    // 讓 UI 有機會更新
    await new Promise(resolve => setTimeout(resolve, 15));
  }
  
  console.timeEnd('📇 分詞+索引建立時間 (分批處理)');
  console.log(isTraditionalChinesePage() ? 
    '✅ 索引建立完成！' : 
    '✅ 索引建立完成！');
}
      
// 完成搜索初始化設置
function finalizeSearchSetup(elements, segmenterEnabled, indexLength) {
      // 顯示完成狀態和分词功能状态
      const segmenterStatus = segmenterEnabled ? 
        (isTraditionalChinesePage() ? '智能中文分詞已啟用' : '智能中文分词已启用') : 
        (isTraditionalChinesePage() ? '使用傳統搜尋模式' : '使用传统搜索模式');
      
      console.timeEnd('🚀 搜索初始化總時間');
      console.log(isTraditionalChinesePage() ? 
        '🎉 搜尋初始化流程完成！' : 
        '🎉 搜索初始化流程完成！');
      
  elements.searchStatus.innerHTML = `
        <div class="search-status-success">
      ✅ ${getI18nText('search.indexReady', isTraditionalChinesePage(), '搜尋準備就緒 (共{count}條記錄)', { count: indexLength })}
          <br><small>🔧 ${segmenterStatus}</small>
        </div>
      `;
      searchInitialized = true;
      
      // 初始化搜索結果欄位高度
      initializeSearchResultsHeight();
      
      // 启用搜索输入框
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.search_placeholder', isTraditionalChinesePage(), '搜尋全文內容...');
      
      // 重新启用激活按钮
      const searchActivateBtn = document.getElementById('search-activate-btn');
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
      }
      
      // 聚焦搜索框
  setTimeout(() => elements.searchInput.focus(), 100);
}
      
// 處理搜索初始化錯誤
function handleSearchInitError(elements, error) {
      console.error('搜索初始化失败:', error);
      
      // 清空狀態並顯示錯誤
  elements.searchStatus.innerHTML = '';
      
      // 創建錯誤UI並提供重試功能
  createErrorUI(elements.searchStatus, error.message || getI18nText('search.loadingFailed', isTraditionalChinesePage(), '搜尋索引載入失敗'), async () => {
        await initSearch();
      });
      
      // 即使失败也要启用输入框，让用户可以重试
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.searchUnavailable', isTraditionalChinesePage(), '搜尋功能暫不可用');
      
      // 重新启用激活按钮，允许用户重试
      const searchActivateBtn = document.getElementById('search-activate-btn');
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
  }
}

// 初始化搜索結果欄位高度 - 移除高度限制
function initializeSearchResultsHeight() {
  const searchResultsList = document.querySelector('.search-results-list');
  if (searchResultsList) {
    // 移除高度限制，顯示所有搜尋結果
    searchResultsList.style.maxHeight = 'none';
    searchResultsList.style.overflowY = 'visible';
  }
}

// 動態擴大搜索結果欄位高度 - 已預設無限制，此函數保留以維持兼容性
function expandSearchResultsHeight() {
  const searchResultsList = document.querySelector('.search-results-list');
  
  if (!searchResultsList) {
    return;
  }
  
  // 確保無高度限制（預設已是如此）
  searchResultsList.style.maxHeight = 'none';
  searchResultsList.style.overflowY = 'visible';
  
  // 添加標記，表示已經展開
  searchResultsList.setAttribute('data-expanded', 'true');
}

// 重置搜索結果欄位高度（新搜索時調用） - 移除高度限制
function resetSearchResultsHeight() {
  const searchResultsList = document.querySelector('.search-results-list');
  if (searchResultsList) {
    // 移除高度限制，顯示所有搜尋結果
    searchResultsList.style.maxHeight = 'none';
    searchResultsList.style.overflowY = 'visible';
    // 移除展開標記，因為預設就是展開狀態
    searchResultsList.removeAttribute('data-expanded');
  }
}

// 初始化搜索功能（内部函数）
async function initSearch() {
  if (!isIndexPage()) return;
  
  console.time('🚀 搜索初始化總時間');
  console.log('📊 開始搜索初始化流程...');
  
  const elements = getSearchElements();
  if (!elements.searchInput || !elements.searchContainer) return;
  
  // 初始化緩存管理器
  let cacheManager = null;
  try {
    if (window.searchCacheManager) {
      await window.searchCacheManager.init();
      cacheManager = window.searchCacheManager;
      console.log('💾 緩存管理器初始化成功');
    }
  } catch (error) {
    console.warn('緩存管理器初始化失敗，將使用標準流程:', error);
  }
  
  try {
    const loadingUI = initializeSearchUI(elements);
    
    // 检查MiniSearch是否可用
    console.time('📚 MiniSearch檢查');
    if (typeof MiniSearch === 'undefined') {
      throw new Error('MiniSearch库未加载');
    }
    console.timeEnd('📚 MiniSearch檢查');
    
    // 初始化中文分词器
    console.time('🔧 分詞器初始化');
    const segmenterEnabled = await initChineseSegmenter();
    console.timeEnd('🔧 分詞器初始化');
    console.log(isTraditionalChinesePage() ? 
      `📝 分詞器狀態: ${segmenterEnabled ? '已啟用' : '未啟用'}` :
      `📝 分词器状态: ${segmenterEnabled ? '已启用' : '未启用'}`);
    
    // 加载搜索索引（優先從緩存）
    console.time('📥 JSON載入時間');
    const isTraditional = isTraditionalChinesePage();
    
    // 檢查是否需要更新緩存（基於哈希）
    let needsUpdate = true;
    if (cacheManager) {
      needsUpdate = await cacheManager.needsUpdate(isTraditional);
    }
    
    if (!needsUpdate) {
      // 從緩存加載
      searchIndex = await cacheManager.getCachedSearchIndex(isTraditional);
      if (searchIndex) {
        console.log('⚡ 從緩存加載搜索索引（哈希驗證通過）');
      } else {
        console.log('📡 緩存數據丟失，重新下載...');
        needsUpdate = true;
      }
    }
    
    if (needsUpdate) {
      // 從網絡加載
      console.log('📡 從網絡加載搜索索引...');
      searchIndex = await loadSearchIndexWithProgress();
      
      // 保存到緩存並更新哈希
      if (cacheManager && searchIndex) {
        await cacheManager.cacheSearchIndex(searchIndex, isTraditional);
        
        // 獲取並保存哈希值
        const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
        const hashFileName = `${indexFileName}.hash`;
        const hashData = await cacheManager.fetchHashFile(hashFileName);
        if (hashData) {
          await cacheManager.saveHashMetadata(hashData, isTraditional);
          
          // 清除舊的處理後索引緩存（因為原始索引已更新）
          console.log('🗑️ 清除舊的處理後索引緩存...');
          await cacheManager.clearOldProcessedIndexes(isTraditional, hashData.hash);
        }
      }
    }
    
    console.timeEnd('📥 JSON載入時間');
    console.log(`📋 索引記錄數: ${searchIndex.length}`);
    
    // 載入完成，移除載入UI
    elements.searchStatus.removeChild(loadingUI.loadingDiv);
    
    // 創建並配置 MiniSearch 實例
    console.time('🏗️ MiniSearch對象創建');
    const searchConfig = createSearchConfig(segmenterEnabled);
    miniSearch = new MiniSearch(searchConfig);
    console.timeEnd('🏗️ MiniSearch對象創建');
    
    console.log(isTraditionalChinesePage() ? 
      '✅ 使用統一搜索配置' : 
      '✅ 使用统一搜索配置');
      
    // 分批分詞並建立搜索索引（統一處理，支持緩存）
    await buildSearchIndexInBatchesWithCache(miniSearch, searchIndex, elements.searchStatus, segmenterEnabled, cacheManager, isTraditional);
      
    // 完成搜索初始化設置
    finalizeSearchSetup(elements, segmenterEnabled, searchIndex.length);
      
    } catch (error) {
      handleSearchInitError(elements, error);
      return;
    }
    
    // 搜索功能处理
    function performSearch(query) {
      // 重置搜索結果欄位高度（新搜索開始時）
      resetSearchResultsHeight();
      
      if (!miniSearch || !query || query.trim().length < 2) {
        elements.searchResults.style.display = 'none';
        elements.tocHeader.style.display = 'block';
        currentSearchResults = [];
        displayedResultsCount = 0;
        hideLoadMoreButtons();
        if (query && query.trim().length > 0 && query.trim().length < 2) {
          elements.searchStatus.textContent = getI18nText('search.minCharWarning', isTraditionalChinesePage(), '請輸入至少2個字元進行搜尋');
        } else {
          elements.searchStatus.innerHTML = `
            ${getText(`搜索准备就绪 (共${searchIndex ? searchIndex.length : 0}条记录)`, `搜尋準備就緒 (共${searchIndex ? searchIndex.length : 0}條記錄)`)}
          `;
        }
        return;
      }
      
      const trimmedQuery = query.trim();
      
      try {
        let searchQuery = trimmedQuery;
        let searchOptions = {
          boost: { processedContent: 1 } // 只對 processedContent 進行搜索
        };
        
        // 如果啟用了分詞，對用戶查詢進行分詞處理
        if (chineseSegmenter && trimmedQuery.length > 1) {
          const queryWords = segmentWithJieba(trimmedQuery, true);
          if (queryWords.length > 0) {
            // 使用分詞後的詞語進行搜索，用空格連接
            searchQuery = queryWords.join(' ');
          }
        }
        
        // 执行搜索
        const results = miniSearch.search(searchQuery, searchOptions);
        
        // 按MiniSearch的score由高到低排序
        results.sort((a, b) => {
          return b.score - a.score;
        });
        
        // 调试信息：显示前5个结果的score值
        if (results.length > 0) {
          results.slice(0, 5).forEach((result, index) => {
          });
        }
        
        // 保存所有结果
        currentSearchResults = results;
        displayedResultsCount = 0;
        
        if (results.length > 0) {
          // 重置搜索結果容器高度（移除滾動條，保持分頁）
          resetSearchResultsHeight();
          displayPagedResults(trimmedQuery);
        } else {
          displayNoResults(trimmedQuery);
          elements.searchStatus.textContent = getText('未找到匹配结果', '未找到匹配結果');
        }
        
        elements.searchResults.style.display = 'block';
        elements.tocHeader.style.display = 'none';
        
        // 延迟更新浮动控制状态，让DOM变化完成
        setTimeout(updateFloatingControlsState, 10);
        
        // 更新搜索按鈕顯示狀態
        setTimeout(updateBottomSearchButtonsVisibility, 10);
        
      } catch (error) {
        console.error('搜索出错:', error);
        elements.searchStatus.textContent = getText('搜索出现错误，请重试', '搜尋出現錯誤，請重試');
        // 在出错时也隐藏搜索结果
        elements.searchResults.style.display = 'none';
        elements.tocHeader.style.display = 'block';
        
        // 延迟更新浮动控制状态，让DOM变化完成
        setTimeout(updateFloatingControlsState, 10);
      }
    }
    
    // 显示分页搜索结果
    function displayPagedResults(query) {
      // 初始顯示第一頁結果（20條）
      displayedResultsCount = Math.min(RESULTS_PER_PAGE, currentSearchResults.length);
      const resultsToShow = currentSearchResults.slice(0, displayedResultsCount);
      
      displayResults(resultsToShow, query);
      updateResultsCounter();
      updateLoadMoreButtons(); // 根據是否有更多結果顯示按鈕
      
      // 更新搜索状态为成功状态
      const totalResults = currentSearchResults.length;
      const searchStatus = document.getElementById('search-status');
      if (searchStatus) {
      searchStatus.textContent = getText(`找到 ${totalResults} 条匹配结果`, `找到 ${totalResults} 條匹配結果`);
      }
    }
    



    
    // 收縮搜索結果欄位高度 - 已移除收縮功能，此函數保留以維持兼容性
    function collapseSearchResultsHeight() {
      const searchResultsList = document.querySelector('.search-results-list');
      
      if (!searchResultsList) {
        return;
      }
      
      // 保持無高度限制（不再提供收縮功能）
      searchResultsList.style.maxHeight = 'none';
      searchResultsList.style.overflowY = 'visible';
      
      // 移除展開標記
      searchResultsList.removeAttribute('data-expanded');
    }



    // 加载更多结果 - 修正邏輯：只加載20條但展開畫面
    function loadMoreResults() {
      const startIndex = displayedResultsCount;
      const endIndex = Math.min(startIndex + RESULTS_PER_PAGE, currentSearchResults.length);
      const additionalResults = currentSearchResults.slice(startIndex, endIndex);
      
      if (additionalResults.length > 0) {
        // 1. 加載下一批20條結果
        displayedResultsCount = endIndex;
        appendResults(additionalResults);
        updateResultsCounter();
        
        // 2. 展開搜索結果畫面到最大，移除滾動條
        expandSearchResultsHeight();
        updateLoadMoreButtons();
        
        // 更新搜索状态
        const totalResults = currentSearchResults.length;
        const searchStatus = document.getElementById('search-status');
        if (searchStatus) {
        searchStatus.textContent = getText(`找到 ${totalResults} 条匹配结果`, `找到 ${totalResults} 條匹配結果`);
        }
      }
    }
    
    // 加载所有结果
    function loadAllResults() {
      if (displayedResultsCount < currentSearchResults.length) {
        // 1. 加載所有剩餘結果
        const remainingResults = currentSearchResults.slice(displayedResultsCount);
        displayedResultsCount = currentSearchResults.length;
        appendResults(remainingResults);
        updateResultsCounter();
        
        // 2. 展開搜索結果畫面到最大，移除滾動條
        expandSearchResultsHeight();
        updateLoadMoreButtons();
        
        // 更新搜索状态
        const totalResults = currentSearchResults.length;
        const searchStatus = document.getElementById('search-status');
        if (searchStatus) {
        searchStatus.textContent = getText(`找到 ${totalResults} 条匹配结果`, `找到 ${totalResults} 條匹配結果`);
        }
      }
    }
    
    // 調整搜索結果容器高度 - 已預設無限制，此函數保留以維持兼容性
    function adjustSearchResultsHeight() {
      const searchResultsList = document.getElementById('search-results-list');
      const searchResults = document.getElementById('search-results');
      
      if (searchResultsList && searchResults) {
        // 確保無高度限制（預設已是如此）
        searchResultsList.style.maxHeight = 'none';
        searchResultsList.style.overflowY = 'visible';
        
        // 確保搜索結果容器也能完全顯示
        const searchResults = document.getElementById('search-results');
        if (searchResults) {
        searchResults.style.maxHeight = 'none';
        }
        
        console.log('🔧 已調整搜索結果容器為自適應高度');
      }
    }

    
    // 更新结果计数器
    function updateResultsCounter() {
      const totalResults = currentSearchResults.length;
      elements.searchResultsCount.textContent = getText(`显示 ${displayedResultsCount} / ${totalResults} 条结果`, `顯示 ${displayedResultsCount} / ${totalResults} 條結果`);
    }
    

    

    
    // 追加搜索结果到列表
    // 生成單個搜索結果項目的HTML
    function generateSearchResultItem(result, index, indexOffset = 0, query = '') {
      const typeText = {
        'heading': getI18nText('search.resultTypes.heading', isTraditionalChinesePage(), '標題'),
        'question': getI18nText('search.resultTypes.question', isTraditionalChinesePage(), '問題'), 
        'answer': getI18nText('search.resultTypes.answer', isTraditionalChinesePage(), '回答'),
        'content': getI18nText('search.resultTypes.content', isTraditionalChinesePage(), '內容')
      }[result.type] || getText('内容', '內容');
      
      // 智能获取最佳context并高亮搜索关键词
      const bestContext = query ? getBestContextForHighlight(result, query) : result.context;
      const highlightedContext = query ? highlightSearchTerm(bestContext, query) : bestContext;
      
      // 計算全局序號
      const globalIndex = indexOffset + index + 1;
      const totalResults = currentSearchResults.length;
      
      return `
        <li class="search-result-item" data-url="${result.url}">
          <div class="search-result-header">
            <span class="search-result-number">${globalIndex}/${totalResults}</span>
            <span class="search-result-type">${typeText}</span>
            <div class="search-result-title">
              ${escapeHtml(result.title)}
            </div>
          </div>
          <div class="search-result-content">${highlightedContext}</div>
        </li>
      `;
    }

    function appendResults(results) {
      const query = document.getElementById('search-input').value.trim();
      const startIndex = displayedResultsCount - results.length; // 計算當前批次的起始序號
      
      const additionalHTML = results.map((result, index) => 
        generateSearchResultItem(result, index, startIndex, query)
      ).join('');
      
      elements.searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);
    }
    
    // 显示搜索结果（原函数，现在用于内部调用）
    function displayResults(results, query) {
      elements.searchResultsList.innerHTML = results.map((result, index) => 
        generateSearchResultItem(result, index, 0, query)
      ).join('');
    }
    
    // 显示无结果
    function displayNoResults(query) {
      elements.searchResultsCount.textContent = getText('未找到结果', '未找到結果');
      elements.searchResultsList.innerHTML = `
        <li class="search-result-item" style="text-align: center; color: #999;">
          <div>${getText(`未找到包含"${escapeHtml(query)}"的内容`, `未找到包含"${escapeHtml(query)}"的內容`)}</div>
          <div style="font-size: 12px; margin-top: 8px;">${getText('尝试使用不同的关键词', '嘗試使用不同的關鍵詞')}</div>
        </li>
      `;
    }
    
    // 转义正则表达式特殊字符
    function escapeRegex(str) {
      if (!str || typeof str !== 'string') {
        return '';
      }
      // 简单的字符串替换，避免复杂的正则表达式
      const chars = {
        '\\\\': '\\\\\\\\',
        '.': '\\\\.',
        '*': '\\\\*',
        '+': '\\\\+',
        '?': '\\\\?',
        '^': '\\\\^',
        '$': '\\\\$',
        '{': '\\\\{',
        '}': '\\\\}',
        '(': '\\\\(',
        ')': '\\\\)',
        '|': '\\\\|',
        '[': '\\\\[',
        ']': '\\\\]',
        '/': '\\\\/'
      };
      let result = str;
      Object.keys(chars).forEach(char => {
        result = result.split(char).join(chars[char]);
      });
      return result;
    }
    
    // 转义HTML特殊字符
    function escapeHtml(str) {
      if (!str || typeof str !== 'string') {
        return '';
      }
      try {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
      } catch (e) {
        console.warn('HTML转义失败:', e);
        // 降级处理：手动替换基本的HTML字符
        return str.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&#39;');
      }
    }
    
    // 智能获取最佳context用于高亮显示
    function getBestContextForHighlight(result, query) {
      if (!query || !result.content) {
        return result.context || result.content;
      }
      
      const searchTerm = query.trim();
      const content = result.content;
      const lowerContent = content.toLowerCase();
      const lowerSearchTerm = searchTerm.toLowerCase();
      
      // 如果沒有 context 或 context 為空，使用 content
      if (!result.context) {
        return content;
      }
      
      // 如果原context包含完整搜索词，直接使用
      if (result.context.toLowerCase().includes(lowerSearchTerm)) {
        return result.context;
      }
      
      // 尝试完整匹配
      const exactIndex = lowerContent.indexOf(lowerSearchTerm);
      if (exactIndex !== -1) {
        return extractContextAroundPosition(content, exactIndex, 120);
      }
      
      // 智能分词：将搜索词拆分为多个关键词
      const keywords = extractKeywords(searchTerm);
      
      if (keywords.length <= 1) {
        // 单个关键词，使用原有逻辑
        return result.context || result.content;
      }
      
      // 多关键词处理：找到所有关键词的位置
      const keywordPositions = [];
      keywords.forEach(keyword => {
        const lowerKeyword = keyword.toLowerCase();
        let index = lowerContent.indexOf(lowerKeyword);
        while (index !== -1) {
          keywordPositions.push({
            keyword: keyword,
            position: index,
            length: keyword.length
          });
          index = lowerContent.indexOf(lowerKeyword, index + 1);
        }
      });
      
      if (keywordPositions.length === 0) {
        return result.context || result.content;
      }
      
      // 生成包含所有关键词的最佳context
      return generateMultiKeywordContext(content, keywordPositions, 150);
    }
    
    // 提取关键词（简单的中文分词）
    function extractKeywords(searchTerm) {
      // 移除多余空格
      const cleaned = searchTerm.trim().replace(/\s+/g, ' ');
      
      // 按空格分割
      const spaceWords = cleaned.split(' ').filter(word => word.length > 0);
      
      // 如果有空格分割的结果，使用它们
      if (spaceWords.length > 1) {
        return spaceWords;
      }
      
      // 中文智能分词（简单版本）
      const keywords = [];
      const text = cleaned;
      
      // 2-4字的常见词组模式
      const commonPatterns = [
        /[\u4e00-\u9fff]{2,4}/g  // 2-4个中文字符的组合
      ];
      
      // 如果输入较短（<=4字符），尝试按2字符分割
      if (text.length <= 4) {
        for (let i = 0; i < text.length; i += 2) {
          const word = text.substr(i, 2);
          if (word.length >= 2) {
            keywords.push(word);
          }
        }
      } else {
        // 较长输入，尝试更智能的分割
        // 先尝试按常见的2字词分割
        for (let i = 0; i < text.length - 1; i++) {
          const word2 = text.substr(i, 2);
          const word3 = text.substr(i, 3);
          
          // 优先选择3字词，然后是2字词
          if (i < text.length - 2 && isLikelyWord(word3)) {
            keywords.push(word3);
            i += 2; // 跳过下一个字符
          } else if (isLikelyWord(word2)) {
            keywords.push(word2);
            i += 1; // 跳过下一个字符
          }
        }
      }
      
      // 如果没有找到合适的分词，返回原始输入
      return keywords.length > 0 ? keywords : [text];
    }
    
    // 简单判断是否像一个词（可以扩展更复杂的逻辑）
    function isLikelyWord(word) {
      // 基本的中文词汇判断
      return /^[\u4e00-\u9fff]+$/.test(word) && word.length >= 2;
    }
    
    // 生成包含多个关键词的context
    function generateMultiKeywordContext(content, keywordPositions, maxLength = 150) {
      if (keywordPositions.length === 0) {
        return content.substring(0, maxLength);
      }
      
      // 按位置排序
      keywordPositions.sort((a, b) => a.position - b.position);
      
      // 计算覆盖范围
      const firstPos = keywordPositions[0].position;
      const lastPos = keywordPositions[keywordPositions.length - 1];
      const lastEnd = lastPos.position + lastPos.length;
      const totalSpan = lastEnd - firstPos;
      
      // 如果所有关键词都在合理范围内，生成包含所有的context
      if (totalSpan <= maxLength * 0.8) {
        const contextStart = Math.max(0, firstPos - Math.floor((maxLength - totalSpan) / 2));
        const contextEnd = Math.min(content.length, contextStart + maxLength);
        
        let context = content.substring(contextStart, contextEnd);
        
        // 添加省略号
        if (contextStart > 0) context = '...' + context;
        if (contextEnd < content.length) context = context + '...';
        
        return context;
      }
      
      // 如果关键词分布太散，选择最重要的几个
      const importantPositions = selectImportantPositions(keywordPositions, maxLength);
      
      // 为每个重要位置生成小段context，然后合并
      const contextParts = [];
      importantPositions.forEach(pos => {
        const partLength = Math.floor(maxLength / importantPositions.length);
        const start = Math.max(0, pos.position - Math.floor(partLength / 2));
        const end = Math.min(content.length, start + partLength);
        
        let part = content.substring(start, end);
        if (start > 0) part = '...' + part;
        if (end < content.length) part = part + '...';
        
        contextParts.push(part);
      });
      
      return contextParts.join(' ');
    }
    
    // 选择最重要的关键词位置
    function selectImportantPositions(positions, maxLength) {
      // 简单策略：选择前几个不重叠的位置
      const selected = [];
      const minDistance = 20; // 最小距离
      
      for (const pos of positions) {
        const tooClose = selected.some(sel => 
          Math.abs(sel.position - pos.position) < minDistance
        );
        
        if (!tooClose) {
          selected.push(pos);
        }
        
        // 限制数量
        if (selected.length >= 3) break;
      }
      
      return selected.length > 0 ? selected : [positions[0]];
    }
    
    // 从指定位置提取上下文
    function extractContextAroundPosition(text, position, maxLength = 100) {
      const halfLength = Math.floor(maxLength / 2);
      let start = Math.max(0, position - halfLength);
      let end = Math.min(text.length, position + halfLength);
      
      // 尝试在词边界处截断，避免截断词语
      if (start > 0) {
        const beforeText = text.substring(start - 10, start);
        const spaceIndex = beforeText.lastIndexOf(' ');
        const punctIndex = Math.max(
          beforeText.lastIndexOf('。'),
          beforeText.lastIndexOf('，'),
          beforeText.lastIndexOf('！'),
          beforeText.lastIndexOf('？')
        );
        if (spaceIndex !== -1 || punctIndex !== -1) {
          start = start - 10 + Math.max(spaceIndex, punctIndex) + 1;
        }
      }
      
      if (end < text.length) {
        const afterText = text.substring(end, end + 10);
        const spaceIndex = afterText.indexOf(' ');
        const punctIndex = Math.min(
          afterText.indexOf('。') !== -1 ? afterText.indexOf('。') : Infinity,
          afterText.indexOf('，') !== -1 ? afterText.indexOf('，') : Infinity,
          afterText.indexOf('！') !== -1 ? afterText.indexOf('！') : Infinity,
          afterText.indexOf('？') !== -1 ? afterText.indexOf('？') : Infinity
        );
        if (spaceIndex !== -1 || punctIndex !== Infinity) {
          end = end + Math.min(spaceIndex !== -1 ? spaceIndex : Infinity, punctIndex);
        }
      }
      
      let context = text.substring(start, end);
      
      // 添加省略号
      if (start > 0) context = '...' + context;
      if (end < text.length) context = context + '...';
      
      return context;
    }

    // 智能高亮搜索关键词（支持多关键词）
    function highlightSearchTerm(text, searchTerm) {
      if (!text || !searchTerm || typeof text !== 'string' || typeof searchTerm !== 'string') {
        return text;
      }
      
      const term = searchTerm.trim();
      if (!term) return text;
      
      try {
        // 首先尝试完整匹配
        const exactRegex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        let result = text.replace(exactRegex, '<span class="search-result-highlight">$1</span>');
        
        if (result !== text) {
          return result;
        }
        
        // 如果完整匹配失败，尝试多关键词高亮
        const keywords = extractKeywords(term);
      
        if (keywords.length > 1) {
          // 多关键词高亮
          result = highlightMultipleKeywords(text, keywords);
          if (result !== text) {
            return result;
          }
        }
        
        // 回退到原有的模糊匹配逻辑
        return highlightWithFuzzyMatching(text, term);
        
      } catch (e) {
        console.warn('智能高亮处理失败:', e, '搜索词:', term);
        return highlightWithFuzzyMatching(text, term);
      }
    }
    
    // 多关键词高亮
    function highlightMultipleKeywords(text, keywords) {
      let result = text;
      let hasMatch = false;
      
      // 按长度排序，先处理长的关键词，避免短词覆盖长词
      const sortedKeywords = keywords.sort((a, b) => b.length - a.length);
      
      sortedKeywords.forEach(keyword => {
        const keywordRegex = new RegExp(`(${escapeRegex(keyword)})`, 'gi');
        const beforeReplace = result;
        result = result.replace(keywordRegex, '<span class="search-result-highlight">$1</span>');
        
        if (result !== beforeReplace) {
          hasMatch = true;
        }
      });
      
      return hasMatch ? result : text;
    }
    
    // 模糊匹配高亮（原有逻辑）
    function highlightWithFuzzyMatching(text, term) {
      try {
        // 策略1: 忽略标点符号的模糊匹配
        const punctuation = '[\\s\\u3000-\\u303F\\uFF00-\\uFFEF\\u2000-\\u206F\\u0020-\\u002F\\u003A-\\u0040\\u005B-\\u0060\\u007B-\\u007E\\u2010-\\u2027\\u2030-\\u205F\\u3001-\\u3003\\u3008-\\u3011\\u3014-\\u301F\\uFE10-\\uFE19\\uFE30-\\uFE6F]';
        
        const flexiblePattern = term.split('').map(char => {
          return escapeRegex(char);
        }).join(`${punctuation}*`);
        
        const flexibleRegex = new RegExp(`(${flexiblePattern})`, 'gi');
        let result = text.replace(flexibleRegex, '<span class="search-result-highlight">$1</span>');
        
        if (result !== text) {
          return result;
        }
        
        // 策略2: 字符级模糊匹配
        const chars = term.split('');
        if (chars.length > 1) {
          const charPattern = chars.map(char => escapeRegex(char)).join(`${punctuation}*`);
          const charRegex = new RegExp(`(${charPattern})`, 'gi');
          
          result = text.replace(charRegex, '<span class="search-result-highlight">$1</span>');
          if (result !== text) {
            return result;
          }
        }
        
        // 策略3: 单字符逐个匹配
        chars.forEach(char => {
          if (char.trim()) {
            const singleCharRegex = new RegExp(`(${escapeRegex(char)})`, 'gi');
            result = result.replace(singleCharRegex, '<span class="search-result-highlight">$1</span>');
          }
        });
        
        return result;
        
      } catch (e) {
        console.warn('模糊高亮处理失败:', e);
        // 最后的安全降级
        try {
          const simpleRegex = new RegExp(term.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&'), 'gi');
          return text.replace(simpleRegex, '<span class="search-result-highlight">$&</span>');
        } catch (e2) {
          console.warn('简单高亮也失败:', e2);
          return text;
        }
      }
    }
    
    // 清除搜索
    function clearSearch() {
      const searchInput = document.getElementById('search-input');
      const searchResults = document.getElementById('search-results');
      const tocHeader = document.getElementById('toc-header');
      const searchStatus = document.getElementById('search-status');
      
      if (searchInput) searchInput.value = '';
      if (searchResults) searchResults.style.display = 'none';
      if (tocHeader) tocHeader.style.display = 'block';
      currentSearchResults = [];
      displayedResultsCount = 0;
      hideLoadMoreButtons();
      
      // 重置搜索結果容器高度
      resetSearchResultsHeight();
      
      if (searchStatus) {
        const recordCount = searchIndex ? searchIndex.length : 0;
      searchStatus.innerHTML = `
          ${getText(`搜索准备就绪 (共${recordCount}条记录)`, `搜尋準備就緒 (共${recordCount}條記錄)`)}
      `;
      }
    }
    
    // 事件监听
    let searchTimeout;
    elements.searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();
      
      // 防抖处理
      searchTimeout = setTimeout(() => {
        performSearch(query);
      }, 300);
    });
    
    // 清除搜索按钮
    elements.searchClear.addEventListener('click', clearSearch);
    
    // 收起搜索按钮
    elements.searchCollapse.addEventListener('click', collapseSearch);
    
    // 顯示更多按鈕（頂部和底部）
    const loadMoreBtn = document.getElementById('search-load-more');
    const loadAllBtn = document.getElementById('search-load-all');
    const loadMoreBtnBottom = document.getElementById('search-load-more-bottom');
    const loadAllBtnBottom = document.getElementById('search-load-all-bottom');
    
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', loadMoreResults);
    }
    
    if (loadAllBtn) {
      loadAllBtn.addEventListener('click', loadAllResults);
    }
    
    // 底部按鈕事件監聽器
    if (loadMoreBtnBottom) {
      loadMoreBtnBottom.addEventListener('click', loadMoreResults);
    }
    
    if (loadAllBtnBottom) {
      loadAllBtnBottom.addEventListener('click', loadAllResults);
    }
    
    // 底部清除和收起按鈕
    const searchClearBottom = document.getElementById('search-clear-bottom');
    const searchCollapseBottom = document.getElementById('search-collapse-bottom');
    
    if (searchClearBottom) {
      searchClearBottom.addEventListener('click', clearSearch);
    }
    
    if (searchCollapseBottom) {
      searchCollapseBottom.addEventListener('click', collapseSearch);
    }
    
    // 搜索结果点击
    elements.searchResultsList.addEventListener('click', (e) => {
      const item = e.target.closest('.search-result-item');
      if (item) {
        const url = item.dataset.url;
        if (url) {
          // 检查是否按住修饰键
          if (e.ctrlKey || e.metaKey) {
            // Ctrl/Cmd+Click：在新标签页打开（静默）
            window.open(url, '_blank', 'noopener,noreferrer');
          } else if (e.shiftKey) {
            // Shift+Click：在新窗口打开
            window.open(url, '_blank', 'noopener,noreferrer,width=1200,height=800');
          } else {
            // 默认：在新标签页打开
            window.open(url, '_blank', 'noopener,noreferrer');
          }
        }
      }
    });
    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
      // Ctrl+F 快捷键已禁用，不再激活搜索功能
      // 用户可以使用浏览器原生的 Ctrl+F 进行页面内搜索
      

    });
  }
  
  // 收起搜索功能
  function collapseSearch() {
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const tocHeader = document.getElementById('toc-header');
    
    if (searchContainer && searchActivation) {
      // 清除搜索内容和重置分页状态
      if (searchInput) searchInput.value = '';
      if (searchResults) searchResults.style.display = 'none';
      if (tocHeader) tocHeader.style.display = 'block';
      
      // 重置分页状态
      currentSearchResults = [];
      displayedResultsCount = 0;
      hideLoadMoreButtons();
      
      // 清空搜索狀態和結果顯示
      const searchStatus = document.getElementById('search-status');
      const searchResultsList = document.getElementById('search-results-list');
      const searchResultsCount = document.getElementById('search-results-count');
      
      if (searchStatus) {
        searchStatus.innerHTML = '';
      }
      if (searchResultsList) {
        searchResultsList.innerHTML = '';
      }
      if (searchResultsCount) {
        searchResultsCount.textContent = '';
      }
      
      // 重置搜索結果容器高度
      // 重用已聲明的 searchResultsList 和 searchResults 變數
      if (searchResultsList && searchResults) {
        searchResultsList.style.maxHeight = '';
        searchResultsList.style.overflowY = '';
        searchResults.style.maxHeight = '';
      }
      
      // 隐藏搜索容器，显示激活按钮
      searchContainer.style.display = 'none';
      searchActivation.style.display = 'block';
      
      // 延迟更新浮动控制状态，让DOM变化完成
      setTimeout(updateFloatingControlsState, 10);
    }
  }
  
  // 如果是首页，添加搜索激活事件监听
  if (isIndexPage()) {
    const searchActivateBtn = document.getElementById('search-activate-btn');
    if (searchActivateBtn) {
      searchActivateBtn.addEventListener('click', activateSearch);
    }
    
    // Ctrl+F 快捷键已禁用，不再激活搜索功能
    // 用户可以使用浏览器原生的 Ctrl+F 进行页面内搜索
  }

  // 創建閱讀工具欄
  function createReadingToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'reading-toolbar hidden';
    toolbar.innerHTML = 
      '<div class="toolbar-header">' +
        '<span>⚙️ ' + getI18nText('readingSettings.title', isTraditionalChinesePage(), '閱讀設置') + '</span>' +
        '<button class="ctrl-btn" data-action="close-toolbar">✕</button>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + 
          getI18nText('readingSettings.fontSize', isTraditionalChinesePage(), '字體大小') + 
        '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn font-adjust" data-action="font-decrease" title="縮小字體">' + getI18nText('readingSettings.fontDecrease', isTraditionalChinesePage(), 'A-') + '</button>' +
          '<button class="ctrl-btn font-option active" data-action="font-normal" title="重置為默認字體">' + getI18nText('readingSettings.fontNormal', isTraditionalChinesePage(), 'A') + '</button>' +
          '<button class="ctrl-btn font-adjust" data-action="font-increase" title="放大字體">' + getI18nText('readingSettings.fontIncrease', isTraditionalChinesePage(), 'A+') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.lineHeight', isTraditionalChinesePage(), '行距') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="line-tight">' + getI18nText('readingSettings.lineTight', isTraditionalChinesePage(), '緊密') + '</button>' +
          '<button class="ctrl-btn active" data-action="line-normal">' + getI18nText('readingSettings.lineNormal', isTraditionalChinesePage(), '正常') + '</button>' +
          '<button class="ctrl-btn" data-action="line-loose">' + getI18nText('readingSettings.lineLoose', isTraditionalChinesePage(), '寬鬆') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.width', isTraditionalChinesePage(), '寬度') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="width-narrow">' + getI18nText('readingSettings.widthNarrow', isTraditionalChinesePage(), '窄') + '</button>' +
          '<button class="ctrl-btn active" data-action="width-normal">' + getI18nText('readingSettings.widthNormal', isTraditionalChinesePage(), '中') + '</button>' +
          '<button class="ctrl-btn" data-action="width-wide">' + getI18nText('readingSettings.widthWide', isTraditionalChinesePage(), '寬') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.theme', isTraditionalChinesePage(), '主題') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="theme-light">' + getI18nText('readingSettings.themeLight', isTraditionalChinesePage(), '☀️ 日間') + '</button>' +
          '<button class="ctrl-btn" data-action="theme-dark">' + getI18nText('readingSettings.themeDark', isTraditionalChinesePage(), '🌙 夜間') + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(toolbar);
    return toolbar;
  }
  
  // 更新主題按鈕狀態
  function updateThemeButtons() {
    const isDark = document.body.classList.contains('dark-mode');
    const lightBtn = document.querySelector('[data-action="theme-light"]');
    const darkBtn = document.querySelector('[data-action="theme-dark"]');
    
    if (lightBtn && darkBtn) {
      lightBtn.classList.toggle('active', !isDark);
      darkBtn.classList.toggle('active', isDark);
    }
  }

  // 更新閱讀設置按鈕狀態
  function updateReadingSettingsButtons() {
    updateFontSizeButtons();
    updateLineHeightButtons();
    updateContentWidthButtons();
  }

  // 更新字體大小按鈕狀態
  function updateFontSizeButtons() {
    // 只更新選項按鈕的狀態，不影響調整按鈕
    const fontOptionBtns = document.querySelectorAll('[data-action^="font-"].font-option');
    fontOptionBtns.forEach(btn => btn.classList.remove('active'));
    
    // 根據當前字體大小標記對應按鈕
    const defaultFontSize = getDefaultFontSize();
    if (fontSize === defaultFontSize || fontSize === 16) {
      const normalBtn = document.querySelector('[data-action="font-normal"]');
      if (normalBtn) normalBtn.classList.add('active');
    }
    
    // A- 和 A+ 按鈕使用 font-adjust 類，不參與 active 狀態管理
  }

  // 更新行距按鈕狀態
  function updateLineHeightButtons() {
    const lineHeightBtns = document.querySelectorAll('[data-action^="line-"]');
    lineHeightBtns.forEach(btn => btn.classList.remove('active'));
    
    let activeLineHeightBtn = null;
    if (lineHeight === 1.2) {
      activeLineHeightBtn = document.querySelector('[data-action="line-tight"]');
    } else if (lineHeight === 1.6) {
      activeLineHeightBtn = document.querySelector('[data-action="line-normal"]');
    } else if (lineHeight === 2.0) {
      activeLineHeightBtn = document.querySelector('[data-action="line-loose"]');
    }
    
    if (activeLineHeightBtn) {
      activeLineHeightBtn.classList.add('active');
    }
  }

  // 更新內容寬度按鈕狀態
  function updateContentWidthButtons() {
    const widthBtns = document.querySelectorAll('[data-action^="width-"]');
    widthBtns.forEach(btn => btn.classList.remove('active'));
    
    let activeWidthBtn = null;
    if (contentWidth === 600) {
      activeWidthBtn = document.querySelector('[data-action="width-narrow"]');
    } else if (contentWidth === 800) {
      activeWidthBtn = document.querySelector('[data-action="width-normal"]');
    } else if (contentWidth === 1000) {
      activeWidthBtn = document.querySelector('[data-action="width-wide"]');
    }
    
    if (activeWidthBtn) {
      activeWidthBtn.classList.add('active');
    }
  }

  // 創建閱讀進度條
  function createReadingProgress() {
    const progress = document.createElement('div');
    progress.className = 'reading-progress';
    progress.innerHTML = '<div class="reading-progress-bar"></div>';
    document.body.appendChild(progress);
    return progress;
  }

  // 創建浮動目錄
  function createFloatingTOC() {
    const toc = document.createElement('div');
    toc.className = 'floating-toc';
    
    let tocItems = '';
    
    if (currentChapter.isHomepage) {
      // 首頁：從TOC連結提取目錄結構
      const tocLinks = document.querySelectorAll('h2 + ul li a, ul li a');
      tocLinks.forEach((link, index) => {
        const text = link.textContent;
        const href = link.getAttribute('href');
        
        // 更準確的層級判斷：計算嵌套深度
        const listItem = link.closest('li');
        let level = 0;
        let currentElement = listItem.parentElement; // 从ul开始计算
        
        // 向上遍歷，計算嵌套的ul層數
        while (currentElement && currentElement.tagName === 'UL') {
          level++;
          // 跳过li，直接到下一个ul
          currentElement = currentElement.parentElement;
          if (currentElement && currentElement.tagName === 'LI') {
            currentElement = currentElement.parentElement;
          }
        }
        
        // 根據層級添加對應的class (level=1是第一层，无缩进)
        // 顯示前四層目錄，跳過第五層及以下
        if (level >= 5) {
          return; // 跳過第五層及以下的項目
        }
        
        let levelClass = '';
        if (level === 2) {
          levelClass = ' level-h3';
        } else if (level === 3) {
          levelClass = ' level-h4';
        } else if (level === 4) {
          levelClass = ' level-h5';  // Note: this maps to what would be level 4 content
        }
        
        // 為首頁TOC項目使用特殊的data屬性
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-href="' + href + '">' + text + '</div>';
      });
    } else {
      // 其他頁面：收集標題
      const headings = document.querySelectorAll('h2, h3, h4');
      headings.forEach((heading, index) => {
        const text = heading.textContent;
        const id = heading.id || ('heading-' + index);
        if (!heading.id) heading.id = id;
        
        const level = heading.tagName.toLowerCase();
        const levelClass = level !== 'h2' ? ' level-' + level : '';
        
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-target="#' + id + '">' + text + '</div>';
      });
    }
    
    // 根據是否為首頁決定標籤頁內容
    let tabsHtml = '';
    let contentHtml = '';
    
    if (currentChapter.isHomepage) {
      // 首頁只顯示書籤，不顯示目錄標籤（因為首頁本身就是目錄）
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="bookmarks">📖 ' + getI18nText('bookmark.myBookmarks', isTraditionalChinesePage(), '我的書籤') + ' <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<ul id="bookmarks-list" class="floating-toc-list" style="display: block;">' +
          '<li class="bookmarks-empty">' + getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>' +
        '</ul>';
    } else {
      // 其他頁面顯示目錄和書籤
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="toc">' + getI18nText('navigation.tableOfContents', isTraditionalChinesePage(), '目錄') + '</button>' +
        '<button class="floating-toc-tab" data-tab="bookmarks">' + getI18nText('navigation.bookmarks', isTraditionalChinesePage(), '書籤') + ' <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<ul id="toc-list" class="floating-toc-list">' +
          tocItems +
        '</ul>' +
        '<ul id="bookmarks-list" class="floating-toc-list" style="display: none;">' +
          '<li class="bookmarks-empty">' + getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>' +
        '</ul>';
    }
    
    // 根據頁面類型設定初始標題
    const initialTitle = currentChapter.isHomepage ? 
      '🔖 ' + getI18nText('bookmark.myBookmarks', isTraditionalChinesePage(), '我的書籤') : 
      '📖 ' + getI18nText('navigation.chapterDirectory', isTraditionalChinesePage(), '章節目錄');
    
    toc.innerHTML = 
      '<div class="floating-toc-header">' +
        '<span id="toc-title">' + initialTitle + '</span>' +
        '<button class="ctrl-btn" data-action="close-toc">✕</button>' +
      '</div>' +
      '<div class="floating-toc-tabs">' +
        tabsHtml +
      '</div>' +
      '<div class="floating-toc-content">' +
        contentHtml +
      '</div>';
    
    // 檢查是否已存在靜態TOC，如果有則替換，否則添加新的
    const existingTOC = document.getElementById('floating-toc');
    if (existingTOC) {
      existingTOC.parentNode.replaceChild(toc, existingTOC);
    } else {
      document.body.appendChild(toc);
    }
    return toc;
  }

  // 創建操作按鈕組
  function createActionButtons() {
    const buttons = document.createElement('div');
    buttons.className = 'action-buttons';
    
    // 根據頁面類型設置第一個按鈕的內容
    const firstBtnIcon = currentChapter.isHomepage ? '🔖' : '📖';
    const firstBtnTitle = currentChapter.isHomepage ? 
      getI18nText('navigation.bookmarks', isTraditionalChinesePage(), '書籤') : 
      getI18nText('ui.tableOfContents', isTraditionalChinesePage(), '目錄');
    
    // 為章節頁面添加回首頁按鈕
    const homeButton = currentChapter.isHomepage ? '' : 
      '<button class="action-btn" data-action="home" title="' + getI18nText('ui.home', isTraditionalChinesePage(), '回首頁') + '">🏠</button>';
    
    buttons.innerHTML = 
      '<div class="action-menu">' +
        '<button class="action-btn menu-btn" data-action="toggle-menu" title="' + getI18nText('ui.functionMenu', isTraditionalChinesePage(), '功能選單') + '">☰</button>' +
        '<div class="action-menu-items">' +
          '<button class="action-btn" data-action="toc" title="' + firstBtnTitle + '">' + firstBtnIcon + '</button>' +
          homeButton +
          '<button class="action-btn" data-action="top" title="' + getI18nText('ui.backToTop', isTraditionalChinesePage(), '回到頂部') + '">↑</button>' +
          '<button class="action-btn" data-action="settings" title="' + getI18nText('ui.settings', isTraditionalChinesePage(), '設置') + '">⚙️</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(buttons);
    return buttons;
  }

  // 為問答添加互動按鈕
  function addQAActions() {
    const qaElements = document.querySelectorAll('.question, .answer');
    qaElements.forEach((element) => {
      // 確保元素有唯一ID（用於分享功能）
      const prefix = element.classList.contains('question') ? 'question' : 'answer';
      ensureElementId(element, prefix);
      
      element.style.position = 'relative';
      const actions = document.createElement('div');
      actions.className = 'qa-actions';
      
      const isQuestion = element.classList.contains('question');
      const isAnswer = element.classList.contains('answer');
      
      // 首頁不顯示書籤按鈕
      let actionsHtml = '';
      
      if (isQuestion) {
        actionsHtml += `<button class="qa-btn" data-action="copy-qa" title="${getText('复制问答', '複製問答')}">📋</button>`;
        if (!currentChapter.isHomepage) {
          actionsHtml += `<button class="qa-btn" data-action="bookmark-qa" title="${getText('加入书签', '加入書籤')}">🔖</button>`;
        }
        actionsHtml += `<button class="qa-btn" data-action="share" title="${getText('分享问题', '分享問題')}">📤</button>`;
      } else if (isAnswer) {
        actionsHtml += `<button class="qa-btn" data-action="copy-qa" title="${getText('复制问答', '複製問答')}">📋</button>`;
        if (!currentChapter.isHomepage) {
          actionsHtml += `<button class="qa-btn" data-action="bookmark-qa" title="${getText('加入书签', '加入書籤')}">🔖</button>`;
        }
        actionsHtml += `<button class="qa-btn" data-action="share" title="${getText('分享回答', '分享回答')}">📤</button>`;
      }
      
      actions.innerHTML = actionsHtml;
      element.appendChild(actions);
    });
  }

