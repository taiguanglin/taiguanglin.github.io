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

// 開發日誌開關（預設關閉、零輸出）：localStorage 設 'w2e:debug'='1' 時，
// 各模組的開發診斷日誌（搜尋索引建立、目錄層級選擇、浮動按鈕、書籤遷移、
// IndexedDB 快取…）才會輸出。一般使用者的 console 保持乾淨；真正的
// 錯誤路徑仍照常 console.warn/error。reading-prepaint.js 與
// search-cache.js 是獨立載入的檔案，各自持有同鍵的本份判斷。
function debugOn() {
  try { return localStorage.getItem('w2e:debug') === '1'; } catch (e) { return false; }
}

// 捲動行為偵錯開關（預設關閉、零輸出）：localStorage 設 'w2e:scrollDebug'='1'
// 時，03d 面板同步與 05／03d 的收斂迴圈會輸出定位過程與「外部捲動介入」
// 警示，供回報畫面閃跳問題時直接提供 console 記錄。
function scrollDebugOn() {
  try { return localStorage.getItem('w2e:scrollDebug') === '1'; } catch (e) { return false; }
}

// 收斂迴圈「單飛」守門（03d settleAnchorTo 與 05 settleInPageAnchor 共用）：
// 每次啟動收斂先 ++w2eSettleRunId 取得自己的回合編號，迴圈每步（含等動畫
// 階段）檢查編號是否仍最新。使用者在前一回合結束前（最短 1.8s）又點了
// 另一個目錄項時，舊目標的迴圈必須立即讓位給新回合——否則兩個 want 不同的
// 迴圈同時對視窗 scrollTo 互搶，畫面就在兩個目標之間來回閃跳
// （2026-10 實測：連點兩個目錄項即重現，stable 不斷歸零）。
let w2eSettleRunId = 0;

// ------------------------------------------------------------------ //
// 暗色模式初始化                                                       //
// 1. 已有偏好（localStorage 'darkMode'）→ 照偏好。                      //
// 2. 首次造訪未設偏好 → 跟隨作業系統 prefers-color-scheme（未寫回偏好， //
//    使用者明確切換後才凍結）。                                        //
// 「防閃爍」由模板 <head> 內聯腳本在首繪前於 <html> 掛 dark-mode；      //
// 這裡在 DOM 就緒後把狀態移到 <body>（版面著色主體），並移除 <html> 上  //
// 的暫時類別（避免內容不足整頁時底部露出深色底）。                      //
// ------------------------------------------------------------------ //

function shouldUseDarkMode() {
  try {
    var pref = localStorage.getItem('darkMode');
    if (pref === 'true') return true;
    if (pref === 'false') return false;
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  } catch (e) {
    return false;
  }
}

if (shouldUseDarkMode()) {
  document.body.classList.add('dark-mode');
}
document.documentElement.classList.remove('dark-mode');
