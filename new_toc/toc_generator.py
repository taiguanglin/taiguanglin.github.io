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


class SimplifiedChineseConverter:
    """簡繁轉換器"""
    
    def __init__(self):
        self._opencc_t2s = None
    
    @property
    def opencc_t2s(self):
        """懒加载 OpenCC 繁体转简体"""
        if self._opencc_t2s is None:
            try:
                import opencc
                self._opencc_t2s = opencc.OpenCC('t2s')  # 繁体转简体
            except ImportError:
                print("警告: OpenCC 未安装，无法进行简繁转换")
                self._opencc_t2s = None
        return self._opencc_t2s
    
    def to_simplified(self, text: str) -> str:
        """转换为简体中文"""
        if not text or not self.opencc_t2s:
            return text
        
        try:
            return self.opencc_t2s.convert(text)
        except Exception as e:
            print(f"警告: 转换文本时发生错误: {e}")
            return text


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
    original_count: Optional[int] = None  # 原始计数（从文本中提取）
    calculated_count: Optional[int] = None  # 计算得出的计数
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    @property
    def is_leaf(self) -> bool:
        """判断是否为末端节点（叶子节点）"""
        return len(self.children) == 0
    
    @property
    def display_count(self) -> Optional[int]:
        """获取用于显示的计数值"""
        if self.is_leaf:
            # 末端节点使用原始计数
            return self.original_count
        else:
            # 非末端节点使用计算得出的计数
            return self.calculated_count
    
    @property
    def text_without_count(self) -> str:
        """获取去除计数的文本内容"""
        # 移除文本中的 (数字) 格式，可能后面还有其他符号
        count_pattern = r'\s*\(\d+\)'
        return re.sub(count_pattern, '', self.text).strip()
    
    @property
    def display_text(self) -> str:
        """获取用于显示的文本（包含重新计算的计数）"""
        base_text = self.text_without_count
        count = self.display_count
        
        if self.is_leaf:
            # 末端节点：只有当原始计数存在且大于0时才显示
            if count is not None and count > 0:
                return f"{base_text} ({count})"
        else:
            # 非末端节点：显示计算出的计数，包括0
            if count is not None:
                return f"{base_text} ({count})"
        
        return base_text


class TocParser:
    """TOC 文件解析器"""
    
    # 罗马数字映射
    ROMAN_NUMERALS = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15
    }
    
    # 罗马数字模式：匹配 I., I.I, I.II.III 等
    # 注意：需要按长度从长到短排列，避免部分匹配（如XIV被匹配成XI）
    ROMAN_PATTERN = re.compile(r'^((?:XIII|XIV|XII|XV|VIII|VII|VI|IX|IV|III|II|XI|X|V|I)(?:\.(?:XIII|XIV|XII|XV|VIII|VII|VI|IX|IV|III|II|XI|X|V|I))*)\.?\s*(.+)$')
    
    # 阿拉伯数字模式：匹配 1., 1.1, 1.2.3 等（可选的结尾点号）
    ARABIC_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$')
    
    # 旧结构模式：包含箭头的结构
    OLD_STRUCTURE_PATTERN = re.compile(r'.*->.*')
    
    def __init__(self, convert_to_simplified: bool = True):
        """初始化解析器
        
        Args:
            convert_to_simplified: 是否将所有内容转换为简体中文
        """
        self.items: List[TocItem] = []
        self.convert_to_simplified = convert_to_simplified
        self.converter = SimplifiedChineseConverter() if convert_to_simplified else None
    
    def _extract_count_from_text(self, text: str) -> Optional[int]:
        """从文本中提取括号内的数字"""
        # 匹配 (数字)，可能后面有空格、📋或其他符号
        count_pattern = r'\((\d+)\)'
        match = re.search(count_pattern, text)
        if match:
            return int(match.group(1))
        return None
    
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
        hierarchy = self._build_hierarchy()
        
        # 计算各项目的计数
        self._calculate_counts(hierarchy)
        
        return hierarchy
    
    def _parse_line(self, line: str, line_num: int) -> Optional[TocItem]:
        """解析单行内容"""
        # 去除前导空格（忽略缩排）
        clean_line = line.lstrip()
        
        # 提取原始计数
        original_count = self._extract_count_from_text(clean_line)
        
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
            
            # 转换为简体中文（如果启用）
            if self.convert_to_simplified and self.converter:
                formatted_text = self.converter.to_simplified(formatted_text)
            
            return TocItem(
                text=formatted_text,
                level=level,
                is_roman=True,
                is_arabic=False,
                is_old_structure=is_old_structure,
                children=[],
                number_path=number_path,
                original_count=original_count
            )
        
        # 尝试匹配阿拉伯数字模式
        arabic_match = self.ARABIC_PATTERN.match(clean_line)
        if arabic_match:
            number_path = arabic_match.group(1)
            text = arabic_match.group(2)
            level = len(number_path.split('.'))
            
            # 转换为简体中文（如果启用）
            converted_text = clean_line
            if self.convert_to_simplified and self.converter:
                converted_text = self.converter.to_simplified(clean_line)
            
            return TocItem(
                text=converted_text,
                level=level,
                is_roman=False,
                is_arabic=True,
                is_old_structure=is_old_structure,
                children=[],
                number_path=number_path,
                original_count=original_count
            )
        
        # 非数字结构
        # 转换为简体中文（如果启用）
        converted_text = clean_line
        if self.convert_to_simplified and self.converter:
            converted_text = self.converter.to_simplified(clean_line)
        
        return TocItem(
            text=converted_text,
            level=0,  # 非数字项目暂时设为 0
            is_roman=False,
            is_arabic=False,
            is_old_structure=is_old_structure,
            children=[],
            number_path="",
            original_count=original_count
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
    
    def _calculate_counts(self, items: List[TocItem]) -> None:
        """计算所有项目的计数（自底向上）"""
        for item in items:
            self._calculate_item_count(item)
    
    def _calculate_item_count(self, item: TocItem) -> int:
        """递归计算单个项目的计数"""
        if item.is_leaf:
            # 末端节点使用原始计数
            if item.original_count is not None:
                return item.original_count
            else:
                # 如果没有原始计数，默认为0
                return 0
        else:
            # 非末端节点：先递归计算所有子项目，然后求和
            total_count = 0
            for child in item.children:
                child_count = self._calculate_item_count(child)
                total_count += child_count
            
            # 设置计算得出的计数
            item.calculated_count = total_count
            return total_count


class HtmlGenerator:
    """HTML 生成器"""
    
    def __init__(self, use_simplified: bool = True):
        """初始化HTML生成器
        
        Args:
            use_simplified: 是否使用简体中文界面
        """
        self.use_simplified = use_simplified
        self.converter = SimplifiedChineseConverter() if use_simplified else None
    
    def _get_ui_text(self, key: str) -> str:
        """获取界面文字"""
        texts = {
            'lang': 'zh-Hans' if self.use_simplified else 'zh-Hant',
            'level_1': '第 1 层' if self.use_simplified else '第 1 層',
            'level_2': '第 2 层' if self.use_simplified else '第 2 層',
            'level_3': '第 3 层' if self.use_simplified else '第 3 層',
            'level_4': '第 4 层' if self.use_simplified else '第 4 層',
            'level_5': '第 5 层' if self.use_simplified else '第 5 層',
            'toggle_old': '切换旧目录显示' if self.use_simplified else '切換舊目錄顯示',
            'import': '📁 汇入' if self.use_simplified else '📁 匯入',
            'export': '📄 汇出' if self.use_simplified else '📄 匯出'
        }
        return texts.get(key, key)
    
    def _generate_html_template(self) -> str:
        """生成HTML模板"""
        return f"""<!doctype html>
<html lang="{self._get_ui_text('lang')}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{{page_title}}</title>
<link rel="stylesheet" href="toc-style.css">
</head>
<body>
<h1>{{header_title}}</h1>
<div class="controls">
  <button data-level="1">{self._get_ui_text('level_1')}</button>
  <button data-level="2">{self._get_ui_text('level_2')}</button>
  <button data-level="3">{self._get_ui_text('level_3')}</button>
  <button data-level="4">{self._get_ui_text('level_4')}</button>
  <button data-level="5">{self._get_ui_text('level_5')}</button>
  <button id="expandAll">🔽</button>
  <button id="collapseAll">🔼</button>
  <button id="toggleNumbers">{self._get_ui_text('toggle_old')}</button>
  <button id="importToc">{self._get_ui_text('import')}</button>
  <button id="exportToc">{self._get_ui_text('export')}</button>
</div>

<!-- 隐藏的文件输入元素 -->
<input type="file" id="fileInput" accept=".txt" style="display: none;">

<ul id="tree">
{{tree_content}}
</ul>

<!-- 浮动控制栏 -->
<div id="floatingControls" class="floating-controls">
  <div class="floating-controls-content">
    <button data-level="1" class="level-btn">{self._get_ui_text('level_1')}</button>
    <button data-level="2" class="level-btn">{self._get_ui_text('level_2')}</button>
    <button data-level="3" class="level-btn">{self._get_ui_text('level_3')}</button>
    <button data-level="4" class="level-btn">{self._get_ui_text('level_4')}</button>
    <button data-level="5" class="level-btn">{self._get_ui_text('level_5')}</button>
    <button id="floatingExpandAll" class="action-btn">🔽</button>
    <button id="floatingCollapseAll" class="action-btn">🔼</button>
    <button id="floatingToggleNumbers" class="action-btn">隐藏原始目录</button>
  </div>
</div>

<script src="toc-script.js"></script>
</body>
</html>"""
    
    def generate_html(self, items: List[TocItem], output_path: str, input_filename: str = ""):
        """生成 HTML 文件"""
        tree_content = self._generate_tree_html(items)
        
        # 生成页面标题：使用输入文件名（去除扩展名）
        if input_filename:
            # 去除路径和扩展名，只保留文件名
            import os
            base_name = os.path.splitext(os.path.basename(input_filename))[0]
            page_title = f"{base_name} - {'可折叠目录' if self.use_simplified else '可摺疊目錄'}"
            header_title = base_name
        else:
            page_title = "可折叠目录" if self.use_simplified else "可摺疊目錄"
            header_title = "可折叠式目录" if self.use_simplified else "可摺疊式目錄"
        
        # 转换标题为简体（如果启用且有转换器）
        if self.use_simplified and self.converter:
            header_title = self.converter.to_simplified(header_title)
        
        # 生成HTML模板并填充内容
        html_template = self._generate_html_template()
        html_content = html_template.format(
            tree_content=tree_content,
            page_title=page_title,
            header_title=header_title
        )
        
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
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.display_text)}</span>')
                html_parts.append(f'{"  " * (indent_level + 1)}<ul>')
                html_parts.append(children_html)
                html_parts.append(f'{"  " * (indent_level + 1)}</ul>')
                html_parts.append(f'{"  " * indent_level}</li>')
            else:
                # 叶子项目
                html_parts.append(f'{"  " * indent_level}<li{class_attr}><span class="label">{self._escape_html(item.display_text)}</span></li>')
        
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
    parser.add_argument('input_file', help='输入的 toc_full.txt 文件路径（必须提供）')
    parser.add_argument('-o', '--output', default='.', help='输出目录（默认：当前目录）')
    parser.add_argument('--html-name', default='index.html', help='HTML 文件名（默认：index.html）')
    parser.add_argument('--simplified', action='store_true', default=True, help='转换所有内容为简体中文（默认：启用）')
    parser.add_argument('--no-simplified', dest='simplified', action='store_false', help='不转换内容，保持原始语言')
    
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
    print(f"简体转换: {'启用' if args.simplified else '禁用'}")
    toc_parser = TocParser(convert_to_simplified=args.simplified)
    items = toc_parser.parse_file(args.input_file)
    
    print(f"解析完成，共找到 {len(items)} 个根项目")
    
    # 生成 HTML
    html_path = os.path.join(args.output, args.html_name)
    
    # 如果文件已存在，给出提示
    if os.path.exists(html_path):
        print(f"⚠️  文件 {html_path} 已存在，将被覆盖")
    
    print(f"正在生成 HTML 文件：{html_path}")
    generator = HtmlGenerator(use_simplified=args.simplified)
    generator.generate_html(items, html_path, args.input_file)
    
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
    print("- 指定文件：python toc_generator.py toc_full.txt")
    print("- 指定其他文件：python toc_generator.py my_toc.txt")
    print("- 指定输出目录：python toc_generator.py toc_full.txt -o output_dir")
    print("- 指定HTML文件名：python toc_generator.py toc_full.txt --html-name custom.html")


if __name__ == '__main__':
    main()
