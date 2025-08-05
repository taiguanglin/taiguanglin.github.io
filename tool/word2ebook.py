import os
import sys
import shutil
import re
import argparse
from docx import Document
from docx.oxml.ns import qn
from slugify import slugify
from opencc import OpenCC

# ========== 粉紅色主題 CSS & 平滑滾動 JS ==========
CSS_CONTENT = """\
body { font-family: 'Helvetica', sans-serif; margin: 40px auto; max-width: 800px; line-height: 1.6; background: #fff0f5; color: #333; transition: 0.3s; }

h1 { color: #e75480; border-bottom: 2px solid #f8c8dc; padding-bottom: 10px; }
h2 { color: #d44d75; margin-top: 40px; }
h3 { color: #b73c65; margin-top: 25px; }
p { margin: 15px 0; }
img { max-width: 100%; display: block; margin: 20px auto; }
a { color: #e75480; text-decoration: none; }
a:hover { text-decoration: underline; color: #ff69b4; }
hr { border: none; height: 2px; background: linear-gradient(to right, #f8c8dc, #e75480, #f8c8dc); margin: 30px 0; border-radius: 1px; }
.nav { margin-bottom: 20px; }
.nav-footer { display: flex; justify-content: space-between; margin-top: 50px; }
.toc { margin: 20px 0; }
.toc ul { list-style: disc; padding-left: 1.5em; }
.toc ul ul { list-style: circle; padding-left: 2em; }

/* 問答樣式 */
.question {
    padding: 15px;
    background: #fff;
    border-radius: 8px;
    border-left: 4px solid #e75480;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(231, 84, 128, 0.1);
}

.question-meta {
    margin-bottom: 10px;
    line-height: 1.6;
}

.question-meta .questioner {
    margin-right: 10px;
}

.questioner {
    font-weight: 600;
    color: #e75480;
    font-size: 16px;
}

.question-time {
    background: #f8c8dc;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 14px;
    color: #b73c65;
    font-weight: 500;
}

.question-text {
    color: #333;
    line-height: 1.6;
    margin: 0;
}

.answer {
    padding: 15px;
    background: linear-gradient(135deg, #fff8f0 0%, #ffffff 100%);
    border-radius: 8px;
    border-left: 4px solid #ff69b4;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(255, 105, 180, 0.1);
}

.answer-meta {
    margin-bottom: 10px;
    line-height: 1.6;
}

.answer-meta .answerer {
    margin-right: 10px;
}

.answerer {
    font-weight: 700;
    color: #ff69b4;
    font-size: 16px;
}

.answer-text {
    color: #333;
    line-height: 1.7;
    margin: 0;
    font-weight: 500;
}

/* 暗色模式 */
body.dark-mode { background: #3b1c32; color: #fddde6; }
body.dark-mode a { color: #ff91af; }
body.dark-mode hr { background: linear-gradient(to right, #5a2d49, #ff91af, #5a2d49); }
body.dark-mode .question { background: #4a2c3a; border-left-color: #ff91af; box-shadow: 0 2px 8px rgba(255, 145, 175, 0.1); }
body.dark-mode .question-text { color: #fddde6; }
body.dark-mode .questioner { color: #ff91af; }
body.dark-mode .question-time { background: #5a2d49; color: #ff91af; }
body.dark-mode .answer { background: linear-gradient(135deg, #4a2c3a 0%, #3b1c32 100%); border-left-color: #ff69b4; }
body.dark-mode .answer-text { color: #fddde6; }
body.dark-mode .answerer { color: #ff69b4; }

/* 夜間模式按鈕已移至閱讀設置中 */
.back-to-top { text-align: right; margin: 20px 0; }
.back-to-top a { font-size: 0.9em; color: #d44d75; }
.back-to-top a:hover { color: #ff69b4; }
.lang-switch { text-align: right; margin-bottom: 10px; }
.lang-switch a { font-size: 0.9em; margin: 0 5px; }

/* ============ UX 增強功能 ============ */

/* 閱讀工具欄 */
.reading-toolbar {
    position: fixed;
    top: 70px;
    right: 20px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    transition: transform 0.3s ease, opacity 0.3s ease;
}

.reading-toolbar.hidden {
    transform: translateX(100%);
    opacity: 0;
}

.toolbar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f0f0f0;
    font-size: 14px;
    font-weight: 600;
    color: #e75480;
}

.toolbar-section {
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f0f0f0;
}

.toolbar-section:last-child {
    margin-bottom: 0;
    border-bottom: none;
}

.toolbar-label {
    font-size: 12px;
    color: #666;
    margin-bottom: 5px;
    font-weight: 500;
}

.toolbar-controls {
    display: flex;
    gap: 5px;
    align-items: center;
}

.ctrl-btn {
    padding: 6px 10px;
    border: 1px solid #ddd;
    background: #fff;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s ease;
    min-width: 30px;
    text-align: center;
}

.ctrl-btn:hover {
    background: #f5f5f5;
    border-color: #ccc;
}

.ctrl-btn.active {
    background: #e75480;
    color: white;
    border-color: #e75480;
}

/* 搜索功能已移除 */

/* 閱讀進度條 */
.reading-progress {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: rgba(231, 84, 128, 0.2);
    z-index: 9999;
}

.reading-progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #e75480, #ff69b4);
    width: 0%;
    transition: width 0.1s ease;
}

/* 浮動目錄 */
.floating-toc {
    position: fixed;
    left: -250px;
    top: 50%;
    transform: translateY(-50%);
    width: 240px;
    max-height: 70vh;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    z-index: 1000;
    transition: left 0.3s ease;
    overflow-y: auto;
}

.floating-toc.visible {
    left: 20px;
}

.floating-toc-header {
    padding: 15px;
    border-bottom: 1px solid #f0f0f0;
    font-weight: 600;
    color: #e75480;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    z-index: 10;
    border-radius: 12px 12px 0 0;
}

.floating-toc-list {
    padding: 10px;
}

.floating-toc-item {
    padding: 8px 12px;
    margin: 2px 0;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 13px;
    border-left: 3px solid transparent;
}

.floating-toc-item.level-h3 {
    padding-left: 24px;
    font-size: 12px;
    color: #666;
}

.floating-toc-item.level-h4 {
    padding-left: 36px;
    font-size: 11px;
    color: #888;
}

.floating-toc-item:hover {
    background: rgba(231, 84, 128, 0.1);
}

.floating-toc-item.active {
    background: rgba(231, 84, 128, 0.2);
    border-left-color: #e75480;
    font-weight: 600;
    color: #e75480;
    border-radius: 4px;
    transform: translateX(2px);
    box-shadow: 0 1px 4px rgba(231, 84, 128, 0.3);
}

/* 浮動目錄標籤頁 */
.floating-toc-tabs {
    display: flex;
    border-bottom: 1px solid #f0f0f0;
}

.floating-toc-tab {
    flex: 1;
    padding: 10px;
    text-align: center;
    cursor: pointer;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    transition: all 0.2s ease;
    font-size: 12px;
}

.floating-toc-tab.active {
    color: #e75480;
    border-bottom-color: #e75480;
    font-weight: 600;
}

.floating-toc-tab:hover {
    background: rgba(231, 84, 128, 0.05);
}

/* 書籤樣式 */
.bookmark-item {
    padding: 10px 12px;
    margin: 4px 0;
    border-radius: 6px;
    border: 1px solid #f0f0f0;
    background: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
}

.bookmark-item:hover {
    background: rgba(231, 84, 128, 0.05);
    border-color: #e75480;
}

.qa-pair-bookmark {
    border-left: 3px solid #ff69b4;
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.08) 0%, rgba(255, 255, 255, 0.5) 100%);
}

.qa-pair-bookmark:hover {
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.12) 0%, rgba(231, 84, 128, 0.05) 100%);
}

.bookmark-meta {
    display: flex;
    align-items: center;
    margin-bottom: 5px;
    font-size: 11px;
    color: #666;
    gap: 6px;
}

.bookmark-type {
    font-size: 12px;
    flex-shrink: 0;
}

.bookmark-questioner {
    font-weight: 600;
    color: #e75480;
    flex: 1;
}

.bookmark-time {
    font-size: 10px;
    flex-shrink: 0;
}

.bookmark-preview {
    font-size: 12px;
    color: #333;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}

.bookmark-delete {
    position: absolute;
    top: 5px;
    right: 5px;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    cursor: pointer;
    font-size: 10px;
    color: #999;
    opacity: 0;
    transition: opacity 0.2s ease;
}

.bookmark-item:hover .bookmark-delete {
    opacity: 1;
}

.bookmark-delete:hover {
    background: #ff4757;
    color: white;
}

.bookmarks-empty {
    text-align: center;
    padding: 20px;
    color: #999;
    font-size: 12px;
}

/* 操作按鈕組 - 可展開菜單 */
.action-buttons {
    position: fixed;
    bottom: 30px;
    right: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    z-index: 1000;
}

.action-menu {
    position: relative;
}

.action-btn {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    border: none;
    background: #ff69b4;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    box-shadow: 0 4px 15px rgba(255, 105, 180, 0.3);
    transition: all 0.3s ease;
}

.action-btn:hover {
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 6px 20px rgba(255, 105, 180, 0.4);
}

.action-btn.menu-btn {
    background: #ff69b4;
    z-index: 1001;
}

.action-btn.menu-btn.expanded {
    transform: rotate(90deg);
    background: #e75480;
}

.action-menu-items {
    position: absolute;
    bottom: 60px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    gap: 10px;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    pointer-events: none;
}

.action-menu.expanded .action-menu-items {
    opacity: 1;
    visibility: visible;
    pointer-events: all;
}

.action-menu-items .action-btn {
    width: 45px;
    height: 45px;
    font-size: 16px;
    background: #ff69b4;
    transform: scale(0.8);
}

.action-menu.expanded .action-menu-items .action-btn {
    transform: scale(1);
}

.action-menu-items .action-btn:hover {
    background: #e75480;
    transform: scale(1.05);
}

/* 暗色模式適配 */
body.dark-mode .action-btn {
    background: #ff69b4;
    box-shadow: 0 4px 15px rgba(255, 105, 180, 0.4);
}

body.dark-mode .action-btn:hover {
    background: #e75480;
    box-shadow: 0 6px 20px rgba(255, 105, 180, 0.5);
}

body.dark-mode .action-btn.menu-btn.expanded {
    background: #e75480;
}

body.dark-mode .action-menu-items .action-btn {
    background: #ff69b4;
}

body.dark-mode .action-menu-items .action-btn:hover {
    background: #e75480;
}

/* 問答互動功能 */
.qa-actions {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    gap: 8px;
    opacity: 0;
    transition: opacity 0.2s ease;
}

.question:hover .qa-actions,
.answer:hover .qa-actions {
    opacity: 1;
}

.qa-btn {
    width: 28px;
    height: 28px;
    border: none;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    color: #666;
    transition: all 0.2s ease;
}

.qa-btn:hover {
    background: #e75480;
    color: white;
    transform: scale(1.1);
}

/* 通知消息 */
.toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #333;
    color: white;
    padding: 12px 20px;
    border-radius: 25px;
    font-size: 14px;
    z-index: 9999;
    transition: transform 0.3s ease;
}

.toast.show {
    transform: translateX(-50%) translateY(0);
}

/* 暗色模式適配 */
body.dark-mode .reading-toolbar,
body.dark-mode .floating-toc {
    background: rgba(59, 28, 50, 0.95);
    border-color: #5a2d49;
}

body.dark-mode .floating-toc-header {
    background: rgba(59, 28, 50, 0.95);
    border-bottom: 1px solid #5a2d49;
}

body.dark-mode .ctrl-btn,
body.dark-mode .qa-btn {
    background: rgba(90, 45, 73, 0.9);
    color: #fddde6;
    border-color: #5a2d49;
}

body.dark-mode .ctrl-btn:hover,
body.dark-mode .qa-btn:hover {
    background: #ff69b4;
}

body.dark-mode .ctrl-btn.active {
    background: #ff69b4;
    color: #fff;
    border-color: #ff69b4;
    box-shadow: 0 0 8px rgba(255, 105, 180, 0.5);
}

body.dark-mode .floating-toc-item {
    color: #fddde6;
}

body.dark-mode .floating-toc-item.level-h3 {
    color: #ff91af;
}

body.dark-mode .floating-toc-item.level-h4 {
    color: #d44d75;
}

body.dark-mode .floating-toc-item:hover {
    background: rgba(255, 105, 180, 0.2);
}

body.dark-mode .floating-toc-item.active {
    background: rgba(255, 105, 180, 0.25);
    border-left-color: #ff69b4;
    color: #ff69b4;
    box-shadow: 0 1px 4px rgba(255, 105, 180, 0.4);
}

/* 書籤視覺標識 */
.bookmarked {
    position: relative;
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.1) 0%, rgba(255, 182, 193, 0.1) 100%);
    border-left: 4px solid #ff69b4;
    box-shadow: 0 2px 8px rgba(255, 105, 180, 0.2);
}

.bookmark-indicator {
    position: absolute;
    bottom: 8px;
    right: 8px;
    font-size: 16px;
    opacity: 0.8;
    z-index: 10;
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
}

.bookmark-indicator:hover {
    opacity: 1;
    transform: scale(1.1);
}

body.dark-mode .bookmarked {
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.15) 0%, rgba(139, 69, 19, 0.1) 100%);
    border-left-color: #ff69b4;
    box-shadow: 0 2px 8px rgba(255, 105, 180, 0.3);
}

/* 書籤分組樣式 */
.bookmark-chapter {
    margin: 12px 0 8px 0;
    padding: 8px 12px;
    background: rgba(231, 84, 128, 0.1);
    border-radius: 6px;
    border-left: 4px solid #e75480;
}

.bookmark-chapter-title {
    font-weight: 600;
    color: #e75480;
    font-size: 14px;
    margin: 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.bookmark-chapter-toggle {
    font-size: 12px;
    transition: transform 0.2s ease;
}

.bookmark-chapter.collapsed .bookmark-chapter-toggle {
    transform: rotate(-90deg);
}

.bookmark-chapter-items {
    margin-top: 8px;
    transition: max-height 0.2s ease;
    overflow: hidden;
}

.bookmark-chapter.collapsed .bookmark-chapter-items {
    max-height: 0;
    margin-top: 0;
}

.bookmark-chapter-count {
    font-size: 12px;
    background: rgba(231, 84, 128, 0.2);
    padding: 2px 6px;
    border-radius: 10px;
    color: #e75480;
}

body.dark-mode .bookmark-chapter {
    background: rgba(255, 105, 180, 0.15);
    border-left-color: #ff69b4;
}

body.dark-mode .bookmark-chapter-title {
    color: #ff69b4;
}

body.dark-mode .bookmark-chapter-count {
    background: rgba(255, 105, 180, 0.3);
    color: #ff69b4;
}

/* 夜間模式下標籤頁樣式 */
body.dark-mode .floating-toc-tab {
    color: #fddde6;
    border-bottom: 1px solid #5a2d49;
}

body.dark-mode .floating-toc-tab.active {
    color: #ff69b4;
    border-bottom-color: #ff69b4;
}

body.dark-mode .floating-toc-tab:hover {
    background: rgba(255, 105, 180, 0.1);
}

/* 當前章節信息樣式 */
.current-chapter-info {
    padding: 8px 12px;
    margin-bottom: 12px;
    background: rgba(231, 84, 128, 0.1);
    border-radius: 6px;
    border-left: 4px solid #e75480;
}

.chapter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0;
}

.current-chapter-title {
    font-size: 14px;
    font-weight: 600;
    color: #e75480;
    flex: 1;
}

.current-chapter-count {
    font-size: 12px;
    color: #666;
}

.bookmark-clear-icon {
    background: none;
    border: none;
    font-size: 16px;
    cursor: pointer;
    opacity: 0;
    transition: all 0.3s ease;
    padding: 3px;
    border-radius: 3px;
    position: relative;
}

.current-chapter-info:hover .bookmark-clear-icon {
    opacity: 0.7;
}

.bookmark-clear-icon:hover {
    opacity: 1 !important;
    background: rgba(255, 71, 87, 0.1);
    transform: scale(1.05);
}

.bookmark-clear-icon:hover::after {
    content: '清空書籤';
    position: absolute;
    top: -30px;
    right: 0;
    background: #333;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    white-space: nowrap;
    z-index: 1000;
}

.bookmark-clear-icon:active {
    transform: scale(0.95);
}

body.dark-mode .current-chapter-info {
    background: rgba(255, 105, 180, 0.15);
    border-left-color: #ff69b4;
}

body.dark-mode .current-chapter-title {
    color: #ff69b4;
}

body.dark-mode .current-chapter-count {
    color: #fddde6;
}

body.dark-mode .current-chapter-info:hover .bookmark-clear-icon {
    opacity: 0.7;
}

body.dark-mode .bookmark-clear-icon:hover {
    background: rgba(255, 105, 180, 0.2) !important;
    opacity: 1 !important;
}

body.dark-mode .bookmark-clear-icon:hover::after {
    background: #5a2d49;
    color: #fddde6;
}

body.dark-mode .qa-pair-bookmark {
    border-left-color: #ff69b4;
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.15) 0%, rgba(59, 28, 50, 0.5) 100%);
}

body.dark-mode .qa-pair-bookmark:hover {
    background: linear-gradient(135deg, rgba(255, 105, 180, 0.2) 0%, rgba(255, 105, 180, 0.1) 100%);
}

/* ============ 搜索激活按钮样式 ============ */
.search-activation {
    margin: 30px 0;
    text-align: center;
}

.search-activate-btn {
    background: linear-gradient(135deg, #e75480 0%, #ff69b4 100%);
    color: white;
    border: none;
    padding: 15px 30px;
    border-radius: 25px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(231, 84, 128, 0.3);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.search-activate-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(231, 84, 128, 0.4);
    background: linear-gradient(135deg, #ff69b4 0%, #e75480 100%);
}

.search-activate-btn:active {
    transform: translateY(0);
}

.search-activate-hint {
    display: block;
    font-size: 12px;
    font-weight: normal;
    opacity: 0.9;
    margin-top: 4px;
}

/* ============ 搜索功能样式 ============ */
.search-container {
    margin: 30px 0;
    padding: 20px;
    background: linear-gradient(135deg, #fff8f5 0%, #ffffff 100%);
    border-radius: 12px;
    border: 1px solid #f8c8dc;
    box-shadow: 0 4px 12px rgba(231, 84, 128, 0.1);
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.search-box {
    position: relative;
    margin-bottom: 15px;
}

#search-input {
    width: 100%;
    padding: 12px 20px;
    font-size: 16px;
    border: 2px solid #f8c8dc;
    border-radius: 25px;
    background: #fff;
    color: #333;
    box-sizing: border-box;
    transition: all 0.3s ease;
    outline: none;
}

#search-input:focus {
    border-color: #e75480;
    box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.1);
}

#search-input::placeholder {
    color: #999;
}

.search-status {
    margin-top: 8px;
    font-size: 14px;
    color: #666;
    min-height: 20px;
}

.search-results {
    margin-top: 20px;
}

.search-results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f8c8dc;
}

.search-results-count {
    font-weight: 600;
    color: #e75480;
}

.search-clear, .search-collapse {
    background: #f8c8dc;
    color: #b73c65;
    border: none;
    padding: 6px 12px;
    border-radius: 15px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.3s ease;
    margin-left: 8px;
}

.search-clear:hover, .search-collapse:hover {
    background: #e75480;
    color: white;
}

.search-collapse {
    background: #e0e0e0;
    color: #666;
}

.search-collapse:hover {
    background: #999;
    color: white;
}

.search-results-list {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 400px;
    overflow-y: auto;
}

.search-result-item {
    margin-bottom: 12px;
    padding: 15px;
    background: #fff;
    border-radius: 8px;
    border-left: 3px solid #e75480;
    box-shadow: 0 2px 6px rgba(231, 84, 128, 0.1);
    cursor: pointer;
    transition: all 0.3s ease;
}

.search-result-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(231, 84, 128, 0.15);
    border-left-color: #ff69b4;
}

.search-result-title {
    font-weight: 600;
    color: #e75480;
    margin-bottom: 8px;
    font-size: 14px;
}

.search-result-type {
    display: inline-block;
    background: #f8c8dc;
    color: #b73c65;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    margin-right: 8px;
}

.search-result-content {
    color: #555;
    font-size: 14px;
    line-height: 1.5;
    margin: 8px 0;
}

.search-result-highlight {
    background: linear-gradient(120deg, #ffeb3b 0%, #ffc107 100%);
    padding: 1px 2px;
    border-radius: 2px;
    font-weight: 600;
}

.search-result-url {
    font-size: 12px;
    color: #999;
    text-decoration: none;
}

/* 暗色模式搜索样式 */
body.dark-mode .search-activate-btn {
    background: linear-gradient(135deg, #ff69b4 0%, #e75480 100%);
    box-shadow: 0 4px 15px rgba(255, 105, 180, 0.4);
}

body.dark-mode .search-activate-btn:hover {
    background: linear-gradient(135deg, #e75480 0%, #ff69b4 100%);
    box-shadow: 0 6px 20px rgba(255, 105, 180, 0.5);
}

body.dark-mode .search-container {
    background: linear-gradient(135deg, #2d1e2e 0%, #1a1a1a 100%);
    border-color: #4a2c4a;
}

body.dark-mode #search-input {
    background: #2d1e2e;
    color: #fff;
    border-color: #4a2c4a;
}

body.dark-mode #search-input::placeholder {
    color: #ccc;
}

body.dark-mode #search-input:focus {
    border-color: #ff69b4;
    box-shadow: 0 0 0 3px rgba(255, 105, 180, 0.2);
}

body.dark-mode .search-results-header {
    border-bottom-color: #4a2c4a;
}

body.dark-mode .search-result-item {
    background: #2d1e2e;
    border-left-color: #ff69b4;
}

body.dark-mode .search-result-content {
    color: #ccc;
}

body.dark-mode .search-clear, body.dark-mode .search-collapse {
    background: #4a2c4a;
    color: #ff69b4;
}

body.dark-mode .search-clear:hover, body.dark-mode .search-collapse:hover {
    background: #ff69b4;
    color: #1a1a1a;
}

body.dark-mode .search-collapse {
    background: #333;
    color: #ccc;
}

body.dark-mode .search-collapse:hover {
    background: #555;
    color: #fff;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .search-activate-btn {
        padding: 12px 24px;
        font-size: 14px;
    }
    
    .search-activate-hint {
        font-size: 11px;
    }
    
    .search-container {
        margin: 20px 0;
        padding: 15px;
    }
    
    #search-input {
        font-size: 16px; /* 防止iOS缩放 */
    }
    
    .search-results-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .search-result-item {
        padding: 12px;
    }
}

"""

JS_CONTENT = """document.addEventListener('DOMContentLoaded', function() {
  // ============ 基本設置 ============
  
  // 暗色模式初始化
  if(localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }

  // ============ UX 增強功能 ============
  
  // ============ 搜索功能（延迟加载） ============
  let searchIndex = null;
  let miniSearch = null;
  let searchInitialized = false;
  
  // 检测当前页面类型
  function isIndexPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index.html' || filename === 'index_trad.html';
  }
  
  // 获取搜索索引文件名
  function getSearchIndexFile() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename === 'index_trad.html' ? 'search_index_trad.json' : 'search_index.json';
  }
  
  // 激活搜索功能
  async function activateSearch() {
    if (searchInitialized) {
      // 如果已经初始化，直接显示搜索容器
      const searchContainer = document.getElementById('search-container');
      const searchActivation = document.querySelector('.search-activation');
      if (searchContainer && searchActivation) {
        searchActivation.style.display = 'none';
        searchContainer.style.display = 'block';
        // 聚焦搜索框
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          setTimeout(() => searchInput.focus(), 100);
        }
      }
      return;
    }
    
    await initSearch();
  }
  
  // 初始化搜索功能（内部函数）
  async function initSearch() {
    if (!isIndexPage()) return;
    
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchStatus = document.getElementById('search-status');
    const searchResults = document.getElementById('search-results');
    const searchResultsList = document.getElementById('search-results-list');
    const searchResultsCount = document.getElementById('search-results-count');
    const searchClear = document.getElementById('search-clear');
    const searchCollapse = document.getElementById('search-collapse');
    const tocHeader = document.getElementById('toc-header');
    
    if (!searchInput || !searchContainer) return;
    
    try {
      // 显示搜索容器，隐藏激活按钮
      if (searchActivation) searchActivation.style.display = 'none';
      searchContainer.style.display = 'block';
      
      searchStatus.textContent = '正在加载搜索索引...';
      
      // 检查MiniSearch是否可用
      if (typeof MiniSearch === 'undefined') {
        throw new Error('MiniSearch库未加载');
      }
      
      // 加载搜索索引
      const indexFile = getSearchIndexFile();
      const response = await fetch(indexFile);
      
      if (!response.ok) {
        throw new Error('无法加载搜索索引');
      }
      
      searchIndex = await response.json();
      
      // 初始化MiniSearch
      miniSearch = new MiniSearch({
        fields: ['title', 'content'], // 搜索字段
        storeFields: ['id', 'title', 'type', 'content', 'context', 'url', 'weight'], // 存储字段
        searchOptions: {
          boost: { title: 3, content: 1 }, // 标题权重更高
          fuzzy: 0.2, // 模糊搜索
          prefix: true // 前缀匹配
        },
        extractField: (document, fieldName) => {
          // 为中文优化：简单字符分割
          const text = document[fieldName] || '';
          return text;
        }
      });
      
      // 添加文档到索引
      miniSearch.addAll(searchIndex);
      
      searchStatus.textContent = `搜索准备就绪 (共${searchIndex.length}条记录)`;
      searchInitialized = true;
      
      // 聚焦搜索框
      setTimeout(() => searchInput.focus(), 100);
      
    } catch (error) {
      console.error('搜索初始化失败:', error);
      searchStatus.textContent = '搜索功能不可用：' + error.message;
      return;
    }
    
    // 搜索功能处理
    function performSearch(query) {
      if (!miniSearch || !query || query.trim().length < 2) {
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
        if (query && query.trim().length > 0 && query.trim().length < 2) {
          searchStatus.textContent = '请输入至少2个字符进行搜索';
        } else {
          searchStatus.textContent = `搜索准备就绪 (共${searchIndex ? searchIndex.length : 0}条记录)`;
        }
        return;
      }
      
      const trimmedQuery = query.trim();
      
      try {
        // 执行搜索
        const results = miniSearch.search(trimmedQuery, {
          boost: { title: 3, content: 1 },
          fuzzy: 0.2,
          prefix: true
        });
        
        // 按权重和评分排序
        results.sort((a, b) => {
          const scoreA = a.score * (a.weight || 1);
          const scoreB = b.score * (b.weight || 1);
          return scoreB - scoreA;
        });
        
        // 限制结果数量
        const limitedResults = results.slice(0, 20);
        
        if (limitedResults.length > 0) {
          displayResults(limitedResults, trimmedQuery);
          searchStatus.textContent = `找到 ${results.length} 条结果` + (results.length > 20 ? ' (仅显示前20条)' : '');
        } else {
          displayNoResults(trimmedQuery);
          searchStatus.textContent = '未找到匹配结果';
        }
        
        searchResults.style.display = 'block';
        tocHeader.style.display = 'none';
        
      } catch (error) {
        console.error('搜索出错:', error);
        searchStatus.textContent = '搜索出现错误，请重试';
        // 在出错时也隐藏搜索结果
        searchResults.style.display = 'none';
        tocHeader.style.display = 'block';
      }
    }
    
    // 显示搜索结果
    function displayResults(results, query) {
      searchResultsCount.textContent = `找到 ${results.length} 条结果`;
      
      searchResultsList.innerHTML = results.map(result => {
        const typeText = {
          'heading': '标题',
          'question': '问题', 
          'answer': '回答',
          'content': '内容'
        }[result.type] || '内容';
        
        // 高亮搜索关键词 - 安全处理
        let highlightedContext = result.context;
        try {
          if (query && query.trim()) {
            const escapedQuery = escapeRegex(query.trim());
            if (escapedQuery) {
              const regex = new RegExp(`(${escapedQuery})`, 'gi');
              highlightedContext = result.context.replace(regex, '<span class="search-result-highlight">$1</span>');
            }
          }
        } catch (e) {
          console.warn('搜索高亮处理失败:', e);
          // 降级处理：不高亮但显示内容
          highlightedContext = result.context;
        }
        
        return `
          <li class="search-result-item" data-url="${result.url}">
            <div class="search-result-title">
              <span class="search-result-type">${typeText}</span>
              ${escapeHtml(result.title)}
            </div>
            <div class="search-result-content">${highlightedContext}</div>
            <div class="search-result-url">${result.url}</div>
          </li>
        `;
      }).join('');
    }
    
    // 显示无结果
    function displayNoResults(query) {
      searchResultsCount.textContent = '未找到结果';
      searchResultsList.innerHTML = `
        <li class="search-result-item" style="text-align: center; color: #999;">
          <div>未找到包含"${escapeHtml(query)}"的内容</div>
          <div style="font-size: 12px; margin-top: 8px;">尝试使用不同的关键词</div>
        </li>
      `;
    }
    
    // 转义正则表达式特殊字符
    function escapeRegex(str) {
      if (!str || typeof str !== 'string') {
        return '';
      }
      // 简单的字符串替换，避免复杂的正则表达式
      const chars = {
        '\\\\': '\\\\\\\\',
        '.': '\\\\.',
        '*': '\\\\*',
        '+': '\\\\+',
        '?': '\\\\?',
        '^': '\\\\^',
        '$': '\\\\$',
        '{': '\\\\{',
        '}': '\\\\}',
        '(': '\\\\(',
        ')': '\\\\)',
        '|': '\\\\|',
        '[': '\\\\[',
        ']': '\\\\]',
        '/': '\\\\/'
      };
      let result = str;
      Object.keys(chars).forEach(char => {
        result = result.split(char).join(chars[char]);
      });
      return result;
    }
    
    // 转义HTML特殊字符
    function escapeHtml(str) {
      if (!str || typeof str !== 'string') {
        return '';
      }
      try {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
      } catch (e) {
        console.warn('HTML转义失败:', e);
        // 降级处理：手动替换基本的HTML字符
        return str.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&#39;');
      }
    }
    
    // 清除搜索
    function clearSearch() {
      searchInput.value = '';
      searchResults.style.display = 'none';
      tocHeader.style.display = 'block';
      searchStatus.textContent = `搜索准备就绪 (共${searchIndex.length}条记录)`;
    }
    
    // 事件监听
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();
      
      // 防抖处理
      searchTimeout = setTimeout(() => {
        performSearch(query);
      }, 300);
    });
    
    // 清除搜索按钮
    searchClear.addEventListener('click', clearSearch);
    
    // 收起搜索按钮
    searchCollapse.addEventListener('click', collapseSearch);
    
    // 搜索结果点击
    searchResultsList.addEventListener('click', (e) => {
      const item = e.target.closest('.search-result-item');
      if (item) {
        const url = item.dataset.url;
        if (url) {
          window.location.href = url;
        }
      }
    });
    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
      // Ctrl+F 或 Cmd+F 激活搜索
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        if (searchInitialized) {
          searchInput.focus();
        } else {
          activateSearch();
        }
      }
      
      // ESC 收起搜索
      if (e.key === 'Escape' && document.activeElement === searchInput) {
        collapseSearch();
      }
    });
  }
  
  // 收起搜索功能
  function collapseSearch() {
    const searchContainer = document.getElementById('search-container');
    const searchActivation = document.querySelector('.search-activation');
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const tocHeader = document.getElementById('toc-header');
    
    if (searchContainer && searchActivation) {
      // 清除搜索内容
      if (searchInput) searchInput.value = '';
      if (searchResults) searchResults.style.display = 'none';
      if (tocHeader) tocHeader.style.display = 'block';
      
      // 隐藏搜索容器，显示激活按钮
      searchContainer.style.display = 'none';
      searchActivation.style.display = 'block';
    }
  }
  
  // 如果是首页，添加搜索激活事件监听
  if (isIndexPage()) {
    const searchActivateBtn = document.getElementById('search-activate-btn');
    if (searchActivateBtn) {
      searchActivateBtn.addEventListener('click', activateSearch);
    }
    
    // Ctrl+F 快捷键激活搜索
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && !searchInitialized) {
        e.preventDefault();
        activateSearch();
      }
    });
  }

  // 創建閱讀工具欄
  function createReadingToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'reading-toolbar hidden';
    toolbar.innerHTML = 
      '<div class="toolbar-header">' +
        '<span>⚙️ 閱讀設置</span>' +
        '<button class="ctrl-btn" data-action="close-toolbar">✕</button>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">字體大小</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="font-decrease">A-</button>' +
          '<button class="ctrl-btn active" data-action="font-normal">A</button>' +
          '<button class="ctrl-btn" data-action="font-increase">A+</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">行距</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="line-tight">緊密</button>' +
          '<button class="ctrl-btn active" data-action="line-normal">正常</button>' +
          '<button class="ctrl-btn" data-action="line-loose">寬鬆</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">寬度</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="width-narrow">窄</button>' +
          '<button class="ctrl-btn active" data-action="width-normal">中</button>' +
          '<button class="ctrl-btn" data-action="width-wide">寬</button>' +
        '</div>' +
      '</div>' +
      '<div class="toolbar-section">' +
        '<div class="toolbar-label">主題</div>' +
        '<div class="toolbar-controls">' +
          '<button class="ctrl-btn" data-action="theme-light">☀️ 日間</button>' +
          '<button class="ctrl-btn" data-action="theme-dark">🌙 夜間</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(toolbar);
    return toolbar;
  }
  
  // 更新主題按鈕狀態
  function updateThemeButtons() {
    const isDark = document.body.classList.contains('dark-mode');
    const lightBtn = document.querySelector('[data-action="theme-light"]');
    const darkBtn = document.querySelector('[data-action="theme-dark"]');
    
    if (lightBtn && darkBtn) {
      lightBtn.classList.toggle('active', !isDark);
      darkBtn.classList.toggle('active', isDark);
    }
  }

  // 創建閱讀進度條
  function createReadingProgress() {
    const progress = document.createElement('div');
    progress.className = 'reading-progress';
    progress.innerHTML = '<div class="reading-progress-bar"></div>';
    document.body.appendChild(progress);
    return progress;
  }

  // 創建浮動目錄
  function createFloatingTOC() {
    const toc = document.createElement('div');
    toc.className = 'floating-toc';
    
    let tocItems = '';
    
    if (currentChapter.isHomepage) {
      // 首頁：從TOC連結提取目錄結構
      const tocLinks = document.querySelectorAll('h2 + ul li a, ul li a');
      tocLinks.forEach((link, index) => {
        const text = link.textContent;
        const href = link.getAttribute('href');
        
        // 更準確的層級判斷：計算嵌套深度
        const listItem = link.closest('li');
        let level = 0;
        let currentElement = listItem.parentElement; // 从ul开始计算
        
        // 向上遍歷，計算嵌套的ul層數
        while (currentElement && currentElement.tagName === 'UL') {
          level++;
          // 跳过li，直接到下一个ul
          currentElement = currentElement.parentElement;
          if (currentElement && currentElement.tagName === 'LI') {
            currentElement = currentElement.parentElement;
          }
        }
        
        // 根據層級添加對應的class (level=1是第一层，无缩进)
        // 只顯示前兩層目錄，跳過第三層及以下
        if (level >= 3) {
          return; // 跳過第三層及以下的項目
        }
        
        let levelClass = '';
        if (level === 2) {
          levelClass = ' level-h3';
        }
        
        // 為首頁TOC項目使用特殊的data屬性
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-href="' + href + '">' + text + '</div>';
      });
    } else {
      // 其他頁面：收集標題
      const headings = document.querySelectorAll('h2, h3, h4');
      headings.forEach((heading, index) => {
        const text = heading.textContent;
        const id = heading.id || ('heading-' + index);
        if (!heading.id) heading.id = id;
        
        const level = heading.tagName.toLowerCase();
        const levelClass = level !== 'h2' ? ' level-' + level : '';
        
        tocItems += '<div class="floating-toc-item' + levelClass + '" data-target="#' + id + '">' + text + '</div>';
      });
    }
    
    // 根據是否為首頁決定標籤頁內容
    let tabsHtml = '';
    let contentHtml = '';
    
    if (currentChapter.isHomepage) {
      // 首頁只顯示目錄
      tabsHtml = '<button class="floating-toc-tab active" data-tab="toc">目錄</button>';
      contentHtml = 
        '<div class="floating-toc-list" id="toc-list">' +
          tocItems +
        '</div>';
    } else {
      // 其他頁面顯示目錄和書籤
      tabsHtml = 
        '<button class="floating-toc-tab active" data-tab="toc">目錄</button>' +
        '<button class="floating-toc-tab" data-tab="bookmarks">書籤 <span id="bookmark-count">(0)</span></button>';
      contentHtml = 
        '<div class="floating-toc-list" id="toc-list">' +
          tocItems +
        '</div>' +
        '<div class="floating-toc-list" id="bookmarks-list" style="display: none;">' +
          '<div class="bookmarks-empty">尚無書籤</div>' +
        '</div>';
    }
    
    toc.innerHTML = 
      '<div class="floating-toc-header">' +
        '<span id="toc-title">📖 章節目錄</span>' +
        '<button class="ctrl-btn" data-action="close-toc">✕</button>' +
      '</div>' +
      '<div class="floating-toc-tabs">' +
        tabsHtml +
      '</div>' +
      '<div class="floating-toc-content">' +
        contentHtml +
      '</div>';
    
    document.body.appendChild(toc);
    return toc;
  }

  // 創建操作按鈕組
  function createActionButtons() {
    const buttons = document.createElement('div');
    buttons.className = 'action-buttons';
    buttons.innerHTML = 
      '<div class="action-menu">' +
        '<button class="action-btn menu-btn" data-action="toggle-menu" title="功能菜單">⋯</button>' +
        '<div class="action-menu-items">' +
          '<button class="action-btn" data-action="toc" title="目錄">📖</button>' +
          '<button class="action-btn" data-action="top" title="回到頂部">↑</button>' +
          '<button class="action-btn" data-action="settings" title="設置">⚙️</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(buttons);
    return buttons;
  }

  // 為問答添加互動按鈕
  function addQAActions() {
    const qaElements = document.querySelectorAll('.question, .answer');
    qaElements.forEach((element) => {
      // 確保元素有唯一ID（用於分享功能）
      const prefix = element.classList.contains('question') ? 'question' : 'answer';
      ensureElementId(element, prefix);
      
      element.style.position = 'relative';
      const actions = document.createElement('div');
      actions.className = 'qa-actions';
      
      const isQuestion = element.classList.contains('question');
      const isAnswer = element.classList.contains('answer');
      
      // 首頁不顯示書籤按鈕
      let actionsHtml = '';
      
      if (isQuestion) {
        actionsHtml += '<button class="qa-btn" data-action="copy" title="複製問題">📋</button>';
        if (!currentChapter.isHomepage) {
          actionsHtml += '<button class="qa-btn" data-action="bookmark-qa" title="加入書籤">🔖</button>';
        }
        actionsHtml += '<button class="qa-btn" data-action="share" title="分享問題">📤</button>';
      } else if (isAnswer) {
        actionsHtml += '<button class="qa-btn" data-action="copy-qa" title="複製問答">📋</button>';
        if (!currentChapter.isHomepage) {
          actionsHtml += '<button class="qa-btn" data-action="bookmark-qa" title="加入書籤">🔖</button>';
        }
        actionsHtml += '<button class="qa-btn" data-action="share" title="分享回答">📤</button>';
      }
      
      actions.innerHTML = actionsHtml;
      element.appendChild(actions);
    });
  }

  // ============ 功能實現 ============
  
  // 生成內容的簡單hash
  function simpleHash(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 轉換為32位整數
    }
    return Math.abs(hash).toString(36);
  }
  
  // 確保元素有唯一且穩定的ID
  function ensureElementId(element, prefix = 'qa') {
    if (!element.id) {
      // 基於內容生成穩定的ID
      let contentText = '';
      
      if (element.classList.contains('question')) {
        const questioner = element.querySelector('.questioner')?.textContent || '';
        const questionText = element.querySelector('.question-text')?.textContent || '';
        const time = element.querySelector('.question-time')?.textContent || '';
        contentText = questioner + questionText + time;
      } else if (element.classList.contains('answer')) {
        const answerer = element.querySelector('.answerer')?.textContent || '';
        const answerText = element.querySelector('.answer-text')?.textContent || '';
        contentText = answerer + answerText.substring(0, 100); // 只取前100字符
      }
      
      // 生成基於內容的穩定ID
      const contentHash = simpleHash(contentText);
      element.id = prefix + '-' + contentHash;
    }
    return element.id;
  }
  
  // 生成分享URL
  function generateShareUrl(targetElement) {
    const prefix = targetElement.classList.contains('question') ? 'question' : 'answer';
    const elementId = ensureElementId(targetElement, prefix);
    const baseUrl = window.location.origin + window.location.pathname;
    return baseUrl + '#' + elementId;
  }
  
  // 找到問答配對
  function findQuestionForAnswer(answerElement) {
    let currentElement = answerElement.previousElementSibling;
    
    // 向上查找最近的問題元素
    while (currentElement) {
      if (currentElement.classList.contains('question')) {
        return currentElement;
      }
      currentElement = currentElement.previousElementSibling;
    }
    
    return null;
  }
  
  function findAnswerForQuestion(questionElement) {
    let currentElement = questionElement.nextElementSibling;
    
    // 向下查找最近的回答元素
    while (currentElement) {
      if (currentElement.classList.contains('answer')) {
        return currentElement;
      }
      currentElement = currentElement.nextElementSibling;
    }
    
    return null;
  }
  
  // 獲取問答的完整文本
  function getQAPairText(answerElement) {
    const questionElement = findQuestionForAnswer(answerElement);
    let text = '';
    
    if (questionElement) {
      // 提取問題內容
      const questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
      const questionTime = questionElement.querySelector('.question-time')?.textContent || '';
      const questionText = questionElement.querySelector('.question-text')?.textContent || '';
      
      text += `問：${questioner}`;
      if (questionTime) text += ` (${questionTime})`;
      text += `\n${questionText}\n\n`;
    }
    
    // 提取回答內容
    const answerer = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
    const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
    
    text += `答：${answerer}\n${answerText}`;
    
    return text;
  }
  
  // ============ 書籤功能 ============
  
  // 書籤管理
  function getBookmarks(chapterId = null) {
    const allBookmarks = localStorage.getItem('ebook-bookmarks');
    const bookmarks = allBookmarks ? JSON.parse(allBookmarks) : [];
    
    // 如果指定了章節ID，只返回該章節的書籤
    if (chapterId) {
      return bookmarks.filter(bookmark => 
        bookmark.chapter && bookmark.chapter.id === chapterId
      );
    }
    
    return bookmarks;
  }
  
  function getCurrentChapterBookmarks() {
    return getBookmarks(currentChapter.id);
  }
  
  function saveBookmarks(bookmarks) {
    localStorage.setItem('ebook-bookmarks', JSON.stringify(bookmarks));
    updateBookmarkCount();
  }
  
  // 為元素獲取文件級章節信息（文件級書籤）
  function findChapterForElement(element) {
    // 直接返回當前文件的章節信息
    return {
      title: currentChapter.title,
      id: currentChapter.id,
      filename: currentChapter.filename
    };
  }

  // 添加書籤視覺標識
  function addBookmarkVisualIndicator(element) {
    if (!element.classList.contains('bookmarked')) {
      element.classList.add('bookmarked');
      
      // 添加可點擊的書籤標記
      if (!element.querySelector('.bookmark-indicator')) {
        const indicator = document.createElement('span');
        indicator.className = 'bookmark-indicator';
        indicator.textContent = '🔖';
        indicator.title = '點擊移除書籤';
        element.appendChild(indicator);
      }
    }
  }
  
  // 移除書籤視覺標識
  function removeBookmarkVisualIndicator(element) {
    element.classList.remove('bookmarked');
    
    // 移除書籤標記元素
    const indicator = element.querySelector('.bookmark-indicator');
    if (indicator) {
      element.removeChild(indicator);
    }
  }
  
  // 恢復所有書籤的視覺狀態
  function restoreBookmarkVisualStates() {
    const bookmarks = getBookmarks();
    bookmarks.forEach(bookmark => {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        addBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，還需要為問題添加視覺標識
        if (bookmark.type === 'qa-pair' && element.classList.contains('answer')) {
          const questionElement = findQuestionForAnswer(element);
          if (questionElement) {
            addBookmarkVisualIndicator(questionElement);
          }
        }
      }
    });
  }
  
  // 檢測當前文件信息（文件級書籤）
  function getCurrentChapter() {
    // 獲取當前頁面的文件名
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    
    // 從頁面標題或第一個H1獲取章節名稱
    let chapterTitle = document.title;
    const firstH1 = document.querySelector('h1');
    if (firstH1) {
      chapterTitle = firstH1.textContent.trim();
    }
    
    // 如果是首頁，返回特殊標識
    if (filename === 'index.html' || filename === 'index_trad.html') {
      return {
        title: '首頁',
        id: 'homepage',
        isHomepage: true
      };
    }
    
    // 為其他頁面生成章節信息
    const chapterId = filename.replace('.html', '');
    
    return {
      title: chapterTitle || '未知章節',
      id: chapterId,
      filename: filename,
      isHomepage: false
    };
  }
  
  // 初始化當前文件信息（文件級書籤，無需監聽滾動）
  let currentChapter = getCurrentChapter();

  function toggleBookmark(element) {
    // 首頁不允許操作書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const bookmarks = getBookmarks();
    const isQuestion = element.classList.contains('question');
    const isAnswer = element.classList.contains('answer');
    
    if (!isQuestion && !isAnswer) return;
    
    // 生成唯一ID
    const id = element.id || ('bookmark-' + Date.now());
    element.id = id;
    
    // 檢查是否已存在書籤
    const existingBookmark = bookmarks.find(bookmark => bookmark.elementId === id);
    
    if (existingBookmark) {
      // 已存在，移除書籤
      removeBookmarkVisualIndicator(element);
      const updatedBookmarks = bookmarks.filter(bookmark => bookmark.elementId !== id);
      saveBookmarks(updatedBookmarks);
      renderBookmarks();
      showToast('已從書籤移除');
      return;
    }
    
    // 不存在，添加書籤
    const chapter = findChapterForElement(element);
    
    // 提取內容
    let questioner = '', time = '', preview = '';
    
    if (isQuestion) {
      const questionerEl = element.querySelector('.questioner');
      const timeEl = element.querySelector('.question-time');
      const textEl = element.querySelector('.question-text');
      
      questioner = questionerEl ? questionerEl.textContent : '匿名';
      time = timeEl ? timeEl.textContent : '';
      preview = textEl ? textEl.textContent.substring(0, 100) + '...' : '';
    } else if (isAnswer) {
      const answererEl = element.querySelector('.answerer');
      const textEl = element.querySelector('.answer-text');
      
      questioner = answererEl ? answererEl.textContent : 'Taiguanglin';
      preview = textEl ? textEl.textContent.substring(0, 100) + '...' : '';
    }
    
    const bookmark = {
      id: 'bookmark-' + Date.now(),
      elementId: id,
      type: isQuestion ? 'question' : 'answer',
      questioner: questioner,
      time: time,
      preview: preview,
      chapter: chapter,
      timestamp: new Date().toLocaleString()
    };
    
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    addBookmarkVisualIndicator(element);
    renderBookmarks();
    showToast('已添加到書籤');
  }
  
  function toggleQAPairBookmark(answerElement) {
    // 首頁不允許操作書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const bookmarks = getBookmarks();
    const questionElement = findQuestionForAnswer(answerElement);
    
    // 生成唯一ID
    const id = answerElement.id || ('qa-bookmark-' + Date.now());
    answerElement.id = id;
    
    // 檢查是否已存在書籤
    const existingBookmark = bookmarks.find(bookmark => bookmark.elementId === id);
    
    if (existingBookmark) {
      // 已存在，移除書籤
      removeBookmarkVisualIndicator(answerElement);
      if (questionElement) {
        removeBookmarkVisualIndicator(questionElement);
      }
      const updatedBookmarks = bookmarks.filter(bookmark => bookmark.elementId !== id);
      saveBookmarks(updatedBookmarks);
      renderBookmarks();
      showToast('已從書籤移除問答');
      return;
    }
    
    // 不存在，添加問答書籤
    const chapter = findChapterForElement(answerElement);
    
    // 提取問答信息
    let questioner = '匿名', time = '', preview = '';
    
    if (questionElement) {
      const questionerEl = questionElement.querySelector('.questioner');
      const timeEl = questionElement.querySelector('.question-time');
      const questionTextEl = questionElement.querySelector('.question-text');
      
      questioner = questionerEl ? questionerEl.textContent : '匿名';
      time = timeEl ? timeEl.textContent : '';
      
      // 構建預覽：問題開頭 + 回答開頭
      const questionText = questionTextEl ? questionTextEl.textContent : '';
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      preview = `問：${questionText.substring(0, 50)}... 答：${answerText.substring(0, 50)}...`;
    } else {
      // 只有回答的情況
      const answererEl = answerElement.querySelector('.answerer');
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      
      questioner = answererEl ? answererEl.textContent : 'Taiguanglin';
      preview = `答：${answerText.substring(0, 100)}...`;
    }
    
    const bookmark = {
      id: 'qa-bookmark-' + Date.now(),
      elementId: id,
      type: 'qa-pair',
      questioner: questioner,
      time: time,
      preview: preview,
      chapter: chapter,
      timestamp: new Date().toLocaleString()
    };
    
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    
    // 為問答添加視覺標識
    addBookmarkVisualIndicator(answerElement);
    if (questionElement) {
      addBookmarkVisualIndicator(questionElement);
    }
    
    renderBookmarks();
    showToast('已添加問答到書籤');
  }
  
  function removeBookmark(bookmarkId) {
    const bookmarks = getBookmarks();
    const bookmark = bookmarks.find(b => b.id === bookmarkId);
    
    // 移除視覺標識
    if (bookmark) {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        removeBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，還需要移除問題的視覺標識
        if (bookmark.type === 'qa-pair' && element.classList.contains('answer')) {
          const questionElement = findQuestionForAnswer(element);
          if (questionElement) {
            removeBookmarkVisualIndicator(questionElement);
          }
        }
      }
    }
    
    const updatedBookmarks = bookmarks.filter(bookmark => bookmark.id !== bookmarkId);
    saveBookmarks(updatedBookmarks);
    renderBookmarks();
    showToast('已從書籤移除');
  }
  
  function clearCurrentChapterBookmarks() {
    // 首頁不允許清空書籤
    if (currentChapter.isHomepage) {
      showToast('首頁不支持書籤功能');
      return;
    }
    
    const currentBookmarks = getCurrentChapterBookmarks();
    if (currentBookmarks.length === 0) {
      showToast('本文件暫無書籤');
      return;
    }
    
    // 確認對話框
    if (!confirm(`確定要清空本文件的所有 ${currentBookmarks.length} 個書籤嗎？此操作無法撤銷。`)) {
      return;
    }
    
    // 移除當前文件所有書籤的視覺標識
    currentBookmarks.forEach(bookmark => {
      const element = document.getElementById(bookmark.elementId);
      if (element) {
        removeBookmarkVisualIndicator(element);
        
        // 如果是問答書籤，還需要移除問題的視覺標識
        if (bookmark.type === 'qa-pair' && element.classList.contains('answer')) {
          const questionElement = findQuestionForAnswer(element);
          if (questionElement) {
            removeBookmarkVisualIndicator(questionElement);
          }
        }
      }
    });
    
    // 從總書籤列表中移除當前文件的書籤
    const allBookmarks = getBookmarks();
    const updatedBookmarks = allBookmarks.filter(bookmark => 
      !bookmark.chapter || bookmark.chapter.id !== currentChapter.id
    );
    
    saveBookmarks(updatedBookmarks);
    renderBookmarks();
    showToast(`已清空本文件的 ${currentBookmarks.length} 個書籤`);
  }
  
  function renderBookmarks() {
    const bookmarksList = document.getElementById('bookmarks-list');
    
    // 首頁不顯示書籤
    if (currentChapter.isHomepage || !bookmarksList) {
      return;
    }
    
    const chapterBookmarks = getCurrentChapterBookmarks();
    
    if (chapterBookmarks.length === 0) {
      bookmarksList.innerHTML = 
        '<div class="bookmarks-empty">' +
          '<div>本文件暫無書籤</div>' +
          '<div style="font-size: 12px; color: #999; margin-top: 8px;">當前文件：' + currentChapter.title + '</div>' +
        '</div>';
      return;
    }
    
    let bookmarksHTML = '';
    
    // 添加當前文件標題和清空按鈕
    bookmarksHTML += 
      '<div class="current-chapter-info">' +
        '<div class="chapter-header">' +
          '<div class="current-chapter-title">📄 ' + currentChapter.title + '</div>' +
          '<button class="bookmark-clear-icon" data-action="clear-bookmarks" title="清空本文件所有書籤">🗑️</button>' +
        '</div>' +
      '</div>';
    
    // 直接顯示當前文件的書籤，不需要分組
    chapterBookmarks.forEach(bookmark => {
      const isQAPair = bookmark.type === 'qa-pair';
      const typeIcon = isQAPair ? '💬' : '📝';
      const typeClass = isQAPair ? ' qa-pair-bookmark' : '';
      
      bookmarksHTML += 
        '<div class="bookmark-item' + typeClass + '" data-target="#' + bookmark.elementId + '">' +
          '<div class="bookmark-meta">' +
            '<span class="bookmark-type">' + typeIcon + '</span>' +
            '<span class="bookmark-questioner">' + bookmark.questioner + '</span>' +
            '<span class="bookmark-time">' + bookmark.time + '</span>' +
          '</div>' +
          '<div class="bookmark-preview">' + bookmark.preview + '</div>' +
          '<button class="bookmark-delete" data-bookmark-id="' + bookmark.id + '" title="刪除書籤">✕</button>' +
        '</div>';
    });
    
    bookmarksList.innerHTML = bookmarksHTML;
  }
  
  function updateBookmarkCount() {
    // 首頁不顯示書籤計數
    if (currentChapter.isHomepage) {
      return;
    }
    
    const count = getCurrentChapterBookmarks().length;
    const countEl = document.getElementById('bookmark-count');
    if (countEl) {
      countEl.textContent = '(' + count + ')';
    }
  }

  // 閱讀設置功能
  let fontSize = parseInt(localStorage.getItem('fontSize')) || 16;
  let lineHeight = parseFloat(localStorage.getItem('lineHeight')) || 1.6;
  let contentWidth = parseInt(localStorage.getItem('contentWidth')) || 800;
  
  function applyReadingSettings() {
    document.body.style.fontSize = fontSize + 'px';
    document.body.style.lineHeight = lineHeight;
    document.body.style.maxWidth = contentWidth + 'px';
  }
  
  function updateFontSize(change) {
    fontSize = Math.max(12, Math.min(24, fontSize + change));
    localStorage.setItem('fontSize', fontSize);
    applyReadingSettings();
  }
  
  function updateLineHeight(value) {
    lineHeight = value;
    localStorage.setItem('lineHeight', lineHeight);
    applyReadingSettings();
  }
  
  function updateContentWidth(value) {
    contentWidth = value;
    localStorage.setItem('contentWidth', contentWidth);
    applyReadingSettings();
  }

  // 閱讀進度功能
  function updateReadingProgress() {
    const scrollTop = window.pageYOffset;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    
    const progressBar = document.querySelector('.reading-progress-bar');
    if (progressBar) {
      progressBar.style.width = Math.max(0, Math.min(100, progress)) + '%';
    }
  }

  // 章節跟踪功能
  function updateCurrentSection() {
    // 首頁跳過章節跟踪
    if (currentChapter.isHomepage) {
      return;
    }
    
    const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
    const scrollTop = window.pageYOffset;
    const offset = 100; // 偏移量，調整觸發點
    
    let currentSection = null;
    
    // 找到最接近當前位置的章節
    headings.forEach((heading) => {
      const rect = heading.getBoundingClientRect();
      const elementTop = scrollTop + rect.top;
      
      if (elementTop <= scrollTop + offset) {
        currentSection = heading;
      }
    });
    
    // 更新TOC高亮狀態
    const tocItems = document.querySelectorAll('.floating-toc-item[data-target]');
    let activeItem = null;
    
    tocItems.forEach(item => {
      item.classList.remove('active');
      
      if (currentSection) {
        const targetId = '#' + currentSection.id;
        if (item.dataset.target === targetId) {
          item.classList.add('active');
          activeItem = item;
        }
      }
    });
    
    // 自動滾動sidebar到當前章節
    if (activeItem) {
      const tocContainer = activeItem.closest('.floating-toc');
      if (tocContainer && tocContainer.classList.contains('visible')) {
        // 檢查activeItem是否在可視區域內
        const containerRect = tocContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        
        // 如果item不在容器的可視區域內，則滾動到該位置
        if (itemRect.top < containerRect.top + 60 || itemRect.bottom > containerRect.bottom - 20) {
          activeItem.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
        }
      }
    }
  }

  // 顯示通知
  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
  }

  // 複製功能
  function copyText(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('已複製到剪貼板');
      });
    } else {
      // 降級處理
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('已複製到剪貼板');
    }
  }
  
  // 處理頁面加載時的錨點跳轉
  function handleInitialAnchor() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      const targetId = hash.substring(1); // 移除#號
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        // 延遲滾動，確保頁面布局完成
        setTimeout(() => {
          targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
          
          // 添加臨時高亮效果
          targetElement.style.transition = 'background-color 0.3s ease';
          targetElement.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
          setTimeout(() => {
            targetElement.style.backgroundColor = '';
          }, 3000);
        }, 300);
      }
    }
  }

  // ============ 事件監聽 ============
  
  // 初始化所有組件
  const toolbar = createReadingToolbar();
  const progressBar = createReadingProgress();
  const floatingTOC = createFloatingTOC();
  const actionButtons = createActionButtons();
  addQAActions();
  applyReadingSettings();
  
  // 初始化當前章節
  currentChapter = getCurrentChapter();
  
  updateBookmarkCount();
  updateThemeButtons();
  restoreBookmarkVisualStates();
  
  // 延遲執行章節跟踪，確保頁面完全渲染
  setTimeout(updateCurrentSection, 100);
  
  // 處理頁面加載時的錨點跳轉
  setTimeout(handleInitialAnchor, 200);

  document.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    
    // 點擊外部區域關閉菜單
    if (!action && !e.target.closest('.action-menu')) {
      const openMenu = document.querySelector('.action-menu.expanded');
      if (openMenu) {
        openMenu.classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
      }
    }
    
    if (!action) return;

    switch (action) {
      // 字體設置
      case 'font-decrease':
        updateFontSize(-2);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'font-normal':
        fontSize = 16;
        localStorage.setItem('fontSize', fontSize);
        applyReadingSettings();
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'font-increase':
        updateFontSize(2);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 行距設置 - 擴大調整幅度讓用戶感受到明顯差異
      case 'line-tight':
        updateLineHeight(0.4);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'line-normal':
        updateLineHeight(1.0);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'line-loose':
        updateLineHeight(2.0);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 寬度設置
      case 'width-narrow':
        updateContentWidth(600);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'width-normal':
        updateContentWidth(800);
        updateActiveButton(e.target.parentElement, e.target);
        break;
      case 'width-wide':
        updateContentWidth(1000);
        updateActiveButton(e.target.parentElement, e.target);
        break;

      // 主題切換
      case 'theme-light':
        document.body.classList.remove('dark-mode');
        localStorage.setItem('darkMode', false);
        updateThemeButtons();
        break;
      case 'theme-dark':
        document.body.classList.add('dark-mode');
        localStorage.setItem('darkMode', true);
        updateThemeButtons();
        break;

      // 操作按鈕
      case 'toggle-menu':
        const actionMenu = e.target.closest('.action-menu');
        actionMenu.classList.toggle('expanded');
        e.target.classList.toggle('expanded');
        break;
      case 'toc':
        floatingTOC.classList.toggle('visible');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'close-toc':
        floatingTOC.classList.remove('visible');
        break;
      case 'top':
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'settings':
        toolbar.classList.toggle('hidden');
        // 關閉菜單
        document.querySelector('.action-menu').classList.remove('expanded');
        document.querySelector('.action-btn.menu-btn').classList.remove('expanded');
        break;
      case 'close-toolbar':
        toolbar.classList.add('hidden');
        break;

      // 問答操作
      case 'copy':
        const copyElement = e.target.closest('.question, .answer');
        const text = copyElement.textContent.trim();
        copyText(text);
        break;
      case 'bookmark':
        const bookmarkElement = e.target.closest('.question, .answer');
        if (bookmarkElement) {
          toggleBookmark(bookmarkElement);
        }
        break;
      case 'copy-qa':
        const copyAnswerElement = e.target.closest('.answer');
        if (copyAnswerElement) {
          const qaPairText = getQAPairText(copyAnswerElement);
          copyText(qaPairText);
        }
        break;
      case 'bookmark-qa':
        const qaBookmarkElement = e.target.closest('.question, .answer');
        if (qaBookmarkElement) {
          if (qaBookmarkElement.classList.contains('answer')) {
            toggleQAPairBookmark(qaBookmarkElement);
          } else if (qaBookmarkElement.classList.contains('question')) {
            // 如果是問題，找到對應的回答
            const answerElement = findAnswerForQuestion(qaBookmarkElement);
            if (answerElement) {
              toggleQAPairBookmark(answerElement);
            } else {
              // 如果沒有對應回答，提示用戶
              showToast('找不到對應的回答');
            }
          }
        }
        break;
      case 'share':
        const shareElement = e.target.closest('.question, .answer');
        if (shareElement) {
          // 直接分享點擊的區塊（問題或回答）
          const shareUrl = generateShareUrl(shareElement);
          const isQuestion = shareElement.classList.contains('question');
          const toastMessage = isQuestion ? '問題鏈接已複製' : '回答鏈接已複製';
          
          if (navigator.share) {
            navigator.share({
              url: shareUrl
            });
          } else {
            copyText(shareUrl);
            showToast(toastMessage);
          }
        } else {
          // 降級處理：分享頁面鏈接
          if (navigator.share) {
            navigator.share({
              url: window.location.href
            });
          } else {
            copyText(window.location.href);
            showToast('頁面鏈接已複製');
          }
        }
        break;
      case 'clear-bookmarks':
        clearCurrentChapterBookmarks();
        break;
    }
  });

  // 浮動目錄點擊
  document.addEventListener('click', (e) => {
    // 目錄項點擊
    if (e.target.classList.contains('floating-toc-item')) {
      // 首頁的TOC項目：跳轉到其他頁面
      if (e.target.dataset.href) {
        const href = e.target.dataset.href;
        window.location.href = href;
        return;
      }
      
      // 其他頁面：頁面內跳轉
      const target = e.target.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // 移除自動關閉sidebar，讓用戶可以連續導航
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 標籤頁切換
    if (e.target.classList.contains('floating-toc-tab')) {
      const tab = e.target.dataset.tab;
      
      // 更新標籤頁狀態
      document.querySelectorAll('.floating-toc-tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      
      // 切換內容
      const tocList = document.getElementById('toc-list');
      const bookmarksList = document.getElementById('bookmarks-list');
      const tocTitle = document.getElementById('toc-title');
      
      if (tab === 'toc') {
        tocList.style.display = 'block';
        bookmarksList.style.display = 'none';
        tocTitle.textContent = '📖 章節目錄';
      } else if (tab === 'bookmarks') {
        tocList.style.display = 'none';
        bookmarksList.style.display = 'block';
        tocTitle.textContent = '🔖 我的書籤';
        renderBookmarks();
      }
    }
    
    // 書籤項點擊
    const bookmarkItem = e.target.closest('.bookmark-item');
    if (bookmarkItem && !e.target.classList.contains('bookmark-delete')) {
      const target = bookmarkItem.dataset.target;
      const element = document.querySelector(target);
      if (element) {
        // 添加臨時高亮效果
        element.style.transition = 'background-color 0.3s ease';
        element.style.backgroundColor = 'rgba(255, 105, 180, 0.2)';
        setTimeout(() => {
          element.style.backgroundColor = '';
        }, 2000);
        
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // 移除自動關閉側邊欄，讓用戶可以連續瀏覽書籤
        // floatingTOC.classList.remove('visible');
      }
    }
    
    // 書籤刪除按鈕
    if (e.target.classList.contains('bookmark-delete')) {
      e.stopPropagation();
      const bookmarkId = e.target.dataset.bookmarkId;
      if (bookmarkId) {
        removeBookmark(bookmarkId);
      }
    }
    
    // 書籤標記點擊 - 移除書籤
    if (e.target.classList.contains('bookmark-indicator')) {
      e.stopPropagation();
      const bookmarkedElement = e.target.closest('.question, .answer');
      if (bookmarkedElement) {
        // 首先檢查是否為問答書籤（通過檢查配對元素）
        let isQAPairBookmark = false;
        let answerElement = null;
        let questionElement = null;
        
        if (bookmarkedElement.classList.contains('answer')) {
          answerElement = bookmarkedElement;
          questionElement = findQuestionForAnswer(answerElement);
        } else {
          questionElement = bookmarkedElement;
          answerElement = findAnswerForQuestion(questionElement);
        }
        
        // 如果問題和回答都有書籤標記，說明是問答書籤
        if (questionElement && answerElement && 
            questionElement.classList.contains('bookmarked') && 
            answerElement.classList.contains('bookmarked')) {
          isQAPairBookmark = true;
        }
        
        if (isQAPairBookmark && answerElement) {
          // 問答書籤：使用問答切換功能移除
          toggleQAPairBookmark(answerElement);
        } else {
          // 單個元素書籤：使用原來的切換功能
          toggleBookmark(bookmarkedElement);
        }
      }
    }
  });

  function updateActiveButton(container, activeBtn) {
    container.querySelectorAll('.ctrl-btn').forEach(btn => btn.classList.remove('active'));
    activeBtn.classList.add('active');
  }

  // 滾動事件（帶節流優化）
  let scrollTimeout;
  function handleScroll() {
    updateReadingProgress();
    
    // 節流處理章節跟踪，避免過度頻繁更新
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateCurrentSection, 50);
  }
  
  window.addEventListener('scroll', handleScroll);
  updateReadingProgress();
  updateCurrentSection(); // 初始化當前章節

  // 快捷鍵支持
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'k':
          e.preventDefault();
          floatingTOC.classList.toggle('visible');
          break;
        case '[':
          e.preventDefault();
          updateFontSize(-2);
          break;
        case ']':
          e.preventDefault();
          updateFontSize(2);
          break;
      }
    }
    
    if (e.key === 'Escape') {
      floatingTOC.classList.remove('visible');
      toolbar.classList.add('hidden');
    }
  });

  // 平滑滾動章節內 TOC 與回到頂部
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, null, href);
      }
    });
  });
});
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div id="top"></div>
<div class="lang-switch">
{lang_switch_links}
</div>
<div class="nav">
<a href="{home_link}">🏠 回首頁</a>
</div>

<div class="toc">
<h3>本章目錄</h3>
{chapter_toc}
</div>

{content}

<div class="nav-footer">
{prev_link}
{next_link}
</div>
</body>
</html>
"""

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="https://cdn.jsdelivr.net/npm/minisearch@6.3.0/dist/umd/index.min.js"></script>
<script>
// 备用CDN加载
if (typeof MiniSearch === 'undefined') {{
  console.log('主CDN失败，尝试备用CDN...');
  const script = document.createElement('script');
  script.src = 'https://unpkg.com/minisearch@6.3.0/dist/umd/index.min.js';
  script.onload = function() {{
    console.log('备用CDN加载成功');
    // 重新初始化搜索
    if (typeof initSearch === 'function') {{
      initSearch();
    }}
  }};
  script.onerror = function() {{
    console.error('所有CDN都失败了，搜索功能不可用');
    const searchInput = document.getElementById('search-input');
    const searchStatus = document.getElementById('search-status');
    if (searchInput) searchInput.disabled = true;
    if (searchStatus) searchStatus.textContent = '搜索功能暂不可用（网络问题）';
  }};
  document.head.appendChild(script);
}}
</script>
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div class="lang-switch">
<a href="index.html">简体</a> | <a href="index_trad.html">繁體</a>
</div>
<h1>{book_title}</h1>

<!-- 搜索激活按钮 -->
<div class="search-activation">
  <button class="search-activate-btn" id="search-activate-btn">
    🔍 启用全文搜索
    <span class="search-activate-hint">点击启用跨章节搜索功能</span>
  </button>
</div>

<!-- 搜索功能（默认隐藏） -->
<div class="search-container" id="search-container" style="display: none;">
  <div class="search-box">
    <input type="text" id="search-input" placeholder="搜索全文内容..." autocomplete="off">
    <div class="search-status" id="search-status">正在初始化搜索功能...</div>
  </div>
  
  <!-- 搜索结果 -->
  <div class="search-results" id="search-results" style="display: none;">
    <div class="search-results-header">
      <span class="search-results-count" id="search-results-count"></span>
      <button class="search-clear" id="search-clear">清除搜索</button>
      <button class="search-collapse" id="search-collapse">收起搜索</button>
    </div>
    <ul class="search-results-list" id="search-results-list"></ul>
  </div>
</div>

<h2 id="toc-header">Table of Contents</h2>
{toc_items}
</body>
</html>
"""

# ========== 功能實作 ==========

def extract_text_content(html_content, base_filename):
    """從HTML內容中提取搜索索引數據"""
    from bs4 import BeautifulSoup
    import hashlib
    
    soup = BeautifulSoup(html_content, 'html.parser')
    search_items = []
    item_id = 0
    
    def clean_text(text):
        """清理文本，移除多余空白"""
        return ' '.join(text.split())
    
    def get_context(element, length=50):
        """獲取元素的上下文，前後各length個字符"""
        text = element.get_text()
        if len(text) <= length * 2:
            return clean_text(text)
        # 簡單截取，避免截斷詞語
        context = text[:length] + "..." + text[-length:]
        return clean_text(context)
    
    def generate_id(element, item_type, content):
        """為元素生成唯一ID"""
        if element.get('id'):
            return element.get('id')
        # 基於內容生成ID
        content_hash = hashlib.md5(content[:100].encode()).hexdigest()[:8]
        return f"{item_type}-{content_hash}"
    
    # 提取標題 (h1, h2, h3, h4)
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        if heading.get_text().strip():
            content = clean_text(heading.get_text())
            element_id = generate_id(heading, 'heading', content)
            heading['id'] = element_id  # 確保HTML中有ID
            
            weight = 4.0 if heading.name == 'h1' else (3.0 if heading.name == 'h2' else 2.0)
            search_items.append({
                'id': f"{base_filename}-{item_id}",
                'title': content,
                'type': 'heading',
                'content': content,
                'context': content,
                'url': f"{base_filename}#{element_id}",
                'weight': weight
            })
            item_id += 1
    
    # 提取問題
    for question in soup.find_all(class_='question'):
        if question.get_text().strip():
            content = clean_text(question.get_text())
            element_id = generate_id(question, 'question', content)
            question['id'] = element_id
            
            # 提取問題者和時間信息作為標題
            questioner = question.find(class_='questioner')
            time_elem = question.find(class_='question-time')
            title_parts = []
            if questioner:
                title_parts.append(questioner.get_text().strip())
            if time_elem:
                title_parts.append(time_elem.get_text().strip())
            title = ' | '.join(title_parts) if title_parts else '問題'
            
            search_items.append({
                'id': f"{base_filename}-{item_id}",
                'title': title,
                'type': 'question',
                'content': content,
                'context': get_context(question, 80),
                'url': f"{base_filename}#{element_id}",
                'weight': 3.0
            })
            item_id += 1
    
    # 提取答案
    for answer in soup.find_all(class_='answer'):
        if answer.get_text().strip():
            content = clean_text(answer.get_text())
            element_id = generate_id(answer, 'answer', content)
            answer['id'] = element_id
            
            # 提取回答者信息作為標題
            answerer = answer.find(class_='answerer')
            title = answerer.get_text().strip() if answerer else 'Taiguanglin'
            
            search_items.append({
                'id': f"{base_filename}-{item_id}",
                'title': f"{title}的回答",
                'type': 'answer',
                'content': content,
                'context': get_context(answer, 80),
                'url': f"{base_filename}#{element_id}",
                'weight': 2.0
            })
            item_id += 1
    
    # 提取其他段落內容
    for para in soup.find_all('p'):
        if para.get_text().strip() and not para.find_parent(class_=['question', 'answer']):
            content = clean_text(para.get_text())
            if len(content) > 20:  # 只索引較長的段落
                element_id = generate_id(para, 'content', content)
                para['id'] = element_id
                
                search_items.append({
                    'id': f"{base_filename}-{item_id}",
                    'title': content[:50] + "..." if len(content) > 50 else content,
                    'type': 'content',
                    'content': content,
                    'context': get_context(para, 60),
                    'url': f"{base_filename}#{element_id}",
                    'weight': 1.0
                })
                item_id += 1
    
    return search_items, str(soup)

def generate_search_index(chapters, output_folder, is_traditional=False):
    """生成搜索索引JSON文件"""
    import json
    
    all_search_items = []
    
    for chapter in chapters:
        filename = chapter['filename']
        if is_traditional:
            filename = get_traditional_filename(filename)
        
        # 從已生成的HTML文件中讀取內容
        html_file_path = os.path.join(output_folder, filename)
        if os.path.exists(html_file_path):
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            base_filename = os.path.splitext(filename)[0]
            search_items, updated_html = extract_text_content(html_content, filename)
            all_search_items.extend(search_items)
            
            # 更新HTML文件，確保所有元素都有ID
            with open(html_file_path, 'w', encoding='utf-8') as f:
                f.write(updated_html)
    
    # 按權重和相關性排序
    all_search_items.sort(key=lambda x: x['weight'], reverse=True)
    
    # 生成索引文件
    index_filename = 'search_index_trad.json' if is_traditional else 'search_index.json'
    index_path = os.path.join(output_folder, index_filename)
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(all_search_items, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 搜索索引已生成：{index_filename} (共 {len(all_search_items)} 條記錄)")

def extract_images(doc, output_folder):
    """從 Word 取出圖片到 output_folder，返回 mapping {rId: filename}"""
    rels = doc.part.rels
    image_map = {}
    img_index = 1
    for rel in rels.values():
        if "image" in rel.target_ref:
            image = rel.target_part.blob
            filename = f"image_{img_index}.png"
            filepath = os.path.join(output_folder, filename)
            with open(filepath, "wb") as f:
                f.write(image)
            image_map[rel.rId] = f"assets/images/{filename}"
            img_index += 1
    return image_map

def build_chapter_toc(toc_items, filename=None):
    """將 (level, text, anchor) 結構轉成巢狀 <ul>"""
    html = "<ul>\n"
    prev_level = 2
    for level, text, anchor in toc_items:
        link = f'{filename}#{anchor}' if filename else f'#{anchor}'
        if level > prev_level:
            html += "<ul>\n" * (level - prev_level)
        elif level < prev_level:
            html += "</ul>\n" * (prev_level - level)
        html += f'<li><a href="{link}">{text}</a></li>\n'
        prev_level = level
    while prev_level > 2:
        html += "</ul>\n"
        prev_level -= 1
    html += "</ul>"
    return html

def extract_time_from_text(text):
    """從文字中提取時間，支援多種格式，正確處理換行符"""
    # 完整時間格式：2024-02-18 10:47 或 2024-2-23 15:45  
    time_pattern1 = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})'
    match = re.search(time_pattern1, text)
    if match:
        time_str = match.group(1)
        # 提取時間後的剩餘內容，處理換行符
        remaining = text.replace(time_str, '', 1).strip()
        # 如果剩餘內容以換行符開始，去掉換行符並strip
        remaining = re.sub(r'^\s*\n\s*', '', remaining)
        return time_str, remaining
    
    # 只有日期：2024/02/03 或 18/02/2024 或 2024-02-18
    time_pattern2 = r'(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})'
    match = re.search(time_pattern2, text)
    if match:
        time_str = match.group(1)
        # 提取時間後的剩餘內容，處理換行符
        remaining = text.replace(time_str, '', 1).strip()
        # 如果剩餘內容以換行符開始，去掉換行符並strip
        remaining = re.sub(r'^\s*\n\s*', '', remaining)
        return time_str, remaining
    
    return None, text

def paragraph_to_html(paragraph, image_map, toc_list, bold_mode_state):
    """將段落轉 HTML，並處理圖片、文字與章節內書籤"""
    for run in paragraph.runs:
        drawing = run.element.find(qn('w:drawing'))
        pict = run.element.find(qn('w:pict'))
        if drawing is not None or pict is not None:
            blips = run.element.findall('.//a:blip', namespaces={'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
            for blip in blips:
                rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rId in image_map:
                    return f'<img src="{image_map[rId]}" alt="Image">'

    text = paragraph.text.strip()
    if not text:
        return ""

    # 偵測分隔線
    is_separator = bool(re.match(r"^_+$", text)) and len(text) >= 10
    if is_separator:
        bold_mode_state["bold_mode"] = False
        return "<hr>"

    style = paragraph.style.name.lower()
    if "heading 1" in style:
        return f"<h1>{text}</h1>"
    elif "heading 2" in style:
        anchor = slugify(text)
        toc_list.append((2, text, anchor))
        return f'<h2 id="{anchor}">{text}</h2>'
    elif "heading 3" in style:
        anchor = slugify(text)
        toc_list.append((3, text, anchor))
        return f'<h3 id="{anchor}">{text}</h3>'
    else:
        # 檢查是否為 Taiguanglin 回答
        taiguanglin_match = re.match(r'^(Taiguanglin|taiguanglin)[:：]\s*(.*)', text, re.IGNORECASE | re.DOTALL)
        if taiguanglin_match:
            bold_mode_state["bold_mode"] = True
            answer_content = taiguanglin_match.group(2)
            time_info, clean_content = extract_time_from_text(answer_content)
            
            # 如果有時間則顯示，否則不顯示時間部分
            time_html = f'<span class="question-time">{time_info}</span>' if time_info else ''
            
            return f'''<div class="answer">
    <div class="answer-meta">
        <span class="answerer">Taiguanglin</span>
        {time_html}
    </div>
    <div class="answer-text">{clean_content}</div>
</div>'''
        
        # 檢查是否為提問者格式（姓名：時間 內容）
        questioner_match = re.match(r'^([^：:]+)[:：]\s*(.*)', text, re.DOTALL)
        if questioner_match and not bold_mode_state["bold_mode"]:
            questioner_name = questioner_match.group(1).strip()
            question_content = questioner_match.group(2).strip()
            
            # 如果 question_content 為空，表示只有姓名，沒有時間和內容
            if not question_content:
                return f'''<div class="question">
    <div class="question-meta">
        <span class="questioner">{questioner_name}</span>
    </div>
    <div class="question-text"></div>
</div>'''
            
            # 嘗試提取時間
            time_info, clean_content = extract_time_from_text(question_content)
            
            # 如果提取到時間但內容為空，說明這行只有姓名和時間，問題內容在後續段落
            if time_info and not clean_content.strip():
                time_html = f'<span class="question-time">{time_info}</span>'
                return f'''<div class="question">
    <div class="question-meta">
        <span class="questioner">{questioner_name}</span>
        {time_html}
    </div>
    <div class="question-text"></div>
</div>'''
            
            # 如果沒有時間信息，整個 question_content 就是問題內容
            if not time_info:
                clean_content = question_content
                time_html = ''
            else:
                time_html = f'<span class="question-time">{time_info}</span>'
            
            return f'''<div class="question">
    <div class="question-meta">
        <span class="questioner">{questioner_name}</span>
        {time_html}
    </div>
    <div class="question-text">{clean_content}</div>
</div>'''
        
        # 一般段落處理
        if bold_mode_state["bold_mode"]:
            # 在回答模式中，作為回答內容的延續
            return f'<div class="answer-text">{text}</div>'
        else:
            return f"<p>{text}</p>"

def safe_filename(title, index):
    slug = slugify(title)
    if not slug:
        slug = f"chapter{index}"
    return f"{index:02d}-{slug}.html"

def build_index_toc(chapters, is_traditional=False):
    """建立首頁目錄，is_traditional=True 時使用繁體版檔案名"""
    html = "<ul>\n"
    for ch in chapters:
        filename = ch["filename"]
        if is_traditional:
            filename = filename.replace(".html", "_trad.html")
        
        html += f'<li><a href="{filename}">{ch["title"]}</a>\n'
        if ch["toc_items"]:
            html += build_chapter_toc(ch["toc_items"], filename)
        html += "</li>\n"
    html += "</ul>"
    return html

def merge_qa_blocks(content_blocks):
    """合併連續的問答區塊"""
    merged_blocks = []
    i = 0
    
    while i < len(content_blocks):
        current_block = content_blocks[i]
        
        # 檢查是否為問題開始
        if current_block.startswith('<div class="question">'):
            # 收集所有連續的問題內容
            question_parts = [current_block]
            i += 1
            
            # 收集後續的普通段落作為問題內容的延續
            while i < len(content_blocks):
                next_block = content_blocks[i]
                
                # 如果遇到新的問題、回答或標題，停止收集
                if (next_block.startswith('<div class="question">') or 
                    next_block.startswith('<div class="answer">') or
                    next_block.startswith('<h1>') or 
                    next_block.startswith('<h2>') or 
                    next_block.startswith('<h3>') or
                    next_block.startswith('<hr>')):
                    break
                
                # 如果是普通段落，添加為問題內容
                if next_block.startswith('<p>'):
                    content = next_block.replace('<p>', '').replace('</p>', '')
                    question_parts.append(f'    <div class="question-text">{content}</div>')
                    i += 1
                else:
                    break
            
            # 確保問題區塊正確結束
            if not question_parts[-1].endswith('</div>'):
                question_parts.append('</div>')
                
            merged_blocks.append('\n'.join(question_parts))
            
        # 檢查是否為回答開始
        elif current_block.startswith('<div class="answer">'):
            # 收集所有連續的回答內容
            answer_parts = [current_block]
            i += 1
            
            # 收集後續的 answer-text div 或普通段落（如果是多段落回答）
            while i < len(content_blocks):
                next_block = content_blocks[i]
                
                # 如果遇到新的問題、回答或標題，停止收集
                if (next_block.startswith('<div class="question">') or 
                    next_block.startswith('<div class="answer">') or
                    next_block.startswith('<h1>') or 
                    next_block.startswith('<h2>') or 
                    next_block.startswith('<h3>') or
                    next_block.startswith('<hr>')):
                    break
                
                # 如果是answer-text或普通段落，添加為回答內容
                if next_block.startswith('<div class="answer-text">'):
                    answer_parts.append('    ' + next_block)
                    i += 1
                elif next_block.startswith('<p>'):
                    content = next_block.replace('<p>', '').replace('</p>', '')
                    answer_parts.append(f'    <div class="answer-text">{content}</div>')
                    i += 1
                else:
                    break
            
            # 確保回答區塊正確結束
            if not answer_parts[-1].endswith('</div>'):
                answer_parts.append('</div>')
                
            merged_blocks.append('\n'.join(answer_parts))
            
        else:
            merged_blocks.append(current_block)
            i += 1
    
    return merged_blocks

def insert_back_to_top(content_blocks):
    """根據章節內 H2/H3 結構插入回到頂部連結"""
    # 先合併問答區塊
    content_blocks = merge_qa_blocks(content_blocks)
    
    output_blocks = []
    h3_count = 0
    h2_count = 0
    last_heading_type = None

    for block in content_blocks:
        is_h2 = block.startswith("<h2 ")
        is_h3 = block.startswith("<h3 ")

        if is_h3:
            if last_heading_type == "h3":
                output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
            h3_count += 1
            last_heading_type = "h3"
        elif is_h2 and h3_count == 0:  # 無 H3 時 H2 也加按鈕
            if last_heading_type == "h2":
                output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
            h2_count += 1
            last_heading_type = "h2"

        output_blocks.append(block)

    # 補最後一個小節的回到頂部
    output_blocks.append('<div class="back-to-top"><a href="#top">⬆️ 回到本章目錄</a></div>')
    return output_blocks

def get_traditional_filename(filename):
    """將簡體檔名轉換為繁體檔名"""
    return filename.replace(".html", "_trad.html")

def get_simplified_filename(filename):
    """將繁體檔名轉換為簡體檔名"""
    return filename.replace("_trad.html", ".html")

def convert_word_to_ebook(input_file, output_folder, generate_search=True, generate_traditional=True):
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(os.path.join(output_folder, "assets/css"), exist_ok=True)
    os.makedirs(os.path.join(output_folder, "assets/js"), exist_ok=True)
    os.makedirs(os.path.join(output_folder, "assets/images"), exist_ok=True)

    doc = Document(input_file)
    image_map = extract_images(doc, os.path.join(output_folder, "assets/images"))

    chapters = []
    current_chapter = None
    toc_items = []
    bold_mode_state = {"bold_mode": False}
    content_blocks = []

    for paragraph in doc.paragraphs:
        html = paragraph_to_html(paragraph, image_map, toc_items, bold_mode_state)
        if not html:
            continue

        if html.startswith("<h1>"):  # 新章節
            if current_chapter:
                content_blocks = insert_back_to_top(content_blocks)
                current_chapter["content"] = "\n".join(content_blocks)
                current_chapter["chapter_toc"] = build_chapter_toc(toc_items)
                current_chapter["toc_items"] = toc_items[:]
                chapters.append(current_chapter)

            title = re.sub(r"<.*?>", "", html)
            filename = safe_filename(title, len(chapters)+1)
            current_chapter = {"title": title, "filename": filename, "content": "", "chapter_toc": "", "toc_items": []}
            toc_items = []
            content_blocks = [html]
        else:
            if current_chapter:
                content_blocks.append(html)

    if current_chapter:
        content_blocks = insert_back_to_top(content_blocks)
        current_chapter["content"] = "\n".join(content_blocks)
        current_chapter["chapter_toc"] = build_chapter_toc(toc_items)
        current_chapter["toc_items"] = toc_items[:]
        chapters.append(current_chapter)

    # ========== 生成簡體 HTML ==========
    for i, ch in enumerate(chapters):
        # 簡體版的上下章導航
        prev_link = f'<a href="{chapters[i-1]["filename"]}">⬅️ 上一章</a>' if i > 0 else ""
        next_link = f'<a href="{chapters[i+1]["filename"]}">下一章 ➡️</a>' if i < len(chapters)-1 else ""
        
        # 簡體版的語言切換連結
        trad_filename = get_traditional_filename(ch["filename"])
        lang_switch_links = f'<a href="{ch["filename"]}">简体</a> | <a href="{trad_filename}">繁體</a>'
        
        html_page = HTML_TEMPLATE.format(
            title=ch["title"],
            chapter_toc=ch["chapter_toc"],
            content=ch["content"],
            prev_link=prev_link,
            next_link=next_link,
            home_link="index.html",
            lang_switch_links=lang_switch_links
        )
        with open(os.path.join(output_folder, ch["filename"]), "w", encoding="utf-8") as f:
            f.write(html_page)

    # 簡體 index.html
    book_title = os.path.splitext(os.path.basename(input_file))[0]
    toc_html = build_index_toc(chapters, is_traditional=False)
    with open(os.path.join(output_folder, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_TEMPLATE.format(book_title=book_title, toc_items=toc_html))

    # ========== 生成繁體 HTML ==========
    trad_chapters = []  # 初始化，即使不生成繁体版也需要这个变量
    
    if generate_traditional:
        print("🈴 正在生成繁體版...")
        cc = OpenCC('s2t')
        
        for i, ch in enumerate(chapters):
            trad_filename = get_traditional_filename(ch["filename"])
            
            # 繁體版的上下章導航
            prev_link = ""
            next_link = ""
            if i > 0:
                prev_trad_filename = get_traditional_filename(chapters[i-1]["filename"])
                prev_link = f'<a href="{prev_trad_filename}">⬅️ 上一章</a>'
            if i < len(chapters)-1:
                next_trad_filename = get_traditional_filename(chapters[i+1]["filename"])
                next_link = f'<a href="{next_trad_filename}">下一章 ➡️</a>'
            
            # 繁體版的語言切換連結
            lang_switch_links = f'<a href="{ch["filename"]}">简体</a> | <a href="{trad_filename}">繁體</a>'
            
            html_page = HTML_TEMPLATE.format(
                title=cc.convert(ch["title"]),
                chapter_toc=cc.convert(ch["chapter_toc"]),
                content=cc.convert(ch["content"]),
                prev_link=cc.convert(prev_link),
                next_link=cc.convert(next_link),
                home_link="index_trad.html",
                lang_switch_links=cc.convert(lang_switch_links)
            )
            with open(os.path.join(output_folder, trad_filename), "w", encoding="utf-8") as f:
                f.write(html_page)

        # 繁體 index_trad.html - 使用繁體版檔案名的 TOC
        for ch in chapters:
            trad_ch = ch.copy()
            trad_ch["title"] = cc.convert(ch["title"])
            trad_ch["toc_items"] = [(level, cc.convert(text), anchor) for level, text, anchor in ch["toc_items"]]
            trad_chapters.append(trad_ch)
        
        trad_toc_html = build_index_toc(trad_chapters, is_traditional=True)
        with open(os.path.join(output_folder, "index_trad.html"), "w", encoding="utf-8") as f:
            f.write(INDEX_TEMPLATE.format(
                book_title=cc.convert(book_title), 
                toc_items=trad_toc_html
            ))
    else:
        print("⏭️  跳過繁體版生成")

    # ========== 生成搜索索引 ==========
    if generate_search:
        print("🔍 正在生成搜索索引...")
        
        # 生成簡體版搜索索引
        generate_search_index(chapters, output_folder, is_traditional=False)
        
        # 生成繁體版搜索索引（如果有繁体版）
        if generate_traditional and trad_chapters:
            generate_search_index(trad_chapters, output_folder, is_traditional=True)
    else:
        print("⏭️  跳過搜索索引生成")

    # 寫入 CSS 與 JS
    with open(os.path.join(output_folder, "assets/css/style.css"), "w", encoding="utf-8") as f:
        f.write(CSS_CONTENT)
    with open(os.path.join(output_folder, "assets/js/script.js"), "w", encoding="utf-8") as f:
        f.write(JS_CONTENT)

    print(f"✅ 轉換完成！HTML 電子書已輸出到 {output_folder}，含簡體與繁體版本")
    print(f"📖 簡體版首頁: {output_folder}/index.html")
    print(f"📖 繁體版首頁: {output_folder}/index_trad.html")

# ========== 主程式入口 ==========
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='將Word文檔轉換為HTML電子書',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python word2ebook.py input.docx output_folder                    # 生成完整版本
  python word2ebook.py input.docx output_folder --fast            # 快速模式
  python word2ebook.py input.docx output_folder --skip-search     # 跳過搜索索引
  python word2ebook.py input.docx output_folder --skip-traditional # 跳過繁體版
        """
    )
    
    parser.add_argument('input_file', help='輸入的Word文檔路徑')
    parser.add_argument('output_folder', help='輸出HTML電子書的目錄')
    
    parser.add_argument('--skip-search', action='store_true', 
                       help='跳過搜索索引生成（加快轉換速度）')
    parser.add_argument('--skip-traditional', action='store_true',
                       help='跳過繁體版生成（加快轉換速度）')
    parser.add_argument('--fast', action='store_true',
                       help='快速模式：跳過搜索索引和繁體版生成')
    
    args = parser.parse_args()
    
    # 處理快速模式
    generate_search = not (args.skip_search or args.fast)
    generate_traditional = not (args.skip_traditional or args.fast)
    
    # 顯示配置信息
    print("📋 轉換配置:")
    print(f"   輸入文件: {args.input_file}")
    print(f"   輸出目錄: {args.output_folder}")
    print(f"   生成繁體版: {'✅' if generate_traditional else '❌'}")
    print(f"   生成搜索索引: {'✅' if generate_search else '❌'}")
    print()
    
    convert_word_to_ebook(args.input_file, args.output_folder, 
                         generate_search=generate_search, 
                         generate_traditional=generate_traditional)