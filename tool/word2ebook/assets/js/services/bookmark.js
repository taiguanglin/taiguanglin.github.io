/**
 * @fileoverview 書籤服務
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG } from '../constants/config.js';
import { PageUtils } from '../utils/page.js';
import { BookmarkStorage } from '../utils/storage.js';
import { I18nService } from './i18n.js';

/**
 * 書籤服務類
 * @class BookmarkService
 */
export class BookmarkService {
  constructor() {
    this.isInitialized = false;
    this.eventListeners = new Map();
    this._init();
  }

  /**
   * 初始化書籤服務
   * @private
   */
  _init() {
    // 遷移舊版書籤數據
    BookmarkStorage.migrateOldBookmarks();
    this.isInitialized = true;
  }

  /**
   * 獲取當前語言版本的書籤
   * @param {string} [chapterId] - 章節 ID（可選）
   * @returns {Array} 書籤陣列
   */
  getBookmarks(chapterId = null) {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    return BookmarkStorage.getBookmarks(isTraditional, chapterId);
  }

  /**
   * 獲取當前章節的書籤
   * @returns {Array} 當前章節的書籤
   */
  getCurrentChapterBookmarks() {
    const currentChapter = this.getCurrentChapter();
    return this.getBookmarks(currentChapter.id);
  }

  /**
   * 添加書籤
   * @param {Element} element - 要書籤的元素
   * @returns {Object} 操作結果
   */
  async addBookmark(element) {
    if (!element) {
      return { success: false, error: 'INVALID_ELEMENT' };
    }

    try {
      const bookmark = this._createBookmarkFromElement(element);
      const isTraditional = PageUtils.isTraditionalChinesePage();
      
      // 檢查是否已存在
      const existingBookmarks = this.getBookmarks();
      const exists = existingBookmarks.some(item => item.id === bookmark.id);
      
      if (exists) {
        return { success: false, error: 'BOOKMARK_EXISTS' };
      }

      // 保存書籤
      const success = BookmarkStorage.addBookmark(bookmark, isTraditional);
      
      if (success) {
        // 添加視覺標識
        this._addBookmarkVisualIndicator(element);
        
        // 觸發事件
        this._emitEvent('bookmarkAdded', { bookmark, element });
        
        return { success: true, bookmark };
      } else {
        return { success: false, error: 'SAVE_FAILED' };
      }

    } catch (error) {
      console.error('添加書籤失敗:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * 移除書籤
   * @param {string} bookmarkId - 書籤 ID
   * @returns {Object} 操作結果
   */
  async removeBookmark(bookmarkId) {
    if (!bookmarkId) {
      return { success: false, error: 'INVALID_BOOKMARK_ID' };
    }

    try {
      const isTraditional = PageUtils.isTraditionalChinesePage();
      const success = BookmarkStorage.removeBookmark(bookmarkId, isTraditional);
      
      if (success) {
        // 移除視覺標識
        this._removeBookmarkVisualIndicator(bookmarkId);
        
        // 觸發事件
        this._emitEvent('bookmarkRemoved', { bookmarkId });
        
        return { success: true };
      } else {
        return { success: false, error: 'BOOKMARK_NOT_FOUND' };
      }

    } catch (error) {
      console.error('移除書籤失敗:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * 切換書籤狀態
   * @param {Element} element - 目標元素
   * @returns {Object} 操作結果
   */
  async toggleBookmark(element) {
    if (!element) {
      return { success: false, error: 'INVALID_ELEMENT' };
    }

    const bookmarkId = this._generateBookmarkId(element);
    const existingBookmarks = this.getBookmarks();
    const exists = existingBookmarks.some(item => item.id === bookmarkId);

    if (exists) {
      return this.removeBookmark(bookmarkId);
    } else {
      return this.addBookmark(element);
    }
  }

  /**
   * 檢查元素是否已被書籤
   * @param {Element} element - 目標元素
   * @returns {boolean} 是否已書籤
   */
  isBookmarked(element) {
    if (!element) return false;

    const bookmarkId = this._generateBookmarkId(element);
    const bookmarks = this.getBookmarks();
    return bookmarks.some(bookmark => bookmark.id === bookmarkId);
  }

  /**
   * 更新書籤
   * @param {string} bookmarkId - 書籤 ID
   * @param {Object} updates - 更新內容
   * @returns {Object} 操作結果
   */
  async updateBookmark(bookmarkId, updates) {
    if (!bookmarkId || !updates) {
      return { success: false, error: 'INVALID_PARAMETERS' };
    }

    try {
      const isTraditional = PageUtils.isTraditionalChinesePage();
      const success = BookmarkStorage.updateBookmark(bookmarkId, updates, isTraditional);
      
      if (success) {
        this._emitEvent('bookmarkUpdated', { bookmarkId, updates });
        return { success: true };
      } else {
        return { success: false, error: 'UPDATE_FAILED' };
      }

    } catch (error) {
      console.error('更新書籤失敗:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * 清空當前章節的書籤
   * @returns {Object} 操作結果
   */
  async clearCurrentChapterBookmarks() {
    try {
      const currentChapter = this.getCurrentChapter();
      const isTraditional = PageUtils.isTraditionalChinesePage();
      const success = BookmarkStorage.clearChapterBookmarks(currentChapter.id, isTraditional);
      
      if (success) {
        // 移除所有視覺標識
        this._removeAllBookmarkVisualIndicators();
        
        // 觸發事件
        this._emitEvent('chapterBookmarksCleared', { chapterId: currentChapter.id });
        
        return { success: true };
      } else {
        return { success: false, error: 'CLEAR_FAILED' };
      }

    } catch (error) {
      console.error('清空章節書籤失敗:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * 恢復書籤視覺狀態
   */
  restoreBookmarkVisualStates() {
    const bookmarks = this.getCurrentChapterBookmarks();
    
    bookmarks.forEach(bookmark => {
      const element = this._findElementByBookmarkId(bookmark.id);
      if (element) {
        this._addBookmarkVisualIndicator(element);
      }
    });
  }

  /**
   * 導出書籤
   * @param {string} [format='json'] - 導出格式
   * @returns {string} 導出的書籤數據
   */
  exportBookmarks(format = 'json') {
    const bookmarks = this.getBookmarks();
    
    switch (format) {
      case 'json':
        return JSON.stringify(bookmarks, null, 2);
      
      case 'csv':
        const headers = ['ID', 'Title', 'Type', 'Chapter', 'Created At', 'URL'];
        const rows = bookmarks.map(bookmark => [
          bookmark.id,
          bookmark.title || '',
          bookmark.type || '',
          bookmark.chapter?.title || '',
          bookmark.createdAt || '',
          bookmark.url || '',
        ]);
        
        const csvContent = [headers, ...rows]
          .map(row => row.map(field => `"${String(field).replace(/"/g, '""')}"`).join(','))
          .join('\n');
        
        return csvContent;
      
      default:
        throw new Error(`不支援的導出格式: ${format}`);
    }
  }

  /**
   * 導入書籤
   * @param {string} data - 書籤數據
   * @param {string} [format='json'] - 數據格式
   * @returns {Object} 導入結果
   */
  async importBookmarks(data, format = 'json') {
    try {
      let bookmarks;
      
      switch (format) {
        case 'json':
          bookmarks = JSON.parse(data);
          break;
        
        default:
          throw new Error(`不支援的導入格式: ${format}`);
      }

      if (!Array.isArray(bookmarks)) {
        throw new Error('書籤數據格式無效');
      }

      const isTraditional = PageUtils.isTraditionalChinesePage();
      const currentBookmarks = this.getBookmarks();
      
      let importedCount = 0;
      let skippedCount = 0;

      for (const bookmark of bookmarks) {
        // 檢查是否已存在
        const exists = currentBookmarks.some(item => item.id === bookmark.id);
        
        if (!exists) {
          const success = BookmarkStorage.addBookmark(bookmark, isTraditional);
          if (success) {
            importedCount++;
          }
        } else {
          skippedCount++;
        }
      }

      this._emitEvent('bookmarksImported', { importedCount, skippedCount });
      
      return {
        success: true,
        importedCount,
        skippedCount,
        totalCount: bookmarks.length,
      };

    } catch (error) {
      console.error('導入書籤失敗:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * 獲取書籤統計信息
   * @returns {Object} 統計信息
   */
  getStats() {
    const allBookmarks = this.getBookmarks();
    const currentChapterBookmarks = this.getCurrentChapterBookmarks();
    
    // 按類型統計
    const typeStats = allBookmarks.reduce((stats, bookmark) => {
      const type = bookmark.type || 'unknown';
      stats[type] = (stats[type] || 0) + 1;
      return stats;
    }, {});

    // 按章節統計
    const chapterStats = allBookmarks.reduce((stats, bookmark) => {
      const chapterTitle = bookmark.chapter?.title || 'unknown';
      stats[chapterTitle] = (stats[chapterTitle] || 0) + 1;
      return stats;
    }, {});

    return {
      totalBookmarks: allBookmarks.length,
      currentChapterBookmarks: currentChapterBookmarks.length,
      typeStats,
      chapterStats,
      oldestBookmark: allBookmarks.length > 0 ? 
        allBookmarks.reduce((oldest, bookmark) => 
          new Date(bookmark.createdAt) < new Date(oldest.createdAt) ? bookmark : oldest
        ) : null,
      newestBookmark: allBookmarks.length > 0 ? 
        allBookmarks.reduce((newest, bookmark) => 
          new Date(bookmark.createdAt) > new Date(newest.createdAt) ? bookmark : newest
        ) : null,
    };
  }

  /**
   * 添加事件監聽器
   * @param {string} eventType - 事件類型
   * @param {Function} callback - 回調函數
   */
  addEventListener(eventType, callback) {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, []);
    }
    this.eventListeners.get(eventType).push(callback);
  }

  /**
   * 移除事件監聽器
   * @param {string} eventType - 事件類型
   * @param {Function} callback - 回調函數
   */
  removeEventListener(eventType, callback) {
    if (this.eventListeners.has(eventType)) {
      const listeners = this.eventListeners.get(eventType);
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  /**
   * 觸發事件
   * @private
   * @param {string} eventType - 事件類型
   * @param {Object} data - 事件數據
   */
  _emitEvent(eventType, data) {
    if (this.eventListeners.has(eventType)) {
      this.eventListeners.get(eventType).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`事件處理器錯誤 (${eventType}):`, error);
        }
      });
    }
  }

  /**
   * 從元素創建書籤對象
   * @private
   * @param {Element} element - 目標元素
   * @returns {Object} 書籤對象
   */
  _createBookmarkFromElement(element) {
    const id = this._generateBookmarkId(element);
    const currentChapter = this.getCurrentChapter();
    
    let title = '';
    let type = '';
    let content = '';

    if (element.classList.contains('question')) {
      type = 'question';
      title = element.querySelector('.question-text')?.textContent?.trim() || '';
      content = title;
    } else if (element.classList.contains('answer')) {
      type = 'answer';
      title = element.querySelector('.answer-text')?.textContent?.trim() || '';
      content = title;
    } else {
      type = 'content';
      title = element.textContent?.trim() || '';
      content = title;
    }

    // 限制標題長度
    if (title.length > 100) {
      title = title.substring(0, 100) + '...';
    }

    return {
      id,
      title,
      type,
      content: content.substring(0, 500), // 限制內容長度
      chapter: {
        id: currentChapter.id,
        title: currentChapter.title,
        filename: currentChapter.filename,
      },
      url: this._generateBookmarkUrl(element),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  /**
   * 生成書籤 ID
   * @private
   * @param {Element} element - 目標元素
   * @returns {string} 書籤 ID
   */
  _generateBookmarkId(element) {
    // 確保元素有 ID
    if (!element.id) {
      element.id = this._generateElementId(element);
    }
    
    const currentChapter = this.getCurrentChapter();
    return `${currentChapter.id}_${element.id}`;
  }

  /**
   * 生成元素 ID
   * @private
   * @param {Element} element - 目標元素
   * @returns {string} 元素 ID
   */
  _generateElementId(element) {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    
    if (element.classList.contains('question')) {
      return `question_${timestamp}_${random}`;
    } else if (element.classList.contains('answer')) {
      return `answer_${timestamp}_${random}`;
    } else {
      return `content_${timestamp}_${random}`;
    }
  }

  /**
   * 生成書籤 URL
   * @private
   * @param {Element} element - 目標元素
   * @returns {string} 書籤 URL
   */
  _generateBookmarkUrl(element) {
    const baseUrl = window.location.origin + window.location.pathname;
    const elementId = element.id;
    return `${baseUrl}#${elementId}`;
  }

  /**
   * 獲取當前章節信息
   * @private
   * @returns {Object} 章節信息
   */
  getCurrentChapter() {
    const filename = PageUtils.getCurrentFilename();
    
    if (PageUtils.isIndexPage()) {
      return {
        title: I18nService.getText('navigation.homepage', null, '首頁'),
        id: 'homepage',
        filename,
        isHomepage: true,
      };
    }

    // 從頁面標題獲取章節名稱
    let title = document.title;
    if (title.includes(' - ')) {
      title = title.split(' - ')[0];
    }

    return {
      title,
      id: filename.replace(/\.html$/, '').replace(/_trad$/, ''),
      filename,
      isHomepage: false,
    };
  }

  /**
   * 添加書籤視覺標識
   * @private
   * @param {Element} element - 目標元素
   */
  _addBookmarkVisualIndicator(element) {
    if (!element.classList.contains('bookmarked')) {
      element.classList.add('bookmarked');
      
      // 添加可點擊的書籤標記
      if (!element.querySelector('.bookmark-indicator')) {
        const indicator = document.createElement('span');
        indicator.className = 'bookmark-indicator';
        indicator.textContent = '🔖';
        indicator.title = I18nService.getText('bookmark.removeBookmark', null, '點擊移除書籤');
        
        // 添加點擊事件
        indicator.addEventListener('click', (e) => {
          e.stopPropagation();
          this.removeBookmark(this._generateBookmarkId(element));
        });
        
        element.appendChild(indicator);
      }
    }
  }

  /**
   * 移除書籤視覺標識
   * @private
   * @param {string} bookmarkId - 書籤 ID
   */
  _removeBookmarkVisualIndicator(bookmarkId) {
    const element = this._findElementByBookmarkId(bookmarkId);
    if (element) {
      element.classList.remove('bookmarked');
      
      const indicator = element.querySelector('.bookmark-indicator');
      if (indicator) {
        element.removeChild(indicator);
      }
    }
  }

  /**
   * 移除所有書籤視覺標識
   * @private
   */
  _removeAllBookmarkVisualIndicators() {
    const bookmarkedElements = document.querySelectorAll('.bookmarked');
    bookmarkedElements.forEach(element => {
      element.classList.remove('bookmarked');
      
      const indicator = element.querySelector('.bookmark-indicator');
      if (indicator) {
        element.removeChild(indicator);
      }
    });
  }

  /**
   * 根據書籤 ID 查找元素
   * @private
   * @param {string} bookmarkId - 書籤 ID
   * @returns {Element|null} 找到的元素
   */
  _findElementByBookmarkId(bookmarkId) {
    const elementId = bookmarkId.split('_').slice(1).join('_');
    return document.getElementById(elementId);
  }
}

// 創建全域書籤服務實例
export const bookmarkService = new BookmarkService();
