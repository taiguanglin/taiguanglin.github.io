#!/usr/bin/env python3
"""Synchronise the shared 圖解 navigation across published site HTML.

The site is static, so navigation stays in the HTML for no-JS users and crawlers.
This script is the single source of truth for the dropdown information architecture.
Run it after any generator that writes root, wenda2/, or stories/ HTML.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ITEMS = (
    (
        "infographic.html",
        "名詞圖解",
        "用圖像快速認識核心概念",
        {"infographic.html"},
    ),
    (
        "mindmap.html",
        "坐禪與講經心智圖",
        "看懂名詞關聯與經典依據",
        {"mindmap.html"},
    ),
    (
        "wenda2_mindmap.html",
        "問答錄2心智圖",
        "看懂 57 個高頻名詞關聯",
        {"wenda2_mindmap.html"},
    ),
)

SEO_PAGES = {
    "infographic.html",
    "mindmap.html",
    "wenda2_mindmap.html",
}

DROPDOWN_RE = re.compile(
    r'(?P<indent>[ \t]*)<div class="nav-dropdown(?: is-current)?" id="nav-dropdown">'
    r'.*?</div>\s*</div>',
    re.DOTALL,
)


def page_prefix(path: Path) -> str:
    # 404.html 會在任何不存在的路徑下被 GitHub Pages 渲染，相對連結會隨路徑壞掉，
    # 導覽一律輸出根絕對路徑。
    if path.name == "404.html":
        return "/"
    return "../" * max(0, len(path.relative_to(ROOT).parts) - 1)


def current_key(path: Path) -> str | None:
    name = path.name
    for href, _label, _desc, aliases in ITEMS:
        if name in aliases:
            return href
    return None


def render(path: Path, indent: str) -> str:
    prefix = page_prefix(path)
    current = current_key(path)
    is_current = current is not None
    wrapper_class = "nav-dropdown is-current" if is_current else "nav-dropdown"
    toggle_class = "nav-link nav-dropdown-toggle active" if is_current else "nav-link nav-dropdown-toggle"
    toggle_current = ' aria-current="true"' if is_current else ""

    lines = [
        f'{indent}<div class="{wrapper_class}" id="nav-dropdown">',
        f'{indent}    <button type="button" class="{toggle_class}" id="dropdown-toggle"'
        f' aria-expanded="false" aria-controls="nav-knowledge-menu"{toggle_current}>'
        f'圖解 <span aria-hidden="true">▾</span></button>',
        f'{indent}    <div class="nav-dropdown-menu" id="nav-knowledge-menu">',
    ]
    for href, label, desc, _aliases in ITEMS:
        active = current == href
        classes = "nav-dropdown-item active" if active else "nav-dropdown-item"
        aria = ' aria-current="page"' if active else ""
        lines.extend(
            (
                f'{indent}        <a href="{prefix}{href}" class="{classes}"{aria}>',
                f'{indent}            <strong>{label}</strong>',
                f'{indent}            <span>{desc}</span>',
                f'{indent}        </a>',
            )
        )
    lines.extend((f"{indent}    </div>", f"{indent}</div>"))
    return "\n".join(lines)


def sync_structured_data(path: Path, text: str) -> str:
    marker_re = re.compile(
        r'\s*<!-- STRUCTURED-DATA:START -->.*?'
        r'<!-- STRUCTURED-DATA:END -->\s*',
        re.DOTALL,
    )
    text = marker_re.sub("\n", text)
    if path.name not in SEO_PAGES:
        return text

    title_match = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
    desc_match = re.search(
        r'<meta name="description" content="([^"]*)">', text, re.DOTALL
    )
    canonical_match = re.search(
        r'<link rel="canonical" href="([^"]+)">', text, re.DOTALL
    )
    if not title_match or not desc_match or not canonical_match:
        raise ValueError(f"{path.relative_to(ROOT)}: incomplete SEO metadata")

    title = re.sub(r"\s+", " ", title_match.group(1)).strip()
    description = re.sub(r"\s+", " ", desc_match.group(1)).strip()
    canonical = canonical_match.group(1).strip()
    label = title.split("｜", 1)[0].strip()

    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": canonical + "#webpage",
                "url": canonical,
                "name": title,
                "description": description,
                "inLanguage": "zh-TW",
                "isPartOf": {
                    "@type": "WebSite",
                    "@id": "https://taiguanglin.info/#website",
                    "url": "https://taiguanglin.info/",
                    "name": "TaiGuangLin 次世代終極佛法",
                },
                "breadcrumb": {"@id": canonical + "#breadcrumb"},
            },
            {
                "@type": "BreadcrumbList",
                "@id": canonical + "#breadcrumb",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "首頁",
                        "item": "https://taiguanglin.info/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": label,
                        "item": canonical,
                    },
                ],
            },
        ],
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    block = (
        "<!-- STRUCTURED-DATA:START -->\n"
        '<script type="application/ld+json">' + payload + "</script>\n"
        "<!-- STRUCTURED-DATA:END -->"
    )
    head_end = text.find("</head>")
    if head_end < 0:
        raise ValueError(f"{path.relative_to(ROOT)}: closing head not found")
    return text[:head_end].rstrip() + "\n" + block + "\n" + text[head_end:]


def html_targets() -> list[Path]:
    paths = list(ROOT.glob("*.html"))
    paths += list((ROOT / "wenda2").glob("*.html"))
    paths += list((ROOT / "stories").glob("*.html"))
    return sorted(
        p for p in paths
        if 'id="navbar"' in p.read_text(encoding="utf-8", errors="ignore")
        and "shared.js" in p.read_text(encoding="utf-8", errors="ignore")
    )


def sync(check: bool = False) -> int:
    changed: list[Path] = []
    errors: list[str] = []

    for path in html_targets():
        text = path.read_text(encoding="utf-8")
        matches = list(DROPDOWN_RE.finditer(text))
        if len(matches) != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected one dropdown, found {len(matches)}")
            continue
        match = matches[0]
        updated = text[:match.start()] + render(path, match.group("indent")) + text[match.end():]
        try:
            updated = sync_structured_data(path, updated)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if updated != text:
            changed.append(path)
            if not check:
                path.write_text(updated, encoding="utf-8")

    if errors:
        raise SystemExit("\n".join(errors))
    if check and changed:
        print("Navigation is out of sync:")
        for path in changed:
            print(f"  {path.relative_to(ROOT)}")
        return 1

    verb = "would update" if check else "updated"
    print(f"site chrome: {verb} {len(changed)} page(s); checked {len(html_targets())}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if any page is out of sync")
    args = parser.parse_args()
    raise SystemExit(sync(check=args.check))


if __name__ == "__main__":
    main()
