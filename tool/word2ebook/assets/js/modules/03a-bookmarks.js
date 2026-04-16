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
        indicator.title = getI18nText('bookmark.removeBookmark', isTraditionalChinesePage(), '點擊移除書籤');
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
        title: getI18nText('navigation.homepage', isTraditionalChinesePage(), '首頁'),
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
        bookmarksList.innerHTML = '<li class="bookmarks-empty">' + getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>';
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
    showToast(getI18nText('bookmark.bookmarkDeleted', isTraditionalChinesePage(), '書籤已刪除'));
  }
  
  // 書籤添加成功的視覺反饋
  function showBookmarkAddedFeedback() {
    // 首頁有floating-toc，章節頁面沒有，需要分別處理
    if (currentChapter.isHomepage) {
      // 首頁：顯示提示並引導到側邊欄
      showToast(getI18nText('bookmark.viewInSidebar', isTraditionalChinesePage(), '已添加到書籤，可在側邊欄查看'));
      
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
  
