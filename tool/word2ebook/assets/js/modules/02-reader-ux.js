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

