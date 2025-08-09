# Word2EBook 配置指南

## 新功能概述

本次更新為 Word2EBook 工具新增了強大的配置功能，主要包括：

1. **📖 自訂電子書標題** - 支援簡體和繁體版本分別設定不同標題
2. **🌐 完整的國際化支援** - 修正所有UI文字的簡繁轉換
3. **🔧 靈活的配置系統** - 通過 YAML 配置文件進行個性化設定

## 主要改進

### 1. 電子書標題配置
- ✅ 新增 `config.yaml` 配置文件支援
- ✅ 可分別設定簡體和繁體版本的電子書標題
- ✅ 優先使用配置文件中的標題，未設定時才使用檔案名

### 2. 國際化文字修正
- ✅ "Table of Contents" → "目錄"（簡體："目录"，繁體："目錄"）
- ✅ 修正"章節目錄"、"回首頁"、"書籤"等UI文字的簡繁轉換
- ✅ 語言切換按鈕：繁體頁面中的"簡體"顯示為簡體字
- ✅ JavaScript中的所有硬編碼中文文字支援國際化

### 3. 技術改進
- ✅ 建立統一的國際化（i18n）機制
- ✅ 支援 YAML 配置文件讀取
- ✅ 模組化的模板管理系統

## 使用方法

### 基本使用（無需配置）

工具仍然完全向後兼容，原有的使用方式不變：

```bash
python main.py input.docx output_folder
```

### 進階使用（自訂配置）

1. **複製配置範例文件**：
   ```bash
   cp config-example.yaml config.yaml
   ```

2. **編輯配置文件**：
   ```yaml
   # config.yaml
   book_title:
     simplified: "您的簡體書名"
     traditional: "您的繁體書名"
   ```

3. **執行轉換**：
   ```bash
   python main.py input.docx output_folder
   ```

## 配置文件說明

### 完整配置範例

```yaml
# Word2EBook 配置文件
book_title:
  simplified: "太光林问答录"    # 簡體版標題
  traditional: "太光林問答錄"   # 繁體版標題

# 自訂UI文字（可選）
i18n:
  table_of_contents:
    simplified: "目录"
    traditional: "目錄"
  
  navigation:
    home:
      simplified: "回首页"
      traditional: "回首頁"
```

### 配置選項說明

| 配置項 | 說明 | 預設值 |
|--------|------|--------|
| `book_title.simplified` | 簡體版電子書標題 | 使用檔案名 |
| `book_title.traditional` | 繁體版電子書標題 | 使用檔案名 |
| `i18n.*` | 自訂UI文字 | 使用內建預設值 |

## 技術細節

### 新增文件

- `config.yaml` - 主配置文件
- `config-example.yaml` - 配置範例
- `utils/config_utils.py` - 配置管理器
- `templates/i18n_templates.py` - 國際化模板管理
- `assets/js/i18n-text.js` - JavaScript國際化支援

### 修改文件

- `models/document_models.py` - 新增標題獲取方法
- `generators/html_generator.py` - 整合國際化模板
- `main.py` - 支援新的資源文件
- `requirements.txt` - 新增 PyYAML 依賴

## 常見問題

### Q: 如果不創建配置文件會怎樣？
A: 工具會使用預設設定，行為與原版完全相同。

### Q: 可以只設定簡體或繁體標題嗎？
A: 可以。未設定的版本會使用檔案名作為標題。

### Q: 配置文件放在哪裡？
A: 放在 `word2ebook` 目錄根部，與 `main.py` 同級。

### Q: 如何恢復原始設定？
A: 刪除或重命名 `config.yaml` 文件即可。

## 升級注意事項

1. **依賴更新**：需要安裝 PyYAML
   ```bash
   pip install -r requirements.txt
   ```

2. **向後兼容**：所有原有功能保持不變

3. **配置可選**：不創建配置文件不會影響使用

## 範例輸出

使用配置後，生成的電子書將會：

- **簡體版** (`index.html`)：顯示"太光林问答录"，所有UI文字為簡體
- **繁體版** (`index_trad.html`)：顯示"太光林問答錄"，所有UI文字為繁體
- **語言切換**：繁體頁面中的"簡體"按鈕顯示簡體字"简体"

## 結語

這次更新大幅提升了工具的國際化支援和靈活性，同時保持了完全的向後兼容。無論是簡單使用還是深度自訂，都能滿足不同用戶的需求。
