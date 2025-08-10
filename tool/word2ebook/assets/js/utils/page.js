/**
 * @fileoverview 頁面相關工具函數
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG } from '../constants/config.js';

/**
 * 頁面工具類
 * @class PageUtils
 */
export class PageUtils {
  /**
   * 檢查是否為首頁
   * @returns {boolean} 是否為首頁
   */
  static isIndexPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return CONFIG.FILE_PATTERNS.INDEX_FILES.includes(filename);
  }

  /**
   * 檢查是否為繁體中文頁面
   * @returns {boolean} 是否為繁體中文頁面
   */
  static isTraditionalChinesePage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename.includes(CONFIG.FILE_PATTERNS.TRADITIONAL_SUFFIX);
  }

  /**
   * 獲取當前頁面語言
   * @returns {string} 語言代碼 ('zh-TW' | 'zh-CN')
   */
  static getCurrentLanguage() {
    return this.isTraditionalChinesePage() ? 'zh-TW' : 'zh-CN';
  }

  /**
   * 獲取搜索索引文件名
   * @returns {string} 搜索索引文件名
   */
  static getSearchIndexFile() {
    return this.isTraditionalChinesePage() 
      ? CONFIG.FILE_PATTERNS.SEARCH_INDEX.TRADITIONAL
      : CONFIG.FILE_PATTERNS.SEARCH_INDEX.SIMPLIFIED;
  }

  /**
   * 獲取當前文件名
   * @returns {string} 當前文件名
   */
  static getCurrentFilename() {
    const pathname = window.location.pathname;
    return pathname.split('/').pop() || 'index.html';
  }

  /**
   * 獲取當前路徑信息
   * @returns {Object} 路徑信息
   */
  static getPathInfo() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    const directory = pathname.substring(0, pathname.lastIndexOf('/') + 1);
    
    return {
      pathname,
      filename,
      directory,
      isIndex: this.isIndexPage(),
      isTraditional: this.isTraditionalChinesePage(),
      language: this.getCurrentLanguage(),
    };
  }

  /**
   * 獲取對應語言版本的 URL
   * @param {string} [targetLanguage] - 目標語言 ('zh-TW' | 'zh-CN')
   * @returns {string} 對應語言版本的 URL
   */
  static getLanguageUrl(targetLanguage) {
    const currentFilename = this.getCurrentFilename();
    const isCurrentTraditional = this.isTraditionalChinesePage();
    
    // 如果未指定目標語言，則切換到另一種語言
    if (!targetLanguage) {
      targetLanguage = isCurrentTraditional ? 'zh-CN' : 'zh-TW';
    }
    
    let targetFilename;
    if (targetLanguage === 'zh-TW' && !isCurrentTraditional) {
      // 簡體 -> 繁體
      if (currentFilename === 'index.html') {
        targetFilename = 'index_trad.html';
      } else {
        targetFilename = currentFilename.replace('.html', '_trad.html');
      }
    } else if (targetLanguage === 'zh-CN' && isCurrentTraditional) {
      // 繁體 -> 簡體
      if (currentFilename === 'index_trad.html') {
        targetFilename = 'index.html';
      } else {
        targetFilename = currentFilename.replace('_trad.html', '.html');
      }
    } else {
      // 同語言，不變
      targetFilename = currentFilename;
    }
    
    const currentPath = window.location.pathname;
    const directory = currentPath.substring(0, currentPath.lastIndexOf('/') + 1);
    
    return `${window.location.origin}${directory}${targetFilename}`;
  }

  /**
   * 導航到指定 URL
   * @param {string} url - 目標 URL
   * @param {boolean} [newTab=false] - 是否在新標籤頁打開
   */
  static navigateTo(url, newTab = false) {
    if (newTab) {
      window.open(url, '_blank');
    } else {
      window.location.href = url;
    }
  }

  /**
   * 重新載入當前頁面
   * @param {boolean} [force=false] - 是否強制重新載入
   */
  static reload(force = false) {
    window.location.reload(force);
  }

  /**
   * 獲取 URL 參數
   * @param {string} [paramName] - 參數名，如果不提供則返回所有參數
   * @returns {string|Object} 參數值或參數對象
   */
  static getUrlParams(paramName) {
    const params = new URLSearchParams(window.location.search);
    
    if (paramName) {
      return params.get(paramName);
    }
    
    const result = {};
    for (const [key, value] of params) {
      result[key] = value;
    }
    return result;
  }

  /**
   * 設置 URL 參數
   * @param {Object} params - 要設置的參數
   * @param {boolean} [replace=false] - 是否替換當前歷史記錄
   */
  static setUrlParams(params, replace = false) {
    const url = new URL(window.location);
    
    Object.entries(params).forEach(([key, value]) => {
      if (value === null || value === undefined) {
        url.searchParams.delete(key);
      } else {
        url.searchParams.set(key, value);
      }
    });
    
    if (replace) {
      window.history.replaceState({}, '', url);
    } else {
      window.history.pushState({}, '', url);
    }
  }

  /**
   * 獲取頁面滾動位置
   * @returns {Object} 滾動位置信息
   */
  static getScrollPosition() {
    return {
      x: window.pageXOffset || document.documentElement.scrollLeft,
      y: window.pageYOffset || document.documentElement.scrollTop,
    };
  }

  /**
   * 設置頁面滾動位置
   * @param {number} x - 水平滾動位置
   * @param {number} y - 垂直滾動位置
   * @param {boolean} [smooth=true] - 是否平滑滾動
   */
  static setScrollPosition(x, y, smooth = true) {
    if (smooth) {
      window.scrollTo({
        left: x,
        top: y,
        behavior: 'smooth',
      });
    } else {
      window.scrollTo(x, y);
    }
  }

  /**
   * 滾動到頂部
   * @param {boolean} [smooth=true] - 是否平滑滾動
   */
  static scrollToTop(smooth = true) {
    this.setScrollPosition(0, 0, smooth);
  }

  /**
   * 獲取視窗尺寸
   * @returns {Object} 視窗尺寸信息
   */
  static getViewportSize() {
    return {
      width: window.innerWidth || document.documentElement.clientWidth,
      height: window.innerHeight || document.documentElement.clientHeight,
    };
  }

  /**
   * 檢查是否為移動設備
   * @returns {boolean} 是否為移動設備
   */
  static isMobileDevice() {
    return /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  }

  /**
   * 檢查是否為觸控設備
   * @returns {boolean} 是否為觸控設備
   */
  static isTouchDevice() {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  }

  /**
   * 獲取頁面標題
   * @returns {string} 頁面標題
   */
  static getPageTitle() {
    return document.title;
  }

  /**
   * 設置頁面標題
   * @param {string} title - 新標題
   */
  static setPageTitle(title) {
    document.title = title;
  }

  /**
   * 添加到瀏覽器歷史記錄
   * @param {string} url - URL
   * @param {string} [title] - 標題
   * @param {Object} [state] - 狀態對象
   */
  static pushState(url, title, state = {}) {
    window.history.pushState(state, title, url);
    if (title) {
      this.setPageTitle(title);
    }
  }

  /**
   * 替換當前瀏覽器歷史記錄
   * @param {string} url - URL
   * @param {string} [title] - 標題
   * @param {Object} [state] - 狀態對象
   */
  static replaceState(url, title, state = {}) {
    window.history.replaceState(state, title, url);
    if (title) {
      this.setPageTitle(title);
    }
  }
}
