"""文件操作工具"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any
from slugify import slugify


def safe_filename(title: str, index: int) -> str:
    """生成安全的文件名"""
    slug = slugify(title)
    if not slug:
        slug = f"chapter{index}"
    return f"{index:02d}-{slug}.html"


class FileManager:
    """文件管理器"""
    
    def __init__(self, output_folder: Path):
        self.output_folder = Path(output_folder)
    
    def setup_output_directory(self, clean_existing: bool = True) -> None:
        """设置输出目录结构
        
        Args:
            clean_existing: 是否清空現有目錄。
                          True（默認）- 完全重建，清空現有內容
                          False - 增量更新，保留現有內容
        """
        if clean_existing:
            # 完全重建模式：如果输出目录存在，先删除
            if self.output_folder.exists():
                print("🗑️  清空現有目錄，完全重建...")
                shutil.rmtree(self.output_folder)
        else:
            # 增量更新模式：保留現有內容，只確保目錄結構存在
            if self.output_folder.exists():
                print("📁 保留現有內容，增量更新...")
            else:
                print("📁 創建新目錄...")
        
        # 创建目录结构（如果不存在）
        self.output_folder.mkdir(parents=True, exist_ok=True)
        (self.output_folder / "assets" / "css").mkdir(parents=True, exist_ok=True)
        (self.output_folder / "assets" / "js").mkdir(parents=True, exist_ok=True)
        (self.output_folder / "assets" / "images").mkdir(parents=True, exist_ok=True)
    
    def get_assets_path(self, asset_type: str) -> Path:
        """获取资源文件路径"""
        return self.output_folder / "assets" / asset_type
    
    def write_file(self, filename: str, content: str, encoding: str = 'utf-8') -> None:
        """写入文件"""
        file_path = self.output_folder / filename
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
    
    def write_binary_file(self, filename: str, content: bytes) -> None:
        """写入二进制文件"""
        file_path = self.output_folder / filename
        with open(file_path, 'wb') as f:
            f.write(content)
    
    def copy_file(self, source: Path, dest_filename: str) -> None:
        """复制文件到输出目录"""
        dest_path = self.output_folder / dest_filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest_path)
    
    def file_exists(self, filename: str) -> bool:
        """检查文件是否存在"""
        return (self.output_folder / filename).exists()
    
    def get_file_path(self, filename: str) -> Path:
        """获取文件的完整路径"""
        return self.output_folder / filename


class ImageHandler:
    """图片处理器"""
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.image_counter = 1
    
    def extract_images_from_document(self, doc, image_map: Dict[str, str]) -> Dict[str, str]:
        """从 Word 文档提取图片并保存到输出目录
        
        Args:
            doc: Word 文档对象
            image_map: 已有的图片映射字典
            
        Returns:
            图片ID到相对路径的映射字典 {rId: relative_path}
        """
        rels = doc.part.rels
        
        for rel in rels.values():
            if "image" in rel.target_ref:
                image_data = rel.target_part.blob
                filename = f"image_{self.image_counter}.png"
                
                # 保存图片到 assets/images 目录
                image_path = self.file_manager.get_assets_path("images") / filename
                with open(image_path, "wb") as f:
                    f.write(image_data)
                
                # 记录映射关系（使用相对路径）
                relative_path = f"assets/images/{filename}"
                image_map[rel.rId] = relative_path
                self.image_counter += 1
        
        return image_map