/**
 * @fileoverview DOM 操作工具函數
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG, CSS_CLASSES } from '../constants/config.js';

/**
 * DOM 操作工具類
 * @class DOMUtils
 */
export class DOMUtils {
  /**
   * 安全獲取元素
   * @param {string} selector - CSS 選擇器
   * @param {Element} [context=document] - 查找上下文
   * @returns {Element|null} 找到的元素或 null
   */
  static querySelector(selector, context = document) {
    try {
      return context.querySelector(selector);
    } catch (error) {
      console.warn(`Invalid selector: ${selector}`, error);
      return null;
    }
  }

  /**
   * 安全獲取多個元素
   * @param {string} selector - CSS 選擇器
   * @param {Element} [context=document] - 查找上下文
   * @returns {NodeList} 元素列表
   */
  static querySelectorAll(selector, context = document) {
    try {
      return context.querySelectorAll(selector);
    } catch (error) {
      console.warn(`Invalid selector: ${selector}`, error);
      return [];
    }
  }

  /**
   * 創建元素
   * @param {string} tagName - 標籤名
   * @param {Object} [options={}] - 選項
   * @param {string} [options.className] - CSS 類名
   * @param {string} [options.id] - 元素 ID
   * @param {string} [options.innerHTML] - 內部 HTML
   * @param {Object} [options.attributes] - 屬性對象
   * @param {Object} [options.dataset] - data-* 屬性
   * @returns {Element} 創建的元素
   */
  static createElement(tagName, options = {}) {
    const element = document.createElement(tagName);
    
    if (options.className) {
      element.className = options.className;
    }
    
    if (options.id) {
      element.id = options.id;
    }
    
    if (options.innerHTML) {
      element.innerHTML = options.innerHTML;
    }
    
    if (options.attributes) {
      Object.entries(options.attributes).forEach(([key, value]) => {
        element.setAttribute(key, value);
      });
    }
    
    if (options.dataset) {
      Object.entries(options.dataset).forEach(([key, value]) => {
        element.dataset[key] = value;
      });
    }
    
    return element;
  }

  /**
   * 添加類名
   * @param {Element} element - 目標元素
   * @param {...string} classNames - 要添加的類名
   */
  static addClass(element, ...classNames) {
    if (element && element.classList) {
      element.classList.add(...classNames);
    }
  }

  /**
   * 移除類名
   * @param {Element} element - 目標元素
   * @param {...string} classNames - 要移除的類名
   */
  static removeClass(element, ...classNames) {
    if (element && element.classList) {
      element.classList.remove(...classNames);
    }
  }

  /**
   * 切換類名
   * @param {Element} element - 目標元素
   * @param {string} className - 要切換的類名
   * @param {boolean} [force] - 強制添加或移除
   * @returns {boolean} 切換後是否包含該類名
   */
  static toggleClass(element, className, force) {
    if (element && element.classList) {
      return element.classList.toggle(className, force);
    }
    return false;
  }

  /**
   * 檢查是否包含類名
   * @param {Element} element - 目標元素
   * @param {string} className - 要檢查的類名
   * @returns {boolean} 是否包含類名
   */
  static hasClass(element, className) {
    return !!(element && element.classList && element.classList.contains(className));
  }

  /**
   * 顯示元素
   * @param {Element} element - 目標元素
   * @param {string} [display='block'] - 顯示方式
   */
  static show(element, display = 'block') {
    if (element) {
      element.style.display = display;
      this.removeClass(element, CSS_CLASSES.STATE.HIDDEN);
    }
  }

  /**
   * 隱藏元素
   * @param {Element} element - 目標元素
   */
  static hide(element) {
    if (element) {
      element.style.display = 'none';
      this.addClass(element, CSS_CLASSES.STATE.HIDDEN);
    }
  }

  /**
   * 切換元素顯示/隱藏
   * @param {Element} element - 目標元素
   * @param {string} [display='block'] - 顯示方式
   */
  static toggle(element, display = 'block') {
    if (element) {
      const isHidden = element.style.display === 'none' || 
                      this.hasClass(element, CSS_CLASSES.STATE.HIDDEN);
      if (isHidden) {
        this.show(element, display);
      } else {
        this.hide(element);
      }
    }
  }

  /**
   * 設置元素屬性
   * @param {Element} element - 目標元素
   * @param {Object} attributes - 屬性對象
   */
  static setAttributes(element, attributes) {
    if (element && attributes) {
      Object.entries(attributes).forEach(([key, value]) => {
        element.setAttribute(key, value);
      });
    }
  }

  /**
   * 移除元素屬性
   * @param {Element} element - 目標元素
   * @param {...string} attributeNames - 要移除的屬性名
   */
  static removeAttributes(element, ...attributeNames) {
    if (element) {
      attributeNames.forEach(name => {
        element.removeAttribute(name);
      });
    }
  }

  /**
   * 清空元素內容
   * @param {Element} element - 目標元素
   */
  static empty(element) {
    if (element) {
      element.innerHTML = '';
    }
  }

  /**
   * 移除元素
   * @param {Element} element - 要移除的元素
   */
  static remove(element) {
    if (element && element.parentNode) {
      element.parentNode.removeChild(element);
    }
  }

  /**
   * 在元素前插入
   * @param {Element} newElement - 新元素
   * @param {Element} referenceElement - 參考元素
   */
  static insertBefore(newElement, referenceElement) {
    if (newElement && referenceElement && referenceElement.parentNode) {
      referenceElement.parentNode.insertBefore(newElement, referenceElement);
    }
  }

  /**
   * 在元素後插入
   * @param {Element} newElement - 新元素
   * @param {Element} referenceElement - 參考元素
   */
  static insertAfter(newElement, referenceElement) {
    if (newElement && referenceElement && referenceElement.parentNode) {
      referenceElement.parentNode.insertBefore(newElement, referenceElement.nextSibling);
    }
  }

  /**
   * 檢查元素是否可見
   * @param {Element} element - 目標元素
   * @returns {boolean} 是否可見
   */
  static isVisible(element) {
    if (!element) return false;
    
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && 
           style.visibility !== 'hidden' && 
           style.opacity !== '0';
  }

  /**
   * 獲取元素位置信息
   * @param {Element} element - 目標元素
   * @returns {Object} 位置信息
   */
  static getPosition(element) {
    if (!element) return { 
      top: 0, 
      left: 0, 
      width: 0, 
      height: 0,
      viewportTop: 0,
      viewportLeft: 0,
    };
    
    const rect = element.getBoundingClientRect();
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
    
    return {
      top: rect.top + scrollTop,
      left: rect.left + scrollLeft,
      width: rect.width,
      height: rect.height,
      viewportTop: rect.top,
      viewportLeft: rect.left,
    };
  }

  /**
   * 平滑滾動到元素
   * @param {Element} element - 目標元素
   * @param {Object} [options={}] - 滾動選項
   * @param {string} [options.behavior='smooth'] - 滾動行為
   * @param {string} [options.block='start'] - 垂直對齊
   */
  static scrollToElement(element, options = {}) {
    if (element) {
      element.scrollIntoView({
        behavior: options.behavior || 'smooth',
        block: options.block || 'start',
        ...options,
      });
    }
  }

  /**
   * 節流函數
   * @param {Function} func - 要節流的函數
   * @param {number} delay - 延遲時間
   * @returns {Function} 節流後的函數
   */
  static throttle(func, delay) {
    let timeoutId;
    let lastExecTime = 0;
    
    return function (...args) {
      const currentTime = Date.now();
      
      if (currentTime - lastExecTime > delay) {
        func.apply(this, args);
        lastExecTime = currentTime;
      } else {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          func.apply(this, args);
          lastExecTime = Date.now();
        }, delay - (currentTime - lastExecTime));
      }
    };
  }

  /**
   * 防抖函數
   * @param {Function} func - 要防抖的函數
   * @param {number} delay - 延遲時間
   * @returns {Function} 防抖後的函數
   */
  static debounce(func, delay) {
    let timeoutId;
    
    return function (...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
  }
}
