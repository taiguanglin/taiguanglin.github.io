# Word2EBook - 重构版

这是 Word2EBook 工具的重构版本，采用模块化设计，便于维护和扩展。

## 功能特性

- 📖 **Word 文档解析**：支持 .docx 格式，提取文本、图片和结构
- 🌐 **HTML 生成**：生成响应式电子书，支持问答格式
- 🔍 **全文搜索**：集成搜索功能，支持中文检索
- 🌏 **多语言支持**：自动生成简体和繁体中文版本
- 📱 **用户体验**：书签、导航、阅读设置等前端功能
- 🧪 **测试计划**：测试用例尚未完善，未来将提供单元测试以确保代码质量

## 项目结构

```
word2ebook/
├── core/                   # 核心解析模块
│   ├── document_parser.py  # Word 文档解析器
│   └── content_processor.py # 内容处理器
├── generators/             # 生成器模块
│   ├── html_generator.py   # HTML 生成器
│   └── search_generator.py # 搜索索引生成器
├── templates/              # 模板和静态资源
│   ├── html_templates.py   # HTML 模板管理
│   └── static_assets.py    # CSS/JS 资源管理
├── utils/                  # 工具模块
│   ├── text_utils.py       # 文本处理工具
│   ├── file_utils.py       # 文件操作工具
│   └── i18n_utils.py       # 国际化工具
├── models/                 # 数据模型
│   └── document_models.py  # 文档数据结构
├── config/                 # 配置管理
│   └── settings.py         # 配置和常量
├── main.py                 # 主程序入口
├── gen_all.py              # 問答錄 2 一鍵完整重建（Word + PDF + QA）
├── gen_all_and_push.py     # 重建後 git add / commit / push
├── run.py                  # 啟動腳本（解決相對匯入）
├── word2ebook.py          # 向后兼容接口
└── requirements.txt        # 依赖包
```

## 安装和使用

### 安装依赖

```bash
cd word2ebook_refactored
pip install -r requirements.txt
```

### 基本使用

```bash
# 生成完整版本（简体+繁体+搜索）
python main.py input.docx output_folder

# 快速模式（只生成简体版）
python main.py input.docx output_folder --fast

# 跳过搜索索引
python main.py input.docx output_folder --skip-index

# 跳过繁体版
python main.py input.docx output_folder --skip-traditional

# Word + 附加 PDF 答疑（依月份分章，接在 Word 章節之後）
python main.py input.docx output_folder --pdf answers.pdf

# 開發用部分模式（略過首頁與搜尋索引，快速預覽版型）
python main.py input.docx output_folder --pdf answers.pdf --only-pdf  # 只重生 PDF 章節
python main.py input.docx output_folder --only-word                   # 只重生 Word 章節
```

> `--pdf` 會把「每月答疑合併 PDF」解析成月份章節（章節標題如 `13二〇二五年六月`），
> 章節內以「日期 + 來源」（例如 `2025年6月9日 貼吧`）作為第二層目錄，版型、計數與
> 全文搜尋皆與 Word 章節一致。部分模式僅供開發快速預覽，最終發佈請執行一次完整建置。

### 問答錄 2 一鍵完整重建

修正 `qa/` 文字稿、或更新 Word/PDF 來源後，在 `tool/word2ebook/` 執行：

```bash
cd tool/word2ebook
python3 gen_all.py
```

此腳本會完整重建 `wenda2_ebook/`（Word 章節 + PDF 月份章節 + QA 月份章節，含簡繁雙語、
首頁目錄與搜尋索引）。預設路徑（皆相對於 repo 根目錄）：

| 來源 | 路徑 |
|------|------|
| Word | `問答錄2/wenda2_250810_截止25年5月17日答疑_含图版.docx` |
| PDF | `問答錄2/2025年6月-9月答疑合并（未分类）.pdf` |
| QA | `qa/` |
| 輸出 | `wenda2_ebook/` |

### 重建並推送到 GitHub

重建完成後若要把變更直接提交、推送：

```bash
cd tool/word2ebook
python3 gen_all_and_push.py
```

自訂 commit 訊息：

```bash
python3 gen_all_and_push.py -m "更新 2026 年 3 月 QA 校稿"
```

此腳本會依序執行 `gen_all.py` → `git add :/` → `git commit` → `git push`（在 repo
根目錄操作）。若重建後沒有任何變更，會略過 commit 與 push。

開發時若只需快速驗證 QA 文字稿轉換（略過 Word/PDF 與首頁、搜尋索引），仍可使用：

```bash
python3 main.py - ../../wenda2_ebook --qa ../../qa --only-qa
```

### 程序化使用

```python
from pathlib import Path
from main import Word2EBookConverter
from models.document_models import ConversionConfig

# 创建配置
config = ConversionConfig(
    input_file=Path("input.docx"),
    output_folder=Path("output"),
    generate_search=True,
    generate_traditional=True
)

# 执行转换
converter = Word2EBookConverter(config)
converter.convert()
```

## 重构改进

### 1. 模块化设计
- **单一职责**：每个模块专注特定功能
- **清晰接口**：模块间依赖关系明确
- **易于扩展**：新功能可独立开发

### 2. 代码质量
- **类型注解**：使用 Python type hints
- **文档字符串**：详细的函数说明
- **现代特性**：dataclasses、pathlib 等

### 3. 测试计划
- 目前尚未提供测试用例，未来将使用 pytest 编写单元测试以验证核心模块

### 4. 配置管理
- **外部化配置**：设置与代码分离
- **常量定义**：统一管理常量值
- **默认值**：合理的默认配置

## 向后兼容

重构版本保持与原版完全兼容的接口：

```python
# 原版接口依然可用
from word2ebook import convert_word_to_ebook

convert_word_to_ebook(
    input_file="input.docx",
    output_folder="output",
    generate_search=True,
    generate_traditional=True
)
```

## 运行测试

当前尚未提供测试用例。一旦测试就绪，可通过以下命令运行：

```bash
python -m pytest -v
```

## 扩展开发

### 添加新的处理器

1. 在 `core/` 目录下创建新的处理器类
2. 继承或组合现有的基础类
3. 在 `main.py` 中集成新处理器

### 添加新的生成器

1. 在 `generators/` 目录下创建新生成器
2. 实现生成接口
3. 更新主程序流程

### 自定义模板

1. 修改 `templates/html_templates.py` 中的模板
2. 或者创建新的模板管理器
3. 在生成器中使用自定义模板

## 技术栈

- **Python 3.7+**
- **python-docx**：Word 文档处理
- **beautifulsoup4**：HTML 解析
- **opencc-python-reimplemented**：简繁转换
- **python-slugify**：URL 友好化
- **pytest**：测试框架

## 许可证

与原版相同的许可证。