#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試分類器功能
"""

import sys
from qa_classifier import QAClassifier

def test_single_classification():
    """測試單個分類功能"""
    print("=== 測試單個分類功能 ===")
    
    try:
        classifier = QAClassifier()
        
        # 測試數據
        test_title = "關於打坐時的妄想問題"
        test_content = """
        問：師父，我在打坐的時候總是有很多妄想，應該如何對治？
        
        答：妄想是修行過程中的正常現象。重要的是不要與妄想對抗，
        而是要觀照它們。當妄想起來時，不追隨，不壓制，只是覺知。
        通過持續的練習，妄想會自然減少。
        """
        
        print(f"測試標題: {test_title}")
        print(f"測試內容: {test_content[:100]}...")
        
        result = classifier.classify_qa(test_title, test_content)
        
        print("\\n分類結果:")
        print(f"最佳分類: {result['classification']}")
        print(f"理由: {result['reason']}")
        print(f"問題摘要: {result['question_summary']}")
        print(f"回答摘要: {result['answer_summary']}")
        
        return True
        
    except Exception as e:
        print(f"測試失敗: {e}")
        return False

def test_excel_loading():
    """測試Excel載入功能"""
    print("\\n=== 測試Excel載入功能 ===")
    
    try:
        classifier = QAClassifier()
        workbook, worksheet = classifier.load_excel_data()
        
        print(f"成功載入工作表: {worksheet.title}")
        print(f"最大行數: {worksheet.max_row}")
        print(f"最大列數: {worksheet.max_column}")
        
        # 測試提取第一行數據
        if worksheet.max_row >= 2:
            title, content = classifier.extract_qa_content(worksheet, 2)
            print(f"\\n第2行數據預覽:")
            print(f"標題: {title[:50]}...")
            print(f"內容: {content[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"Excel載入測試失敗: {e}")
        return False

def test_category_system():
    """測試目錄體系載入"""
    print("\\n=== 測試目錄體系載入 ===")
    
    try:
        classifier = QAClassifier()
        categories = classifier.category_system
        
        print("目錄體系預覽:")
        print(categories[:500] + "..." if len(categories) > 500 else categories)
        
        return True
        
    except Exception as e:
        print(f"目錄體系載入測試失敗: {e}")
        return False

def main():
    """運行所有測試"""
    print("問答分類器測試程序")
    print("=" * 50)
    
    tests = [
        ("目錄體系載入", test_category_system),
        ("Excel載入功能", test_excel_loading),
        ("單個分類功能", test_single_classification),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\\n運行測試: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"測試 {test_name} 發生異常: {e}")
            results.append((test_name, False))
    
    # 顯示測試結果
    print("\\n" + "=" * 50)
    print("測試結果摘要:")
    
    for test_name, success in results:
        status = "✅ 通過" if success else "❌ 失敗"
        print(f"{test_name}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    
    print(f"\\n總測試數: {total_tests}")
    print(f"通過測試: {passed_tests}")
    print(f"失敗測試: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("\\n🎉 所有測試通過！系統可以正常運行。")
    else:
        print("\\n⚠️  部分測試失敗，請檢查配置和依賴。")

if __name__ == "__main__":
    main()
