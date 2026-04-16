"""静态资源管理"""

from pathlib import Path
from typing import Optional


# Base directory for all source assets (sibling of this package)
_ASSETS_BASE = Path(__file__).parent.parent / "assets"

JS_WRAPPER_OPEN = "document.addEventListener('DOMContentLoaded', function() {\n"
JS_WRAPPER_CLOSE = "});\n"


class CSSAssets:
    """CSS 资源管理器（提供基础回退内容）"""

    def __init__(self):
        self._css_content: Optional[str] = None

    def get_css_content(self) -> str:
        if self._css_content is None:
            self._css_content = self._load_css_content()
        return self._css_content

    def _load_css_content(self) -> str:
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

h1 { color: #e75480; border-bottom: 2px solid #f8c8dc; padding-bottom: 10px; }
h2 { color: #e75480; margin-top: 40px; }
h3 { color: #e85aad; margin-top: 25px; }

.question {
    padding: 15px;
    background: #fff;
    border-radius: 8px;
    border-left: 4px solid #e75480;
    margin-bottom: 15px;
}

.answer {
    padding: 15px;
    background: linear-gradient(135deg, #fff8f0 0%, #ffffff 100%);
    border-radius: 8px;
    border-left: 4px solid #ff69b4;
    margin-bottom: 15px;
}"""

    @classmethod
    def load_from_original_file(cls, original_file_path: Optional[Path] = None) -> str:
        if original_file_path and original_file_path.exists():
            import re
            with open(original_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            css_match = re.search(r'CSS_CONTENT = """\\?\n(.*?)\n"""', content, re.DOTALL)
            if css_match:
                return css_match.group(1)
        return cls().get_css_content()


class JSAssets:
    """JavaScript 资源管理器（提供基础回退内容）"""

    def __init__(self):
        self._js_content: Optional[str] = None

    def get_js_content(self) -> str:
        if self._js_content is None:
            self._js_content = self._load_js_content()
        return self._js_content

    def _load_js_content(self) -> str:
        return """document.addEventListener('DOMContentLoaded', function() {
  if(localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }
});"""

    @classmethod
    def load_from_original_file(cls, original_file_path: Optional[Path] = None) -> str:
        if original_file_path and original_file_path.exists():
            import re
            with open(original_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            js_match = re.search(r'JS_CONTENT = """(.*?)\n"""', content, re.DOTALL)
            if js_match:
                return js_match.group(1)
        return cls().get_js_content()


class StaticAssetsManager:
    """静态资源管理器

    Loading priority for CSS:
      1. assets/css/modules/*.css  (sorted, concatenated)
      2. assets/css/style.css      (monolithic fallback)
      3. CSSAssets inline stub     (last resort)

    Loading priority for JS:
      1. assets/js/modules/*.js    (sorted, concatenated, wrapped in DOMContentLoaded)
      2. assets/js/script.js       (monolithic fallback)
      3. JSAssets inline stub      (last resort)
    """

    def __init__(self, original_file_path: Optional[Path] = None):
        self.original_file_path = original_file_path
        self.css_assets = CSSAssets()
        self.js_assets = JSAssets()
        # Allow tests to override the assets base directory
        self._assets_base: Path = _ASSETS_BASE

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def get_full_css_content(self) -> str:
        modules_dir = self._assets_base / "css" / "modules"
        if modules_dir.exists():
            return self._concat_files(modules_dir, "*.css")

        single_file = self._assets_base / "css" / "style.css"
        if single_file.exists():
            return single_file.read_text(encoding="utf-8")

        return CSSAssets.load_from_original_file(self.original_file_path)

    # ------------------------------------------------------------------
    # JavaScript
    # ------------------------------------------------------------------

    def get_full_js_content(self) -> str:
        modules_dir = self._assets_base / "js" / "modules"
        if modules_dir.exists():
            inner = self._concat_files(modules_dir, "*.js")
            return JS_WRAPPER_OPEN + inner + JS_WRAPPER_CLOSE

        single_file = self._assets_base / "js" / "script.js"
        if single_file.exists():
            return single_file.read_text(encoding="utf-8")

        return JSAssets.load_from_original_file(self.original_file_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _concat_files(directory: Path, pattern: str) -> str:
        """Sort and concatenate all files matching *pattern* in *directory*."""
        files = sorted(directory.glob(pattern))
        return "".join(f.read_text(encoding="utf-8") for f in files)
