/**
 * @fileoverview 應用程式配置常數
 * @author Assistant
 * @version 1.0.0
 */

/**
 * 應用程式配置常數
 * @namespace CONFIG
 */
export const CONFIG = {
  /** 搜索功能配置 */
  SEARCH: {
    /** 每頁結果數量 */
    RESULTS_PER_PAGE: 20,
    /** 最小搜索字符數 */
    MIN_SEARCH_LENGTH: 2,
    /** 搜索延遲時間 (ms) */
    SEARCH_DELAY: 300,
  },

  /** UI 配置 */
  UI: {
    /** 動畫持續時間 (ms) */
    ANIMATION_DURATION: 300,
    /** Toast 顯示時間 (ms) */
    TOAST_DURATION: 3000,
    /** 滾動節流時間 (ms) */
    SCROLL_THROTTLE: 100,
  },

  /** 本地儲存鍵值 */
  STORAGE_KEYS: {
    /** 深色模式 */
    DARK_MODE: 'darkMode',
    /** 書籤 - 簡體 */
    BOOKMARKS_SIMPLIFIED: 'ebook-bookmarks-simplified',
    /** 書籤 - 繁體 */
    BOOKMARKS_TRADITIONAL: 'ebook-bookmarks-traditional',
    /** 書籤遷移標記 */
    BOOKMARKS_MIGRATED: 'bookmarks-migrated',
    /** 字型大小 */
    FONT_SIZE: 'fontSize',
    /** 行距 */
    LINE_HEIGHT: 'lineHeight',
  },

  /** 文件名稱模式 */
  FILE_PATTERNS: {
    /** 首頁文件 */
    INDEX_FILES: ['index.html', 'index_trad.html'],
    /** 繁體文件後綴 */
    TRADITIONAL_SUFFIX: '_trad.html',
    /** 搜索索引文件 */
    SEARCH_INDEX: {
      SIMPLIFIED: 'search_index.json',
      TRADITIONAL: 'search_index_trad.json',
    },
  },

  /** CSS 選擇器 */
  SELECTORS: {
    /** 主要容器 */
    CONTAINERS: {
      SEARCH: '#search-container',
      FLOATING_TOC: '#floating-toc',
      READING_TOOLBAR: '.reading-toolbar',
      ACTION_BUTTONS: '.action-buttons',
    },
    /** 按鈕 */
    BUTTONS: {
      SEARCH_ACTIVATE: '#search-activate-btn',
      THEME_LIGHT: '[data-action="theme-light"]',
      THEME_DARK: '[data-action="theme-dark"]',
    },
    /** 輸入框 */
    INPUTS: {
      SEARCH: '#search-input',
    },
  },

  /** 事件類型 */
  EVENTS: {
    /** DOM 載入完成 */
    DOM_CONTENT_LOADED: 'DOMContentLoaded',
    /** 滾動 */
    SCROLL: 'scroll',
    /** 點擊 */
    CLICK: 'click',
    /** 輸入 */
    INPUT: 'input',
    /** 按鍵 */
    KEYDOWN: 'keydown',
    /** 視窗大小改變 */
    RESIZE: 'resize',
  },
};

/**
 * CSS 類名常數
 * @namespace CSS_CLASSES
 */
export const CSS_CLASSES = {
  /** 狀態類 */
  STATE: {
    ACTIVE: 'active',
    HIDDEN: 'hidden',
    VISIBLE: 'visible',
    COLLAPSED: 'collapsed',
    EXPANDED: 'expanded',
    DISABLED: 'disabled',
    LOADING: 'loading',
  },

  /** 主題類 */
  THEME: {
    DARK_MODE: 'dark-mode',
    LIGHT_MODE: 'light-mode',
  },

  /** 組件類 */
  COMPONENTS: {
    TOC_ITEM: 'toc-item',
    BOOKMARK_ITEM: 'bookmark-item',
    SEARCH_RESULT: 'search-result-item',
    ACTION_BTN: 'action-btn',
    FLOATING_TOC: 'floating-toc',
    READING_TOOLBAR: 'reading-toolbar',
  },
};

/**
 * API 端點配置
 * @namespace API_ENDPOINTS
 */
export const API_ENDPOINTS = {
  /** 搜索相關 */
  SEARCH: {
    /** 獲取搜索索引 */
    INDEX: (isTraditional) => 
      isTraditional ? CONFIG.FILE_PATTERNS.SEARCH_INDEX.TRADITIONAL 
                    : CONFIG.FILE_PATTERNS.SEARCH_INDEX.SIMPLIFIED,
  },
};

/**
 * 錯誤訊息常數
 * @namespace ERROR_MESSAGES
 */
export const ERROR_MESSAGES = {
  /** 搜索相關錯誤 */
  SEARCH: {
    NETWORK_ERROR: 'SEARCH_NETWORK_ERROR',
    LOADING_FAILED: 'SEARCH_LOADING_FAILED',
    INDEX_NOT_FOUND: 'SEARCH_INDEX_NOT_FOUND',
  },
  
  /** 書籤相關錯誤 */
  BOOKMARK: {
    SAVE_FAILED: 'BOOKMARK_SAVE_FAILED',
    LOAD_FAILED: 'BOOKMARK_LOAD_FAILED',
    MIGRATION_FAILED: 'BOOKMARK_MIGRATION_FAILED',
  },
};
