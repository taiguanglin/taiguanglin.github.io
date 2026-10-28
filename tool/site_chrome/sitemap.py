#!/usr/bin/env python3
"""sitemap.xml 的單一產生器（SoT）。

以前 sitemap.xml 是「手工維護 + `tool/stories2html/build_index.py` 打補丁」，
結果電子書的 `<lastmod>` 停在 2026-10-10，內容卻在 10-27／10-28 更新過——
Google 官方說明 `<lastmod>` 只有在「持續且可驗證準確」時才會被採用。

本腳本改成**由實際發布的檔案反推 sitemap**：

- 只收錄「可索引」的 HTML：帶 `noindex` 或 `meta refresh` 的頁一律跳過
  （舊章跳轉頁、音檔校稿頁等）。
- `<lastmod>` 取自該檔案在 git 的最後提交日期（可驗證、與發布內容同步）；
  尚未提交的新檔用檔案 mtime。
- 不再輸出 `<priority>` / `<changefreq>`：Google 直接忽略這兩個欄位，
  百度官方也明說 sitemap 的 priority 不影響排名，留著只造成誤解。
- 輸出格式與舊檔一致（分區註解），方便人工 diff。

用法：

    python3 tool/site_chrome/sitemap.py            # 重寫 sitemap.xml
    python3 tool/site_chrome/sitemap.py --check    # 只檢查是否與現況一致（CI 用）

站台網址與章節清單集中在下方常數；新增頁面請更新這裡，不要再手改 XML。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://taiguanglin.info"
SITEMAP_PATH = ROOT / "sitemap.xml"

# 站點首頁與固定落地頁：(檔案, 註解, 站台路徑)
ROOT_PAGES: list[tuple[str, str, str]] = [
    ("index.html", "網站首頁", "/"),
    ("stories.html", "實修故事列表", "/stories.html"),
    ("wenda2.html", "問答錄主頁面", "/wenda2.html"),
    ("infographic.html", "佛法名詞圖解", "/infographic.html"),
    ("mindmap.html", "名詞關聯心智圖", "/mindmap.html"),
    ("wenda2_mindmap.html", "坐禪之問答錄2 名詞心智圖", "/wenda2_mindmap.html"),
]

# 電子書輸出目錄（掃描其 *.html；跳過 noindex / meta refresh 頁）→ 區段標題
EBOOK_DIRS = {
    "wenda2_ebook": "問答錄完整版2 電子書",
    "ebook": "坐禪與講經系列電子書",
}

# 問答錄主題目錄（wenda2/ 是手工維護的 12 章 TOC 頁，非電子書產物）
WENDA2_DIR = "wenda2"


def _git_lastmod(rel_path: str) -> str:
    """檔案最後一次被 git 提交修改的日期（YYYY-MM-DD）。

    沒有 git 紀錄（新檔、尚未 commit）時退回檔案 mtime；再不行就用今天。
    """
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        proc = None
    if proc is not None and proc.stdout.strip():
        return proc.stdout.strip().splitlines()[0].strip()
    path = ROOT / rel_path
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return date.today().isoformat()


def _is_indexable(path: Path) -> bool:
    """可索引頁判定：帶 noindex 或 meta refresh 的頁面不得進 sitemap。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if re.search(r'<meta\s+name="robots"[^>]*noindex', text, re.I):
        return False
    if re.search(r'<meta\s+http-equiv="refresh"', text, re.I):
        return False
    return True


def _story_entries() -> list[tuple[str, str, str]]:
    """實修故事（逐篇 HTML）——順序與註解沿用 stories2html 的 metadata SoT。"""
    docs_path = ROOT / "tool" / "stories2html" / "docs.py"
    entries: list[tuple[str, str, str]] = []
    if not docs_path.exists():
        return entries
    import importlib.util

    spec = importlib.util.spec_from_file_location("_stories_docs", docs_path)
    if spec is None or spec.loader is None:
        return entries
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for category in module.CATEGORY_ORDER:
        for doc in [d for d in module.DOCS if d["category"] == category]:
            slug = doc["slug"]
            rel = f"stories/{slug}.html"
            if not (ROOT / rel).exists():
                continue
            entries.append((rel, f"{doc['category']}｜{doc['title']}", f"/stories/{slug}.html"))
    return entries


def _wenda2_entries() -> list[tuple[str, str, str]]:
    """wenda2/ 手工目錄頁。"""
    entries: list[tuple[str, str, str]] = []
    folder = ROOT / WENDA2_DIR
    if not folder.is_dir():
        return entries
    for path in sorted(folder.glob("chapter-*.html")):
        rel = f"{WENDA2_DIR}/{path.name}"
        entries.append((rel, path.stem.replace("-", " "), f"/{WENDA2_DIR}/{path.name}"))
    return entries


def build_sections() -> list[tuple[str, list[tuple[str, str, str]]]]:
    """組出 (區段標題, [(來源檔, 註解, 站台路徑)])。"""
    sections: list[tuple[str, list[tuple[str, str, str]]]] = [
        ("主要頁面", ROOT_PAGES),
        ("問答錄章節（主題目錄）", _wenda2_entries()),
    ]
    for dirname, title in EBOOK_DIRS.items():
        sections.append((title, _ebook_entries_for_dir(dirname)))
    sections.append(("實修故事（逐篇 HTML）", _story_entries()))
    return [(title, items) for title, items in sections if items]


def _ebook_entries_for_dir(dirname: str) -> list[tuple[str, str, str]]:
    folder = ROOT / dirname
    entries: list[tuple[str, str, str]] = []
    if not folder.is_dir():
        return entries
    for path in sorted(folder.glob("*.html")):
        if not _is_indexable(path):
            continue
        rel = f"{dirname}/{path.name}"
        entries.append((rel, path.stem, f"/{dirname}/{path.name}"))
    return entries


def render_sitemap() -> str:
    """產生 sitemap.xml 全文。"""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
        '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
        "",
    ]
    for title, items in build_sections():
        lines.append(f"  <!-- ============ {title} ============ -->")
        for rel, comment, site_path in items:
            url = SITE + site_path
            lines.append(f"  <!-- {comment} -->")
            lines.append("  <url>")
            lines.append(f"    <loc>{url}</loc>")
            lines.append(f"    <lastmod>{_git_lastmod(rel)}</lastmod>")
            lines.append("  </url>")
        lines.append("")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def write_sitemap() -> Path:
    content = render_sitemap()
    SITEMAP_PATH.write_text(content, encoding="utf-8")
    return SITEMAP_PATH


def check_sitemap() -> int:
    """比對現況 sitemap.xml 與產生結果；一致回 0，不一致回 1。"""
    if not SITEMAP_PATH.exists():
        print("sitemap.xml 不存在")
        return 1
    current = SITEMAP_PATH.read_text(encoding="utf-8")
    expected = render_sitemap()
    if current == expected:
        print("sitemap.xml：與產生器一致 ✅")
        return 0
    print("sitemap.xml：與產生器不一致 ❌（執行 python3 tool/site_chrome/sitemap.py 產生）")
    import difflib

    diff = list(
        difflib.unified_diff(
            current.splitlines(), expected.splitlines(), "current", "expected", lineterm=""
        )
    )
    for line in diff[:60]:
        print("  " + line)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="產生／檢查 sitemap.xml")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只檢查 sitemap.xml 是否與產生器一致（不寫檔）",
    )
    args = parser.parse_args(argv)
    if args.check:
        return check_sitemap()
    path = write_sitemap()
    count = render_sitemap().count("<url>")
    print(f"✅ sitemap.xml 已更新（{count} 個 URL）：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
