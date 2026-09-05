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
  updateReadingSettingsButtons();
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
        addFontAdjustFeedback(e.target);
        break;
      case 'font-normal':
        fontSize = getDefaultFontSize();
        localStorage.setItem('fontSize', fontSize);
        applyReadingSettings();
        updateFontSizeButtons();
        break;
      case 'font-increase':
        updateFontSize(2);
        addFontAdjustFeedback(e.target);
        break;

      // 行距設置
      case 'line-tight':
        updateLineHeight(1.2);
        break;
      case 'line-normal':
        updateLineHeight(1.6);
        break;
      case 'line-loose':
        updateLineHeight(2.0);
        break;

      // 寬度設置
      case 'width-narrow':
        updateContentWidth(600);
        break;
      case 'width-normal':
        updateContentWidth(800);
        break;
      case 'width-wide':
        updateContentWidth(1000);
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
      case 'home':
        // 回到首頁 - 根據當前頁面語言版本決定目標首頁
        const homePageUrl = isTraditionalChinesePage() ? 'index_trad.html' : 'index.html';
        window.location.href = homePageUrl;
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
      case 'copy-para':
        const copyParaElement = e.target.closest('.para-block');
        if (copyParaElement) {
          copyText(getParagraphText(copyParaElement));
        }
        break;
      case 'bookmark-para':
        const paraBookmarkElement = e.target.closest('.para-block');
        if (paraBookmarkElement) {
          toggleParagraphBookmark(paraBookmarkElement);
        }
        break;
      case 'share':
        const shareElement = e.target.closest('.question, .answer, .para-block');
        if (shareElement) {
          // 直接分享點擊的區塊（問題、回答或段落）
          const shareUrl = generateShareUrl(shareElement);
          const isQuestion = shareElement.classList.contains('question');
          const isParagraph = shareElement.classList.contains('para-block');
          const toastMessage = isParagraph ? '段落鏈接已複製' : (isQuestion ? '問題鏈接已複製' : '回答鏈接已複製');
          
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
        
        // 切換到目錄標籤頁時，自動定位到當前章節
        // 添加小延遲確保DOM更新完成
        setTimeout(() => {
          updateCurrentSection();
        }, 50);
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
      const bookmarkedElement = e.target.closest('.question, .answer, .para-block');
      if (bookmarkedElement) {
        // 段落書籤：直接切換移除
        if (bookmarkedElement.classList.contains('para-block')) {
          toggleParagraphBookmark(bookmarkedElement);
          return;
        }
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

  // 為字體調整按鈕添加點擊反饋效果
  function addFontAdjustFeedback(button) {
    if (button.classList.contains('font-adjust')) {
      button.classList.add('clicked');
      setTimeout(() => {
        button.classList.remove('clicked');
      }, 150); // 150ms後移除反饋效果
    }
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

