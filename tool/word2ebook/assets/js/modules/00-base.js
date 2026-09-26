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
