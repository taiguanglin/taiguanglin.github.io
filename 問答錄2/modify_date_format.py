import pandas as pd
import re
import os

def normalize_and_format_date(text):
    """
    從文字中識別日期時間，統一格式為 YYYY-MM-DD，並移除時間部分。
    支援截圖中的格式:
    - 2024/3/19 -> 2024-03-19
    - 2024-03-20 19:44 -> 2024-03-20
    - 明月:2024/3/20 -> 2024-03-20
    """
    if not isinstance(text, str):
        return text

    # 定義匹配規則 (優先匹配長格式)
    patterns = [
        # 1. YYYY-MM-DD HH:MM (標準或無空格/無冒號變體)
        # 涵蓋: 2025-03-09 11:30, 2024-03-0310:57
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(\d{1,2}:\d{2}|\d{4})\b', 'ymd_time'),
        
        # 2. DD/MM/YYYY (歐式格式，如 21/06/2024)
        (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', 'dmy'),
        
        # 3. YYYY/MM/DD (僅日期，涵蓋截圖中的 2024/3/19)
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 'ymd_date_only')
    ]

    for pattern, type_ in patterns:
        match = re.search(pattern, text)
        if match:
            original_str = match.group(0) # 抓取完整的日期時間字串
            
            # 解析年-月-日
            if type_ == 'ymd_time' or type_ == 'ymd_date_only':
                year, month, day = match.group(1), match.group(2), match.group(3)
            elif type_ == 'dmy':
                day, month, year = match.group(1), match.group(2), match.group(3)
            
            # 格式化為 YYYY-MM-DD
            formatted_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            
            # 替換原文中的日期字串
            new_text = text.replace(original_str, formatted_date)
            return new_text

    return text

# ================= 設定區 (依據截圖填入) =================
# 檔案名稱 (請確認你的檔案副檔名是 xlsx 還是 xlsm)
file_name = '1_坐禅问答汇总 分类精选工作表 20251219.xlsx' 

# 工作表名稱 (下方 Tab 顯示的名稱)
sheet_name = '答疑汇总' 

# 目標欄位名稱 (Column V 的標題)
target_col = '问题' 

# 標題所在的 Excel 行數 (截圖中標題在第 6 行)
# Python index = Excel Row - 1
header_row_excel = 6 

# 要處理的 Excel Row 範圍
start_excel_row = 2916
end_excel_row = 4369
# ========================================================

# 檢查檔案是否存在
if not os.path.exists(file_name):
    print(f"錯誤: 找不到檔案 '{file_name}'")
    print("請確認檔案位於程式執行的同一資料夾內，或是名稱是否完全正確。")
else:
    print(f"正在讀取檔案: {file_name} ...")
    
    # 1. 讀取 Excel
    # header參數設為 header_row_excel - 1，因為 pandas 是 0-based
    df = pd.read_excel(file_name, sheet_name=sheet_name, header=header_row_excel-1)

    # 2. 計算 Pandas 的 Index 範圍
    # 假設標題在第 6 行，則第 7 行是 index 0
    # 公式: Index = Excel行號 - (標題行號 + 1)
    offset = header_row_excel + 1
    start_idx = start_excel_row - offset
    end_idx = end_excel_row - offset

    print(f"標題在第 {header_row_excel} 行。")
    print(f"正在處理 Excel Row {start_excel_row} (Index {start_idx}) 到 {end_excel_row} (Index {end_idx})...")

    # 3. 執行轉換
    # 檢查目標欄位是否存在
    if target_col in df.columns:
        # 使用 .loc 鎖定範圍進行處理
        subset = df.loc[start_idx:end_idx, target_col].copy()
        
        # 顯示處理前的前幾筆供確認 (可選)
        # print("處理前範例:\n", subset.head(3))
        
        df.loc[start_idx:end_idx, target_col] = subset.apply(normalize_and_format_date)
        
        # 4. 存檔
        output_file = 'output_' + file_name
        df.to_excel(output_file, index=False)
        print("------------------------------------------------")
        print(f"✅ 處理完成！")
        print(f"檔案已儲存為: {output_file}")
        print("請打開新檔案檢查 Row 2916 附近的日期格式是否正確。")
        
    else:
        print(f"錯誤: 在工作表中找不到欄位 '{target_col}'。請確認標題列位置是否正確。")

