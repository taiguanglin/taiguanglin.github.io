/**
 * @fileoverview 國際化服務
 * @author Assistant
 * @version 1.0.0
 */

import { PageUtils } from '../utils/page.js';

/**
 * 國際化服務類
 * @class I18nService
 */
export class I18nService {
  /**
   * 獲取國際化文字
   * @param {string} keyPath - 文字鍵值路徑，如 'bookmark.myBookmarks'
   * @param {boolean} [isTraditional] - 是否為繁體版，可選
   * @param {string} [defaultText=''] - 預設文字
   * @param {Object} [params={}] - 參數對象，用於替換文字中的佔位符
   * @returns {string} 本地化文字
   */
  static getText(keyPath, isTraditional = null, defaultText = '', params = {}) {
    // 如果沒有指定語言，則自動檢測
    if (isTraditional === null) {
      isTraditional = PageUtils.isTraditionalChinesePage();
    }

    if (!window.I18N_TEXT) {
      console.warn('I18N_TEXT not loaded, using default text:', defaultText);
      return defaultText;
    }

    // 解析嵌套鍵值路徑
    const keys = keyPath.split('.');
    let current = window.I18N_TEXT;

    try {
      for (const key of keys) {
        current = current[key];
        if (!current) {
          console.warn(`I18n key not found: ${keyPath}, using default text:`, defaultText);
          return defaultText;
        }
      }

      // 獲取對應語言版本
      let text;
      if (typeof current === 'object' && current !== null) {
        text = isTraditional ? current.traditional : current.simplified;
      } else {
        text = current;
      }

      if (!text) {
        console.warn(`I18n text not found for ${keyPath} (${isTraditional ? 'traditional' : 'simplified'}), using default:`, defaultText);
        return defaultText;
      }

      // 替換參數
      Object.keys(params).forEach(key => {
        text = text.replace(new RegExp(`\\{${key}\\}`, 'g'), params[key]);
      });

      return text;

    } catch (error) {
      console.error('I18n getText failed:', keyPath, error);
      return defaultText;
    }
  }

  /**
   * 便捷方法：獲取本地化文字（使用當前頁面語言）
   * @param {string} simplifiedText - 簡體文字
   * @param {string} traditionalText - 繁體文字
   * @param {Object} [params={}] - 參數對象
   * @returns {string} 本地化文字
   */
  static getLocalText(simplifiedText, traditionalText, params = {}) {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    let text = isTraditional ? traditionalText : simplifiedText;

    // 替換參數
    Object.keys(params).forEach(key => {
      text = text.replace(new RegExp(`\\{${key}\\}`, 'g'), params[key]);
    });

    return text;
  }

  /**
   * 檢查 I18N 文字是否已載入
   * @returns {boolean} 是否已載入
   */
  static isLoaded() {
    return typeof window.I18N_TEXT === 'object' && window.I18N_TEXT !== null;
  }

  /**
   * 載入 I18N 文字配置
   * @param {Object} i18nData - I18N 數據
   * @returns {boolean} 是否載入成功
   */
  static loadI18nData(i18nData) {
    try {
      if (typeof i18nData === 'object' && i18nData !== null) {
        window.I18N_TEXT = i18nData;
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to load I18N data:', error);
      return false;
    }
  }

  /**
   * 獲取可用的語言列表
   * @returns {Array} 語言列表
   */
  static getAvailableLanguages() {
    return [
      { code: 'zh-CN', name: '简体中文', nativeName: '简体' },
      { code: 'zh-TW', name: '繁體中文', nativeName: '繁體' },
    ];
  }

  /**
   * 獲取當前語言信息
   * @returns {Object} 語言信息
   */
  static getCurrentLanguageInfo() {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    const languages = this.getAvailableLanguages();
    return languages.find(lang => 
      isTraditional ? lang.code === 'zh-TW' : lang.code === 'zh-CN'
    );
  }

  /**
   * 格式化數字
   * @param {number} number - 要格式化的數字
   * @param {Object} [options={}] - 格式化選項
   * @returns {string} 格式化後的數字字串
   */
  static formatNumber(number, options = {}) {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    const locale = isTraditional ? 'zh-TW' : 'zh-CN';
    
    try {
      return new Intl.NumberFormat(locale, options).format(number);
    } catch (error) {
      console.warn('Number formatting failed, using default:', error);
      return number.toString();
    }
  }

  /**
   * 格式化日期
   * @param {Date|string|number} date - 要格式化的日期
   * @param {Object} [options={}] - 格式化選項
   * @returns {string} 格式化後的日期字串
   */
  static formatDate(date, options = {}) {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    const locale = isTraditional ? 'zh-TW' : 'zh-CN';
    
    try {
      const dateObj = new Date(date);
      if (isNaN(dateObj.getTime())) {
        throw new Error('Invalid date');
      }
      
      const defaultOptions = {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        ...options,
      };
      
      return new Intl.DateTimeFormat(locale, defaultOptions).format(dateObj);
    } catch (error) {
      console.warn('Date formatting failed, using default:', error);
      return new Date(date).toLocaleDateString();
    }
  }

  /**
   * 格式化相對時間
   * @param {Date|string|number} date - 要格式化的日期
   * @returns {string} 相對時間字串
   */
  static formatRelativeTime(date) {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    
    try {
      const now = new Date();
      const targetDate = new Date(date);
      const diffMs = now - targetDate;
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffMinutes < 1) {
        return isTraditional ? '剛剛' : '刚刚';
      } else if (diffMinutes < 60) {
        return isTraditional ? `${diffMinutes} 分鐘前` : `${diffMinutes} 分钟前`;
      } else if (diffHours < 24) {
        return isTraditional ? `${diffHours} 小時前` : `${diffHours} 小时前`;
      } else if (diffDays < 30) {
        return isTraditional ? `${diffDays} 天前` : `${diffDays} 天前`;
      } else {
        return this.formatDate(date, { month: 'numeric', day: 'numeric' });
      }
    } catch (error) {
      console.warn('Relative time formatting failed:', error);
      return this.formatDate(date);
    }
  }

  /**
   * 檢查文字方向
   * @returns {string} 文字方向 ('ltr' | 'rtl')
   */
  static getTextDirection() {
    // 中文都是從左到右
    return 'ltr';
  }

  /**
   * 獲取貨幣符號
   * @returns {string} 貨幣符號
   */
  static getCurrencySymbol() {
    const isTraditional = PageUtils.isTraditionalChinesePage();
    return isTraditional ? 'NT$' : '¥';
  }

  /**
   * 驗證 I18N 配置完整性
   * @param {Array} requiredKeys - 必需的鍵值列表
   * @returns {Object} 驗證結果
   */
  static validateI18nConfig(requiredKeys = []) {
    const missing = [];
    const errors = [];

    if (!this.isLoaded()) {
      errors.push('I18N configuration not loaded');
      return { isValid: false, missing, errors };
    }

    requiredKeys.forEach(keyPath => {
      const simplifiedText = this.getText(keyPath, false, null);
      const traditionalText = this.getText(keyPath, true, null);

      if (!simplifiedText || !traditionalText) {
        missing.push(keyPath);
      }
    });

    return {
      isValid: missing.length === 0 && errors.length === 0,
      missing,
      errors,
    };
  }
}

// 向後兼容：導出全域函數
export const getI18nText = I18nService.getText;
export const getText = I18nService.getLocalText;
