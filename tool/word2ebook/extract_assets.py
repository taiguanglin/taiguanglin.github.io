#!/usr/bin/env python3
"""
从原始 word2ebook.py 文件中提取 CSS 和 JavaScript 内容
"""

import re
from pathlib import Path

def extract_assets_from_original():
    """从原始文件中提取 CSS 和 JS 内容"""
    original_file = Path(__file__).parent.parent / "word2ebook.py"
    
    if not original_file.exists():
        print(f"错误：找不到原始文件 {original_file}")
        return
    
    with open(original_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 CSS 内容
    css_match = re.search(r'CSS_CONTENT = """\\?\n(.*?)\n"""', content, re.DOTALL)
    if css_match:
        css_content = css_match.group(1)
        
        # 写入 CSS 文件
        css_file = Path(__file__).parent / "assets" / "css" / "style.css"
        css_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content)
        print(f"✅ CSS 内容已提取到：{css_file}")
    else:
        print("❌ 未找到 CSS_CONTENT")
    
    # 提取 JS 内容
    js_match = re.search(r'JS_CONTENT = """(.*?)\n"""', content, re.DOTALL)
    if js_match:
        js_content = js_match.group(1)
        
        # 写入 JS 文件
        js_file = Path(__file__).parent / "assets" / "js" / "script.js"
        js_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write(js_content)
        print(f"✅ JavaScript 内容已提取到：{js_file}")
    else:
        print("❌ 未找到 JS_CONTENT")

if __name__ == "__main__":
    extract_assets_from_original()