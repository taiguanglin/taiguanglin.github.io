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

// #region agent log
(function(){
  var root = getComputedStyle(document.documentElement);
  var vars = {
    colorPrimary: root.getPropertyValue('--color-primary').trim(),
    colorPrimaryLight: root.getPropertyValue('--color-primary-light').trim(),
    colorBgPage: root.getPropertyValue('--color-bg-page').trim(),
    radiusSm: root.getPropertyValue('--radius-sm').trim(),
    lineHeight: root.getPropertyValue('--line-height').trim()
  };
  fetch('http://127.0.0.1:7618/ingest/29c0cb97-0ee5-4d63-80f1-c39c24c9f364',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1e1df3'},body:JSON.stringify({sessionId:'1e1df3',hypothesisId:'H-A',location:'00-base.js:runtime',message:'CSS var resolved values',data:vars,timestamp:Date.now()})}).catch(function(){});
})();
// #endregion
