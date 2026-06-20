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
from core.pdf_parser import PDFParser
from core.qa_parser import QAParser
from generators.html_generator import HTMLGenerator
from generators.search_generator import SearchIndexGenerator
from templates.static_assets import StaticAssetsManager


class Word2EBookConverter:
    """Word 转 EBook 转换器主类"""
    
    def __init__(self, config: ConversionConfig, settings: Optional[Settings] = None):
        self.config = config
        self.settings = settings or DEFAULT_SETTINGS
        
        # 初始化组件
        self.file_manager = FileManager(config.output_folder)
        self.document_parser = DocumentParser(self.settings, self.file_manager)
        self.pdf_parser = PDFParser(self.settings)
        self.qa_parser = QAParser(self.settings)
        extra_sources = [config.pdf_file] if config.pdf_file else []
        self.html_generator = HTMLGenerator(
            self.settings, self.file_manager, config.input_file,
            extra_source_files=extra_sources,
            include_qa_source=bool(config.qa_folder),
        )
        self.search_generator = SearchIndexGenerator(self.settings, self.file_manager)
        
        # 静态资源管理器（从原文件加载完整CSS/JS）
        original_file = Path(__file__).parent.parent / "word2ebook.py"
        self.assets_manager = StaticAssetsManager(original_file)

    @property
    def _is_partial(self) -> bool:
        """開發用部分模式：只重生 Word / 只重生 PDF / 只重生 QA 的章節頁。"""
        return self.config.only_word or self.config.only_pdf or self.config.only_qa

    def convert(self) -> None:
        """执行转换"""
        print(f"📋 开始转换：{self.config.input_file} -> {self.config.output_folder}")
        if self.config.pdf_file:
            print(f"   附加 PDF 來源: {self.config.pdf_file}")
        if self.config.qa_folder:
            print(f"   附加 QA 來源: {self.config.qa_folder}")
        if self._is_partial:
            if self.config.only_word:
                mode = "只重生 Word 章節"
            elif self.config.only_pdf:
                mode = "只重生 PDF 章節"
            else:
                mode = "只重生 QA 章節"
            print(f"   ⚡ 部分模式: {mode}（略過首頁與搜尋索引）")
        print(f"   生成简体版: {'✅' if self.config.generate_simplified else '❌'}")
        print(f"   生成繁体版: {'✅' if self.config.generate_traditional else '❌'}")
        print(f"   生成搜索索引: {'✅' if self.config.generate_search else '❌'}")
        print(f"   更新模式: {'🔄 增量更新' if not self.config.generate_search else '🆕 完整重建'}")
        print()
        
        # 1. 设置输出目录
        self._setup_output_directory()
        
        # 1.5. 複製favicon文件（如果有的話）
        self.html_generator.copy_favicon_after_setup()
        
        # 2. 解析來源（Word + 可選的 PDF）
        chapters = self._parse_chapters()
        print(f"✅ 解析完成，共 {len(chapters)} 个章节")
        
        # 3. 生成HTML页面
        print("🔧 正在生成 HTML 页面...")
        self.html_generator.generate_chapter_pages(chapters, self.config.generate_traditional, self.config.generate_simplified)
        if self._is_partial:
            print("⏭️  部分模式：保留現有首頁與搜尋索引（不重建）")
        else:
            self.html_generator.generate_index_pages(chapters, self.config, self.config.generate_traditional, self.config.generate_simplified)
        print("✅ HTML 页面生成完成")
        
        # 4. 处理搜索索引（部分模式下不重建）
        if self._is_partial:
            pass
        elif self.config.generate_search:
            print("🔍 正在生成搜索索引...")
            self.search_generator.generate_search_indexes(chapters, self.config.generate_traditional, self.config.generate_simplified)
        else:
            print("⏭️  跳过搜索索引生成，确保索引文件存在...")
            self.search_generator.ensure_search_index_files(self.config.generate_traditional, self.config.generate_simplified)
        
        # 5. 生成静态资源
        print("🎨 正在生成静态资源...")
        self._generate_static_assets()
        print("✅ 静态资源生成完成")
        
        # 6. 显示完成信息
        self._show_completion_info()

    def _parse_chapters(self) -> list:
        """解析 Word + PDF + QA 來源並串接成單一章節清單。

        完整執行時章節編號依序串接：Word → PDF → QA；各 ``--only-*`` 模式只重生
        對應來源，並使用各自設定的起始編號（保留其他章節頁、首頁與搜尋索引）。
        """
        chapters: list = []

        if not self.config.only_pdf and not self.config.only_qa:
            print("📖 正在解析 Word 文档...")
            word_chapters, _image_map = self.document_parser.parse_document(self.config.input_file)
            print(f"   Word 章節: {len(word_chapters)}")
            chapters.extend(word_chapters)

        if self.config.pdf_file and not self.config.only_word and not self.config.only_qa:
            # 完整執行時 PDF 章節接在 Word 章節之後；只跑 PDF 時用設定的起始編號
            start_index = self.config.pdf_start_index if self.config.only_pdf else len(chapters)
            print(f"📕 正在解析 PDF 答疑（章節編號從 {start_index + 1} 開始）...")
            pdf_chapters = self.pdf_parser.parse(self.config.pdf_file, start_index=start_index)
            print(f"   PDF 章節: {len(pdf_chapters)}")
            chapters.extend(pdf_chapters)

        if self.config.qa_folder and not self.config.only_word and not self.config.only_pdf:
            # 完整執行時 QA 章節接在 Word + PDF 章節之後；只跑 QA 時用設定的起始編號
            start_index = self.config.qa_start_index if self.config.only_qa else len(chapters)
            print(f"📂 正在解析 QA 答疑（章節編號從 {start_index + 1} 開始）...")
            qa_chapters = self.qa_parser.parse_folder(self.config.qa_folder, start_index=start_index)
            print(f"   QA 章節: {len(qa_chapters)}")
            chapters.extend(qa_chapters)

        return chapters
    
    def _setup_output_directory(self) -> None:
        """设置输出目录"""
        print("📁 正在设置输出目录...")
        # 决定是否清空目录的逻辑：
        # 1. 部分模式（只重生 Word/PDF）一定保留現有內容
        # 2. 如果跳过任何版本生成（简体或繁体），则保留现有内容
        # 3. 如果跳过搜索索引生成，则保留现有内容
        # 4. 只有在完整重建时（生成所有内容）才清空目录
        skip_any_version = not self.config.generate_simplified or not self.config.generate_traditional
        clean_existing = (
            self.config.generate_search
            and not skip_any_version
            and not self._is_partial
        )
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
        
        # 写入搜索缓存管理器 JavaScript
        cache_js_path = Path(__file__).parent / "assets" / "js" / "search-cache.js"
        if cache_js_path.exists():
            with open(cache_js_path, 'r', encoding='utf-8') as f:
                cache_js_content = f.read()
            self.file_manager.write_file("assets/js/search-cache.js", cache_js_content)
        
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
        if self.config.generate_simplified:
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
  python main.py input.docx output_folder                    # 生成完整版本
  python main.py input.docx output_folder --pdf answers.pdf  # Word + PDF 月份章節（完整重建）
  python main.py input.docx output_folder --pdf answers.pdf --qa qa  # Word + PDF + QA（完整重建）
  python main.py input.docx output_folder --fast            # 快速模式
  python main.py input.docx output_folder --skip-index      # 跳过搜索索引生成
  python main.py input.docx output_folder --skip-traditional # 跳过繁体版
  python main.py input.docx output_folder --skip-simplified  # 跳过简体版

  # 開發用部分模式（略過首頁與搜尋索引，快速預覽版型）：
  python main.py input.docx output_folder --pdf answers.pdf --only-pdf   # 只重生 PDF 章節
  python main.py input.docx output_folder --only-word                    # 只重生 Word 章節
  python main.py - output_folder --qa qa --only-qa                       # 只重生 QA 章節（省去 Word/PDF 轉換時間）

  # 問答錄 2 一鍵完整重建（Word + PDF + QA → wenda2_ebook/）：
  python3 gen_all.py

        """
    )
    
    parser.add_argument('input_file', help='输入的Word文档路径')
    parser.add_argument('output_folder', help='输出HTML电子书的目录')
    
    parser.add_argument('--skip-index', action='store_true', 
                       help='跳过搜索索引生成，保留现有索引文件（增量更新模式）')
    parser.add_argument('--skip-traditional', action='store_true',
                       help='跳过繁体版生成（加快转换速度）')
    parser.add_argument('--skip-simplified', action='store_true',
                       help='跳过简体版生成（只生成繁体版）')

    parser.add_argument('--fast', action='store_true',
                       help='快速模式：跳过搜索索引生成和繁体版生成')

    parser.add_argument('--pdf', dest='pdf_file', default=None,
                       help='附加的 PDF 答疑來源，會以月份分章接在 Word 章節之後')

    parser.add_argument('--qa', dest='qa_folder', default=None,
                       help='附加的 QA 答疑資料夾（含 txt 文字稿），會以月份分章接在 Word/PDF 章節之後')

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--only-word', action='store_true',
                       help='開發用：只重生 Word 章節頁（保留 PDF/QA 章節、首頁、搜尋索引）')
    mode_group.add_argument('--only-pdf', action='store_true',
                       help='開發用：只重生 PDF 章節頁（保留 Word/QA 章節、首頁、搜尋索引）')
    mode_group.add_argument('--only-qa', action='store_true',
                       help='開發用：只重生 QA 章節頁（保留 Word/PDF 章節、首頁、搜尋索引；省去 Word/PDF 轉換時間）')

    parser.add_argument('--pdf-start-index', type=int, default=12,
                       help='只跑 --only-pdf 時，PDF 章節編號的起始基準（預設 12 → 從 13 開始）')

    parser.add_argument('--qa-start-index', type=int, default=16,
                       help='只跑 --only-qa 時，QA 章節編號的起始基準（預設 16 → 從 17 開始）')
    
    return parser


def main() -> None:
    """主函数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 检查参数冲突
    if args.skip_traditional and args.skip_simplified:
        print("❌ 错误：不能同时跳过简体版和繁体版生成")
        print("   请选择生成至少一种版本")
        sys.exit(1)

    if args.only_pdf and not args.pdf_file:
        print("❌ 错误：--only-pdf 需要同時提供 --pdf <PDF 路徑>")
        sys.exit(1)

    if args.only_qa and not args.qa_folder:
        print("❌ 错误：--only-qa 需要同時提供 --qa <QA 資料夾路徑>")
        sys.exit(1)

    only_word = args.only_word
    only_pdf = args.only_pdf
    only_qa = args.only_qa
    is_partial = only_word or only_pdf or only_qa

    # 处理快速模式和生成选项
    generate_search_index = not (args.skip_index or args.fast)
    generate_traditional = not (args.skip_traditional or args.fast)
    generate_simplified = not (args.skip_simplified or args.fast)

    # 部分模式：略過搜尋索引重建（保留現有索引），加速開發迭代
    if is_partial:
        generate_search_index = False

    
    # 測試優化：如果沒有明確指定，默認只生成繁體版（用於開發測試）
    if not args.skip_traditional and not args.skip_simplified and not args.fast:
        # 檢查是否在開發環境（可以通過環境變量或其他方式判斷）
        import os
        if os.environ.get('WORD2EBOOK_TEST_MODE', '').lower() == 'true':
            print("🧪 測試模式：只生成繁體版以加快測試速度")
            generate_simplified = False
    
    # 创建转换配置
    config = ConversionConfig(
        input_file=Path(args.input_file),
        output_folder=Path(args.output_folder),
        generate_search=generate_search_index,
        generate_traditional=generate_traditional,
        generate_simplified=generate_simplified,
        pdf_file=Path(args.pdf_file) if args.pdf_file else None,
        qa_folder=Path(args.qa_folder) if args.qa_folder else None,
        only_word=only_word,
        only_pdf=only_pdf,
        only_qa=only_qa,
        pdf_start_index=args.pdf_start_index,
        qa_start_index=args.qa_start_index,
    )
    
    # 验证输入文件（--only-pdf / --only-qa 不需要 Word 來源，可省去 Word 轉換時間）
    if not (only_pdf or only_qa):
        if not config.input_file.exists():
            print(f"❌ 错误：输入文件不存在 - {config.input_file}")
            return

        if not config.input_file.suffix.lower() in ['.docx', '.doc']:
            print(f"❌ 错误：不支持的文件格式 - {config.input_file.suffix}")
            return

    # 验证 PDF 来源
    if config.pdf_file is not None:
        if not config.pdf_file.exists():
            print(f"❌ 错误：PDF 文件不存在 - {config.pdf_file}")
            return
        if config.pdf_file.suffix.lower() != '.pdf':
            print(f"❌ 错误：不支持的 PDF 文件格式 - {config.pdf_file.suffix}")
            return

    # 验证 QA 来源
    if config.qa_folder is not None:
        if not config.qa_folder.exists():
            print(f"❌ 错误：QA 資料夾不存在 - {config.qa_folder}")
            return
        if not config.qa_folder.is_dir():
            print(f"❌ 错误：QA 路徑不是資料夾 - {config.qa_folder}")
            return
    
    try:
        # 创建设置副本并应用配置
        settings = DEFAULT_SETTINGS
        
        # 创建转换器并执行转换
        converter = Word2EBookConverter(config, settings)
        converter.convert()
        
    except Exception as e:
        print(f"❌ 转换过程中发生错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()