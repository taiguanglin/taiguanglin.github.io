"""快速檢視各書解析結果（開發用）。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import extract
import parsers


def main():
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else None
    books = config.BOOKS if idx is None else [config.BOOKS[idx]]
    for bc in books:
        pdf = os.path.join(config.DEFAULT_BOOKS_DIR, bc.pdf)
        lines, images = extract.extract_lines(pdf, skip_pages=bc.skip_pages)
        toc = extract.find_toc_pages(lines)
        blocks = parsers.parse_book(bc.parser, lines, toc, images)
        kinds = {}
        for b in blocks:
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
        print("=" * 72)
        print(bc.title, "| toc pages:", sorted(toc), "| blocks:", len(blocks), kinds)
        # 印出標題結構
        for i, b in enumerate(blocks):
            if b["kind"] in ("h2", "h3", "h4"):
                print("   " * (int(b["kind"][1]) - 2) + f'[{b["kind"]}] {b["text"][:50]}')
        if "-v" in sys.argv:
            import json
            for b in blocks[:40]:
                print(json.dumps(b, ensure_ascii=False)[:160])


if __name__ == "__main__":
    main()
