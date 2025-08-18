#!/bin/bash

echo "問答分類系統安裝和測試腳本"
echo "=================================="

# 檢查Python版本
echo "檢查Python版本..."
python3 --version

# 安裝依賴包
echo "安裝依賴包..."
pip3 install -r requirements.txt

# 檢查安裝是否成功
echo "測試模塊載入..."
python3 -c "
try:
    import configparser
    import openpyxl
    print('✅ 基本模塊載入成功')
except ImportError as e:
    print(f'❌ 基本模塊載入失敗: {e}')

try:
    import openai
    print('✅ OpenAI模塊載入成功')
except ImportError as e:
    print(f'❌ OpenAI模塊載入失敗: {e}')
"

echo ""
echo "安裝完成！"
echo ""
echo "下一步："
echo "1. 編輯 config.ini 設置您的 OpenAI API Key"
echo "2. 根據需要調整 prompt_template.txt"
echo "3. 運行: python3 qa_classifier.py"
