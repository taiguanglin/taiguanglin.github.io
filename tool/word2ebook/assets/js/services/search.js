/**
 * @fileoverview 搜索服務
 * @author Assistant
 * @version 1.0.0
 */

import { CONFIG, API_ENDPOINTS, ERROR_MESSAGES } from '../constants/config.js';
import { PageUtils } from '../utils/page.js';
import { DOMUtils } from '../utils/dom.js';
import { I18nService } from './i18n.js';

/**
 * 搜索服務類
 * @class SearchService
 */
export class SearchService {
  constructor() {
    this.searchIndex = null;
    this.miniSearch = null;
    this.isInitialized = false;
    this.currentResults = [];
    this.displayedResultsCount = 0;
  }

  /**
   * 檢查是否已初始化
   * @returns {boolean} 是否已初始化
   */
  isReady() {
    return this.isInitialized && this.miniSearch !== null;
  }

  /**
   * 初始化搜索服務
   * @returns {Promise<boolean>} 是否初始化成功
   */
  async initialize() {
    if (this.isInitialized) {
      return true;
    }

    try {
      // 只在首頁初始化搜索功能
      if (!PageUtils.isIndexPage()) {
        console.log('非首頁，跳過搜索初始化');
        return false;
      }

      // 動態載入 MiniSearch
      if (typeof window.MiniSearch === 'undefined') {
        await this._loadMiniSearch();
      }

      // 載入搜索索引
      this.searchIndex = await this._loadSearchIndex();
      
      if (!this.searchIndex || this.searchIndex.length === 0) {
        throw new Error('搜索索引為空');
      }

      // 初始化 MiniSearch
      this.miniSearch = new window.MiniSearch({
        fields: ['title', 'content', 'type'],
        storeFields: ['title', 'content', 'type', 'url', 'context'],
        searchOptions: {
          boost: { title: 2 },
          fuzzy: 0.2,
        },
        extractField: (document, fieldName) => {
          const text = document[fieldName];
          if (!text || typeof text !== 'string') return '';
          
          // 移除 HTML 標籤，但保留文字內容
          return text.replace(/<[^>]*>/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();
        },
      });

      // 添加文檔到索引
      this.miniSearch.addAll(this.searchIndex);
      this.isInitialized = true;

      console.log(`搜索服務初始化成功，共 ${this.searchIndex.length} 條記錄`);
      return true;

    } catch (error) {
      console.error('搜索服務初始化失敗:', error);
      this.isInitialized = false;
      throw error;
    }
  }

  /**
   * 執行搜索
   * @param {string} query - 搜索查詢
   * @param {Object} [options={}] - 搜索選項
   * @returns {Array} 搜索結果
   */
  search(query, options = {}) {
    if (!this.isReady()) {
      console.warn('搜索服務未初始化');
      return [];
    }

    if (!query || query.trim().length < CONFIG.SEARCH.MIN_SEARCH_LENGTH) {
      this.currentResults = [];
      this.displayedResultsCount = 0;
      return [];
    }

    try {
      const searchOptions = {
        limit: options.limit || 1000,
        fuzzy: options.fuzzy !== undefined ? options.fuzzy : 0.2,
        boost: options.boost || { title: 2 },
        ...options,
      };

      const results = this.miniSearch.search(query.trim(), searchOptions);
      
      // 處理搜索結果
      const processedResults = results.map(result => ({
        ...result,
        context: this._generateContext(result.content, query),
        relevanceScore: result.score,
      }));

      this.currentResults = processedResults;
      this.displayedResultsCount = 0;

      return processedResults;

    } catch (error) {
      console.error('搜索執行失敗:', error);
      return [];
    }
  }

  /**
   * 獲取分頁搜索結果
   * @param {number} [page=1] - 頁碼
   * @param {number} [pageSize] - 每頁大小
   * @returns {Object} 分頁結果
   */
  getPagedResults(page = 1, pageSize = CONFIG.SEARCH.RESULTS_PER_PAGE) {
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const results = this.currentResults.slice(startIndex, endIndex);
    
    return {
      results,
      currentPage: page,
      totalPages: Math.ceil(this.currentResults.length / pageSize),
      totalResults: this.currentResults.length,
      hasNextPage: endIndex < this.currentResults.length,
      hasPrevPage: page > 1,
    };
  }

  /**
   * 載入更多結果
   * @param {number} count - 要載入的數量
   * @returns {Array} 新載入的結果
   */
  loadMoreResults(count = CONFIG.SEARCH.RESULTS_PER_PAGE) {
    const startIndex = this.displayedResultsCount;
    const endIndex = Math.min(startIndex + count, this.currentResults.length);
    const newResults = this.currentResults.slice(startIndex, endIndex);
    
    this.displayedResultsCount = endIndex;
    
    return {
      results: newResults,
      loaded: newResults.length,
      remaining: this.currentResults.length - this.displayedResultsCount,
      hasMore: this.displayedResultsCount < this.currentResults.length,
    };
  }

  /**
   * 獲取搜索建議
   * @param {string} query - 查詢字串
   * @param {number} [limit=5] - 建議數量限制
   * @returns {Array} 搜索建議
   */
  getSuggestions(query, limit = 5) {
    if (!this.isReady() || !query || query.length < 2) {
      return [];
    }

    try {
      const suggestions = this.miniSearch.autoSuggest(query, {
        limit,
        fuzzy: 0.3,
      });

      return suggestions.map(suggestion => ({
        text: suggestion.suggestion,
        score: suggestion.score,
        terms: suggestion.terms,
      }));

    } catch (error) {
      console.error('獲取搜索建議失敗:', error);
      return [];
    }
  }

  /**
   * 高亮搜索詞
   * @param {string} text - 原始文字
   * @param {string} searchTerm - 搜索詞
   * @returns {string} 高亮後的文字
   */
  highlightSearchTerm(text, searchTerm) {
    if (!text || !searchTerm) return text;

    try {
      // 轉義特殊字符
      const escapedTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      
      // 分詞處理中文
      const terms = searchTerm.trim().split(/\s+/).filter(term => term.length > 0);
      
      let highlightedText = text;
      
      terms.forEach(term => {
        const escapedSingleTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        // 完整詞匹配（優先級高）
        const exactRegex = new RegExp(`(${escapedSingleTerm})`, 'gi');
        highlightedText = highlightedText.replace(exactRegex, '<mark class="search-highlight-exact">$1</mark>');
        
        // 字符級匹配（用於中文）
        if (term.length >= 2) {
          for (let i = 0; i < term.length; i++) {
            const char = term[i].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const charRegex = new RegExp(`(?<!<[^>]*)(${char})(?![^<]*>)`, 'gi');
            highlightedText = highlightedText.replace(charRegex, '<mark class="search-highlight-partial">$1</mark>');
          }
        }
      });

      return highlightedText;

    } catch (error) {
      console.warn('搜索詞高亮失敗:', error, '搜索詞:', searchTerm);
      return text;
    }
  }

  /**
   * 清空搜索結果
   */
  clearResults() {
    this.currentResults = [];
    this.displayedResultsCount = 0;
  }

  /**
   * 獲取搜索統計信息
   * @returns {Object} 統計信息
   */
  getStats() {
    return {
      isInitialized: this.isInitialized,
      totalDocuments: this.searchIndex ? this.searchIndex.length : 0,
      currentResultsCount: this.currentResults.length,
      displayedResultsCount: this.displayedResultsCount,
    };
  }

  /**
   * 載入 MiniSearch 庫
   * @private
   */
  async _loadMiniSearch() {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/minisearch@6.0.1/dist/umd/index.min.js';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load MiniSearch library'));
      document.head.appendChild(script);
    });
  }

  /**
   * 載入搜索索引
   * @private
   */
  async _loadSearchIndex() {
    const indexFile = PageUtils.getSearchIndexFile();
    
    try {
      const response = await fetch(indexFile);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const searchIndex = await response.json();
      
      if (!Array.isArray(searchIndex)) {
        throw new Error('搜索索引格式無效');
      }
      
      return searchIndex;
      
    } catch (error) {
      console.error('載入搜索索引失敗:', error);
      throw new Error(I18nService.getText('search.networkError', null, '網路連接失敗，請檢查網路後重試'));
    }
  }

  /**
   * 生成搜索結果上下文
   * @private
   * @param {string} content - 內容
   * @param {string} query - 搜索查詢
   * @returns {string} 上下文
   */
  _generateContext(content, query) {
    if (!content || !query) return content;

    try {
      // 移除 HTML 標籤
      const cleanContent = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
      
      if (cleanContent.length <= 200) {
        return cleanContent;
      }

      // 尋找搜索詞位置
      const lowerContent = cleanContent.toLowerCase();
      const lowerQuery = query.toLowerCase();
      const index = lowerContent.indexOf(lowerQuery);
      
      if (index === -1) {
        // 找不到精確匹配，返回前200字符
        return cleanContent.substring(0, 200) + '...';
      }

      // 計算上下文範圍
      const contextLength = 100;
      const start = Math.max(0, index - contextLength);
      const end = Math.min(cleanContent.length, index + lowerQuery.length + contextLength);
      
      let context = cleanContent.substring(start, end);
      
      // 添加省略號
      if (start > 0) context = '...' + context;
      if (end < cleanContent.length) context = context + '...';
      
      return context;

    } catch (error) {
      console.warn('生成搜索上下文失敗:', error);
      return content.substring(0, 200);
    }
  }
}

// 創建全域搜索服務實例
export const searchService = new SearchService();
