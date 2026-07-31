/**
 * 國際化文字配置
 */

// 定義所有需要國際化的文字
window.I18N_TEXT = {
  // 搜索相關
  search: {
    loading: {
      simplified: '正在加载搜索功能，请稍候...',
      traditional: '正在載入搜尋功能，請稍候...'
    },
    loadingIndex: {
      simplified: '正在加载搜索索引...',
      traditional: '正在載入搜尋索引...'
    },
    loadingData: {
      simplified: '正在下载搜索数据...',
      traditional: '正在下載搜尋資料...'
    },
    processingIndex: {
      simplified: '正在处理搜索索引...',
      traditional: '正在處理搜尋索引...'
    },
    indexReady: {
      simplified: '搜索准备就绪 (共{count}条记录)',
      traditional: '搜尋準備就緒 (共{count}條記錄)'
    },
    loadingFailed: {
      simplified: '搜索索引加载失败',
      traditional: '搜尋索引載入失敗'
    },
    retry: {
      simplified: '重试',
      traditional: '重試'
    },
    networkError: {
      simplified: '网络连接失败，请检查网络后重试',
      traditional: '網路連接失敗，請檢查網路後重試'
    },
    searchUnavailable: {
      simplified: '搜索功能暂不可用',
      traditional: '搜尋功能暫不可用'
    },
    search_placeholder: {
      simplified: '搜索全文内容...',
      traditional: '搜尋全文內容...'
    },
    minCharWarning: {
      simplified: '请输入至少2个字符进行搜索',
      traditional: '請輸入至少2個字元進行搜尋'
    },
    resultTypes: {
      heading: {
        simplified: '标题',
        traditional: '標題'
      },
      question: {
        simplified: '问题',
        traditional: '問題'
      },
      answer: {
        simplified: '回答',
        traditional: '回答'
      },
      content: {
        simplified: '内容',
        traditional: '內容'
      }
    },
    scope_label: {
      simplified: '搜索范围',
      traditional: '搜尋範圍'
    },
    scope_question: {
      simplified: '问题',
      traditional: '問題'
    },
    scope_answer: {
      simplified: '回答',
      traditional: '回答'
    },
    scope_both: {
      simplified: '两者',
      traditional: '兩者'
    }
  },
  
  // 書籤相關
  bookmark: {
    myBookmarks: {
      simplified: '我的书签',
      traditional: '我的書籤'
    },
    noBookmarks: {
      simplified: '暂无书签',
      traditional: '尚無書籤'
    },
    empty: {
      simplified: '尚无书签',
      traditional: '尚無書籤'
    },
    addToBookmark: {
      simplified: '加入书签',
      traditional: '加入書籤'
    },
    removeBookmark: {
      simplified: '点击移除书签',
      traditional: '點擊移除書籤'
    },
    processing: {
      simplified: '处理 {count} 个书签...',
      traditional: '處理 {count} 個書籤...'
    },
    deleteBookmark: {
      simplified: '删除书签',
      traditional: '刪除書籤'
    },
    bookmarkAdded: {
      simplified: '已添加到书签，可在侧边栏查看',
      traditional: '已添加到書籤，可在側邊欄查看'
    },
    bookmarkDeleted: {
      simplified: '书签已删除',
      traditional: '書籤已刪除'
    },
    viewInSidebar: {
      simplified: '已添加到书签，可在侧边栏查看',
      traditional: '已添加到書籤，可在側邊欄查看'
    }
  },
  
  // 導航相關
  navigation: {
    tableOfContents: {
      simplified: '目录',
      traditional: '目錄'
    },
    chapterDirectory: {
      simplified: '章节目录',
      traditional: '章節目錄'
    },
    bookmarks: {
      simplified: '书签',
      traditional: '書籤'
    },
    unknownChapter: {
      simplified: '未知章节',
      traditional: '未知章節'
    },
    homepage: {
      simplified: '首页',
      traditional: '首頁'
    }
  },
  
  // 操作相關
  actions: {
    copyQA: {
      simplified: '复制问答',
      traditional: '複製問答'
    },
    shareQuestion: {
      simplified: '分享问题',
      traditional: '分享問題'
    },
    shareAnswer: {
      simplified: '分享回答',
      traditional: '分享回答'
    }
  },
  
  // UI相關
  ui: {
    home: {
      simplified: '回首页',
      traditional: '回首頁'
    },
    functionMenu: {
      simplified: '功能菜单',
      traditional: '功能選單'
    },
    settings: {
      simplified: '设置',
      traditional: '設置'
    },
    backToTop: {
      simplified: '回到顶部',
      traditional: '回到頂部'
    },
    directory: {
      simplified: '目录',
      traditional: '目錄'
    },
    tableOfContents: {
      simplified: '目录',
      traditional: '目錄'
    }
  },
  
  // 閱讀設置相關
  readingSettings: {
    title: {
      simplified: '阅读设置',
      traditional: '閱讀設置'
    },
    fontSize: {
      simplified: '字体大小',
      traditional: '字體大小'
    },
    lineHeight: {
      simplified: '行距',
      traditional: '行距'
    },
    width: {
      simplified: '宽度',
      traditional: '寬度'
    },
    theme: {
      simplified: '主题',
      traditional: '主題'
    },
    fontDecrease: {
      simplified: 'A-',
      traditional: 'A-'
    },
    fontNormal: {
      simplified: '默认',
      traditional: '預設'
    },
    fontIncrease: {
      simplified: 'A+',
      traditional: 'A+'
    },
    lineTight: {
      simplified: '紧凑',
      traditional: '緊密'
    },
    lineNormal: {
      simplified: '正常',
      traditional: '正常'
    },
    lineLoose: {
      simplified: '松散',
      traditional: '寬鬆'
    },
    widthNarrow: {
      simplified: '窄',
      traditional: '窄'
    },
    widthNormal: {
      simplified: '中',
      traditional: '中'
    },
    widthWide: {
      simplified: '宽',
      traditional: '寬'
    },
    themeLight: {
      simplified: '☀️ 日间',
      traditional: '☀️ 日間'
    },
    themeDark: {
      simplified: '🌙 夜间',
      traditional: '🌙 夜間'
    }
  },
  
  // 功能說明
  instructions: {
    bookmarkHelp: {
      simplified: '书签功能说明',
      traditional: '書籤功能說明'
    },
    enterChapter: {
      simplified: '• 进入任意章节',
      traditional: '• 進入任意章節'
    },
    findInteresting: {
      simplified: '• 找到感兴趣的问答',
      traditional: '• 找到感興趣的問答'
    },
    clickBookmark: {
      simplified: '• 点击右上角书签图标',
      traditional: '• 點擊右上角書籤圖標'
    },
    returnToView: {
      simplified: '• 返回此处查看收藏',
      traditional: '• 返回此處查看收藏'
    }
  }
};

/**
 * 獲取國際化文字
 * @param {string} keyPath - 文字鍵值路徑，如 'bookmark.myBookmarks'
 * @param {boolean} isTraditional - 是否為繁體版
 * @param {string} defaultText - 默認文字
 * @param {Object} params - 參數對象，用於替換文字中的佔位符
 * @returns {string} 本地化文字
 */
function getI18nText(keyPath, isTraditional = false, defaultText = '', params = {}) {
  if (!window.I18N_TEXT) {
    return defaultText;
  }
  
  // 解析嵌套鍵值路徑
  const keys = keyPath.split('.');
  let current = window.I18N_TEXT;
  
  try {
    for (const key of keys) {
      current = current[key];
      if (!current) {
        return defaultText;
      }
    }
    
    // 獲取對應語言版本
    let text;
    if (typeof current === 'object' && current !== null) {
      text = isTraditional ? current.traditional : current.simplified;
    } else {
      text = current;
    }
    
    if (!text) {
      return defaultText;
    }
    
    // 替換參數
    Object.keys(params).forEach(key => {
      text = text.replace(new RegExp(`\\{${key}\\}`, 'g'), params[key]);
    });
    
    return text;
    
  } catch (error) {
    console.warn('獲取國際化文字失敗:', keyPath, error);
    return defaultText;
  }
}

// 判斷是否為繁體版頁面
function isTraditionalChinesePage() {
  const pathname = window.location.pathname;
  const filename = pathname.split('/').pop() || 'index.html';
  return filename.includes('_trad.html');
}

// 便捷函數 - 獲取本地化文字
function getText(simplifiedText, traditionalText, params = {}) {
  return isTraditionalChinesePage() ? traditionalText : simplifiedText;
}
