"""支援國際化的HTML模板管理"""

from typing import Dict, Any
from config.settings import Constants
from utils.config_utils import get_i18n_text


class I18nTemplateManager:
    """支援國際化的HTML模板管理器"""
    
    def __init__(self):
        self._templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """加載所有模板"""
        self._templates['chapter'] = self._get_chapter_template()
        self._templates['index'] = self._get_index_template()
    
    def get_template(self, template_name: str) -> str:
        """獲取模板"""
        if template_name not in self._templates:
            raise ValueError(f"未知的模板名稱: {template_name}")
        return self._templates[template_name]
    
    def render_chapter(self, is_traditional: bool = False, **kwargs) -> str:
        """渲染章節模板"""
        # 獲取國際化文字
        i18n_kwargs = self._get_chapter_i18n_kwargs(is_traditional)
        i18n_kwargs.update(kwargs)
        
        # 設置favicon默認值
        if 'favicon_tag' not in i18n_kwargs:
            i18n_kwargs['favicon_tag'] = ''
            
        return self.get_template('chapter').format(**i18n_kwargs)
    
    def render_index(self, is_traditional: bool = False, **kwargs) -> str:
        """渲染首頁模板"""
        # 獲取國際化文字
        i18n_kwargs = self._get_index_i18n_kwargs(is_traditional)
        i18n_kwargs.update(kwargs)
        
        # 設置favicon默認值
        if 'favicon_tag' not in i18n_kwargs:
            i18n_kwargs['favicon_tag'] = ''
            
        return self.get_template('index').format(**i18n_kwargs)
    
    def _get_chapter_i18n_kwargs(self, is_traditional: bool) -> Dict[str, str]:
        """獲取章節頁面的國際化文字"""
        return {
            'home_text': get_i18n_text('navigation.home', is_traditional, '🏠 回首頁'),
            'chapter_toc_title': get_i18n_text('navigation.chapter_toc', is_traditional, '本章目錄'),
            'previous_chapter': get_i18n_text('ui.previous_chapter', is_traditional, '上一章'),
            'next_chapter': get_i18n_text('ui.next_chapter', is_traditional, '下一章'),
        }
    
    def _get_index_i18n_kwargs(self, is_traditional: bool) -> Dict[str, str]:
        """獲取首頁的國際化文字"""
        return {
            'table_of_contents': get_i18n_text('table_of_contents', is_traditional, '目錄'),
            'activate_search': get_i18n_text('search.activate_search', is_traditional, '🔍 啟用全文搜尋'),
            'search_placeholder': get_i18n_text('search.search_placeholder', is_traditional, '搜尋全文內容...'),
            'search_initializing': get_i18n_text('search.search_initializing', is_traditional, '正在初始化搜尋功能...'),
            'show_more': get_i18n_text('search.show_more', is_traditional, '顯示更多'),
            'show_all': get_i18n_text('search.show_all', is_traditional, '顯示全部'),
            'clear_search': get_i18n_text('search.clear_search', is_traditional, '清除搜尋'),
            'collapse_search': get_i18n_text('search.collapse_search', is_traditional, '收起搜尋'),
            'show_level': get_i18n_text('level_control.show_level', is_traditional, '顯示層級'),
            'level': get_i18n_text('level_control.level', is_traditional, '層級'),
            'bookmarks': get_i18n_text('navigation.bookmarks', is_traditional, '書籤'),
            'my_bookmarks': get_i18n_text('navigation.my_bookmarks', is_traditional, '我的書籤'),
            'chapter_directory': get_i18n_text('navigation.chapter_directory', is_traditional, '章節目錄'),
            'function_menu': get_i18n_text('ui.function_menu', is_traditional, '功能選單'),
            'settings': get_i18n_text('ui.settings', is_traditional, '設置'),
            'back_to_top': get_i18n_text('ui.back_to_top', is_traditional, '回到頂部'),
        }
    
    def _get_chapter_template(self) -> str:
        """章節頁面模板"""
        return '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{favicon_tag}
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/i18n-text.js"></script>
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div id="top"></div>
<div class="lang-switch">
{lang_switch_links}
</div>
<div class="nav">
<a href="{home_link}">{home_text}</a>
</div>

<div class="top-nav">
{top_nav_links}
</div>

<div class="toc">
<h3>{chapter_toc_title}</h3>
{chapter_toc}
</div>

{content}

<div class="nav-footer">
{prev_link}
{next_link}
</div>
</body>
</html>'''
    
    def _get_index_template(self) -> str:
        """首頁模板"""
        return '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_title}</title>
{favicon_tag}
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
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div class="lang-switch">
{lang_switch_links}
</div>
<h1>{book_title}</h1>

<!-- 搜索激活按钮 -->
<div class="search-activation">
  <button class="search-activate-btn" id="search-activate-btn">
    {activate_search}
  </button>
</div>

<!-- 搜索功能（默认隐藏） -->
<div class="search-container" id="search-container" style="display: none;">
  <div class="search-box">
    <input type="text" id="search-input" placeholder="{search_placeholder}" autocomplete="off">
    <div class="search-status" id="search-status">{search_initializing}</div>
  </div>
  
  <!-- 搜索结果 -->
  <div class="search-results" id="search-results" style="display: none;">
    <div class="search-results-header">
      <span class="search-results-count" id="search-results-count"></span>
      <div class="search-results-actions">
        <button class="search-load-more" id="search-load-more" style="display: none;">{show_more}</button>
        <button class="search-load-all" id="search-load-all" style="display: none;">{show_all}</button>
        <button class="search-clear" id="search-clear">{clear_search}</button>
        <button class="search-collapse" id="search-collapse">{collapse_search}</button>
      </div>
    </div>
    <ul class="search-results-list" id="search-results-list"></ul>
  </div>
</div>

<!-- TOC标题和层级控制的水平布局 -->
<div class="toc-header-container">
  <h2 id="toc-header">{table_of_contents}</h2>
  <div class="toc-level-controls">
    <div class="toc-level-label">{show_level}</div>
    <div class="toc-level-buttons-vertical">
      <button class="toc-level-btn" data-level="1" title="显示第1层">1</button>
      <button class="toc-level-btn active" data-level="2" title="显示前2层">2</button>
      <button class="toc-level-btn" data-level="3" title="显示前3层">3</button>
    </div>
  </div>
</div>

<div class="toc" id="main-toc">
{toc_items}
</div>

<!-- 懸浮操作按钮 -->
<div class="action-buttons">
  <div class="action-menu">
    <button class="action-btn menu-btn" data-action="toggle-menu" title="{function_menu}">☰</button>
    <div class="action-menu-items">
      <button class="action-btn" data-action="toc" title="{bookmarks}">🔖</button>
      <button class="action-btn" data-action="top" title="{back_to_top}">↑</button>
      <button class="action-btn" data-action="settings" title="{settings}">⚙️</button>
    </div>
  </div>
</div>

<!-- 懸浮目錄 -->
<div class="floating-toc" id="floating-toc">
  <div class="floating-toc-header">
    <div class="floating-toc-tabs">
      <button class="floating-toc-tab active" data-tab="toc">📖 {table_of_contents}</button>
      <button class="floating-toc-tab" data-tab="bookmarks">🔖 {bookmarks}</button>
    </div>
    <button class="ctrl-btn" data-action="close-toc">✕</button>
  </div>
  
  <div class="floating-toc-content">
    <h3 id="toc-title">📖 {chapter_directory}</h3>
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
  <div class="floating-level-label">{level}</div>
  <div class="floating-level-buttons">
    <button class="floating-level-btn" data-level="1" title="显示第1层">1</button>
    <button class="floating-level-btn active" data-level="2" title="显示前2层">2</button>
    <button class="floating-level-btn" data-level="3" title="显示前3层">3</button>
  </div>
</div>

</body>
</html>'''
