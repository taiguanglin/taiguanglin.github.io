/**
 * @fileoverview 本地儲存工具函數
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG } from '../constants/config.js';

/**
 * 本地儲存工具類
 * @class StorageUtils
 */
export class StorageUtils {
  /**
   * 設置 localStorage 項目
   * @param {string} key - 鍵名
   * @param {any} value - 值
   * @returns {boolean} 是否設置成功
   */
  static setItem(key, value) {
    try {
      const serializedValue = JSON.stringify(value);
      localStorage.setItem(key, serializedValue);
      return true;
    } catch (error) {
      console.error('LocalStorage setItem failed:', error);
      return false;
    }
  }

  /**
   * 獲取 localStorage 項目
   * @param {string} key - 鍵名
   * @param {any} [defaultValue=null] - 預設值
   * @returns {any} 儲存的值或預設值
   */
  static getItem(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      if (item === null) {
        return defaultValue;
      }
      return JSON.parse(item);
    } catch (error) {
      console.error('LocalStorage getItem failed:', error);
      return defaultValue;
    }
  }

  /**
   * 移除 localStorage 項目
   * @param {string} key - 鍵名
   * @returns {boolean} 是否移除成功
   */
  static removeItem(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      console.error('LocalStorage removeItem failed:', error);
      return false;
    }
  }

  /**
   * 清空 localStorage
   * @returns {boolean} 是否清空成功
   */
  static clear() {
    try {
      localStorage.clear();
      return true;
    } catch (error) {
      console.error('LocalStorage clear failed:', error);
      return false;
    }
  }

  /**
   * 檢查是否支援 localStorage
   * @returns {boolean} 是否支援
   */
  static isSupported() {
    try {
      const testKey = '__localStorage_test__';
      localStorage.setItem(testKey, 'test');
      localStorage.removeItem(testKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * 獲取所有鍵名
   * @returns {string[]} 鍵名陣列
   */
  static getAllKeys() {
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        keys.push(key);
      }
    }
    return keys;
  }

  /**
   * 獲取儲存使用量（字節）
   * @returns {number} 使用量
   */
  static getUsage() {
    let total = 0;
    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        total += key.length + (localStorage[key]?.length || 0);
      }
    }
    return total;
  }

  /**
   * 獲取剩餘儲存空間（估算）
   * @returns {number} 剩餘空間（字節）
   */
  static getRemainingSpace() {
    const maxSize = 5 * 1024 * 1024; // 假設 5MB 上限
    return maxSize - this.getUsage();
  }

  /**
   * 設置 sessionStorage 項目
   * @param {string} key - 鍵名
   * @param {any} value - 值
   * @returns {boolean} 是否設置成功
   */
  static setSessionItem(key, value) {
    try {
      const serializedValue = JSON.stringify(value);
      sessionStorage.setItem(key, serializedValue);
      return true;
    } catch (error) {
      console.error('SessionStorage setItem failed:', error);
      return false;
    }
  }

  /**
   * 獲取 sessionStorage 項目
   * @param {string} key - 鍵名
   * @param {any} [defaultValue=null] - 預設值
   * @returns {any} 儲存的值或預設值
   */
  static getSessionItem(key, defaultValue = null) {
    try {
      const item = sessionStorage.getItem(key);
      if (item === null) {
        return defaultValue;
      }
      return JSON.parse(item);
    } catch (error) {
      console.error('SessionStorage getItem failed:', error);
      return defaultValue;
    }
  }

  /**
   * 移除 sessionStorage 項目
   * @param {string} key - 鍵名
   * @returns {boolean} 是否移除成功
   */
  static removeSessionItem(key) {
    try {
      sessionStorage.removeItem(key);
      return true;
    } catch (error) {
      console.error('SessionStorage removeItem failed:', error);
      return false;
    }
  }

  /**
   * 清空 sessionStorage
   * @returns {boolean} 是否清空成功
   */
  static clearSession() {
    try {
      sessionStorage.clear();
      return true;
    } catch (error) {
      console.error('SessionStorage clear failed:', error);
      return false;
    }
  }
}

/**
 * 書籤儲存管理器
 * @class BookmarkStorage
 */
export class BookmarkStorage extends StorageUtils {
  /**
   * 獲取書籤儲存鍵名
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {string} 儲存鍵名
   */
  static getStorageKey(isTraditional) {
    return isTraditional 
      ? CONFIG.STORAGE_KEYS.BOOKMARKS_TRADITIONAL
      : CONFIG.STORAGE_KEYS.BOOKMARKS_SIMPLIFIED;
  }

  /**
   * 獲取書籤
   * @param {boolean} isTraditional - 是否為繁體版
   * @param {string} [chapterId] - 章節 ID（可選）
   * @returns {Array} 書籤陣列
   */
  static getBookmarks(isTraditional, chapterId = null) {
    const storageKey = this.getStorageKey(isTraditional);
    const allBookmarks = this.getItem(storageKey, []);
    
    if (chapterId) {
      return allBookmarks.filter(bookmark => 
        bookmark.chapter && bookmark.chapter.id === chapterId
      );
    }
    
    return allBookmarks;
  }

  /**
   * 儲存書籤
   * @param {Array} bookmarks - 書籤陣列
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {boolean} 是否儲存成功
   */
  static saveBookmarks(bookmarks, isTraditional) {
    const storageKey = this.getStorageKey(isTraditional);
    return this.setItem(storageKey, bookmarks);
  }

  /**
   * 添加書籤
   * @param {Object} bookmark - 書籤對象
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {boolean} 是否添加成功
   */
  static addBookmark(bookmark, isTraditional) {
    const bookmarks = this.getBookmarks(isTraditional);
    
    // 檢查是否已存在
    const exists = bookmarks.some(item => item.id === bookmark.id);
    if (exists) {
      return false;
    }
    
    bookmarks.push(bookmark);
    return this.saveBookmarks(bookmarks, isTraditional);
  }

  /**
   * 移除書籤
   * @param {string} bookmarkId - 書籤 ID
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {boolean} 是否移除成功
   */
  static removeBookmark(bookmarkId, isTraditional) {
    const bookmarks = this.getBookmarks(isTraditional);
    const filteredBookmarks = bookmarks.filter(bookmark => bookmark.id !== bookmarkId);
    
    if (filteredBookmarks.length === bookmarks.length) {
      return false; // 沒有找到要移除的書籤
    }
    
    return this.saveBookmarks(filteredBookmarks, isTraditional);
  }

  /**
   * 更新書籤
   * @param {string} bookmarkId - 書籤 ID
   * @param {Object} updates - 更新內容
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {boolean} 是否更新成功
   */
  static updateBookmark(bookmarkId, updates, isTraditional) {
    const bookmarks = this.getBookmarks(isTraditional);
    const bookmarkIndex = bookmarks.findIndex(bookmark => bookmark.id === bookmarkId);
    
    if (bookmarkIndex === -1) {
      return false; // 沒有找到要更新的書籤
    }
    
    bookmarks[bookmarkIndex] = { ...bookmarks[bookmarkIndex], ...updates };
    return this.saveBookmarks(bookmarks, isTraditional);
  }

  /**
   * 清空指定章節的書籤
   * @param {string} chapterId - 章節 ID
   * @param {boolean} isTraditional - 是否為繁體版
   * @returns {boolean} 是否清空成功
   */
  static clearChapterBookmarks(chapterId, isTraditional) {
    const bookmarks = this.getBookmarks(isTraditional);
    const filteredBookmarks = bookmarks.filter(bookmark => 
      !bookmark.chapter || bookmark.chapter.id !== chapterId
    );
    
    return this.saveBookmarks(filteredBookmarks, isTraditional);
  }

  /**
   * 遷移舊版書籤
   * @returns {boolean} 是否遷移成功
   */
  static migrateOldBookmarks() {
    // 檢查是否已完成遷移
    if (this.getItem(CONFIG.STORAGE_KEYS.BOOKMARKS_MIGRATED)) {
      return true;
    }

    try {
      const oldBookmarks = this.getItem('ebook-bookmarks');
      if (!oldBookmarks || !Array.isArray(oldBookmarks)) {
        this.setItem(CONFIG.STORAGE_KEYS.BOOKMARKS_MIGRATED, true);
        return true;
      }

      const simplifiedBookmarks = [];
      const traditionalBookmarks = [];

      oldBookmarks.forEach(bookmark => {
        if (bookmark.chapterFilename && bookmark.chapterFilename.includes('_trad.html')) {
          traditionalBookmarks.push(bookmark);
        } else {
          simplifiedBookmarks.push(bookmark);
        }
      });

      // 儲存分離後的書籤
      this.saveBookmarks(simplifiedBookmarks, false);
      this.saveBookmarks(traditionalBookmarks, true);

      // 移除舊書籤
      this.removeItem('ebook-bookmarks');
      this.setItem(CONFIG.STORAGE_KEYS.BOOKMARKS_MIGRATED, true);

      console.log(`書籤遷移完成: 簡體 ${simplifiedBookmarks.length} 個, 繁體 ${traditionalBookmarks.length} 個`);
      return true;

    } catch (error) {
      console.error('書籤遷移失敗:', error);
      this.setItem(CONFIG.STORAGE_KEYS.BOOKMARKS_MIGRATED, true);
      return false;
    }
  }
}

/**
 * 設置儲存管理器
 * @class SettingsStorage
 */
export class SettingsStorage extends StorageUtils {
  /**
   * 獲取字型大小
   * @returns {number} 字型大小
   */
  static getFontSize() {
    return this.getItem(CONFIG.STORAGE_KEYS.FONT_SIZE, 16);
  }

  /**
   * 設置字型大小
   * @param {number} size - 字型大小
   * @returns {boolean} 是否設置成功
   */
  static setFontSize(size) {
    return this.setItem(CONFIG.STORAGE_KEYS.FONT_SIZE, size);
  }

  /**
   * 獲取行距
   * @returns {number} 行距
   */
  static getLineHeight() {
    return this.getItem(CONFIG.STORAGE_KEYS.LINE_HEIGHT, 1.6);
  }

  /**
   * 設置行距
   * @param {number} height - 行距
   * @returns {boolean} 是否設置成功
   */
  static setLineHeight(height) {
    return this.setItem(CONFIG.STORAGE_KEYS.LINE_HEIGHT, height);
  }

  /**
   * 獲取深色模式狀態
   * @returns {boolean} 是否為深色模式
   */
  static getDarkMode() {
    return this.getItem(CONFIG.STORAGE_KEYS.DARK_MODE, false);
  }

  /**
   * 設置深色模式
   * @param {boolean} enabled - 是否啟用深色模式
   * @returns {boolean} 是否設置成功
   */
  static setDarkMode(enabled) {
    return this.setItem(CONFIG.STORAGE_KEYS.DARK_MODE, enabled);
  }

  /**
   * 重置所有設置
   * @returns {boolean} 是否重置成功
   */
  static resetSettings() {
    const keys = [
      CONFIG.STORAGE_KEYS.FONT_SIZE,
      CONFIG.STORAGE_KEYS.LINE_HEIGHT,
      CONFIG.STORAGE_KEYS.DARK_MODE,
    ];

    let success = true;
    keys.forEach(key => {
      if (!this.removeItem(key)) {
        success = false;
      }
    });

    return success;
  }
}
