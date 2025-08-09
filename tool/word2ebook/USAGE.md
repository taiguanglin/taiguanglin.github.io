# Word2EBook 重构版使用说明

## 快速开始

重构版本已经修复了导入问题，现在可以直接使用：

### 基本使用

```bash
# 进入重构版目录
cd word2ebook_refactored

# 运行转换（推荐使用 run.py）
python3 run.py input.docx output_folder

# 或者使用原版兼容接口
python3 word2ebook.py input.docx output_folder
```

### 转换选项

```bash
# 生成完整版本（简体+繁体+搜索）
python3 run.py input.docx output_folder

# 快速模式（只生成简体版，跳过繁体和搜索）
python3 run.py input.docx output_folder --fast

# 跳过搜索索引（生成简体和繁体，但不生成搜索功能）
python3 run.py input.docx output_folder --skip-search

# 跳过繁体版（生成简体和搜索，但不生成繁体）
python3 run.py input.docx output_folder --skip-traditional
```

### 实际使用示例

```bash
# 转换问答文档到 wenda2_ebook 目录
python3 run.py ~/Downloads/wenda.docx ~/taiguanglin.github.io/wenda2_ebook

# 快速转换（测试用）
python3 run.py ~/Downloads/wenda.docx ~/taiguanglin.github.io/wenda2_ebook --fast
```

## 重构优势

1. **模块化设计**：代码分为7个模块，职责清晰
2. **类型安全**：添加了完整的类型注解
3. **易于维护**：结构化的代码便于修改和扩展
4. **测试覆盖**：包含单元测试
5. **向后兼容**：保持与原版完全一致的接口

## 问题解决

如果遇到导入错误，请确保：

1. 使用 `run.py` 而不是直接运行其他文件
2. 在正确的目录中运行（`word2ebook_refactored/`）
3. 检查 Python 环境和依赖包

## 开发测试

```bash
# 运行测试
python -m pytest tests/ -v

# 检查帮助
python3 run.py --help
```