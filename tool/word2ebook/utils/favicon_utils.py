"""Favicon 處理工具"""

from pathlib import Path
from typing import Optional, List
import shutil


class FaviconManager:
    """Favicon 管理器"""
    
    def __init__(self, input_file_path: Path, output_folder: Path, search_patterns: List[str] = None):
        """初始化 Favicon 管理器
        
        Args:
            input_file_path: 輸入Word文件路徑
            output_folder: 輸出目錄路徑
            search_patterns: 搜索模式列表，默認為 ["favicon.ico", "favicon.png", "favicon.svg"]
        """
        self.input_file_path = input_file_path
        self.output_folder = output_folder
        self.search_patterns = search_patterns or ["favicon.ico", "favicon.png", "favicon.svg"]
        self.favicon_file = None
        self.favicon_relative_path = None
    
    def find_favicon(self) -> Optional[Path]:
        """在Word文件同目錄下尋找favicon文件
        
        Returns:
            找到的favicon文件路徑，如果沒找到則返回None
        """
        # 獲取Word文件所在目錄
        source_dir = self.input_file_path.parent
        
        # 按優先級順序搜索favicon文件
        for pattern in self.search_patterns:
            favicon_path = source_dir / pattern
            if favicon_path.exists() and favicon_path.is_file():
                print(f"✅ 找到 favicon 文件：{favicon_path}")
                self.favicon_file = favicon_path
                self.favicon_relative_path = pattern
                return favicon_path
        
        print("⚠️  【警告】未找到 favicon 文件！")
        print("   已搜索以下文件：")
        for pattern in self.search_patterns:
            search_path = source_dir / pattern
            print(f"   - {search_path}")
        print("   程序將繼續運行，但網頁將沒有 favicon 圖標。")
        return None
    
    def copy_favicon_to_output(self) -> bool:
        """將favicon文件複製到輸出目錄
        
        Returns:
            是否成功複製
        """
        if not self.favicon_file:
            return False
        
        try:
            # 確保輸出目錄存在
            self.output_folder.mkdir(parents=True, exist_ok=True)
            
            # 複製到輸出目錄根部
            output_favicon_path = self.output_folder / self.favicon_relative_path
            shutil.copy2(self.favicon_file, output_favicon_path)
            print(f"✅ Favicon 已複製到：{output_favicon_path}")
            return True
            
        except Exception as e:
            print(f"⚠️  複製 favicon 失敗：{e}")
            return False
    
    def get_favicon_html_tag(self) -> str:
        """獲取favicon的HTML標籤
        
        Returns:
            HTML link標籤字符串，如果沒有favicon則返回空字符串
        """
        if not self.favicon_relative_path:
            return ""
        
        # 根據文件擴展名決定type
        ext = Path(self.favicon_relative_path).suffix.lower()
        
        if ext == '.ico':
            return f'<link rel="icon" type="image/x-icon" href="{self.favicon_relative_path}">'
        elif ext == '.png':
            return f'<link rel="icon" type="image/png" href="{self.favicon_relative_path}">'
        elif ext == '.svg':
            return f'<link rel="icon" type="image/svg+xml" href="{self.favicon_relative_path}">'
        else:
            # 通用格式
            return f'<link rel="icon" href="{self.favicon_relative_path}">'
    
    def process_favicon(self) -> str:
        """處理favicon的完整流程
        
        Returns:
            favicon的HTML標籤，如果處理失敗則返回空字符串
        """
        # 1. 尋找favicon文件
        if not self.find_favicon():
            return ""
        
        # 2. 複製favicon文件
        if not self.copy_favicon_to_output():
            return ""
        
        # 3. 生成HTML標籤
        return self.get_favicon_html_tag()


def process_favicon_for_conversion(input_file: Path, output_folder: Path, 
                                  search_patterns: List[str] = None) -> str:
    """為轉換過程處理favicon的便捷函數
    
    Args:
        input_file: 輸入Word文件路徑
        output_folder: 輸出目錄路徑
        search_patterns: 搜索模式列表
        
    Returns:
        favicon的HTML標籤字符串
    """
    manager = FaviconManager(input_file, output_folder, search_patterns)
    return manager.process_favicon()
