// ============================================================
// reading-prepaint.js — 閱讀設置引擎（首繪前執行）
//
// 為什麼獨立於 script.js：字級、行距、內容寬度與依字級連動的 TOC／搜尋
// 字級，過去都由 03d-reading-settings.js 在 DOMContentLoaded 才寫進
// document.body.style。章節頁的 body 因此在第一屏是 16px／800px，script.js
// 到位後才變成 20px／834px —— 整頁文字與目錄重新排版，使用者看到明顯位移
// （實測 TOC 縮排 251px → 234px）。
//
// 本檔是 03d 的單一真相來源，以 <script src>（**不加 defer**）在 <head>
// 同步載入並立即套用，03d 之後只負責「使用者改設定時重套」與按鈕 UI。
// 套用方式是寫 <html> 的 CSS 自訂屬性（--w2e-font-size / --w2e-content-width
// / --line-height），由 00-base.css 的 body 規則與本檔注入的動態樣式消費；
// 因為 <body> 還沒建好，不能用 body 的 inline style。
// ============================================================
(function (global) {
  'use strict';

  // 03d 與本檔都在同一個 concatenated scope 之外，故各自判斷頁型。
  // 規則與 00-base.js 的 isIndexPage() 相同。
  function isIndexPage() {
    var f = global.location.pathname.split('/').pop() || 'index.html';
    return f === 'index.html' || f === 'index_trad.html';
  }

// 閱讀設置功能
//
// 字級階梯：預設字級 = 螢幕寬度對應的「基礎值」+ FONT_SIZE_STEP × 該區間的加強級數。
// 加強級數依裝置而異——電腦 +2 級（＝按兩次 A+）、平板 +1 級（＝按一次 A+）、
// 手機不額外加強（維持原預設），因為小螢幕本來就靠基礎值偏大來兼顧可讀性。
// 總目錄頁（index / index_trad）則一律不加強：目錄要能一覽更多章節，
// 字級一大就得多行才有重點、且捲動距離翻倍，反而不好找書。
// 上下界一併留出空間，讓加強後的預設值上下仍各有三級（±6px）可調。
//   下限 14px：12px 的中文在非 Retina 螢幕上筆畫會糊在一起，
//   拉丁文 12px 勉強可讀、中文不行，中文實務下限約 14px。
const FONT_SIZE_STEP = 2;                        // A+／A- 每按一級的 px 差
const FONT_STEPS_SMALL_PHONE = 0;                // ≤400px：不快調
const FONT_STEPS_PHONE = 0;                      // ≤600px：不加調
const FONT_STEPS_TABLET = 1;                     // ≤768px：+1 級（A+ 按一次）
const FONT_STEPS_DESKTOP = 2;                    // >768px：+2 級（A+ 按兩次）
const FONT_SIZE_MIN = 14;
const FONT_SIZE_MAX = 28;
const FONT_BASE_SMALL_PHONE = 19;                // 基礎值（不含加強級數）
const FONT_BASE_PHONE = 18;
const FONT_BASE_TABLET = 17;
const FONT_BASE_DESKTOP = 16;

// 中文長文的行長：每行 30–45 字可讀、35–40 字最舒服。超過 45 字眼睛回到
// 行首時容易跳錯行。內文實際行長 = 內容寬 − 左右 padding(15×2) − 邊框(4)。
const MEASURE_TARGET_CHARS = 40;                 // 目標行長（字／行）
const CONTENT_CHROME_PX = 34;                    // .question/.answer 的 padding + 邊框
const CONTENT_WIDTH_MIN = 600;
const CONTENT_WIDTH_MAX = 1000;
const TOC_CONTENT_WIDTH = 800;                   // 總目錄沿用 800px 固定寬度

const FONT_STEP_KEY = 'fontStep';
const LEGACY_FONT_SIZE_KEY = 'fontSize';

function isHandheldPointer() {
  return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
}

function getBaseFontSize(screenWidth) {
  if (screenWidth <= 400) {
    return FONT_BASE_SMALL_PHONE;
  } else if (screenWidth <= 600) {
    return FONT_BASE_PHONE;
  } else if (screenWidth <= 768) {
    return FONT_BASE_TABLET;
  }
  // 觸控為主（手機／平板橫向）不論視窗多寬都算平板級，避免掉進桌面的 16px 基礎值
  return isHandheldPointer() ? FONT_BASE_TABLET : FONT_BASE_DESKTOP;
}

function getFontBoostSteps(screenWidth) {
  if (screenWidth <= 400) {
    return FONT_STEPS_SMALL_PHONE;
  } else if (screenWidth <= 600) {
    return FONT_STEPS_PHONE;
  } else if (screenWidth <= 768) {
    return FONT_STEPS_TABLET;
  }
  return isHandheldPointer() ? FONT_STEPS_TABLET : FONT_STEPS_DESKTOP;
}

function getDefaultFontSize() {
  const screenWidth = window.innerWidth;
  const base = getBaseFontSize(screenWidth);
  // 總目錄頁維持原預設字級：目錄行數是找書的關鍵，不跟內文一起放大
  if (isIndexPage()) {
    return base;
  }
  return base + FONT_SIZE_STEP * getFontBoostSteps(screenWidth);
}

function clampFontSize(size) {
  return Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, size));
}

function readStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch (e) {
    /* 私密瀏覽／配額滿：偏好存不下就退化成每次用預設 */
  }
}

function removeStorage(key) {
  try {
    localStorage.removeItem(key);
  } catch (e) {
    /* 忽略 */
  }
}

function migrateLegacyFontStep(base) {
  const legacy = parseInt(readStorage(LEGACY_FONT_SIZE_KEY));
  if (isNaN(legacy)) return null;
  const step = Math.round((legacy - base) / FONT_SIZE_STEP);
  writeStorage(FONT_STEP_KEY, step);
  removeStorage(LEGACY_FONT_SIZE_KEY);
  return step;
}

function loadFontStep(base) {
  const stored = parseInt(readStorage(FONT_STEP_KEY));
  if (!isNaN(stored)) return stored;          // 0 是合法值，不能當「沒有」
  const migrated = migrateLegacyFontStep(base);
  return migrated === null ? 0 : migrated;    // 完全沒設定過 = 用預設，不寫回
}

function getDefaultContentWidth(fontSize) {
  // 總目錄維持 800px：章節標題是短標籤不是散文，且沿用既有版面避免大改
  if (isIndexPage()) {
    return TOC_CONTENT_WIDTH;
  }
  const byMeasure = MEASURE_TARGET_CHARS * fontSize + CONTENT_CHROME_PX;
  return Math.max(CONTENT_WIDTH_MIN, Math.min(CONTENT_WIDTH_MAX, Math.round(byMeasure)));
}

function applyTocStyles(fontSize, lineHeight) {
  // 以 <html> 上的 CSS 自訂屬性承載，而不是 body 的 inline style：
  // 本檔在 <head> 內同步執行，早於 <body> 存在，且必須在首繪前就讓
  // 00-base.css 的 body 規則取得正確值，否則字級／行寬／目錄字級會在
  // script.js 到位後整頁重排（章節頁實測 body 由 800px→834px、位移 17px）。
  const root = document.documentElement.style;
  root.setProperty('--w2e-font-size', fontSize + 'px');
  root.setProperty('--w2e-content-width', getContentWidth() + 'px');
  root.setProperty('--line-height', lineHeight);
  
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
  applySearchFontStyles(fontSize, lineHeight);
}

function applySearchFontStyles(fontSize, lineHeight) {
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

  // ---- 狀態（單一真相來源；03d 透過 W2EReading 讀寫）-------------------

  var state = null;

  function compute() {
    var base = getBaseFontSize(global.innerWidth);
    var step = loadFontStep(base);
    var fontSize = clampFontSize(getDefaultFontSize() + step * FONT_SIZE_STEP);
    return {
      fontStep: step,
      fontSize: fontSize,
      lineHeight: parseFloat(readStorage('lineHeight')) || 1.6,
      // getDefaultContentWidth 依「本頁實際字級」算行長，故傳入而非讀全域
      contentWidth: parseInt(readStorage('contentWidth'), 10) || getDefaultContentWidth(fontSize)
    };
  }

  function getContentWidth() {
    return state ? state.contentWidth : getDefaultContentWidth(16);
  }

  /** 套用當前（或指定）設定。冪等，可重複呼叫。 */
  function apply(next) {
    if (next) state = next;
    if (!state) state = compute();
    applyTocStyles(state.fontSize, state.lineHeight);
  }

  global.W2EReading = {
    FONT_SIZE_STEP: FONT_SIZE_STEP,
    FONT_STEP_KEY: FONT_STEP_KEY,
    LEGACY_FONT_SIZE_KEY: LEGACY_FONT_SIZE_KEY,
    FONT_SIZE_MIN: FONT_SIZE_MIN,
    FONT_SIZE_MAX: FONT_SIZE_MAX,
    clampFontSize: clampFontSize,
    getDefaultFontSize: getDefaultFontSize,
    getDefaultContentWidth: getDefaultContentWidth,
    readStorage: readStorage,
    writeStorage: writeStorage,
    getState: function () { return state; },
    /** 重算預設值（視窗寬度可能已變；03d 的 font-normal 走這條） */
    recompute: function () { state = compute(); return state; },
    apply: apply,
    /** 使用者調整字級後回推級數，讓偏好跨裝置成立 */
    setFontSize: function (px) {
      state.fontSize = clampFontSize(px);
      state.fontStep = Math.round((state.fontSize - getDefaultFontSize()) / FONT_SIZE_STEP);
      writeStorage(FONT_STEP_KEY, state.fontStep);
      return state;
    },
    setLineHeight: function (v) {
      state.lineHeight = v;
      writeStorage('lineHeight', v);
      return state;
    },
    setContentWidth: function (v) {
      state.contentWidth = v;
      writeStorage('contentWidth', v);
      return state;
    },
    /** 回到預設字級（不動行距／寬度），對應工具列的「A 正常」 */
    resetFontSize: function () {
      state.fontStep = 0;
      writeStorage(FONT_STEP_KEY, 0);
      state.fontSize = getDefaultFontSize();
      return state;
    }
  };

  // 首繪前立即套用（同步執行，<body> 尚未建立）。
  apply();
})(window);
