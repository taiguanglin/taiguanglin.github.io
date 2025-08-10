document.addEventListener('DOMContentLoaded', function() {
  // ============ 基本設置 ============
  
  // 暗色模式初始化
  if(localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }

  // ============ UX 增強功能 ============
  
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
      
      updateLoadingText(getI18nText('search.indexReady', isTraditionalChinesePage(), '搜尋準備就緒 (共{count}條記錄)', { count: searchIndex.length }));
      
      return searchIndex;
      
    } catch (error) {
      console.error('載入搜索索引失敗:', error);
      throw error;
    }
  }
  
  // 初始化搜索功能（内部函数）
  async function initSearch() {
    if (!isIndexPage()) return;
    
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchStatus = document.getElementById('search-status');
    const searchResults = document.getElementById('search-results');
    const searchResultsList = document.getElementById('search-results-list');
    const searchResultsCount = document.getElementById('search-results-count');
    const searchClear = document.getElementById('search-clear');
    const searchCollapse = document.getElementById('search-collapse');
    const tocHeader = document.getElementById('toc-header');
    
    if (!searchInput || !searchContainer) return;
    
    try {
      // 显示搜索容器，隐藏激活按钮
      if (searchActivation) searchActivation.style.display = 'none';
      searchContainer.style.display = 'block';
      
      // 清空當前狀態並創建載入UI
      searchStatus.innerHTML = '';
      const loadingUI = createLoadingUI(searchStatus);
      
      // 检查MiniSearch是否可用
      if (typeof MiniSearch === 'undefined') {
        throw new Error('MiniSearch库未加载');
      }
      
      // 加载搜索索引（帶進度）
      searchIndex = await loadSearchIndexWithProgress();
      
      // 載入完成，移除載入UI
      searchStatus.removeChild(loadingUI.loadingDiv);
      
      // 初始化MiniSearch
      miniSearch = new MiniSearch({
        fields: ['title', 'content'], // 搜索字段
        storeFields: ['id', 'title', 'type', 'content', 'context', 'url', 'weight'], // 存储字段
        searchOptions: {
          boost: { title: 3, content: 1 }, // 标题权重更高
          fuzzy: 0.2, // 模糊搜索
          prefix: true // 前缀匹配
        },
        extractField: (document, fieldName) => {
          // 为中文优化：简单字符分割
          const text = document[fieldName] || '';
          return text;
        }
      });
      
      // 添加文档到索引
      miniSearch.addAll(searchIndex);
      
      // 顯示完成狀態
      searchStatus.innerHTML = `
        <div class="search-status-success">
          ✅ ${getI18nText('search.indexReady', isTraditionalChinesePage(), '搜尋準備就緒 (共{count}條記錄)', { count: searchIndex.length })}
        </div>
      `;
      searchInitialized = true;
      
      // 启用搜索输入框
      searchInput.disabled = false;
      searchInput.placeholder = getI18nText('search.search_placeholder', isTraditionalChinesePage(), '搜尋全文內容...');
      
      // 重新启用激活按钮
      const searchActivateBtn = document.getElementById('search-activate-btn');
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
      }
      
      // 聚焦搜索框
      setTimeout(() => searchInput.focus(), 100);
      
    } catch (error) {
      console.error('搜索初始化失败:', error);
      
      // 清空狀態並顯示錯誤
      searchStatus.innerHTML = '';
      
      // 創建錯誤UI並提供重試功能
      createErrorUI(searchStatus, error.message || getI18nText('search.loadingFailed', isTraditionalChinesePage(), '搜尋索引載入失敗'), async () => {
        await initSearch();
      });
      
      // 即使失败也要启用输入框，让用户可以重试
      searchInput.disabled = false;
      searchInput.placeholder = getI18nText('search.searchUnavailable', isTraditionalChinesePage(), '搜尋功能暫不可用');
      
      // 重新启用激活按钮，允许用户重试
      const searchActivateBtn = document.getElementById('search-activate-btn');
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
      }
      
      return;
    }
    
    // 搜索功能处理
    function performSearch(query) {
      if (!miniSearch || !query || query.trim().length < 2) {
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
        currentSearchResults = [];
        displayedResultsCount = 0;
        hideLoadMoreButtons();
        if (query && query.trim().length > 0 && query.trim().length < 2) {
          searchStatus.textContent = getText('请输入至少2个字符进行搜索', '請輸入至少2個字元進行搜尋');
        } else {
          searchStatus.innerHTML = `
            ${getText(`搜索准备就绪 (共${searchIndex ? searchIndex.length : 0}条记录)`, `搜尋準備就緒 (共${searchIndex ? searchIndex.length : 0}條記錄)`)}
          `;
        }
        return;
      }
      
      const trimmedQuery = query.trim();
      
      try {
        // 执行搜索
        const results = miniSearch.search(trimmedQuery, {
          boost: { title: 3, content: 1 },
          fuzzy: 0.2,
          prefix: true
        });
        
        // 按权重和评分排序
        results.sort((a, b) => {
          const scoreA = a.score * (a.weight || 1);
          const scoreB = b.score * (b.weight || 1);
          return scoreB - scoreA;
        });
        
        // 保存所有结果
        currentSearchResults = results;
        displayedResultsCount = 0;
        
        if (results.length > 0) {
          displayPagedResults(trimmedQuery);
        } else {
          displayNoResults(trimmedQuery);
          searchStatus.textContent = getText('未找到匹配结果', '未找到匹配結果');
        }
        
        searchResults.style.display = 'block';
        tocHeader.style.display = 'none';
        
        // 延迟更新浮动控制状态，让DOM变化完成
        setTimeout(updateFloatingControlsState, 10);
        
      } catch (error) {
        console.error('搜索出错:', error);
        searchStatus.textContent = getText('搜索出现错误，请重试', '搜尋出現錯誤，請重試');
        // 在出错时也隐藏搜索结果
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
        
        // 延迟更新浮动控制状态，让DOM变化完成
        setTimeout(updateFloatingControlsState, 10);
      }
    }
    
    // 显示分页搜索结果
    function displayPagedResults(query) {
      displayedResultsCount = Math.min(RESULTS_PER_PAGE, currentSearchResults.length);
      const resultsToShow = currentSearchResults.slice(0, displayedResultsCount);
      
      displayResults(resultsToShow, query);
      updateResultsCounter();
      updateLoadMoreButtons();
    }
    
    // 加载更多结果
    function loadMoreResults() {
      const startIndex = displayedResultsCount;
      const endIndex = Math.min(startIndex + RESULTS_PER_PAGE, currentSearchResults.length);
      const additionalResults = currentSearchResults.slice(startIndex, endIndex);
      
      if (additionalResults.length > 0) {
        displayedResultsCount = endIndex;
        appendResults(additionalResults);
        updateResultsCounter();
        updateLoadMoreButtons();
      }
    }
    
    // 加载所有结果
    function loadAllResults() {
      if (displayedResultsCount < currentSearchResults.length) {
        const remainingResults = currentSearchResults.slice(displayedResultsCount);
        displayedResultsCount = currentSearchResults.length;
        appendResults(remainingResults);
        updateResultsCounter();
        updateLoadMoreButtons();
      }
    }
    
    // 更新结果计数器
    function updateResultsCounter() {
      const totalResults = currentSearchResults.length;
      searchResultsCount.textContent = getText(`显示 ${displayedResultsCount} / ${totalResults} 条结果`, `顯示 ${displayedResultsCount} / ${totalResults} 條結果`);
    }
    
    // 更新加载更多按钮的显示状态
    function updateLoadMoreButtons() {
      const loadMoreBtn = document.getElementById('search-load-more');
      const loadAllBtn = document.getElementById('search-load-all');
      
      if (displayedResultsCount < currentSearchResults.length) {
        loadMoreBtn.style.display = 'inline-block';
        loadAllBtn.style.display = 'inline-block';
      } else {
        loadMoreBtn.style.display = 'none';
        loadAllBtn.style.display = 'none';
      }
    }
    
    // 隐藏加载更多按钮
    function hideLoadMoreButtons() {
      const loadMoreBtn = document.getElementById('search-load-more');
      const loadAllBtn = document.getElementById('search-load-all');
      if (loadMoreBtn) loadMoreBtn.style.display = 'none';
      if (loadAllBtn) loadAllBtn.style.display = 'none';
    }
    
    // 追加搜索结果到列表
    function appendResults(results) {
      const query = document.getElementById('search-input').value.trim();
      const additionalHTML = results.map(result => {
        const typeText = {
          'heading': getText('标题', '標題'),
          'question': getText('问题', '問題'), 
          'answer': getText('回答', '回答'),
          'content': getText('内容', '內容')
        }[result.type] || getText('内容', '內容');
        
        // 智能高亮搜索关键词
        const highlightedContext = query ? highlightSearchTerm(result.context, query) : result.context;
        
        return `
          <li class="search-result-item" data-url="${result.url}">
            <div class="search-result-title">
              <span class="search-result-type">${typeText}</span>
              ${escapeHtml(result.title)}

            </div>
            <div class="search-result-content">${highlightedContext}</div>

          </li>
        `;
      }).join('');
      
      searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);
    }
    
    // 显示搜索结果（原函数，现在用于内部调用）
    function displayResults(results, query) {
      searchResultsList.innerHTML = results.map(result => {
        const typeText = {
          'heading': getText('标题', '標題'),
          'question': getText('问题', '問題'), 
          'answer': getText('回答', '回答'),
          'content': getText('内容', '內容')
        }[result.type] || getText('内容', '內容');
        
        // 智能高亮搜索关键词
        const highlightedContext = query ? highlightSearchTerm(result.context, query) : result.context;
        
        return `
          <li class="search-result-item" data-url="${result.url}">
            <div class="search-result-title">
              <span class="search-result-type">${typeText}</span>
              ${escapeHtml(result.title)}

            </div>
            <div class="search-result-content">${highlightedContext}</div>

          </li>
        `;
      }).join('');
    }
    
    // 显示无结果
    function displayNoResults(query) {
      searchResultsCount.textContent = getText('未找到结果', '未找到結果');
      searchResultsList.innerHTML = `
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
    
    // 智能高亮搜索关键词
    function highlightSearchTerm(text, searchTerm) {
      if (!text || !searchTerm || typeof text !== 'string' || typeof searchTerm !== 'string') {
        return text;
      }
      
      const term = searchTerm.trim();
      if (!term) return text;
      
      try {
        // 策略1: 精确匹配（最常见情况）
        const exactRegex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        let result = text.replace(exactRegex, '<span class="search-result-highlight">$1</span>');
        
        // 检查是否有匹配
        if (result !== text) {
          return result;
        }
        
        // 策略2: 忽略标点符号的模糊匹配
        // 定义中文和英文标点符号（更全面的范围）
        const punctuation = '[\\s\\u3000-\\u303F\\uFF00-\\uFFEF\\u2000-\\u206F\\u0020-\\u002F\\u003A-\\u0040\\u005B-\\u0060\\u007B-\\u007E\\u2010-\\u2027\\u2030-\\u205F\\u3001-\\u3003\\u3008-\\u3011\\u3014-\\u301F\\uFE10-\\uFE19\\uFE30-\\uFE6F]';
        
        // 为搜索词的每个字符之间添加可选的标点符号匹配
        const flexiblePattern = term.split('').map(char => {
          return escapeRegex(char);
        }).join(`${punctuation}*`);
        
        const flexibleRegex = new RegExp(`(${flexiblePattern})`, 'gi');
        result = text.replace(flexibleRegex, '<span class="search-result-highlight">$1</span>');
        
        if (result !== text) {
          return result;
        }
        
        // 策略3: 字符级模糊匹配（最后的保险）
        const chars = term.split('');
        if (chars.length > 1) {
          // 构建一个匹配所有字符但允许标点符号间隔的正则
          const charPattern = chars.map(char => escapeRegex(char)).join(`${punctuation}*`);
          const charRegex = new RegExp(`(${charPattern})`, 'gi');
          
          result = text.replace(charRegex, '<span class="search-result-highlight">$1</span>');
          if (result !== text) {
            return result;
          }
        }
        
        // 策略4: 单字符逐个匹配（中文常见情况）
        chars.forEach(char => {
          if (char.trim()) {
            const singleCharRegex = new RegExp(`(${escapeRegex(char)})`, 'gi');
            result = result.replace(singleCharRegex, '<span class="search-result-highlight">$1</span>');
          }
        });
        
        return result;
        
      } catch (e) {
        console.warn('智能高亮处理失败:', e, '搜索词:', term);
        // 安全降级：尝试最简单的匹配
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
      searchInput.value = '';
      searchResults.style.display = 'none';
      tocHeader.style.display = 'block';
      currentSearchResults = [];
      displayedResultsCount = 0;
      hideLoadMoreButtons();
      searchStatus.innerHTML = `
        ${getText(`搜索准备就绪 (共${searchIndex.length}条记录)`, `搜尋準備就緒 (共${searchIndex.length}條記錄)`)}
      `;
    }
    
    // 事件监听
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();
      
      // 防抖处理
      searchTimeout = setTimeout(() => {
        performSearch(query);
      }, 300);
    });
    
    // 清除搜索按钮
    searchClear.addEventListener('click', clearSearch);
    
    // 收起搜索按钮
    searchCollapse.addEventListener('click', collapseSearch);
    
    // 显示更多按钮
    const loadMoreBtn = document.getElementById('search-load-more');
    const loadAllBtn = document.getElementById('search-load-all');
    
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', loadMoreResults);
    }
    
    if (loadAllBtn) {
      loadAllBtn.addEventListener('click', loadAllResults);
    }
    
    // 搜索结果点击
    searchResultsList.addEventListener('click', (e) => {
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
            // 默认：在新标签页打开，保持搜索状态
            window.open(url, '_blank', 'noopener,noreferrer');
          }
        }
      }
    });
    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
      // Ctrl+F 或 Cmd+F 激活搜索
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        if (searchInitialized) {
          searchInput.focus();
        } else {
          activateSearch();
        }
      }
      
      // ESC 收起搜索
      if (e.key === 'Escape' && document.activeElement === searchInput) {
        collapseSearch();
      }
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
    
    // Ctrl+F 快捷键激活搜索
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && !searchInitialized) {
        e.preventDefault();
        activateSearch();
      }
    });
  }

  // 創建閱讀工具欄
  function createReadingToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'reading-toolbar hidden';
    toolbar.innerHTML = 
      '<div class="toolbar-header">' +
        '<span>⚙️ 閱讀設置</span>' +
        '<button class="ctrl-btn" data-action="close-toolbar">✕</button>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">字體大小</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="font-decrease">A-</button>' +
          '<button class="ctrl-btn active" data-action="font-normal">A</button>' +
          '<button class="ctrl-btn" data-action="font-increase">A+</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">行距</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="line-tight">緊密</button>' +
          '<button class="ctrl-btn active" data-action="line-normal">正常</button>' +
          '<button class="ctrl-btn" data-action="line-loose">寬鬆</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">寬度</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="width-narrow">窄</button>' +
          '<button class="ctrl-btn active" data-action="width-normal">中</button>' +
          '<button class="ctrl-btn" data-action="width-wide">寬</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">主題</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="theme-light">☀️ 日間</button>' +
          '<button class="ctrl-btn" data-action="theme-dark">🌙 夜間</button>' +
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
          '<li class="bookmarks-empty">尚無書籤</li>' +
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
          '<li class="bookmarks-empty">尚無書籤</li>' +
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
    const firstBtnTitle = currentChapter.isHomepage ? '書籤' : '目錄';
    
    buttons.innerHTML = 
      '<div class="action-menu">' +
        '<button class="action-btn menu-btn" data-action="toggle-menu" title="功能菜單">☰</button>' +
        '<div class="action-menu-items">' +
          '<button class="action-btn" data-action="toc" title="' + firstBtnTitle + '">' + firstBtnIcon + '</button>' +
          '<button class="action-btn" data-action="top" title="回到頂部">↑</button>' +
          '<button class="action-btn" data-action="settings" title="設置">⚙️</button>' +
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

  // ============ 功能實現 ============
  
  // 生成內容的簡單hash（與Python端保持一致，使用MD5前12位）
  function simpleHash(str) {
    // 注意：這是一個簡化版本，實際應該使用與Python端相同的MD5算法
    // 為了保持一致性，我們暫時使用相同的邏輯結構
    let hash = 0;
    if (str.length === 0) return '000000000000';
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 轉換為32位整數
    }
    // 將hash轉換為12位16進制字符串，模擬MD5前12位
    const hexHash = Math.abs(hash).toString(16).padStart(12, '0').substring(0, 12);
    return hexHash;
  }
  
  // 標準化文本內容，提高ID生成的穩定性
  function normalizeTextForId(text) {
    if (!text) return '';
    
    return text
      .trim()                                    // 移除首尾空白
      .replace(/[\\r\\n\\t]/g, ' ')              // 替換換行符和制表符為空格
      .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');  // 處理HTML實體，與Python端保持一致
  }
  
  // 生成穩定的內容ID
  function generateStableContentId(questioner, content, time) {
    // 標準化各個組件
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    
    // 標準化時間：只保留數字部分
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    // 組合穩定的標識內容：人名 + 時間 + 前50個字（與Python端保持一致）
    const stableContent = normalizedQuestioner + 
                         normalizedTime +
                         normalizedContent.substring(0, 50); // 改為50字符，與用戶要求一致
    
    return simpleHash(stableContent);
  }
  
  // 生成兼容性的舊版ID（用於遷移）
  function generateLegacyContentId(questioner, content, time) {
    // 使用舊的邏輯生成ID，用於查找現有書籤
    const contentText = questioner + content + time;
    return simpleHash(contentText);
  }
  
  // 生成舊版80字符邏輯的ID（用於向後兼容）
  function generateLegacy80CharId(questioner, content, time) {
    // 舊的邏輯：人名 + 前80字符 + 時間
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    const stableContent = normalizedQuestioner + 
                         normalizedContent.substring(0, 80) + // 舊的80字符
                         normalizedTime;
    
    return simpleHash(stableContent);
  }
  
  // 嘗試查找元素的多種ID策略
  function findElementByMultipleIds(questioner, content, time, prefix = 'qa') {
    // 1. 先嘗試新的穩定ID（人名+時間+前50字）
    const stableId = prefix + '-' + generateStableContentId(questioner, content, time);
    let element = document.getElementById(stableId);
    
    if (!element) {
      // 2. 嘗試舊的80字符邏輯
      const legacy80Id = prefix + '-' + generateLegacy80CharId(questioner, content, time);
      element = document.getElementById(legacy80Id);
    }
    
    if (!element) {
      // 3. 嘗試最原始的舊ID邏輯
      const legacyId = prefix + '-' + generateLegacyContentId(questioner, content, time);
      element = document.getElementById(legacyId);
    }
    
    return element;
  }
  
  // 確保元素有唯一且穩定的ID
  function ensureElementId(element, prefix = 'qa') {
    if (!element.id) {
      let questioner = '', content = '', time = '';
      
      if (element.classList.contains('question')) {
        questioner = element.querySelector('.questioner')?.textContent || '';
        content = element.querySelector('.question-text')?.textContent || '';
        time = element.querySelector('.question-time')?.textContent || '';
      } else if (element.classList.contains('answer')) {
        questioner = element.querySelector('.answerer')?.textContent || '';
        content = element.querySelector('.answer-text')?.textContent || '';
        // 答案通常沒有時間，使用空字符串
        time = '';
      }
      
      // 使用新的穩定ID生成邏輯
      const stableHash = generateStableContentId(questioner, content, time);
      element.id = prefix + '-' + stableHash;
    }
    return element.id;
  }
  
  // 生成分享URL
  function generateShareUrl(targetElement) {
    const prefix = targetElement.classList.contains('question') ? 'question' : 'answer';
    const elementId = ensureElementId(targetElement, prefix);
    const baseUrl = window.location.origin + window.location.pathname;
    return baseUrl + '#' + elementId;
  }
  
  // 找到問答配對
  function findQuestionForAnswer(answerElement) {
    let currentElement = answerElement.previousElementSibling;
    
    // 向上查找最近的問題元素
    while (currentElement) {
      if (currentElement.classList.contains('question')) {
        return currentElement;
      }
      currentElement = currentElement.previousElementSibling;
    }
    
    return null;
  }
  
  function findAnswerForQuestion(questionElement) {
    let currentElement = questionElement.nextElementSibling;
    
    // 向下查找最近的回答元素
    while (currentElement) {
      if (currentElement.classList.contains('answer')) {
        return currentElement;
      }
      currentElement = currentElement.nextElementSibling;
    }
    
    return null;
  }
  
  // 獲取問答的完整文本
  function getQAPairText(element) {
    let questionElement, answerElement;
    let text = '';
    
    // 判断传入的是问题还是答案元素
    if (element.classList.contains('question')) {
      questionElement = element;
      answerElement = findAnswerForQuestion(element);
    } else if (element.classList.contains('answer')) {
      answerElement = element;
      questionElement = findQuestionForAnswer(element);
    }
    
    // 提取問題內容
    if (questionElement) {
      const questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
      const questionTime = questionElement.querySelector('.question-time')?.textContent || '';
      const questionText = questionElement.querySelector('.question-text')?.textContent || '';
      
      text += `問：${questioner}`;
      if (questionTime) text += ` (${questionTime})`;
      text += `\n${questionText}\n\n`;
    }
    
    // 提取回答內容
    if (answerElement) {
      const answerer = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      
      text += `答：${answerer}\n${answerText}`;
    }
    
    return text;
  }
  
  // ============ 書籤功能 ============
  
  // 獲取當前語言版本的書籤存儲鍵
  function getBookmarkStorageKey() {
    return isTraditionalChinesePage() ? 'ebook-bookmarks-traditional' : 'ebook-bookmarks-simplified';
  }

  // 遷移舊書籤數據到新的分離存儲結構
  function migrateOldBookmarks() {
    // 檢查是否已經完成遷移
    if (localStorage.getItem('bookmarks-migrated')) {
      return;
    }
    
    const oldBookmarks = localStorage.getItem('ebook-bookmarks');
    if (!oldBookmarks) {
      // 沒有舊書籤，標記為已遷移
      localStorage.setItem('bookmarks-migrated', 'true');
      return;
    }

    try {
      const bookmarks = JSON.parse(oldBookmarks);
      const simplifiedBookmarks = [];
      const traditionalBookmarks = [];

      // 根據章節文件名分離書籤
      bookmarks.forEach(bookmark => {
        if (bookmark.chapterFilename && bookmark.chapterFilename.includes('_trad.html')) {
          traditionalBookmarks.push(bookmark);
        } else {
          simplifiedBookmarks.push(bookmark);
        }
      });

      // 存儲到新的分離結構
      if (simplifiedBookmarks.length > 0) {
        localStorage.setItem('ebook-bookmarks-simplified', JSON.stringify(simplifiedBookmarks));
      }
      if (traditionalBookmarks.length > 0) {
        localStorage.setItem('ebook-bookmarks-traditional', JSON.stringify(traditionalBookmarks));
      }

      // 刪除舊的統一存儲
      localStorage.removeItem('ebook-bookmarks');
      
      // 標記遷移完成
      localStorage.setItem('bookmarks-migrated', 'true');
      
      console.log(`書籤遷移完成: 簡體 ${simplifiedBookmarks.length} 個, 繁體 ${traditionalBookmarks.length} 個`);
    } catch (error) {
      console.error('書籤遷移失敗:', error);
      // 即使失敗也標記為已嘗試，避免無限重試
      localStorage.setItem('bookmarks-migrated', 'true');
    }
  }

  // 書籤管理
  function getBookmarks(chapterId = null) {
    // 檢查並遷移舊書籤數據
    migrateOldBookmarks();
    
    const storageKey = getBookmarkStorageKey();
    const allBookmarks = localStorage.getItem(storageKey);
    const bookmarks = allBookmarks ? JSON.parse(allBookmarks) : [];
    
    // 如果指定了章節ID，只返回該章節的書籤
    if (chapterId) {
      return bookmarks.filter(bookmark => 
        bookmark.chapter && bookmark.chapter.id === chapterId
      );
    }
    
    return bookmarks;
  }
  
  function getCurrentChapterBookmarks() {
    return getBookmarks(currentChapter.id);
  }
  
  function saveBookmarks(bookmarks) {
    const storageKey = getBookmarkStorageKey();
    localStorage.setItem(storageKey, JSON.stringify(bookmarks));
    updateBookmarkCount();
  }
  
  // 為元素獲取文件級章節信息（文件級書籤）
  function findChapterForElement(element) {
    // 直接返回當前文件的章節信息
    return {
      title: currentChapter.title,
      id: currentChapter.id,
      filename: currentChapter.filename
    };
  }

  // 添加書籤視覺標識
  function addBookmarkVisualIndicator(element) {
    if (!element.classList.contains('bookmarked')) {
      element.classList.add('bookmarked');
      
      // 添加可點擊的書籤標記
      if (!element.querySelector('.bookmark-indicator')) {
        const indicator = document.createElement('span');
        indicator.className = 'bookmark-indicator';
        indicator.textContent = '🔖';
        indicator.title = '點擊移除書籤';
        element.appendChild(indicator);
      }
    }
  }
  
  // 移除書籤視覺標識
  function removeBookmarkVisualIndicator(element) {
    element.classList.remove('bookmarked');
    
    // 移除書籤標記元素
    const indicator = element.querySelector('.bookmark-indicator');
    if (indicator) {
      element.removeChild(indicator);
    }
  }
  
  // 恢復所有書籤的視覺狀態
  function restoreBookmarkVisualStates() {
    const bookmarks = getBookmarks();
    bookmarks.forEach(bookmark => {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        addBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，需要為問題和回答都添加視覺標識
        if (bookmark.type === 'qa-pair') {
          if (element.classList.contains('question')) {
            // 元素是問題，需要找到對應的回答
            const answerElement = findAnswerForQuestion(element);
            if (answerElement) {
              addBookmarkVisualIndicator(answerElement);
            }
          } else if (element.classList.contains('answer')) {
            // 元素是回答，需要找到對應的問題
            const questionElement = findQuestionForAnswer(element);
            if (questionElement) {
              addBookmarkVisualIndicator(questionElement);
            }
          }
        }
      }
    });
  }
  
  // 檢測當前文件信息（文件級書籤）
  function getCurrentChapter() {
    // 獲取當前頁面的文件名
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    
    // 從頁面標題或第一個H1獲取章節名稱
    let chapterTitle = document.title;
    const firstH1 = document.querySelector('h1');
    if (firstH1) {
      chapterTitle = firstH1.textContent.trim();
    }
    
    // 如果是首頁，返回特殊標識
    if (filename === 'index.html' || filename === 'index_trad.html') {
      return {
        title: '首頁',
        id: 'homepage',
        isHomepage: true
      };
    }
    
    // 為其他頁面生成章節信息
    const chapterId = filename.replace('.html', '');
    
    return {
      title: chapterTitle || '未知章節',
      id: chapterId,
      filename: filename,
      isHomepage: false
    };
  }
  
  // 首頁專用：初始化浮動TOC功能
  function initializeHomepageTOC() {
    const tocList = document.getElementById('toc-list');
    const mainTOC = document.querySelector('.toc ul');
    
    if (tocList && mainTOC) {
      // 複製主TOC內容到浮動TOC
      tocList.innerHTML = mainTOC.innerHTML;
      
      // 為TOC項目添加點擊事件（頁面內跳轉）
      tocList.addEventListener('click', (e) => {
        if (e.target.tagName === 'A') {
          e.preventDefault();
          const href = e.target.getAttribute('href');
          if (href && href.startsWith('#')) {
            const targetElement = document.querySelector(href);
            if (targetElement) {
              targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          } else if (href) {
            // 跳轉到其他頁面
            window.location.href = href;
          }
        }
      });
    }
    
    // 初始化書籤顯示
    refreshHomepageBookmarks();
    updateBookmarkCount();
  }
  
  // 首頁專用：刷新所有章節的書籤顯示
  function refreshHomepageBookmarks() {
    if (!currentChapter.isHomepage) return;
    
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 使用異步處理來避免阻塞UI
    setTimeout(() => {
      // 獲取當前語言版本的所有書籤數據
      const allBookmarks = getBookmarks();
      
      if (allBookmarks.length === 0) {
        bookmarksList.innerHTML = '<li class="bookmarks-empty">暫無書籤</li>';
        return;
      }
      
      // 如果書籤數量較多，顯示處理進度
      if (allBookmarks.length > 50) {
        showBookmarkProcessingIndicator(allBookmarks.length);
      }
      
      processHomepageBookmarks(allBookmarks);
    }, 10); // 短暫延遲讓載入動畫顯示
  }
  
  // 顯示書籤處理指示器（針對大量書籤）
  function showBookmarkProcessingIndicator(totalCount) {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    const processingHTML = `
      <div class="bookmark-loading-container">
        <div class="bookmark-loading-spinner">
          <div class="loading-progress-ring">
            <svg width="40" height="40" viewBox="0 0 40 40">
              <circle cx="20" cy="20" r="16" stroke="#f0f0f0" stroke-width="3" fill="none"/>
              <circle cx="20" cy="20" r="16" stroke="#ff69b4" stroke-width="3" fill="none" 
                      stroke-dasharray="100" stroke-dashoffset="100" class="progress-circle"/>
            </svg>
          </div>
          <div class="loading-text">處理 ${totalCount} 個書籤...</div>
        </div>
      </div>
    `;
    
    bookmarksList.innerHTML = processingHTML;
  }
  
  // 處理首頁書籤數據（分批處理）
  function processHomepageBookmarks(allBookmarks) {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 使用requestAnimationFrame分批處理，避免阻塞UI
    requestAnimationFrame(() => {
      // 按章節分組書籤
      const bookmarksByChapter = {};
      allBookmarks.forEach(bookmark => {
        const chapterTitle = bookmark.chapterTitle || '未知章節';
        if (!bookmarksByChapter[chapterTitle]) {
          bookmarksByChapter[chapterTitle] = [];
        }
        bookmarksByChapter[chapterTitle].push(bookmark);
      });
      
      // 對章節標題進行排序（按照章節數字順序）
      const sortedChapterTitles = Object.keys(bookmarksByChapter).sort((a, b) => {
        // 提取章節數字，格式如：01自性与意识、06修福积功德等
        const extractChapterNumber = (title) => {
          // 嘗試匹配開頭的數字（1-2位數字）
          const match = title.match(/^(\d{1,2})/);
          const result = match ? parseInt(match[1], 10) : 999; // 未匹配的放在最後
          // 調試信息（可選）
          // console.log(`Chapter "${title}" -> number: ${result}`);
          return result;
        };
        
        const numA = extractChapterNumber(a);
        const numB = extractChapterNumber(b);
        return numA - numB;
      });
      
      // 分批渲染章節
      renderBookmarkChaptersBatch(sortedChapterTitles, bookmarksByChapter, 0);
    });
  }
  
  // 分批渲染書籤章節，避免大量DOM操作阻塞UI
  function renderBookmarkChaptersBatch(chapterTitles, bookmarksByChapter, startIndex) {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 調試：顯示章節渲染順序
    // if (startIndex === 0) {
    //   console.log('開始渲染書籤，章節順序：', chapterTitles);
    // }
    
    const batchSize = 3; // 每批處理3個章節
    const endIndex = Math.min(startIndex + batchSize, chapterTitles.length);
    
    // 如果是第一批，清空並創建容器
    if (startIndex === 0) {
      bookmarksList.innerHTML = '';
    }
    
    // 處理當前批次的章節
    for (let i = startIndex; i < endIndex; i++) {
      const chapterTitle = chapterTitles[i];
      const chapterBookmarks = bookmarksByChapter[chapterTitle];
      
      // 創建章節組容器
      const chapterGroup = document.createElement('li');
      chapterGroup.className = 'bookmark-chapter-group';
      
      let chapterHTML = `
        <div class="bookmark-chapter-title">${chapterTitle}</div>
        <ul class="bookmark-chapter-list">
      `;
      
      chapterBookmarks.forEach(bookmark => {
        const bookmarkQuestioner = bookmark.questioner || '匿名';
        const bookmarkTime = bookmark.time || '';
        const bookmarkPreview = bookmark.preview || '';
        const chapterFilename = bookmark.chapterFilename || '';
        const elementId = bookmark.elementId || '';
        const isQAPair = bookmark.type === 'qa-pair';
        const typeIcon = isQAPair ? '💬' : '📝';
        const typeClass = isQAPair ? ' qa-pair-bookmark' : '';
        
        const linkUrl = chapterFilename && elementId ? `${chapterFilename}#${elementId}` : '#';
        
        chapterHTML += `
          <li class="bookmark-item${typeClass}" data-bookmark-id="${bookmark.id}">
            <div class="bookmark-meta">
              <span class="bookmark-type">${typeIcon}</span>
              <span class="bookmark-questioner">${bookmarkQuestioner}</span>
              <span class="bookmark-time">${bookmarkTime}</span>
            </div>
            <div class="bookmark-preview">
              <a href="${linkUrl}" target="_blank" title="點擊跳轉到原問答">${bookmarkPreview}</a>
            </div>
            <button class="bookmark-delete" data-bookmark-id="${bookmark.id}" title="刪除書籤">✕</button>
          </li>
        `;
      });
      
      chapterHTML += '</ul>';
      chapterGroup.innerHTML = chapterHTML;
      bookmarksList.appendChild(chapterGroup);
    }
    
    // 如果還有更多章節需要處理，繼續下一批
    if (endIndex < chapterTitles.length) {
      requestAnimationFrame(() => {
        renderBookmarkChaptersBatch(chapterTitles, bookmarksByChapter, endIndex);
      });
    } else {
      // 所有章節渲染完成，添加事件監聽器
      addHomepageBookmarkEventListeners();
    }
  }
  
  // 添加首頁書籤事件監聽器
  function addHomepageBookmarkEventListeners() {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 移除舊的事件監聽器，避免重複綁定
    const existingHandler = bookmarksList.bookmarkClickHandler;
    if (existingHandler) {
      bookmarksList.removeEventListener('click', existingHandler);
    }
    
    // 創建新的事件處理器
    const newHandler = (e) => {
      if (e.target.classList.contains('bookmark-delete')) {
        e.stopPropagation();
        const bookmarkId = e.target.getAttribute('data-bookmark-id');
        removeBookmarkById(bookmarkId);
        refreshHomepageBookmarks(); // 刷新顯示
        updateBookmarkCount(); // 更新書籤計數
      } else {
        const clickedLink = e.target.closest('a');
        if (clickedLink) {
          return;
        }
        
        const bookmarkItem = e.target.closest('.bookmark-item');
        if (bookmarkItem) {
          const bookmarkId = bookmarkItem.getAttribute('data-bookmark-id');
          jumpToBookmark(bookmarkId);
        }
      }
    };
    
    // 綁定新的事件監聽器
    bookmarksList.addEventListener('click', newHandler);
    bookmarksList.bookmarkClickHandler = newHandler; // 保存引用以便移除
  }
  
  // 跳轉到指定書籤
  function jumpToBookmark(bookmarkId) {
    const allBookmarks = getBookmarks();
    const bookmark = allBookmarks.find(b => b.id === bookmarkId);
    
    if (bookmark && bookmark.chapterFilename) {
      // 跳轉到對應章節頁面，並定位到書籤位置
      const targetUrl = `${bookmark.chapterFilename}#${bookmark.elementId}`;
      // 在新視窗打開，保持與文字鏈接一致的行為
      window.open(targetUrl, '_blank');
    }
  }
  
  // 根據ID刪除書籤
  function removeBookmarkById(bookmarkId) {
    const allBookmarks = getBookmarks();
    const updatedBookmarks = allBookmarks.filter(bookmark => bookmark.id !== bookmarkId);
    saveBookmarks(updatedBookmarks);
    showToast('書籤已刪除');
  }
  
  // 書籤添加成功的視覺反饋
  function showBookmarkAddedFeedback() {
    // 首頁有floating-toc，章節頁面沒有，需要分別處理
    if (currentChapter.isHomepage) {
      // 首頁：顯示提示並引導到側邊欄
      showToast('已添加到書籤，可在側邊欄查看');
      
      const floatingTOC = document.getElementById('floating-toc');
      const bookmarkTab = document.querySelector('.floating-toc-tab[data-tab="bookmarks"]');
      
      if (floatingTOC && bookmarkTab) {
        // 如果TOC未顯示，短暫顯示並高亮書籤tab
        if (!floatingTOC.classList.contains('visible')) {
          floatingTOC.classList.add('visible');
          
          // 高亮書籤tab
          bookmarkTab.style.background = '#ff69b4';
          bookmarkTab.style.color = 'white';
          bookmarkTab.style.transform = 'scale(1.1)';
          bookmarkTab.style.transition = 'all 0.3s ease';
          bookmarkTab.style.boxShadow = '0 2px 8px rgba(255, 105, 180, 0.5)';
          
          setTimeout(() => {
            bookmarkTab.style.background = '';
            bookmarkTab.style.color = '';
            bookmarkTab.style.transform = '';
            bookmarkTab.style.boxShadow = '';
            
            setTimeout(() => {
              floatingTOC.classList.remove('visible');
            }, 1500);
          }, 1200);
        } else {
          // TOC已顯示，只高亮書籤tab
          bookmarkTab.style.background = '#ff69b4';
          bookmarkTab.style.color = 'white';
          bookmarkTab.style.transform = 'scale(1.1)';
          bookmarkTab.style.transition = 'all 0.3s ease';
          bookmarkTab.style.boxShadow = '0 2px 8px rgba(255, 105, 180, 0.5)';
          
          setTimeout(() => {
            bookmarkTab.style.background = '';
            bookmarkTab.style.color = '';
            bookmarkTab.style.transform = '';
            bookmarkTab.style.boxShadow = '';
          }, 1500);
        }
      }
    } else {
      // 章節頁面：增強型Toast提示 + 特殊動畫效果
      showEnhancedBookmarkToast();
    }
  }
  
  // 章節頁面專用的增強書籤提示
  function showEnhancedBookmarkToast() {
    // 創建特殊的toast元素
    const toast = document.createElement('div');
    toast.className = 'bookmark-success-toast';
    toast.innerHTML = `
      <div class="toast-icon">🔖</div>
      <div class="toast-content">
        <div class="toast-title">書籤已添加！</div>
        <div class="toast-subtitle">點擊右下角 📖 查看所有書籤</div>
      </div>
    `;
    
    // 添加樣式
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: linear-gradient(135deg, #ff69b4, #e75480);
      color: white;
      padding: 16px 20px;
      border-radius: 12px;
      box-shadow: 0 8px 25px rgba(231, 84, 128, 0.3);
      z-index: 10000;
      transform: translateX(400px);
      transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
      display: flex;
      align-items: center;
      gap: 12px;
      max-width: 300px;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    `;
    
    toast.querySelector('.toast-icon').style.cssText = `
      font-size: 24px;
      animation: bounce 0.6s ease infinite alternate;
    `;
    
    toast.querySelector('.toast-title').style.cssText = `
      font-weight: 600;
      font-size: 14px;
      margin-bottom: 2px;
    `;
    
    toast.querySelector('.toast-subtitle').style.cssText = `
      font-size: 12px;
      opacity: 0.9;
    `;
    
    // 添加彈跳動畫CSS
    const style = document.createElement('style');
    style.textContent = `
      @keyframes bounce {
        0% { transform: translateY(0); }
        100% { transform: translateY(-6px); }
      }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(toast);
    
    // 動畫顯示
    setTimeout(() => {
      toast.style.transform = 'translateX(0)';
    }, 100);
    
    // 3.5秒後淡出並移除
    setTimeout(() => {
      toast.style.transform = 'translateX(400px)';
      toast.style.opacity = '0';
      setTimeout(() => {
        if (toast.parentNode) {
          document.body.removeChild(toast);
        }
        if (style.parentNode) {
          document.head.removeChild(style);
        }
      }, 400);
    }, 3500);
  }
  
  // 初始化當前文件信息（文件級書籤，無需監聽滾動）
  let currentChapter;

  function toggleBookmark(element) {
    // 首頁不允許操作書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const bookmarks = getBookmarks();
    const isQuestion = element.classList.contains('question');
    const isAnswer = element.classList.contains('answer');
    
    if (!isQuestion && !isAnswer) return;
    
    // 生成唯一ID
    const id = element.id || ('bookmark-' + Date.now());
    element.id = id;
    
    // 檢查是否已存在書籤
    const existingBookmark = bookmarks.find(bookmark => bookmark.elementId === id);
    
    if (existingBookmark) {
      // 已存在，移除書籤
      removeBookmarkVisualIndicator(element);
      const updatedBookmarks = bookmarks.filter(bookmark => bookmark.elementId !== id);
      saveBookmarks(updatedBookmarks);
      renderBookmarks();
      showToast('已從書籤移除');
      return;
    }
    
    // 不存在，添加書籤
    const chapter = findChapterForElement(element);
    
    // 提取內容
    let questioner = '', time = '', preview = '';
    
    if (isQuestion) {
      const questionerEl = element.querySelector('.questioner');
      const timeEl = element.querySelector('.question-time');
      const textEl = element.querySelector('.question-text');
      
      questioner = questionerEl ? questionerEl.textContent : '匿名';
      time = timeEl ? timeEl.textContent : '';
      preview = textEl ? textEl.textContent.substring(0, 100) + '...' : '';
    } else if (isAnswer) {
      const answererEl = element.querySelector('.answerer');
      const textEl = element.querySelector('.answer-text');
      
      questioner = answererEl ? answererEl.textContent : 'Taiguanglin';
      preview = textEl ? textEl.textContent.substring(0, 100) + '...' : '';
    }
    
    const bookmark = {
      id: 'bookmark-' + Date.now(),
      elementId: id,
      type: isQuestion ? 'question' : 'answer',
      questioner: questioner,
      time: time,
      preview: preview,
      chapter: chapter,
      chapterTitle: currentChapter.title,
      chapterFilename: currentChapter.filename,
      timestamp: new Date().toLocaleString()
    };
    
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    addBookmarkVisualIndicator(element);
    renderBookmarks();
    showBookmarkAddedFeedback();
  }
  
  function toggleQAPairBookmark(answerElement) {
    // 首頁不允許操作書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const bookmarks = getBookmarks();
    const questionElement = findQuestionForAnswer(answerElement);
    
    // 決定要用作書籤定位的元素ID
    let targetElement, targetId;
    if (questionElement) {
      // 如果有對應問題，使用問題元素作為書籤定位目標
      targetElement = questionElement;
      targetId = questionElement.id || ('qa-question-' + Date.now());
      questionElement.id = targetId;
    } else {
      // 如果沒有對應問題，使用回答元素
      targetElement = answerElement;
      targetId = answerElement.id || ('qa-answer-' + Date.now());
      answerElement.id = targetId;
    }
    
    // 確保回答元素也有ID（用於視覺標識管理）
    if (!answerElement.id) {
      answerElement.id = 'qa-answer-' + Date.now();
    }
    
    // 檢查是否已存在書籤（使用目標元素ID）
    const existingBookmark = bookmarks.find(bookmark => bookmark.elementId === targetId);
    
    if (existingBookmark) {
      // 已存在，移除書籤
      removeBookmarkVisualIndicator(answerElement);
      if (questionElement) {
        removeBookmarkVisualIndicator(questionElement);
      }
      const updatedBookmarks = bookmarks.filter(bookmark => bookmark.elementId !== targetId);
      saveBookmarks(updatedBookmarks);
      renderBookmarks();
      showToast('已從書籤移除問答');
      return;
    }
    
    // 不存在，添加問答書籤
    const chapter = findChapterForElement(answerElement);
    
    // 提取問答信息
    let questioner = '匿名', time = '', preview = '';
    
    if (questionElement) {
      const questionerEl = questionElement.querySelector('.questioner');
      const timeEl = questionElement.querySelector('.question-time');
      const questionTextEl = questionElement.querySelector('.question-text');
      
      questioner = questionerEl ? questionerEl.textContent : '匿名';
      time = timeEl ? timeEl.textContent : '';
      
      // 構建預覽：問題開頭 + 回答開頭
      const questionText = questionTextEl ? questionTextEl.textContent : '';
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      preview = `問：${questionText.substring(0, 50)}... 答：${answerText.substring(0, 50)}...`;
    } else {
      // 只有回答的情況
      const answererEl = answerElement.querySelector('.answerer');
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      
      questioner = answererEl ? answererEl.textContent : 'Taiguanglin';
      preview = `答：${answerText.substring(0, 100)}...`;
    }
    
    const bookmark = {
      id: 'qa-bookmark-' + Date.now(),
      elementId: targetId,
      type: 'qa-pair',
      questioner: questioner,
      time: time,
      preview: preview,
      chapter: chapter,
      chapterTitle: currentChapter.title,
      chapterFilename: currentChapter.filename,
      timestamp: new Date().toLocaleString()
    };
    
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    
    // 為問答添加視覺標識
    addBookmarkVisualIndicator(answerElement);
    if (questionElement) {
      addBookmarkVisualIndicator(questionElement);
    }
    
    renderBookmarks();
    showBookmarkAddedFeedback();
  }
  
  function removeBookmark(bookmarkId) {
    const bookmarks = getBookmarks();
    const bookmark = bookmarks.find(b => b.id === bookmarkId);
    
    // 移除視覺標識
    if (bookmark) {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        removeBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，需要移除問題和回答的視覺標識
        if (bookmark.type === 'qa-pair') {
          if (element.classList.contains('question')) {
            // 元素是問題，需要找到對應的回答
            const answerElement = findAnswerForQuestion(element);
            if (answerElement) {
              removeBookmarkVisualIndicator(answerElement);
            }
          } else if (element.classList.contains('answer')) {
            // 元素是回答，需要找到對應的問題
            const questionElement = findQuestionForAnswer(element);
            if (questionElement) {
              removeBookmarkVisualIndicator(questionElement);
            }
          }
        }
      }
    }
    
    const updatedBookmarks = bookmarks.filter(bookmark => bookmark.id !== bookmarkId);
    saveBookmarks(updatedBookmarks);
    renderBookmarks();
    showToast('已從書籤移除');
  }
  
  function clearCurrentChapterBookmarks() {
    // 首頁不允許清空書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const currentBookmarks = getCurrentChapterBookmarks();
    if (currentBookmarks.length === 0) {
      showToast('本文件暫無書籤');
      return;
    }
    
    // 確認對話框
    if (!confirm(`確定要清空本文件的所有 ${currentBookmarks.length} 個書籤嗎？此操作無法撤銷。`)) {
      return;
    }
    
    // 移除當前文件所有書籤的視覺標識
    currentBookmarks.forEach(bookmark => {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        removeBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，還需要移除問題的視覺標識
        if (bookmark.type === 'qa-pair' && element.classList.contains('answer')) {
          const questionElement = findQuestionForAnswer(element);
          if (questionElement) {
            removeBookmarkVisualIndicator(questionElement);
          }
        }
      }
    });
    
    // 從總書籤列表中移除當前文件的書籤
    const allBookmarks = getBookmarks();
    const updatedBookmarks = allBookmarks.filter(bookmark => 
      !bookmark.chapter || bookmark.chapter.id !== currentChapter.id
    );
    
    saveBookmarks(updatedBookmarks);
    renderBookmarks();
    showToast(`已清空本文件的 ${currentBookmarks.length} 個書籤`);
  }
  
  // 渲染首頁動態TOC內容
  function renderIndexTOC() {
    const tocList = document.getElementById('toc-list');
    const bookmarksList = document.getElementById('bookmarks-list');
    
    if (!tocList) return;
    
    // 獲取首頁的TOC鏈接
    const mainTOC = document.querySelector('.toc');
    if (!mainTOC) return;
    
    const tocLinks = mainTOC.querySelectorAll('a[href]');
    let tocHTML = '';
    
    tocLinks.forEach(link => {
      const href = link.getAttribute('href');
      const text = link.textContent.trim();
      
      // 只顯示主章節（不包含錨點的鏈接）
      if (href && !href.includes('#') && text) {
        tocHTML += `<div class="floating-toc-item" data-href="${href}">${text}</div>`;
      }
    });
    
    tocList.innerHTML = tocHTML;
    
    // 同時更新書籤列表為章節書籤功能說明
    if (bookmarksList) {
      bookmarksList.innerHTML = `
        <div class="bookmarks-empty">
          <p>📖 書籤功能說明</p>
          <p>• 進入任意章節</p>
          <p>• 找到感興趣的問答</p>
          <p>• 點擊右上角書籤圖標</p>
          <p>• 返回此處查看收藏</p>
        </div>
      `;
    }
  }
  
  // 顯示書籤載入指示器
  function showBookmarkLoadingIndicator() {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 創建載入動畫HTML
    const loadingHTML = `
      <div class="bookmark-loading-container">
        <div class="bookmark-loading-spinner">
          <div class="loading-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <div class="loading-text">載入書籤中...</div>
        </div>
      </div>
    `;
    
    bookmarksList.innerHTML = loadingHTML;
    
    // 動態添加載入動畫CSS（如果尚未添加）
    if (!document.querySelector('#bookmark-loading-styles')) {
      const style = document.createElement('style');
      style.id = 'bookmark-loading-styles';
      style.textContent = `
        .bookmark-loading-container {
          display: flex;
          justify-content: center;
          align-items: center;
          padding: 40px 20px;
          min-height: 120px;
        }
        
        .bookmark-loading-spinner {
          text-align: center;
          color: #666;
        }
        
        .loading-dots {
          display: flex;
          gap: 4px;
          justify-content: center;
          margin-bottom: 12px;
        }
        
        .loading-dots .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: #ff69b4;
          animation: bookmarkDotPulse 1.4s infinite ease-in-out both;
        }
        
        .loading-dots .dot:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots .dot:nth-child(2) { animation-delay: -0.16s; }
        .loading-dots .dot:nth-child(3) { animation-delay: 0s; }
        
        .loading-text {
          font-size: 14px;
          color: #999;
          font-weight: 500;
        }
        
        @keyframes bookmarkDotPulse {
          0%, 80%, 100% {
            transform: scale(0.6);
            opacity: 0.5;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
        
        /* 暗色模式支持 */
        .dark-mode .bookmark-loading-spinner {
          color: #ccc;
        }
        
        .dark-mode .loading-text {
          color: #aaa;
        }
      `;
      document.head.appendChild(style);
    }
  }

  function renderBookmarks() {
    const bookmarksList = document.getElementById('bookmarks-list');
    
    if (!bookmarksList) {
      return;
    }
    
    // 首頁使用專門的書籤顯示函數
    if (currentChapter.isHomepage) {
      refreshHomepageBookmarks();
      return;
    }
    
    // 對於章節頁面，也使用異步處理來改善UX
    setTimeout(() => {
      const chapterBookmarks = getCurrentChapterBookmarks();
      
      if (chapterBookmarks.length === 0) {
        bookmarksList.innerHTML = 
          '<div class="bookmarks-empty">' +
            '<div>本文件暫無書籤</div>' +
            '<div style="font-size: 12px; color: #999; margin-top: 8px;">當前文件：' + currentChapter.title + '</div>' +
          '</div>';
        return;
      }
      
      let bookmarksHTML = '';
      
      // 添加當前文件標題和清空按鈕
      bookmarksHTML += 
        '<div class="current-chapter-info">' +
          '<div class="chapter-header">' +
            '<div class="current-chapter-title">📄 ' + currentChapter.title + '</div>' +
            '<button class="bookmark-clear-icon" data-action="clear-bookmarks" title="清空本文件所有書籤">🗑️</button>' +
          '</div>' +
        '</div>';
      
      // 直接顯示當前文件的書籤，不需要分組
      chapterBookmarks.forEach(bookmark => {
        const isQAPair = bookmark.type === 'qa-pair';
        const typeIcon = isQAPair ? '💬' : '📝';
        const typeClass = isQAPair ? ' qa-pair-bookmark' : '';
        
        bookmarksHTML += 
          '<div class="bookmark-item' + typeClass + '" data-target="#' + bookmark.elementId + '">' +
            '<div class="bookmark-meta">' +
              '<span class="bookmark-type">' + typeIcon + '</span>' +
              '<span class="bookmark-questioner">' + bookmark.questioner + '</span>' +
              '<span class="bookmark-time">' + bookmark.time + '</span>' +
            '</div>' +
            '<div class="bookmark-preview">' + bookmark.preview + '</div>' +
            '<button class="bookmark-delete" data-bookmark-id="' + bookmark.id + '" title="刪除書籤">✕</button>' +
          '</div>';
      });
      
      bookmarksList.innerHTML = bookmarksHTML;
    }, 10); // 短暫延遲讓載入動畫顯示
  }
  
  function updateBookmarkCount() {
    const countEl = document.getElementById('bookmark-count');
    if (!countEl) {
      return;
    }
    
    let count;
    if (currentChapter.isHomepage) {
      // 首頁顯示所有書籤的總數
      const allBookmarks = getBookmarks();
      count = allBookmarks.length;
    } else {
      // 章節頁面顯示當前章節的書籤數
      count = getCurrentChapterBookmarks().length;
    }
    if (countEl) {
      countEl.textContent = '(' + count + ')';
    }
  }

  // 閱讀設置功能
  let fontSize = parseInt(localStorage.getItem('fontSize')) || 16;
  let lineHeight = parseFloat(localStorage.getItem('lineHeight')) || 1.6;
  let contentWidth = parseInt(localStorage.getItem('contentWidth')) || 800;
  
  function applyReadingSettings() {
    document.body.style.fontSize = fontSize + 'px';
    document.documentElement.style.setProperty('--line-height', lineHeight);
    document.body.style.maxWidth = contentWidth + 'px';
  }
  
  function updateFontSize(change) {
    fontSize = Math.max(12, Math.min(24, fontSize + change));
    localStorage.setItem('fontSize', fontSize);
    applyReadingSettings();
  }
  
  function updateLineHeight(value) {
    lineHeight = value;
    localStorage.setItem('lineHeight', lineHeight);
    applyReadingSettings();
  }
  
  function updateContentWidth(value) {
    contentWidth = value;
    localStorage.setItem('contentWidth', contentWidth);
    applyReadingSettings();
  }

  // 閱讀進度功能
  function updateReadingProgress() {
    const scrollTop = window.pageYOffset;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    
    const progressBar = document.querySelector('.reading-progress-bar');
    if (progressBar) {
      progressBar.style.width = Math.max(0, Math.min(100, progress)) + '%';
    }
  }

  // 章節跟踪功能
  function updateCurrentSection() {
    // 首頁跳過章節跟踪
    if (currentChapter.isHomepage) {
      return;
    }
    
    const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
    const scrollTop = window.pageYOffset;
    const offset = 100; // 偏移量，調整觸發點
    
    let currentSection = null;
    
    // 找到最接近當前位置的章節
    headings.forEach((heading) => {
      const rect = heading.getBoundingClientRect();
      const elementTop = scrollTop + rect.top;
      
      if (elementTop <= scrollTop + offset) {
        currentSection = heading;
      }
    });
    
    // 更新TOC高亮狀態
    const tocItems = document.querySelectorAll('.floating-toc-item[data-target]');
    let activeItem = null;
    
    tocItems.forEach(item => {
      item.classList.remove('active');
      
      if (currentSection) {
        const targetId = '#' + currentSection.id;
        if (item.dataset.target === targetId) {
          item.classList.add('active');
          activeItem = item;
        }
      }
    });
    
    // 自動滾動sidebar到當前章節
    if (activeItem) {
      const tocContainer = activeItem.closest('.floating-toc');
      if (tocContainer && tocContainer.classList.contains('visible')) {
        // 檢查activeItem是否在可視區域內
        const containerRect = tocContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        
        // 如果item不在容器的可視區域內，則滾動到該位置
        if (itemRect.top < containerRect.top + 60 || itemRect.bottom > containerRect.bottom - 20) {
          activeItem.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
        }
      }
    }
  }

  // 顯示通知
  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
  }

  // 複製功能
  function copyText(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('已複製到剪貼板');
      });
    } else {
      // 降級處理
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('已複製到剪貼板');
    }
  }
  
  // 處理頁面加載時的錨點跳轉
  function handleInitialAnchor() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      const targetId = hash.substring(1); // 移除#號
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        // 延遲滾動，確保頁面布局完成
        setTimeout(() => {
          targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
          
          // 添加臨時高亮效果
          targetElement.style.transition = 'background-color 0.3s ease';
          targetElement.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
          setTimeout(() => {
            targetElement.style.backgroundColor = '';
          }, 3000);
        }, 300);
      }
    }
  }

  // ============ 事件監聽 ============
  
  // 首先初始化當前章節信息
  currentChapter = getCurrentChapter();
  
  // 初始化所有組件
  const toolbar = createReadingToolbar();
  const progressBar = createReadingProgress();
  const floatingTOC = createFloatingTOC();
  
  // 只在章節頁面創建action-buttons，首頁已有靜態HTML
  if (!currentChapter.isHomepage) {
    const actionButtons = createActionButtons();
  }
  
  addQAActions();
  applyReadingSettings();
  
  // 首頁專用：初始化浮動TOC
  if (currentChapter.isHomepage) {
    initializeHomepageTOC();
  }
  
  updateBookmarkCount();
  updateThemeButtons();
  restoreBookmarkVisualStates();
  
  // 延遲執行章節跟踪，確保頁面完全渲染
  setTimeout(updateCurrentSection, 100);
  
  // 處理頁面加載時的錨點跳轉
  setTimeout(handleInitialAnchor, 200);
  
  // 如果是首頁，渲染動態TOC內容
  if (isIndexPage()) {
    renderIndexTOC();
  }

  document.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    
    // 點擊外部區域關閉所有打開的sidebars
    if (!action && !isClickInsideSidebar(e.target)) {
      closeSidebars();
    }
    
    if (!action) return;

    switch (action) {
      // 字體設置
      case 'font-decrease':
        updateFontSize(-2);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'font-normal':
        fontSize = 16;
        localStorage.setItem('fontSize', fontSize);
        applyReadingSettings();
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'font-increase':
        updateFontSize(2);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 行距設置
      case 'line-tight':
        updateLineHeight(1.2);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'line-normal':
        updateLineHeight(1.6);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'line-loose':
        updateLineHeight(2.0);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 寬度設置
      case 'width-narrow':
        updateContentWidth(600);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'width-normal':
        updateContentWidth(800);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'width-wide':
        updateContentWidth(1000);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 主題切換
      case 'theme-light':
        document.body.classList.remove('dark-mode');
        localStorage.setItem('darkMode', false);
        updateThemeButtons();
        break;
      case 'theme-dark':
        document.body.classList.add('dark-mode');
        localStorage.setItem('darkMode', true);
        updateThemeButtons();
        break;

      // 操作按鈕
      case 'toggle-menu':
        // 兼容首頁和章節頁面的不同結構
        const actionButtons = e.target.closest('.action-buttons');
        let actionMenu = actionButtons.querySelector('.action-menu');
        
        // 如果沒找到.action-menu，可能是首頁結構，直接查找同級的.action-menu
        if (!actionMenu) {
          actionMenu = e.target.nextElementSibling;
          if (actionMenu && !actionMenu.classList.contains('action-menu')) {
            actionMenu = null;
          }
        }
        
        if (actionMenu) {
          actionMenu.classList.toggle('expanded');
        }
        e.target.classList.toggle('expanded');
        break;
      case 'toc':
        floatingTOC.classList.toggle('visible');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        // 如果TOC剛打開，立即定位當前章節
        if (floatingTOC.classList.contains('visible')) {
          setTimeout(updateCurrentSection, 100); // 等待CSS transition完成
        }
        break;
      case 'close-toc':
        floatingTOC.classList.remove('visible');
        break;
      case 'top':
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;

      case 'settings':
        toolbar.classList.toggle('hidden');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'close-toolbar':
        toolbar.classList.add('hidden');
        break;

      // 問答操作
      case 'bookmark':
        const bookmarkElement = e.target.closest('.question, .answer');
        if (bookmarkElement) {
          toggleBookmark(bookmarkElement);
        }
        break;
      case 'copy-qa':
        const copyQAElement = e.target.closest('.question, .answer');
        if (copyQAElement) {
          const qaPairText = getQAPairText(copyQAElement);
          copyText(qaPairText);
        }
        break;
      case 'bookmark-qa':
        const qaBookmarkElement = e.target.closest('.question, .answer');
        if (qaBookmarkElement) {
          if (qaBookmarkElement.classList.contains('answer')) {
            toggleQAPairBookmark(qaBookmarkElement);
          } else if (qaBookmarkElement.classList.contains('question')) {
            // 如果是問題，找到對應的回答
            const answerElement = findAnswerForQuestion(qaBookmarkElement);
            if (answerElement) {
              toggleQAPairBookmark(answerElement);
            } else {
              // 如果沒有對應回答，提示用戶
              showToast('找不到對應的回答');
            }
          }
        }
        break;
      case 'share':
        const shareElement = e.target.closest('.question, .answer');
        if (shareElement) {
          // 直接分享點擊的區塊（問題或回答）
          const shareUrl = generateShareUrl(shareElement);
          const isQuestion = shareElement.classList.contains('question');
          const toastMessage = isQuestion ? '問題鏈接已複製' : '回答鏈接已複製';
          
          if (navigator.share) {
            navigator.share({
              url: shareUrl
            });
          } else {
            copyText(shareUrl);
            showToast(toastMessage);
          }
        } else {
          // 降級處理：分享頁面鏈接
          if (navigator.share) {
            navigator.share({
              url: window.location.href
            });
          } else {
            copyText(window.location.href);
            showToast('頁面鏈接已複製');
          }
        }
        break;
      case 'clear-bookmarks':
        clearCurrentChapterBookmarks();
        break;
    }
  });

  // 浮動目錄點擊
  document.addEventListener('click', (e) => {
    // 目錄項點擊
    if (e.target.classList.contains('floating-toc-item')) {
      // 首頁的TOC項目：跳轉到其他頁面
      if (e.target.dataset.href) {
        const href = e.target.dataset.href;
        window.location.href = href;
        return;
      }
      
      // 其他頁面：頁面內跳轉
      const target = e.target.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // 移除自動關閉sidebar，讓用戶可以連續導航
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 標籤頁切換
    if (e.target.classList.contains('floating-toc-tab')) {
      const tab = e.target.dataset.tab;
      
      // 更新標籤頁狀態
      document.querySelectorAll('.floating-toc-tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      
      // 切換內容
      const tocList = document.getElementById('toc-list');
      const bookmarksList = document.getElementById('bookmarks-list');
      const tocTitle = document.getElementById('toc-title');
      
      if (tab === 'toc') {
        // 目录模式：显示目录，隐藏书签
        if (tocList) tocList.style.display = 'block';
        if (bookmarksList) bookmarksList.style.display = 'none';
        if (tocTitle) {
          tocTitle.textContent = '📖 章節目錄';
          tocTitle.style.display = 'block';
        }
      } else if (tab === 'bookmarks') {
        // 书签模式：隐藏目录，只显示书签内容
        if (tocList) tocList.style.display = 'none';
        if (bookmarksList) bookmarksList.style.display = 'block';
        if (tocTitle) {
          tocTitle.textContent = '🔖 我的書籤';
          tocTitle.style.display = 'block';
        }
        
        // 立即顯示載入指示器，改善UX
        showBookmarkLoadingIndicator();
        
        // 使用requestAnimationFrame延遲渲染，讓載入動畫先顯示
        requestAnimationFrame(() => {
          renderBookmarks();
        });
      }
    }
    
    // 書籤項點擊
    const bookmarkItem = e.target.closest('.bookmark-item');
    if (bookmarkItem && !e.target.classList.contains('bookmark-delete')) {
      const target = bookmarkItem.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        // 添加臨時高亮效果
        element.style.transition = 'background-color 0.3s ease';
        element.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
        setTimeout(() => {
          element.style.backgroundColor = '';
        }, 2000);
        
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // 移除自動關閉側邊欄，讓用戶可以連續瀏覽書籤
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 書籤刪除按鈕
    if (e.target.classList.contains('bookmark-delete')) {
      e.stopPropagation();
      const bookmarkId = e.target.dataset.bookmarkId;
      if (bookmarkId) {
        removeBookmark(bookmarkId);
      }
    }
    
    // 書籤標記點擊 - 移除書籤
    if (e.target.classList.contains('bookmark-indicator')) {
      e.stopPropagation();
      const bookmarkedElement = e.target.closest('.question, .answer');
      if (bookmarkedElement) {
        // 首先檢查是否為問答書籤（通過檢查配對元素）
        let isQAPairBookmark = false;
        let answerElement = null;
        let questionElement = null;
        
        if (bookmarkedElement.classList.contains('answer')) {
          answerElement = bookmarkedElement;
          questionElement = findQuestionForAnswer(answerElement);
        } else {
          questionElement = bookmarkedElement;
          answerElement = findAnswerForQuestion(questionElement);
        }
        
        // 如果問題和回答都有書籤標記，說明是問答書籤
        if (questionElement && answerElement && 
            questionElement.classList.contains('bookmarked') && 
            answerElement.classList.contains('bookmarked')) {
          isQAPairBookmark = true;
        }
        
        if (isQAPairBookmark && answerElement) {
          // 問答書籤：使用問答切換功能移除
          toggleQAPairBookmark(answerElement);
        } else {
          // 單個元素書籤：使用原來的切換功能
          toggleBookmark(bookmarkedElement);
        }
      }
    }
  });

  function updateActiveButton(container, activeBtn) {
    container.querySelectorAll('.ctrl-btn').forEach(btn => btn.classList.remove('active'));
    activeBtn.classList.add('active');
  }

  // 檢查點擊是否在sidebar內部
  function isClickInsideSidebar(target) {
    return target.closest('.action-menu') || 
           target.closest('.floating-toc') || 
           target.closest('.reading-toolbar');
  }

  // 關閉所有打開的sidebars
  function closeSidebars() {
    // 關閉操作菜單
    const openMenu = document.querySelector('.action-menu.expanded');
    if (openMenu) {
      openMenu.classList.remove('expanded');
      document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
    }
    
    // 關閉浮動目錄
    const visibleTOC = document.querySelector('.floating-toc.visible');
    if (visibleTOC) {
      visibleTOC.classList.remove('visible');
    }
    
    // 關閉閱讀工具栏
    const visibleToolbar = document.querySelector('.reading-toolbar:not(.hidden)');
    if (visibleToolbar) {
      visibleToolbar.classList.add('hidden');
    }
  }

  // 滾動事件（帶節流優化）
  let scrollTimeout;
  function handleScroll() {
    updateReadingProgress();
    
    // 節流處理章節跟踪，避免過度頻繁更新
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateCurrentSection, 50);
  }
  
  window.addEventListener('scroll', handleScroll);
  updateReadingProgress();
  updateCurrentSection(); // 初始化當前章節


  // 平滑滾動章節內 TOC 與回到頂部
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, null, href);
      }
    });
  });

  // ========== 目录折叠控制功能 ==========
  
  // 初始化目录折叠控制（首页和章节页面都需要）
  initTocCollapseControl();
  initFloatingLevelControls();
  
  function initTocCollapseControl() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 根據頁面類型設定不同的默認值
    const isChapterPage = document.getElementById('chapter-toc') !== null;
    const defaultLevel = isChapterPage ? '3' : '2'; // 章節頁面默認第3層，首頁默認第2層
    
    // 获取用户保存的偏好，使用對應的默認值
    const savedLevel = localStorage.getItem('toc-display-level') || defaultLevel;
    
    // 初始化按钮状态
    updateLevelButtonsActive(savedLevel);
    
    // 根据保存的偏好设置初始显示
    setTocDisplayLevel(savedLevel);
    
    // 绑定层级切换按钮事件
    bindLevelControlEvents();
    
    // 为有展开图标的目录项添加 toc-expandable 类
    initializeTocExpandableItems();
    
    // 绑定展开/折叠图标事件
    bindExpandCollapseEvents();
    
    // 绑定全部展开/折叠按钮事件
    bindExpandAllEvents();
  }
  
  function bindLevelControlEvents() {
    const levelButtons = document.querySelectorAll('.toc-level-btn');
    levelButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括浮动按钮）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateLevelButtonsActive(activeLevel) {
    // 保持向后兼容，但现在使用统一的更新函数
    updateAllLevelButtonsActive(activeLevel);
  }
  
  function setTocDisplayLevel(level) {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const allItems = tocContainer.querySelectorAll('.toc-item');
    const targetLevel = parseInt(level);
    
    // 清除所有手動標記，讓層級控制重新接管
    allItems.forEach(item => {
      item.removeAttribute('data-user-toggled');
      item.removeAttribute('data-manually-shown');
    });
    
    allItems.forEach(item => {
      const itemLevel = parseInt(item.getAttribute('data-level'));
      
      // 根據層級控制顯示/隱藏
      if (itemLevel <= targetLevel) {
        item.classList.remove('hidden');
      } else {
        item.classList.add('hidden');
      }
      
      // 重新設置圖標狀態
      const expandIcon = item.querySelector('.toc-expand-icon');
      if (expandIcon) {
        if (itemLevel < targetLevel) {
          // 小於目標層級的項目自動展開
          expandIcon.classList.remove('collapsed');
          expandIcon.textContent = '▼';
        } else if (itemLevel === targetLevel) {
          // 等於目標層級的項目設為折疊狀態
          expandIcon.classList.add('collapsed');
          expandIcon.textContent = '▶';
        }
      }
    });
  }
  
  // 同步图标状态与实际展开状态
  function syncIconStates() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const expandableItems = tocContainer.querySelectorAll('.toc-item.toc-expandable');
    expandableItems.forEach(item => {
      const icon = item.querySelector('.toc-expand-icon');
      if (icon) {
        const actuallyExpanded = hasVisibleDirectChildren(item);
        
        if (actuallyExpanded) {
          icon.classList.remove('collapsed');
          icon.textContent = '▼';
        } else {
          icon.classList.add('collapsed');
          icon.textContent = '▶';
        }
      }
    });
  }

  // 初始化可展开的目录项
  function initializeTocExpandableItems() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 为所有有展开图标的目录项添加 toc-expandable 类
    const itemsWithIcons = tocContainer.querySelectorAll('.toc-item .toc-expand-icon');
    itemsWithIcons.forEach(icon => {
      const tocItem = icon.closest('.toc-item');
      if (tocItem) {
        tocItem.classList.add('toc-expandable');
      }
    });
    
    // 同步图标状态
    syncIconStates();
  }

  // 检查一个目录项是否有可见的直接子项
  function hasVisibleDirectChildren(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    let nextSibling = parentItem.nextElementSibling;
    
    // 查找直接子项
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      if (siblingLevel === parentLevel + 1) {
        // 这是直接子项，检查是否可见
        if (!nextSibling.classList.contains('hidden')) {
          return true;
        }
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
    
    return false;
  }

  function bindExpandCollapseEvents() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 使用事件委托处理展开/折叠和跳转
    tocContainer.addEventListener('click', function(e) {
      // 检查是否直接点击了链接文字
      if (e.target.tagName === 'A') {
        // 直接点击链接文字，允许默认行为（页面跳转）
        return;
      }
      
      // 查找最近的目录项
      const tocItem = e.target.closest('.toc-item');
      if (!tocItem) return;
      
      // 检查是否点击了可展开的目录项（有三角形图标的）
      const expandableItem = tocItem.classList.contains('toc-expandable') ? tocItem : null;
      if (expandableItem) {
        e.preventDefault();
        e.stopPropagation();
        
        const icon = expandableItem.querySelector('.toc-expand-icon');
        if (icon) {
          // 检查实际的展开状态：查看是否有可见的直接子项
          const actuallyExpanded = hasVisibleDirectChildren(expandableItem);
          
          // 标记这个项目已经被用户手动操作
          expandableItem.setAttribute('data-user-toggled', 'true');
          
          if (actuallyExpanded) {
            // 当前已展开，执行折叠
            collapseTocItem(expandableItem);
            icon.classList.add('collapsed');
            icon.textContent = '▶';
          } else {
            // 当前已折叠，执行展开
            expandTocItem(expandableItem);
            icon.classList.remove('collapsed');
            icon.textContent = '▼';
          }
        }
      } else {
        // 这是没有展开图标的目录项（叶子节点），处理整行点击跳转
        const link = tocItem.querySelector('a');
        if (link && !e.target.closest('a')) {
          // 点击的是目录项但不是链接本身，触发链接跳转
          e.preventDefault();
          e.stopPropagation();
          
          // 模拟点击链接
          link.click();
        }
      }
    });
  }
  
  function expandTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    let nextSibling = parentItem.nextElementSibling;
    
    // 找到所有直接子项并显示
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      if (siblingLevel === parentLevel + 1) {
        // 这是直接子项，显示它
        nextSibling.classList.remove('hidden');
        // 添加标记，表示这是用户手动展开的
        nextSibling.setAttribute('data-manually-shown', 'true');
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function collapseTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    let nextSibling = parentItem.nextElementSibling;
    
    // 隐藏所有子项
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      // 这是子项，隐藏它，并同时折叠其展开状态
      nextSibling.classList.add('hidden');
      // 清除手动展开标记
      nextSibling.removeAttribute('data-manually-shown');
      const childIcon = nextSibling.querySelector('.toc-expand-icon');
      if (childIcon) {
        childIcon.classList.add('collapsed');
        childIcon.textContent = '▶';
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function bindExpandAllEvents() {
    // 移除了全部展开/折叠按钮，因为现在只有3个层级按钮
    // 功能已经整合到层级按钮中
  }
  
  // ========== 浮动层级控制功能 ==========
  
  // 检测固定层级控制按钮是否在视窗中可见
  function areTocControlsVisible() {
    const tocControls = document.querySelector('.toc-level-controls');
    if (!tocControls) return false;
    
    const rect = tocControls.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 检查控制按钮是否在视窗内可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 检测目录内容是否在视窗中可见（确保有目录需要控制）
  function isTocContentVisible() {
    const mainToc = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!mainToc) return false;
    
    const rect = mainToc.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 目录内容的任何部分在视窗内都算可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 更新浮动层级控制的显示状态（全局函数，供搜索功能调用）
  function updateFloatingControlsState() {
    const floatingControls = document.getElementById('floating-level-controls');
    if (!floatingControls) return;
    
    const currentScrollY = window.scrollY;
    const isMobile = window.innerWidth <= 600;
    const scrollThreshold = isMobile ? 100 : 200;
    
    // 检查固定控制按钮是否可见
    const areControlsVisible = areTocControlsVisible();
    // 检查目录内容是否可见（确保有内容需要控制）
    const isTocContentAvailable = isTocContentVisible();
    
    // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
    const shouldShow = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
    
    if (shouldShow) {
      floatingControls.style.display = 'block';
    } else {
      floatingControls.style.display = 'none';
    }
  }
  
  function initFloatingLevelControls() {
    const floatingControls = document.getElementById('floating-level-controls');
    const tocControls = document.querySelector('.toc-level-controls');
    
    if (!floatingControls || !tocControls) return;
    
    // 调试模式：检查元素是否正确创建
    const debugMode = window.location.hash.includes('debug');
    if (debugMode) {
      console.log('FloatingControls found:', floatingControls);
      console.log('Screen size:', window.innerWidth, 'x', window.innerHeight);
      console.log('Device pixel ratio:', window.devicePixelRatio);
      console.log('User agent:', navigator.userAgent);
    }
    
    // 绑定浮动按钮事件
    bindFloatingLevelEvents();
    
    // 样式重置函数 - 清除JavaScript设置的内联样式
    function resetFloatingControlsStyles() {
      floatingControls.style.removeProperty('right');
      floatingControls.style.removeProperty('zIndex');
      floatingControls.style.removeProperty('position');
      if (debugMode) {
        console.log('Floating controls styles reset');
      }
    }
    
    // 重新应用正确的样式
    function applyCorrectStyles() {
      const isMobile = window.innerWidth <= 600;
      const isSmallMobile = window.innerWidth <= 400;
      
      if (isMobile) {
        // 移动端保持右側定位，設置必要的樣式
        floatingControls.style.zIndex = '10000';
        floatingControls.style.position = 'fixed';
        floatingControls.style.right = isSmallMobile ? '5px' : '8px';
        // 移除 left 設定，確保右側定位
        floatingControls.style.removeProperty('left');
      } else {
        // 桌面端时清除所有内联样式，让CSS媒体查询生效
        resetFloatingControlsStyles();
      }
      
      if (debugMode) {
        console.log('Styles applied for:', isMobile ? 'mobile' : 'desktop', 
                   `(${window.innerWidth}px)`);
      }
    }

    // 监听滚动，控制浮动按钮显示
    let lastScrollY = window.scrollY;
    const tocControlsRect = tocControls.getBoundingClientRect();
    const initialTop = tocControlsRect.top + window.scrollY;
    
    function handleScroll() {
      const currentScrollY = window.scrollY;
      // 检测移动端，降低显示门槛
      const isMobile = window.innerWidth <= 600;
      const scrollThreshold = isMobile ? 100 : 200; // 移动端更早显示
      
      // 检查固定控制按钮是否可见
      const areControlsVisible = areTocControlsVisible();
      // 检查目录内容是否可见
      const isTocContentAvailable = isTocContentVisible();
      
      // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
      const shouldShowFloating = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
      
      // 调试输出
      if (debugMode && currentScrollY > 50) {
        console.log(`Scroll: ${currentScrollY}px, Mobile: ${isMobile}, Threshold: ${scrollThreshold}, ControlsVisible: ${areControlsVisible}, TocContentVisible: ${isTocContentAvailable}, Show: ${shouldShowFloating}`);
      }
      
      if (shouldShowFloating) {
        // 滚动时显示浮动版本（仅当固定按钮不可见但目录内容可见时）
        floatingControls.style.display = 'block';
        // 应用正确的样式（基于当前屏幕尺寸）
        applyCorrectStyles();
      } else {
        // 页面顶部时、固定按钮可见时、或目录内容不可见时隐藏浮动版本
        floatingControls.style.display = 'none';
      }
      
      lastScrollY = currentScrollY;
    }
    
    // 添加滚动监听
    window.addEventListener('scroll', handleScroll, { passive: true });
    
    // 添加窗口大小变化监听（处理屏幕旋转）
    let resizeTimeout;
    window.addEventListener('resize', () => {
      // 去抖动处理，避免resize过程中频繁触发
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (debugMode) {
          console.log('Resize detected, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        // 重置所有内联样式，然后重新应用
        resetFloatingControlsStyles();
        handleScroll(); // 重新检查显示状态和应用样式
      }, 150); // 增加延迟确保resize完全完成
    }, { passive: true });
    
    // 添加方向变化监听（移动端特有）
    function handleOrientationChange() {
      setTimeout(() => {
        if (debugMode) {
          console.log('Orientation changed, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        resetFloatingControlsStyles();
        handleScroll();
      }, 200);
    }
    
    if (screen && screen.orientation) {
      screen.orientation.addEventListener('change', handleOrientationChange);
    } else {
      // 兼容旧浏览器的方向变化检测
      window.addEventListener('orientationchange', handleOrientationChange);
    }
    
    // 初始状态
    handleScroll();
  }
  
  function bindFloatingLevelEvents() {
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括顶部和浮动）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateAllLevelButtonsActive(activeLevel) {
    // 更新顶部按钮
    const topButtons = document.querySelectorAll('.toc-level-btn');
    topButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
    
    // 更新浮动按钮
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
  }

});