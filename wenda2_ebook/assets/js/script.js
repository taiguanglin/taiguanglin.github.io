document.addEventListener('DOMContentLoaded', function() {
// ============================================================
// 00-base.js — 全局命名空间、页面类型检测、暗色模式初始化
//
// 规则：所有跨模块共享的工具函数都应在此定义。
// 其他模块通过 W2E.* 命名空间或直接调用这里定义的全局函数。
// ============================================================

// 全局命名空间：用于模块间显式通信（减少裸全局变量）
const W2E = window.W2E = {};

// ------------------------------------------------------------------ //
// 页面类型检测（在所有模块中共享）                                    //
// ------------------------------------------------------------------ //

function _getPageFilename() {
  return window.location.pathname.split('/').pop() || 'index.html';
}

function isIndexPage() {
  const f = _getPageFilename();
  return f === 'index.html' || f === 'index_trad.html';
}

function isTraditionalChinesePage() {
  return _getPageFilename().includes('_trad.html');
}

// 简体/繁体文本选择（当 I18N_TEXT 不可用时的降级）
function getText(simplifiedText, traditionalText) {
  return isTraditionalChinesePage() ? traditionalText : simplifiedText;
}

// ------------------------------------------------------------------ //
// 暗色模式初始化（在 DOM 解析时立即执行，避免闪烁）                   //
// ------------------------------------------------------------------ //

if (localStorage.getItem('darkMode') === 'true') {
  document.body.classList.add('dark-mode');
}
  // ============ 搜索功能（延迟加载） ============
  // isIndexPage / isTraditionalChinesePage / getText 由 00-base.js 提供

  let searchIndex = null;
  let miniSearch = null;
  let searchInitialized = false;
  let currentSearchResults = [];
  let displayedResultsCount = 0;
  let searchScope = 'both'; // 'question' | 'answer' | 'both'
  const RESULTS_PER_PAGE = 20;

  // 获取搜索索引文件名
  function getSearchIndexFile() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index_trad.html' ? 'search_index_trad.json' : 'search_index.json';
  }
  
  // 激活搜索功能
  async function activateSearch() {
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchActivateBtn = document.getElementById('search-activate-btn');
    
    // 立即禁用激活按钮防止重复点击
    if (searchActivateBtn) {
      searchActivateBtn.disabled = true;
    }
    
    if (searchInitialized) {
      // 如果已经初始化，直接显示搜索容器
      if (searchContainer && searchActivation) {
        searchActivation.style.display = 'none';
        searchContainer.style.display = 'block';
        
        // 恢復搜索準備就緒狀態信息
        const searchStatus = document.getElementById('search-status');
        if (searchStatus && searchIndex && searchIndex.length > 0) {
          const isSegmenterEnabled = chineseSegmenter && chineseSegmenter.cut;
          const segmenterStatus = isSegmenterEnabled ? 
            (isTraditionalChinesePage() ? '智能中文分詞已啟用' : '智能中文分词已启用') : 
            (isTraditionalChinesePage() ? '使用傳統搜尋模式' : '使用传统搜索模式');
          
          searchStatus.innerHTML = `
            <div class="search-status-success">
              ✅ ${getI18nText('search.indexReady', isTraditionalChinesePage(), '搜尋準備就緒 (共{count}條記錄)', { count: searchIndex.length })}
              <br><small>🔧 ${segmenterStatus}</small>
            </div>
          `;
        }
        
        // 聚焦搜索框
        if (searchInput) {
          setTimeout(() => searchInput.focus(), 100);
        }
      }
      // 重新启用激活按钮
      if (searchActivateBtn) {
        searchActivateBtn.disabled = false;
      }
      return;
    }
    
    // 立即禁用搜索输入框并显示加载状态
    if (searchInput) {
      searchInput.disabled = true;
      searchInput.placeholder = getI18nText('search.loading', isTraditionalChinesePage(), '正在載入搜尋功能，請稍候...');
    }
    
    await initSearch();
  }
  
  // 創建載入UI（spinner；下載進度改由 createProgressUI 負責）
  function createLoadingUI(container) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'search-loading';
    loadingDiv.innerHTML = `
      <div class="search-loading-spinner"></div>
      <div class="search-loading-text" id="search-loading-text"></div>
    `;
    
    container.appendChild(loadingDiv);
    
    return {
      loadingDiv,
      textElement: loadingDiv.querySelector('#search-loading-text')
    };
  }
  
  // 創建錯誤UI
  function createErrorUI(container, message, onRetry) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'search-error';
    errorDiv.innerHTML = `
      <span>⚠️ ${message}</span>
      <button class="search-retry-btn" id="search-retry-btn">${getI18nText('search.retry', isTraditionalChinesePage(), '重試')}</button>
    `;
    
    container.appendChild(errorDiv);
    
    const retryBtn = errorDiv.querySelector('#search-retry-btn');
    retryBtn.addEventListener('click', () => {
      container.removeChild(errorDiv);
      onRetry();
    });
    
    return errorDiv;
  }

  function formatDownloadMb(bytes) {
    return (bytes / (1024 * 1024)).toFixed(1);
  }

  /**
   * 載入搜索索引並顯示下載進度條。
   * @param {number|null|undefined} expectedTotalBytes 未壓縮 JSON 位元組數（來自 .hash 的 size）；
   *   勿使用 HTTP Content-Length（gzip 時為壓縮大小，與 body stream 單位不一致）。
   * @param {HTMLElement} searchStatus 狀態容器
   */
  async function loadSearchIndexWithProgress(expectedTotalBytes, searchStatus) {
    const indexFile = getSearchIndexFile();
    const isTrad = isTraditionalChinesePage();
    const total = (typeof expectedTotalBytes === 'number' && expectedTotalBytes > 0)
      ? expectedTotalBytes
      : null;

    try {
      const initialText = getI18nText('search.loadingIndex', isTrad, '正在載入搜尋索引...');
      const progress = createProgressUI(searchStatus, initialText);
      const progressBar = progress.fill.parentElement;
      if (total === null && progressBar) {
        progressBar.classList.add('is-indeterminate');
      }

      const response = await fetch(indexFile);

      if (!response.ok) {
        throw new Error(getI18nText('search.networkError', isTrad, '網路連接失敗，請檢查網路後重試'));
      }

      let loaded = 0;
      const reader = response.body.getReader();
      const chunks = [];
      let lastUiAt = 0;
      let lastPct = -1;

      const renderDownloadProgress = (force) => {
        const now = Date.now();
        const loadedMb = formatDownloadMb(loaded);
        let pct = null;
        if (total !== null) {
          pct = Math.min(100, Math.round((loaded / total) * 100));
        }
        if (!force) {
          const pctUnchanged = pct === null || pct === lastPct;
          if (now - lastUiAt < 100 && pctUnchanged) return;
        }
        lastUiAt = now;
        if (pct !== null) lastPct = pct;

        if (pct !== null) {
          const totalMb = formatDownloadMb(total);
          progress.text.textContent = getI18nText(
            'search.downloadingProgress',
            isTrad,
            '正在下載搜尋資料… ' + loadedMb + ' / ' + totalMb + ' MB（' + pct + '%）',
            { loaded: loadedMb, total: totalMb, pct: pct }
          );
          progress.fill.style.width = pct + '%';
        } else {
          progress.text.textContent = getI18nText(
            'search.downloadingBytes',
            isTrad,
            '正在下載搜尋資料… ' + loadedMb + ' MB',
            { loaded: loadedMb }
          );
        }
      };

      renderDownloadProgress(true);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        loaded += value.length;
        renderDownloadProgress(false);
      }

      if (progressBar) progressBar.classList.remove('is-indeterminate');
      progress.fill.style.width = '100%';
      progress.text.textContent = getI18nText(
        'search.processingIndex',
        isTrad,
        '正在處理搜尋索引...'
      );

      const allChunks = new Uint8Array(loaded);
      let position = 0;
      for (let i = 0; i < chunks.length; i++) {
        allChunks.set(chunks[i], position);
        position += chunks[i].length;
      }

      const text = new TextDecoder().decode(allChunks);
      const parsedIndex = JSON.parse(text);

      progress.text.textContent = getI18nText(
        'search.preparingIndex',
        isTrad,
        '準備智能搜尋索引... 即將完成'
      );

      return parsedIndex;

    } catch (error) {
      console.error('載入搜索索引失敗:', error);
      throw error;
    }
  }
  
  // 中文分词器（使用 jieba-wasm）
  let chineseSegmenter = null;
  
  // 初始化中文分词器 (jieba-wasm)
  async function initChineseSegmenter() {
    try {
      // 檢查是否已經初始化
      if (chineseSegmenter) {
        console.log(isTraditionalChinesePage() ? 
          '✅ jieba-wasm 已初始化，跳過重複初始化' : 
          '✅ jieba-wasm 已初始化，跳过重复初始化');
        return true;
      }

      // 引入 jieba_rs_wasm.js 模塊
      console.log(isTraditionalChinesePage() ? 
        '⏳ 正在載入 jieba_rs_wasm.js...' : 
        '⏳ 正在载入 jieba_rs_wasm.js...');
      
      const { default: jiebaInit, cut } = await import('./jieba_rs_wasm.js');
      await jiebaInit();
      
      chineseSegmenter = {
        cut: function(text) {
          try {
            return cut(text, true);
          } catch (error) {
            console.error('jieba-wasm 分詞錯誤:', error);
            return [];
          }
        }
      };
      
      console.log(isTraditionalChinesePage() ? 
        '✅ jieba-wasm 已啟用，支持高性能中文分詞' : 
        '✅ jieba-wasm 已启用，支持高性能中文分词');
      return true;
      
    } catch (error) {
      console.error(isTraditionalChinesePage() ? 
        '❌ jieba-wasm 初始化失敗:' : 
        '❌ jieba-wasm 初始化失败:', error);
      return false;
    }
  }
  
  // jieba-wasm 統一分詞功能
  // 分詞統計變數（調試用）
  let segmentationStats = { calls: 0, totalTime: 0 };
  
  /**
   * 使用 jieba-wasm 進行文本分詞
   * @param {string} text - 要分詞的文本
   * @param {boolean} returnArray - 是否返回數組格式（默認返回空格分隔的字符串）
   * @returns {string|Array} 分詞結果
   */
  function segmentWithJieba(text, returnArray = false) {
    if (!text || typeof text !== 'string') {
      return returnArray ? [] : '';
    }
    
    // 統計調用次數和性能
    segmentationStats.calls++;
    const startTime = performance.now();
    
    if (chineseSegmenter && chineseSegmenter.cut) {
      try {
        // 使用 jieba-wasm 分詞
        const words = chineseSegmenter.cut(text);
        
        // 記錄處理時間
        const endTime = performance.now();
        segmentationStats.totalTime += (endTime - startTime);
        
        // 每2000次調用輸出一次統計（避免日誌過多）
        if (segmentationStats.calls % 2000 === 0) {
          console.log(isTraditionalChinesePage() ? 
            `🔤 jieba-wasm 統計: ${segmentationStats.calls} 次調用, 平均耗時: ${(segmentationStats.totalTime / segmentationStats.calls).toFixed(2)}ms` :
            `🔤 jieba-wasm 统计: ${segmentationStats.calls} 次调用, 平均耗时: ${(segmentationStats.totalTime / segmentationStats.calls).toFixed(2)}ms`);
        }
        
        return returnArray ? words : words.join(' ');
      } catch (error) {
        console.error(isTraditionalChinesePage() ? 
          '❌ jieba-wasm 分詞失敗:' : 
          '❌ jieba-wasm 分词失败:', error);
        return returnArray ? [] : '';
      }
    }
    
    // jieba-wasm 不可用時的降級處理
    console.warn(isTraditionalChinesePage() ? 
      '⚠️ jieba-wasm 不可用，返回原文本' : 
      '⚠️ jieba-wasm 不可用，返回原文本');
    return returnArray ? [text] : text;
  }
// ============================================================
// 01b-search-index.js — 搜索索引构建（分批分词、缓存集成）
// ============================================================

// 創建搜索配置
function createSearchConfig(segmenterEnabled) {
  if (segmenterEnabled) {
    return {
      fields: ['processedContent'],
      storeFields: ['id', 'title', 'type', 'content', 'processedContent', 'context', 'url'],
      searchOptions: {
        boost: { processedContent: 1 },
        combineWith: 'AND'
      },
    };
  } else {
    return {
      fields: ['content'],
      storeFields: ['id', 'title', 'type', 'content', 'context', 'url'],
      searchOptions: {
        boost: { content: 1 },
        combineWith: 'AND'
      }
    };
  }
}

// 创建统一的进度条 UI（返回 { container, fill, text }）
function createProgressUI(searchStatus, initialText) {
  const container = document.createElement('div');
  container.className = 'search-progress-container';
  container.innerHTML = `
    <div class="search-loading-text">${initialText}</div>
    <div class="search-progress-bar">
      <div class="search-progress-fill" style="width: 0%"></div>
    </div>
  `;
  searchStatus.innerHTML = '';
  searchStatus.appendChild(container);
  return {
    container,
    fill: container.querySelector('.search-progress-fill'),
    text: container.querySelector('.search-loading-text'),
  };
}

// 分批建立搜索索引（含即時分詞）
async function buildSearchIndexInBatches(miniSearch, searchIndex, searchStatus, segmenterEnabled) {
  console.time('📇 分詞+索引建立時間 (分批處理)');
  const isTrad = isTraditionalChinesePage();
  console.log(isTrad
    ? `🔄 開始分批分詞並建立索引 ${searchIndex.length} 條記錄...`
    : `🔄 开始分批分词并建立索引 ${searchIndex.length} 条记录...`);

  const BATCH_SIZE = 300;
  const totalBatches = Math.ceil(searchIndex.length / BATCH_SIZE);
  const initialText = isTrad
    ? `📊 正在分詞並建立搜尋索引...0/${searchIndex.length}`
    : `📊 正在分词并建立搜索索引...0/${searchIndex.length}`;
  const progress = createProgressUI(searchStatus, initialText);

  for (let i = 0; i < totalBatches; i++) {
    const startIdx = i * BATCH_SIZE;
    const endIdx = Math.min(startIdx + BATCH_SIZE, searchIndex.length);
    const batch = searchIndex.slice(startIdx, endIdx).map(doc => {
      const processed = { ...doc };
      if (segmenterEnabled && doc.content) {
        processed.processedContent = segmentWithJieba(doc.content);
      } else {
        processed.processedContent = doc.content;
      }
      return processed;
    });

    miniSearch.addAll(batch);

    const pct = Math.round((endIdx / searchIndex.length) * 100);
    progress.fill.style.width = `${pct}%`;
    progress.text.textContent = isTrad
      ? `📊 正在分詞並建立搜尋索引...${endIdx}/${searchIndex.length}`
      : `📊 正在分词并建立搜索索引...${endIdx}/${searchIndex.length}`;

    await new Promise(resolve => setTimeout(resolve, 15));
  }

  searchStatus.removeChild(progress.container);
  console.timeEnd('📇 分詞+索引建立時間 (分批處理)');
  console.log('✅ 索引建立完成！');
}

// 分批建立索引並收集處理後數據（供緩存使用）
async function buildSearchIndexInBatchesAndCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, processedItems) {
  console.time('📇 分詞+索引建立時間 (分批處理)');
  const isTrad = isTraditionalChinesePage();
  console.log(isTrad
    ? `🔄 開始分批分詞並建立索引 ${searchIndex.length} 條記錄...`
    : `🔄 开始分批分词并建立索引 ${searchIndex.length} 条记录...`);

  const BATCH_SIZE = 300;
  const totalItems = searchIndex.length;
  const initialText = isTrad
    ? `📊 正在分詞並建立搜尋索引...0/${totalItems}`
    : `📊 正在分词并建立搜索索引...0/${totalItems}`;
  const progress = createProgressUI(searchStatus, initialText);

  for (let i = 0; i < totalItems; i += BATCH_SIZE) {
    const batch = searchIndex.slice(i, i + BATCH_SIZE);
    const processedBatch = [];

    for (const doc of batch) {
      const processed = { ...doc };
      if (segmenterEnabled && doc.content) {
        processed.processedContent = segmentWithJieba(doc.content);
      }
      processedBatch.push(processed);
      processedItems.push(processed);
    }

    miniSearch.addAll(processedBatch);

    const prog = Math.min(i + BATCH_SIZE, totalItems);
    const pct = Math.round((prog / totalItems) * 100);
    progress.fill.style.width = `${pct}%`;
    progress.text.textContent = isTrad
      ? `📊 正在分詞並建立搜尋索引...${prog}/${totalItems}`
      : `📊 正在分词并建立搜索索引...${prog}/${totalItems}`;

    await new Promise(resolve => setTimeout(resolve, 15));
  }

  console.timeEnd('📇 分詞+索引建立時間 (分批處理)');
  console.log('✅ 索引建立完成！');
}

// 支持緩存的索引建立（優先嘗試從緩存恢復）
async function buildSearchIndexInBatchesWithCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, cacheManager, isTraditional) {
  const isTrad = isTraditionalChinesePage();

  let currentHash = null;
  if (cacheManager) {
    const hashKey = `hash_${isTraditional ? 'trad' : 'simp'}`;
    const hashData = await cacheManager.getMetadata(hashKey);
    currentHash = hashData ? hashData.hash : null;
  }

  let processedData = null;
  if (cacheManager && currentHash) {
    processedData = await cacheManager.getCachedProcessedIndex(isTraditional, segmenterEnabled, currentHash);
  }

  if (processedData) {
    console.time('📇 從緩存恢復索引');
    console.log('⚡ 從緩存恢復處理後的搜索索引...');
    try {
      const BATCH_SIZE = 1000;
      const totalItems = processedData.length;
      const initialText = isTrad
        ? `⚡ 從緩存恢復處理後的搜索索引...0/${totalItems}`
        : `⚡ 从缓存恢复处理后的搜索索引...0/${totalItems}`;
      const progress = createProgressUI(searchStatus, initialText);

      for (let i = 0; i < totalItems; i += BATCH_SIZE) {
        miniSearch.addAll(processedData.slice(i, i + BATCH_SIZE));
        const prog = Math.min(i + BATCH_SIZE, totalItems);
        const pct = Math.round((prog / totalItems) * 100);
        progress.fill.style.width = `${pct}%`;
        progress.text.textContent = isTrad
          ? `⚡ 從緩存恢復處理後的搜索索引...${prog}/${totalItems}`
          : `⚡ 从缓存恢复处理后的搜索索引...${prog}/${totalItems}`;
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      console.timeEnd('📇 從緩存恢復索引');
      console.log(isTrad ? '⚡ 從緩存快速恢復索引完成！' : '⚡ 从缓存快速恢复索引完成！');
    } catch (error) {
      console.warn('從緩存恢復失敗，將重新建立索引:', error);
      await buildSearchIndexInBatches(miniSearch, searchIndex, searchStatus, segmenterEnabled);
    }
  } else {
    console.log('🔄 執行完整的分詞和索引建立流程...');
    const processedItems = [];
    await buildSearchIndexInBatchesAndCache(miniSearch, searchIndex, searchStatus, segmenterEnabled, processedItems);
    if (cacheManager && processedItems.length > 0) {
      console.log('💾 保存處理後的索引到緩存...');
      await cacheManager.cacheProcessedIndex(processedItems, isTraditional, segmenterEnabled, currentHash);
    }
  }
}
// ============================================================
// 01c-search-highlight.js — 搜索结果高亮 & 上下文提取
// ============================================================

// 转义 HTML 特殊字符
function escapeHtml(str) {
  if (!str || typeof str !== 'string') return '';
  try {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  } catch (e) {
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;');
  }
}

// 转义正则表达式特殊字符
function escapeRegex(str) {
  if (!str || typeof str !== 'string') return '';
  const chars = {
    '\\': '\\\\', '.': '\\.', '*': '\\*', '+': '\\+', '?': '\\?',
    '^': '\\^', '$': '\\$', '{': '\\{', '}': '\\}', '(': '\\(',
    ')': '\\)', '|': '\\|', '[': '\\[', ']': '\\]', '/': '\\/'
  };
  let result = str;
  Object.keys(chars).forEach(c => { result = result.split(c).join(chars[c]); });
  return result;
}

// 智能获取最佳 context 用于高亮显示
function getBestContextForHighlight(result, query) {
  if (!query || !result.content) return result.context || result.content;

  const term = query.trim();
  const content = result.content;
  const lowerContent = content.toLowerCase();
  const lowerTerm = term.toLowerCase();

  if (!result.context) return content;
  if (result.context.toLowerCase().includes(lowerTerm)) return result.context;

  const exactIndex = lowerContent.indexOf(lowerTerm);
  if (exactIndex !== -1) return extractContextAroundPosition(content, exactIndex, 120);

  const keywords = extractKeywords(term);
  if (keywords.length > 1) return generateMultiKeywordContext(content, buildKeywordPositions(content, keywords), 150);

  return result.context || result.content;
}

function buildKeywordPositions(content, keywords) {
  const lowerContent = content.toLowerCase();
  const positions = [];
  keywords.forEach(kw => {
    const lw = kw.toLowerCase();
    let idx = lowerContent.indexOf(lw);
    while (idx !== -1) {
      positions.push({ keyword: kw, position: idx, length: kw.length });
      idx = lowerContent.indexOf(lw, idx + 1);
    }
  });
  return positions;
}

// 提取关键词（支持空格分割和中文简单分词）
function extractKeywords(searchTerm) {
  const cleaned = searchTerm.trim().replace(/\s+/g, ' ');
  const spaceWords = cleaned.split(' ').filter(w => w.length > 0);
  if (spaceWords.length > 1) return spaceWords;

  const keywords = [];
  const text = cleaned;
  if (text.length <= 4) {
    for (let i = 0; i < text.length; i += 2) {
      const w = text.substr(i, 2);
      if (w.length >= 2) keywords.push(w);
    }
  } else {
    for (let i = 0; i < text.length - 1; i++) {
      const w3 = text.substr(i, 3);
      const w2 = text.substr(i, 2);
      if (i < text.length - 2 && isLikelyWord(w3)) {
        keywords.push(w3); i += 2;
      } else if (isLikelyWord(w2)) {
        keywords.push(w2); i += 1;
      }
    }
  }
  return keywords.length > 0 ? keywords : [text];
}

function isLikelyWord(word) {
  return /^[\u4e00-\u9fff]+$/.test(word) && word.length >= 2;
}

// 生成包含多个关键词的 context 段落
function generateMultiKeywordContext(content, keywordPositions, maxLength) {
  if (!keywordPositions.length) return content.substring(0, maxLength);

  keywordPositions.sort((a, b) => a.position - b.position);
  const firstPos = keywordPositions[0].position;
  const last = keywordPositions[keywordPositions.length - 1];
  const totalSpan = last.position + last.length - firstPos;

  if (totalSpan <= maxLength * 0.8) {
    const start = Math.max(0, firstPos - Math.floor((maxLength - totalSpan) / 2));
    const end = Math.min(content.length, start + maxLength);
    let ctx = content.substring(start, end);
    if (start > 0) ctx = '...' + ctx;
    if (end < content.length) ctx += '...';
    return ctx;
  }

  const important = selectImportantPositions(keywordPositions, maxLength);
  return important.map(pos => {
    const partLen = Math.floor(maxLength / important.length);
    const s = Math.max(0, pos.position - Math.floor(partLen / 2));
    const e = Math.min(content.length, s + partLen);
    let part = content.substring(s, e);
    if (s > 0) part = '...' + part;
    if (e < content.length) part += '...';
    return part;
  }).join(' ');
}

function selectImportantPositions(positions, maxLength) {
  const selected = [];
  for (const pos of positions) {
    if (!selected.some(s => Math.abs(s.position - pos.position) < 20)) {
      selected.push(pos);
    }
    if (selected.length >= 3) break;
  }
  return selected.length > 0 ? selected : [positions[0]];
}

// 从指定位置提取上下文（智能裁剪到词边界）
function extractContextAroundPosition(text, position, maxLength) {
  const half = Math.floor(maxLength / 2);
  let start = Math.max(0, position - half);
  let end = Math.min(text.length, position + half);

  if (start > 0) {
    const before = text.substring(start - 10, start);
    const si = before.lastIndexOf(' ');
    const pi = Math.max(before.lastIndexOf('。'), before.lastIndexOf('，'), before.lastIndexOf('！'), before.lastIndexOf('？'));
    if (si !== -1 || pi !== -1) start = start - 10 + Math.max(si, pi) + 1;
  }
  if (end < text.length) {
    const after = text.substring(end, end + 10);
    const si = after.indexOf(' ');
    const pi = Math.min(
      after.indexOf('。') !== -1 ? after.indexOf('。') : Infinity,
      after.indexOf('，') !== -1 ? after.indexOf('，') : Infinity,
      after.indexOf('！') !== -1 ? after.indexOf('！') : Infinity,
      after.indexOf('？') !== -1 ? after.indexOf('？') : Infinity
    );
    if (si !== -1 || pi !== Infinity) end += Math.min(si !== -1 ? si : Infinity, pi);
  }

  let ctx = text.substring(start, end);
  if (start > 0) ctx = '...' + ctx;
  if (end < text.length) ctx += '...';
  return ctx;
}

// 智能高亮搜索词（支持精确 / 多关键词 / 模糊降级）
function highlightSearchTerm(text, searchTerm) {
  if (!text || !searchTerm || typeof text !== 'string' || typeof searchTerm !== 'string') return text;
  const term = searchTerm.trim();
  if (!term) return text;

  try {
    const exactRegex = new RegExp(`(${escapeRegex(term)})`, 'gi');
    const exact = text.replace(exactRegex, '<span class="search-result-highlight">$1</span>');
    if (exact !== text) return exact;

    const keywords = extractKeywords(term);
    if (keywords.length > 1) {
      const multi = highlightMultipleKeywords(text, keywords);
      if (multi !== text) return multi;
    }

    return highlightWithFuzzyMatching(text, term);
  } catch (e) {
    console.warn('智能高亮处理失败:', e);
    return highlightWithFuzzyMatching(text, term);
  }
}

function highlightMultipleKeywords(text, keywords) {
  let result = text;
  let hasMatch = false;
  const sorted = keywords.slice().sort((a, b) => b.length - a.length);
  sorted.forEach(kw => {
    const r = new RegExp(`(${escapeRegex(kw)})`, 'gi');
    const before = result;
    result = result.replace(r, '<span class="search-result-highlight">$1</span>');
    if (result !== before) hasMatch = true;
  });
  return hasMatch ? result : text;
}

function highlightWithFuzzyMatching(text, term) {
  try {
    const punct = '[\\s\\u3000-\\u303F\\uFF00-\\uFFEF\\u2000-\\u206F\\u0020-\\u002F\\u003A-\\u0040\\u005B-\\u0060\\u007B-\\u007E\\u2010-\\u2027\\u2030-\\u205F\\u3001-\\u3003\\u3008-\\u3011\\u3014-\\u301F\\uFE10-\\uFE19\\uFE30-\\uFE6F]';
    const flexPattern = term.split('').map(c => escapeRegex(c)).join(`${punct}*`);
    const flex = text.replace(new RegExp(`(${flexPattern})`, 'gi'), '<span class="search-result-highlight">$1</span>');
    if (flex !== text) return flex;

    const chars = term.split('');
    if (chars.length > 1) {
      const charPat = chars.map(c => escapeRegex(c)).join(`${punct}*`);
      const charResult = text.replace(new RegExp(`(${charPat})`, 'gi'), '<span class="search-result-highlight">$1</span>');
      if (charResult !== text) return charResult;
    }

    let result = text;
    chars.forEach(c => {
      if (c.trim()) result = result.replace(new RegExp(`(${escapeRegex(c)})`, 'gi'), '<span class="search-result-highlight">$1</span>');
    });
    return result;
  } catch (e) {
    console.warn('模糊高亮处理失败:', e);
    try {
      return text.replace(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), '<span class="search-result-highlight">$&</span>');
    } catch (e2) {
      return text;
    }
  }
}
// ============================================================
// 01d-search-perform.js — 搜索执行、结果展示、分页
// ============================================================

// 生成单个搜索结果 item 的 HTML
function generateSearchResultItem(result, index, indexOffset, query) {
  const typeText = {
    heading:  getI18nText('search.resultTypes.heading',  isTraditionalChinesePage(), '標題'),
    question: getI18nText('search.resultTypes.question', isTraditionalChinesePage(), '問題'),
    answer:   getI18nText('search.resultTypes.answer',   isTraditionalChinesePage(), '回答'),
    content:  getI18nText('search.resultTypes.content',  isTraditionalChinesePage(), '內容'),
  }[result.type] || getText('内容', '內容');

  const bestContext = query ? getBestContextForHighlight(result, query) : result.context;
  const highlightedContext = query ? highlightSearchTerm(bestContext, query) : bestContext;
  const globalIndex = (indexOffset || 0) + index + 1;
  const total = currentSearchResults.length;

  return `
    <li class="search-result-item" data-url="${result.url}">
      <div class="search-result-header">
        <span class="search-result-number">${globalIndex}/${total}</span>
        <span class="search-result-type">${typeText}</span>
        <div class="search-result-title">${escapeHtml(result.title)}</div>
      </div>
      <div class="search-result-content">${highlightedContext}</div>
    </li>
  `;
}

// 执行搜索
function performSearch(query) {
  const elements = getSearchElements();
  resetSearchResultsHeight();

  if (!miniSearch || !query || query.trim().length < 2) {
    elements.searchResults.style.display = 'none';
    elements.tocHeader.style.display = 'block';
    currentSearchResults = [];
    displayedResultsCount = 0;
    hideLoadMoreButtons();
    setSearchScopeVisible(false);
    if (query && query.trim().length > 0 && query.trim().length < 2) {
      elements.searchStatus.textContent = getI18nText('search.minCharWarning', isTraditionalChinesePage(), '請輸入至少2個字元進行搜尋');
    } else {
      const count = searchIndex ? searchIndex.length : 0;
      elements.searchStatus.innerHTML = getText(`搜索准备就绪 (共${count}条记录)`, `搜尋準備就緒 (共${count}條記錄)`);
    }
    return;
  }

  const trimmedQuery = query.trim();
  try {
    let searchQuery = trimmedQuery;
    const allowedTypes = searchScope === 'question' ? ['question']
      : searchScope === 'answer' ? ['answer']
      : ['question', 'answer'];
    const searchOptions = {
      boost: { processedContent: 1 },
      filter: function (result) {
        return allowedTypes.indexOf(result.type) !== -1;
      }
    };

    if (chineseSegmenter && trimmedQuery.length > 1) {
      const words = segmentWithJieba(trimmedQuery, true);
      if (words.length > 0) searchQuery = words.join(' ');
    }

    const results = miniSearch.search(searchQuery, searchOptions);
    results.sort((a, b) => b.score - a.score);

    currentSearchResults = results;
    displayedResultsCount = 0;

    if (results.length > 0) {
      resetSearchResultsHeight();
      displayPagedResults(trimmedQuery);
      setSearchScopeVisible(true);
    } else {
      displayNoResults(trimmedQuery, elements);
      elements.searchStatus.textContent = getText('未找到匹配结果', '未找到匹配結果');
      // 若使用者已透過有結果的搜尋打開過範圍選項，保留可見以免切換後無法切回
      const scopeEl = document.querySelector('.search-scope');
      if (!(scopeEl && scopeEl.classList.contains('is-visible'))) {
        setSearchScopeVisible(false);
      }
    }

    elements.searchResults.style.display = 'block';
    elements.tocHeader.style.display = 'none';
    setTimeout(updateFloatingControlsState, 10);
    setTimeout(updateBottomSearchButtonsVisibility, 10);

  } catch (error) {
    console.error('搜索出错:', error);
    elements.searchStatus.textContent = getText('搜索出现错误，请重试', '搜尋出現錯誤，請重試');
    elements.searchResults.style.display = 'none';
    elements.tocHeader.style.display = 'block';
    setSearchScopeVisible(false);
    setTimeout(updateFloatingControlsState, 10);
  }
}

// 展示第一页结果（分页）
function displayPagedResults(query) {
  const elements = getSearchElements();
  displayedResultsCount = Math.min(RESULTS_PER_PAGE, currentSearchResults.length);
  const resultsToShow = currentSearchResults.slice(0, displayedResultsCount);
  elements.searchResultsList.innerHTML = resultsToShow.map((r, i) =>
    generateSearchResultItem(r, i, 0, query)
  ).join('');
  updateResultsCounter();
  updateLoadMoreButtons();
  const total = currentSearchResults.length;
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${total} 条匹配结果`, `找到 ${total} 條匹配結果`);
}

// 加载更多结果（每次追加 RESULTS_PER_PAGE 条）
function loadMoreResults() {
  const elements = getSearchElements();
  const startIndex = displayedResultsCount;
  const endIndex = Math.min(startIndex + RESULTS_PER_PAGE, currentSearchResults.length);
  const batch = currentSearchResults.slice(startIndex, endIndex);
  if (!batch.length) return;

  displayedResultsCount = endIndex;
  const query = document.getElementById('search-input').value.trim();
  const additionalHTML = batch.map((r, i) =>
    generateSearchResultItem(r, i, startIndex, query)
  ).join('');
  elements.searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);

  expandSearchResultsHeight();
  updateResultsCounter();
  updateLoadMoreButtons();
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${currentSearchResults.length} 条匹配结果`, `找到 ${currentSearchResults.length} 條匹配結果`);
}

// 加载所有剩余结果
function loadAllResults() {
  const elements = getSearchElements();
  const remaining = currentSearchResults.slice(displayedResultsCount);
  if (!remaining.length) return;

  const startIndex = displayedResultsCount;
  displayedResultsCount = currentSearchResults.length;
  const query = document.getElementById('search-input').value.trim();
  const additionalHTML = remaining.map((r, i) =>
    generateSearchResultItem(r, i, startIndex, query)
  ).join('');
  elements.searchResultsList.insertAdjacentHTML('beforeend', additionalHTML);

  expandSearchResultsHeight();
  updateResultsCounter();
  updateLoadMoreButtons();
  const el = document.getElementById('search-status');
  if (el) el.textContent = getText(`找到 ${currentSearchResults.length} 条匹配结果`, `找到 ${currentSearchResults.length} 條匹配結果`);
}

// 显示无结果占位符
function displayNoResults(query, elements) {
  const el = elements || getSearchElements();
  el.searchResultsCount.textContent = getText('未找到结果', '未找到結果');
  el.searchResultsList.innerHTML = `
    <li class="search-result-item" style="text-align: center; color: #999;">
      <div>${getText(`未找到包含"${escapeHtml(query)}"的内容`, `未找到包含"${escapeHtml(query)}"的內容`)}</div>
      <div style="font-size: 12px; margin-top: 8px;">${getText('尝试使用不同的关键词', '嘗試使用不同的關鍵詞')}</div>
    </li>
  `;
}

// 更新结果计数器文本
function updateResultsCounter() {
  const elements = getSearchElements();
  if (elements.searchResultsCount) {
    elements.searchResultsCount.textContent = getText(
      `显示 ${displayedResultsCount} / ${currentSearchResults.length} 条结果`,
      `顯示 ${displayedResultsCount} / ${currentSearchResults.length} 條結果`
    );
  }
}
// ============================================================
// 01e-search-ui.js — 搜索 UI 状态管理、initSearch、事件绑定
// ============================================================

// 获取搜索相关的 DOM 元素
function getSearchElements() {
  return {
    searchContainer:    document.getElementById('search-container'),
    searchActivation:   document.querySelector('.search-activation'),
    searchInput:        document.getElementById('search-input'),
    searchStatus:       document.getElementById('search-status'),
    searchResults:      document.getElementById('search-results'),
    searchResultsList:  document.getElementById('search-results-list'),
    searchResultsCount: document.getElementById('search-results-count'),
    searchClear:        document.getElementById('search-clear'),
    searchCollapse:     document.getElementById('search-collapse'),
    tocHeader:          document.getElementById('toc-header'),
  };
}

// 初始化搜索 UI（显示容器；进度条由下载／建索引阶段自行挂载）
function initializeSearchUI(elements) {
  if (elements.searchActivation) elements.searchActivation.style.display = 'none';
  elements.searchContainer.style.display = 'block';
  elements.searchStatus.innerHTML = '';
  const loadingUI = createLoadingUI(elements.searchStatus);
  if (loadingUI.textElement) {
    loadingUI.textElement.textContent = getI18nText(
      'search.loading',
      isTraditionalChinesePage(),
      '正在載入搜尋功能，請稍候...'
    );
  }
  return loadingUI;
}

// 更新「显示更多」按钮的显示状态
function updateLoadMoreButtons() {
  if (typeof displayedResultsCount === 'undefined' || typeof currentSearchResults === 'undefined') return;
  const shouldShow = displayedResultsCount < currentSearchResults.length;
  ['search-load-more', 'search-load-all', 'search-load-more-bottom', 'search-load-all-bottom'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.style.display = shouldShow ? 'inline-block' : 'none';
  });
}

// 隐藏所有「显示更多」按钮
function hideLoadMoreButtons() {
  ['search-load-more', 'search-load-all', 'search-load-more-bottom', 'search-load-all-bottom'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.style.display = 'none';
  });
}

// 搜索结果列表高度工具函数（预设无限制，保留兼容性）
function initializeSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; }
}
function expandSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; list.setAttribute('data-expanded', 'true'); }
}
function resetSearchResultsHeight() {
  const list = document.querySelector('.search-results-list');
  if (list) { list.style.maxHeight = 'none'; list.style.overflowY = 'visible'; list.removeAttribute('data-expanded'); }
}

// 完成搜索初始化设置（更新状态、启用输入框）
function finalizeSearchSetup(elements, segmenterEnabled, indexLength) {
  const isTrad = isTraditionalChinesePage();
  const segStatus = segmenterEnabled
    ? (isTrad ? '智能中文分詞已啟用' : '智能中文分词已启用')
    : (isTrad ? '使用傳統搜尋模式' : '使用传统搜索模式');

  console.timeEnd('🚀 搜索初始化總時間');
  console.log(isTrad ? '🎉 搜尋初始化流程完成！' : '🎉 搜索初始化流程完成！');

  elements.searchStatus.innerHTML = `
    <div class="search-status-success">
      ✅ ${getI18nText('search.indexReady', isTrad, '搜尋準備就緒 (共{count}條記錄)', { count: indexLength })}
      <br><small>🔧 ${segStatus}</small>
    </div>
  `;
  searchInitialized = true;
  initializeSearchResultsHeight();
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.search_placeholder', isTrad, '搜尋全文內容...');
  const activateBtn = document.getElementById('search-activate-btn');
  if (activateBtn) activateBtn.disabled = false;
  setTimeout(() => elements.searchInput.focus(), 100);
}

// 处理搜索初始化错误
function handleSearchInitError(elements, error) {
  const isTrad = isTraditionalChinesePage();
  console.error('搜索初始化失败:', error);
  elements.searchStatus.innerHTML = '';
  createErrorUI(elements.searchStatus, error.message || getI18nText('search.loadingFailed', isTrad, '搜尋索引載入失敗'), async () => {
    await initSearch();
  });
  elements.searchInput.disabled = false;
  elements.searchInput.placeholder = getI18nText('search.searchUnavailable', isTrad, '搜尋功能暫不可用');
  const activateBtn = document.getElementById('search-activate-btn');
  if (activateBtn) activateBtn.disabled = false;
}

// 搜尋範圍選項：僅在有結果時顯示，保持載入／空輸入時介面乾淨
function setSearchScopeVisible(visible) {
  const scopeEl = document.querySelector('.search-scope');
  if (!scopeEl) return;
  scopeEl.classList.toggle('is-visible', !!visible);
}

// 清除搜索状态（重置输入框、结果、计数）
function clearSearch() {
  const elements = getSearchElements();
  if (elements.searchInput) elements.searchInput.value = '';
  if (elements.searchResults) elements.searchResults.style.display = 'none';
  if (elements.tocHeader) elements.tocHeader.style.display = 'block';
  currentSearchResults = [];
  displayedResultsCount = 0;
  hideLoadMoreButtons();
  resetSearchResultsHeight();
  setSearchScopeVisible(false);
  if (elements.searchStatus) {
    const count = searchIndex ? searchIndex.length : 0;
    elements.searchStatus.innerHTML = getText(`搜索准备就绪 (共${count}条记录)`, `搜尋準備就緒 (共${count}條記錄)`);
  }
}

// 收起搜索面板
function collapseSearch() {
  const searchContainer  = document.getElementById('search-container');
  const searchActivation = document.querySelector('.search-activation');
  if (!searchContainer || !searchActivation) return;

  const searchInput        = document.getElementById('search-input');
  const searchResults      = document.getElementById('search-results');
  const tocHeader          = document.getElementById('toc-header');
  const searchStatus       = document.getElementById('search-status');
  const searchResultsList  = document.getElementById('search-results-list');
  const searchResultsCount = document.getElementById('search-results-count');

  if (searchInput) searchInput.value = '';
  if (searchResults) searchResults.style.display = 'none';
  if (tocHeader) tocHeader.style.display = 'block';
  currentSearchResults = [];
  displayedResultsCount = 0;
  hideLoadMoreButtons();
  setSearchScopeVisible(false);

  if (searchStatus) searchStatus.innerHTML = '';
  if (searchResultsList) { searchResultsList.innerHTML = ''; searchResultsList.style.maxHeight = ''; searchResultsList.style.overflowY = ''; }
  if (searchResultsCount) searchResultsCount.textContent = '';
  if (searchResults) searchResults.style.maxHeight = '';

  searchContainer.style.display = 'none';
  searchActivation.style.display = 'block';
  setTimeout(updateFloatingControlsState, 10);
}

// ============================================================
// initSearch — 搜索功能主入口（async）
// ============================================================
async function initSearch() {
  if (!isIndexPage()) return;

  console.time('🚀 搜索初始化總時間');
  console.log('📊 開始搜索初始化流程...');

  const elements = getSearchElements();
  if (!elements.searchInput || !elements.searchContainer) return;

  // 初始化缓存管理器
  let cacheManager = null;
  try {
    if (window.searchCacheManager) {
      await window.searchCacheManager.init();
      cacheManager = window.searchCacheManager;
      console.log('💾 緩存管理器初始化成功');
    }
  } catch (err) {
    console.warn('緩存管理器初始化失敗，將使用標準流程:', err);
  }

  try {
    initializeSearchUI(elements);

    if (typeof MiniSearch === 'undefined') throw new Error('MiniSearch库未加载');

    const segmenterEnabled = await initChineseSegmenter();
    console.log(isTraditionalChinesePage()
      ? `📝 分詞器狀態: ${segmenterEnabled ? '已啟用' : '未啟用'}`
      : `📝 分词器状态: ${segmenterEnabled ? '已启用' : '未启用'}`);

    const isTraditional = isTraditionalChinesePage();
    const isTrad = isTraditionalChinesePage();

    let needsUpdate = true;
    let hashData = null;
    if (cacheManager) {
      const updateInfo = await cacheManager.checkUpdate(isTraditional);
      needsUpdate = updateInfo.needsUpdate;
      hashData = updateInfo.hashData;
    }

    if (!needsUpdate) {
      elements.searchStatus.innerHTML = '';
      const cacheMsg = document.createElement('div');
      cacheMsg.className = 'search-loading-text';
      cacheMsg.textContent = getI18nText(
        'search.loadingFromCache',
        isTrad,
        '正在從快取載入搜尋索引…'
      );
      elements.searchStatus.appendChild(cacheMsg);
      searchIndex = await cacheManager.getCachedSearchIndex(isTraditional);
      if (!searchIndex) {
        console.log('📡 緩存數據丟失，重新下載...');
        needsUpdate = true;
      } else {
        console.log('⚡ 從緩存加載搜索索引（哈希驗證通過）');
      }
    }

    if (needsUpdate) {
      console.log('📡 從網絡加載搜索索引...');
      if (!hashData && cacheManager) {
        const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
        hashData = await cacheManager.fetchHashFile(`${indexFileName}.hash`);
      } else if (!hashData) {
        try {
          const indexFileName = isTraditional ? 'search_index_trad.json' : 'search_index.json';
          const hashResp = await fetch(`${indexFileName}.hash`);
          if (hashResp.ok) hashData = await hashResp.json();
        } catch (e) { /* 無 hash 時改顯示位元組進度 */ }
      }
      const expectedSize = hashData && typeof hashData.size === 'number' ? hashData.size : null;
      searchIndex = await loadSearchIndexWithProgress(expectedSize, elements.searchStatus);
      if (cacheManager && searchIndex) {
        await cacheManager.cacheSearchIndex(searchIndex, isTraditional);
        if (hashData) {
          await cacheManager.saveHashMetadata(hashData, isTraditional);
          console.log('🗑️ 清除舊的處理後索引緩存...');
          await cacheManager.clearOldProcessedIndexes(isTraditional, hashData.hash);
        }
      }
    }

    console.log(`📋 索引記錄數: ${searchIndex.length}`);

    const searchConfig = createSearchConfig(segmenterEnabled);
    miniSearch = new MiniSearch(searchConfig);

    await buildSearchIndexInBatchesWithCache(miniSearch, searchIndex, elements.searchStatus, segmenterEnabled, cacheManager, isTraditional);
    finalizeSearchSetup(elements, segmenterEnabled, searchIndex.length);

  } catch (error) {
    handleSearchInitError(elements, error);
    return;
  }

  // 搜索输入防抖
  let searchTimeout;
  elements.searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();
    searchTimeout = setTimeout(() => performSearch(query), 300);
  });

  // 搜尋範圍：問題 / 回答 / 兩者
  document.querySelectorAll('.search-scope-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const scope = btn.getAttribute('data-scope');
      if (!scope || scope === searchScope) return;
      searchScope = scope;
      document.querySelectorAll('.search-scope-btn').forEach((b) => {
        const active = b.getAttribute('data-scope') === searchScope;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      const query = elements.searchInput.value.trim();
      if (query.length >= 2) performSearch(query);
    });
  });

  // 清除 / 收起按钮
  if (elements.searchClear) elements.searchClear.addEventListener('click', clearSearch);
  if (elements.searchCollapse) elements.searchCollapse.addEventListener('click', collapseSearch);

  // 显示更多 / 全部按钮（顶部 + 底部）
  [['search-load-more', loadMoreResults], ['search-load-all', loadAllResults],
   ['search-load-more-bottom', loadMoreResults], ['search-load-all-bottom', loadAllResults],
   ['search-clear-bottom', clearSearch], ['search-collapse-bottom', collapseSearch]
  ].forEach(([id, fn]) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', fn);
  });

  // 结果列表点击（在新标签打开）
  elements.searchResultsList.addEventListener('click', (e) => {
    const item = e.target.closest('.search-result-item');
    if (item && item.dataset.url) {
      window.open(item.dataset.url, '_blank', 'noopener,noreferrer');
    }
  });
}

// ============================================================
// 首页搜索激活按钮监听（模块加载后绑定）
// ============================================================
if (isIndexPage()) {
  const searchActivateBtn = document.getElementById('search-activate-btn');
  if (searchActivateBtn) {
    searchActivateBtn.addEventListener('click', activateSearch);
  }
}
  // ============ 功能實現 ============
  
  // 生成內容的簡單hash（與Python端保持一致，使用MD5前12位）
  function simpleHash(str) {
    // 注意：這是一個簡化版本，實際應該使用與Python端相同的MD5算法
    // 為了保持一致性，我們暫時使用相同的邏輯結構
    let hash = 0;
    if (str.length === 0) return '000000000000';
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 轉換為32位整數
    }
    // 將hash轉換為12位16進制字符串，模擬MD5前12位
    const hexHash = Math.abs(hash).toString(16).padStart(12, '0').substring(0, 12);
    return hexHash;
  }
  
  // 標準化文本內容，提高ID生成的穩定性
  function normalizeTextForId(text) {
    if (!text) return '';
    
    return text
      .trim()                                    // 移除首尾空白
      .replace(/[\\r\\n\\t]/g, ' ')              // 替換換行符和制表符為空格
      .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');  // 處理HTML實體，與Python端保持一致
  }
  
  // 生成穩定的內容ID
  function generateStableContentId(questioner, content, time) {
    // 標準化各個組件
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    
    // 標準化時間：只保留數字部分
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    // 組合穩定的標識內容：人名 + 時間 + 前50個字（與Python端保持一致）
    const stableContent = normalizedQuestioner + 
                         normalizedTime +
                         normalizedContent.substring(0, 50); // 改為50字符，與用戶要求一致
    
    return simpleHash(stableContent);
  }
  
  // 生成兼容性的舊版ID（用於遷移）
  function generateLegacyContentId(questioner, content, time) {
    // 使用舊的邏輯生成ID，用於查找現有書籤
    const contentText = questioner + content + time;
    return simpleHash(contentText);
  }
  
  // 生成舊版80字符邏輯的ID（用於向後兼容）
  function generateLegacy80CharId(questioner, content, time) {
    // 舊的邏輯：人名 + 前80字符 + 時間
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    const stableContent = normalizedQuestioner + 
                         normalizedContent.substring(0, 80) + // 舊的80字符
                         normalizedTime;
    
    return simpleHash(stableContent);
  }
  
  // 嘗試查找元素的多種ID策略
  function findElementByMultipleIds(questioner, content, time, prefix = 'qa') {
    // 1. 先嘗試新的穩定ID（人名+時間+前50字）
    const stableId = prefix + '-' + generateStableContentId(questioner, content, time);
    let element = document.getElementById(stableId);
    
    if (!element) {
      // 2. 嘗試舊的80字符邏輯
      const legacy80Id = prefix + '-' + generateLegacy80CharId(questioner, content, time);
      element = document.getElementById(legacy80Id);
    }
    
    if (!element) {
      // 3. 嘗試最原始的舊ID邏輯
      const legacyId = prefix + '-' + generateLegacyContentId(questioner, content, time);
      element = document.getElementById(legacyId);
    }
    
    return element;
  }
  
  // 確保元素有唯一且穩定的ID
  function ensureElementId(element, prefix = 'qa') {
    if (!element.id) {
      let questioner = '', content = '', time = '';
      
      if (element.classList.contains('question')) {
        questioner = element.querySelector('.questioner')?.textContent || '';
        content = element.querySelector('.question-text')?.textContent || '';
        time = element.querySelector('.question-time')?.textContent || '';
      } else if (element.classList.contains('answer')) {
        questioner = element.querySelector('.answerer')?.textContent || '';
        content = element.querySelector('.answer-text')?.textContent || '';
        // 答案通常沒有時間，使用空字符串
        time = '';
      }
      
      // 使用新的穩定ID生成邏輯
      const stableHash = generateStableContentId(questioner, content, time);
      element.id = prefix + '-' + stableHash;
    }
    return element.id;
  }
  
  // 生成分享URL
  function generateShareUrl(targetElement) {
    const prefix = targetElement.classList.contains('question') ? 'question' : 'answer';
    const elementId = ensureElementId(targetElement, prefix);
    const baseUrl = window.location.origin + window.location.pathname;
    return baseUrl + '#' + elementId;
  }
  
  // 找到問答配對
  function findQuestionForAnswer(answerElement) {
    let currentElement = answerElement.previousElementSibling;
    
    // 向上查找最近的問題元素
    while (currentElement) {
      if (currentElement.classList.contains('question')) {
        return currentElement;
      }
      currentElement = currentElement.previousElementSibling;
    }
    
    return null;
  }
  
  function findAnswerForQuestion(questionElement) {
    let currentElement = questionElement.nextElementSibling;
    
    // 向下查找最近的回答元素
    while (currentElement) {
      if (currentElement.classList.contains('answer')) {
        return currentElement;
      }
      currentElement = currentElement.nextElementSibling;
    }
    
    return null;
  }
  
  // 獲取問答的完整文本
  function getQAPairText(element) {
    let questionElement, answerElement;
    let text = '';
    
    // 判断传入的是问题还是答案元素
    if (element.classList.contains('question')) {
      questionElement = element;
      answerElement = findAnswerForQuestion(element);
    } else if (element.classList.contains('answer')) {
      answerElement = element;
      questionElement = findQuestionForAnswer(element);
    }
    
    // 提取問題內容
    if (questionElement) {
      const questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
      const questionTime = questionElement.querySelector('.question-time')?.textContent || '';
      const questionText = questionElement.querySelector('.question-text')?.textContent || '';
      
      text += `問：${questioner}`;
      if (questionTime) text += ` (${questionTime})`;
      text += `\n${questionText}\n\n`;
    }
    
    // 提取回答內容
    if (answerElement) {
      const answerer = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      
      text += `答：${answerer}\n${answerText}`;
    }
    
    return text;
  }
  
  // 創建閱讀工具欄
  function createReadingToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'reading-toolbar hidden';
    toolbar.innerHTML = 
      '<div class="toolbar-header">' +
        '<span>⚙️ ' + getI18nText('readingSettings.title', isTraditionalChinesePage(), '閱讀設置') + '</span>' +
        '<button class="ctrl-btn" data-action="close-toolbar">✕</button>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + 
          getI18nText('readingSettings.fontSize', isTraditionalChinesePage(), '字體大小') + 
        '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn font-adjust" data-action="font-decrease" title="縮小字體">' + getI18nText('readingSettings.fontDecrease', isTraditionalChinesePage(), 'A-') + '</button>' +
          '<button class="ctrl-btn font-option active" data-action="font-normal" title="重置為默認字體">' + getI18nText('readingSettings.fontNormal', isTraditionalChinesePage(), 'A') + '</button>' +
          '<button class="ctrl-btn font-adjust" data-action="font-increase" title="放大字體">' + getI18nText('readingSettings.fontIncrease', isTraditionalChinesePage(), 'A+') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.lineHeight', isTraditionalChinesePage(), '行距') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="line-tight">' + getI18nText('readingSettings.lineTight', isTraditionalChinesePage(), '緊密') + '</button>' +
          '<button class="ctrl-btn active" data-action="line-normal">' + getI18nText('readingSettings.lineNormal', isTraditionalChinesePage(), '正常') + '</button>' +
          '<button class="ctrl-btn" data-action="line-loose">' + getI18nText('readingSettings.lineLoose', isTraditionalChinesePage(), '寬鬆') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.width', isTraditionalChinesePage(), '寬度') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="width-narrow">' + getI18nText('readingSettings.widthNarrow', isTraditionalChinesePage(), '窄') + '</button>' +
          '<button class="ctrl-btn active" data-action="width-normal">' + getI18nText('readingSettings.widthNormal', isTraditionalChinesePage(), '中') + '</button>' +
          '<button class="ctrl-btn" data-action="width-wide">' + getI18nText('readingSettings.widthWide', isTraditionalChinesePage(), '寬') + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">' + getI18nText('readingSettings.theme', isTraditionalChinesePage(), '主題') + '</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="theme-light">' + getI18nText('readingSettings.themeLight', isTraditionalChinesePage(), '☀️ 日間') + '</button>' +
          '<button class="ctrl-btn" data-action="theme-dark">' + getI18nText('readingSettings.themeDark', isTraditionalChinesePage(), '🌙 夜間') + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(toolbar);
    return toolbar;
  }
  
  // 更新主題按鈕狀態
  function updateThemeButtons() {
    const isDark = document.body.classList.contains('dark-mode');
    const lightBtn = document.querySelector('[data-action="theme-light"]');
    const darkBtn = document.querySelector('[data-action="theme-dark"]');
    
    if (lightBtn && darkBtn) {
      lightBtn.classList.toggle('active', !isDark);
      darkBtn.classList.toggle('active', isDark);
    }
  }

  // 更新閱讀設置按鈕狀態
  function updateReadingSettingsButtons() {
    updateFontSizeButtons();
    updateLineHeightButtons();
    updateContentWidthButtons();
  }

  // 更新字體大小按鈕狀態
  function updateFontSizeButtons() {
    // 只更新選項按鈕的狀態，不影響調整按鈕
    const fontOptionBtns = document.querySelectorAll('[data-action^="font-"].font-option');
    fontOptionBtns.forEach(btn => btn.classList.remove('active'));
    
    // 根據當前字體大小標記對應按鈕
    const defaultFontSize = getDefaultFontSize();
    if (fontSize === defaultFontSize || fontSize === 16) {
      const normalBtn = document.querySelector('[data-action="font-normal"]');
      if (normalBtn) normalBtn.classList.add('active');
    }
    
    // A- 和 A+ 按鈕使用 font-adjust 類，不參與 active 狀態管理
  }

  // 更新行距按鈕狀態
  function updateLineHeightButtons() {
    const lineHeightBtns = document.querySelectorAll('[data-action^="line-"]');
    lineHeightBtns.forEach(btn => btn.classList.remove('active'));
    
    let activeLineHeightBtn = null;
    if (lineHeight === 1.2) {
      activeLineHeightBtn = document.querySelector('[data-action="line-tight"]');
    } else if (lineHeight === 1.6) {
      activeLineHeightBtn = document.querySelector('[data-action="line-normal"]');
    } else if (lineHeight === 2.0) {
      activeLineHeightBtn = document.querySelector('[data-action="line-loose"]');
    }
    
    if (activeLineHeightBtn) {
      activeLineHeightBtn.classList.add('active');
    }
  }

  // 更新內容寬度按鈕狀態
  function updateContentWidthButtons() {
    const widthBtns = document.querySelectorAll('[data-action^="width-"]');
    widthBtns.forEach(btn => btn.classList.remove('active'));
    
    let activeWidthBtn = null;
    if (contentWidth === 600) {
      activeWidthBtn = document.querySelector('[data-action="width-narrow"]');
    } else if (contentWidth === 800) {
      activeWidthBtn = document.querySelector('[data-action="width-normal"]');
    } else if (contentWidth === 1000) {
      activeWidthBtn = document.querySelector('[data-action="width-wide"]');
    }
    
    if (activeWidthBtn) {
      activeWidthBtn.classList.add('active');
    }
  }

  // 創建閱讀進度條
  function createReadingProgress() {
    const progress = document.createElement('div');
    progress.className = 'reading-progress';
    progress.innerHTML = '<div class="reading-progress-bar"></div>';
    document.body.appendChild(progress);
    return progress;
  }

  // 創建浮動目錄
  function createFloatingTOC() {
    const toc = document.createElement('div');
    toc.className = 'floating-toc';
    
    let tocItems = '';
    
    if (currentChapter.isHomepage) {
      // 首頁：從TOC連結提取目錄結構
      const tocLinks = document.querySelectorAll('h2 + ul li a, ul li a');
      tocLinks.forEach((link, index) => {
        const text = link.textContent;
        const href = link.getAttribute('href');
        
        // 更準確的層級判斷：計算嵌套深度
        const listItem = link.closest('li');
        let level = 0;
        let currentElement = listItem.parentElement; // 从ul开始计算
        
        // 向上遍歷，計算嵌套的ul層數
        while (currentElement && currentElement.tagName === 'UL') {
          level++;
          // 跳过li，直接到下一个ul
          currentElement = currentElement.parentElement;
          if (currentElement && currentElement.tagName === 'LI') {
            currentElement = currentElement.parentElement;
          }
        }
        
        // 根據層級添加對應的class (level=1是第一层，无缩进)
        // 顯示前四層目錄，跳過第五層及以下
        if (level >= 5) {
          return; // 跳過第五層及以下的項目
        }
        
        let levelClass = '';
        if (level === 2) {
          levelClass = ' level-h3';
        } else if (level === 3) {
          levelClass = ' level-h4';
        } else if (level === 4) {
          levelClass = ' level-h5';  // Note: this maps to what would be level 4 content
        }
        
        // 為首頁TOC項目使用特殊的data屬性
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-href="' + href + '">' + text + '</div>';
      });
    } else {
      // 其他頁面：收集標題
      const headings = document.querySelectorAll('h2, h3, h4');
      headings.forEach((heading, index) => {
        const text = heading.textContent;
        const id = heading.id || ('heading-' + index);
        if (!heading.id) heading.id = id;
        
        const level = heading.tagName.toLowerCase();
        const levelClass = level !== 'h2' ? ' level-' + level : '';
        
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-target="#' + id + '">' + text + '</div>';
      });
    }
    
    // 根據是否為首頁決定標籤頁內容
    let tabsHtml = '';
    let contentHtml = '';
    
    if (currentChapter.isHomepage) {
      // 首頁只顯示書籤，不顯示目錄標籤（因為首頁本身就是目錄）
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="bookmarks">📖 ' + getI18nText('bookmark.myBookmarks', isTraditionalChinesePage(), '我的書籤') + ' <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<ul id="bookmarks-list" class="floating-toc-list" style="display: block;">' +
          '<li class="bookmarks-empty">' + getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>' +
        '</ul>';
    } else {
      // 其他頁面顯示目錄和書籤
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="toc">' + getI18nText('navigation.tableOfContents', isTraditionalChinesePage(), '目錄') + '</button>' +
        '<button class="floating-toc-tab" data-tab="bookmarks">' + getI18nText('navigation.bookmarks', isTraditionalChinesePage(), '書籤') + ' <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<ul id="toc-list" class="floating-toc-list">' +
          tocItems +
        '</ul>' +
        '<ul id="bookmarks-list" class="floating-toc-list" style="display: none;">' +
          '<li class="bookmarks-empty">' + getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>' +
        '</ul>';
    }
    
    // 根據頁面類型設定初始標題
    const initialTitle = currentChapter.isHomepage ? 
      '🔖 ' + getI18nText('bookmark.myBookmarks', isTraditionalChinesePage(), '我的書籤') : 
      '📖 ' + getI18nText('navigation.chapterDirectory', isTraditionalChinesePage(), '章節目錄');
    
    toc.innerHTML = 
      '<div class="floating-toc-header">' +
        '<span id="toc-title">' + initialTitle + '</span>' +
        '<button class="ctrl-btn" data-action="close-toc">✕</button>' +
      '</div>' +
      '<div class="floating-toc-tabs">' +
        tabsHtml +
      '</div>' +
      '<div class="floating-toc-content">' +
        contentHtml +
      '</div>';
    
    // 檢查是否已存在靜態TOC，如果有則替換，否則添加新的
    const existingTOC = document.getElementById('floating-toc');
    if (existingTOC) {
      existingTOC.parentNode.replaceChild(toc, existingTOC);
    } else {
      document.body.appendChild(toc);
    }
    return toc;
  }

  // 創建操作按鈕組
  function createActionButtons() {
    const buttons = document.createElement('div');
    buttons.className = 'action-buttons';
    
    // 根據頁面類型設置第一個按鈕的內容
    const firstBtnIcon = currentChapter.isHomepage ? '🔖' : '📖';
    const firstBtnTitle = currentChapter.isHomepage ? 
      getI18nText('navigation.bookmarks', isTraditionalChinesePage(), '書籤') : 
      getI18nText('ui.tableOfContents', isTraditionalChinesePage(), '目錄');
    
    // 為章節頁面添加回首頁按鈕
    const homeButton = currentChapter.isHomepage ? '' : 
      '<button class="action-btn" data-action="home" title="' + getI18nText('ui.home', isTraditionalChinesePage(), '回首頁') + '">🏠</button>';
    
    buttons.innerHTML = 
      '<div class="action-menu">' +
        '<button class="action-btn menu-btn" data-action="toggle-menu" title="' + getI18nText('ui.functionMenu', isTraditionalChinesePage(), '功能選單') + '">☰</button>' +
        '<div class="action-menu-items">' +
          '<button class="action-btn" data-action="toc" title="' + firstBtnTitle + '">' + firstBtnIcon + '</button>' +
          homeButton +
          '<button class="action-btn" data-action="top" title="' + getI18nText('ui.backToTop', isTraditionalChinesePage(), '回到頂部') + '">↑</button>' +
          '<button class="action-btn" data-action="settings" title="' + getI18nText('ui.settings', isTraditionalChinesePage(), '設置') + '">⚙️</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(buttons);
    return buttons;
  }

  // 為問答添加互動按鈕
  function addQAActions() {
    const qaElements = document.querySelectorAll('.question, .answer');
    qaElements.forEach((element) => {
      // 確保元素有唯一ID（用於分享功能）
      const prefix = element.classList.contains('question') ? 'question' : 'answer';
      ensureElementId(element, prefix);
      
      element.style.position = 'relative';
      const actions = document.createElement('div');
      actions.className = 'qa-actions';
      
      const isQuestion = element.classList.contains('question');
      const isAnswer = element.classList.contains('answer');
      
      // 首頁不顯示書籤按鈕
      let actionsHtml = '';
      
      if (isQuestion) {
        actionsHtml += `<button class="qa-btn" data-action="copy-qa" title="${getText('复制问答', '複製問答')}">📋</button>`;
        if (!currentChapter.isHomepage) {
          actionsHtml += `<button class="qa-btn" data-action="bookmark-qa" title="${getText('加入书签', '加入書籤')}">🔖</button>`;
        }
        actionsHtml += `<button class="qa-btn" data-action="share" title="${getText('分享问题', '分享問題')}">📤</button>`;
      } else if (isAnswer) {
        actionsHtml += `<button class="qa-btn" data-action="copy-qa" title="${getText('复制问答', '複製問答')}">📋</button>`;
        if (!currentChapter.isHomepage) {
          actionsHtml += `<button class="qa-btn" data-action="bookmark-qa" title="${getText('加入书签', '加入書籤')}">🔖</button>`;
        }
        actionsHtml += `<button class="qa-btn" data-action="share" title="${getText('分享回答', '分享回答')}">📤</button>`;
      }
      
      actions.innerHTML = actionsHtml;
      element.appendChild(actions);
    });
  }

// ============================================================
// 03a-bookmark-data.js — 书签存储、CRUD、章节检测、视觉标识
// ============================================================

// 当前文件章节信息（在 DOMContentLoaded 后设置）
let currentChapter;

// 获取当前语言版本的 localStorage 键
function getBookmarkStorageKey() {
  return isTraditionalChinesePage() ? 'ebook-bookmarks-traditional' : 'ebook-bookmarks-simplified';
}

// 迁移旧版统一书签到按语言分离的结构（只执行一次）
function migrateOldBookmarks() {
  if (localStorage.getItem('bookmarks-migrated')) return;

  const oldData = localStorage.getItem('ebook-bookmarks');
  if (!oldData) { localStorage.setItem('bookmarks-migrated', 'true'); return; }

  try {
    const all = JSON.parse(oldData);
    const simplified = all.filter(b => !(b.chapterFilename && b.chapterFilename.includes('_trad.html')));
    const traditional = all.filter(b => b.chapterFilename && b.chapterFilename.includes('_trad.html'));
    if (simplified.length) localStorage.setItem('ebook-bookmarks-simplified', JSON.stringify(simplified));
    if (traditional.length) localStorage.setItem('ebook-bookmarks-traditional', JSON.stringify(traditional));
    localStorage.removeItem('ebook-bookmarks');
    localStorage.setItem('bookmarks-migrated', 'true');
    console.log(`书签迁移完成: 简体 ${simplified.length} 个, 繁体 ${traditional.length} 个`);
  } catch (e) {
    console.error('书签迁移失败:', e);
    localStorage.setItem('bookmarks-migrated', 'true');
  }
}

// 读取书签列表（可选按章节 ID 过滤）
function getBookmarks(chapterId = null) {
  migrateOldBookmarks();
  const raw = localStorage.getItem(getBookmarkStorageKey());
  const all = raw ? JSON.parse(raw) : [];
  return chapterId ? all.filter(b => b.chapter && b.chapter.id === chapterId) : all;
}

function getCurrentChapterBookmarks() {
  return getBookmarks(currentChapter.id);
}

// 持久化书签列表并更新计数显示
function saveBookmarks(bookmarks) {
  localStorage.setItem(getBookmarkStorageKey(), JSON.stringify(bookmarks));
  updateBookmarkCount();
}

// 根据当前页面 URL 和 h1 构建章节信息对象
function getCurrentChapter() {
  const filename = (window.location.pathname.split('/').pop()) || 'index.html';
  if (filename === 'index.html' || filename === 'index_trad.html') {
    return {
      title: getI18nText('navigation.homepage', isTraditionalChinesePage(), '首頁'),
      id: 'homepage',
      isHomepage: true,
    };
  }
  const h1 = document.querySelector('h1');
  const title = (h1 ? h1.textContent.trim() : document.title) || '未知章節';
  return { title, id: filename.replace('.html', ''), filename, isHomepage: false };
}

// 为元素查找所属章节（直接使用 currentChapter）
function findChapterForElement(_element) {
  return { title: currentChapter.title, id: currentChapter.id, filename: currentChapter.filename };
}

// ------------------------------------------------------------------ //
// 视觉标识                                                            //
// ------------------------------------------------------------------ //

function addBookmarkVisualIndicator(element) {
  if (element.classList.contains('bookmarked')) return;
  element.classList.add('bookmarked');
  if (!element.querySelector('.bookmark-indicator')) {
    const span = document.createElement('span');
    span.className = 'bookmark-indicator';
    span.textContent = '🔖';
    span.title = getI18nText('bookmark.removeBookmark', isTraditionalChinesePage(), '點擊移除書籤');
    element.appendChild(span);
  }
}

function removeBookmarkVisualIndicator(element) {
  element.classList.remove('bookmarked');
  const indicator = element.querySelector('.bookmark-indicator');
  if (indicator) element.removeChild(indicator);
}

function restoreBookmarkVisualStates() {
  getBookmarks().forEach(bookmark => {
    const el = document.getElementById(bookmark.elementId);
    if (!el) return;
    addBookmarkVisualIndicator(el);
    if (bookmark.type === 'qa-pair') {
      if (el.classList.contains('question')) {
        const ans = findAnswerForQuestion(el);
        if (ans) addBookmarkVisualIndicator(ans);
      } else if (el.classList.contains('answer')) {
        const q = findQuestionForAnswer(el);
        if (q) addBookmarkVisualIndicator(q);
      }
    }
  });
}

// ------------------------------------------------------------------ //
// CRUD 操作                                                           //
// ------------------------------------------------------------------ //

function toggleBookmark(element) {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }

  const bookmarks = getBookmarks();
  const isQuestion = element.classList.contains('question');
  const isAnswer = element.classList.contains('answer');
  if (!isQuestion && !isAnswer) return;

  element.id = element.id || ('bookmark-' + Date.now());
  const id = element.id;
  const existing = bookmarks.find(b => b.elementId === id);

  if (existing) {
    removeBookmarkVisualIndicator(element);
    saveBookmarks(bookmarks.filter(b => b.elementId !== id));
    renderBookmarks();
    showToast('已從書籤移除');
    return;
  }

  let questioner = '', time = '', preview = '';
  if (isQuestion) {
    questioner = element.querySelector('.questioner')?.textContent || '匿名';
    time = element.querySelector('.question-time')?.textContent || '';
    preview = (element.querySelector('.question-text')?.textContent || '').substring(0, 100) + '...';
  } else {
    questioner = element.querySelector('.answerer')?.textContent || 'Taiguanglin';
    preview = (element.querySelector('.answer-text')?.textContent || '').substring(0, 100) + '...';
  }

  bookmarks.push({
    id: 'bookmark-' + Date.now(),
    elementId: id,
    type: isQuestion ? 'question' : 'answer',
    questioner, time, preview,
    chapter: findChapterForElement(element),
    chapterTitle: currentChapter.title,
    chapterFilename: currentChapter.filename,
    timestamp: new Date().toLocaleString(),
  });
  saveBookmarks(bookmarks);
  addBookmarkVisualIndicator(element);
  renderBookmarks();
  showBookmarkAddedFeedback();
}

function toggleQAPairBookmark(answerElement) {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }

  const bookmarks = getBookmarks();
  const questionElement = findQuestionForAnswer(answerElement);

  const targetEl = questionElement || answerElement;
  targetEl.id = targetEl.id || ('qa-question-' + Date.now());
  if (!answerElement.id) answerElement.id = 'qa-answer-' + Date.now();
  const targetId = targetEl.id;

  const existing = bookmarks.find(b => b.elementId === targetId);
  if (existing) {
    removeBookmarkVisualIndicator(answerElement);
    if (questionElement) removeBookmarkVisualIndicator(questionElement);
    saveBookmarks(bookmarks.filter(b => b.elementId !== targetId));
    renderBookmarks();
    showToast('已從書籤移除問答');
    return;
  }

  let questioner = '匿名', time = '', preview = '';
  if (questionElement) {
    questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
    time = questionElement.querySelector('.question-time')?.textContent || '';
    const qText = questionElement.querySelector('.question-text')?.textContent || '';
    const aText = answerElement.querySelector('.answer-text')?.textContent || '';
    preview = `問：${qText.substring(0, 50)}... 答：${aText.substring(0, 50)}...`;
  } else {
    questioner = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
    const aText = answerElement.querySelector('.answer-text')?.textContent || '';
    preview = `答：${aText.substring(0, 100)}...`;
  }

  bookmarks.push({
    id: 'qa-bookmark-' + Date.now(),
    elementId: targetId,
    type: 'qa-pair',
    questioner, time, preview,
    chapter: findChapterForElement(answerElement),
    chapterTitle: currentChapter.title,
    chapterFilename: currentChapter.filename,
    timestamp: new Date().toLocaleString(),
  });
  saveBookmarks(bookmarks);
  addBookmarkVisualIndicator(answerElement);
  if (questionElement) addBookmarkVisualIndicator(questionElement);
  renderBookmarks();
  showBookmarkAddedFeedback();
}

function removeBookmark(bookmarkId) {
  const bookmarks = getBookmarks();
  const bookmark = bookmarks.find(b => b.id === bookmarkId);
  if (bookmark) {
    const el = document.getElementById(bookmark.elementId);
    if (el) {
      removeBookmarkVisualIndicator(el);
      if (bookmark.type === 'qa-pair') {
        const other = el.classList.contains('question')
          ? findAnswerForQuestion(el)
          : findQuestionForAnswer(el);
        if (other) removeBookmarkVisualIndicator(other);
      }
    }
  }
  saveBookmarks(bookmarks.filter(b => b.id !== bookmarkId));
  renderBookmarks();
  showToast('已從書籤移除');
}

function removeBookmarkById(bookmarkId) {
  saveBookmarks(getBookmarks().filter(b => b.id !== bookmarkId));
  showToast(getI18nText('bookmark.bookmarkDeleted', isTraditionalChinesePage(), '書籤已刪除'));
}

function clearCurrentChapterBookmarks() {
  if (currentChapter.isHomepage) { showToast('首頁不支持書籤功能'); return; }
  const current = getCurrentChapterBookmarks();
  if (!current.length) { showToast('本文件暫無書籤'); return; }
  if (!confirm(`確定要清空本文件的所有 ${current.length} 個書籤嗎？此操作無法撤銷。`)) return;

  current.forEach(b => {
    const el = document.getElementById(b.elementId);
    if (el) {
      removeBookmarkVisualIndicator(el);
      if (b.type === 'qa-pair' && el.classList.contains('answer')) {
        const q = findQuestionForAnswer(el);
        if (q) removeBookmarkVisualIndicator(q);
      }
    }
  });

  const all = getBookmarks();
  saveBookmarks(all.filter(b => !b.chapter || b.chapter.id !== currentChapter.id));
  renderBookmarks();
  showToast(`已清空本文件的 ${current.length} 個書籤`);
}

// 跳转到指定书签（新标签页）
function jumpToBookmark(bookmarkId) {
  const bm = getBookmarks().find(b => b.id === bookmarkId);
  if (bm && bm.chapterFilename) {
    window.open(`${bm.chapterFilename}#${bm.elementId}`, '_blank');
  }
}
// ============================================================
// 03b-bookmark-render.js — 书签渲染、首页书签、Toast 反馈
// ============================================================

// ------------------------------------------------------------------ //
// 书签添加反馈                                                        //
// ------------------------------------------------------------------ //

function showBookmarkAddedFeedback() {
  if (currentChapter.isHomepage) {
    showToast(getI18nText('bookmark.viewInSidebar', isTraditionalChinesePage(), '已添加到書籤，可在側邊欄查看'));
    _highlightBookmarkTab();
  } else {
    showEnhancedBookmarkToast();
  }
}

function _highlightBookmarkTab() {
  const floatingTOC = document.getElementById('floating-toc');
  const bookmarkTab = document.querySelector('.floating-toc-tab[data-tab="bookmarks"]');
  if (!floatingTOC || !bookmarkTab) return;

  const wasHidden = !floatingTOC.classList.contains('visible');
  if (wasHidden) floatingTOC.classList.add('visible');

  Object.assign(bookmarkTab.style, {
    background: '#ff69b4', color: 'white',
    transform: 'scale(1.1)', transition: 'all 0.3s ease',
    boxShadow: '0 2px 8px rgba(255, 105, 180, 0.5)',
  });
  setTimeout(() => {
    Object.assign(bookmarkTab.style, { background: '', color: '', transform: '', boxShadow: '' });
    if (wasHidden) setTimeout(() => floatingTOC.classList.remove('visible'), 1500);
  }, 1200);
}

// 章节页专用的增强 Toast
function showEnhancedBookmarkToast() {
  const toast = document.createElement('div');
  toast.className = 'bookmark-success-toast';
  toast.innerHTML = `
    <div class="toast-icon">🔖</div>
    <div class="toast-content">
      <div class="toast-title">書籤已添加！</div>
      <div class="toast-subtitle">點擊右下角 📖 查看所有書籤</div>
    </div>
  `;
  Object.assign(toast.style, {
    position: 'fixed', top: '20px', right: '20px',
    background: 'linear-gradient(135deg, #ff69b4, #e75480)',
    color: 'white', padding: '16px 20px', borderRadius: '12px',
    boxShadow: '0 8px 25px rgba(231, 84, 128, 0.3)',
    zIndex: '10000', transform: 'translateX(400px)',
    transition: 'all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    display: 'flex', alignItems: 'center', gap: '12px',
    maxWidth: '300px', fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
  });

  const style = document.createElement('style');
  style.textContent = `@keyframes bounce { 0% { transform:translateY(0); } 100% { transform:translateY(-6px); } }`;
  document.head.appendChild(style);
  document.body.appendChild(toast);

  setTimeout(() => { toast.style.transform = 'translateX(0)'; }, 100);
  setTimeout(() => {
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    setTimeout(() => {
      if (toast.parentNode) document.body.removeChild(toast);
      if (style.parentNode) document.head.removeChild(style);
    }, 400);
  }, 3500);
}

// ------------------------------------------------------------------ //
// 首页书签渲染                                                        //
// ------------------------------------------------------------------ //

function initializeHomepageTOC() {
  const tocList = document.getElementById('toc-list');
  const mainTOC = document.querySelector('.toc ul');
  if (tocList && mainTOC) {
    tocList.innerHTML = mainTOC.innerHTML;
    tocList.addEventListener('click', (e) => {
      if (e.target.tagName !== 'A') return;
      e.preventDefault();
      const href = e.target.getAttribute('href');
      if (href && href.startsWith('#')) {
        document.querySelector(href)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else if (href) {
        window.location.href = href;
      }
    });
  }
  refreshHomepageBookmarks();
  updateBookmarkCount();
}

function refreshHomepageBookmarks() {
  if (!currentChapter.isHomepage) return;
  const bookmarksList = document.getElementById('bookmarks-list');
  if (!bookmarksList) return;

  setTimeout(() => {
    const all = getBookmarks();
    if (!all.length) {
      bookmarksList.innerHTML = '<li class="bookmarks-empty">' +
        getI18nText('bookmark.empty', isTraditionalChinesePage(), '尚無書籤') + '</li>';
      return;
    }
    if (all.length > 50) showBookmarkProcessingIndicator(all.length);
    processHomepageBookmarks(all);
  }, 10);
}

function showBookmarkProcessingIndicator(totalCount) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;
  el.innerHTML = `
    <div class="bookmark-loading-container">
      <div class="bookmark-loading-spinner">
        <div class="loading-text">處理 ${totalCount} 個書籤...</div>
      </div>
    </div>
  `;
}

function processHomepageBookmarks(allBookmarks) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;
  requestAnimationFrame(() => {
    const byChapter = {};
    allBookmarks.forEach(b => {
      const key = b.chapterTitle || '未知章節';
      (byChapter[key] = byChapter[key] || []).push(b);
    });
    const sorted = Object.keys(byChapter).sort((a, b) => {
      const num = t => { const m = t.match(/^(\d{1,2})/); return m ? parseInt(m[1], 10) : 999; };
      return num(a) - num(b);
    });
    renderBookmarkChaptersBatch(sorted, byChapter, 0);
  });
}

function renderBookmarkChaptersBatch(titles, byChapter, startIndex) {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;

  const BATCH = 3;
  const end = Math.min(startIndex + BATCH, titles.length);
  if (startIndex === 0) el.innerHTML = '';

  for (let i = startIndex; i < end; i++) {
    const title = titles[i];
    const bookmarks = byChapter[title];
    const group = document.createElement('li');
    group.className = 'bookmark-chapter-group';

    let html = `<div class="bookmark-chapter-title">${title}</div><ul class="bookmark-chapter-list">`;
    bookmarks.forEach(b => {
      const isQA = b.type === 'qa-pair';
      const icon = isQA ? '💬' : '📝';
      const cls = isQA ? ' qa-pair-bookmark' : '';
      const link = (b.chapterFilename && b.elementId) ? `${b.chapterFilename}#${b.elementId}` : '#';
      html += `
        <li class="bookmark-item${cls}" data-bookmark-id="${b.id}">
          <div class="bookmark-meta">
            <span class="bookmark-type">${icon}</span>
            <span class="bookmark-questioner">${b.questioner || '匿名'}</span>
            <span class="bookmark-time">${b.time || ''}</span>
          </div>
          <div class="bookmark-preview">
            <a href="${link}" target="_blank" title="點擊跳轉到原問答">${b.preview || ''}</a>
          </div>
          <button class="bookmark-delete" data-bookmark-id="${b.id}" title="刪除書籤">✕</button>
        </li>
      `;
    });
    html += '</ul>';
    group.innerHTML = html;
    el.appendChild(group);
  }

  if (end < titles.length) {
    requestAnimationFrame(() => renderBookmarkChaptersBatch(titles, byChapter, end));
  } else {
    addHomepageBookmarkEventListeners();
  }
}

function addHomepageBookmarkEventListeners() {
  const el = document.getElementById('bookmarks-list');
  if (!el) return;

  if (el.bookmarkClickHandler) el.removeEventListener('click', el.bookmarkClickHandler);

  const handler = (e) => {
    if (e.target.classList.contains('bookmark-delete')) {
      e.stopPropagation();
      removeBookmarkById(e.target.getAttribute('data-bookmark-id'));
      refreshHomepageBookmarks();
      updateBookmarkCount();
    } else if (!e.target.closest('a')) {
      const item = e.target.closest('.bookmark-item');
      if (item) jumpToBookmark(item.getAttribute('data-bookmark-id'));
    }
  };

  el.addEventListener('click', handler);
  el.bookmarkClickHandler = handler;
}
  // 渲染首頁動態TOC內容
  function renderIndexTOC() {
    const tocList = document.getElementById('toc-list');
    const bookmarksList = document.getElementById('bookmarks-list');
    
    if (!tocList) return;
    
    // 獲取首頁的TOC鏈接
    const mainTOC = document.querySelector('.toc');
    if (!mainTOC) return;
    
    const tocLinks = mainTOC.querySelectorAll('a[href]');
    let tocHTML = '';
    
    tocLinks.forEach(link => {
      const href = link.getAttribute('href');
      const text = link.textContent.trim();
      
      // 只顯示主章節（不包含錨點的鏈接）
      if (href && !href.includes('#') && text) {
        tocHTML += `<div class="floating-toc-item" data-href="${href}">${text}</div>`;
      }
    });
    
    tocList.innerHTML = tocHTML;
    
    // 同時更新書籤列表為章節書籤功能說明
    if (bookmarksList) {
      bookmarksList.innerHTML = `
        <div class="bookmarks-empty">
          <p>📖 書籤功能說明</p>
          <p>• 進入任意章節</p>
          <p>• 找到感興趣的問答</p>
          <p>• 點擊右上角書籤圖標</p>
          <p>• 返回此處查看收藏</p>
        </div>
      `;
    }
  }
  
  // 顯示書籤載入指示器
  function showBookmarkLoadingIndicator() {
    const bookmarksList = document.getElementById('bookmarks-list');
    if (!bookmarksList) return;
    
    // 創建載入動畫HTML
    const loadingHTML = `
      <div class="bookmark-loading-container">
        <div class="bookmark-loading-spinner">
          <div class="loading-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
          <div class="loading-text">載入書籤中...</div>
        </div>
      </div>
    `;
    
    bookmarksList.innerHTML = loadingHTML;
    
    // 動態添加載入動畫CSS（如果尚未添加）
    if (!document.querySelector('#bookmark-loading-styles')) {
      const style = document.createElement('style');
      style.id = 'bookmark-loading-styles';
      style.textContent = `
        .bookmark-loading-container {
          display: flex;
          justify-content: center;
          align-items: center;
          padding: 40px 20px;
          min-height: 120px;
        }
        
        .bookmark-loading-spinner {
          text-align: center;
          color: #666;
        }
        
        .loading-dots {
          display: flex;
          gap: 4px;
          justify-content: center;
          margin-bottom: 12px;
        }
        
        .loading-dots .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: #ff69b4;
          animation: bookmarkDotPulse 1.4s infinite ease-in-out both;
        }
        
        .loading-dots .dot:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots .dot:nth-child(2) { animation-delay: -0.16s; }
        .loading-dots .dot:nth-child(3) { animation-delay: 0s; }
        
        .loading-text {
          font-size: 14px;
          color: #999;
          font-weight: 500;
        }
        
        @keyframes bookmarkDotPulse {
          0%, 80%, 100% {
            transform: scale(0.6);
            opacity: 0.5;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
        
        /* 暗色模式支持 */
        .dark-mode .bookmark-loading-spinner {
          color: #ccc;
        }
        
        .dark-mode .loading-text {
          color: #aaa;
        }
      `;
      document.head.appendChild(style);
    }
  }

  function renderBookmarks() {
    const bookmarksList = document.getElementById('bookmarks-list');
    
    if (!bookmarksList) {
      return;
    }
    
    // 首頁使用專門的書籤顯示函數
    if (currentChapter.isHomepage) {
      refreshHomepageBookmarks();
      return;
    }
    
    // 對於章節頁面，也使用異步處理來改善UX
    setTimeout(() => {
      const chapterBookmarks = getCurrentChapterBookmarks();
      
      if (chapterBookmarks.length === 0) {
        bookmarksList.innerHTML = 
          '<div class="bookmarks-empty">' +
            '<div>本文件暫無書籤</div>' +
            '<div style="font-size: 12px; color: #999; margin-top: 8px;">當前文件：' + currentChapter.title + '</div>' +
          '</div>';
        return;
      }
      
      let bookmarksHTML = '';
      
      // 添加當前文件標題和清空按鈕
      bookmarksHTML += 
        '<div class="current-chapter-info">' +
          '<div class="chapter-header">' +
            '<div class="current-chapter-title">📄 ' + currentChapter.title + '</div>' +
            '<button class="bookmark-clear-icon" data-action="clear-bookmarks" title="清空本文件所有書籤">🗑️</button>' +
          '</div>' +
        '</div>';
      
      // 直接顯示當前文件的書籤，不需要分組
      chapterBookmarks.forEach(bookmark => {
        const isQAPair = bookmark.type === 'qa-pair';
        const typeIcon = isQAPair ? '💬' : '📝';
        const typeClass = isQAPair ? ' qa-pair-bookmark' : '';
        
        bookmarksHTML += 
          '<div class="bookmark-item' + typeClass + '" data-target="#' + bookmark.elementId + '">' +
            '<div class="bookmark-meta">' +
              '<span class="bookmark-type">' + typeIcon + '</span>' +
              '<span class="bookmark-questioner">' + bookmark.questioner + '</span>' +
              '<span class="bookmark-time">' + bookmark.time + '</span>' +
            '</div>' +
            '<div class="bookmark-preview">' + bookmark.preview + '</div>' +
            '<button class="bookmark-delete" data-bookmark-id="' + bookmark.id + '" title="刪除書籤">✕</button>' +
          '</div>';
      });
      
      bookmarksList.innerHTML = bookmarksHTML;
    }, 10); // 短暫延遲讓載入動畫顯示
  }
  
  function updateBookmarkCount() {
    const countEl = document.getElementById('bookmark-count');
    if (!countEl) {
      return;
    }
    
    let count;
    if (currentChapter.isHomepage) {
      // 首頁顯示所有書籤的總數
      const allBookmarks = getBookmarks();
      count = allBookmarks.length;
    } else {
      // 章節頁面顯示當前章節的書籤數
      count = getCurrentChapterBookmarks().length;
    }
    if (countEl) {
      countEl.textContent = '(' + count + ')';
    }
  }

  // 閱讀設置功能
  // 根据屏幕尺寸设置默认字体大小
  function getDefaultFontSize() {
    const screenWidth = window.innerWidth;
    if (screenWidth <= 400) {
      return 19; // 小手机默认19px
    } else if (screenWidth <= 600) {
      return 18; // 手机默认18px
    } else if (screenWidth <= 768) {
      return 17; // 平板默认17px
    }
    return 16; // 桌面默认16px
  }
  
  let fontSize = parseInt(localStorage.getItem('fontSize')) || getDefaultFontSize();
  let lineHeight = parseFloat(localStorage.getItem('lineHeight')) || 1.6;
  let contentWidth = parseInt(localStorage.getItem('contentWidth')) || 800;
  
  function applyReadingSettings() {
    // 使用!important确保字体大小设置在移动设备上生效
    document.body.style.setProperty('font-size', fontSize + 'px', 'important');
    document.documentElement.style.setProperty('--line-height', lineHeight);
    document.body.style.maxWidth = contentWidth + 'px';
    
    // 動態調整TOC目錄的字型大小和間距
    // 移除現有的動態TOC樣式
    let existingTocStyle = document.getElementById('dynamic-toc-styles');
    if (existingTocStyle) {
      existingTocStyle.remove();
    }
    
    // 創建新的動態樣式
    const tocStyle = document.createElement('style');
    tocStyle.id = 'dynamic-toc-styles';
    
    // 檢測螢幕大小，調整響應式基礎字型
    const screenWidth = window.innerWidth;
    let responsiveBaseFontSize = fontSize;
    
    // 根據螢幕寬度調整基礎字型大小，但允許用户自由调整
    // 移除最小值限制，允许用户设置更小的字体
    responsiveBaseFontSize = fontSize;
    
    // 計算相對於響應式基礎字型大小的比例
    const fontScale = responsiveBaseFontSize / 16;
    const lineHeightValue = lineHeight;
    
    // 各層級的字型大小比例（相對於響應式基礎大小）
    const level1Size = Math.round(responsiveBaseFontSize * 1.1); // 第一層：稍大
    const level2Size = responsiveBaseFontSize; // 第二層：基礎大小  
    const level3Size = Math.round(responsiveBaseFontSize * 0.95); // 第三層：稍小
    const level4Size = Math.round(responsiveBaseFontSize * 0.9); // 第四層：更小
    
    // 調試信息
    console.log('字體設置應用:', {
      screenWidth,
      fontSize,
      responsiveBaseFontSize,
      level1Size,
      level2Size,
      level3Size,
      level4Size,
      lineHeightValue
    });
    
    // 間距調整（基於行距設置）
    const spacing1 = Math.round(8 * lineHeightValue / 1.6); // 第一層間距
    const spacing2 = Math.round(6 * lineHeightValue / 1.6); // 第二層間距  
    const spacing3 = Math.round(4 * lineHeightValue / 1.6); // 第三層間距
    const spacing4 = Math.round(3 * lineHeightValue / 1.6); // 第四層間距
    
    tocStyle.textContent = `
      /* 首頁TOC樣式調整 - 使用更高的特定性確保生效 */
      #main-toc .toc > ul > li,
      .toc > ul > li { 
        font-size: ${level1Size}px !important; 
        margin-bottom: ${spacing1}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul > li,
      .toc ul ul > li { 
        font-size: ${level2Size}px !important; 
        margin-bottom: ${spacing2}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul ul > li,
      .toc ul ul ul > li { 
        font-size: ${level3Size}px !important; 
        margin-bottom: ${spacing3}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #main-toc .toc ul ul ul ul > li,
      .toc ul ul ul ul > li { 
        font-size: ${level4Size}px !important; 
        margin-bottom: ${spacing4}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      /* 章節頁TOC樣式調整 - 使用更高的特定性確保生效 */
      #chapter-toc .toc-item.toc-level-1 > a,
      .toc-item.toc-level-1 > a {
        font-size: ${level1Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-2 > a,
      .toc-item.toc-level-2 > a {
        font-size: ${level2Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-3 > a,
      .toc-item.toc-level-3 > a {
        font-size: ${level3Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      #chapter-toc .toc-item.toc-level-4 > a,
      .toc-item.toc-level-4 > a {
        font-size: ${level4Size}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      /* TOC項目的間距調整 */
      .toc-item.toc-level-1 {
        margin-bottom: ${spacing1}px !important;
      }
      
      .toc-item.toc-level-2 {
        margin-bottom: ${spacing2}px !important;
      }
      
      .toc-item.toc-level-3 {
        margin-bottom: ${spacing3}px !important;
      }
      
      .toc-item.toc-level-4 {
        margin-bottom: ${spacing4}px !important;
      }
      
      /* 浮動TOC樣式調整 */
      .floating-toc-item {
        font-size: ${Math.round(fontSize * 0.85)}px !important;
        line-height: ${lineHeightValue} !important;
      }
      
      .floating-toc-item.level-h3 {
        font-size: ${Math.round(fontSize * 0.8)}px !important;
      }
      
      .floating-toc-item.level-h4 {
        font-size: ${Math.round(fontSize * 0.75)}px !important;
      }
      
      .floating-toc-item.level-h5 {
        font-size: ${Math.round(fontSize * 0.7)}px !important;
      }
      
      /* 層級控制按鈕樣式調整 */
      .toc-level-label {
        font-size: ${Math.round(fontSize * 0.9)}px !important;
      }
      
      .toc-level-btn, .floating-level-btn {
        font-size: ${Math.round(fontSize * 0.9)}px !important;
      }
      
      .floating-level-label {
        font-size: ${Math.round(fontSize * 0.7)}px !important;
      }
    `;
    
    document.head.appendChild(tocStyle);
    
    // 動態調整搜索功能的字型大小
    applySearchFontStyles();
  }
  
  // 應用搜索功能字體樣式
  function applySearchFontStyles() {
    // 移除現有的動態搜索樣式
    let existingSearchStyle = document.getElementById('dynamic-search-styles');
    if (existingSearchStyle) {
      existingSearchStyle.remove();
    }
    
    // 創建新的動態搜索樣式
    const searchStyle = document.createElement('style');
    searchStyle.id = 'dynamic-search-styles';
    
    // 計算搜索相關元素的字體大小
    const baseFontSize = fontSize;
    const inputFontSize = Math.max(14, Math.min(20, baseFontSize)); // 輸入框：14-20px範圍
    const contentFontSize = Math.max(12, Math.round(baseFontSize * 0.9)); // 搜索結果內容稍小，最小12px
    const titleFontSize = Math.max(12, Math.round(baseFontSize * 0.85)); // 標題更小，最小12px
    const controlFontSize = Math.max(10, Math.round(baseFontSize * 0.75)); // 控制按鈕最小10px
    const statusFontSize = Math.max(11, Math.round(baseFontSize * 0.8)); // 狀態文字最小11px
    const activateBtnFontSize = Math.max(13, Math.round(baseFontSize * 0.9)); // 激活按鈕最小13px
    
    // 調試信息
    console.log('搜索字體設置應用:', {
      baseFontSize,
      inputFontSize,
      contentFontSize,
      titleFontSize,
      controlFontSize,
      statusFontSize,
      activateBtnFontSize
    });
    
    searchStyle.textContent = `
      /* 搜索輸入框字體 */
      #search-input {
        font-size: ${inputFontSize}px !important;
      }
      
      /* 搜索輸入框占位符字體 */
      #search-input::placeholder {
        font-size: ${inputFontSize}px !important;
      }
      
      /* 搜索結果內容字體 */
      .search-result-content {
        font-size: ${contentFontSize}px !important;
        line-height: ${lineHeight} !important;
      }
      
      /* 搜索結果標題字體 */
      .search-result-title {
        font-size: ${titleFontSize}px !important;
      }
      
      /* 搜索狀態文字 */
      .search-status,
      .search-loading-text {
        font-size: ${statusFontSize}px !important;
      }
      
      /* 搜索控制按鈕 */
      .search-clear,
      .search-collapse,
      .search-load-more,
      .search-load-all,
      .search-retry-btn {
        font-size: ${controlFontSize}px !important;
      }
      
      /* 搜索結果底部控制按鈕 */
      .search-results-footer {
        padding: 10px;
        border-top: 1px solid var(--border-color);
        background: var(--bg-color);
        position: sticky;
        bottom: 0;
      }
      
      .search-results-footer .search-results-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        flex-wrap: wrap;
      }
      
      /* 搜索結果編號 */
      .search-result-header {
        display: inline-block;
        align-items: center;
        gap: 4px;
        margin-bottom: 4px;
        flex-wrap: nowrap;
        min-height: fit-content;
      }
      
      .search-result-number {
        background: #e75480;
        color: white;
        padding: 2px 4px;
        border-radius: 3px;
        font-size: ${Math.max(9, Math.round(titleFontSize * 0.8))}px !important;
        font-weight: bold;
        flex-shrink: 0;
        white-space: nowrap;
        line-height: 1.2;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
      }
      
      .search-result-title {
        display: inline-block;
        flex: 1;
        min-width: 0;
        margin: 0;
        padding: 0;
      }
      
      /* 搜索激活按鈕 */
      .search-activate-btn {
        font-size: ${activateBtnFontSize}px !important;
      }
      
      /* 搜索結果類型標籤 */
      .search-result-type {
        font-size: ${Math.round(controlFontSize * 0.9)}px !important;
      }
      
      /* 搜索結果統計 */
      .search-results-count {
        font-size: ${statusFontSize}px !important;
      }
      
    `;
    
    document.head.appendChild(searchStyle);
  }
  
  function updateFontSize(change) {
    fontSize = Math.max(12, Math.min(24, fontSize + change));
    localStorage.setItem('fontSize', fontSize);
    applyReadingSettings();
    updateFontSizeButtons();
  }
  
  function updateLineHeight(value) {
    lineHeight = value;
    localStorage.setItem('lineHeight', lineHeight);
    applyReadingSettings();
    updateLineHeightButtons();
  }
  
  function updateContentWidth(value) {
    contentWidth = value;
    localStorage.setItem('contentWidth', contentWidth);
    applyReadingSettings();
    updateContentWidthButtons();
  }

  // 閱讀進度功能
  function updateReadingProgress() {
    const scrollTop = window.pageYOffset;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    
    const progressBar = document.querySelector('.reading-progress-bar');
    if (progressBar) {
      progressBar.style.width = Math.max(0, Math.min(100, progress)) + '%';
    }
  }

  // 章節跟踪功能
  function updateCurrentSection() {
    // 首頁跳過章節跟踪
    if (currentChapter.isHomepage) {
      return;
    }
    
    const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
    const scrollTop = window.pageYOffset;
    const offset = 100; // 偏移量，調整觸發點
    
    let currentSection = null;
    
    // 找到最接近當前位置的章節
    headings.forEach((heading) => {
      const rect = heading.getBoundingClientRect();
      const elementTop = scrollTop + rect.top;
      
      if (elementTop <= scrollTop + offset) {
        currentSection = heading;
      }
    });
    
    // 更新TOC高亮狀態
    const tocItems = document.querySelectorAll('.floating-toc-item[data-target]');
    let activeItem = null;
    
    tocItems.forEach(item => {
      item.classList.remove('active');
      
      if (currentSection) {
        const targetId = '#' + currentSection.id;
        if (item.dataset.target === targetId) {
          item.classList.add('active');
          activeItem = item;
        }
      }
    });
    
    // 自動滾動sidebar到當前章節
    if (activeItem) {
      const tocContainer = activeItem.closest('.floating-toc');
      if (tocContainer && tocContainer.classList.contains('visible')) {
        // 檢查activeItem是否在可視區域內
        const containerRect = tocContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        
        // 如果item不在容器的可視區域內，則滾動到該位置
        if (itemRect.top < containerRect.top + 60 || itemRect.bottom > containerRect.bottom - 20) {
          activeItem.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
        }
      }
    }
  }

  // 顯示通知
  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
  }

  // 複製功能
  function copyText(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('已複製到剪貼板');
      });
    } else {
      // 降級處理
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('已複製到剪貼板');
    }
  }
  
  // 處理頁面加載時的錨點跳轉
  function handleInitialAnchor() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      const targetId = hash.substring(1); // 移除#號
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        // 延遲滾動，確保頁面布局完成
        setTimeout(() => {
          targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
          
          // 添加臨時高亮效果
          targetElement.style.transition = 'background-color 0.3s ease';
          targetElement.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
          setTimeout(() => {
            targetElement.style.backgroundColor = '';
          }, 3000);
        }, 300);
      }
    }
  }

  // ============ 事件監聽 ============
  
  // 首先初始化當前章節信息
  currentChapter = getCurrentChapter();
  
  // 初始化所有組件
  const toolbar = createReadingToolbar();
  const progressBar = createReadingProgress();
  const floatingTOC = createFloatingTOC();
  
  // 只在章節頁面創建action-buttons，首頁已有靜態HTML
  if (!currentChapter.isHomepage) {
    const actionButtons = createActionButtons();
  }
  
  addQAActions();
  applyReadingSettings();
  
  // 首頁專用：初始化浮動TOC
  if (currentChapter.isHomepage) {
    initializeHomepageTOC();
  }
  
  updateBookmarkCount();
  updateThemeButtons();
  updateReadingSettingsButtons();
  restoreBookmarkVisualStates();
  
  // 延遲執行章節跟踪，確保頁面完全渲染
  setTimeout(updateCurrentSection, 100);
  
  // 處理頁面加載時的錨點跳轉
  setTimeout(handleInitialAnchor, 200);
  
  // 如果是首頁，渲染動態TOC內容
  if (isIndexPage()) {
    renderIndexTOC();
  }

  document.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    
    // 點擊外部區域關閉所有打開的sidebars
    if (!action && !isClickInsideSidebar(e.target)) {
      closeSidebars();
    }
    
    if (!action) return;

    switch (action) {
      // 字體設置
      case 'font-decrease':
        updateFontSize(-2);
        addFontAdjustFeedback(e.target);
        break;
      case 'font-normal':
        fontSize = getDefaultFontSize();
        localStorage.setItem('fontSize', fontSize);
        applyReadingSettings();
        updateFontSizeButtons();
        break;
      case 'font-increase':
        updateFontSize(2);
        addFontAdjustFeedback(e.target);
        break;

      // 行距設置
      case 'line-tight':
        updateLineHeight(1.2);
        break;
      case 'line-normal':
        updateLineHeight(1.6);
        break;
      case 'line-loose':
        updateLineHeight(2.0);
        break;

      // 寬度設置
      case 'width-narrow':
        updateContentWidth(600);
        break;
      case 'width-normal':
        updateContentWidth(800);
        break;
      case 'width-wide':
        updateContentWidth(1000);
        break;

      // 主題切換
      case 'theme-light':
        document.body.classList.remove('dark-mode');
        localStorage.setItem('darkMode', false);
        updateThemeButtons();
        break;
      case 'theme-dark':
        document.body.classList.add('dark-mode');
        localStorage.setItem('darkMode', true);
        updateThemeButtons();
        break;

      // 操作按鈕
      case 'toggle-menu':
        // 兼容首頁和章節頁面的不同結構
        const actionButtons = e.target.closest('.action-buttons');
        let actionMenu = actionButtons.querySelector('.action-menu');
        
        // 如果沒找到.action-menu，可能是首頁結構，直接查找同級的.action-menu
        if (!actionMenu) {
          actionMenu = e.target.nextElementSibling;
          if (actionMenu && !actionMenu.classList.contains('action-menu')) {
            actionMenu = null;
          }
        }
        
        if (actionMenu) {
          actionMenu.classList.toggle('expanded');
        }
        e.target.classList.toggle('expanded');
        break;
      case 'toc':
        floatingTOC.classList.toggle('visible');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        // 如果TOC剛打開，立即定位當前章節
        if (floatingTOC.classList.contains('visible')) {
          setTimeout(updateCurrentSection, 100); // 等待CSS transition完成
        }
        break;
      case 'close-toc':
        floatingTOC.classList.remove('visible');
        break;
      case 'top':
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'home':
        // 回到首頁 - 根據當前頁面語言版本決定目標首頁
        const homePageUrl = isTraditionalChinesePage() ? 'index_trad.html' : 'index.html';
        window.location.href = homePageUrl;
        break;

      case 'settings':
        toolbar.classList.toggle('hidden');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'close-toolbar':
        toolbar.classList.add('hidden');
        break;

      // 問答操作
      case 'bookmark':
        const bookmarkElement = e.target.closest('.question, .answer');
        if (bookmarkElement) {
          toggleBookmark(bookmarkElement);
        }
        break;
      case 'copy-qa':
        const copyQAElement = e.target.closest('.question, .answer');
        if (copyQAElement) {
          const qaPairText = getQAPairText(copyQAElement);
          copyText(qaPairText);
        }
        break;
      case 'bookmark-qa':
        const qaBookmarkElement = e.target.closest('.question, .answer');
        if (qaBookmarkElement) {
          if (qaBookmarkElement.classList.contains('answer')) {
            toggleQAPairBookmark(qaBookmarkElement);
          } else if (qaBookmarkElement.classList.contains('question')) {
            // 如果是問題，找到對應的回答
            const answerElement = findAnswerForQuestion(qaBookmarkElement);
            if (answerElement) {
              toggleQAPairBookmark(answerElement);
            } else {
              // 如果沒有對應回答，提示用戶
              showToast('找不到對應的回答');
            }
          }
        }
        break;
      case 'share':
        const shareElement = e.target.closest('.question, .answer');
        if (shareElement) {
          // 直接分享點擊的區塊（問題或回答）
          const shareUrl = generateShareUrl(shareElement);
          const isQuestion = shareElement.classList.contains('question');
          const toastMessage = isQuestion ? '問題鏈接已複製' : '回答鏈接已複製';
          
          if (navigator.share) {
            navigator.share({
              url: shareUrl
            });
          } else {
            copyText(shareUrl);
            showToast(toastMessage);
          }
        } else {
          // 降級處理：分享頁面鏈接
          if (navigator.share) {
            navigator.share({
              url: window.location.href
            });
          } else {
            copyText(window.location.href);
            showToast('頁面鏈接已複製');
          }
        }
        break;
      case 'clear-bookmarks':
        clearCurrentChapterBookmarks();
        break;
    }
  });

  // 浮動目錄點擊
  document.addEventListener('click', (e) => {
    // 目錄項點擊
    if (e.target.classList.contains('floating-toc-item')) {
      // 首頁的TOC項目：跳轉到其他頁面
      if (e.target.dataset.href) {
        const href = e.target.dataset.href;
        window.location.href = href;
        return;
      }
      
      // 其他頁面：頁面內跳轉
      const target = e.target.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // 移除自動關閉sidebar，讓用戶可以連續導航
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 標籤頁切換
    if (e.target.classList.contains('floating-toc-tab')) {
      const tab = e.target.dataset.tab;
      
      // 更新標籤頁狀態
      document.querySelectorAll('.floating-toc-tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      
      // 切換內容
      const tocList = document.getElementById('toc-list');
      const bookmarksList = document.getElementById('bookmarks-list');
      const tocTitle = document.getElementById('toc-title');
      
      if (tab === 'toc') {
        // 目录模式：显示目录，隐藏书签
        if (tocList) tocList.style.display = 'block';
        if (bookmarksList) bookmarksList.style.display = 'none';
        if (tocTitle) {
          tocTitle.textContent = '📖 章節目錄';
          tocTitle.style.display = 'block';
        }
        
        // 切換到目錄標籤頁時，自動定位到當前章節
        // 添加小延遲確保DOM更新完成
        setTimeout(() => {
          updateCurrentSection();
        }, 50);
      } else if (tab === 'bookmarks') {
        // 书签模式：隐藏目录，只显示书签内容
        if (tocList) tocList.style.display = 'none';
        if (bookmarksList) bookmarksList.style.display = 'block';
        if (tocTitle) {
          tocTitle.textContent = '🔖 我的書籤';
          tocTitle.style.display = 'block';
        }
        
        // 立即顯示載入指示器，改善UX
        showBookmarkLoadingIndicator();
        
        // 使用requestAnimationFrame延遲渲染，讓載入動畫先顯示
        requestAnimationFrame(() => {
          renderBookmarks();
        });
      }
    }
    
    // 書籤項點擊
    const bookmarkItem = e.target.closest('.bookmark-item');
    if (bookmarkItem && !e.target.classList.contains('bookmark-delete')) {
      const target = bookmarkItem.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        // 添加臨時高亮效果
        element.style.transition = 'background-color 0.3s ease';
        element.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
        setTimeout(() => {
          element.style.backgroundColor = '';
        }, 2000);
        
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // 移除自動關閉側邊欄，讓用戶可以連續瀏覽書籤
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 書籤刪除按鈕
    if (e.target.classList.contains('bookmark-delete')) {
      e.stopPropagation();
      const bookmarkId = e.target.dataset.bookmarkId;
      if (bookmarkId) {
        removeBookmark(bookmarkId);
      }
    }
    
    // 書籤標記點擊 - 移除書籤
    if (e.target.classList.contains('bookmark-indicator')) {
      e.stopPropagation();
      const bookmarkedElement = e.target.closest('.question, .answer');
      if (bookmarkedElement) {
        // 首先檢查是否為問答書籤（通過檢查配對元素）
        let isQAPairBookmark = false;
        let answerElement = null;
        let questionElement = null;
        
        if (bookmarkedElement.classList.contains('answer')) {
          answerElement = bookmarkedElement;
          questionElement = findQuestionForAnswer(answerElement);
        } else {
          questionElement = bookmarkedElement;
          answerElement = findAnswerForQuestion(questionElement);
        }
        
        // 如果問題和回答都有書籤標記，說明是問答書籤
        if (questionElement && answerElement && 
            questionElement.classList.contains('bookmarked') && 
            answerElement.classList.contains('bookmarked')) {
          isQAPairBookmark = true;
        }
        
        if (isQAPairBookmark && answerElement) {
          // 問答書籤：使用問答切換功能移除
          toggleQAPairBookmark(answerElement);
        } else {
          // 單個元素書籤：使用原來的切換功能
          toggleBookmark(bookmarkedElement);
        }
      }
    }
  });

  function updateActiveButton(container, activeBtn) {
    container.querySelectorAll('.ctrl-btn').forEach(btn => btn.classList.remove('active'));
    activeBtn.classList.add('active');
  }

  // 為字體調整按鈕添加點擊反饋效果
  function addFontAdjustFeedback(button) {
    if (button.classList.contains('font-adjust')) {
      button.classList.add('clicked');
      setTimeout(() => {
        button.classList.remove('clicked');
      }, 150); // 150ms後移除反饋效果
    }
  }

  // 檢查點擊是否在sidebar內部
  function isClickInsideSidebar(target) {
    return target.closest('.action-menu') || 
           target.closest('.floating-toc') || 
           target.closest('.reading-toolbar');
  }

  // 關閉所有打開的sidebars
  function closeSidebars() {
    // 關閉操作菜單
    const openMenu = document.querySelector('.action-menu.expanded');
    if (openMenu) {
      openMenu.classList.remove('expanded');
      document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
    }
    
    // 關閉浮動目錄
    const visibleTOC = document.querySelector('.floating-toc.visible');
    if (visibleTOC) {
      visibleTOC.classList.remove('visible');
    }
    
    // 關閉閱讀工具栏
    const visibleToolbar = document.querySelector('.reading-toolbar:not(.hidden)');
    if (visibleToolbar) {
      visibleToolbar.classList.add('hidden');
    }
  }

  // ========== 搜索按鈕智能顯示功能 ==========
  
  // 檢測頂部搜索控制按鈕是否在視窗中完全可見
  function areTopSearchControlsVisible() {
    const searchHeader = document.querySelector('.search-results-header');
    if (!searchHeader) return false;
    
    const rect = searchHeader.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 設置觸發閾值：當頂部按鈕開始被遮住時就顯示底部按鈕
    // 使用50px的緩衝區，確保用戶體驗的連續性
    const threshold = 50;
    
    // 檢查頂部控制按鈕是否有足夠的可見區域
    // 當按鈕開始被遮住超過閾值時，就認為不完全可見
    return rect.bottom > threshold && rect.top < (viewportHeight - threshold);
  }
  
  // 更新底部搜索按鈕的顯示狀態
  function updateBottomSearchButtonsVisibility() {
    const bottomFooter = document.querySelector('.search-results-footer');
    if (!bottomFooter) return;
    
    const areTopControlsVisible = areTopSearchControlsVisible();
    
    // 當頂部按鈕可見時隱藏底部按鈕，否則顯示底部按鈕
    if (areTopControlsVisible) {
      bottomFooter.style.display = 'none';
    } else {
      bottomFooter.style.display = 'block';
    }
  }

  // 滾動事件（帶節流優化）
  let scrollTimeout;
  function handleScroll() {
    updateReadingProgress();
    
    // 節流處理章節跟踪，避免過度頻繁更新
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateCurrentSection, 50);
    
    // 更新搜索按鈕顯示狀態
    updateBottomSearchButtonsVisibility();
  }
  
  window.addEventListener('scroll', handleScroll);
  
  // 窗口大小變化時更新搜索按鈕狀態
  window.addEventListener('resize', () => {
    setTimeout(updateBottomSearchButtonsVisibility, 100);
  });
  
  updateReadingProgress();
  updateCurrentSection(); // 初始化當前章節


  // 平滑滾動章節內 TOC 與回到頂部
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, null, href);
      }
    });
  });

  // ========== 目录折叠控制功能 ==========
  
  // 初始化目录折叠控制（首页和章节页面都需要）
  initTocCollapseControl();
  initFloatingLevelControls();
  
  function initTocCollapseControl() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 检测实际的目录层级并隐藏不必要的按钮
    const maxLevel = detectAndHideLevelButtons(tocContainer);
    
    // 根據頁面類型設定不同的默認值
    const isChapterPage = document.getElementById('chapter-toc') !== null;
    const defaultLevel = isChapterPage ? '3' : '2'; // 章節頁面默認第3層，首頁默認第2層
    
    // 获取用户保存的偏好，使用對應的默認值
    const rawSavedLevel = localStorage.getItem('toc-display-level') || defaultLevel;
    
    // 智能選擇可用的層級
    const validLevel = selectValidLevel(rawSavedLevel, maxLevel, defaultLevel, tocContainer);
    
    // 初始化按钮状态
    updateLevelButtonsActive(validLevel);
    
    // 根据智能选择的层级设置初始显示
    setTocDisplayLevel(validLevel);
    
    // 绑定层级切换按钮事件
    bindLevelControlEvents();
    
    // 为有展开图标的目录项添加 toc-expandable 类
    initializeTocExpandableItems();
    
    // 绑定展开/折叠图标事件
    bindExpandCollapseEvents();
    
    // 绑定全部展开/折叠按钮事件
    bindExpandAllEvents();
  }
  
  // 智能選擇可用的層級
  function selectValidLevel(savedLevel, maxLevel, defaultLevel, tocContainer) {
    const savedLevelNum = parseInt(savedLevel);
    const maxLevelNum = parseInt(maxLevel);
    const defaultLevelNum = parseInt(defaultLevel);
    
    // 檢查當前頁面實際存在的層級（有內容的層級）
    const availableLevels = [];
    
    // 檢查每個層級是否有實際的目錄項目
    for (let level = 1; level <= maxLevelNum; level++) {
      const itemsAtLevel = tocContainer.querySelectorAll(`.toc-item[data-level="${level}"]`);
      if (itemsAtLevel.length > 0) {
        availableLevels.push(level);
      }
    }
    
    // 也檢查是否有對應的層級按鈕可見
    const visibleButtons = [];
    const allLevelButtons = document.querySelectorAll('.toc-level-btn, .floating-level-btn');
    allLevelButtons.forEach(btn => {
      const level = parseInt(btn.getAttribute('data-level'));
      if (btn.style.display !== 'none' && !btn.hasAttribute('data-hidden-level')) {
        if (!visibleButtons.includes(level)) {
          visibleButtons.push(level);
        }
      }
    });
    
    // 取交集：既有內容又有按鈕的層級
    const validLevels = availableLevels.filter(level => visibleButtons.includes(level));
    
    console.log('有內容的層級:', availableLevels, '可見按鈕層級:', visibleButtons, '有效層級:', validLevels);
    console.log('保存的層級:', savedLevelNum, '最大層級:', maxLevelNum);
    
    // 如果保存的層級在有效層級中，直接使用
    if (validLevels.includes(savedLevelNum)) {
      console.log('使用保存的層級:', savedLevelNum);
      return savedLevel;
    }
    
    // 如果保存的層級不可用，選擇最接近的有效層級
    if (validLevels.length === 0) {
      console.warn('沒有找到有效層級，使用默認值');
      return defaultLevel;
    }
    
    // 找到最接近保存層級的有效層級
    let selectedLevel = validLevels[0];
    let minDistance = Math.abs(validLevels[0] - savedLevelNum);
    
    for (const level of validLevels) {
      const distance = Math.abs(level - savedLevelNum);
      if (distance < minDistance) {
        minDistance = distance;
        selectedLevel = level;
      }
    }
    
    console.log('智能選擇的層級:', selectedLevel, '原因: 最接近保存的層級', savedLevelNum);
    return selectedLevel.toString();
  }

  // 检测目录实际层级并隐藏不必要的层级按钮
  function detectAndHideLevelButtons(tocContainer) {
    let maxLevel = 1; // 默认至少有第1层
    
    // 检测所有目录项的层级
    const tocItems = tocContainer.querySelectorAll('.toc-item[data-level]');
    tocItems.forEach(item => {
      const level = parseInt(item.getAttribute('data-level'));
      if (level > maxLevel) {
        maxLevel = level;
      }
    });
    
    // 也检查传统的嵌套结构（ul > li）
    const nestedItems = tocContainer.querySelectorAll('ul li');
    if (nestedItems.length > 0) {
      // 计算嵌套深度
      nestedItems.forEach(item => {
        let depth = 1;
        let parent = item.parentElement;
        while (parent && parent !== tocContainer) {
          if (parent.tagName === 'UL') {
            depth++;
          }
          parent = parent.parentElement;
        }
        if (depth > maxLevel) {
          maxLevel = depth;
        }
      });
    }
    
    console.log('检测到的最大目录层级:', maxLevel);
    
    // 隐藏超出实际层级的按钮
    const allLevelButtons = document.querySelectorAll('.toc-level-btn, .floating-level-btn');
    allLevelButtons.forEach(btn => {
      const buttonLevel = parseInt(btn.getAttribute('data-level'));
      if (buttonLevel > maxLevel) {
        btn.style.display = 'none';
        // 同时为其父容器添加一个属性，表示这个按钮被隐藏了
        btn.setAttribute('data-hidden-level', 'true');
      } else {
        btn.style.display = '';
        btn.removeAttribute('data-hidden-level');
      }
    });
    
    // 返回检测到的最大层级，供其他函数使用
    return maxLevel;
  }
  
  function bindLevelControlEvents() {
    const levelButtons = document.querySelectorAll('.toc-level-btn');
    levelButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括浮动按钮）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateLevelButtonsActive(activeLevel) {
    // 保持向后兼容，但现在使用统一的更新函数
    updateAllLevelButtonsActive(activeLevel);
  }
  
  function setTocDisplayLevel(level) {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const allItems = tocContainer.querySelectorAll('.toc-item');
    const targetLevel = parseInt(level);
    
    // 清除所有手動標記，讓層級控制重新接管
    allItems.forEach(item => {
      item.removeAttribute('data-user-toggled');
      item.removeAttribute('data-manually-shown');
    });
    
    allItems.forEach(item => {
      const itemLevel = parseInt(item.getAttribute('data-level'));
      
      // 根據層級控制顯示/隱藏
      if (itemLevel <= targetLevel) {
        item.classList.remove('hidden');
      } else {
        item.classList.add('hidden');
      }
      
      // 重新設置圖標狀態
      const expandIcon = item.querySelector('.toc-expand-icon');
      if (expandIcon) {
        if (itemLevel < targetLevel) {
          // 小於目標層級的項目自動展開
          expandIcon.classList.remove('collapsed');
          expandIcon.textContent = '▼';
        } else if (itemLevel === targetLevel) {
          // 等於目標層級的項目設為折疊狀態
          expandIcon.classList.add('collapsed');
          expandIcon.textContent = '▶';
        }
      }
    });
  }
  
  // 同步图标状态与实际展开状态
  function syncIconStates() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const expandableItems = tocContainer.querySelectorAll('.toc-item.toc-expandable');
    expandableItems.forEach(item => {
      const icon = item.querySelector('.toc-expand-icon');
      if (icon) {
        const actuallyExpanded = hasVisibleDirectChildren(item);
        
        if (actuallyExpanded) {
          icon.classList.remove('collapsed');
          icon.textContent = '▼';
        } else {
          icon.classList.add('collapsed');
          icon.textContent = '▶';
        }
      }
    });
  }

  // 初始化可展开的目录项
  function initializeTocExpandableItems() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 为所有有展开图标的目录项添加 toc-expandable 类
    const itemsWithIcons = tocContainer.querySelectorAll('.toc-item .toc-expand-icon');
    itemsWithIcons.forEach(icon => {
      const tocItem = icon.closest('.toc-item');
      if (tocItem) {
        tocItem.classList.add('toc-expandable');
      }
    });
    
    // 同步图标状态
    syncIconStates();
  }

  // 检查一个目录项是否有可见的直接子项
  function hasVisibleDirectChildren(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    
    // 首先检查嵌套结构（首页TOC）：查找直接的ul子元素
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const directChildren = nestedUl.querySelectorAll(':scope > .toc-item');
      for (let child of directChildren) {
        if (!child.classList.contains('hidden')) {
          return true;
        }
      }
      return false;
    }
    
    // 然后检查扁平结构（章节页TOC）：查找兄弟元素
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      if (siblingLevel === parentLevel + 1) {
        // 这是直接子项，检查是否可见
        if (!nextSibling.classList.contains('hidden')) {
          return true;
        }
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
    
    return false;
  }

  function bindExpandCollapseEvents() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 使用事件委托处理展开/折叠和跳转
    tocContainer.addEventListener('click', function(e) {
      // 检查是否直接点击了链接文字
      if (e.target.tagName === 'A') {
        // 直接点击链接文字，允许默认行为（页面跳转）
        return;
      }
      
      // 查找最近的目录项
      const tocItem = e.target.closest('.toc-item');
      if (!tocItem) return;
      
      // 检查是否点击了可展开的目录项（有三角形图标的）
      const expandableItem = tocItem.classList.contains('toc-expandable') ? tocItem : null;
      if (expandableItem) {
        e.preventDefault();
        e.stopPropagation();
        
        const icon = expandableItem.querySelector('.toc-expand-icon');
        if (icon) {
          // 检查实际的展开状态：查看是否有可见的直接子项
          const actuallyExpanded = hasVisibleDirectChildren(expandableItem);
          
          // 标记这个项目已经被用户手动操作
          expandableItem.setAttribute('data-user-toggled', 'true');
          
          if (actuallyExpanded) {
            // 当前已展开，执行折叠
            collapseTocItem(expandableItem);
            icon.classList.add('collapsed');
            icon.textContent = '▶';
          } else {
            // 当前已折叠，执行展开
            expandTocItem(expandableItem);
            icon.classList.remove('collapsed');
            icon.textContent = '▼';
          }
        }
      } else {
        // 这是没有展开图标的目录项（叶子节点），处理整行点击跳转
        const link = tocItem.querySelector('a');
        if (link && !e.target.closest('a')) {
          // 点击的是目录项但不是链接本身，触发链接跳转
          e.preventDefault();
          e.stopPropagation();
          
          // 模拟点击链接
          link.click();
        }
      }
    });
  }
  
  function expandTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    const parentChapter = parentItem.getAttribute('data-chapter');
    
    // 首先检查嵌套结构（首页TOC）
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const directChildren = nestedUl.querySelectorAll(':scope > .toc-item');
      directChildren.forEach(child => {
        const childLevel = parseInt(child.getAttribute('data-level'));
        const childChapter = child.getAttribute('data-chapter');
        
        // 只展開同一章節且是直接子項的項目
        if (childLevel === parentLevel + 1 && childChapter === parentChapter) {
          child.classList.remove('hidden');
          child.setAttribute('data-manually-shown', 'true');
        }
      });
      return;
    }
    
    // 处理扁平结构（章节页TOC）
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      const siblingChapter = nextSibling.getAttribute('data-chapter');
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      // 只處理同一章節的子項目
      if (siblingLevel === parentLevel + 1 && siblingChapter === parentChapter) {
        // 这是直接子项，显示它
        nextSibling.classList.remove('hidden');
        // 添加标记，表示这是用户手动展开的
        nextSibling.setAttribute('data-manually-shown', 'true');
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function collapseTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    const parentChapter = parentItem.getAttribute('data-chapter');
    
    // 首先检查嵌套结构（首页TOC）
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const allChildren = nestedUl.querySelectorAll('.toc-item');
      allChildren.forEach(child => {
        const childLevel = parseInt(child.getAttribute('data-level'));
        const childChapter = child.getAttribute('data-chapter');
        
        // 只收縮同一章節且層級更深的項目
        if (childLevel > parentLevel && childChapter === parentChapter) {
          child.classList.add('hidden');
          child.removeAttribute('data-manually-shown');
          const childIcon = child.querySelector('.toc-expand-icon');
          if (childIcon) {
            childIcon.classList.add('collapsed');
            childIcon.textContent = '▶';
          }
        }
      });
      return;
    }
    
    // 处理扁平结构（章节页TOC）
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      const siblingChapter = nextSibling.getAttribute('data-chapter');
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      // 只處理同一章節的子項目
      if (siblingChapter === parentChapter) {
        // 这是子项，隐藏它，并同时折叠其展开状态
        nextSibling.classList.add('hidden');
        // 清除手动展开标记
        nextSibling.removeAttribute('data-manually-shown');
        const childIcon = nextSibling.querySelector('.toc-expand-icon');
        if (childIcon) {
          childIcon.classList.add('collapsed');
          childIcon.textContent = '▶';
        }
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function bindExpandAllEvents() {
    // 移除了全部展开/折叠按钮，因为现在只有3个层级按钮
    // 功能已经整合到层级按钮中
  }
  
  // ========== 浮动层级控制功能 ==========
  
  // 检测固定层级控制按钮是否在视窗中可见
  function areTocControlsVisible() {
    const tocControls = document.querySelector('.toc-level-controls');
    if (!tocControls) return false;
    
    const rect = tocControls.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 检查控制按钮是否在视窗内可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 检测目录内容是否在视窗中可见（确保有目录需要控制）
  function isTocContentVisible() {
    const mainToc = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!mainToc) return false;
    
    const rect = mainToc.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 目录内容的任何部分在视窗内都算可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 更新浮动层级控制的显示状态（全局函数，供搜索功能调用）
  function updateFloatingControlsState() {
    const floatingControls = document.getElementById('floating-level-controls');
    if (!floatingControls) return;
    
    const currentScrollY = window.scrollY;
    const isMobile = window.innerWidth <= 600;
    const scrollThreshold = isMobile ? 100 : 200;
    
    // 检查固定控制按钮是否可见
    const areControlsVisible = areTocControlsVisible();
    // 检查目录内容是否可见（确保有内容需要控制）
    const isTocContentAvailable = isTocContentVisible();
    
    // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
    const shouldShow = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
    
    if (shouldShow) {
      floatingControls.style.display = 'block';
    } else {
      floatingControls.style.display = 'none';
    }
  }
  
  function initFloatingLevelControls() {
    const floatingControls = document.getElementById('floating-level-controls');
    const tocControls = document.querySelector('.toc-level-controls');
    
    if (!floatingControls || !tocControls) return;
    
    // 确保浮动控制也应用层级检测（以防在初始化时有时序问题）
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (tocContainer) {
      detectAndHideLevelButtons(tocContainer);
    }
    
    // 调试模式：检查元素是否正确创建
    const debugMode = window.location.hash.includes('debug');
    if (debugMode) {
      console.log('FloatingControls found:', floatingControls);
      console.log('Screen size:', window.innerWidth, 'x', window.innerHeight);
      console.log('Device pixel ratio:', window.devicePixelRatio);
      console.log('User agent:', navigator.userAgent);
    }
    
    // 绑定浮动按钮事件
    bindFloatingLevelEvents();
    
    // 绑定浮动层级控制的收縮/展開功能
    initFloatingLevelToggle();
    
    // 样式重置函数 - 清除JavaScript设置的内联样式
    function resetFloatingControlsStyles() {
      floatingControls.style.removeProperty('right');
      floatingControls.style.removeProperty('zIndex');
      floatingControls.style.removeProperty('position');
      if (debugMode) {
        console.log('Floating controls styles reset');
      }
    }
    
    // 重新应用正确的样式
    function applyCorrectStyles() {
      const isMobile = window.innerWidth <= 600;
      const isSmallMobile = window.innerWidth <= 400;
      
      if (isMobile) {
        // 移动端保持右側定位，設置必要的樣式
        floatingControls.style.zIndex = '10000';
        floatingControls.style.position = 'fixed';
        floatingControls.style.right = isSmallMobile ? '5px' : '8px';
        // 移除 left 設定，確保右側定位
        floatingControls.style.removeProperty('left');
      } else {
        // 桌面端时清除所有内联样式，让CSS媒体查询生效
        resetFloatingControlsStyles();
      }
      
      if (debugMode) {
        console.log('Styles applied for:', isMobile ? 'mobile' : 'desktop', 
                   `(${window.innerWidth}px)`);
      }
    }

    // 监听滚动，控制浮动按钮显示
    let lastScrollY = window.scrollY;
    const tocControlsRect = tocControls.getBoundingClientRect();
    const initialTop = tocControlsRect.top + window.scrollY;
    
    function handleScroll() {
      const currentScrollY = window.scrollY;
      // 检测移动端，降低显示门槛
      const isMobile = window.innerWidth <= 600;
      const scrollThreshold = isMobile ? 100 : 200; // 移动端更早显示
      
      // 检查固定控制按钮是否可见
      const areControlsVisible = areTocControlsVisible();
      // 检查目录内容是否可见
      const isTocContentAvailable = isTocContentVisible();
      
      // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
      const shouldShowFloating = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
      
      // 调试输出
      if (debugMode && currentScrollY > 50) {
        console.log(`Scroll: ${currentScrollY}px, Mobile: ${isMobile}, Threshold: ${scrollThreshold}, ControlsVisible: ${areControlsVisible}, TocContentVisible: ${isTocContentAvailable}, Show: ${shouldShowFloating}`);
      }
      
      if (shouldShowFloating) {
        // 滚动时显示浮动版本（仅当固定按钮不可见但目录内容可见时）
        floatingControls.style.display = 'block';
        // 应用正确的样式（基于当前屏幕尺寸）
        applyCorrectStyles();
      } else {
        // 页面顶部时、固定按钮可见时、或目录内容不可见时隐藏浮动版本
        floatingControls.style.display = 'none';
      }
      
      lastScrollY = currentScrollY;
    }
    
    // 添加滚动监听
    window.addEventListener('scroll', handleScroll, { passive: true });
    
    // 添加窗口大小变化监听（处理屏幕旋转）
    let resizeTimeout;
    window.addEventListener('resize', () => {
      // 去抖动处理，避免resize过程中频繁触发
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (debugMode) {
          console.log('Resize detected, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        // 重新应用字体设置，确保在屏幕尺寸变化时字体调整依然有效
        applyReadingSettings();
        // 重置所有内联样式，然后重新应用
        resetFloatingControlsStyles();
        handleScroll(); // 重新检查显示状态和应用样式
      }, 150); // 增加延迟确保resize完全完成
    }, { passive: true });
    
    // 添加方向变化监听（移动端特有）
    function handleOrientationChange() {
      setTimeout(() => {
        if (debugMode) {
          console.log('Orientation changed, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        // 重新应用字体设置，确保方向变化后字体调整依然有效
        applyReadingSettings();
        resetFloatingControlsStyles();
        handleScroll();
      }, 200);
    }
    
    if (screen && screen.orientation) {
      screen.orientation.addEventListener('change', handleOrientationChange);
    } else {
      // 兼容旧浏览器的方向变化检测
      window.addEventListener('orientationchange', handleOrientationChange);
    }
    
    // 初始状态
    handleScroll();
  }
  
  function initFloatingLevelToggle() {
    const toggleBtn = document.getElementById('floating-level-toggle');
    const floatingControls = document.getElementById('floating-level-controls');
    
    if (!toggleBtn || !floatingControls) return;
    
    // 獲取保存的收縮狀態，默認為展開（false）
    const savedState = localStorage.getItem('floating-level-collapsed');
    const isCollapsed = savedState === 'true'; // 只有明確設置為 'true' 才收縮，其他情況（包括 null）都展開
    
    // 應用保存的狀態
    if (isCollapsed) {
      floatingControls.classList.add('collapsed');
      toggleBtn.innerHTML = '↔';
      toggleBtn.title = getI18nText('level_control.collapse_expand', false, '收縮/展開層級控制');
    } else {
      floatingControls.classList.remove('collapsed');
      toggleBtn.innerHTML = '⇄';
      toggleBtn.title = getI18nText('level_control.collapse_expand', false, '收縮/展開層級控制');
    }
    
    // 綁定點擊事件
    toggleBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      
      const isNowCollapsed = floatingControls.classList.contains('collapsed');
      
      if (isNowCollapsed) {
        // 展開
        floatingControls.classList.remove('collapsed');
        toggleBtn.innerHTML = '⇄';
        localStorage.setItem('floating-level-collapsed', 'false');
      } else {
        // 收縮
        floatingControls.classList.add('collapsed');
        toggleBtn.innerHTML = '↔';
        localStorage.setItem('floating-level-collapsed', 'true');
      }
    });
  }
  
  function bindFloatingLevelEvents() {
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括顶部和浮动）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateAllLevelButtonsActive(activeLevel) {
    // 更新顶部按钮
    const topButtons = document.querySelectorAll('.toc-level-btn');
    topButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
    
    // 更新浮动按钮
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
  }


  // ============================================================
  // 08-qa-audio.js — QA 答疑章節的逐段音檔播放（含底部浮動播放器）
  //
  // 僅 qa/ 資料夾轉出的章節含 .qa-play 按鈕（data-audio/-start/-end/-label）。
  // 點擊後從指定時間播放對應 .opus 音檔，到段落結束自動停止，並在畫面底部
  // 顯示一個浮動迷你播放器（音檔名稱 + 起訖時間 + 可拖拉進度條 + ±5s + 暫停 +
  // 音量控制：b站風格，列上只有一個喇叭鈕，點擊後彈出垂直音量滑桿
  // （頂部 0–100 數字 + 已達到的音量以主色填滿軌道），音量值存於 localStorage 以便跨頁保留）。
  //
  // 首次載入（或跳到尚未緩衝的時間點）時，播放鈕與迷你播放器會顯示載入中
  // 狀態與緩衝進度，避免使用者以為沒反應。
  //
  // data-audio 為 percent-encoded 的相對路徑（../audio/<檔名>.opus），可避免
  // OpenCC 簡繁轉換破壞中文檔名；顯示時再以 decodeURIComponent 還原。
  //
  // 以具名 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中）。
  // ============================================================
  ;(function () {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('button.qa-play')
    );
    if (!buttons.length) return;

    var SKIP_SECONDS = 5;
    var LOADING_DELAY_MS = 120; // 避免已快取音檔時載入 UI 閃爍
    var VOLUME_STORAGE_KEY = 'qa-volume';

    var audio = new Audio();
    audio.preload = 'none';

    var segEnd = null;       // 目前段落的結束秒數（到此自動停止）
    var segStart = 0;        // 目前段落的起始秒數
    var activeButton = null; // 目前播放中的按鈕
    var isDragging = false;  // 拖拉進度條中
    var isLoading = false;   // 正在等待音檔可播放
    var loadGen = 0;         // 載入世代，用於取消過期回呼
    var loadingDelayTimer = null;
    var savedRangeLabel = '';

    // ---- 底部浮動播放器 ------------------------------------------------
    var bar = document.createElement('div');
    bar.className = 'qa-player';
    bar.setAttribute('aria-hidden', 'true');
    bar.innerHTML =
      '<button class="qa-player-toggle" type="button" aria-label="播放/暫停">▶</button>' +
      '<div class="qa-player-info">' +
        '<div class="qa-player-file"></div>' +
        '<div class="qa-player-range"></div>' +
        '<div class="qa-player-seek-row">' +
          '<button class="qa-player-skip qa-player-skip--back" type="button" aria-label="後退 5 秒">−5s</button>' +
          '<div class="qa-player-progress" role="slider" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" tabindex="0">' +
            '<span class="qa-player-progress-fill"></span>' +
            '<span class="qa-player-progress-thumb"></span>' +
          '</div>' +
          '<button class="qa-player-skip qa-player-skip--fwd" type="button" aria-label="前進 5 秒">+5s</button>' +
          '<div class="qa-player-volume-group">' +
            '<button class="qa-player-volume-btn" type="button" aria-label="音量" aria-expanded="false">' +
              '<svg class="qa-player-volume-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
                '<path class="qa-volume-symbol qa-volume-speaker" d="M3 9v6h4l5 4V5L7 9H3z"/>' +
                '<path class="qa-volume-symbol qa-volume-waves" d="M16 8a4 4 0 0 1 0 8M12 3v18" opacity="0"/>' +
              '</svg>' +
            '</button>' +
            '<div class="qa-player-volume-popup" role="group" aria-label="音量">' +
              '<div class="qa-player-volume-value">100</div>' +
              '<div class="qa-player-volume-track-wrap">' +
                '<input class="qa-player-volume" type="range" min="0" max="100" step="1" value="100" aria-label="音量">' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<button class="qa-player-close" type="button" aria-label="關閉">✕</button>';
    document.body.appendChild(bar);

    var toggleBtn = bar.querySelector('.qa-player-toggle');
    var fileEl = bar.querySelector('.qa-player-file');
    var rangeEl = bar.querySelector('.qa-player-range');
    var progressEl = bar.querySelector('.qa-player-progress');
    var fillEl = bar.querySelector('.qa-player-progress-fill');
    var thumbEl = bar.querySelector('.qa-player-progress-thumb');
    var skipBackBtn = bar.querySelector('.qa-player-skip--back');
    var skipFwdBtn = bar.querySelector('.qa-player-skip--fwd');
    var volumeGroup = bar.querySelector('.qa-player-volume-group');
    var volumeBtn = bar.querySelector('.qa-player-volume-btn');
    var volumeBtnWaves = bar.querySelector('.qa-player-volume-icon .qa-volume-waves');
    var volumeValue = bar.querySelector('.qa-player-volume-value');
    var volumeInput = bar.querySelector('.qa-player-volume');
    var closeBtn = bar.querySelector('.qa-player-close');

    function isTrad() {
      return typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage();
    }

    function qaText(key, fallback, params) {
      if (typeof getI18nText === 'function') {
        return getI18nText(key, isTrad(), fallback, params || {});
      }
      return fallback;
    }

    function decodeName(url) {
      var base = (url || '').split('/').pop();
      try { base = decodeURIComponent(base); } catch (e) {}
      return base;
    }

    function absoluteUrl(url) {
      try { return new URL(url, window.location.href).href; } catch (e) { return url; }
    }

    // ---- 音量控制（b站風格：喇叭鈕點擊後彈出垂直音量滑桿） --------------
    function clampVolume(v) {
      if (!isFinite(v)) return 1;
      return Math.max(0, Math.min(1, v));
    }

    function loadSavedVolume() {
      try {
        var saved = localStorage.getItem(VOLUME_STORAGE_KEY);
        if (saved == null) return 1;
        return clampVolume(parseFloat(saved));
      } catch (e) {
        return 1;
      }
    }

    function saveVolume(v) {
      try { localStorage.setItem(VOLUME_STORAGE_KEY, String(v)); } catch (e) {}
    }

    function updateVolumeUI() {
      var pct = Math.round(clampVolume(audio.volume) * 100);
      var muted = audio.muted || pct === 0;
      // 音量波紋顯示（0 = 靜音時隱藏波紋）
      if (volumeBtnWaves) {
        volumeBtnWaves.setAttribute('opacity', muted ? '0' : '1');
      }
      // 頂部 0–100 數字 + 軌道填色比例（b站風格）
      volumeValue.textContent = String(pct);
      volumeInput.style.setProperty('--qa-volume-pct', pct + '%');
    }

    function setVolumeOpen(open) {
      volumeGroup.classList.toggle('is-open', open);
      volumeBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    // 初始化音量（預設 1，若有上次儲存值則還原）
    audio.volume = loadSavedVolume();
    volumeInput.value = String(Math.round(audio.volume * 100));
    volumeInput.setAttribute('aria-label', qaText('qaAudio.volume', '音量'));
    updateVolumeUI();

    function segmentEndLimit() {
      if (segEnd != null) return segEnd;
      return isFinite(audio.duration) ? audio.duration : segStart;
    }

    function clampToSegment(t) {
      return Math.max(segStart, Math.min(t, segmentEndLimit()));
    }

    function updateProgressUI(currentTime) {
      if (isLoading) return;
      var end = segmentEndLimit();
      var span = end - segStart;
      var pct = 0;
      if (span > 0) {
        pct = ((currentTime - segStart) / span) * 100;
        pct = Math.max(0, Math.min(100, pct));
      }
      fillEl.style.width = pct + '%';
      thumbEl.style.left = pct + '%';
      progressEl.setAttribute('aria-valuenow', String(Math.round(pct)));
    }

    function showBar() {
      bar.classList.add('visible');
      bar.setAttribute('aria-hidden', 'false');
    }

    function getBufferPercent() {
      try {
        if (!audio.buffered || audio.buffered.length === 0) return 0;
        var i;
        for (i = 0; i < audio.buffered.length; i++) {
          if (audio.buffered.start(i) <= segStart && audio.buffered.end(i) >= segStart) {
            return 100;
          }
        }
        var farthest = 0;
        var covered = 0;
        for (i = 0; i < audio.buffered.length; i++) {
          farthest = Math.max(farthest, audio.buffered.end(i));
          covered += audio.buffered.end(i) - audio.buffered.start(i);
        }
        if (audio.duration && isFinite(audio.duration) && audio.duration > 0) {
          return Math.min(99, Math.round((covered / audio.duration) * 100));
        }
        if (segStart > 0) {
          return Math.min(99, Math.round((farthest / segStart) * 100));
        }
        return farthest > 0 ? 50 : 0;
      } catch (e) {
        return -1;
      }
    }

    function setPlayIconLoading(btn, loading) {
      if (!btn) return;
      var icon = btn.querySelector('.qa-play-icon');
      if (!icon) return;
      if (loading) {
        if (!icon.getAttribute('data-play-icon-html')) {
          icon.setAttribute('data-play-icon-html', icon.innerHTML);
        }
        icon.innerHTML = '';
        icon.classList.add('qa-play-icon--spinner');
      } else {
        icon.classList.remove('qa-play-icon--spinner');
        var saved = icon.getAttribute('data-play-icon-html');
        if (saved != null) {
          icon.innerHTML = saved;
          icon.removeAttribute('data-play-icon-html');
        }
        btn.style.removeProperty('--qa-load-pct');
      }
    }

    function applyLoadingVisual(pct) {
      bar.classList.add('is-loading');
      var known = pct > 0;
      progressEl.classList.toggle('is-indeterminate', !known);
      if (known) {
        fillEl.style.width = pct + '%';
        thumbEl.style.left = pct + '%';
        progressEl.setAttribute('aria-valuenow', String(pct));
        rangeEl.textContent = qaText(
          'qaAudio.loadingProgress',
          '正在載入音檔… ' + pct + '%',
          { pct: pct }
        );
        if (activeButton) {
          activeButton.style.setProperty('--qa-load-pct', pct + '%');
        }
      } else {
        rangeEl.textContent = qaText('qaAudio.loading', '正在載入音檔…');
        if (activeButton) {
          activeButton.style.setProperty('--qa-load-pct', '0%');
        }
      }
      toggleBtn.classList.add('is-loading');
      toggleBtn.setAttribute('aria-label', qaText('qaAudio.loading', '正在載入音檔…'));
      toggleBtn.setAttribute('aria-busy', 'true');
      if (activeButton) {
        activeButton.classList.add('loading');
        activeButton.setAttribute('aria-busy', 'true');
        setPlayIconLoading(activeButton, true);
      }
    }

    function clearLoadingVisual() {
      bar.classList.remove('is-loading');
      progressEl.classList.remove('is-indeterminate');
      toggleBtn.classList.remove('is-loading');
      toggleBtn.removeAttribute('aria-busy');
      buttons.forEach(function (b) {
        b.classList.remove('loading');
        b.removeAttribute('aria-busy');
        setPlayIconLoading(b, false);
      });
      if (savedRangeLabel) {
        rangeEl.textContent = savedRangeLabel;
      }
    }

    function updateLoadProgress() {
      if (!isLoading) return;
      var pct = getBufferPercent();
      applyLoadingVisual(pct);
    }

    function beginLoading() {
      if (loadingDelayTimer) {
        clearTimeout(loadingDelayTimer);
        loadingDelayTimer = null;
      }
      isLoading = true;
      // 短延遲後再顯示，避免本機快取命中時閃一下
      loadingDelayTimer = setTimeout(function () {
        loadingDelayTimer = null;
        if (!isLoading) return;
        updateLoadProgress();
      }, LOADING_DELAY_MS);
    }

    function endLoading() {
      if (loadingDelayTimer) {
        clearTimeout(loadingDelayTimer);
        loadingDelayTimer = null;
      }
      if (!isLoading && !bar.classList.contains('is-loading')) return;
      isLoading = false;
      clearLoadingVisual();
      updateProgressUI(audio.currentTime || segStart);
    }

    function setPlayingUI(isPlaying) {
      if (!toggleBtn.classList.contains('is-loading')) {
        toggleBtn.textContent = isPlaying ? '⏸' : '▶';
        toggleBtn.setAttribute('aria-label', isPlaying ? '暫停' : '播放');
      }
      buttons.forEach(function (b) { b.classList.remove('playing'); });
      if (activeButton && isPlaying) activeButton.classList.add('playing');
    }

    function stopPlayback() {
      audio.pause();
      endLoading();
      setPlayingUI(false);
    }

    function seekTo(time, updateUi) {
      var t = clampToSegment(time);
      try { audio.currentTime = t; } catch (e) {}
      if (updateUi !== false) updateProgressUI(t);
      return t;
    }

    function seekFromClientX(clientX) {
      var rect = progressEl.getBoundingClientRect();
      if (!rect.width) return segStart;
      var ratio = (clientX - rect.left) / rect.width;
      ratio = Math.max(0, Math.min(1, ratio));
      var end = segmentEndLimit();
      return seekTo(segStart + ratio * (end - segStart));
    }

    function skipBy(delta) {
      if (!activeButton || isLoading) return;
      seekTo(audio.currentTime + delta);
      if (audio.paused) {
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      }
    }

    function playSegment(btn) {
      var url = btn.getAttribute('data-audio');
      if (!url) return;
      var myGen = ++loadGen;
      segStart = parseFloat(btn.getAttribute('data-start')) || 0;
      var end = parseFloat(btn.getAttribute('data-end'));
      segEnd = isNaN(end) ? null : end;
      activeButton = btn;

      savedRangeLabel = btn.getAttribute('data-label') || '';
      fileEl.textContent = decodeName(url);
      rangeEl.textContent = savedRangeLabel;
      updateProgressUI(segStart);
      showBar();
      beginLoading();

      var seekAndPlay = function () {
        if (myGen !== loadGen) return;
        seekTo(segStart);
        var p = audio.play();
        if (p && p.catch) {
          p.catch(function () {
            if (myGen === loadGen) endLoading();
          });
        }
      };

      if (absoluteUrl(url) !== audio.src) {
        audio.src = url;
        audio.addEventListener('loadedmetadata', seekAndPlay, { once: true });
        audio.load();
      } else if (audio.readyState >= 1) {
        seekAndPlay();
      } else {
        audio.addEventListener('loadedmetadata', seekAndPlay, { once: true });
        audio.load();
      }
    }

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        // 點擊正在播放的同一段 → 暫停
        if (activeButton === btn && !audio.paused) {
          stopPlayback();
          return;
        }
        // 點擊正在載入的同一段 → 取消載入
        if (activeButton === btn && isLoading) {
          loadGen += 1;
          stopPlayback();
          return;
        }
        playSegment(btn);
      });
    });

    audio.addEventListener('timeupdate', function () {
      if (isDragging || isLoading) return;
      if (segEnd != null && audio.currentTime >= segEnd) {
        stopPlayback();
        updateProgressUI(segEnd);
        return;
      }
      updateProgressUI(audio.currentTime);
    });

    audio.addEventListener('progress', function () {
      if (isLoading) updateLoadProgress();
    });

    audio.addEventListener('waiting', function () {
      if (!activeButton || audio.paused) return;
      beginLoading();
      updateLoadProgress();
    });

    audio.addEventListener('playing', function () {
      endLoading();
      setPlayingUI(true);
    });

    audio.addEventListener('play', function () { setPlayingUI(true); });
    audio.addEventListener('pause', function () {
      if (!isLoading) setPlayingUI(false);
    });
    audio.addEventListener('ended', function () { stopPlayback(); });
    audio.addEventListener('error', function () {
      endLoading();
      rangeEl.textContent = qaText('qaAudio.loadError', '音檔載入失敗');
      setPlayingUI(false);
    });

    toggleBtn.addEventListener('click', function () {
      if (!activeButton || isLoading) return;
      if (audio.paused) {
        // 若已播到段落結束，重頭播該段
        if (segEnd != null && audio.currentTime >= segEnd) {
          seekTo(segStart);
        }
        beginLoading();
        var p = audio.play();
        if (p && p.catch) p.catch(function () { endLoading(); });
      } else {
        audio.pause();
      }
    });

    skipBackBtn.addEventListener('click', function () { skipBy(-SKIP_SECONDS); });
    skipFwdBtn.addEventListener('click', function () { skipBy(SKIP_SECONDS); });

    volumeBtn.addEventListener('click', function () {
      setVolumeOpen(!volumeGroup.classList.contains('is-open'));
    });

    // 點擊控制區外或按 Esc 時關閉音量彈出層
    document.addEventListener('pointerdown', function (e) {
      if (!volumeGroup.classList.contains('is-open')) return;
      if (!volumeGroup.contains(e.target)) {
        setVolumeOpen(false);
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && volumeGroup.classList.contains('is-open')) {
        setVolumeOpen(false);
        volumeBtn.focus();
      }
    });

    volumeInput.addEventListener('input', function () {
      var v = clampVolume((parseFloat(volumeInput.value) || 0) / 100);
      audio.volume = v;
      if (v === 0) {
        audio.muted = true;
      } else if (audio.muted) {
        audio.muted = false;
      }
      updateVolumeUI();
      saveVolume(v);
    });

    progressEl.addEventListener('pointerdown', function (e) {
      if (!activeButton || isLoading) return;
      isDragging = true;
      fillEl.style.transition = 'none';
      thumbEl.style.transition = 'none';
      progressEl.setPointerCapture(e.pointerId);
      seekFromClientX(e.clientX);
      e.preventDefault();
    });

    progressEl.addEventListener('pointermove', function (e) {
      if (!isDragging) return;
      seekFromClientX(e.clientX);
    });

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      fillEl.style.transition = '';
      thumbEl.style.transition = '';
      if (e && progressEl.hasPointerCapture(e.pointerId)) {
        progressEl.releasePointerCapture(e.pointerId);
      }
    }

    progressEl.addEventListener('pointerup', endDrag);
    progressEl.addEventListener('pointercancel', endDrag);

    progressEl.addEventListener('keydown', function (e) {
      if (!activeButton || isLoading) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        skipBy(-SKIP_SECONDS);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        skipBy(SKIP_SECONDS);
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        toggleBtn.click();
      }
    });

    closeBtn.addEventListener('click', function () {
      loadGen += 1;
      stopPlayback();
      setVolumeOpen(false);
      bar.classList.remove('visible');
      bar.setAttribute('aria-hidden', 'true');
    });
  })();
// ============================================================
// 09-image-lightbox.js — 章節內嵌圖 lightbox（原圖／縮放／同頁切換）
//
// 點擊 img[src*="assets/images/"] 開啟；同頁前後張；適窗／縮放／拖曳。
// 獨立 IIFE，避免與共享 DOMContentLoaded 作用域碰撞。
// ============================================================

(function () {
  const IMG_SEL = 'img[src*="assets/images/"]';
  const MIN_SCALE = 0.25;
  const MAX_SCALE = 8;
  const ZOOM_STEP = 1.25;

  let root = null;
  let stage = null;
  let imgEl = null;
  let counterEl = null;
  let btnPrev = null;
  let btnNext = null;
  let btnJump = null;
  let btnClose = null;
  let btnZoomIn = null;
  let btnZoomOut = null;
  let btnReset = null;

  let gallery = [];
  let index = 0;
  let open = false;
  let scale = 1;
  let fitScale = 1;
  let tx = 0;
  let ty = 0;
  let naturalW = 0;
  let naturalH = 0;

  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragOriginTx = 0;
  let dragOriginTy = 0;
  let moved = false;

  let pinchActive = false;
  let pinchStartDist = 0;
  let pinchStartScale = 1;
  let lastTapTime = 0;

  function t(sim, trad) {
    if (typeof getText === 'function') return getText(sim, trad);
    return trad;
  }

  function collectGallery() {
    return Array.from(document.querySelectorAll(IMG_SEL));
  }

  function ensureDom() {
    if (root) return;

    root = document.createElement('div');
    root.className = 'img-lightbox';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-label', t('图片查看', '圖片檢視'));

    const toolbar = document.createElement('div');
    toolbar.className = 'img-lightbox__toolbar';

    btnPrev = makeBtn('prev', '‹', t('上一张', '上一張'));
    btnNext = makeBtn('next', '›', t('下一张', '下一張'));
    btnJump = makeBtn('jump', t('跳到问答', '跳到問答'), t('关闭并滚动到该图片所在问答', '關閉並捲動到該圖片所在問答'));
    btnZoomOut = makeBtn('zoom-out', '−', t('缩小', '縮小'));
    btnZoomIn = makeBtn('zoom-in', '+', t('放大', '放大'));
    btnReset = makeBtn('reset', '1:1', t('实际大小', '實際大小'));
    btnClose = makeBtn('close', '×', t('关闭', '關閉'));

    counterEl = document.createElement('span');
    counterEl.className = 'img-lightbox__counter';
    counterEl.setAttribute('aria-live', 'polite');

    toolbar.append(
      btnPrev, counterEl, btnNext, btnJump,
      btnZoomOut, btnZoomIn, btnReset, btnClose,
    );

    stage = document.createElement('div');
    stage.className = 'img-lightbox__stage';

    imgEl = document.createElement('img');
    imgEl.className = 'img-lightbox__img';
    imgEl.alt = '';
    stage.appendChild(imgEl);

    root.append(toolbar, stage);
    document.body.appendChild(root);

    btnPrev.addEventListener('click', (e) => { e.stopPropagation(); go(-1); });
    btnNext.addEventListener('click', (e) => { e.stopPropagation(); go(1); });
    btnJump.addEventListener('click', (e) => { e.stopPropagation(); jumpToSource(); });
    btnZoomIn.addEventListener('click', (e) => { e.stopPropagation(); zoomBy(ZOOM_STEP); });
    btnZoomOut.addEventListener('click', (e) => { e.stopPropagation(); zoomBy(1 / ZOOM_STEP); });
    btnReset.addEventListener('click', (e) => { e.stopPropagation(); toggleFitOrOne(); });
    btnClose.addEventListener('click', (e) => { e.stopPropagation(); closeLightbox(); });

    root.addEventListener('click', (e) => {
      if (moved) {
        moved = false;
        return;
      }
      if (e.target === root || e.target === stage) closeLightbox();
    });

    stage.addEventListener('pointerdown', onPointerDown);
    stage.addEventListener('pointermove', onPointerMove);
    stage.addEventListener('pointerup', onPointerUp);
    stage.addEventListener('pointercancel', onPointerUp);
    stage.addEventListener('wheel', onWheel, { passive: false });
    stage.addEventListener('dblclick', onDblClick);
    stage.addEventListener('touchstart', onTouchStart, { passive: false });
    stage.addEventListener('touchmove', onTouchMove, { passive: false });
    stage.addEventListener('touchend', onTouchEnd);
    stage.addEventListener('touchcancel', onTouchEnd);
  }

  function makeBtn(action, label, title) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'img-lightbox__btn';
    b.dataset.action = action;
    b.textContent = label;
    b.title = title;
    b.setAttribute('aria-label', title);
    return b;
  }

  function applyTransform() {
    imgEl.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  }

  function clampPan() {
    const sw = stage.clientWidth;
    const sh = stage.clientHeight;
    const dw = naturalW * scale;
    const dh = naturalH * scale;
    const maxX = Math.max(0, (dw - sw) / 2);
    const maxY = Math.max(0, (dh - sh) / 2);
    tx = Math.min(maxX, Math.max(-maxX, tx));
    ty = Math.min(maxY, Math.max(-maxY, ty));
  }

  function computeFitScale() {
    const sw = Math.max(1, stage.clientWidth - 16);
    const sh = Math.max(1, stage.clientHeight - 16);
    if (!naturalW || !naturalH) return 1;
    return Math.min(1, sw / naturalW, sh / naturalH);
  }

  function setScale(next, pivotX, pivotY) {
    const prev = scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, next));
    if (pivotX != null && pivotY != null && prev > 0) {
      const rect = stage.getBoundingClientRect();
      const cx = pivotX - rect.left - rect.width / 2;
      const cy = pivotY - rect.top - rect.height / 2;
      const ratio = scale / prev;
      tx = cx - (cx - tx) * ratio;
      ty = cy - (cy - ty) * ratio;
    }
    clampPan();
    applyTransform();
    updateResetLabel();
  }

  function zoomBy(factor, pivotX, pivotY) {
    setScale(scale * factor, pivotX, pivotY);
  }

  function updateResetLabel() {
    const nearFit = Math.abs(scale - fitScale) < 0.02;
    if (nearFit) {
      btnReset.textContent = '1:1';
      btnReset.title = t('实际大小', '實際大小');
      btnReset.setAttribute('aria-label', btnReset.title);
    } else {
      btnReset.textContent = t('适窗', '適窗');
      btnReset.title = t('适合窗口', '適合視窗');
      btnReset.setAttribute('aria-label', btnReset.title);
    }
  }

  function toggleFitOrOne() {
    const nearFit = Math.abs(scale - fitScale) < 0.02;
    if (nearFit) {
      setScale(1);
      tx = 0;
      ty = 0;
      clampPan();
      applyTransform();
    } else {
      fitToViewport();
    }
    updateResetLabel();
  }

  function fitToViewport() {
    fitScale = computeFitScale();
    scale = fitScale;
    tx = 0;
    ty = 0;
    applyTransform();
    updateResetLabel();
  }

  function updateNav() {
    const n = gallery.length;
    counterEl.textContent = n ? `${index + 1} / ${n}` : '0 / 0';
    btnPrev.disabled = index <= 0;
    btnNext.disabled = index >= n - 1;
  }

  function showAt(i) {
    if (i < 0 || i >= gallery.length) return;
    index = i;
    const src = gallery[i].currentSrc || gallery[i].src;
    imgEl.onload = () => {
      naturalW = imgEl.naturalWidth;
      naturalH = imgEl.naturalHeight;
      fitToViewport();
    };
    if (imgEl.src !== src) {
      imgEl.src = src;
    } else if (imgEl.complete && imgEl.naturalWidth) {
      naturalW = imgEl.naturalWidth;
      naturalH = imgEl.naturalHeight;
      fitToViewport();
    }
    updateNav();
  }

  function go(delta) {
    const next = index + delta;
    if (next < 0 || next >= gallery.length) return;
    showAt(next);
  }

  /** Closest Q/A card for the current gallery image; fall back to the img itself. */
  function sourceAnchor() {
    const img = gallery[index];
    if (!img || !document.body.contains(img)) return null;
    return img.closest('.question, .answer') || img;
  }

  function jumpToSource() {
    const target = sourceAnchor();
    closeLightbox();
    if (!target) return;
    // Wait a frame so body overflow is restored before scrolling.
    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (target.id) {
        try {
          history.replaceState(null, '', `#${target.id}`);
        } catch (_) { /* ignore */ }
      }
    });
  }

  function openLightbox(fromImg) {
    ensureDom();
    gallery = collectGallery();
    const i = gallery.indexOf(fromImg);
    if (i < 0) return;
    open = true;
    root.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    showAt(i);
  }

  function closeLightbox() {
    if (!open) return;
    open = false;
    root.classList.remove('is-open');
    document.body.style.overflow = '';
    dragging = false;
    pinchActive = false;
    stage.classList.remove('is-dragging');
  }

  function onPointerDown(e) {
    if (e.pointerType === 'touch') return;
    if (e.button != null && e.button !== 0) return;
    dragging = true;
    moved = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragOriginTx = tx;
    dragOriginTy = ty;
    stage.classList.add('is-dragging');
    try { stage.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
    tx = dragOriginTx + dx;
    ty = dragOriginTy + dy;
    clampPan();
    applyTransform();
  }

  function onPointerUp(e) {
    if (!dragging) return;
    dragging = false;
    stage.classList.remove('is-dragging');
    try { stage.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }

  function onWheel(e) {
    if (!open) return;
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      zoomBy(factor, e.clientX, e.clientY);
    } else {
      // plain wheel also zooms (common for image viewers)
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      zoomBy(factor, e.clientX, e.clientY);
    }
  }

  function onDblClick(e) {
    e.preventDefault();
    toggleFitOrOne();
  }

  function touchDistance(touches) {
    const a = touches[0];
    const b = touches[1];
    const dx = a.clientX - b.clientX;
    const dy = a.clientY - b.clientY;
    return Math.hypot(dx, dy);
  }

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      e.preventDefault();
      pinchActive = true;
      dragging = false;
      pinchStartDist = touchDistance(e.touches);
      pinchStartScale = scale;
      return;
    }
    if (e.touches.length === 1) {
      const now = Date.now();
      if (now - lastTapTime < 300) {
        e.preventDefault();
        toggleFitOrOne();
        lastTapTime = 0;
        return;
      }
      lastTapTime = now;
      dragging = true;
      moved = false;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragOriginTx = tx;
      dragOriginTy = ty;
      stage.classList.add('is-dragging');
    }
  }

  function onTouchMove(e) {
    if (pinchActive && e.touches.length === 2) {
      e.preventDefault();
      const dist = touchDistance(e.touches);
      if (pinchStartDist > 0) {
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        setScale(pinchStartScale * (dist / pinchStartDist), midX, midY);
      }
      return;
    }
    if (dragging && e.touches.length === 1) {
      e.preventDefault();
      const dx = e.touches[0].clientX - dragStartX;
      const dy = e.touches[0].clientY - dragStartY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
      tx = dragOriginTx + dx;
      ty = dragOriginTy + dy;
      clampPan();
      applyTransform();
    }
  }

  function onTouchEnd(e) {
    if (e.touches.length < 2) pinchActive = false;
    if (e.touches.length === 0) {
      dragging = false;
      stage.classList.remove('is-dragging');
    } else if (e.touches.length === 1) {
      dragging = true;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragOriginTx = tx;
      dragOriginTy = ty;
    }
  }

  function onKeyDown(e) {
    if (!open) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeLightbox();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      go(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      go(1);
    } else if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      zoomBy(ZOOM_STEP);
    } else if (e.key === '-' || e.key === '_') {
      e.preventDefault();
      zoomBy(1 / ZOOM_STEP);
    } else if (e.key === '0') {
      e.preventDefault();
      fitToViewport();
    }
  }

  function onDocClick(e) {
    const img = e.target.closest(IMG_SEL);
    if (!img || !document.body.contains(img)) return;
    if (root && root.contains(img)) return;
    e.preventDefault();
    openLightbox(img);
  }

  function onResize() {
    if (!open) return;
    fitScale = computeFitScale();
    if (scale <= fitScale * 1.02) {
      fitToViewport();
    } else {
      clampPan();
      applyTransform();
      updateResetLabel();
    }
  }

  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('resize', onResize);

  W2E.openImageLightbox = openLightbox;
  W2E.closeImageLightbox = closeLightbox;
})();
});
