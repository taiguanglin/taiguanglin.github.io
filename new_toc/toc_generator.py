#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TOC HTML Generator with Import/Export Functionality
从 toc_full.txt 格式生成可折叠的 HTML 目录页面，支持汇入/汇出功能

功能特点：
- 基于罗马数字和阿拉伯数字解析层次结构（忽略缩排）
- 生成可折叠树状目录
- 支持按层级展开/收起
- 区分罗马数字结构、阿拉伯数字结构和旧目录结构
- 包含导出和汇入功能
- 客户端文件解析和动态目录重建
"""

import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TocItem:
    """目录项目数据结构"""
    text: str
    level: int
    is_roman: bool  # 是否为罗马数字结构
    is_arabic: bool  # 是否为阿拉伯数字结构
    is_old_structure: bool  # 是否为旧结构（包含箭头的结构）
    children: List['TocItem']
    number_path: str  # 数字路径，如 "I.II.III" 或 "1.2.3"
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class TocParser:
    """TOC 文件解析器"""
    
    # 罗马数字映射
    ROMAN_NUMERALS = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15
    }
    
    # 罗马数字模式：匹配 I., I.I, I.II.III 等
    ROMAN_PATTERN = re.compile(r'^((?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)(?:\.(?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V))*)\.?\s*(.+)$')
    
    # 阿拉伯数字模式：匹配 1., 1.1, 1.2.3 等（可选的结尾点号）
    ARABIC_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$')
    
    # 旧结构模式：包含箭头的结构
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
        
        # 构建层次结构
        return self._build_hierarchy()
    
    def _parse_line(self, line: str, line_num: int) -> Optional[TocItem]:
        """解析单行内容"""
        # 去除前导空格（忽略缩排）
        clean_line = line.lstrip()
        
        # 检查是否为旧结构（包含箭头）
        is_old_structure = bool(self.OLD_STRUCTURE_PATTERN.search(clean_line))
        
        # 尝试匹配罗马数字模式
        roman_match = self.ROMAN_PATTERN.match(clean_line)
        if roman_match:
            number_path = roman_match.group(1)
            text = roman_match.group(2)
            level = len(number_path.split('.'))
            
            # 确保格式一致性：如果原本没有点号，添加点号
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
        
        # 尝试匹配阿拉伯数字模式
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
        
        # 非数字结构
        return TocItem(
            text=clean_line,
            level=0,  # 非数字项目暂时设为 0
            is_roman=False,
            is_arabic=False,
            is_old_structure=is_old_structure,
            children=[],
            number_path=""
        )
    
    def _build_hierarchy(self) -> List[TocItem]:
        """构建层次结构"""
        root_items = []
        stack = []  # 用于追踪当前层次的罗马数字父项目
        
        for item in self.items:
            if item.is_roman:
                # 只有罗马数字项目参与层次结构构建
                while stack and stack[-1].level >= item.level:
                    stack.pop()
                
                if stack:
                    stack[-1].children.append(item)
                else:
                    root_items.append(item)
                
                stack.append(item)
            else:
                # 所有非罗马数字项目（包括阿拉伯数字、旧结构、非数字）都添加到最近的罗马数字项目下
                if stack:
                    stack[-1].children.append(item)
                else:
                    # 如果没有罗马数字父项目，作为根项目（这种情况应该很少见）
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
  <button id="toggleNumbers">切换旧目录显示</button>
  <button id="importToc">📁 汇入</button>
  <button id="exportToc">📄 汇出</button>
</div>

<!-- 隐藏的文件输入元素 -->
<input type="file" id="fileInput" accept=".txt" style="display: none;">

<ul id="tree">
{tree_content}
</ul>

<!-- 浮动控制栏 -->
<div id="floatingControls" class="floating-controls">
  <div class="floating-controls-content">
    <button data-level="1" class="level-btn">第 1 层</button>
    <button data-level="2" class="level-btn">第 2 层</button>
    <button data-level="3" class="level-btn">第 3 层</button>
    <button data-level="4" class="level-btn">第 4 层</button>
    <button data-level="5" class="level-btn">第 5 层</button>
    <button id="floatingExpandAll" class="action-btn">🔽</button>
    <button id="floatingCollapseAll" class="action-btn">🔼</button>
    <button id="floatingToggleNumbers" class="action-btn">切换旧目录显示</button>
  </div>
</div>

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
        """生成树状 HTML 结构"""
        html_parts = []
        
        for item in items:
            # 确定 CSS 类
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
            
            # 生成项目 HTML
            if item.children:
                # 有子项目的项目
                children_html = self._generate_tree_html(item.children, indent_level + 1)
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.text)}</span>')
                html_parts.append(f'{"  " * (indent_level + 1)}<ul>')
                html_parts.append(children_html)
                html_parts.append(f'{"  " * (indent_level + 1)}</ul>')
                html_parts.append(f'{"  " * indent_level}</li>')
            else:
                # 叶子项目
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.text)}</span></li>')
        
        return '\n'.join(html_parts)
    
    def _escape_html(self, text: str) -> str:
        """HTML 转义"""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='从 toc_full.txt 生成可折叠的 HTML 目录（支持汇入/汇出）')
    parser.add_argument('input_file', nargs='?', default='toc_full.txt', help='输入的 toc_full.txt 文件路径（默认：toc_full.txt）')
    parser.add_argument('-o', '--output', default='.', help='输出目录（默认：当前目录）')
    parser.add_argument('--html-name', default='index.html', help='HTML 文件名（默认：index.html）')
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not os.path.exists(args.input_file):
        print(f"❌ 错误：找不到输入文件 {args.input_file}")
        print("请确保 toc_full.txt 文件存在于当前目录中")
        return 1
    
    # 确保输出目录存在
    if args.output != '.':
        os.makedirs(args.output, exist_ok=True)
    
    # 解析 TOC 文件
    print(f"正在解析 {args.input_file}...")
    toc_parser = TocParser()
    items = toc_parser.parse_file(args.input_file)
    
    print(f"解析完成，共找到 {len(items)} 个根项目")
    
    # 生成 HTML
    html_path = os.path.join(args.output, args.html_name)
    
    # 如果文件已存在，给出提示
    if os.path.exists(html_path):
        print(f"⚠️  文件 {html_path} 已存在，将被覆盖")
    
    print(f"正在生成 HTML 文件：{html_path}")
    generator = HtmlGenerator()
    generator.generate_html(items, html_path)
    
    # 显示结果
    if args.output == '.':
        print(f"✅ 生成完成！文件已保存：{args.html_name}")
    else:
        print(f"✅ 生成完成！文件保存在：{args.output}/")
        print(f"- {args.html_name}")
    print("\n✨ 完整编辑功能：")
    print("- 📁 汇入：点击汇入按钮可载入新的 toc_full.txt 文件")
    print("- 📄 汇出：汇出完整的目录结构为 toc_full_edited.txt")
    print("- ✏️ 编辑模式：可新增、删除、修改、拖拉移动节点")
    print("- 🎯 精确插入：支持插入到前面、后面或作为子项目")
    print("- 🔢 支持阿拉伯数字和罗马数字的层次解析")
    print("- 🎨 目录显示切换：可在新旧目录间切换显示")
    print("- 🔄 罗马数字自动重新编号")
    print("- 👆 双击编辑、多选支持、视觉反馈")
    print("\n💡 使用方式：")
    print("- 直接运行：python toc_generator.py")
    print("- 指定文件：python toc_generator.py my_toc.txt")
    print("- 指定输出：python toc_generator.py -o output_dir")


if __name__ == '__main__':
    main()
