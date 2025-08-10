/**
 * @fileoverview 基礎組件類
 * @author Assistant
 * @version 1.0.0
 */

import { DOMUtils } from '../utils/dom.js';
import { CONFIG, CSS_CLASSES } from '../constants/config.js';

/**
 * 基礎組件類
 * @class BaseComponent
 */
export class BaseComponent {
  /**
   * 構造函數
   * @param {Element|string} container - 容器元素或選擇器
   * @param {Object} [options={}] - 組件選項
   */
  constructor(container, options = {}) {
    this.container = typeof container === 'string' 
      ? DOMUtils.querySelector(container) 
      : container;
    
    if (!this.container) {
      throw new Error(`Container not found: ${container}`);
    }

    this.options = { ...this.getDefaultOptions(), ...options };
    this.isInitialized = false;
    this.isDestroyed = false;
    this.eventListeners = new Map();
    this.childComponents = [];
    
    this._bindMethods();
    this.init();
  }

  /**
   * 獲取預設選項
   * @returns {Object} 預設選項
   */
  getDefaultOptions() {
    return {
      autoInit: true,
      className: '',
      destroyOnRemove: true,
    };
  }

  /**
   * 初始化組件
   */
  init() {
    if (this.isInitialized || this.isDestroyed) {
      return;
    }

    try {
      this.beforeInit();
      this.render();
      this.bindEvents();
      this.afterInit();
      
      this.isInitialized = true;
      this.emit('initialized');
    } catch (error) {
      console.error(`Component initialization failed:`, error);
      this.emit('error', { error, phase: 'initialization' });
    }
  }

  /**
   * 初始化前的鉤子
   * @protected
   */
  beforeInit() {
    // 子類可以覆寫此方法
  }

  /**
   * 渲染組件
   * @protected
   */
  render() {
    // 子類必須實現此方法
    throw new Error('render() method must be implemented by subclass');
  }

  /**
   * 綁定事件
   * @protected
   */
  bindEvents() {
    // 子類可以覆寫此方法
  }

  /**
   * 初始化後的鉤子
   * @protected
   */
  afterInit() {
    // 子類可以覆寫此方法
  }

  /**
   * 銷毀組件
   */
  destroy() {
    if (this.isDestroyed) {
      return;
    }

    try {
      this.beforeDestroy();
      this.unbindEvents();
      this.destroyChildComponents();
      this.cleanupDOM();
      this.afterDestroy();
      
      this.isDestroyed = true;
      this.isInitialized = false;
      this.emit('destroyed');
    } catch (error) {
      console.error(`Component destruction failed:`, error);
      this.emit('error', { error, phase: 'destruction' });
    }
  }

  /**
   * 銷毀前的鉤子
   * @protected
   */
  beforeDestroy() {
    // 子類可以覆寫此方法
  }

  /**
   * 清理 DOM
   * @protected
   */
  cleanupDOM() {
    if (this.container && this.options.destroyOnRemove) {
      DOMUtils.empty(this.container);
    }
  }

  /**
   * 銷毀後的鉤子
   * @protected
   */
  afterDestroy() {
    // 子類可以覆寫此方法
  }

  /**
   * 綁定方法到當前實例
   * @private
   */
  _bindMethods() {
    const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(this))
      .filter(name => typeof this[name] === 'function' && name !== 'constructor');
    
    methods.forEach(method => {
      if (method.startsWith('handle') || method.startsWith('on')) {
        this[method] = this[method].bind(this);
      }
    });
  }

  /**
   * 添加事件監聽器
   * @param {Element} element - 目標元素
   * @param {string} event - 事件名稱
   * @param {Function} handler - 事件處理器
   * @param {Object} [options] - 事件選項
   */
  addEventListener(element, event, handler, options) {
    if (!element || !event || !handler) {
      return;
    }

    element.addEventListener(event, handler, options);
    
    // 記錄事件監聽器以便後續清理
    const key = `${element}_${event}_${handler.name || 'anonymous'}`;
    this.eventListeners.set(key, { element, event, handler, options });
  }

  /**
   * 移除事件監聽器
   * @param {Element} element - 目標元素
   * @param {string} event - 事件名稱
   * @param {Function} handler - 事件處理器
   */
  removeEventListener(element, event, handler) {
    if (!element || !event || !handler) {
      return;
    }

    element.removeEventListener(event, handler);
    
    const key = `${element}_${event}_${handler.name || 'anonymous'}`;
    this.eventListeners.delete(key);
  }

  /**
   * 解綁所有事件監聽器
   * @protected
   */
  unbindEvents() {
    this.eventListeners.forEach(({ element, event, handler }) => {
      try {
        element.removeEventListener(event, handler);
      } catch (error) {
        console.warn('Failed to remove event listener:', error);
      }
    });
    this.eventListeners.clear();
  }

  /**
   * 添加子組件
   * @param {BaseComponent} component - 子組件
   */
  addChildComponent(component) {
    if (component instanceof BaseComponent) {
      this.childComponents.push(component);
    }
  }

  /**
   * 移除子組件
   * @param {BaseComponent} component - 子組件
   */
  removeChildComponent(component) {
    const index = this.childComponents.indexOf(component);
    if (index > -1) {
      this.childComponents.splice(index, 1);
      if (!component.isDestroyed) {
        component.destroy();
      }
    }
  }

  /**
   * 銷毀所有子組件
   * @protected
   */
  destroyChildComponents() {
    this.childComponents.forEach(component => {
      if (!component.isDestroyed) {
        component.destroy();
      }
    });
    this.childComponents = [];
  }

  /**
   * 觸發自定義事件
   * @param {string} eventType - 事件類型
   * @param {any} [data] - 事件數據
   */
  emit(eventType, data = null) {
    const customEvent = new CustomEvent(`component:${eventType}`, {
      detail: { component: this, data },
      bubbles: true,
      cancelable: true,
    });
    
    if (this.container) {
      this.container.dispatchEvent(customEvent);
    }
  }

  /**
   * 監聽自定義事件
   * @param {string} eventType - 事件類型
   * @param {Function} handler - 事件處理器
   */
  on(eventType, handler) {
    if (this.container) {
      this.addEventListener(this.container, `component:${eventType}`, handler);
    }
  }

  /**
   * 移除自定義事件監聽器
   * @param {string} eventType - 事件類型
   * @param {Function} handler - 事件處理器
   */
  off(eventType, handler) {
    if (this.container) {
      this.removeEventListener(this.container, `component:${eventType}`, handler);
    }
  }

  /**
   * 顯示組件
   * @param {string} [display='block'] - 顯示方式
   */
  show(display = 'block') {
    DOMUtils.show(this.container, display);
    DOMUtils.removeClass(this.container, CSS_CLASSES.STATE.HIDDEN);
    this.emit('shown');
  }

  /**
   * 隱藏組件
   */
  hide() {
    DOMUtils.hide(this.container);
    DOMUtils.addClass(this.container, CSS_CLASSES.STATE.HIDDEN);
    this.emit('hidden');
  }

  /**
   * 切換組件顯示/隱藏
   * @param {string} [display='block'] - 顯示方式
   */
  toggle(display = 'block') {
    if (DOMUtils.isVisible(this.container)) {
      this.hide();
    } else {
      this.show(display);
    }
  }

  /**
   * 啟用組件
   */
  enable() {
    DOMUtils.removeClass(this.container, CSS_CLASSES.STATE.DISABLED);
    this.emit('enabled');
  }

  /**
   * 禁用組件
   */
  disable() {
    DOMUtils.addClass(this.container, CSS_CLASSES.STATE.DISABLED);
    this.emit('disabled');
  }

  /**
   * 設置載入狀態
   * @param {boolean} loading - 是否載入中
   */
  setLoading(loading) {
    if (loading) {
      DOMUtils.addClass(this.container, CSS_CLASSES.STATE.LOADING);
    } else {
      DOMUtils.removeClass(this.container, CSS_CLASSES.STATE.LOADING);
    }
    this.emit('loadingChanged', { loading });
  }

  /**
   * 更新組件選項
   * @param {Object} newOptions - 新選項
   */
  updateOptions(newOptions) {
    this.options = { ...this.options, ...newOptions };
    this.emit('optionsUpdated', { options: this.options });
  }

  /**
   * 獲取組件狀態
   * @returns {Object} 組件狀態
   */
  getState() {
    return {
      isInitialized: this.isInitialized,
      isDestroyed: this.isDestroyed,
      isVisible: DOMUtils.isVisible(this.container),
      isEnabled: !DOMUtils.hasClass(this.container, CSS_CLASSES.STATE.DISABLED),
      isLoading: DOMUtils.hasClass(this.container, CSS_CLASSES.STATE.LOADING),
      childComponentsCount: this.childComponents.length,
      eventListenersCount: this.eventListeners.size,
    };
  }

  /**
   * 驗證組件狀態
   * @returns {Object} 驗證結果
   */
  validate() {
    const errors = [];
    const warnings = [];

    if (!this.container) {
      errors.push('Container element is missing');
    }

    if (this.isDestroyed && this.eventListeners.size > 0) {
      warnings.push('Destroyed component still has event listeners');
    }

    if (this.childComponents.some(child => child.isDestroyed)) {
      warnings.push('Component has destroyed child components');
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * 記錄組件信息
   * @param {string} level - 日誌級別 ('log', 'warn', 'error')
   * @param {string} message - 訊息
   * @param {any} [data] - 額外數據
   */
  log(level = 'log', message, data = null) {
    const componentName = this.constructor.name;
    const prefix = `[${componentName}]`;
    
    if (data) {
      console[level](prefix, message, data);
    } else {
      console[level](prefix, message);
    }
  }
}
