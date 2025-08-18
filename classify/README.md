# 問答分類自動化系統

## 📋 系統概述

這個系統可以自動將"答疑汇总"工作表中的答疑條目按照新目錄體系進行分類評分，使用OpenAI API進行智能分類。

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 配置設定

#### 2.1 設置OpenAI API Key

編輯 `config.ini` 文件：

```ini
[openai]
api_key = 你的_OPENAI_API_KEY
```

#### 2.2 調整配置參數

根據需要修改 `config.ini` 中的設定：

- **Excel文件設定**: 文件路徑、工作表名稱、列位置
- **輸出列設定**: 結果要寫入的列位置
- **處理範圍**: 要處理的行數範圍

### 3. 自定義Prompt

編輯 `prompt_template.txt` 文件來調整分類邏輯和要求。

### 4. 運行程序

```bash
python qa_classifier.py
```

## 📊 配置說明

### config.ini 重要參數

```ini
[excel]
title_column = 6           # 標題所在列（第F列）
qa_start_column = 7        # 答疑內容開始列（第G列）

[output]
classification_column = 20  # 最佳分類排序寫入列（第T列）
reason_column = 21         # 理由寫入列（第U列）
question_summary_column = 22  # 提問摘要寫入列（第V列）
answer_summary_column = 23    # 回答摘要寫入列（第W列）

[processing]
start_row = 2              # 開始處理的行
end_row = 100             # 結束行（0表示處理到最後）
```

## 🎯 輸出格式

系統會在指定列寫入以下內容：

### 最佳分類排序（第T列）
```
【消业】（95%）
【义理】（75%）
【修心】（60%）
```

### 理由（第U列）
說明分類的依據和信心度評估原因

### 提問重點摘要（第V列）
提取問題的核心重點（50字以內）

### 回答重點摘要（第W列）
提取回答的核心重點（100字以內）

## 🔧 功能特點

### ✅ 智能分類
- 基於新目錄體系自動分類
- 多級信心度評估
- 自動摘要提取

### ✅ 安全可靠
- 自動跳過已分類的條目
- 定期保存避免數據丟失
- 詳細的日誌記錄

### ✅ 可配置
- 彈性的配置文件
- 可自定義的Prompt模板
- 可調整的處理範圍

### ✅ 批量處理
- 支持大量數據處理
- API調用頻率控制
- 中斷恢復機制

## 📝 使用注意事項

1. **API費用**: 使用OpenAI API會產生費用，建議先小範圍測試
2. **處理時間**: 大量數據需要較長時間，建議分批處理
3. **備份數據**: 處理前請備份原始Excel文件
4. **網絡穩定**: 確保網絡連接穩定，避免API調用中斷

## 🛠️ 進階使用

### 只處理特定範圍

```python
classifier = QAClassifier()
classifier.process_batch(start_row=2, end_row=10)  # 只處理第2-10行
```

### 檢查日誌

系統會自動生成日誌文件：`classification_YYYYMMDD_HHMMSS.log`

### 自定義分類體系

如需使用不同的目錄文件，請修改 `qa_classifier.py` 中的路徑：

```python
toc_file = "你的目錄文件路徑.txt"
```

## 🔍 故障排除

### 常見問題

1. **API Key錯誤**: 檢查 `config.ini` 中的API Key是否正確
2. **文件找不到**: 確認Excel文件路徑和工作表名稱
3. **列位置錯誤**: 檢查配置文件中的列號設定
4. **權限問題**: 確保對Excel文件有讀寫權限

### 測試建議

1. 先設定小範圍測試（如前10行）
2. 檢查輸出結果是否符合預期
3. 確認配置無誤後再處理全部數據

## 📄 文件說明

- `qa_classifier.py`: 主程序
- `config.ini`: 配置文件
- `prompt_template.txt`: Prompt模板
- `requirements.txt`: Python依賴包
- `README.md`: 使用說明
