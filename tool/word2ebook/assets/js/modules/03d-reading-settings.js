  // 閱讀設置功能
  // 根据屏幕尺寸设置默认字体大小
  function getDefaultFontSize() {
    const screenWidth = window.innerWidth;
    if (screenWidth <= 400) {
      return 19; // 小手机默认19px
    } else if (screenWidth <= 600) {
      return 18; // 手机默认18px
    } else if (screenWidth <= 768) {
      return 17; // 平板默认17px
    }
    return 16; // 桌面默认16px
  }
  
  let fontSize = parseInt(localStorage.getItem('fontSize')) || getDefaultFontSize();
  let lineHeight = parseFloat(localStorage.getItem('lineHeight')) || 1.6;
  let contentWidth = parseInt(localStorage.getItem('contentWidth')) || 800;
  
  function applyReadingSettings() {
    // 使用!important确保字体大小设置在移动设备上生效
    document.body.style.setProperty('font-size', fontSize + 'px', 'important');
    document.documentElement.style.setProperty('--line-height', lineHeight);
    document.body.style.maxWidth = contentWidth + 'px';
    
    // 動態調整TOC目錄的字型大小和間距
    // 移除現有的動態TOC樣式
    let existingTocStyle = document.getElementById('dynamic-toc-styles');
    if (existingTocStyle) {
      existingTocStyle.remove();
    }
    
    // 創建新的動態樣式
    const tocStyle = document.createElement('style');
    tocStyle.id = 'dynamic-toc-styles';
    
    // 檢測螢幕大小，調整響應式基礎字型
    const screenWidth = window.innerWidth;
    let responsiveBaseFontSize = fontSize;
    
    // 根據螢幕寬度調整基礎字型大小，但允許用户自由调整
    // 移除最小值限制，允许用户设置更小的字体
    responsiveBaseFontSize = fontSize;
    
    // 計算相對於響應式基礎字型大小的比例
    const fontScale = responsiveBaseFontSize / 16;
    const lineHeightValue = lineHeight;
    
    // 各層級的字型大小比例（相對於響應式基礎大小）
    const level1Size = Math.round(responsiveBaseFontSize * 1.1); // 第一層：稍大
    const level2Size = responsiveBaseFontSize; // 第二層：基礎大小  
    const level3Size = Math.round(responsiveBaseFontSize * 0.95); // 第三層：稍小
    const level4Size = Math.round(responsiveBaseFontSize * 0.9); // 第四層：更小
    
    // 調試信息
    console.log('字體設置應用:', {
      screenWidth,
      fontSize,
      responsiveBaseFontSize,
      level1Size,
      level2Size,
      level3Size,
      level4Size,
      lineHeightValue
    });
    
    // 間距調整（基於行距設置）
    const spacing1 = Math.round(8 * lineHeightValue / 1.6); // 第一層間距
    const spacing2 = Math.round(6 * lineHeightValue / 1.6); // 第二層間距  
    const spacing3 = Math.round(4 * lineHeightValue / 1.6); // 第三層間距
    const spacing4 = Math.round(3 * lineHeightValue / 1.6); // 第四層間距
    
    tocStyle.textContent = `
      /* 首頁TOC樣式調整 - 使用更高的特定性確保生效 */
      #main-toc .toc > ul > li,
      .toc > ul > li { 
        font-size: ${level1Size}px !important; 
        margin-bottom: ${spacing1}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul > li,
      .toc ul ul > li { 
        font-size: ${level2Size}px !important; 
        margin-bottom: ${spacing2}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul ul > li,
      .toc ul ul ul > li { 
        font-size: ${level3Size}px !important; 
        margin-bottom: ${spacing3}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul ul ul > li,
      .toc ul ul ul ul > li { 
        font-size: ${level4Size}px !important; 
        margin-bottom: ${spacing4}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      /* 章節頁TOC樣式調整 - 使用更高的特定性確保生效 */
      #chapter-toc .toc-item.toc-level-1 > a,
      .toc-item.toc-level-1 > a {
        font-size: ${level1Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-2 > a,
      .toc-item.toc-level-2 > a {
        font-size: ${level2Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-3 > a,
      .toc-item.toc-level-3 > a {
        font-size: ${level3Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-4 > a,
      .toc-item.toc-level-4 > a {
        font-size: ${level4Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      /* TOC項目的間距調整 */
      .toc-item.toc-level-1 {
        margin-bottom: ${spacing1}px !important;
      }
      
      .toc-item.toc-level-2 {
        margin-bottom: ${spacing2}px !important;
      }
      
      .toc-item.toc-level-3 {
        margin-bottom: ${spacing3}px !important;
      }
      
      .toc-item.toc-level-4 {
        margin-bottom: ${spacing4}px !important;
      }
      
      /* 浮動TOC樣式調整 */
      .floating-toc-item {
        font-size: ${Math.round(fontSize * 0.85)}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      .floating-toc-item.level-h3 {
        font-size: ${Math.round(fontSize * 0.8)}px !important;
      }
      
      .floating-toc-item.level-h4 {
        font-size: ${Math.round(fontSize * 0.75)}px !important;
      }
      
      .floating-toc-item.level-h5 {
        font-size: ${Math.round(fontSize * 0.7)}px !important;
      }
      
      /* 層級控制按鈕樣式調整 */
      .toc-level-label {
        font-size: ${Math.round(fontSize * 0.9)}px !important;
      }
      
      .toc-level-btn, .floating-level-btn {
        font-size: ${Math.round(fontSize * 0.9)}px !important;
      }
      
      .floating-level-label {
        font-size: ${Math.round(fontSize * 0.7)}px !important;
      }
    `;
    
    document.head.appendChild(tocStyle);
    
    // 動態調整搜索功能的字型大小
    applySearchFontStyles();
  }
  
  // 應用搜索功能字體樣式
  function applySearchFontStyles() {
    // 移除現有的動態搜索樣式
    let existingSearchStyle = document.getElementById('dynamic-search-styles');
    if (existingSearchStyle) {
      existingSearchStyle.remove();
    }
    
    // 創建新的動態搜索樣式
    const searchStyle = document.createElement('style');
    searchStyle.id = 'dynamic-search-styles';
    
    // 計算搜索相關元素的字體大小
    const baseFontSize = fontSize;
    const inputFontSize = Math.max(14, Math.min(20, baseFontSize)); // 輸入框：14-20px範圍
    const contentFontSize = Math.max(12, Math.round(baseFontSize * 0.9)); // 搜索結果內容稍小，最小12px
    const titleFontSize = Math.max(12, Math.round(baseFontSize * 0.85)); // 標題更小，最小12px
    const controlFontSize = Math.max(10, Math.round(baseFontSize * 0.75)); // 控制按鈕最小10px
    const statusFontSize = Math.max(11, Math.round(baseFontSize * 0.8)); // 狀態文字最小11px
    const activateBtnFontSize = Math.max(13, Math.round(baseFontSize * 0.9)); // 激活按鈕最小13px
    
    // 調試信息
    console.log('搜索字體設置應用:', {
      baseFontSize,
      inputFontSize,
      contentFontSize,
      titleFontSize,
      controlFontSize,
      statusFontSize,
      activateBtnFontSize
    });
    
    searchStyle.textContent = `
      /* 搜索輸入框字體 */
      #search-input {
        font-size: ${inputFontSize}px !important;
      }
      
      /* 搜索輸入框占位符字體 */
      #search-input::placeholder {
        font-size: ${inputFontSize}px !important;
      }
      
      /* 搜索結果內容字體 */
      .search-result-content {
        font-size: ${contentFontSize}px !important;
        line-height: ${lineHeight} !important;
      }
      
      /* 搜索結果標題字體 */
      .search-result-title {
        font-size: ${titleFontSize}px !important;
      }
      
      /* 搜索狀態文字 */
      .search-status,
      .search-loading-text {
        font-size: ${statusFontSize}px !important;
      }
      
      /* 搜索控制按鈕 */
      .search-clear,
      .search-collapse,
      .search-load-more,
      .search-load-all,
      .search-retry-btn {
        font-size: ${controlFontSize}px !important;
      }
      
      /* 搜索結果底部控制按鈕 */
      .search-results-footer {
        padding: 10px;
        border-top: 1px solid var(--border-color);
        background: var(--bg-color);
        position: sticky;
        bottom: 0;
      }
      
      .search-results-footer .search-results-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        flex-wrap: wrap;
      }
      
      /* 搜索結果編號 */
      .search-result-header {
        display: inline-block;
        align-items: center;
        gap: 4px;
        margin-bottom: 4px;
        flex-wrap: nowrap;
        min-height: fit-content;
      }
      
      .search-result-number {
        background: #e75480;
        color: white;
        padding: 2px 4px;
        border-radius: 3px;
        font-size: ${Math.max(9, Math.round(titleFontSize * 0.8))}px !important;
        font-weight: bold;
        flex-shrink: 0;
        white-space: nowrap;
        line-height: 1.2;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
      }
      
      .search-result-title {
        display: inline-block;
        flex: 1;
        min-width: 0;
        margin: 0;
        padding: 0;
      }
      
      /* 搜索激活按鈕 */
      .search-activate-btn {
        font-size: ${activateBtnFontSize}px !important;
      }
      
      /* 搜索結果類型標籤 */
      .search-result-type {
        font-size: ${Math.round(controlFontSize * 0.9)}px !important;
      }
      
      /* 搜索結果統計 */
      .search-results-count {
        font-size: ${statusFontSize}px !important;
      }
      
    `;
    
    document.head.appendChild(searchStyle);
  }
  
  function updateFontSize(change) {
    fontSize = Math.max(12, Math.min(24, fontSize + change));
    localStorage.setItem('fontSize', fontSize);
    applyReadingSettings();
    updateFontSizeButtons();
  }
  
  function updateLineHeight(value) {
    lineHeight = value;
    localStorage.setItem('lineHeight', lineHeight);
    applyReadingSettings();
    updateLineHeightButtons();
  }
  
  function updateContentWidth(value) {
    contentWidth = value;
    localStorage.setItem('contentWidth', contentWidth);
    applyReadingSettings();
    updateContentWidthButtons();
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

