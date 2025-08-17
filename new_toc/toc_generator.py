#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TOC HTML Generator with Import/Export Functionality
從 toc_full.txt 格式生成可折疊的 HTML 目錄頁面，支持匯入/匯出功能

功能特點：
- 基於羅馬數字和阿拉伯數字解析層次結構（忽略縮排）
- 生成可折疊樹狀目錄
- 支持按層級展開/收起
- 區分羅馬數字結構、阿拉伯數字結構和舊目錄結構
- 包含導出和匯入功能
- 客戶端文件解析和動態目錄重建
"""

import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TocItem:
    """目錄項目數據結構"""
    text: str
    level: int
    is_roman: bool  # 是否為羅馬數字結構
    is_arabic: bool  # 是否為阿拉伯數字結構
    is_old_structure: bool  # 是否為舊結構（包含箭頭的結構）
    children: List['TocItem']
    number_path: str  # 數字路徑，如 "I.II.III" 或 "1.2.3"
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class TocParser:
    """TOC 文件解析器"""
    
    # 羅馬數字映射
    ROMAN_NUMERALS = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15
    }
    
    # 羅馬數字模式：匹配 I., I.I, I.II.III 等
    ROMAN_PATTERN = re.compile(r'^((?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)(?:\.(?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V))*)\.?\s*(.+)$')
    
    # 阿拉伯數字模式：匹配 1., 1.1, 1.2.3 等（可選的結尾點號）
    ARABIC_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$')
    
    # 舊結構模式：包含箭頭的結構
    OLD_STRUCTURE_PATTERN = re.compile(r'.*->.*')
    
    def __init__(self):
        self.items = []
    
    def parse_file(self, file_path: str) -> List[TocItem]:
        """解析 TOC 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        return self.parse_lines(lines)
    
    def parse_lines(self, lines: List[str]) -> List[TocItem]:
        """解析文本行列表"""
        self.items = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            item = self._parse_line(line, line_num)
            if item:
                self.items.append(item)
        
        # 構建層次結構
        return self._build_hierarchy()
    
    def _parse_line(self, line: str, line_num: int) -> Optional[TocItem]:
        """解析單行內容"""
        # 去除前導空格（忽略縮排）
        clean_line = line.lstrip()
        
        # 檢查是否為舊結構（包含箭頭）
        is_old_structure = bool(self.OLD_STRUCTURE_PATTERN.search(clean_line))
        
        # 嘗試匹配羅馬數字模式
        roman_match = self.ROMAN_PATTERN.match(clean_line)
        if roman_match:
            number_path = roman_match.group(1)
            text = roman_match.group(2)
            level = len(number_path.split('.'))
            
            # 確保格式一致性：如果原本沒有點號，添加點號
            formatted_text = f"{number_path}. {text}" if not clean_line.startswith(f"{number_path}.") else clean_line
            
            return TocItem(
                text=formatted_text,
                level=level,
                is_roman=True,
                is_arabic=False,
                is_old_structure=is_old_structure,
                children=[],
                number_path=number_path
            )
        
        # 嘗試匹配阿拉伯數字模式
        arabic_match = self.ARABIC_PATTERN.match(clean_line)
        if arabic_match:
            number_path = arabic_match.group(1)
            text = arabic_match.group(2)
            level = len(number_path.split('.'))
            
            return TocItem(
                text=clean_line,
                level=level,
                is_roman=False,
                is_arabic=True,
                is_old_structure=is_old_structure,
                children=[],
                number_path=number_path
            )
        
        # 非數字結構
        return TocItem(
            text=clean_line,
            level=0,  # 非數字項目暫時設為 0
            is_roman=False,
            is_arabic=False,
            is_old_structure=is_old_structure,
            children=[],
            number_path=""
        )
    
    def _build_hierarchy(self) -> List[TocItem]:
        """構建層次結構"""
        root_items = []
        stack = []  # 用於追蹤當前層次的羅馬數字父項目
        
        for item in self.items:
            if item.is_roman:
                # 只有羅馬數字項目參與層次結構構建
                while stack and stack[-1].level >= item.level:
                    stack.pop()
                
                if stack:
                    stack[-1].children.append(item)
                else:
                    root_items.append(item)
                
                stack.append(item)
            else:
                # 所有非羅馬數字項目（包括阿拉伯數字、舊結構、非數字）都添加到最近的羅馬數字項目下
                if stack:
                    stack[-1].children.append(item)
                else:
                    # 如果沒有羅馬數字父項目，作為根項目（這種情況應該很少見）
                    root_items.append(item)
        
        return root_items


class HtmlGenerator:
    """HTML 生成器"""
    
    def __init__(self):
        self.html_template = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>可折叠目录</title>
<link rel="stylesheet" href="toc-style.css">
</head>
<body>
<h1>可折叠式目录</h1>
<div class="controls">
  <button data-level="1">第 1 层</button>
  <button data-level="2">第 2 层</button>
  <button data-level="3">第 3 层</button>
  <button data-level="4">第 4 层</button>
  <button data-level="5">第 5 层</button>
  <button id="expandAll">🔽</button>
  <button id="collapseAll">🔼</button>
  <button id="toggleNumbers">只显示数字目录</button>
  <button id="importToc">📁 匯入</button>
  <button id="exportToc">📄 匯出</button>
</div>

<!-- 隱藏的文件輸入元素 -->
<input type="file" id="fileInput" accept=".txt" style="display: none;">

<ul id="tree">
{tree_content}
</ul>

<script src="toc-script.js"></script>
</body>
</html>"""
    
    def generate_html(self, items: List[TocItem], output_path: str):
        """生成 HTML 文件"""
        tree_content = self._generate_tree_html(items)
        
        html_content = self.html_template.format(tree_content=tree_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_tree_html(self, items: List[TocItem], indent_level: int = 1) -> str:
        """生成樹狀 HTML 結構"""
        html_parts = []
        
        for item in items:
            # 確定 CSS 類
            css_classes = []
            if item.children:
                css_classes.append('has-children')
            if item.is_old_structure:
                css_classes.append('old-structure')
            if not item.is_roman and not item.is_arabic:
                css_classes.append('non-roman')
            if item.is_arabic:
                css_classes.append('arabic-numeric')
            
            class_attr = f' class="{" ".join(css_classes)}"' if css_classes else ''
            
            # 生成項目 HTML
            if item.children:
                # 有子項目的項目
                children_html = self._generate_tree_html(item.children, indent_level + 1)
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.text)}</span>')
                html_parts.append(f'{"  " * (indent_level + 1)}<ul>')
                html_parts.append(children_html)
                html_parts.append(f'{"  " * (indent_level + 1)}</ul>')
                html_parts.append(f'{"  " * indent_level}</li>')
            else:
                # 葉子項目
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.text)}</span></li>')
        
        return '\n'.join(html_parts)
    
    def _escape_html(self, text: str) -> str:
        """HTML 轉義"""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='從 toc_full.txt 生成可折疊的 HTML 目錄（支持匯入/匯出）')
    parser.add_argument('input_file', help='輸入的 toc_full.txt 文件路徑')
    parser.add_argument('-o', '--output', default='output', help='輸出目錄（默認：output）')
    parser.add_argument('--html-name', default='toc.html', help='HTML 文件名（默認：toc.html）')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    os.makedirs(args.output, exist_ok=True)
    
    # 解析 TOC 文件
    print(f"正在解析 {args.input_file}...")
    parser = TocParser()
    items = parser.parse_file(args.input_file)
    
    print(f"解析完成，共找到 {len(items)} 個根項目")
    
    # 生成 HTML
    html_path = os.path.join(args.output, args.html_name)
    print(f"正在生成 HTML 文件：{html_path}")
    generator = HtmlGenerator()
    generator.generate_html(items, html_path)
    
    print(f"生成完成！文件保存在：{args.output}/")
    print(f"- {args.html_name}")
    print("\n新功能：")
    print("- 📁 匯入：點擊匯入按鈕可載入新的 toc_full.txt 文件")
    print("- 📄 匯出：匯出當前展開狀態的目錄結構")
    print("- 🔢 支持阿拉伯數字和羅馬數字的層次解析")
    print("- 🎯 '只显示数字目录' 按鈕可隱藏非數字結構項目")


if __name__ == '__main__':
    main()
