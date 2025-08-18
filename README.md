# 太光林問答錄網站

## 📋 項目概述

太光林問答錄是一個佛學問答網站，提供結構化的佛學修行問答內容。本項目包含網站前端、內容管理工具和相關功能模組。

## 🏗️ 項目結構

### 🌐 主要網站
- `index.html` - 主頁
- `wenda.html` - 問答頁面
- `stories.html` - 修行故事頁面
- `style.css` - 主要樣式
- `script.js` - 主要腳本

### 📚 內容目錄
- `wenda/` - 章節式問答內容
- `wenda_complete/` - 完整問答內容
- `wenda2_ebook/` - 電子書格式問答內容
- `stories/` - 修行經驗分享故事
- `images/` - 圖片資源

### 🛠️ 工具模組

#### Word轉電子書工具 (`tool/word2ebook/`)
將Word文檔轉換為網頁電子書格式的工具。
- 詳細說明請參考: `tool/word2ebook/README.md`

#### 目錄轉換工具 (`new_toc/`)
用於生成和轉換目錄格式的工具。
- 詳細說明請參考: `README_目录转换说明.md`

#### 問答分類工具 (`classify/`)
使用AI自動分類問答內容的工具。
- 詳細說明請參考: `classify/README.md`

## 🚀 快速開始

### 安裝依賴
```bash
pip install -r requirements.txt
```

### 運行網站
直接在瀏覽器中打開 `index.html` 即可瀏覽網站。

## 📝 使用說明

### 網站瀏覽
- 主頁提供網站導航和概述
- 問答頁面包含結構化的佛學問答
- 故事頁面分享修行經驗

### 工具使用
每個工具模組都有獨立的說明文檔，請參考相應目錄下的README文件。

## 🔧 技術架構

- **前端**: HTML5, CSS3, JavaScript
- **內容格式**: 靜態HTML頁面
- **工具鏈**: Python 工具集
- **部署**: 靜態網站部署

## 📄 文件說明

### 核心文件
- `README.md` - 項目說明文檔
- `requirements.txt` - Python依賴包
- `sitemap.xml` - 網站地圖
- `robots.txt` - 搜索引擎規則

### 配置文件
- `CNAME` - 域名配置

## 🤝 貢獻指南

歡迎對項目進行改進和貢獻。請：
1. Fork 此項目
2. 創建功能分支
3. 提交您的修改
4. 發起 Pull Request

## 📞 聯絡方式

如有問題或建議，請通過網站聯絡功能與我們聯繫。