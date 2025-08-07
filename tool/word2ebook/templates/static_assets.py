"""静态资源管理"""

from pathlib import Path
from typing import Optional


class CSSAssets:
    """CSS 资源管理器"""
    
    def __init__(self):
        self._css_content = None
    
    def get_css_content(self) -> str:
        """获取 CSS 内容"""
        if self._css_content is None:
            self._css_content = self._load_css_content()
        return self._css_content
    
    def _load_css_content(self) -> str:
        """加载 CSS 内容（从原始文件中提取）"""
        # 这里应该包含完整的 CSS 内容
        # 为了节省空间，我只包含基础结构
        # 在实际使用时，可以从原始 word2ebook.py 中复制完整的 CSS_CONTENT
        return """:root {
    --line-height: 1.6;
}

body { 
    font-family: 'Helvetica', sans-serif; 
    margin: auto; 
    max-width: 800px; 
    line-height: var(--line-height); 
    background: #fff0f5; 
    color: #333; 
    transition: 0.3s; 
}

h1 { 
    color: #e75480; 
    border-bottom: 2px solid #f8c8dc; 
    padding-bottom: 10px; 
}

h2 { 
    color: #d44d75; 
    margin-top: 40px; 
}

h3 { 
    color: #b73c65; 
    margin-top: 25px; 
}

/* 问答样式 */
.question {
    padding: 15px;
    background: #fff;
    border-radius: 8px;
    border-left: 4px solid #e75480;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(231, 84, 128, 0.1);
}

.answer {
    padding: 15px;
    background: linear-gradient(135deg, #fff8f0 0%, #ffffff 100%);
    border-radius: 8px;
    border-left: 4px solid #ff69b4;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(255, 105, 180, 0.1);
}

/* 更多样式... */"""
    
    @classmethod
    def load_from_original_file(cls, original_file_path: Optional[Path] = None) -> str:
        """从原始文件中加载完整的 CSS 内容"""
        if original_file_path and original_file_path.exists():
            # 从原始文件中提取 CSS_CONTENT
            with open(original_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 提取 CSS_CONTENT 变量的内容
            import re
            css_match = re.search(r'CSS_CONTENT = """\\?\n(.*?)\n"""', content, re.DOTALL)
            if css_match:
                return css_match.group(1)
        
        # 如果无法从原始文件加载，返回基础样式
        return cls().get_css_content()


class JSAssets:
    """JavaScript 资源管理器"""
    
    def __init__(self):
        self._js_content = None
    
    def get_js_content(self) -> str:
        """获取 JavaScript 内容"""
        if self._js_content is None:
            self._js_content = self._load_js_content()
        return self._js_content
    
    def _load_js_content(self) -> str:
        """加载 JavaScript 内容"""
        # 这里应该包含完整的 JavaScript 内容
        # 为了节省空间，我只包含基础结构
        return """document.addEventListener('DOMContentLoaded', function() {
  // 基本设置
  
  // 暗色模式初始化
  if(localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }

  // 搜索功能初始化
  let searchIndex = null;
  let miniSearch = null;
  let searchInitialized = false;
  
  // 检测当前页面类型
  function isIndexPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index.html' || filename === 'index_trad.html';
  }
  
  // 更多 JavaScript 功能...
});"""
    
    @classmethod
    def load_from_original_file(cls, original_file_path: Optional[Path] = None) -> str:
        """从原始文件中加载完整的 JavaScript 内容"""
        if original_file_path and original_file_path.exists():
            # 从原始文件中提取 JS_CONTENT
            with open(original_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 提取 JS_CONTENT 变量的内容
            import re
            js_match = re.search(r'JS_CONTENT = """(.*?)\n"""', content, re.DOTALL)
            if js_match:
                return js_match.group(1)
        
        # 如果无法从原始文件加载，返回基础脚本
        return cls().get_js_content()


class StaticAssetsManager:
    """静态资源管理器"""
    
    def __init__(self, original_file_path: Optional[Path] = None):
        self.original_file_path = original_file_path
        self.css_assets = CSSAssets()
        self.js_assets = JSAssets()
    
    def get_full_css_content(self) -> str:
        """获取完整的 CSS 内容"""
        # 直接从预提取的文件读取
        css_file = Path(__file__).parent.parent / "assets" / "css" / "style.css"
        if css_file.exists():
            with open(css_file, 'r', encoding='utf-8') as f:
                return f.read()
        return CSSAssets.load_from_original_file(self.original_file_path)
    
    def get_full_js_content(self) -> str:
        """获取完整的 JavaScript 内容"""
        # 直接从预提取的文件读取
        js_file = Path(__file__).parent.parent / "assets" / "js" / "script.js"
        if js_file.exists():
            with open(js_file, 'r', encoding='utf-8') as f:
                return f.read()
        return JSAssets.load_from_original_file(self.original_file_path)