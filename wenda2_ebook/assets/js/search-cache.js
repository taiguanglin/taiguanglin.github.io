/**
 * 搜索緩存管理器 - 使用 IndexedDB 緩存搜索相關數據
 */

class SearchCacheManager {
  constructor() {
    this.dbName = 'SearchCache';
    this.dbVersion = 1;
    this.db = null;
    
    // 存儲配置
    this.stores = {
      searchIndex: 'searchIndex',     // 搜索索引 JSON 數據
      processedIndex: 'processedIndex', // 分詞處理後的數據
      metadata: 'metadata'            // 元數據（版本、時間戳等）
    };
  }

  /**
   * 初始化數據庫
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);
      
      request.onerror = () => {
        console.warn('IndexedDB 初始化失敗:', request.error);
        reject(request.error);
      };
      
      request.onsuccess = () => {
        this.db = request.result;
        console.log('✅ IndexedDB 初始化成功');
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // 創建搜索索引存儲
        if (!db.objectStoreNames.contains(this.stores.searchIndex)) {
          const searchStore = db.createObjectStore(this.stores.searchIndex, { keyPath: 'key' });
          searchStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
        
        // 創建處理後索引存儲
        if (!db.objectStoreNames.contains(this.stores.processedIndex)) {
          const processedStore = db.createObjectStore(this.stores.processedIndex, { keyPath: 'key' });
          processedStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
        
        // 創建元數據存儲
        if (!db.objectStoreNames.contains(this.stores.metadata)) {
          db.createObjectStore(this.stores.metadata, { keyPath: 'key' });
        }
        
        console.log('📦 IndexedDB 數據庫結構已創建');
      };
    });
  }

  /**
   * 檢查緩存是否可用
   */
  isAvailable() {
    return 'indexedDB' in window && this.db !== null;
  }

  /**
   * 獲取搜索索引的緩存鍵
   */
  getSearchIndexKey(isTraditional = false) {
    return isTraditional ? 'search_index_trad' : 'search_index_simp';
  }

  /**
   * 獲取處理後索引的緩存鍵
   */
  getProcessedIndexKey(isTraditional = false, segmenterEnabled = false, hashPrefix = null) {
    const lang = isTraditional ? 'trad' : 'simp';
    const seg = segmenterEnabled ? 'seg' : 'noseg';
    const hash = hashPrefix ? `_${hashPrefix}` : '';
    return `processed_index_${lang}_${seg}${hash}`;
  }

  /**
   * 緩存搜索索引 JSON 數據
   */
  async cacheSearchIndex(data, isTraditional = false) {
    if (!this.isAvailable()) return false;
    
    const key = this.getSearchIndexKey(isTraditional);
    const cacheData = {
      key: key,
      data: data,
      timestamp: Date.now(),
      size: JSON.stringify(data).length
    };
    
    try {
      const transaction = this.db.transaction([this.stores.searchIndex], 'readwrite');
      const store = transaction.objectStore(this.stores.searchIndex);
      await this.promisifyRequest(store.put(cacheData));
      
      console.log(`💾 搜索索引已緩存: ${key} (${this.formatSize(cacheData.size)})`);
      return true;
    } catch (error) {
      console.warn('緩存搜索索引失敗:', error);
      return false;
    }
  }

  /**
   * 獲取緩存的搜索索引
   */
  async getCachedSearchIndex(isTraditional = false) {
    if (!this.isAvailable()) return null;
    
    const key = this.getSearchIndexKey(isTraditional);
    
    try {
      const transaction = this.db.transaction([this.stores.searchIndex], 'readonly');
      const store = transaction.objectStore(this.stores.searchIndex);
      const result = await this.promisifyRequest(store.get(key));
      
      if (result) {
        console.log(`📦 從緩存加載搜索索引: ${key} (${this.formatSize(result.size)})`);
        return result.data;
      }
      return null;
    } catch (error) {
      console.warn('獲取緩存搜索索引失敗:', error);
      return null;
    }
  }

  /**
   * 緩存處理後的索引數據
   */
  async cacheProcessedIndex(processedData, isTraditional = false, segmenterEnabled = false, sourceHash = null) {
    if (!this.isAvailable()) return false;
    
    const hashPrefix = sourceHash ? sourceHash.substring(0, 8) : null;
    const key = this.getProcessedIndexKey(isTraditional, segmenterEnabled, hashPrefix);
    const cacheData = {
      key: key,
      data: processedData,
      timestamp: Date.now(),
      segmenterEnabled: segmenterEnabled,
      sourceHash: sourceHash,
      size: JSON.stringify(processedData).length
    };
    
    try {
      const transaction = this.db.transaction([this.stores.processedIndex], 'readwrite');
      const store = transaction.objectStore(this.stores.processedIndex);
      await this.promisifyRequest(store.put(cacheData));
      
      console.log(`💾 處理後索引已緩存: ${key} (${this.formatSize(cacheData.size)})`);
      return true;
    } catch (error) {
      console.warn('緩存處理後索引失敗:', error);
      return false;
    }
  }

  /**
   * 獲取緩存的處理後索引
   */
  async getCachedProcessedIndex(isTraditional = false, segmenterEnabled = false, sourceHash = null) {
    if (!this.isAvailable()) return null;
    
    const hashPrefix = sourceHash ? sourceHash.substring(0, 8) : null;
    const key = this.getProcessedIndexKey(isTraditional, segmenterEnabled, hashPrefix);
    
    try {
      const transaction = this.db.transaction([this.stores.processedIndex], 'readonly');
      const store = transaction.objectStore(this.stores.processedIndex);
      const result = await this.promisifyRequest(store.get(key));
      
      if (result && result.segmenterEnabled === segmenterEnabled) {
        console.log(`📦 從緩存加載處理後索引: ${key} (${this.formatSize(result.size)})`);
        return result.data;
      }
      return null;
    } catch (error) {
      console.warn('獲取緩存處理後索引失敗:', error);
      return null;
    }
  }

  /**
   * 設置元數據
   */
  async setMetadata(key, value) {
    if (!this.isAvailable()) return false;
    
    const metaData = {
      key: key,
      value: value,
      timestamp: Date.now()
    };
    
    try {
      const transaction = this.db.transaction([this.stores.metadata], 'readwrite');
      const store = transaction.objectStore(this.stores.metadata);
      await this.promisifyRequest(store.put(metaData));
      return true;
    } catch (error) {
      console.warn('設置元數據失敗:', error);
      return false;
    }
  }

  /**
   * 獲取元數據
   */
  async getMetadata(key) {
    if (!this.isAvailable()) return null;
    
    try {
      const transaction = this.db.transaction([this.stores.metadata], 'readonly');
      const store = transaction.objectStore(this.stores.metadata);
      const result = await this.promisifyRequest(store.get(key));
      return result ? result.value : null;
    } catch (error) {
      console.warn('獲取元數據失敗:', error);
      return null;
    }
  }

  /**
   * 檢查緩存是否需要更新（基於哈希值）
   * @returns {Promise<boolean>}
   */
  async needsUpdate(isTraditional = false) {
    const result = await this.checkUpdate(isTraditional);
    return result.needsUpdate;
  }

  /**
   * 下載遠程 .hash 並與本地比對；回傳是否需更新與 hash 資料（含未壓縮 size）。
   * @returns {Promise<{needsUpdate: boolean, hashData: object|null}>}
   */
  async checkUpdate(isTraditional = false) {
    try {
      const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
      const hashFileName = `${indexFileName}.hash`;

      const remoteHashData = await this.fetchHashFile(hashFileName);
      if (!remoteHashData) {
        console.log('📡 無法獲取遠程哈希文件，將重新下載索引');
        return { needsUpdate: true, hashData: null };
      }

      const localHashKey = `hash_${isTraditional ? 'trad' : 'simp'}`;
      const localHashData = await this.getMetadata(localHashKey);

      if (!localHashData) {
        console.log('💾 本地無哈希記錄，需要下載');
        return { needsUpdate: true, hashData: remoteHashData };
      }

      const needsUpdate = localHashData.hash !== remoteHashData.hash;
      if (needsUpdate) {
        console.log(`🔄 檢測到內容更新 (${localHashData.hash.substring(0,8)} → ${remoteHashData.hash.substring(0,8)})`);
      } else {
        console.log(`✅ 內容未變更 (${remoteHashData.hash.substring(0,8)})`);
      }

      return { needsUpdate: needsUpdate, hashData: remoteHashData };
    } catch (error) {
      console.warn('哈希檢查失敗，將重新下載:', error);
      return { needsUpdate: true, hashData: null };
    }
  }

  /**
   * 下載哈希文件
   */
  async fetchHashFile(hashFileName) {
    try {
      const response = await fetch(hashFileName);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.warn(`無法下載哈希文件 ${hashFileName}:`, error);
      return null;
    }
  }

  /**
   * 保存哈希值到元數據
   */
  async saveHashMetadata(hashData, isTraditional = false) {
    const hashKey = `hash_${isTraditional ? 'trad' : 'simp'}`;
    await this.setMetadata(hashKey, hashData);
  }

  /**
   * 清除舊的處理後索引緩存（當原始索引更新時）
   */
  async clearOldProcessedIndexes(isTraditional = false, currentHash = null) {
    if (!this.isAvailable()) return;
    
    try {
      const transaction = this.db.transaction([this.stores.processedIndex], 'readwrite');
      const store = transaction.objectStore(this.stores.processedIndex);
      const request = store.openCursor();
      
      const lang = isTraditional ? 'trad' : 'simp';
      let deletedCount = 0;
      
      return new Promise((resolve, reject) => {
        request.onsuccess = (event) => {
          const cursor = event.target.result;
          if (cursor) {
            const key = cursor.value.key;
            // 檢查是否是相同語言的處理後索引
            if (key.includes(`processed_index_${lang}_`)) {
              console.log(`🗑️ 清除處理後索引緩存: ${key}`);
              cursor.delete();
              deletedCount++;
            }
            cursor.continue();
          } else {
            // 遍歷完成
            if (deletedCount > 0) {
              console.log(`✅ 已清除 ${deletedCount} 個舊的處理後索引緩存`);
            } else {
              console.log(`ℹ️ 沒有找到需要清除的處理後索引緩存`);
            }
            resolve();
          }
        };
        
        request.onerror = () => {
          console.warn('清除舊處理後索引失敗:', request.error);
          reject(request.error);
        };
      });
    } catch (error) {
      console.warn('清除舊處理後索引失敗:', error);
    }
  }

  /**
   * 清除所有緩存
   */
  async clearCache() {
    if (!this.isAvailable()) return false;
    
    try {
      const transaction = this.db.transaction([
        this.stores.searchIndex,
        this.stores.processedIndex,
        this.stores.metadata
      ], 'readwrite');
      
      await Promise.all([
        this.promisifyRequest(transaction.objectStore(this.stores.searchIndex).clear()),
        this.promisifyRequest(transaction.objectStore(this.stores.processedIndex).clear()),
        this.promisifyRequest(transaction.objectStore(this.stores.metadata).clear())
      ]);
      
      console.log('🗑️ 所有搜索緩存已清除');
      return true;
    } catch (error) {
      console.warn('清除緩存失敗:', error);
      return false;
    }
  }

  /**
   * 獲取緩存統計信息
   */
  async getCacheStats() {
    if (!this.isAvailable()) return null;
    
    try {
      const stats = {
        searchIndexCount: 0,
        processedIndexCount: 0,
        totalSize: 0
      };
      
      // 統計搜索索引
      const searchTx = this.db.transaction([this.stores.searchIndex], 'readonly');
      const searchStore = searchTx.objectStore(this.stores.searchIndex);
      const searchCursor = searchStore.openCursor();
      
      await this.promisifyCursor(searchCursor, (cursor) => {
        stats.searchIndexCount++;
        stats.totalSize += cursor.value.size || 0;
      });
      
      // 統計處理後索引
      const processedTx = this.db.transaction([this.stores.processedIndex], 'readonly');
      const processedStore = processedTx.objectStore(this.stores.processedIndex);
      const processedCursor = processedStore.openCursor();
      
      await this.promisifyCursor(processedCursor, (cursor) => {
        stats.processedIndexCount++;
        stats.totalSize += cursor.value.size || 0;
      });
      
      return stats;
    } catch (error) {
      console.warn('獲取緩存統計失敗:', error);
      return null;
    }
  }

  /**
   * 將 IndexedDB 請求轉換為 Promise
   */
  promisifyRequest(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 將 IndexedDB 游標轉換為 Promise
   */
  promisifyCursor(cursorRequest, callback) {
    return new Promise((resolve, reject) => {
      cursorRequest.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          callback(cursor);
          cursor.continue();
        } else {
          resolve();
        }
      };
      cursorRequest.onerror = () => reject(cursorRequest.error);
    });
  }

  /**
   * 格式化文件大小
   */
  formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

// 全局緩存管理器實例
window.searchCacheManager = new SearchCacheManager();
