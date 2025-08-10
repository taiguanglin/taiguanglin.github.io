/**
 * @fileoverview SearchService 測試
 * @author Assistant
 * @version 1.0.0
 */

import { SearchService } from '../../assets/js/services/search.js';
import { PageUtils } from '../../assets/js/utils/page.js';

// 模擬 PageUtils
jest.mock('../../assets/js/utils/page.js');

// 模擬 MiniSearch
const mockMiniSearch = {
  addAll: jest.fn(),
  search: jest.fn(),
  autoSuggest: jest.fn(),
};

global.MiniSearch = jest.fn(() => mockMiniSearch);

describe('SearchService', () => {
  let searchService;
  let originalFetch;

  beforeEach(() => {
    searchService = new SearchService();
    originalFetch = global.fetch;
    
    // 重置模擬
    jest.clearAllMocks();
    
    // 設置預設模擬返回值
    PageUtils.isIndexPage.mockReturnValue(true);
    PageUtils.getSearchIndexFile.mockReturnValue('search_index.json');
    
    // 模擬 fetch 成功響應
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve([
          {
            id: 'doc1',
            title: '測試標題',
            content: '測試內容',
            type: 'content',
            url: '/test1.html'
          },
          {
            id: 'doc2',
            title: '另一個標題',
            content: '另一個內容',
            type: 'question',
            url: '/test2.html'
          }
        ])
      })
    );
  });

  afterEach(() => {
    global.fetch = originalFetch;
    delete window.MiniSearch;
  });

  describe('初始化', () => {
    test('應該正確初始化服務實例', () => {
      expect(searchService.searchIndex).toBeNull();
      expect(searchService.miniSearch).toBeNull();
      expect(searchService.isInitialized).toBe(false);
      expect(searchService.currentResults).toEqual([]);
      expect(searchService.displayedResultsCount).toBe(0);
    });

    test('isReady 應該在未初始化時返回 false', () => {
      expect(searchService.isReady()).toBe(false);
    });
  });

  describe('initialize', () => {
    test('應該在首頁成功初始化', async () => {
      const result = await searchService.initialize();

      expect(result).toBe(true);
      expect(searchService.isInitialized).toBe(true);
      expect(searchService.miniSearch).toBeDefined();
      expect(global.fetch).toHaveBeenCalledWith('search_index.json');
      expect(mockMiniSearch.addAll).toHaveBeenCalledWith(expect.any(Array));
    });

    test('應該在非首頁返回 false', async () => {
      PageUtils.isIndexPage.mockReturnValue(false);

      const result = await searchService.initialize();

      expect(result).toBe(false);
      expect(searchService.isInitialized).toBe(false);
    });

    test('應該在已初始化時返回 true', async () => {
      await searchService.initialize();
      const result = await searchService.initialize();

      expect(result).toBe(true);
      expect(global.fetch).toHaveBeenCalledTimes(1); // 只調用一次
    });

    test('應該處理網路錯誤', async () => {
      global.fetch = jest.fn(() =>
        Promise.reject(new Error('Network error'))
      );

      await expect(searchService.initialize()).rejects.toThrow();
      expect(searchService.isInitialized).toBe(false);
    });

    test('應該處理 HTTP 錯誤', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          status: 404
        })
      );

      await expect(searchService.initialize()).rejects.toThrow();
    });

    test('應該處理無效的搜索索引數據', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve('invalid data')
        })
      );

      await expect(searchService.initialize()).rejects.toThrow('搜索索引格式無效');
    });

    test('應該處理空的搜索索引', async () => {
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([])
        })
      );

      await expect(searchService.initialize()).rejects.toThrow('搜索索引為空');
    });
  });

  describe('search', () => {
    beforeEach(async () => {
      await searchService.initialize();
    });

    test('應該在未初始化時返回空陣列', () => {
      const uninitializedService = new SearchService();
      const results = uninitializedService.search('test');

      expect(results).toEqual([]);
    });

    test('應該在查詢太短時返回空陣列', () => {
      const results = searchService.search('a');

      expect(results).toEqual([]);
      expect(mockMiniSearch.search).not.toHaveBeenCalled();
    });

    test('應該成功執行搜索', () => {
      const mockResults = [
        {
          id: 'doc1',
          score: 1.5,
          content: '測試內容',
          type: 'content'
        }
      ];
      mockMiniSearch.search.mockReturnValue(mockResults);

      const results = searchService.search('測試');

      expect(mockMiniSearch.search).toHaveBeenCalledWith('測試', expect.any(Object));
      expect(results).toHaveLength(1);
      expect(results[0]).toMatchObject({
        id: 'doc1',
        score: 1.5,
        relevanceScore: 1.5,
        context: expect.any(String)
      });
    });

    test('應該處理搜索錯誤', () => {
      mockMiniSearch.search.mockImplementation(() => {
        throw new Error('Search error');
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const results = searchService.search('測試');

      expect(results).toEqual([]);
      expect(consoleSpy).toHaveBeenCalledWith('搜索執行失敗:', expect.any(Error));
      
      consoleSpy.mockRestore();
    });

    test('應該支援自定義搜索選項', () => {
      const mockResults = [];
      mockMiniSearch.search.mockReturnValue(mockResults);

      searchService.search('測試', { limit: 50, fuzzy: 0.3 });

      expect(mockMiniSearch.search).toHaveBeenCalledWith('測試', expect.objectContaining({
        limit: 50,
        fuzzy: 0.3
      }));
    });
  });

  describe('getPagedResults', () => {
    beforeEach(async () => {
      await searchService.initialize();
      
      // 設置測試數據
      const mockResults = Array.from({ length: 50 }, (_, i) => ({
        id: `doc${i}`,
        title: `標題 ${i}`,
        content: `內容 ${i}`,
        score: 1.0
      }));
      searchService.currentResults = mockResults;
    });

    test('應該返回第一頁結果', () => {
      const result = searchService.getPagedResults(1, 20);

      expect(result).toMatchObject({
        currentPage: 1,
        totalPages: 3,
        totalResults: 50,
        hasNextPage: true,
        hasPrevPage: false
      });
      expect(result.results).toHaveLength(20);
    });

    test('應該返回中間頁結果', () => {
      const result = searchService.getPagedResults(2, 20);

      expect(result).toMatchObject({
        currentPage: 2,
        totalPages: 3,
        hasNextPage: true,
        hasPrevPage: true
      });
      expect(result.results).toHaveLength(20);
    });

    test('應該返回最後一頁結果', () => {
      const result = searchService.getPagedResults(3, 20);

      expect(result).toMatchObject({
        currentPage: 3,
        totalPages: 3,
        hasNextPage: false,
        hasPrevPage: true
      });
      expect(result.results).toHaveLength(10);
    });
  });

  describe('loadMoreResults', () => {
    beforeEach(async () => {
      await searchService.initialize();
      
      const mockResults = Array.from({ length: 50 }, (_, i) => ({
        id: `doc${i}`,
        title: `標題 ${i}`
      }));
      searchService.currentResults = mockResults;
      searchService.displayedResultsCount = 20;
    });

    test('應該載入更多結果', () => {
      const result = searchService.loadMoreResults(10);

      expect(result).toMatchObject({
        loaded: 10,
        remaining: 20,
        hasMore: true
      });
      expect(result.results).toHaveLength(10);
      expect(searchService.displayedResultsCount).toBe(30);
    });

    test('應該載入剩餘的所有結果', () => {
      const result = searchService.loadMoreResults(50);

      expect(result).toMatchObject({
        loaded: 30,
        remaining: 0,
        hasMore: false
      });
      expect(result.results).toHaveLength(30);
      expect(searchService.displayedResultsCount).toBe(50);
    });
  });

  describe('getSuggestions', () => {
    beforeEach(async () => {
      await searchService.initialize();
    });

    test('應該在查詢太短時返回空陣列', () => {
      const suggestions = searchService.getSuggestions('a');
      expect(suggestions).toEqual([]);
    });

    test('應該返回搜索建議', () => {
      const mockSuggestions = [
        { suggestion: '測試', score: 1.5, terms: ['測試'] }
      ];
      mockMiniSearch.autoSuggest.mockReturnValue(mockSuggestions);

      const suggestions = searchService.getSuggestions('測');

      expect(mockMiniSearch.autoSuggest).toHaveBeenCalledWith('測', {
        limit: 5,
        fuzzy: 0.3
      });
      expect(suggestions).toEqual([{
        text: '測試',
        score: 1.5,
        terms: ['測試']
      }]);
    });

    test('應該處理建議錯誤', () => {
      mockMiniSearch.autoSuggest.mockImplementation(() => {
        throw new Error('Suggestion error');
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const suggestions = searchService.getSuggestions('測試');

      expect(suggestions).toEqual([]);
      expect(consoleSpy).toHaveBeenCalled();
      
      consoleSpy.mockRestore();
    });
  });

  describe('highlightSearchTerm', () => {
    test('應該高亮完整詞匹配', () => {
      const result = searchService.highlightSearchTerm('這是測試文字', '測試');
      expect(result).toContain('<mark class="search-highlight-exact">測試</mark>');
    });

    test('應該處理空輸入', () => {
      expect(searchService.highlightSearchTerm('', '測試')).toBe('');
      expect(searchService.highlightSearchTerm('文字', '')).toBe('文字');
      expect(searchService.highlightSearchTerm(null, '測試')).toBeNull();
    });

    test('應該處理多個搜索詞', () => {
      const result = searchService.highlightSearchTerm('這是測試文字內容', '測試 內容');
      expect(result).toContain('<mark class="search-highlight-exact">測試</mark>');
      expect(result).toContain('<mark class="search-highlight-exact">內容</mark>');
    });

    test('應該處理高亮錯誤', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      // 模擬 replace 錯誤
      const originalReplace = String.prototype.replace;
      String.prototype.replace = jest.fn(() => {
        throw new Error('Replace error');
      });

      const result = searchService.highlightSearchTerm('測試文字', '測試');
      expect(result).toBe('測試文字');
      expect(consoleSpy).toHaveBeenCalled();

      String.prototype.replace = originalReplace;
      consoleSpy.mockRestore();
    });
  });

  describe('clearResults', () => {
    test('應該清空搜索結果', () => {
      searchService.currentResults = [{ id: 'test' }];
      searchService.displayedResultsCount = 10;

      searchService.clearResults();

      expect(searchService.currentResults).toEqual([]);
      expect(searchService.displayedResultsCount).toBe(0);
    });
  });

  describe('getStats', () => {
    test('應該返回正確的統計信息', async () => {
      // 未初始化狀態
      let stats = searchService.getStats();
      expect(stats).toMatchObject({
        isInitialized: false,
        totalDocuments: 0,
        currentResultsCount: 0,
        displayedResultsCount: 0
      });

      // 已初始化狀態
      await searchService.initialize();
      searchService.currentResults = [{ id: 'test1' }, { id: 'test2' }];
      searchService.displayedResultsCount = 1;

      stats = searchService.getStats();
      expect(stats).toMatchObject({
        isInitialized: true,
        totalDocuments: 2,
        currentResultsCount: 2,
        displayedResultsCount: 1
      });
    });
  });

  describe('_generateContext', () => {
    test('應該返回短內容的完整內容', () => {
      const content = '這是一個短內容';
      const context = searchService._generateContext(content, '測試');
      expect(context).toBe(content);
    });

    test('應該生成包含搜索詞的上下文', () => {
      const content = '這是一個很長的內容，包含測試詞彙，還有更多的文字內容，需要被截取成合適的長度以便顯示給用戶查看搜索結果的上下文信息。';
      const context = searchService._generateContext(content, '測試');
      
      expect(context).toContain('測試');
      expect(context.length).toBeLessThan(content.length);
    });

    test('應該在找不到搜索詞時返回前200字符', () => {
      const content = 'a'.repeat(300);
      const context = searchService._generateContext(content, '測試');
      
      expect(context).toHaveLength(203); // 200 + '...'
      expect(context).toEndWith('...');
    });

    test('應該處理錯誤情況', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      const context = searchService._generateContext(null, '測試');
      expect(context).toBeNull();
      
      consoleSpy.mockRestore();
    });
  });
});
