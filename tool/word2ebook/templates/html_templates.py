"""HTML 模板管理"""

from typing import Dict, Any
from config.settings import Constants


class TemplateManager:
    """HTML 模板管理器"""
    
    def __init__(self):
        self._templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载所有模板"""
        self._templates['chapter'] = self._get_chapter_template()
        self._templates['index'] = self._get_index_template()
    
    def get_template(self, template_name: str) -> str:
        """获取模板"""
        if template_name not in self._templates:
            raise ValueError(f"未知的模板名称: {template_name}")
        return self._templates[template_name]
    
    def render_chapter(self, **kwargs) -> str:
        """渲染章节模板"""
        return self.get_template('chapter').format(**kwargs)
    
    def render_index(self, **kwargs) -> str:
        """渲染首页模板"""
        return self.get_template('index').format(**kwargs)
    
    def _get_chapter_template(self) -> str:
        """章节页面模板"""
        return '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div id="top"></div>
<div class="header-nav">
  <div class="nav-home">
    <a href="{home_link}">🌸 回首頁</a>
  </div>
  <div class="lang-switch">
    {lang_switch_links}
  </div>
</div>

<div class="top-nav">
{top_nav_links}
</div>

{chapter_title}{chapter_qa_count}

<!-- 章節TOC標題和層級控制的水平布局 -->
<div class="toc-header-container">
  <h3 id="chapter-toc-header">本章目錄</h3>
  <div class="toc-level-controls">
    <div class="toc-level-label">显示层级</div>
    <div class="toc-level-buttons-vertical">
      <button class="toc-level-btn" data-level="2" title="显示第2层">2</button>
      <button class="toc-level-btn active" data-level="3" title="显示前3层">3</button>
      <button class="toc-level-btn" data-level="4" title="显示前4层">4</button>
    </div>
  </div>
</div>

<div class="toc" id="chapter-toc">
{chapter_toc}
</div>

<!-- 滚动时显示的浮动层级控制按钮 -->
<div class="floating-level-controls" id="floating-level-controls" style="display: none;">
  <button class="floating-level-toggle" id="floating-level-toggle" title="收縮/展開層級控制">⇄</button>
  <div class="floating-level-content">
    <div class="floating-level-label">层级</div>
    <div class="floating-level-buttons">
      <button class="floating-level-btn" data-level="2" title="显示第2层">2</button>
      <button class="floating-level-btn active" data-level="3" title="显示前3层">3</button>
      <button class="floating-level-btn" data-level="4" title="显示前4层">4</button>
    </div>
  </div>
</div>

{content}

<div class="nav-footer">
{prev_link}
{next_link}
</div>
</body>
</html>'''
    
    def _get_index_template(self) -> str:
        """首页模板"""
        return '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="https://cdn.jsdelivr.net/npm/minisearch@6.3.0/dist/umd/index.min.js"></script>
<script>
// 备用CDN加载
if (typeof MiniSearch === 'undefined') {{
  console.log('主CDN失败，尝试备用CDN...');
  const script = document.createElement('script');
  script.src = 'https://unpkg.com/minisearch@6.3.0/dist/umd/index.min.js';
  script.onload = function() {{
    console.log('备用CDN加载成功');
    // 重新初始化搜索
    if (typeof initSearch === 'function') {{
      initSearch();
    }}
  }};
  script.onerror = function() {{
    console.error('所有CDN都失败了，搜索功能不可用');
    const searchInput = document.getElementById('search-input');
    const searchStatus = document.getElementById('search-status');
    if (searchInput) searchInput.disabled = true;
    if (searchStatus) searchStatus.textContent = getText('搜索功能暂不可用（网络问题）', '搜尋功能暫不可用（網路問題）');
  }};
  document.head.appendChild(script);
}}
</script>
<script src="assets/js/i18n-text.js"></script>
<script src="assets/js/script.js"></script>
</head>
<body>
<div class="header-nav index-header">
  <div class="lang-switch">
    {lang_switch_links}
  </div>
</div>
<h1>{book_title}</h1>

<!-- 搜索激活按钮 -->
<div class="search-activation">
  <button class="search-activate-btn" id="search-activate-btn">
    🔍 启用全文搜索
  </button>
</div>

<!-- 搜索功能（默认隐藏） -->
<div class="search-container" id="search-container" style="display: none;">
  <div class="search-box">
    <input type="text" id="search-input" placeholder="搜索全文内容..." autocomplete="off">
    <div class="search-status" id="search-status">正在初始化搜索功能...</div>
  </div>
  
  <!-- 搜索结果 -->
  <div class="search-results" id="search-results" style="display: none;">
    <div class="search-results-header">
      <span class="search-results-count" id="search-results-count"></span>
      <div class="search-results-actions">
        <button class="search-load-more" id="search-load-more" style="display: none;">显示更多</button>
        <button class="search-load-all" id="search-load-all" style="display: none;">显示全部</button>
        <button class="search-clear" id="search-clear">清除搜索</button>
        <button class="search-collapse" id="search-collapse">收起搜索</button>
      </div>
    </div>
    <ul class="search-results-list" id="search-results-list"></ul>
    
    <!-- 底部控制按鈕 -->
    <div class="search-results-footer">
      <div class="search-results-actions">
        <button class="search-load-more" id="search-load-more-bottom" style="display: none;">显示更多</button>
        <button class="search-load-all" id="search-load-all-bottom" style="display: none;">显示全部</button>
        <button class="search-clear" id="search-clear-bottom">清除搜索</button>
        <button class="search-collapse" id="search-collapse-bottom">收起搜索</button>
      </div>
    </div>
  </div>
</div>

<!-- TOC标题和层级控制的水平布局 -->
<div class="toc-header-container">
  <h2 id="toc-header">Table of Contents</h2>
  <div class="toc-level-controls">
    <div class="toc-level-label">显示层级</div>
    <div class="toc-level-buttons-vertical">
      <button class="toc-level-btn" data-level="1" title="显示第1层">1</button>
      <button class="toc-level-btn active" data-level="2" title="显示前2层">2</button>
      <button class="toc-level-btn" data-level="3" title="显示前3层">3</button>
      <button class="toc-level-btn" data-level="4" title="显示前4层">4</button>
    </div>
  </div>
</div>

<div class="toc" id="main-toc">
{toc_items}
</div>

<!-- 懸浮操作按钮 -->
<div class="action-buttons">
  <div class="action-menu">
    <button class="action-btn menu-btn" data-action="toggle-menu" title="功能菜單">☰</button>
    <div class="action-menu-items">
      <button class="action-btn" data-action="toc" title="書籤">🔖</button>
      <button class="action-btn" data-action="top" title="回到頂部">↑</button>
      <button class="action-btn" data-action="settings" title="設置">⚙️</button>
    </div>
  </div>
</div>

<!-- 懸浮目錄 -->
<div class="floating-toc" id="floating-toc">
  <div class="floating-toc-header">
    <div class="floating-toc-tabs">
      <button class="floating-toc-tab active" data-tab="toc">📖 目錄</button>
      <button class="floating-toc-tab" data-tab="bookmarks">🔖 書籤</button>
    </div>
    <button class="ctrl-btn" data-action="close-toc">✕</button>
  </div>
  
  <div class="floating-toc-content">
    <h3 id="toc-title">📖 章節目錄</h3>
    <ul id="toc-list">
      <!-- 動態生成的首頁TOC內容 -->
    </ul>
    <ul id="bookmarks-list" style="display: none;">
      <!-- 動態生成的書籤內容 -->
    </ul>
  </div>
</div>

<!-- 滚动时显示的浮动层级控制按钮 -->
<div class="floating-level-controls" id="floating-level-controls" style="display: none;">
  <button class="floating-level-toggle" id="floating-level-toggle" title="收縮/展開層級控制">⇄</button>
  <div class="floating-level-content">
    <div class="floating-level-label">层级</div>
    <div class="floating-level-buttons">
      <button class="floating-level-btn" data-level="1" title="显示第1层">1</button>
      <button class="floating-level-btn active" data-level="2" title="显示前2层">2</button>
      <button class="floating-level-btn" data-level="3" title="显示前3层">3</button>
      <button class="floating-level-btn" data-level="4" title="显示前4层">4</button>
    </div>
  </div>
</div>

</body>
</html>'''