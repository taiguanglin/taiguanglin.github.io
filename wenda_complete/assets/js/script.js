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
  
  // 检测当前页面类型
  function isIndexPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index.html' || filename === 'index_trad.html';
  }
  
  // 获取搜索索引文件名
  function getSearchIndexFile() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index_trad.html' ? 'search_index_trad.json' : 'search_index.json';
  }
  
  // 激活搜索功能
  async function activateSearch() {
    if (searchInitialized) {
      // 如果已经初始化，直接显示搜索容器
      const searchContainer = document.getElementById('search-container');
      const searchActivation = document.querySelector('.search-activation');
      if (searchContainer && searchActivation) {
        searchActivation.style.display = 'none';
        searchContainer.style.display = 'block';
        // 聚焦搜索框
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          setTimeout(() => searchInput.focus(), 100);
        }
      }
      return;
    }
    
    await initSearch();
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
      
      searchStatus.textContent = '正在加载搜索索引...';
      
      // 检查MiniSearch是否可用
      if (typeof MiniSearch === 'undefined') {
        throw new Error('MiniSearch库未加载');
      }
      
      // 加载搜索索引
      const indexFile = getSearchIndexFile();
      const response = await fetch(indexFile);
      
      if (!response.ok) {
        throw new Error('无法加载搜索索引');
      }
      
      searchIndex = await response.json();
      
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
      
      searchStatus.innerHTML = `
        搜索准备就绪 (共${searchIndex.length}条记录)
        <span style="color: #999; font-size: 12px; margin-left: 10px;">
          💡 点击结果将在新标签页打开
        </span>
      `;
      searchInitialized = true;
      
      // 聚焦搜索框
      setTimeout(() => searchInput.focus(), 100);
      
    } catch (error) {
      console.error('搜索初始化失败:', error);
      searchStatus.textContent = '搜索功能不可用：' + error.message;
      return;
    }
    
    // 搜索功能处理
    function performSearch(query) {
      if (!miniSearch || !query || query.trim().length < 2) {
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
        if (query && query.trim().length > 0 && query.trim().length < 2) {
          searchStatus.textContent = '请输入至少2个字符进行搜索';
        } else {
          searchStatus.textContent = `搜索准备就绪 (共${searchIndex ? searchIndex.length : 0}条记录)`;
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
        
        // 限制结果数量
        const limitedResults = results.slice(0, 20);
        
        if (limitedResults.length > 0) {
          displayResults(limitedResults, trimmedQuery);
          searchStatus.textContent = `找到 ${results.length} 条结果` + (results.length > 20 ? ' (仅显示前20条)' : '');
        } else {
          displayNoResults(trimmedQuery);
          searchStatus.textContent = '未找到匹配结果';
        }
        
        searchResults.style.display = 'block';
        tocHeader.style.display = 'none';
        
      } catch (error) {
        console.error('搜索出错:', error);
        searchStatus.textContent = '搜索出现错误，请重试';
        // 在出错时也隐藏搜索结果
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
      }
    }
    
    // 显示搜索结果
    function displayResults(results, query) {
      searchResultsCount.textContent = `找到 ${results.length} 条结果`;
      
      searchResultsList.innerHTML = results.map(result => {
        const typeText = {
          'heading': '标题',
          'question': '问题', 
          'answer': '回答',
          'content': '内容'
        }[result.type] || '内容';
        
        // 高亮搜索关键词 - 安全处理
        let highlightedContext = result.context;
        try {
          if (query && query.trim()) {
            const escapedQuery = escapeRegex(query.trim());
            if (escapedQuery) {
              const regex = new RegExp(`(${escapedQuery})`, 'gi');
              highlightedContext = result.context.replace(regex, '<span class="search-result-highlight">$1</span>');
            }
          }
        } catch (e) {
          console.warn('搜索高亮处理失败:', e);
          // 降级处理：不高亮但显示内容
          highlightedContext = result.context;
        }
        
        return `
          <li class="search-result-item" data-url="${result.url}">
            <div class="search-result-title">
              <span class="search-result-type">${typeText}</span>
              ${escapeHtml(result.title)}
              <span class="search-result-newtab">↗</span>
            </div>
            <div class="search-result-content">${highlightedContext}</div>
            <div class="search-result-url">${result.url}</div>
          </li>
        `;
      }).join('');
    }
    
    // 显示无结果
    function displayNoResults(query) {
      searchResultsCount.textContent = '未找到结果';
      searchResultsList.innerHTML = `
        <li class="search-result-item" style="text-align: center; color: #999;">
          <div>未找到包含"${escapeHtml(query)}"的内容</div>
          <div style="font-size: 12px; margin-top: 8px;">尝试使用不同的关键词</div>
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
        '\\': '\\\\',
        '.': '\\.',
        '*': '\\*',
        '+': '\\+',
        '?': '\\?',
        '^': '\\^',
        '$': '\\$',
        '{': '\\{',
        '}': '\\}',
        '(': '\\(',
        ')': '\\)',
        '|': '\\|',
        '[': '\\[',
        ']': '\\]',
        '/': '\\/'
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
    
    // 清除搜索
    function clearSearch() {
      searchInput.value = '';
      searchResults.style.display = 'none';
      tocHeader.style.display = 'block';
      searchStatus.innerHTML = `
        搜索准备就绪 (共${searchIndex.length}条记录)
        <span style="color: #999; font-size: 12px; margin-left: 10px;">
          💡 点击结果将在新标签页打开
        </span>
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
      // 清除搜索内容
      if (searchInput) searchInput.value = '';
      if (searchResults) searchResults.style.display = 'none';
      if (tocHeader) tocHeader.style.display = 'block';
      
      // 隐藏搜索容器，显示激活按钮
      searchContainer.style.display = 'none';
      searchActivation.style.display = 'block';
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
        // 只顯示前兩層目錄，跳過第三層及以下
        if (level >= 3) {
          return; // 跳過第三層及以下的項目
        }
        
        let levelClass = '';
        if (level === 2) {
          levelClass = ' level-h3';
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
      // 首頁只顯示目錄
      tabsHtml = '<button class="floating-toc-tab active" data-tab="toc">目錄</button>';
      contentHtml = 
        '<div class="floating-toc-list" id="toc-list">' +
          tocItems +
        '</div>';
    } else {
      // 其他頁面顯示目錄和書籤
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="toc">目錄</button>' +
        '<button class="floating-toc-tab" data-tab="bookmarks">書籤 <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<div class="floating-toc-list" id="toc-list">' +
          tocItems +
        '</div>' +
        '<div class="floating-toc-list" id="bookmarks-list" style="display: none;">' +
          '<div class="bookmarks-empty">尚無書籤</div>' +
        '</div>';
    }
    
    toc.innerHTML = 
      '<div class="floating-toc-header">' +
        '<span id="toc-title">📖 章節目錄</span>' +
        '<button class="ctrl-btn" data-action="close-toc">✕</button>' +
      '</div>' +
      '<div class="floating-toc-tabs">' +
        tabsHtml +
      '</div>' +
      '<div class="floating-toc-content">' +
        contentHtml +
      '</div>';
    
    document.body.appendChild(toc);
    return toc;
  }

  // 創建操作按鈕組
  function createActionButtons() {
    const buttons = document.createElement('div');
    buttons.className = 'action-buttons';
    buttons.innerHTML = 
      '<div class="action-menu">' +
        '<button class="action-btn menu-btn" data-action="toggle-menu" title="功能菜單">⋯</button>' +
        '<div class="action-menu-items">' +
          '<button class="action-btn" data-action="toc" title="目錄">📖</button>' +
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
        actionsHtml += '<button class="qa-btn" data-action="copy" title="複製問題">📋</button>';
        if (!currentChapter.isHomepage) {
          actionsHtml += '<button class="qa-btn" data-action="bookmark-qa" title="加入書籤">🔖</button>';
        }
        actionsHtml += '<button class="qa-btn" data-action="share" title="分享問題">📤</button>';
      } else if (isAnswer) {
        actionsHtml += '<button class="qa-btn" data-action="copy-qa" title="複製問答">📋</button>';
        if (!currentChapter.isHomepage) {
          actionsHtml += '<button class="qa-btn" data-action="bookmark-qa" title="加入書籤">🔖</button>';
        }
        actionsHtml += '<button class="qa-btn" data-action="share" title="分享回答">📤</button>';
      }
      
      actions.innerHTML = actionsHtml;
      element.appendChild(actions);
    });
  }

  // ============ 功能實現 ============
  
  // 生成內容的簡單hash
  function simpleHash(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 轉換為32位整數
    }
    return Math.abs(hash).toString(36);
  }
  
  // 確保元素有唯一且穩定的ID
  function ensureElementId(element, prefix = 'qa') {
    if (!element.id) {
      // 基於內容生成穩定的ID
      let contentText = '';
      
      if (element.classList.contains('question')) {
        const questioner = element.querySelector('.questioner')?.textContent || '';
        const questionText = element.querySelector('.question-text')?.textContent || '';
        const time = element.querySelector('.question-time')?.textContent || '';
        contentText = questioner + questionText + time;
      } else if (element.classList.contains('answer')) {
        const answerer = element.querySelector('.answerer')?.textContent || '';
        const answerText = element.querySelector('.answer-text')?.textContent || '';
        contentText = answerer + answerText.substring(0, 100); // 只取前100字符
      }
      
      // 生成基於內容的穩定ID
      const contentHash = simpleHash(contentText);
      element.id = prefix + '-' + contentHash;
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
  function getQAPairText(answerElement) {
    const questionElement = findQuestionForAnswer(answerElement);
    let text = '';
    
    if (questionElement) {
      // 提取問題內容
      const questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
      const questionTime = questionElement.querySelector('.question-time')?.textContent || '';
      const questionText = questionElement.querySelector('.question-text')?.textContent || '';
      
      text += `問：${questioner}`;
      if (questionTime) text += ` (${questionTime})`;
      text += `
${questionText}

`;
    }
    
    // 提取回答內容
    const answerer = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
    const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
    
    text += `答：${answerer}
${answerText}`;
    
    return text;
  }
  
  // ============ 書籤功能 ============
  
  // 書籤管理
  function getBookmarks(chapterId = null) {
    const allBookmarks = localStorage.getItem('ebook-bookmarks');
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
    localStorage.setItem('ebook-bookmarks', JSON.stringify(bookmarks));
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
        
        // 如果是問答書籤，還需要為問題添加視覺標識
        if (bookmark.type === 'qa-pair' && element.classList.contains('answer')) {
          const questionElement = findQuestionForAnswer(element);
          if (questionElement) {
            addBookmarkVisualIndicator(questionElement);
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
  
  // 初始化當前文件信息（文件級書籤，無需監聽滾動）
  let currentChapter = getCurrentChapter();

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
      timestamp: new Date().toLocaleString()
    };
    
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    addBookmarkVisualIndicator(element);
    renderBookmarks();
    showToast('已添加到書籤');
  }
  
  function toggleQAPairBookmark(answerElement) {
    // 首頁不允許操作書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const bookmarks = getBookmarks();
    const questionElement = findQuestionForAnswer(answerElement);
    
    // 生成唯一ID
    const id = answerElement.id || ('qa-bookmark-' + Date.now());
    answerElement.id = id;
    
    // 檢查是否已存在書籤
    const existingBookmark = bookmarks.find(bookmark => bookmark.elementId === id);
    
    if (existingBookmark) {
      // 已存在，移除書籤
      removeBookmarkVisualIndicator(answerElement);
      if (questionElement) {
        removeBookmarkVisualIndicator(questionElement);
      }
      const updatedBookmarks = bookmarks.filter(bookmark => bookmark.elementId !== id);
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
      elementId: id,
      type: 'qa-pair',
      questioner: questioner,
      time: time,
      preview: preview,
      chapter: chapter,
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
    showToast('已添加問答到書籤');
  }
  
  function removeBookmark(bookmarkId) {
    const bookmarks = getBookmarks();
    const bookmark = bookmarks.find(b => b.id === bookmarkId);
    
    // 移除視覺標識
    if (bookmark) {
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
  
  function renderBookmarks() {
    const bookmarksList = document.getElementById('bookmarks-list');
    
    // 首頁不顯示書籤
    if (currentChapter.isHomepage || !bookmarksList) {
      return;
    }
    
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
  }
  
  function updateBookmarkCount() {
    // 首頁不顯示書籤計數
    if (currentChapter.isHomepage) {
      return;
    }
    
    const count = getCurrentChapterBookmarks().length;
    const countEl = document.getElementById('bookmark-count');
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
    document.body.style.lineHeight = lineHeight;
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
  
  // 初始化所有組件
  const toolbar = createReadingToolbar();
  const progressBar = createReadingProgress();
  const floatingTOC = createFloatingTOC();
  const actionButtons = createActionButtons();
  addQAActions();
  applyReadingSettings();
  
  // 初始化當前章節
  currentChapter = getCurrentChapter();
  
  updateBookmarkCount();
  updateThemeButtons();
  restoreBookmarkVisualStates();
  
  // 延遲執行章節跟踪，確保頁面完全渲染
  setTimeout(updateCurrentSection, 100);
  
  // 處理頁面加載時的錨點跳轉
  setTimeout(handleInitialAnchor, 200);

  document.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    
    // 點擊外部區域關閉菜單
    if (!action && !e.target.closest('.action-menu')) {
      const openMenu = document.querySelector('.action-menu.expanded');
      if (openMenu) {
        openMenu.classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
      }
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

      // 行距設置 - 擴大調整幅度讓用戶感受到明顯差異
      case 'line-tight':
        updateLineHeight(0.4);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'line-normal':
        updateLineHeight(1.0);
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
        const actionMenu = e.target.closest('.action-menu');
        actionMenu.classList.toggle('expanded');
        e.target.classList.toggle('expanded');
        break;
      case 'toc':
        floatingTOC.classList.toggle('visible');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
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
      case 'copy':
        const copyElement = e.target.closest('.question, .answer');
        const text = copyElement.textContent.trim();
        copyText(text);
        break;
      case 'bookmark':
        const bookmarkElement = e.target.closest('.question, .answer');
        if (bookmarkElement) {
          toggleBookmark(bookmarkElement);
        }
        break;
      case 'copy-qa':
        const copyAnswerElement = e.target.closest('.answer');
        if (copyAnswerElement) {
          const qaPairText = getQAPairText(copyAnswerElement);
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
        tocList.style.display = 'block';
        bookmarksList.style.display = 'none';
        tocTitle.textContent = '📖 章節目錄';
      } else if (tab === 'bookmarks') {
        tocList.style.display = 'none';
        bookmarksList.style.display = 'block';
        tocTitle.textContent = '🔖 我的書籤';
        renderBookmarks();
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

  // 快捷鍵支持
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'k':
          e.preventDefault();
          floatingTOC.classList.toggle('visible');
          break;
        case '[':
          e.preventDefault();
          updateFontSize(-2);
          break;
        case ']':
          e.preventDefault();
          updateFontSize(2);
          break;
      }
    }
    
    if (e.key === 'Escape') {
      floatingTOC.classList.remove('visible');
      toolbar.classList.add('hidden');
    }
  });

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
});
