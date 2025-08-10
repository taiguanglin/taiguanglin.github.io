/**
 * @fileoverview 搜索組件
 * @author Assistant
 * @version 1.0.0
 */

import { BaseComponent } from './base-component.js';
import { CONFIG, CSS_CLASSES } from '../constants/config.js';
import { DOMUtils } from '../utils/dom.js';
import { PageUtils } from '../utils/page.js';
import { searchService } from '../services/search.js';
import { I18nService } from '../services/i18n.js';

/**
 * 搜索組件類
 * @class SearchComponent
 * @extends BaseComponent
 */
export class SearchComponent extends BaseComponent {
  /**
   * 獲取預設選項
   * @returns {Object} 預設選項
   */
  getDefaultOptions() {
    return {
      ...super.getDefaultOptions(),
      autoActivate: false,
      showActivateButton: true,
      resultsPerPage: CONFIG.SEARCH.RESULTS_PER_PAGE,
      minSearchLength: CONFIG.SEARCH.MIN_SEARCH_LENGTH,
      searchDelay: CONFIG.SEARCH.SEARCH_DELAY,
      enableSuggestions: true,
    };
  }

  /**
   * 初始化前的鉤子
   * @protected
   */
  beforeInit() {
    this.isActivated = false;
    this.searchTimeout = null;
    this.currentQuery = '';
    this.displayedResultsCount = 0;
    
    // 只在首頁顯示搜索功能
    if (!PageUtils.isIndexPage()) {
      this.hide();
      return;
    }
  }

  /**
   * 渲染組件
   * @protected
   */
  render() {
    if (!PageUtils.isIndexPage()) {
      return;
    }

    this.container.innerHTML = this._getTemplate();
    this._cacheElements();
    
    if (this.options.autoActivate) {
      this.activate();
    }
  }

  /**
   * 綁定事件
   * @protected
   */
  bindEvents() {
    if (!PageUtils.isIndexPage()) {
      return;
    }

    // 激活按鈕事件
    if (this.activateBtn) {
      this.addEventListener(this.activateBtn, 'click', this.handleActivate);
    }

    // 搜索輸入事件
    if (this.searchInput) {
      this.addEventListener(this.searchInput, 'input', this.handleInput);
      this.addEventListener(this.searchInput, 'keydown', this.handleKeydown);
      this.addEventListener(this.searchInput, 'focus', this.handleFocus);
      this.addEventListener(this.searchInput, 'blur', this.handleBlur);
    }

    // 結果列表事件
    if (this.resultsList) {
      this.addEventListener(this.resultsList, 'click', this.handleResultClick);
    }

    // 操作按鈕事件
    if (this.clearBtn) {
      this.addEventListener(this.clearBtn, 'click', this.handleClear);
    }

    if (this.collapseBtn) {
      this.addEventListener(this.collapseBtn, 'click', this.handleCollapse);
    }

    if (this.loadMoreBtn) {
      this.addEventListener(this.loadMoreBtn, 'click', this.handleLoadMore);
    }

    if (this.loadAllBtn) {
      this.addEventListener(this.loadAllBtn, 'click', this.handleLoadAll);
    }
  }

  /**
   * 緩存 DOM 元素
   * @private
   */
  _cacheElements() {
    this.activateBtn = DOMUtils.querySelector('#search-activate-btn', this.container);
    this.activationSection = DOMUtils.querySelector('.search-activation', this.container);
    this.searchContainer = DOMUtils.querySelector('#search-container', this.container);
    this.searchInput = DOMUtils.querySelector('#search-input', this.container);
    this.searchStatus = DOMUtils.querySelector('.search-status', this.container);
    this.resultsContainer = DOMUtils.querySelector('.search-results', this.container);
    this.resultsList = DOMUtils.querySelector('.search-results-list', this.container);
    this.resultsCount = DOMUtils.querySelector('.search-results-count', this.container);
    this.clearBtn = DOMUtils.querySelector('.search-clear', this.container);
    this.collapseBtn = DOMUtils.querySelector('.search-collapse', this.container);
    this.loadMoreBtn = DOMUtils.querySelector('.search-load-more', this.container);
    this.loadAllBtn = DOMUtils.querySelector('.search-load-all', this.container);
  }

  /**
   * 激活搜索功能
   * @returns {Promise<boolean>} 是否激活成功
   */
  async activate() {
    if (this.isActivated) {
      this._showSearchContainer();
      return true;
    }

    try {
      this._setActivateButtonLoading(true);
      this._setSearchInputLoading(true);

      // 初始化搜索服務
      const success = await searchService.initialize();
      
      if (success) {
        this.isActivated = true;
        this._showSearchContainer();
        this._setSearchInputReady();
        this._updateStatus(I18nService.getText('search.indexReady', null, '搜尋準備就緒', {
          count: searchService.getStats().totalDocuments
        }));
        
        // 聚焦搜索框
        setTimeout(() => this.searchInput?.focus(), 100);
        
        this.emit('activated');
        return true;
      } else {
        throw new Error('搜索服務初始化失敗');
      }

    } catch (error) {
      console.error('搜索激活失敗:', error);
      this._showError(error.message || I18nService.getText('search.loadingFailed', null, '搜尋索引載入失敗'));
      this.emit('activationFailed', { error });
      return false;
    } finally {
      this._setActivateButtonLoading(false);
    }
  }

  /**
   * 執行搜索
   * @param {string} query - 搜索查詢
   * @returns {Promise<Array>} 搜索結果
   */
  async search(query) {
    if (!this.isActivated) {
      console.warn('搜索服務未激活');
      return [];
    }

    this.currentQuery = query.trim();
    
    if (this.currentQuery.length < this.options.minSearchLength) {
      this._clearResults();
      if (this.currentQuery.length > 0) {
        this._updateStatus(I18nService.getText('search.minCharWarning', null, '請輸入至少2個字元進行搜尋'));
      } else {
        this._updateStatus(I18nService.getText('search.indexReady', null, '搜尋準備就緒', {
          count: searchService.getStats().totalDocuments
        }));
      }
      return [];
    }

    try {
      this.setLoading(true);
      
      const results = searchService.search(this.currentQuery);
      this._displayResults(results);
      
      this.emit('searchCompleted', { query: this.currentQuery, results });
      return results;

    } catch (error) {
      console.error('搜索執行失敗:', error);
      this._showError(I18nService.getText('search.searchFailed', null, '搜索失敗'));
      this.emit('searchFailed', { query: this.currentQuery, error });
      return [];
    } finally {
      this.setLoading(false);
    }
  }

  /**
   * 清空搜索結果
   */
  clearSearch() {
    this.currentQuery = '';
    this.displayedResultsCount = 0;
    
    if (this.searchInput) {
      this.searchInput.value = '';
    }
    
    this._clearResults();
    this._updateStatus(I18nService.getText('search.indexReady', null, '搜尋準備就緒', {
      count: searchService.getStats().totalDocuments
    }));
    
    searchService.clearResults();
    this.emit('searchCleared');
  }

  /**
   * 收起搜索面板
   */
  collapse() {
    this._hideSearchContainer();
    this.emit('collapsed');
  }

  /**
   * 載入更多結果
   */
  loadMoreResults() {
    const moreResults = searchService.loadMoreResults();
    
    if (moreResults.results.length > 0) {
      this._appendResults(moreResults.results);
      this.displayedResultsCount += moreResults.loaded;
      this._updateLoadMoreButtons(moreResults.hasMore);
      this._updateResultsCount();
      
      this.emit('moreResultsLoaded', moreResults);
    }
  }

  /**
   * 載入所有結果
   */
  loadAllResults() {
    const remainingResults = searchService.currentResults.slice(this.displayedResultsCount);
    
    if (remainingResults.length > 0) {
      this._appendResults(remainingResults);
      this.displayedResultsCount = searchService.currentResults.length;
      this._updateLoadMoreButtons(false);
      this._updateResultsCount();
      
      this.emit('allResultsLoaded', { totalResults: this.displayedResultsCount });
    }
  }

  /**
   * 處理激活按鈕點擊
   * @param {Event} event - 事件對象
   */
  async handleActivate(event) {
    event.preventDefault();
    await this.activate();
  }

  /**
   * 處理輸入事件
   * @param {Event} event - 事件對象
   */
  handleInput(event) {
    const query = event.target.value;
    
    // 防抖處理
    if (this.searchTimeout) {
      clearTimeout(this.searchTimeout);
    }
    
    this.searchTimeout = setTimeout(() => {
      this.search(query);
    }, this.options.searchDelay);
  }

  /**
   * 處理按鍵事件
   * @param {Event} event - 事件對象
   */
  handleKeydown(event) {
    switch (event.key) {
      case 'Enter':
        event.preventDefault();
        this.search(event.target.value);
        break;
      
      case 'Escape':
        this.clearSearch();
        break;
    }
  }

  /**
   * 處理聚焦事件
   * @param {Event} event - 事件對象
   */
  handleFocus(event) {
    this.emit('inputFocused');
  }

  /**
   * 處理失焦事件
   * @param {Event} event - 事件對象
   */
  handleBlur(event) {
    this.emit('inputBlurred');
  }

  /**
   * 處理結果點擊
   * @param {Event} event - 事件對象
   */
  handleResultClick(event) {
    const resultItem = event.target.closest('.search-result-item');
    if (resultItem) {
      const url = resultItem.dataset.url;
      if (url) {
        this.emit('resultClicked', { url, result: resultItem });
        // 導航到結果頁面
        PageUtils.navigateTo(url);
      }
    }
  }

  /**
   * 處理清空按鈕點擊
   * @param {Event} event - 事件對象
   */
  handleClear(event) {
    event.preventDefault();
    this.clearSearch();
  }

  /**
   * 處理收起按鈕點擊
   * @param {Event} event - 事件對象
   */
  handleCollapse(event) {
    event.preventDefault();
    this.collapse();
  }

  /**
   * 處理載入更多按鈕點擊
   * @param {Event} event - 事件對象
   */
  handleLoadMore(event) {
    event.preventDefault();
    this.loadMoreResults();
  }

  /**
   * 處理載入全部按鈕點擊
   * @param {Event} event - 事件對象
   */
  handleLoadAll(event) {
    event.preventDefault();
    this.loadAllResults();
  }

  /**
   * 顯示搜索容器
   * @private
   */
  _showSearchContainer() {
    if (this.activationSection) {
      DOMUtils.hide(this.activationSection);
    }
    if (this.searchContainer) {
      DOMUtils.show(this.searchContainer, 'block');
    }
  }

  /**
   * 隱藏搜索容器
   * @private
   */
  _hideSearchContainer() {
    if (this.searchContainer) {
      DOMUtils.hide(this.searchContainer);
    }
    if (this.activationSection) {
      DOMUtils.show(this.activationSection, 'block');
    }
  }

  /**
   * 設置激活按鈕載入狀態
   * @private
   * @param {boolean} loading - 是否載入中
   */
  _setActivateButtonLoading(loading) {
    if (this.activateBtn) {
      this.activateBtn.disabled = loading;
      if (loading) {
        DOMUtils.addClass(this.activateBtn, CSS_CLASSES.STATE.LOADING);
      } else {
        DOMUtils.removeClass(this.activateBtn, CSS_CLASSES.STATE.LOADING);
      }
    }
  }

  /**
   * 設置搜索輸入載入狀態
   * @private
   * @param {boolean} loading - 是否載入中
   */
  _setSearchInputLoading(loading) {
    if (this.searchInput) {
      this.searchInput.disabled = loading;
      if (loading) {
        this.searchInput.placeholder = I18nService.getText('search.loading', null, '正在載入搜尋功能，請稍候...');
      }
    }
  }

  /**
   * 設置搜索輸入就緒狀態
   * @private
   */
  _setSearchInputReady() {
    if (this.searchInput) {
      this.searchInput.disabled = false;
      this.searchInput.placeholder = I18nService.getText('search.search_placeholder', null, '搜尋全文內容...');
    }
  }

  /**
   * 顯示錯誤信息
   * @private
   * @param {string} message - 錯誤信息
   */
  _showError(message) {
    this._updateStatus(`⚠️ ${message}`);
    
    // 重新啟用輸入框
    if (this.searchInput) {
      this.searchInput.disabled = false;
      this.searchInput.placeholder = I18nService.getText('search.searchUnavailable', null, '搜尋功能暫不可用');
    }
  }

  /**
   * 更新狀態信息
   * @private
   * @param {string} message - 狀態信息
   */
  _updateStatus(message) {
    if (this.searchStatus) {
      this.searchStatus.innerHTML = message;
    }
  }

  /**
   * 顯示搜索結果
   * @private
   * @param {Array} results - 搜索結果
   */
  _displayResults(results) {
    if (!results || results.length === 0) {
      this._showNoResults();
      return;
    }

    // 重置顯示計數
    this.displayedResultsCount = 0;
    
    // 顯示第一批結果
    const firstBatch = results.slice(0, this.options.resultsPerPage);
    this._renderResults(firstBatch);
    
    this.displayedResultsCount = firstBatch.length;
    
    // 顯示結果容器
    DOMUtils.show(this.resultsContainer, 'block');
    
    // 更新結果統計
    this._updateResultsCount();
    
    // 更新載入更多按鈕
    this._updateLoadMoreButtons(results.length > this.displayedResultsCount);
  }

  /**
   * 渲染搜索結果
   * @private
   * @param {Array} results - 搜索結果
   */
  _renderResults(results) {
    if (!this.resultsList) return;

    this.resultsList.innerHTML = results.map(result => this._getResultItemHTML(result)).join('');
  }

  /**
   * 追加搜索結果
   * @private
   * @param {Array} results - 搜索結果
   */
  _appendResults(results) {
    if (!this.resultsList) return;

    const html = results.map(result => this._getResultItemHTML(result)).join('');
    this.resultsList.insertAdjacentHTML('beforeend', html);
  }

  /**
   * 獲取結果項目 HTML
   * @private
   * @param {Object} result - 搜索結果
   * @returns {string} HTML 字串
   */
  _getResultItemHTML(result) {
    const typeText = this._getResultTypeText(result.type);
    const highlightedContext = searchService.highlightSearchTerm(result.context || result.content, this.currentQuery);
    
    return `
      <div class="search-result-item" data-url="${result.url || ''}">
        <div class="search-result-title">
          <span class="search-result-type">${typeText}</span>
          <span class="search-result-score">${result.score?.toFixed(2) || ''}</span>
        </div>
        <div class="search-result-content">${highlightedContext}</div>
      </div>
    `;
  }

  /**
   * 獲取結果類型文字
   * @private
   * @param {string} type - 結果類型
   * @returns {string} 類型文字
   */
  _getResultTypeText(type) {
    const typeMap = {
      'heading': I18nService.getText('search.resultTypes.heading', null, '標題'),
      'question': I18nService.getText('search.resultTypes.question', null, '問題'),
      'answer': I18nService.getText('search.resultTypes.answer', null, '回答'),
      'content': I18nService.getText('search.resultTypes.content', null, '內容'),
    };
    
    return typeMap[type] || typeMap['content'];
  }

  /**
   * 顯示無結果
   * @private
   */
  _showNoResults() {
    if (this.resultsList) {
      this.resultsList.innerHTML = `
        <div class="search-no-results">
          <p>${I18nService.getText('search.noResults', null, '未找到相關結果')}</p>
          <p>${I18nService.getText('search.tryDifferentKeywords', null, '請嘗試使用不同的關鍵詞')}</p>
        </div>
      `;
    }
    
    DOMUtils.show(this.resultsContainer, 'block');
    this._updateResultsCount();
    this._updateLoadMoreButtons(false);
  }

  /**
   * 清空結果
   * @private
   */
  _clearResults() {
    if (this.resultsList) {
      this.resultsList.innerHTML = '';
    }
    
    DOMUtils.hide(this.resultsContainer);
    this._updateLoadMoreButtons(false);
  }

  /**
   * 更新結果統計
   * @private
   */
  _updateResultsCount() {
    if (this.resultsCount) {
      const total = searchService.currentResults.length;
      const displayed = this.displayedResultsCount;
      
      if (total === 0) {
        this.resultsCount.textContent = I18nService.getText('search.noResultsFound', null, '未找到結果');
      } else if (displayed === total) {
        this.resultsCount.textContent = I18nService.getText('search.allResultsShown', null, '共 {count} 個結果', { count: total });
      } else {
        this.resultsCount.textContent = I18nService.getText('search.resultsShown', null, '顯示 {shown} / {total} 個結果', { shown: displayed, total });
      }
    }
  }

  /**
   * 更新載入更多按鈕
   * @private
   * @param {boolean} hasMore - 是否有更多結果
   */
  _updateLoadMoreButtons(hasMore) {
    if (this.loadMoreBtn) {
      DOMUtils.toggle(this.loadMoreBtn, hasMore ? 'inline-block' : 'none');
    }
    
    if (this.loadAllBtn) {
      DOMUtils.toggle(this.loadAllBtn, hasMore ? 'inline-block' : 'none');
    }
  }

  /**
   * 獲取組件模板
   * @private
   * @returns {string} HTML 模板
   */
  _getTemplate() {
    return `
      <div class="search-activation">
        <button id="search-activate-btn" class="search-activate-btn">
          ${I18nService.getText('search.activate_search', null, '啟用全文搜尋')}
        </button>
        <div class="search-activate-hint">
          ${I18nService.getText('search.activateHint', null, '點擊上方按鈕啟用搜尋功能')}
        </div>
      </div>
      
      <div id="search-container" class="search-container" style="display: none;">
        <div class="search-box">
          <input type="text" id="search-input" placeholder="${I18nService.getText('search.search_placeholder', null, '搜尋全文內容...')}" disabled>
        </div>
        
        <div class="search-status"></div>
        
        <div class="search-results" style="display: none;">
          <div class="search-results-header">
            <div class="search-results-count"></div>
            <div class="search-results-actions">
              <button class="search-clear">${I18nService.getText('search.clear_search', null, '清除搜尋')}</button>
              <button class="search-collapse">${I18nService.getText('search.collapse_search', null, '收起搜尋')}</button>
              <button class="search-load-more" style="display: none;">${I18nService.getText('search.show_more', null, '顯示更多')}</button>
              <button class="search-load-all" style="display: none;">${I18nService.getText('search.show_all', null, '顯示全部')}</button>
            </div>
          </div>
          
          <div class="search-results-list"></div>
        </div>
      </div>
    `;
  }
}
