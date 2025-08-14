"""主程序入口"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# 添加当前目录到路径以支持导入
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from models.document_models import ConversionConfig
from config.settings import Settings, DEFAULT_SETTINGS
from utils.file_utils import FileManager
from core.document_parser import DocumentParser
from generators.html_generator import HTMLGenerator
from generators.search_generator import SearchIndexGenerator
from generators.minisearch_generator import MiniSearchIndexGenerator
from templates.static_assets import StaticAssetsManager


class Word2EBookConverter:
    """Word 转 EBook 转换器主类"""
    
    def __init__(self, config: ConversionConfig, settings: Optional[Settings] = None, skip_compress: bool = False):
        self.config = config
        self.settings = settings or DEFAULT_SETTINGS
        self.skip_compress = skip_compress
        
        # 初始化组件
        self.file_manager = FileManager(config.output_folder)
        self.document_parser = DocumentParser(self.settings, self.file_manager)
        self.html_generator = HTMLGenerator(self.settings, self.file_manager, config.input_file)
        self.search_generator = SearchIndexGenerator(self.settings, self.file_manager)
        self.minisearch_generator = MiniSearchIndexGenerator(self.file_manager)
        
        # 静态资源管理器（从原文件加载完整CSS/JS）
        original_file = Path(__file__).parent.parent / "word2ebook.py"
        self.assets_manager = StaticAssetsManager(original_file)
    
    def convert(self) -> None:
        """执行转换"""
        print(f"📋 开始转换：{self.config.input_file} -> {self.config.output_folder}")
        print(f"   生成繁体版: {'✅' if self.config.generate_traditional else '❌'}")
        print(f"   生成搜索索引: {'✅' if self.config.generate_search else '❌'}")
        
        # 壓縮狀態邏輯：如果不生成索引，自動跳過壓縮
        will_compress = self.config.generate_search and not self.skip_compress
        print(f"   壓縮索引文件: {'✅' if will_compress else '❌'}")
        
        print(f"   更新模式: {'🔄 增量更新' if not self.config.generate_search else '🆕 完整重建'}")
        print()
        
        # 1. 设置输出目录
        self._setup_output_directory()
        
        # 1.5. 複製favicon文件（如果有的話）
        self.html_generator.copy_favicon_after_setup()
        
        # 2. 解析文档
        print("📖 正在解析 Word 文档...")
        chapters, image_map = self.document_parser.parse_document(self.config.input_file)
        print(f"✅ 解析完成，共找到 {len(chapters)} 个章节")
        
        # 3. 生成HTML页面
        print("🔧 正在生成 HTML 页面...")
        self.html_generator.generate_chapter_pages(chapters, self.config.generate_traditional)
        self.html_generator.generate_index_pages(chapters, self.config, self.config.generate_traditional)
        print("✅ HTML 页面生成完成")
        
        # 4. 处理搜索索引
        if self.config.generate_search:
            print("🔍 正在生成搜索索引...")
            self.search_generator.generate_search_indexes(chapters, self.config.generate_traditional, self.skip_compress)
            
            # 5. 生成 MiniSearch 索引（依赖于搜索索引）
            print("🔍 正在生成 MiniSearch 索引...")
            self.minisearch_generator.generate_minisearch_indexes(self.config.generate_traditional, self.skip_compress)
        else:
            print("⏭️  跳过搜索索引生成，确保索引文件存在...")
            self.search_generator.ensure_search_index_files(self.config.generate_traditional)
        
        # 5. 生成静态资源
        print("🎨 正在生成静态资源...")
        self._generate_static_assets()
        print("✅ 静态资源生成完成")
        
        # 6. 显示完成信息
        self._show_completion_info()
    
    def _setup_output_directory(self) -> None:
        """设置输出目录"""
        print("📁 正在设置输出目录...")
        # 根據是否生成搜索索引決定是否清空目錄
        # 如果生成搜索索引，表示是完整重建，需要清空
        # 如果跳過搜索索引，表示是增量更新，保留現有內容
        clean_existing = self.config.generate_search
        self.file_manager.setup_output_directory(clean_existing)
    
    def _generate_static_assets(self) -> None:
        """生成静态资源"""
        # 写入 CSS
        css_content = self.assets_manager.get_full_css_content()
        self.file_manager.write_file("assets/css/style.css", css_content)
        
        # 写入 JavaScript
        js_content = self.assets_manager.get_full_js_content()
        self.file_manager.write_file("assets/js/script.js", js_content)
        
        # 写入 i18n JavaScript
        i18n_js_path = Path(__file__).parent / "assets" / "js" / "i18n-text.js"
        if i18n_js_path.exists():
            with open(i18n_js_path, 'r', encoding='utf-8') as f:
                i18n_js_content = f.read()
            self.file_manager.write_file("assets/js/i18n-text.js", i18n_js_content)
        
        # 复制 jieba-wasm 文件
        jieba_js_path = Path(__file__).parent / "assets" / "js" / "jieba_rs_wasm.js"
        jieba_wasm_path = Path(__file__).parent / "assets" / "js" / "jieba_rs_wasm_bg.wasm"
        
        if jieba_js_path.exists():
            with open(jieba_js_path, 'r', encoding='utf-8') as f:
                jieba_js_content = f.read()
            self.file_manager.write_file("assets/js/jieba_rs_wasm.js", jieba_js_content)
        
        if jieba_wasm_path.exists():
            # WASM 文件需要以二进制模式复制
            with open(jieba_wasm_path, 'rb') as f:
                jieba_wasm_content = f.read()
            self.file_manager.write_binary_file("assets/js/jieba_rs_wasm_bg.wasm", jieba_wasm_content)
    
    def _show_completion_info(self) -> None:
        """显示完成信息"""
        print(f"✅ 转换完成！HTML 电子书已输出到 {self.config.output_folder}")
        print(f"📖 简体版首页: {self.config.output_folder}/index.html")
        if self.config.generate_traditional:
            print(f"📖 繁体版首页: {self.config.output_folder}/index_trad.html")


def create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='将Word文档转换为HTML电子书',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py input.docx output_folder                     # 生成完整版本（包含壓縮）
  python main.py input.docx output_folder --fast             # 快速模式（跳過索引和繁體版）
  python main.py input.docx output_folder --skip-index       # 跳过搜索索引生成
  python main.py input.docx output_folder --skip-compress    # 跳过壓縮（推薦用於快速更新）
  python main.py input.docx output_folder --skip-traditional # 跳过繁体版

💡 提示：大部分時候使用 --skip-compress 可以大幅加快生成速度，除非需要部署到生產環境
        """
    )
    
    parser.add_argument('input_file', help='输入的Word文档路径')
    parser.add_argument('output_folder', help='输出HTML电子书的目录')
    
    parser.add_argument('--skip-index', action='store_true', 
                       help='跳过搜索索引生成，保留现有索引文件（增量更新模式）')
    parser.add_argument('--skip-compress', action='store_true',
                       help='跳过索引文件的 Brotli 压缩（加快生成速度）')
    parser.add_argument('--skip-traditional', action='store_true',
                       help='跳过繁体版生成（加快转换速度）')
    parser.add_argument('--fast', action='store_true',
                       help='快速模式：跳过搜索索引生成和繁体版生成')
    
    return parser


def main() -> None:
    """主函数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 处理快速模式和参数逻辑
    generate_search_index = not (args.skip_index or args.fast)
    generate_traditional = not (args.skip_traditional or args.fast)
    
    # 壓縮邏輯：如果不生成索引或明確跳過壓縮，則跳過壓縮
    skip_compress = args.skip_compress or not generate_search_index
    
    # 创建转换配置
    config = ConversionConfig(
        input_file=Path(args.input_file),
        output_folder=Path(args.output_folder),
        generate_search=generate_search_index,
        generate_traditional=generate_traditional
    )
    
    # 验证输入文件
    if not config.input_file.exists():
        print(f"❌ 错误：输入文件不存在 - {config.input_file}")
        return
    
    if not config.input_file.suffix.lower() in ['.docx', '.doc']:
        print(f"❌ 错误：不支持的文件格式 - {config.input_file.suffix}")
        return
    
    try:
        # 创建转换器并执行转换
        converter = Word2EBookConverter(config, DEFAULT_SETTINGS, skip_compress)
        converter.convert()
        
    except Exception as e:
        print(f"❌ 转换过程中发生错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()