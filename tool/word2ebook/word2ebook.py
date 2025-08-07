"""向后兼容的接口

保持与原版 word2ebook.py 相同的接口，便于现有脚本使用。
"""

import sys
import os
from pathlib import Path

# 添加当前目录到 Python 路径，以支持直接运行
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

import argparse
from main import Word2EBookConverter, create_argument_parser
from models.document_models import ConversionConfig
from config.settings import DEFAULT_SETTINGS


def convert_word_to_ebook(input_file: str, output_folder: str, 
                         generate_search: bool = True, 
                         generate_traditional: bool = True) -> None:
    """
    原版接口的兼容函数
    
    Args:
        input_file: 输入文件路径
        output_folder: 输出目录路径
        generate_search: 是否生成搜索索引
        generate_traditional: 是否生成繁体版
    """
    config = ConversionConfig(
        input_file=Path(input_file),
        output_folder=Path(output_folder),
        generate_search=generate_search,
        generate_traditional=generate_traditional
    )
    
    converter = Word2EBookConverter(config, DEFAULT_SETTINGS)
    converter.convert()


if __name__ == "__main__":
    # 使用相同的命令行接口
    from main import main
    main()