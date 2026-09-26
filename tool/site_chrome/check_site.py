#!/usr/bin/env python3
"""Fast checks for shared chrome and content invariants."""

from __future__ import annotations

import re
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_NOTICE = "本頁圖解由 AI 生成，內容僅供參考，請以 Tai 師父原文教導為準。"
AI_PAGES = (
    "infographic.html", "mindmap.html",
    "wenda2_mindmap.html", "session_knowledge.html",
)
KNOWLEDGE_PAGES = (
    "mindmap.html", "wenda2_mindmap.html",
)
SEO_PAGES = ("infographic.html",) + KNOWLEDGE_PAGES
# 內部頁：部署於公開 Pages，但不得被搜尋引擎索引。
# 必須同時滿足 (a) 頁面自帶 noindex、(b) 不在 sitemap.xml、(c) robots.txt 有 Disallow。
# 注意 (a) 與 (c) 不可互相取代：robots.txt 封鎖會讓爬蟲讀不到 noindex，反而殘留索引。
NOINDEX_PAGES = (
    "session_knowledge.html",
    "audio_map/index.html",
    "audio_map2/index.html",
    "audio_map3/index.html",
)
ROBOTS_TXT_DISALLOW = (
    "/audio_map/",
    "/audio_map2/",
    "/audio_map3/",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def main() -> int:
    errors: list[str] = []

    sync = subprocess.run(
        [sys.executable, str(ROOT / "tool/site_chrome/sync.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if sync.returncode:
        errors.append(sync.stdout.strip() or sync.stderr.strip())

    for rel in AI_PAGES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if AI_NOTICE not in text:
            errors.append(f"{rel}: missing AI notice")

    # 內部頁：noindex + 不在 sitemap + robots.txt Disallow
    sitemap_text = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    robots_text = (ROOT / "robots.txt").read_text(encoding="utf-8")
    for rel in NOINDEX_PAGES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if not re.search(r'<meta\s+name="robots"[^>]*noindex', text, re.I):
            errors.append(f"{rel}: internal page missing noindex")
        if f"taiguanglin.info/{rel}" in sitemap_text:
            errors.append(f"{rel}: internal page must not be in sitemap.xml")
    for path in ROBOTS_TXT_DISALLOW:
        if f"Disallow: {path}" not in robots_text:
            errors.append(f"robots.txt: missing 'Disallow: {path}'")

    for rel in KNOWLEDGE_PAGES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if f"https://taiguanglin.info/{rel}" not in text:
            errors.append(f"{rel}: missing self canonical")
        if "/lang-switch.js" not in text:
            errors.append(f"{rel}: missing lang-switch.js")

    for rel in SEO_PAGES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if text.count('type="application/ld+json"') != 1:
            errors.append(f"{rel}: expected one JSON-LD block")
        if text.count("STRUCTURED-DATA:START") != 1:
            errors.append(f"{rel}: structured-data marker missing or duplicated")
        if '"@type":"WebPage"' not in text:
            errors.append(f"{rel}: WebPage structured data missing")
        if '"@type":"BreadcrumbList"' not in text:
            errors.append(f"{rel}: BreadcrumbList structured data missing")

    chrome_paths = list(ROOT.glob("*.html"))
    chrome_paths += list((ROOT / "wenda2").glob("*.html"))
    chrome_paths += list((ROOT / "stories").glob("*.html"))
    checked = 0
    for path in chrome_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if 'id="navbar"' not in text or "shared.js" not in text:
            continue
        checked += 1
        ids = re.findall(r'\bid="([^"]+)"', text)
        duplicates = sorted(k for k, count in Counter(ids).items() if count > 1)
        if duplicates:
            errors.append(f"{path.relative_to(ROOT)}: duplicate ids {duplicates}")
        if text.count('class="nav-dropdown-item') != 3:
            errors.append(f"{path.relative_to(ROOT)}: expected 3 knowledge menu items")
        toggle = re.search(
            r'<button[^>]*class="[^"]*\bnav-dropdown-toggle\b[^"]*"[^>]*>',
            text,
        )
        if not toggle:
            errors.append(f"{path.relative_to(ROOT)}: accessible dropdown button missing")
        else:
            tag = toggle.group(0)
            for required in (
                'type="button"',
                'aria-expanded="false"',
                'aria-controls="nav-knowledge-menu"',
            ):
                if required not in tag:
                    errors.append(f"{path.relative_to(ROOT)}: {required} missing")
        if 'id="nav-knowledge-menu"' not in text:
            errors.append(f"{path.relative_to(ROOT)}: controlled dropdown menu missing")

    link_cache: dict[Path, set[str]] = {}
    broken_links: list[str] = []
    for path in chrome_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if 'id="navbar"' not in text or "shared.js" not in text:
            continue
        parser = LinkParser()
        parser.feed(text)
        for href in parser.links:
            parsed = urlsplit(href)
            if parsed.scheme or href.startswith("//"):
                continue
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            raw_path = unquote(parsed.path)
            if raw_path.startswith("/"):
                # 站內絕對路徑（404.html 在任意不存在路徑下渲染，連結一律用 /…）
                target = ROOT / raw_path.lstrip("/")
            else:
                target = path if not raw_path else path.parent / raw_path
            if not target.exists():
                broken_links.append(
                    f"{path.relative_to(ROOT)} -> {href} (missing target)"
                )
                continue
            if parsed.fragment and target.is_file() and target.suffix == ".html":
                target = target.resolve()
                if target not in link_cache:
                    target_text = target.read_text(encoding="utf-8", errors="ignore")
                    ids = set(re.findall(r'\b(?:id|name)="([^"]+)"', target_text))
                    link_cache[target] = ids
                fragment = unquote(parsed.fragment)
                if fragment not in link_cache[target]:
                    broken_links.append(
                        f"{path.relative_to(ROOT)} -> {href} (missing anchor)"
                    )
    for broken in broken_links:
        errors.append(broken)

    for url in re.findall(r"<loc>(.*?)</loc>", sitemap_text):
        rel = unquote(urlsplit(url).path).lstrip("/") or "index.html"
        target = ROOT / rel
        if rel.endswith("/"):
            target = target / "index.html"
        if not target.exists():
            errors.append(f"sitemap.xml -> {url} (missing target)")

    image_issues: list[str] = []
    for rel in ("index.html", "infographic.html", "stories.html"):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<img\b[^>]*>", text):
            tag = match.group(0)
            src_match = re.search(r'\bsrc="([^"]*)"', tag)
            if not src_match:
                continue
            src = src_match.group(1)
            if src.startswith(("http:", "https:", "//", "data:")):
                continue
            element_id = re.search(r'\bid="([^"]*)"', tag)
            element_id = element_id.group(1) if element_id else ""
            if element_id == "lightbox-img":
                if "decoding=" not in tag:
                    image_issues.append(f"{rel}: lightbox img missing decoding")
                continue
            for required in ("width=", "height=", "decoding="):
                if required not in tag:
                    image_issues.append(f"{rel}: <img src=\"{src}\"> missing {required}")
            # 首屏主圖可刻意 eager，但必須明示優先序；其餘內容圖一律延後載入。
            if "loading=" not in tag and 'fetchpriority="high"' not in tag:
                image_issues.append(
                    f"{rel}: <img src=\"{src}\"> needs loading=lazy or fetchpriority=high"
                )
    errors.extend(image_issues)

    mindmap = (ROOT / "mindmap.html").read_text(encoding="utf-8")
    branch_start = mindmap.find("id: 'b-truth'")
    next_branch = mindmap.find("\n            {\n                id:", branch_start + 1)
    if branch_start < 0 or next_branch < 0:
        errors.append("mindmap.html: cannot locate the complete b-truth branch")
    else:
        branch = mindmap[branch_start:next_branch]
        leaves_start = branch.find("leaves: [")
        if leaves_start < 0:
            errors.append("mindmap.html: b-truth has no leaves array")
        else:
            leaf_block = branch[leaves_start:]
            children = re.findall(r"\bid:\s*'([^']+)'", leaf_block)
            expected = ["axiom-eternal", "axiom-firstthought", "axiom-onebody"]
            if children != expected:
                errors.append(
                    f"mindmap.html: b-truth leaves are {children}, expected {expected}"
                )

    if errors:
        print("SITE CHECK FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"SITE CHECK OK: {checked} shared-chrome pages, 3 menu entries, "
        "8 AI notices, SEO JSON-LD, local links/anchors, sitemap, image attrs, "
        "canonical/lang checks, unique IDs, b-truth=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
