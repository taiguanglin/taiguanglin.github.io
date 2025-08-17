#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新計算 toc_full.txt 文件中的括號數字
父節點的數字 = 所有子節點數字的總和
葉子節點的數字保持不變
"""

import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class TocNode:
    """目錄節點數據結構"""
    text: str
    level: int
    is_roman: bool
    number_path: str
    original_number: int  # 原始數字（括號內）
    calculated_number: int  # 計算後的數字
    children: List['TocNode']
    line_number: int
    raw_line: str  # 保存原始行內容
    
    def __post_init__(self):
        if self.children is None:
            self.children = []

class TocNumberCalculator:
    """TOC 數字重新計算器"""
    
    # 羅馬數字模式
    ROMAN_PATTERN = re.compile(r'^((?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)(?:\.(?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V))*)\.?\s*(.+)$')
    
    # 阿拉伯數字模式
    ARABIC_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$')
    
    # 提取括號內數字的模式
    NUMBER_PATTERN = re.compile(r'\((\d+)\)$')
    
    def __init__(self):
        self.nodes = []
        self.line_count = 0
    
    def parse_file(self, file_path: str) -> List[TocNode]:
        """解析 TOC 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        return self.parse_lines(lines)
    
    def parse_lines(self, lines: List[str]) -> List[TocNode]:
        """解析文本行列表"""
        self.nodes = []
        self.line_count = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            node = self._parse_line(line, line_num)
            if node:
                self.nodes.append(node)
                self.line_count += 1
        
        # 構建層次結構
        root_nodes = self._build_hierarchy()
        
        # 計算數字
        self._calculate_numbers(root_nodes)
        
        return root_nodes
    
    def _parse_line(self, line: str, line_num: int) -> Optional[TocNode]:
        """解析單行內容"""
        clean_line = line.lstrip()
        
        # 提取原始數字（括號內）
        original_number = 0
        number_match = self.NUMBER_PATTERN.search(clean_line)
        if number_match:
            original_number = int(number_match.group(1))
        
        # 檢查是否為羅馬數字模式
        roman_match = self.ROMAN_PATTERN.match(clean_line)
        if roman_match:
            number_path = roman_match.group(1)
            text = roman_match.group(2)
            level = len(number_path.split('.'))
            
            return TocNode(
                text=clean_line,
                level=level,
                is_roman=True,
                number_path=number_path,
                original_number=original_number,
                calculated_number=0,
                children=[],
                line_number=line_num,
                raw_line=line
            )
        
        # 檢查是否為阿拉伯數字模式
        arabic_match = self.ARABIC_PATTERN.match(clean_line)
        if arabic_match:
            number_path = arabic_match.group(1)
            text = arabic_match.group(2)
            level = len(number_path.split('.')) + 10  # 阿拉伯數字層級偏移
            
            return TocNode(
                text=clean_line,
                level=level,
                is_roman=False,
                number_path=number_path,
                original_number=original_number,
                calculated_number=0,
                children=[],
                line_number=line_num,
                raw_line=line
            )
        
        # 非數字結構，可能是葉子節點
        return TocNode(
            text=clean_line,
            level=999,  # 最高層級，作為葉子節點
            is_roman=False,
            number_path="",
            original_number=original_number,
            calculated_number=original_number,  # 葉子節點保持原數字
            children=[],
            line_number=line_num,
            raw_line=line
        )
    
    def _build_hierarchy(self) -> List[TocNode]:
        """構建層次結構"""
        root_nodes = []
        stack = []  # 用於追蹤當前層次的父項目
        
        for node in self.nodes:
            if node.is_roman:
                # 羅馬數字項目參與層次結構構建
                while stack and stack[-1].level >= node.level:
                    stack.pop()
                
                if stack:
                    stack[-1].children.append(node)
                else:
                    root_nodes.append(node)
                
                stack.append(node)
            else:
                # 非羅馬數字項目添加到最近的父項目下
                if stack:
                    stack[-1].children.append(node)
                else:
                    # 如果沒有父項目，作為根項目
                    root_nodes.append(node)
        
        return root_nodes
    
    def _calculate_numbers(self, nodes: List[TocNode]) -> None:
        """遞歸計算節點數字"""
        for node in nodes:
            if node.children:
                # 先計算子節點
                self._calculate_numbers(node.children)
                # 父節點數字 = 所有子節點數字之和
                node.calculated_number = sum(child.calculated_number for child in node.children)
            else:
                # 葉子節點保持原數字
                if node.calculated_number == 0:
                    node.calculated_number = node.original_number
    
    def generate_updated_content(self, nodes: List[TocNode]) -> List[str]:
        """生成更新後的內容"""
        lines = []
        self._generate_lines(nodes, lines)
        return lines
    
    def _generate_lines(self, nodes: List[TocNode], lines: List[str]) -> None:
        """遞歸生成行內容"""
        for node in nodes:
            # 更新文本中的數字
            updated_text = self._update_text_number(node.text, node.calculated_number)
            lines.append(updated_text)
            
            # 處理子節點
            if node.children:
                self._generate_lines(node.children, lines)
    
    def _update_text_number(self, text: str, new_number: int) -> str:
        """更新文本中的數字"""
        # 移除原有的數字（如果有）
        text_without_number = self.NUMBER_PATTERN.sub('', text).rstrip()
        
        # 添加新數字
        if new_number > 0:
            return f"{text_without_number} ({new_number})"
        else:
            return text_without_number
    
    def print_statistics(self, nodes: List[TocNode]) -> None:
        """打印統計信息"""
        total_nodes = 0
        updated_nodes = 0
        
        def count_nodes(node_list):
            nonlocal total_nodes, updated_nodes
            for node in node_list:
                total_nodes += 1
                if node.original_number != node.calculated_number:
                    updated_nodes += 1
                    print(f"📝 第{node.line_number}行: {node.original_number} → {node.calculated_number}")
                count_nodes(node.children)
        
        count_nodes(nodes)
        
        print(f"\n📊 統計信息:")
        print(f"- 總節點數: {total_nodes}")
        print(f"- 更新節點數: {updated_nodes}")
        print(f"- 未變更節點數: {total_nodes - updated_nodes}")

def main():
    """主函數"""
    input_file = 'toc_full.txt'
    output_file = 'toc_full_recalculated.txt'
    
    if not os.path.exists(input_file):
        print(f"❌ 錯誤：找不到文件 {input_file}")
        return 1
    
    print(f"🔄 開始重新計算 {input_file} 中的數字...")
    
    calculator = TocNumberCalculator()
    root_nodes = calculator.parse_file(input_file)
    
    print(f"✅ 解析完成，共找到 {len(root_nodes)} 個根節點")
    
    # 打印統計信息
    calculator.print_statistics(root_nodes)
    
    # 生成更新後的內容
    updated_lines = calculator.generate_updated_content(root_nodes)
    
    # 寫入新文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in updated_lines:
            f.write(line + '\n')
    
    print(f"\n✅ 重新計算完成！")
    print(f"📄 原文件: {input_file}")
    print(f"📄 新文件: {output_file}")
    print(f"💡 請檢查新文件內容，確認無誤後可替換原文件")

if __name__ == '__main__':
    main()
