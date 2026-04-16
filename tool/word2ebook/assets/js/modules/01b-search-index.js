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
