  // ============ 搜索功能（延迟加载） ============
  // isIndexPage / isTraditionalChinesePage / getText 由 00-base.js 提供

  let searchIndex = null;
  let miniSearch = null;
  let searchInitialized = false;
  let currentSearchResults = [];
  let displayedResultsCount = 0;
  const RESULTS_PER_PAGE = 20;

  // 获取搜索索引文件名
  function getSearchIndexFile() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index_trad.html' ? 'search_index_trad.json' : 'search_index.json';
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
