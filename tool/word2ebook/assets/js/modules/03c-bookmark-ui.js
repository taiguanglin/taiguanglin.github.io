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

