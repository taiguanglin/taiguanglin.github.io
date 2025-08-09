# Favicon 功能說明

## 功能概述

Word2EBook 工具現在支援自動檢測和使用Word文件同目錄下的favicon文件作為網站圖標。

## 功能特點

### 1. **自動檢測**
- 工具會自動檢測Word文件同目錄下的favicon文件
- 支援多種格式：`.ico`, `.png`, `.svg`
- 按優先級順序搜索：`favicon.ico` > `favicon.png` > `favicon.svg`

### 2. **全站應用**
- 所有頁面（首頁和章節頁）都會包含favicon
- 簡體版和繁體版都會使用相同的favicon

### 3. **智能處理**
- 如果找到favicon文件，會自動複製到輸出目錄根部
- 在所有HTML頁面的 `<head>` 部分添加對應的 `<link>` 標籤
- 如果沒有找到favicon文件，不會影響正常轉換過程

### 4. **配置靈活**
- 可通過 `config.yaml` 配置是否啟用favicon功能
- 可自定義搜索的文件名模式

## 使用方法

### 基本使用
只需將 `favicon.ico`（或其他支援格式）放在Word文件同目錄下即可：

```
/your/project/folder/
├── document.docx
├── favicon.ico          # 👈 放在這裡
└── ...
```

運行轉換命令：
```bash
python main.py document.docx output_folder
```

### 進階配置
在 `config.yaml` 中自定義favicon設定：

```yaml
# Favicon 設定
favicon:
  # 是否啟用 favicon 功能
  enabled: true
  
  # 搜索 favicon 文件的模式（按優先級順序）
  search_patterns:
    - "favicon.ico"
    - "favicon.png" 
    - "favicon.svg"
    - "logo.ico"      # 可添加自定義名稱
```

## 技術實現

### 文件檢測流程
1. 初始化時檢測Word文件同目錄下的favicon文件
2. 生成對應的HTML標籤內容
3. 在輸出目錄設置完成後複製favicon文件
4. 在所有HTML模板中插入favicon標籤

### HTML標籤生成
根據文件格式自動生成對應的HTML標籤：

- `.ico` 文件：`<link rel="icon" type="image/x-icon" href="favicon.ico">`
- `.png` 文件：`<link rel="icon" type="image/png" href="favicon.png">`
- `.svg` 文件：`<link rel="icon" type="image/svg+xml" href="favicon.svg">`

### 錯誤處理
- 文件不存在：跳過favicon設置，不影響轉換過程
- 複製失敗：記錄警告但繼續轉換
- 格式不支援：使用通用格式 `<link rel="icon" href="...">`

## 測試結果

### ✅ 有favicon文件的情況
```
✅ 找到 favicon 文件：tool/word2ebook/favicon.ico
✅ Favicon 已複製到：wenda2_ebook/favicon.ico
```

生成的HTML包含：
```html
<link rel="icon" type="image/x-icon" href="favicon.ico">
```

### ✅ 沒有favicon文件的情況
```
ℹ️  未找到 favicon 文件，跳過favicon設置
```

生成的HTML不包含favicon標籤，轉換正常完成。

## 向後兼容

- 完全向後兼容，不會影響現有功能
- 如果不放置favicon文件，行為與原版完全相同
- 可通過配置關閉favicon功能

## 檔案結構

### 新增文件
- `utils/favicon_utils.py` - Favicon 處理工具
- `FAVICON_FEATURE.md` - 功能說明文檔

### 修改文件
- `config/settings.py` - 新增favicon配置選項
- `templates/i18n_templates.py` - HTML模板支援favicon
- `generators/html_generator.py` - 整合favicon功能
- `main.py` - 主流程支援favicon
- `config.yaml` - 配置文件新增favicon選項

這個功能提供了完整的favicon支援，讓生成的電子書更加專業和美觀。
