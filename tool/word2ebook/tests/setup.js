/**
 * @fileoverview Jest 測試環境設置
 * @author Assistant
 * @version 1.0.0
 */

// 擴展 Jest 匹配器
import '@testing-library/jest-dom';

// 全域變數設置
global.console = {
  ...console,
  // 在測試中抑制某些日誌輸出
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

// 設置 JSDOM 環境
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost/',
    origin: 'http://localhost',
    pathname: '/index.html',
    search: '',
    hash: '',
    assign: jest.fn(),
    replace: jest.fn(),
    reload: jest.fn(),
  },
  writable: true,
});

Object.defineProperty(window, 'history', {
  value: {
    pushState: jest.fn(),
    replaceState: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    go: jest.fn(),
    length: 1,
    state: null,
  },
  writable: true,
});

// 模擬 localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// 模擬 sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};

Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
  writable: true,
});

// 模擬 fetch API
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(''),
  })
);

// 模擬 IntersectionObserver
global.IntersectionObserver = jest.fn(function(callback, options) {
  this.observe = jest.fn();
  this.unobserve = jest.fn();
  this.disconnect = jest.fn();
});

// 模擬 ResizeObserver
global.ResizeObserver = jest.fn(function(callback) {
  this.observe = jest.fn();
  this.unobserve = jest.fn();
  this.disconnect = jest.fn();
});

// 模擬 matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// 模擬 CSS.supports
Object.defineProperty(window.CSS, 'supports', {
  value: jest.fn(() => true),
});

// 模擬 requestAnimationFrame
global.requestAnimationFrame = jest.fn(cb => setTimeout(cb, 16));
global.cancelAnimationFrame = jest.fn(id => clearTimeout(id));

// 模擬 scrollTo
window.scrollTo = jest.fn();

// 模擬 scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// 模擬 getBoundingClientRect
Element.prototype.getBoundingClientRect = jest.fn(() => ({
  top: 0,
  left: 0,
  bottom: 0,
  right: 0,
  width: 0,
  height: 0,
  x: 0,
  y: 0,
}));

// 模擬 getComputedStyle
window.getComputedStyle = jest.fn((element) => {
  const styles = element?._testStyles || {};
  return {
    getPropertyValue: jest.fn(),
    display: styles.display || element?.style?.display || 'block',
    visibility: styles.visibility || element?.style?.visibility || 'visible',
    opacity: styles.opacity || element?.style?.opacity || '1',
    ...styles,
  };
});

// 設置測試用的 I18N 數據
window.I18N_TEXT = {
  search: {
    loading: {
      simplified: '正在加载搜索功能，请稍候...',
      traditional: '正在載入搜尋功能，請稍候...'
    },
    indexReady: {
      simplified: '搜索准备就绪 (共{count}条记录)',
      traditional: '搜尋準備就緒 (共{count}條記錄)'
    },
    minCharWarning: {
      simplified: '请输入至少2个字符进行搜索',
      traditional: '請輸入至少2個字元進行搜尋'
    },
    resultTypes: {
      heading: {
        simplified: '标题',
        traditional: '標題'
      },
      question: {
        simplified: '问题',
        traditional: '問題'
      },
      answer: {
        simplified: '回答',
        traditional: '回答'
      },
      content: {
        simplified: '内容',
        traditional: '內容'
      }
    }
  },
  bookmark: {
    empty: {
      simplified: '尚无书签',
      traditional: '尚無書籤'
    },
    removeBookmark: {
      simplified: '点击移除书签',
      traditional: '點擊移除書籤'
    },
    bookmarkDeleted: {
      simplified: '书签已删除',
      traditional: '書籤已刪除'
    }
  },
  navigation: {
    homepage: {
      simplified: '首页',
      traditional: '首頁'
    },
    bookmarks: {
      simplified: '书签',
      traditional: '書籤'
    }
  },
  ui: {
    home: {
      simplified: '回首页',
      traditional: '回首頁'
    },
    settings: {
      simplified: '设置',
      traditional: '設置'
    }
  }
};

// 測試工具函數
global.createMockElement = (tagName = 'div', options = {}) => {
  const element = document.createElement(tagName);
  
  if (options.id) {
    element.id = options.id;
  }
  
  if (options.className) {
    element.className = options.className;
  }
  
  if (options.innerHTML) {
    element.innerHTML = options.innerHTML;
  }
  
  if (options.attributes) {
    Object.entries(options.attributes).forEach(([key, value]) => {
      element.setAttribute(key, value);
    });
  }
  
  return element;
};

global.createMockEvent = (type, properties = {}) => {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(event, properties);
  return event;
};

// 清理函數
afterEach(() => {
  // 清除所有模擬調用記錄
  jest.clearAllMocks();
  
  // 重置 localStorage 和 sessionStorage
  localStorageMock.getItem.mockClear();
  localStorageMock.setItem.mockClear();
  localStorageMock.removeItem.mockClear();
  localStorageMock.clear.mockClear();
  
  sessionStorageMock.getItem.mockClear();
  sessionStorageMock.setItem.mockClear();
  sessionStorageMock.removeItem.mockClear();
  sessionStorageMock.clear.mockClear();
  
  // 清除 fetch 模擬
  fetch.mockClear();
  
  // 清除 DOM
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  
  // 重置 window.location
  delete window.location;
  window.location = {
    href: 'http://localhost/',
    origin: 'http://localhost',
    pathname: '/index.html',
    search: '',
    hash: '',
    assign: jest.fn(),
    replace: jest.fn(),
    reload: jest.fn(),
  };
});

// 全域錯誤處理
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// 設置更長的測試超時時間用於異步操作
jest.setTimeout(10000);
