/**
 * @fileoverview 主應用程式入口
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG, CSS_CLASSES } from './constants/config.js';
import { DOMUtils } from './utils/dom.js';
import { PageUtils } from './utils/page.js';
import { SettingsStorage } from './utils/storage.js';
import { I18nService } from './services/i18n.js';
import { searchService } from './services/search.js';
import { bookmarkService } from './services/bookmark.js';
import { SearchComponent } from './components/search-component.js';

/**
 * 主應用程式類
 * @class App
 */
class App {
  constructor() {
    this.isInitialized = false;
    this.components = new Map();
    this.globalEventListeners = [];
    
    this._bindMethods();
  }

  /**
   * 初始化應用程式
   * @returns {Promise<boolean>} 是否初始化成功
   */
  async init() {
    if (this.isInitialized) {
      return true;
    }

    try {
      console.log('🚀 Word2EBook App 初始化開始...');
      
      // 1. 基礎設置
      this._setupBasics();
      
      // 2. 檢查必要條件
      if (!this._checkRequirements()) {
        throw new Error('應用程式初始化條件不足');
      }

      // 3. 初始化主題
      this._initTheme();
      
      // 4. 初始化 i18n
      this._initI18n();
      
      // 5. 初始化服務
      await this._initServices();
      
      // 6. 初始化組件
      this._initComponents();
      
      // 7. 綁定全域事件
      this._bindGlobalEvents();
      
      // 8. 處理初始錨點
      this._handleInitialAnchor();
      
      // 9. 完成初始化
      this.isInitialized = true;
      
      console.log('✅ Word2EBook App 初始化完成');
      this._emitEvent('app:initialized');
      
      return true;

    } catch (error) {
      console.error('❌ Word2EBook App 初始化失敗:', error);
      this._emitEvent('app:initializationFailed', { error });
      return false;
    }
  }

  /**
   * 銷毀應用程式
   */
  destroy() {
    if (!this.isInitialized) {
      return;
    }

    try {
      console.log('🧹 Word2EBook App 銷毀開始...');
      
      // 銷毀組件
      this.components.forEach(component => {
        if (component && typeof component.destroy === 'function') {
          component.destroy();
        }
      });
      this.components.clear();
      
      // 移除全域事件監聽器
      this._unbindGlobalEvents();
      
      this.isInitialized = false;
      
      console.log('✅ Word2EBook App 銷毀完成');
      this._emitEvent('app:destroyed');

    } catch (error) {
      console.error('❌ Word2EBook App 銷毀失敗:', error);
    }
  }

  /**
   * 獲取組件
   * @param {string} name - 組件名稱
   * @returns {Object|null} 組件實例
   */
  getComponent(name) {
    return this.components.get(name) || null;
  }

  /**
   * 綁定方法到當前實例
   * @private
   */
  _bindMethods() {
    this.handleDocumentClick = this.handleDocumentClick.bind(this);
    this.handleWindowScroll = this.handleWindowScroll.bind(this);
    this.handleWindowResize = this.handleWindowResize.bind(this);
    this.handleKeyboardShortcuts = this.handleKeyboardShortcuts.bind(this);
    this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
  }

  /**
   * 基礎設置
   * @private
   */
  _setupBasics() {
    // 設置 body 類名以便 CSS 識別
    DOMUtils.addClass(document.body, 'word2ebook-app');
    
    // 設置頁面類型
    if (PageUtils.isIndexPage()) {
      DOMUtils.addClass(document.body, 'page-index');
    } else {
      DOMUtils.addClass(document.body, 'page-chapter');
    }
    
    // 設置語言類型
    if (PageUtils.isTraditionalChinesePage()) {
      DOMUtils.addClass(document.body, 'lang-traditional');
    } else {
      DOMUtils.addClass(document.body, 'lang-simplified');
    }
  }

  /**
   * 檢查必要條件
   * @private
   * @returns {boolean} 是否滿足條件
   */
  _checkRequirements() {
    // 檢查瀏覽器支援
    if (!window.localStorage) {
      console.error('瀏覽器不支援 localStorage');
      return false;
    }

    if (!window.fetch) {
      console.error('瀏覽器不支援 fetch API');
      return false;
    }

    if (!window.URLSearchParams) {
      console.error('瀏覽器不支援 URLSearchParams');
      return false;
    }

    return true;
  }

  /**
   * 初始化主題
   * @private
   */
  _initTheme() {
    const isDarkMode = SettingsStorage.getDarkMode();
    
    if (isDarkMode) {
      DOMUtils.addClass(document.body, CSS_CLASSES.THEME.DARK_MODE);
    } else {
      DOMUtils.removeClass(document.body, CSS_CLASSES.THEME.DARK_MODE);
    }
    
    console.log(`🎨 主題初始化完成 (${isDarkMode ? '深色' : '淺色'}模式)`);
  }

  /**
   * 初始化國際化
   * @private
   */
  _initI18n() {
    // 檢查 i18n 資源是否已載入
    if (!I18nService.isLoaded()) {
      console.warn('⚠️ I18n 資源尚未載入，將使用預設文字');
    } else {
      console.log('🌍 國際化初始化完成');
    }
  }

  /**
   * 初始化服務
   * @private
   */
  async _initServices() {
    console.log('🔧 服務初始化開始...');
    
    // 書籤服務（同步初始化）
    if (bookmarkService.isInitialized) {
      console.log('📚 書籤服務已初始化');
    }
    
    // 搜索服務（僅在首頁異步初始化）
    if (PageUtils.isIndexPage()) {
      try {
        // 搜索服務由搜索組件管理，這裡不需要初始化
        console.log('🔍 搜索服務將由搜索組件管理');
      } catch (error) {
        console.warn('🔍 搜索服務初始化警告:', error.message);
      }
    }
    
    console.log('✅ 服務初始化完成');
  }

  /**
   * 初始化組件
   * @private
   */
  _initComponents() {
    console.log('🧩 組件初始化開始...');
    
    try {
      // 搜索組件（僅在首頁）
      if (PageUtils.isIndexPage()) {
        const searchContainer = DOMUtils.querySelector('.search-activation, #search-container');
        if (searchContainer) {
          const searchComponent = new SearchComponent(searchContainer, {
            autoActivate: false,
          });
          this.components.set('search', searchComponent);
          console.log('🔍 搜索組件初始化完成');
        }
      }
      
      // TODO: 初始化其他組件
      // - TOC 組件
      // - 書籤組件  
      // - 閱讀工具欄組件
      // - 操作按鈕組件
      
      console.log('✅ 組件初始化完成');

    } catch (error) {
      console.error('❌ 組件初始化失敗:', error);
      throw error;
    }
  }

  /**
   * 綁定全域事件
   * @private
   */
  _bindGlobalEvents() {
    // 文件點擊事件（用於關閉下拉選單等）
    this._addEventListener(document, CONFIG.EVENTS.CLICK, this.handleDocumentClick);
    
    // 視窗滾動事件（節流）
    const throttledScrollHandler = DOMUtils.throttle(this.handleWindowScroll, CONFIG.UI.SCROLL_THROTTLE);
    this._addEventListener(window, CONFIG.EVENTS.SCROLL, throttledScrollHandler);
    
    // 視窗大小改變事件
    const throttledResizeHandler = DOMUtils.throttle(this.handleWindowResize, CONFIG.UI.SCROLL_THROTTLE);
    this._addEventListener(window, CONFIG.EVENTS.RESIZE, throttledResizeHandler);
    
    // 鍵盤快捷鍵
    this._addEventListener(document, CONFIG.EVENTS.KEYDOWN, this.handleKeyboardShortcuts);
    
    // 頁面可見性變化
    this._addEventListener(document, 'visibilitychange', this.handleVisibilityChange);
    
    console.log('🎯 全域事件綁定完成');
  }

  /**
   * 解綁全域事件
   * @private
   */
  _unbindGlobalEvents() {
    this.globalEventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler);
    });
    this.globalEventListeners = [];
  }

  /**
   * 添加事件監聽器（用於追蹤）
   * @private
   * @param {Element} element - 目標元素
   * @param {string} event - 事件名稱
   * @param {Function} handler - 事件處理器
   */
  _addEventListener(element, event, handler) {
    element.addEventListener(event, handler);
    this.globalEventListeners.push({ element, event, handler });
  }

  /**
   * 處理文件點擊事件
   * @param {Event} event - 事件對象
   */
  handleDocumentClick(event) {
    // 檢查是否點擊在側邊欄外部
    const isInsideSidebar = event.target.closest('.floating-toc') ||
                           event.target.closest('.reading-toolbar') ||
                           event.target.closest('.action-menu');
    
    if (!isInsideSidebar) {
      this._closeSidebars();
    }
  }

  /**
   * 處理視窗滾動事件
   * @param {Event} event - 事件對象
   */
  handleWindowScroll(event) {
    // 更新閱讀進度
    this._updateReadingProgress();
    
    // 更新當前章節
    this._updateCurrentSection();
    
    // 更新浮動控制項狀態
    this._updateFloatingControls();
  }

  /**
   * 處理視窗大小改變事件
   * @param {Event} event - 事件對象
   */
  handleWindowResize(event) {
    // 重新計算佈局
    this._recalculateLayout();
    
    // 更新響應式組件
    this._updateResponsiveComponents();
  }

  /**
   * 處理鍵盤快捷鍵
   * @param {Event} event - 事件對象
   */
  handleKeyboardShortcuts(event) {
    // Ctrl/Cmd + K: 開啟搜索
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
      event.preventDefault();
      const searchComponent = this.getComponent('search');
      if (searchComponent && PageUtils.isIndexPage()) {
        searchComponent.activate();
      }
    }
    
    // Escape: 關閉側邊欄
    if (event.key === 'Escape') {
      this._closeSidebars();
    }
    
    // F: 開啟搜索（在搜索輸入框獲得焦點時）
    if (event.key === 'f' && !event.ctrlKey && !event.metaKey) {
      const activeElement = document.activeElement;
      if (activeElement && activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
        const searchComponent = this.getComponent('search');
        if (searchComponent && PageUtils.isIndexPage()) {
          event.preventDefault();
          searchComponent.activate();
        }
      }
    }
  }

  /**
   * 處理頁面可見性變化
   * @param {Event} event - 事件對象
   */
  handleVisibilityChange(event) {
    if (document.hidden) {
      // 頁面隱藏時暫停不必要的操作
      console.log('📱 頁面已隱藏');
    } else {
      // 頁面顯示時恢復操作
      console.log('📱 頁面已顯示');
      this._refreshState();
    }
  }

  /**
   * 處理初始錨點
   * @private
   */
  _handleInitialAnchor() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      setTimeout(() => {
        const targetElement = document.querySelector(hash);
        if (targetElement) {
          DOMUtils.scrollToElement(targetElement);
        }
      }, 100);
    }
  }

  /**
   * 關閉側邊欄
   * @private
   */
  _closeSidebars() {
    // 關閉浮動目錄
    const floatingToc = DOMUtils.querySelector('.floating-toc.visible');
    if (floatingToc) {
      DOMUtils.removeClass(floatingToc, 'visible');
    }
    
    // 關閉操作選單
    const expandedMenu = DOMUtils.querySelector('.action-menu.expanded');
    if (expandedMenu) {
      DOMUtils.removeClass(expandedMenu, 'expanded');
      const menuBtn = DOMUtils.querySelector('.action-btn.menu-btn.expanded');
      if (menuBtn) {
        DOMUtils.removeClass(menuBtn, 'expanded');
      }
    }
    
    // 關閉閱讀工具欄
    const visibleToolbar = DOMUtils.querySelector('.reading-toolbar:not(.hidden)');
    if (visibleToolbar) {
      DOMUtils.addClass(visibleToolbar, 'hidden');
    }
  }

  /**
   * 更新閱讀進度
   * @private
   */
  _updateReadingProgress() {
    const progressBar = DOMUtils.querySelector('.reading-progress-bar');
    if (!progressBar) return;

    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
    
    progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
  }

  /**
   * 更新當前章節
   * @private
   */
  _updateCurrentSection() {
    // TODO: 實現當前章節高亮邏輯
  }

  /**
   * 更新浮動控制項
   * @private
   */
  _updateFloatingControls() {
    // TODO: 實現浮動控制項位置更新邏輯
  }

  /**
   * 重新計算佈局
   * @private
   */
  _recalculateLayout() {
    // TODO: 實現響應式佈局重新計算
  }

  /**
   * 更新響應式組件
   * @private
   */
  _updateResponsiveComponents() {
    // TODO: 通知組件視窗大小已改變
    this.components.forEach(component => {
      if (component && typeof component.handleResize === 'function') {
        component.handleResize();
      }
    });
  }

  /**
   * 刷新狀態
   * @private
   */
  _refreshState() {
    // 恢復書籤視覺狀態
    if (bookmarkService.isInitialized) {
      bookmarkService.restoreBookmarkVisualStates();
    }
    
    // 更新組件狀態
    this.components.forEach(component => {
      if (component && typeof component.refresh === 'function') {
        component.refresh();
      }
    });
  }

  /**
   * 觸發全域事件
   * @private
   * @param {string} eventType - 事件類型
   * @param {any} [data] - 事件數據
   */
  _emitEvent(eventType, data = null) {
    const customEvent = new CustomEvent(eventType, {
      detail: data,
      bubbles: true,
      cancelable: true,
    });
    
    document.dispatchEvent(customEvent);
  }

  /**
   * 獲取應用程式狀態
   * @returns {Object} 應用程式狀態
   */
  getState() {
    return {
      isInitialized: this.isInitialized,
      currentPage: PageUtils.getPathInfo(),
      componentsCount: this.components.size,
      eventListenersCount: this.globalEventListeners.length,
      components: Array.from(this.components.keys()),
    };
  }

  /**
   * 記錄調試信息
   * @param {string} message - 訊息
   * @param {any} [data] - 額外數據
   */
  debug(message, data = null) {
    if (window.location.hostname === 'localhost' || window.location.hostname.includes('dev')) {
      console.log(`[Word2EBook App] ${message}`, data);
    }
  }
}

// 創建全域應用程式實例
const app = new App();

// DOM 載入完成後初始化應用程式
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => app.init());
} else {
  // DOM 已經載入完成
  app.init();
}

// 導出應用程式實例（用於調試）
window.Word2EBookApp = app;

export default app;
