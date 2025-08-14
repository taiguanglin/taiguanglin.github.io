"""MiniSearch 索引生成器"""

import json
import subprocess
import tempfile
from typing import List, Dict, Any
from pathlib import Path

from models.document_models import SearchItem
from utils.file_utils import FileManager
from config.settings import Constants


class MiniSearchIndexGenerator:
    """MiniSearch 索引生成器"""
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
    
    def generate_minisearch_indexes(self, generate_traditional: bool = True, skip_compress: bool = False) -> None:
        """生成 MiniSearch 索引文件"""
        print("🔍 正在生成 MiniSearch 索引...")
        
        # 生成简体版 MiniSearch 索引
        self._generate_minisearch_index(Constants.SEARCH_INDEX_SIMPLIFIED, 
                                      Constants.MINISEARCH_INDEX_SIMPLIFIED, 
                                      skip_compress)
        
        # 生成繁体版 MiniSearch 索引
        if generate_traditional:
            self._generate_minisearch_index(Constants.SEARCH_INDEX_TRADITIONAL, 
                                          Constants.MINISEARCH_INDEX_TRADITIONAL, 
                                          skip_compress)
    
    def _generate_minisearch_index(self, search_index_file: str, output_file: str, skip_compress: bool = False) -> None:
        """生成单个 MiniSearch 索引"""
        search_index_path = self.file_manager.get_file_path(search_index_file)
        
        if not search_index_path.exists():
            print(f"⚠️ 搜索索引文件不存在，跳过 MiniSearch 索引生成: {search_index_file}")
            return
        
        # 读取搜索索引数据
        with open(search_index_path, 'r', encoding='utf-8') as f:
            search_data = json.load(f)
        
        print(f"📊 正在为 {len(search_data)} 条记录生成 MiniSearch 索引...")
        
        # 创建 Node.js 脚本来生成 MiniSearch 索引
        minisearch_index = self._create_minisearch_index(search_data)
        
        # 写入 MiniSearch 索引文件
        self._write_minisearch_index(minisearch_index, output_file, skip_compress)
        
        print(f"✅ MiniSearch 索引已生成：{output_file}")
    
    def _create_minisearch_index(self, search_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """使用 Node.js 创建 MiniSearch 索引"""
        # 创建临时文件存储搜索数据
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
            json.dump(search_data, temp_file, ensure_ascii=False, separators=(',', ':'))
            temp_file_path = temp_file.name
        
        # 创建 Node.js 脚本
        node_script = f'''
const MiniSearch = require('minisearch');
const fs = require('fs');

// 读取搜索数据
const searchData = JSON.parse(fs.readFileSync('{temp_file_path}', 'utf8'));

// 创建 MiniSearch 实例
const miniSearch = new MiniSearch({{
  fields: ['title', 'content', 'tokens'], // 搜索字段
  storeFields: ['title', 'content', 'url', 'type', 'weight', 'tokens'], // 存储字段
  processTerm: (term, _fieldName) => {{
    // 处理中文分词 - 这里我们依赖预处理的 tokens
    if (!term || typeof term !== 'string') return null;
    return term.length >= 1 ? term.toLowerCase() : null;
  }}
}});

// 添加文档到索引
miniSearch.addAll(searchData);

// 导出索引
const indexData = miniSearch.toJSON();
console.log(JSON.stringify(indexData));
'''
        
        try:
            # 执行 Node.js 脚本（在源代码目录中执行以访问 node_modules）
            source_dir = Path(__file__).parent.parent  # tool/word2ebook 目录
            result = subprocess.run(
                ['node', '-e', node_script],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=source_dir
            )
            
            if result.returncode != 0:
                raise Exception(f"Node.js 脚本执行失败: {result.stderr}")
            
            # 解析返回的索引数据
            index_data = json.loads(result.stdout.strip())
            return index_data
            
        finally:
            # 清理临时文件
            Path(temp_file_path).unlink(missing_ok=True)
    
    def _write_minisearch_index(self, index_data: Dict[str, Any], filename: str, skip_compress: bool = False) -> None:
        """写入 MiniSearch 索引文件（支持 Brotli 压缩）"""
        # 序列化索引数据
        index_content = json.dumps(index_data, ensure_ascii=False, separators=(',', ':'))
        
        # 写入原始 JSON 文件
        self.file_manager.write_file(filename, index_content)
        
        # 如果不跳过压缩，则进行 Brotli 压缩
        if not skip_compress:
            try:
                import brotli
                compressed_data = brotli.compress(index_content.encode('utf-8'), quality=11)
                compressed_filename = filename.replace('.json', '.br')
                self.file_manager.write_binary_file(compressed_filename, compressed_data)
                
                original_size = len(index_content.encode('utf-8'))
                compressed_size = len(compressed_data)
                compression_ratio = (1 - compressed_size / original_size) * 100
                
                print(f"📦 Brotli 压缩完成：{filename}")
                print(f"   原始大小: {original_size:,} bytes")
                print(f"   压缩大小: {compressed_size:,} bytes")
                print(f"   压缩率: {compression_ratio:.1f}%")
                
            except Exception as e:
                print(f"⚠️ Brotli 压缩失败 {filename}: {e}")
                print("   将继续使用未压缩的 JSON 文件")
