# -*- coding: utf-8 -*-
"""實修故事來源檔案的中介資料與版面設定。

每個故事一筆設定：
  slug        產生的 HTML 檔名（stories/<slug>.html）
  source      原始檔（相對於網站根目錄）
  title       頁面標題（繁體）
  author      作者／分享者
  date        原文日期（可為空字串）
  category    分類，對應 stories.html 的分組
  summary     摘要（用於 meta description 與頁面導言）
  keywords    SEO 關鍵字
  layout      PDF 版面參數（僅 PDF 需要）
"""

DOCS = [
    # ---------------- 雙盤 ----------------
    {
        "slug": "shuangpan-jieti-fa-meiqin",
        "source": "stories/快速突破双盘两小时的阶梯法-美琴.pdf",
        "title": "快速突破雙盤兩小時的階梯法",
        "orig_title": "快速突破双盘两小时的阶梯法",
        "author": "美琴師兄（美樂琴心）",
        "date": "",
        "category": "雙盤打坐",
        "summary": "以「每天加一分鐘」的階梯法，從零基礎、散盤、單盤逐步推進到雙盤兩小時的具體時程規劃與實作經驗。",
        "keywords": "雙盤,階梯法,突破兩小時,打坐,腹式呼吸,磕大頭,美樂琴心",
        "layout": {"indent_x": 111, "body_x": 90, "right": 505,
                   "heading_min_size": 99, "skip_re": [r"^\d{1,3}$"]},
    },
    {
        "slug": "shuangpan-120-buxu",
        "source": "stories/湖南-不虚：双盘120分钟心得总结.docx",
        "title": "雙盤 120 分鐘心得總結",
        "orig_title": "双盘120分钟心得总结",
        "author": "湖南－不虛師兄",
        "date": "2016-08-27",
        "category": "雙盤打坐",
        "summary": "從時間選擇、身體準備、情緒、環境到關鍵技巧與突破過程，七個面向完整拆解如何練到雙盤 120 分鐘。",
        "keywords": "雙盤120分鐘,打坐突破,熬腿,雙盤技巧,不虛,坐禪",
    },
    {
        "slug": "geren-shuangpan-zongjie",
        "source": "stories/个人双盘总结.docx",
        "title": "個人雙盤總結",
        "orig_title": "个人双盘总结",
        "author": "匿名師兄",
        "date": "2020-02-24",
        "category": "雙盤打坐",
        "summary": "一年多累積兩萬分鐘雙盤、最長單座四小時的實修紀錄，兼談跑步、大禮拜與「神要清明」的心法。",
        "keywords": "雙盤總結,四小時雙盤,羊台山,大禮拜,心印經,神清明",
    },
    {
        "slug": "xiaoxi-shuangpan-riji",
        "source": "stories/小夕師兄 2017.pdf",
        "title": "From 30 to 180 分鐘：小夕雙盤日記",
        "orig_title": "From 30 to 180 分钟——小夕双盘日记",
        "author": "小夕（資料整理：話頭禪師兄）",
        "date": "2013–2016",
        "category": "雙盤打坐",
        "summary": "以日記形式完整記述從雙盤十分鐘到三小時的四年歷程，包含拉筋、大禮拜、痛坎、身心變化與三百次三小時雙盤的紀錄。",
        "keywords": "小夕,雙盤日記,拉筋,雙盤三小時,痛坎,大禮拜,話頭禪",
        "layout": {"indent_x": 60, "body_x": 36, "right": 566,
                   "heading_min_size": 15.5, "skip_pages": [1, 2, 3, 4],
                   "skip_re": [r"^[IVX]+$", r"^\d{1,3}$"],
                   # 書名頁的版心較窄
                   "page_overrides": {0: {"indent_x": 131, "body_x": 107, "right": 488}}},
    },
    # ---------------- 磕大頭 ----------------
    {
        "slug": "shanhui-bairi-30wan",
        "source": "stories/Tai群善慧师兄磕大头百日期30万圆满分享.pdf",
        "title": "磕大頭百日期 30 萬圓滿分享",
        "orig_title": "Tai群善慧师兄磕大头百日期30万圆满分享",
        "author": "Tai 群善慧師兄",
        "date": "",
        "category": "磕大頭（大禮拜）",
        "summary": "百日不間斷、日均 3000 個大禮拜共 30 萬圓滿的十問十答：身心變化、季節與飲食的坑、時間安排與給普通人的建議。",
        "keywords": "磕大頭,百日期,30萬大禮拜,善慧師兄,大禮拜心得,五體投地",
        "layout": {"indent_x": None, "body_x": 90, "right": 505,
                   "heading_min_size": 14, "skip_re": [r"^\d{1,3}$"]},
    },
    {
        "slug": "tianxi-kedatou",
        "source": "stories/【Tai人说】磕大头经历分享-天禧师兄.docx",
        "title": "【Tai 人說】磕大頭經歷分享",
        "orig_title": "【Tai人说】磕大头经历分享",
        "author": "天禧師兄",
        "date": "2018",
        "category": "磕大頭（大禮拜）",
        "summary": "三年磕大頭二十多萬，從剖腹產二胎後身體差到極點，到脫髮停止、脾氣轉穩、家人跟著一起磕大頭的完整轉變。",
        "keywords": "磕大頭,天禧,剖腹產,脫髮,身體變化,打坐,Tai人說",
    },
    {
        "slug": "wuganzi-kedatou",
        "source": "stories/【Tai人说】磕大头经历第二篇-握杆子师兄.docx",
        "title": "【Tai 人說】磕大頭經歷第二篇",
        "orig_title": "【Tai人说】磕大头经历第二篇",
        "author": "握杆子師兄",
        "date": "2018",
        "category": "磕大頭（大禮拜）",
        "summary": "第一次共修十萬大頭：如何把嚇人的目標拆解成每天三組、如何在最累的時候戰勝退轉的念頭。",
        "keywords": "磕大頭,十萬大頭,共修,握杆子,發心,忏悔",
    },
    {
        "slug": "kedatou-jieba-ganwu",
        "source": "stories/磕大头-磕掉结痂感悟.txt",
        "title": "磕大頭：磕掉結痂感悟",
        "orig_title": "磕大头-磕掉结痂感悟",
        "author": "匿名師兄",
        "date": "",
        "category": "磕大頭（大禮拜）",
        "summary": "陳舊性肺結核結痂，以每天 108 個大禮拜配合誦《地藏經》忏悔，複查影像已與正常人無異的親身紀錄。",
        "keywords": "磕大頭,肺結核,結痂,地藏經,忏悔,復查",
    },
    {
        "slug": "huatouchan-kedatou-xiaojie",
        "source": "stories/Tai式磕大头小结(第1版)-话头禅.pdf",
        "title": "Tai 式磕大頭小結（第 1 版）",
        "orig_title": "Tai式磕大头小结（第1版）",
        "author": "話頭禪師兄",
        "date": "2019-06-01",
        "category": "磕大頭（大禮拜）",
        "summary": "工具、方法、計劃、行動、心理、分析六篇，以心率／腰圍／體重／汗味等十項指標追蹤半年每天 555 個大禮拜的完整實驗紀錄。",
        "keywords": "Tai式磕大頭,五體投地,瑜伽墊,555個,每月修行計劃,排毒,話頭禪",
        "layout": {"indent_x": 57, "body_x": 36, "right": 560,
                   "heading_min_size": 99, "skip_pages": [0],
                   "skip_re": [r"^\d{1,3}$"],
                   "heading_re": [r"^[一二三四五六七]、.{2,10}篇$", r"^附录\d[：:].+$"],
                   "heading3_re": [r"^\d、[^，。：；！？]{2,24}$"],
                   "tables": True},
    },
    {
        "slug": "dalibai-wenyang",
        "source": "stories/大礼拜后必须温养.docx",
        "title": "大禮拜後必須溫養",
        "orig_title": "大礼拜后必须温养",
        "author": "匿名師兄",
        "date": "",
        "category": "磕大頭（大禮拜）",
        "summary": "長時間大禮拜後馬上洗澡導致縮筋兩年的親身教訓，以及「溫養關」的五項具體建議。",
        "keywords": "大禮拜,溫養,溫養關,寒濕,地藏七,打七",
    },
    # ---------------- 呼吸法 ----------------
    {
        "slug": "fushi-huxi",
        "source": "stories/腹式呼吸-(文)黄芪，(整理)念离.doc",
        "title": "腹式呼吸法",
        "orig_title": "腹式呼吸",
        "author": "（文）黃芪、（整理）念離",
        "date": "",
        "category": "呼吸法",
        "summary": "從橫膈膜的定位與操作，到腹式呼吸成功的三個標誌，再到身體基礎物質的產生與運行。",
        "keywords": "腹式呼吸,橫膈膜,胎息,肺葉底部,黃芪,念離",
    },
    # ---------------- 經典研習 ----------------
    {
        "slug": "zhancha-zuochan-xinde",
        "source": "stories/话头禅：学习《占察善恶业报经》与再读《坐禅》之心得.pdf",
        "title": "學習《占察善惡業報經》與再讀《坐禪》之心得",
        "orig_title": "学习《占察善恶业报经》与再读《坐禅》之心得",
        "author": "話頭禪師兄",
        "date": "",
        "category": "經典研習",
        "summary": "以《占察善惡業報經》的一心、勇猛心、深心，重新讀懂《坐禪》裡「一有空就念佛」與「滅文字妄想」的真義。",
        "keywords": "占察善惡業報經,占察輪,坐禪,一心,勇猛心,深心,念佛,話頭禪",
        "layout": {"indent_x": 78, "body_x": 57, "right": 538,
                   "heading_min_size": 17, "skip_re": [r"^\d{1,3}$"],
                   "quote_fonts": ["STKaiti"]},
    },
    # ---------------- 綜合實修 ----------------
    {
        "slug": "anhui-3000-dizangjing",
        "source": "stories/安徽師兄 2023.pdf",
        "title": "歷時 5 年多完成 3000 遍地藏經",
        "orig_title": "实修故事：历时5年多完成3000遍地藏经",
        "author": "Tai 群內安徽師兄",
        "date": "2023",
        "category": "綜合實修",
        "summary": "上篇助癌症丈夫治癒、中篇九年 Tai 實修經歷、下篇小編互動問答——半年發願 1000 遍《地藏經》的長文分享。",
        "keywords": "地藏經,3000遍,肺癌,發願,放生,安徽師兄,實修故事",
        "layout": {"indent_x": None, "body_x": 90, "right": 505,
                   "heading_min_size": 13.2, "skip_re": [r"^\d{1,3}$"]},
    },
    {
        "slug": "huatouchan-weile-shuangpan",
        "source": "stories/話頭禪師兄 2016.pdf",
        "title": "為了能雙盤而奮鬥的那些日子裡",
        "orig_title": "为了能双盘而奋斗的那些日子里",
        "author": "話頭禪師兄",
        "date": "2016",
        "category": "雙盤打坐",
        "summary": "從蝴蝶式、單盤、單盤壓腿到拉筋，一年的姿勢實驗紀錄，附完整的每月修行計劃表掃描。",
        "keywords": "雙盤,單盤壓腿,蝴蝶式,拉筋,蓮花坐,降魔坐,每月修行計劃,話頭禪",
        "layout": {"indent_x": 57, "body_x": 36, "right": 560,
                   "heading_min_size": 20,
                   "heading3_re": [r"^\d{4}/\d{2}/\d{2}(\s*[～~-]\s*\d{4}/\d{2}/\d{2})?$"],
                   "skip_re": [r"^\d{1,3}$"]},
    },
]

BY_SLUG = {d["slug"]: d for d in DOCS}

CATEGORY_ORDER = ["雙盤打坐", "磕大頭（大禮拜）", "呼吸法", "經典研習", "綜合實修"]
