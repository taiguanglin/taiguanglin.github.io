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
            # #region agent log
            import json as _json, time as _time
            _log_path = "/Users/paul/tai/taiguanglin.github.io/.cursor/debug-1e1df3.log"
            _css_files = sorted(modules_dir.glob("*.css"))
            _css_names = [f.name for f in _css_files]
            _css_sizes = {f.name: len(f.read_text(encoding="utf-8")) for f in _css_files}
            with open(_log_path, "a") as _lf:
                _lf.write(_json.dumps({"sessionId":"1e1df3","hypothesisId":"H-B,H-D","location":"static_assets.py:get_full_css_content","message":"CSS modules found","data":{"files":_css_names,"sizes":_css_sizes,"total_files":len(_css_files)},"timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion
            _result = self._concat_files(modules_dir, "*.css")
            # #region agent log
            _root_block = _result[:_result.find("}")+1] if "}" in _result else _result[:500]
            _has_self_ref = "var(--color-primary)" in _root_block and "--color-primary:" in _root_block
            with open(_log_path, "a") as _lf:
                _lf.write(_json.dumps({"sessionId":"1e1df3","hypothesisId":"H-A","location":"static_assets.py:get_full_css_content","message":"CSS root block check","data":{"root_block_first200":_root_block[:200],"has_self_ref":_has_self_ref,"total_css_len":len(_result)},"timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion
            return _result

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
            # #region agent log
            import json as _json, time as _time
            _log_path = "/Users/paul/tai/taiguanglin.github.io/.cursor/debug-1e1df3.log"
            _js_files = sorted(modules_dir.glob("*.js"))
            _js_names = [f.name for f in _js_files]
            _js_sizes = {f.name: len(f.read_text(encoding="utf-8")) for f in _js_files}
            with open(_log_path, "a") as _lf:
                _lf.write(_json.dumps({"sessionId":"1e1df3","hypothesisId":"H-C","location":"static_assets.py:get_full_js_content","message":"JS modules found","data":{"files":_js_names,"sizes":_js_sizes,"total_files":len(_js_files)},"timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion
            inner = self._concat_files(modules_dir, "*.js")
            # #region agent log
            _key_fns = ["initSearch","performSearch","getBookmarks","toggleBookmark","renderBookmarks","applyReadingSettings","isIndexPage","isTraditionalChinesePage"]
            _missing = [fn for fn in _key_fns if f"function {fn}" not in inner]
            with open(_log_path, "a") as _lf:
                _lf.write(_json.dumps({"sessionId":"1e1df3","hypothesisId":"H-C","location":"static_assets.py:get_full_js_content","message":"JS key function check","data":{"missing_functions":_missing,"total_js_len":len(inner)},"timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion
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
