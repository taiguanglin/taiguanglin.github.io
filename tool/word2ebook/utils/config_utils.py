"""配置文件工具"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路徑，如果為None則使用默認路徑
        """
        if config_path is None:
            # 默認配置文件路徑
            self.config_path = Path(__file__).parent.parent / "config.yaml"
        else:
            self.config_path = config_path
        
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """加載配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                print(f"⚠️  配置文件不存在：{self.config_path}，使用默認配置")
                self._config = {}
        except Exception as e:
            print(f"⚠️  讀取配置文件失敗：{e}，使用默認配置")
            self._config = {}
    
    def get_book_title(self, is_traditional: bool = False, default_title: str = "") -> str:
        """獲取電子書標題
        
        Args:
            is_traditional: 是否為繁體版
            default_title: 默認標題（通常為文件名）
            
        Returns:
            電子書標題
        """
        if not self._config:
            return default_title
        
        book_title_config = self._config.get('book_title', {})
        
        if is_traditional:
            title = book_title_config.get('traditional', '')
        else:
            title = book_title_config.get('simplified', '')
        
        # 如果配置中沒有設置標題，使用默認標題
        return title if title else default_title
    
    def get_i18n_text(self, key_path: str, is_traditional: bool = False, default: str = "") -> str:
        """獲取國際化文字
        
        Args:
            key_path: 文字鍵值路徑，如 'navigation.home'
            is_traditional: 是否為繁體版
            default: 默認文字
            
        Returns:
            本地化文字
        """
        if not self._config:
            return default
        
        i18n_config = self._config.get('i18n', {})
        
        # 解析嵌套鍵值路徑
        keys = key_path.split('.')
        current = i18n_config
        
        try:
            for key in keys:
                current = current[key]
            
            # 獲取對應語言版本
            if isinstance(current, dict):
                if is_traditional:
                    return current.get('traditional', default)
                else:
                    return current.get('simplified', default)
            else:
                return str(current) if current else default
                
        except (KeyError, TypeError):
            return default
    
    def get_generation_config(self, key: str, default: Any = None) -> Any:
        """獲取生成配置
        
        Args:
            key: 配置鍵
            default: 默認值
            
        Returns:
            配置值
        """
        if not self._config:
            return default
        
        generation_config = self._config.get('generation', {})
        return generation_config.get(key, default)
    
    def reload_config(self) -> None:
        """重新加載配置文件"""
        self._load_config()


# 全局配置管理器實例
config_manager = ConfigManager()


def get_book_title(is_traditional: bool = False, default_title: str = "") -> str:
    """獲取電子書標題的便捷函數"""
    return config_manager.get_book_title(is_traditional, default_title)


def get_i18n_text(key_path: str, is_traditional: bool = False, default: str = "") -> str:
    """獲取國際化文字的便捷函數"""
    return config_manager.get_i18n_text(key_path, is_traditional, default)


def get_generation_config(key: str, default: Any = None) -> Any:
    """獲取生成配置的便捷函數"""
    return config_manager.get_generation_config(key, default)
