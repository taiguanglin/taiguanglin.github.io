#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分類結果寫入Excel程序
讀取JSON格式的分類結果，批量寫入Excel文件
"""

import json
import openpyxl
from openpyxl import load_workbook
import configparser
import logging
from datetime import datetime
import os
import argparse
from typing import Dict, Any

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResultsToExcel:
    """分類結果寫入Excel"""
    
    def __init__(self, config_file: str = 'config.ini'):
        """初始化"""
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')
        
        logger.info("Excel寫入器初始化完成")
    
    def load_results(self, results_file: str) -> Dict[str, Any]:
        """載入分類結果"""
        if not os.path.exists(results_file):
            raise FileNotFoundError(f"結果文件不存在: {results_file}")
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"成功載入結果文件: {results_file}")
            logger.info(f"元數據: 總處理 {data['metadata'].get('total_processed', 0)}, "
                       f"成功 {data['metadata'].get('total_success', 0)}")
            
            return data
        except Exception as e:
            logger.error(f"載入結果文件失敗: {e}")
            raise
    
    def create_output_excel(self, source_file: str, output_file: str) -> tuple:
        """創建輸出Excel文件"""
        try:
            # 複製原始文件
            workbook = load_workbook(source_file)
            sheet_name = self.config.get('excel', 'sheet_name')
            worksheet = workbook[sheet_name]
            
            logger.info(f"成功載入源Excel文件: {source_file}")
            return workbook, worksheet
        except Exception as e:
            logger.error(f"創建輸出Excel失敗: {e}")
            raise
    
    def write_classification_result(self, worksheet, row: int, result: Dict[str, Any]):
        """寫入分類結果到指定行"""
        try:
            # 獲取輸出列配置
            classification_col = self.config.getint('output', 'classification_column')
            reason_col = self.config.getint('output', 'reason_column')
            question_summary_col = self.config.getint('output', 'question_summary_column')
            answer_summary_col = self.config.getint('output', 'answer_summary_column')
            
            # 寫入分類結果
            worksheet.cell(row=row, column=classification_col).value = result.get('classification', '')
            worksheet.cell(row=row, column=reason_col).value = result.get('reason', '')
            worksheet.cell(row=row, column=question_summary_col).value = result.get('question_summary', '')
            worksheet.cell(row=row, column=answer_summary_col).value = result.get('answer_summary', '')
            
        except Exception as e:
            logger.error(f"寫入第 {row} 行結果失敗: {e}")
            raise
    
    def process_results(self, results_file: str, output_file: str = None):
        """處理分類結果並寫入Excel"""
        # 載入結果
        data = self.load_results(results_file)
        results = data.get('results', {})
        metadata = data.get('metadata', {})
        
        if not results:
            logger.warning("沒有找到分類結果")
            return
        
        # 確定輸出文件名
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"classified_results_{timestamp}.xlsx"
        
        # 創建輸出Excel
        source_file = metadata.get('source_file', self.config.get('excel', 'file_path'))
        workbook, worksheet = self.create_output_excel(source_file, output_file)
        
        logger.info(f"開始寫入 {len(results)} 條分類結果")
        
        # 統計信息
        success_count = 0
        failed_count = 0
        
        # 按行號排序處理
        sorted_results = sorted(results.items(), key=lambda x: int(x[0]))
        
        for row_key, result in sorted_results:
            try:
                row_number = int(row_key)
                
                # 寫入結果
                self.write_classification_result(worksheet, row_number, result)
                
                if result.get('status') == 'success':
                    success_count += 1
                else:
                    failed_count += 1
                
                if (success_count + failed_count) % 50 == 0:
                    logger.info(f"已處理 {success_count + failed_count} 條結果")
                
            except Exception as e:
                logger.error(f"處理行 {row_key} 時發生錯誤: {e}")
                failed_count += 1
                continue
        
        # 保存Excel文件
        try:
            workbook.save(output_file)
            logger.info(f"✅ Excel文件已保存: {output_file}")
            logger.info(f"📊 統計: 成功寫入 {success_count} 條，失敗 {failed_count} 條")
            
            # 顯示元數據信息
            if metadata:
                logger.info("📋 處理信息:")
                logger.info(f"   源文件: {metadata.get('source_file', 'N/A')}")
                logger.info(f"   處理時間: {metadata.get('processing_start_time', 'N/A')} - {metadata.get('processing_end_time', 'N/A')}")
                logger.info(f"   總處理: {metadata.get('total_processed', 0)}")
                logger.info(f"   成功率: {metadata.get('total_success', 0)}/{metadata.get('total_processed', 0)}")
            
            return output_file
            
        except Exception as e:
            logger.error(f"保存Excel文件失敗: {e}")
            raise

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='將分類結果寫入Excel文件')
    parser.add_argument('results_file', help='分類結果JSON文件路徑')
    parser.add_argument('-o', '--output', help='輸出Excel文件路徑（可選）')
    parser.add_argument('-c', '--config', default='config.ini', help='配置文件路徑')
    
    args = parser.parse_args()
    
    print("分類結果寫入Excel工具")
    print("=" * 40)
    
    try:
        writer = ResultsToExcel(args.config)
        output_file = writer.process_results(args.results_file, args.output)
        
        print(f"\n✅ 處理完成！")
        print(f"📁 輸出文件: {output_file}")
        
    except Exception as e:
        logger.error(f"程序執行失敗: {e}")
        print(f"❌ 程序執行失敗: {e}")

if __name__ == "__main__":
    main()
