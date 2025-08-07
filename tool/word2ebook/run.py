#!/usr/bin/env python3
"""
Word2EBook 启动脚本

这个脚本解决了直接运行时的相对导入问题。
用法：python run.py [参数...]
"""

import sys
import os
from pathlib import Path

# 确保当前目录在 Python 路径中
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# 导入并运行主程序
if __name__ == "__main__":
    from main import main
    main()