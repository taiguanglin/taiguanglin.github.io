import os
import sys
import shutil
import re
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
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    flex-wrap: wrap;
}

.questioner {
    font-weight: 600;
    color: #e75480;
    font-size: 14px;
}

.question-time {
    background: #f8c8dc;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 12px;
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
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}

.answerer {
    font-weight: 700;
    color: #ff69b4;
    font-size: 14px;
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

.toggle-dark { position: fixed; top: 20px; right: 20px; cursor: pointer; padding: 6px 12px; background: #f8c8dc; border-radius: 5px; }
body.dark-mode .toggle-dark { background: #5a2d49; color: #fff; }
.back-to-top { text-align: right; margin: 20px 0; }
.back-to-top a { font-size: 0.9em; color: #d44d75; }
.back-to-top a:hover { color: #ff69b4; }
.lang-switch { text-align: right; margin-bottom: 10px; }
.lang-switch a { font-size: 0.9em; margin: 0 5px; }

/* 響應式設計 */
@media (max-width: 768px) {
    .question-meta, .answer-meta { flex-direction: column; align-items: flex-start; gap: 5px; }
    .question, .answer { padding: 12px; }
    .questioner, .answerer { font-size: 13px; }
    .question-time { font-size: 11px; }
}
"""

JS_CONTENT = """\
document.addEventListener('DOMContentLoaded', function() {
  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'toggle-dark';
  toggleBtn.textContent = localStorage.getItem('darkMode') === 'true' ? '☀️ 日間模式' : '🌙 夜間模式';
  document.body.appendChild(toggleBtn);

  if(localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }

  toggleBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDark);
    toggleBtn.textContent = isDark ? '☀️ 日間模式' : '🌙 夜間模式';
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
<title>{book_title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div class="lang-switch">
<a href="index.html">简体</a> | <a href="index_trad.html">繁體</a>
</div>
<h1>{book_title}</h1>
<h2>Table of Contents</h2>
{toc_items}
</body>
</html>
"""

# ========== 功能實作 ==========

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

def convert_word_to_ebook(input_file, output_folder):
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
    trad_chapters = []
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
    if len(sys.argv) < 3:
        print("用法: python word2ebook.py input.docx output_folder")
        sys.exit(1)

    input_file = sys.argv[1]
    output_folder = sys.argv[2]
    convert_word_to_ebook(input_file, output_folder)