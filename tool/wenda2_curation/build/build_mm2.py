# -*- coding: utf-8 -*-
import os

# 以腳本位置推算路徑：build/ -> wenda2_curation/ -> repo root
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
CUR_DIR = os.path.dirname(BUILD_DIR)
out = os.path.join(CUR_DIR, 'data')          # data/ (ch01..21.json, curation, stats)
REPO = os.path.dirname(CUR_DIR)              # = tool/
REPO = os.path.dirname(REPO)                  # repo root
os.chdir(REPO)
data_js = open(os.path.join(BUILD_DIR, 'mm_data.js'), encoding='utf-8').read()

NAV = '''    <nav class="navbar" id="navbar">
        <div class="nav-container">
            <a href="index.html" class="nav-logo">
                <span class="logo-name">TaiGuangLin</span>
                <span class="logo-sub">次世代終極佛法</span>
            </a>
            <div class="nav-menu" id="nav-menu">
                <a href="index.html" class="nav-link">首頁</a>
                <a href="index.html#about" class="nav-link">禪師</a>
                <a href="index.html#start" class="nav-link">入門路徑</a>
                <a href="index.html#books" class="nav-link">著作</a>
                <a href="wenda2.html" class="nav-link">問答錄 2</a>
                <a href="stories.html" class="nav-link">實修故事</a>
                <div class="nav-dropdown" id="nav-dropdown">
                    <a href="#" class="nav-link nav-dropdown-toggle" id="dropdown-toggle">圖解 ▾</a>
                    <div class="nav-dropdown-menu">
                        <a href="infographic.html" class="nav-dropdown-item">名詞圖解</a>
                        <a href="mindmap.html" class="nav-dropdown-item">名詞關聯心智圖</a>
                        <a href="books_knowledge.html" class="nav-dropdown-item">九書重點知識</a>
                        <a href="wenda2_knowledge.html" class="nav-dropdown-item">問答錄2 重點知識</a>
                        <a href="wenda2_mindmap.html" class="nav-dropdown-item active" aria-current="page">問答錄2 名詞心智圖</a>
                        <a href="wenda2_knowledge_full.html" class="nav-dropdown-item">問答錄2 知識庫全檔</a>
                    </div>
                </div>
                <a href="index.html#downloads" class="nav-link nav-cta" data-download-trigger>下載資料</a>
            </div>
            <button class="hamburger" id="hamburger" aria-label="開啟選單" aria-expanded="false">
                <span></span><span></span><span></span>
            </button>
        </div>
    </nav>
    <div class="site-menu-veil" id="site-menu-veil"></div>'''

page = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>坐禪之問答錄2 名詞心智圖｜問答錄2 高頻名詞總覽｜TaiGuangLin 禪師</title>
    <meta name="description" content="《坐禪之問答錄2》全書 21 章、9,231 個 Tai 師父回答的關鍵名詞心智圖：自性、阿賴耶識、妄想、分別心、執著、習氣、業、功德、迴向、加持、菩提心、持戒、打坐、雙盤、腹式呼吸、禪定、思情、唸佛、極樂世界、往生、陽神等 57 個名詞的關聯與原文引句。">
    <meta name="keywords" content="坐禪之問答錄2,問答錄2,心智圖,名詞分析,自性,阿賴耶識,妄想,分別心,執著,羯磨,功德,迴向,加持,菩提心,持戒,禪定,思情,唸佛,極樂世界,陽神,TaiGuangLin">
    <meta name="author" content="TaiGuangLin">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="坐禪之問答錄2 名詞心智圖｜TaiGuangLin 禪師">
    <meta property="og:description" content="把《坐禪之問答錄2》9,231 個回答裡的高頻名詞，串成一張可互動的關聯圖">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://taiguanglin.info/wenda2_mindmap.html">
    <meta property="og:image" content="https://taiguanglin.info/images/taiguanglin.png">
    <link rel="canonical" href="https://taiguanglin.info/wenda2_mindmap.html">
    <link rel="icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="shortcut icon" type="image/x-icon" href="images/favicon.ico">
    <link rel="stylesheet" href="style.css">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<script src="/lang-switch.js" defer></script>
</head>
<body>
''' + NAV + '''

    <!-- Hero 區塊 -->
    <section class="page-hero">
        <div class="container">
            <nav class="crumbs" aria-label="位置">
                <a href="index.html">首頁</a><span class="crumbs-sep">/</span><a href="wenda2.html">坐禪之問答錄2</a><span class="crumbs-sep">/</span>
                <span aria-current="page">名詞心智圖</span>
            </nav>
            <span class="kicker">WENDA2 TERM MAP</span>
            <h1 class="display">坐禪之問答錄2 名詞心智圖</h1>
            <p class="lede">《坐禪之問答錄2》全部 21 章、9,231 個 Tai 師父回答，用程式逐字統計選出 57 個高頻名詞，整理成 11 條主幹的可互動關聯圖：自性與意識、果位與聖眾、世界與輪迴、羯磨（業）、功德與福報、發心與戒行、淨土與往生、入門功課、禪定次第、唪誦法門、境界與現象。每個名詞都附定義、要點、逐字引文與電子書原文連結。</p>
        </div>
    </section>
    <!-- 統計 -->
    <section class="section" style="padding-top: var(--spacing-lg); padding-bottom: 0;">
        <div class="container">
            <div class="note-ai" style="margin-bottom: 20px;">
                <span>本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。</span>
            </div>
            <div class="mm-stats">
                <div class="mm-stat">
                    <span class="mm-stat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2.6"/><circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="6" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M6.8 7.3l3.4 3.2M17.2 7.3l-3.4 3.2M6.8 16.7l3.4-3.2M17.2 16.7l-3.4-3.2"/></svg>
                    </span>
                    <strong>57</strong>
                    <span>個名詞節點</span>
                </div>
                <div class="mm-stat">
                    <span class="mm-stat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v16M4 8l8-4 8 4M4 8a2.8 2.8 0 005.6 0M9.2 8a2.8 2.8 0 005.6 0M14.8 8a2.8 2.8 0 005.6 0"/></svg>
                    </span>
                    <strong>11</strong>
                    <span>條主幹</span>
                </div>
                <div class="mm-stat">
                    <span class="mm-stat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 11-9-9"/><path d="M21 3l-9 9"/><path d="M15 3h6v6"/></svg>
                    </span>
                    <strong>9,231</strong>
                    <span>個師父回答</span>
                </div>
                <div class="mm-stat">
                    <span class="mm-stat-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></svg>
                    </span>
                    <strong>21</strong>
                    <span>章（2024.02–2026.03）</span>
                </div>
            </div>
        </div>
    </section>

    <!-- 怎麼讀這張圖 -->
    <section class="section bg-light">
        <div class="container">
            <h2 class="section-title mm-section-title">
                <span class="mm-section-icon" aria-hidden="true">
                    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="18" width="8" height="16" rx="2" fill="currentColor" opacity=".35"/><rect x="16" y="10" width="8" height="24" rx="2" fill="currentColor" opacity=".7"/><rect x="27" y="6" width="8" height="28" rx="2" fill="currentColor"/><circle cx="9" cy="14" r="2.5" fill="currentColor"/><circle cx="20" cy="6" r="2.5" fill="currentColor"/><circle cx="31" cy="3" r="2.5" fill="currentColor"/></svg>
                </span>
                怎麼讀這張圖
            </h2>
            <p class="mm-lead">三個使用說明，讓這張圖變成讀《坐禪之問答錄2》的地圖，而不是另一篇摘要。</p>
            <div class="mm-axiom-grid" id="mm-axioms"></div>
        </div>
    </section>

    <!-- 心智圖 -->
    <section class="section">
        <div class="container">
            <h2 class="section-title mm-section-title">
                <span class="mm-section-icon" aria-hidden="true">
                    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 20l-11-9M20 20l11-9M20 20l-11 9M20 20l11 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".6"/><circle cx="20" cy="20" r="4.6" fill="currentColor"/><circle cx="9" cy="11" r="3.4" fill="currentColor" opacity=".55"/><circle cx="31" cy="11" r="3.4" fill="currentColor" opacity=".55"/><circle cx="9" cy="29" r="3.4" fill="currentColor" opacity=".55"/><circle cx="31" cy="29" r="3.4" fill="currentColor" opacity=".55"/></svg>
                </span>
                問答錄2 名詞關聯圖
            </h2>
            <p class="mm-lead">點選圖中任一名詞，可展開它的釋義、依回答整理的書中要點、逐字引文、出現次數統計與原文連結，以及跨主幹的關聯名詞（虛線標示）。手機請左右滑動圖面。</p>

            <div class="mm-chips" id="mm-chips"></div>

            <div class="mm-canvas-wrap">
                <div class="mm-canvas-inner" id="mm-canvas"></div>
            </div>
            <p class="mm-hint"> 中心為《坐禪之問答錄2》全書；右側五條主幹為義理與世界，左側六條主幹為實修與生活 。</p>

            <div class="mm-detail" id="mm-detail"></div>
        </div>
    </section>

    <!-- 名詞熱度 -->
    <section class="section bg-light">
        <div class="container">
            <h2 class="section-title mm-section-title">
                <span class="mm-section-icon" aria-hidden="true">
                    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 7v26h24" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><rect x="14" y="20" width="6" height="9" rx="1.6" fill="currentColor" opacity=".5"/><rect x="23" y="14" width="6" height="15" rx="1.6" fill="currentColor" opacity=".8"/><circle cx="26" cy="9" r="3" fill="currentColor"/></svg>
                </span>
                名詞熱度與章節分布
            </h2>
            <p class="mm-lead">12 個代表名詞在《坐禪之問答錄2》各篇章的出現次數（程式逐字統計）：義理名詞集中在第 01–04 章，身體功課集中在第 08–10 章，月度問答則把佛菩薩、迴向、極樂世界一再拉回來。</p>
            <div class="mm-chart" id="mm-chart"></div>
        </div>
    </section>

    <!-- 延伸 -->
    <section class="section">
        <div class="container">
            <h2 class="section-title mm-section-title">
                <span class="mm-section-icon" aria-hidden="true">
                    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 6l3.5 7.5L31 14.5l-5.5 5.5L26.8 28 20 24.3 13.2 28l1.3-8L9 14.5l7.5-1z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" fill="none"/><circle cx="20" cy="20" r="15" stroke="currentColor" stroke-width="1.2" opacity=".4" fill="none"/></svg>
                </span>
                繼續讀
            </h2>
            <div class="mm-more-grid">
                <a class="mm-more-card" href="wenda2_knowledge.html">
                    <strong>坐禪之問答錄2 重點知識</strong>
                    <span>按 21 章整理 Tai 師父回答的重點：章導讀、書中要點、逐字引句與原文連結。</span>
                </a>
                <a class="mm-more-card" href="wenda2_knowledge_full.html">
                    <strong>問答錄2 知識庫全檔</strong>
                    <span>名詞全檔、出現次數統計總表與 21 章全部小節引句的完整參考頁。</span>
                </a>
                <a class="mm-more-card" href="wenda2.html">
                    <strong>問答錄2 主題目錄</strong>
                    <span>前 12 章主題選讀，每一章的介紹與代表問答。</span>
                </a>
                <a class="mm-more-card" href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">
                    <strong>問答錄2 完整電子書</strong>
                    <span>9,231 個回答全文檢索；本頁所有引文都連回這裡的原文位置。</span>
                </a>
                <a class="mm-more-card" href="mindmap.html">
                    <strong>名詞關聯心智圖（九本著作）</strong>
                    <span>想看《坐禪1》《坐禪2》與六部講經的全套名詞結構，請用這張總圖。</span>
                </a>
            </div>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <div class="footer-top">
                <div class="footer-brand">
                    <div class="logo-name">TaiGuangLin</div>
                    <p>次世代終極版佛法</p>
                    <p>用現代通俗易懂的語言，傳承純正佛法智慧。</p>
                </div>
                <div class="footer-col">
                    <h4>著作與電子書</h4>
                    <ul>
                        <li><a href="index.html#books">全部著作</a></li>
                        <li><a href="ebook/index_trad.html" target="_blank" rel="noopener noreferrer">坐禪系列電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>問答錄2</h4>
                    <ul>
                        <li><a href="wenda2.html">主題目錄（12 章）</a></li>
                        <li><a href="wenda2_ebook/index_trad.html" target="_blank" rel="noopener noreferrer">完整電子書</a></li>
                    </ul>
                </div>
                <div class="footer-col">
                    <h4>更多資源</h4>
                    <ul>
                        <li><a href="infographic.html">名詞圖解</a></li>
                        <li><a href="mindmap.html">名詞關聯心智圖</a></li>
                        <li><a href="wenda2_knowledge.html">問答錄2 重點知識</a></li>
                        <li><a href="wenda2_mindmap.html">問答錄2 名詞心智圖</a></li>
                        <li><a href="wenda2_knowledge_full.html">問答錄2 知識庫全檔</a></li>
                        <li><a href="stories.html">實修故事</a></li>
                        <li><a href="index.html#downloads">資料下載</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>歡迎分享給更多人結法緣</p>
                <p>願一切眾生離苦得樂，早證菩提</p>
            </div>
        </div>
    </footer>

    <script src="shared.js" defer></script>
    <script>
(function () {
'use strict';
''' + data_js + '''
    </script>
</body>
</html>
'''

with open('wenda2_mindmap.html', 'w', encoding='utf-8') as f:
    f.write(page)
print('wenda2_mindmap.html written:', len(page), 'chars')
