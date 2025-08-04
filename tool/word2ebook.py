import os
import sys
import shutil
import re
from docx import Document
from docx.oxml.ns import qn
from slugify import slugify

# ========== CSS & JS 模板 ==========
CSS_CONTENT = """\
body { font-family: 'Helvetica', sans-serif; margin: 40px auto; max-width: 800px; line-height: 1.6; background: #fff; color: #333; transition: 0.3s; }
h1 { color: #2c3e50; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
h2 { color: #34495e; margin-top: 40px; }
p { margin: 15px 0; }
img { max-width: 100%; display: block; margin: 20px auto; }
a { color: #2980b9; text-decoration: none; }
a:hover { text-decoration: underline; }
.nav { margin-bottom: 20px; }
.nav-footer { display: flex; justify-content: space-between; margin-top: 50px; }
.toc { margin: 20px 0; }
body.dark-mode { background: #121212; color: #ddd; }
body.dark-mode a { color: #81caff; }
.toggle-dark { position: fixed; top: 20px; right: 20px; cursor: pointer; padding: 6px 12px; background: #eee; border-radius: 5px; }
body.dark-mode .toggle-dark { background: #333; color: #fff; }
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
});
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/script.js" defer></script>
</head>
<body>
<div class="nav">
<a href="index.html">🏠 回首頁</a>
</div>

<div class="toc">
<h3>本章目錄</h3>
<ul>
{chapter_toc}
</ul>
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
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{book_title}</title>
<link rel="stylesheet" href="assets/css/style.css">
<script src="assets/js/script.js" defer></script>
</head>
<body>
<h1>{book_title}</h1>
<h2>Table of Contents</h2>
<ul>
{toc_items}
</ul>
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

def paragraph_to_html(paragraph, image_map, chapter_toc_list):
    """
    將段落轉 HTML，並處理圖片、文字與章節內書籤
    """
    # 檢查圖片
    for run in paragraph.runs:
        drawing = run.element.find(qn('w:drawing'))
        pict = run.element.find(qn('w:pict'))
        if drawing is not None or pict is not None:
            # 找到圖片的 <a:blip>
            blips = run.element.findall('.//a:blip', namespaces={'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
            for blip in blips:
                rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rId in image_map:
                    return f'<img src="{image_map[rId]}" alt="Image">'
            return ""

    # 普通文字
    text = paragraph.text.strip()
    if not text:
        return ""
    style = paragraph.style.name.lower()
    if "heading 1" in style:
        return f"<h1>{text}</h1>"
    elif "heading 2" in style:
        anchor = slugify(text)
        chapter_toc_list.append(f'<li><a href="#{anchor}">{text}</a></li>')
        return f'<h2 id="{anchor}">{text}</h2>'
    else:
        return f"<p>{text}</p>"

def safe_filename(title, index):
    """產生安全的英文檔名"""
    slug = slugify(title)
    if not slug:
        slug = f"chapter{index}"
    return f"{index:02d}-{slug}.html"

def convert_word_to_ebook(input_file, output_folder):
    # 建立輸出資料夾
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(os.path.join(output_folder, "assets/css"), exist_ok=True)
    os.makedirs(os.path.join(output_folder, "assets/js"), exist_ok=True)
    os.makedirs(os.path.join(output_folder, "assets/images"), exist_ok=True)

    # 讀取 Word 文件
    doc = Document(input_file)
    image_map = extract_images(doc, os.path.join(output_folder, "assets/images"))

    chapters = []
    current_chapter = None
    chapter_toc = []

    for paragraph in doc.paragraphs:
        html = paragraph_to_html(paragraph, image_map, chapter_toc)
        if not html:
            continue

        if html.startswith("<h1>"):  # 新章節
            if current_chapter:
                current_chapter["content"] = "\n".join(current_chapter["content"])
                current_chapter["chapter_toc"] = "\n".join(chapter_toc)
                chapters.append(current_chapter)

            title = re.sub(r"<.*?>", "", html)
            filename = safe_filename(title, len(chapters)+1)
            current_chapter = {"title": title, "filename": filename, "content": [html], "chapter_toc": ""}
            chapter_toc = []
        else:
            if current_chapter:
                current_chapter["content"].append(html)

    if current_chapter:
        current_chapter["content"] = "\n".join(current_chapter["content"])
        current_chapter["chapter_toc"] = "\n".join(chapter_toc)
        chapters.append(current_chapter)

    # 生成章節 HTML
    for i, ch in enumerate(chapters):
        prev_link = f'<a href="{chapters[i-1]["filename"]}">⬅️ 上一章</a>' if i > 0 else ""
        next_link = f'<a href="{chapters[i+1]["filename"]}">下一章 ➡️</a>' if i < len(chapters)-1 else ""
        html_page = HTML_TEMPLATE.format(
            title=ch["title"],
            chapter_toc=ch["chapter_toc"],
            content=ch["content"],
            prev_link=prev_link,
            next_link=next_link
        )
        with open(os.path.join(output_folder, ch["filename"]), "w", encoding="utf-8") as f:
            f.write(html_page)

    # 生成目錄 index.html
    toc_items = "\n".join([f'<li><a href="{ch["filename"]}">{ch["title"]}</a></li>' for ch in chapters])
    book_title = os.path.splitext(os.path.basename(input_file))[0]
    with open(os.path.join(output_folder, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_TEMPLATE.format(book_title=book_title, toc_items=toc_items))

    # 寫入 CSS 與 JS
    with open(os.path.join(output_folder, "assets/css/style.css"), "w", encoding="utf-8") as f:
        f.write(CSS_CONTENT)
    with open(os.path.join(output_folder, "assets/js/script.js"), "w", encoding="utf-8") as f:
        f.write(JS_CONTENT)

    print(f"✅ 轉換完成！HTML 電子書已輸出到 {output_folder}")

# ========== 主程式入口 ==========
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python word2ebook.py input.docx output_folder")
        sys.exit(1)

    input_file = sys.argv[1]
    output_folder = sys.argv[2]
    convert_word_to_ebook(input_file, output_folder)

