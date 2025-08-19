# 問答分類系統 v2.0 使用說明

## 🎯 **新版本特點**

### **分離式處理架構**
- **階段1**: 分類處理 → JSON結果文件
- **階段2**: JSON結果 → Excel文件
- **優勢**: 高效能、容錯性強、支持中斷續處理

## 📁 **文件結構**

```
classify/
├── qa_classifier_v2.py      # 主分類程序（v2.0）
├── results_to_excel.py      # 結果寫入Excel工具
├── config.ini               # 配置文件
├── prompt_template.txt      # OpenAI提示詞模板
├── README_v2.md            # 本使用說明
└── requirements.txt         # 依賴包列表
```

## 🚀 **快速開始**

### **步驟1: 執行分類處理**
```bash
# 使用默認配置處理
python3 qa_classifier_v2.py

# 輸出示例
問答分類自動化系統 v2.0
==================================================
2025-08-19 05:20:27 - INFO - OpenAI設置完成 - 模型: gpt-4o
2025-08-19 05:20:27 - INFO - 開始處理第 2 到 12 行，共 11 條記錄
2025-08-19 05:20:27 - INFO - 結果將保存到: qa_classification_results_20250819_052027.json
...
✅ 分類完成！結果已保存到: qa_classification_results_20250819_052027.json
```

### **步驟2: 寫入Excel文件**
```bash
# 將JSON結果寫入Excel
python3 results_to_excel.py qa_classification_results_20250819_052027.json

# 指定輸出文件名
python3 results_to_excel.py results.json -o final_classified.xlsx

# 輸出示例
分類結果寫入Excel工具
========================================
2025-08-19 05:25:00 - INFO - 開始寫入 95 條分類結果
✅ 處理完成！
📁 輸出文件: classified_results_20250819_052500.xlsx
```

## ⚙️ **配置說明**

### **config.ini 配置項**
```ini
[processing]
start_row = 2      # 開始處理的行號
end_row = 100      # 結束行號（0表示處理到最後）
batch_size = 10    # 批次大小（暫時未使用）

[output]
classification_column = 20    # T列 - 分類結果
reason_column = 21           # U列 - 分類理由
question_summary_column = 22 # V列 - 問題摘要
answer_summary_column = 23   # W列 - 答案摘要
```

## 📊 **結果格式**

### **JSON結果文件結構**
```json
{
  "metadata": {
    "source_file": "坐禅问答汇总 20250810.xlsx",
    "processing_start_time": "2025-08-19T05:20:27",
    "total_processed": 95,
    "total_success": 90
  },
  "results": {
    "7": {
      "row_number": 7,
      "question": "什么是如来自性？",
      "answer": "恒常不变的本我叫如来自性...",
      "classification": "【自性与意识】（95%）【修心】（75%）",
      "reason": "問題直接詢問如來自性的定義",
      "question_summary": "詢問如來自性的含義", 
      "answer_summary": "解釋自性恒常不變的特性",
      "status": "success",
      "processed_time": "2025-08-19T05:20:28"
    }
  }
}
```

## 🔄 **中斷續處理**

### **自動續處理機制**
- 如果程序中斷，重新運行時會自動檢測已處理的條目
- 只處理尚未分類的條目，節省時間和API調用費用

```bash
# 程序中斷後重新運行，會自動跳過已處理項目
python3 qa_classifier_v2.py
# 輸出: 第 7 行已處理，跳過
```

## 📈 **進度監控**

### **實時日誌**
- 處理進度實時顯示
- 每10條記錄自動保存中間結果
- 成功/失敗統計

### **日誌文件**
- 自動生成: `classification_YYYYMMDD_HHMMSS.log`
- 包含詳細的處理記錄和錯誤信息

## 🛠️ **高級用法**

### **指定處理範圍**
```python
# 在 qa_classifier_v2.py 的 main() 函數中修改
classifier.process_batch(start_row=100, end_row=200)
```

### **自定義結果文件名**
```python
# 指定結果文件名
results_file = classifier.process_batch(results_file='my_results.json')
```

### **批量處理多個範圍**
```bash
# 處理不同範圍
python3 -c "
from qa_classifier_v2 import QAClassifierV2
classifier = QAClassifierV2()
classifier.process_batch(start_row=2, end_row=50, results_file='batch1.json')
classifier.process_batch(start_row=51, end_row=100, results_file='batch2.json')
"
```

## 🔍 **故障排除**

### **常見問題**

1. **OpenAI API錯誤**
   ```
   錯誤: OpenAI API調用失敗
   解決: 檢查API Key和網絡連接
   ```

2. **Excel文件鎖定**
   ```
   錯誤: 無法寫入Excel文件
   解決: 確保Excel文件未被其他程序打開
   ```

3. **JSON文件損壞**
   ```
   錯誤: 載入結果文件失敗
   解決: 檢查JSON文件格式，或重新運行分類
   ```

### **調試模式**
```bash
# 啟用詳細日誌
export PYTHONPATH=.
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from qa_classifier_v2 import QAClassifierV2
classifier = QAClassifierV2()
classifier.process_batch(start_row=7, end_row=8)  # 只處理一條測試
"
```

## 📋 **版本對比**

| 功能 | v1.0 | v2.0 |
|------|------|------|
| Excel操作 | 每條記錄都寫入 | 批量寫入 |
| 中斷恢復 | ❌ | ✅ |
| 進度保存 | ❌ | ✅ 每10條保存 |
| 錯誤容忍 | 低 | 高 |
| 處理速度 | 慢 | 快 |
| 結果格式 | Excel only | JSON + Excel |

## 🎉 **使用建議**

1. **小批次測試**: 先設定小範圍測試（如end_row=10）
2. **分段處理**: 大量數據建議分段處理，避免長時間運行
3. **備份結果**: JSON結果文件很重要，建議備份
4. **監控API費用**: 注意OpenAI API的使用量和費用

---

🔗 **相關文件**
- [配置說明](config.ini) 
- [提示詞模板](prompt_template.txt)
- [依賴包列表](requirements.txt)
