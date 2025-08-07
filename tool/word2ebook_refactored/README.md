# Word2EBook - 重构版

这是 Word2EBook 工具的重构版本，采用模块化设计，便于维护和扩展。

## 功能特性

- 📖 **Word 文档解析**：支持 .docx 格式，提取文本、图片和结构
- 🌐 **HTML 生成**：生成响应式电子书，支持问答格式
- 🔍 **全文搜索**：集成搜索功能，支持中文检索
- 🌏 **多语言支持**：自动生成简体和繁体中文版本
- 📱 **用户体验**：书签、导航、阅读设置等前端功能
- 🧪 **测试覆盖**：包含单元测试，确保代码质量

## 项目结构

```
word2ebook_refactored/
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
├── tests/                  # 测试模块
│   ├── test_text_utils.py  # 文本工具测试
│   └── test_models.py      # 模型测试
├── main.py                 # 主程序入口
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
python main.py input.docx output_folder --skip-search

# 跳过繁体版
python main.py input.docx output_folder --skip-traditional
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

### 3. 测试覆盖
- **单元测试**：使用 pytest 框架
- **模型测试**：验证数据结构正确性
- **工具测试**：确保工具函数可靠

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

```bash
cd word2ebook_refactored
python -m pytest tests/ -v
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