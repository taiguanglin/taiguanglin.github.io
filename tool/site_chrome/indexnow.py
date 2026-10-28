#!/usr/bin/env python3
"""IndexNow 變更通知（https://www.indexnow.org/documentation）。

內容新增／更新／刪除後通知 Bing 等 IndexNow 參與者，讓爬蟲不必等
sitemap 重新抓取——這正是「版本搬遷後公開搜尋結果仍是舊內容」的解方。

用法：

    # 通知本次變更影響到的 URL（從 git diff 的檔名推導）
    python3 tool/site_chrome/indexnow.py --changed

    # 通知 sitemap 裡的全部 URL
    python3 tool/site_chrome/indexnow.py --all

金鑰（key）來源順序：
1. 環境變數 ``INDEXNOW_KEY``
2. repo 根目錄 ``indexnow-key.txt``（部署後即為
   https://taiguanglin.info/indexnow-key.txt，符合 IndexNow 的驗證要求）

每次最多送出 10,000 個 URL（協定上限）。失敗只回報、不中斷建置流程。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://taiguanglin.info"
ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_FILE = ROOT / "indexnow-key.txt"
SITEMAP_PATH = ROOT / "sitemap.xml"
MAX_URLS = 10_000

# 站台路徑 → 可索引的 HTML 產物
INDEXABLE_PREFIXES = ("wenda2_ebook/", "ebook/", "wenda2/", "stories/")


def load_key() -> str:
    """取出 IndexNow key（金鑰是公開驗證碼，不是秘密）。"""
    env_key = os.environ.get("INDEXNOW_KEY", "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def _git_changed_files() -> list[str]:
    """本次工作樹相對 HEAD 變更的檔案（含未追蹤的新檔）。"""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    files: list[str] = []
    for line in out.splitlines():
        path = line[3:].strip()
        if " -> " in path:  # rename
            path = path.split(" -> ")[-1].strip()
        if path:
            files.append(path)
    return files


def urls_from_changed(files: list[str]) -> list[str]:
    """把變更檔名轉成站台 URL（只取可索引的 HTML）。"""
    urls: list[str] = []
    for rel in files:
        rel = rel.replace("\\", "/")
        if not rel.endswith(".html"):
            continue
        if not rel.startswith(INDEXABLE_PREFIXES) and rel not in (
            "index.html",
            "stories.html",
            "wenda2.html",
            "infographic.html",
            "mindmap.html",
            "wenda2_mindmap.html",
        ):
            continue
        url = SITE + "/" + rel
        if url not in urls:
            urls.append(url)
    return urls


def urls_from_sitemap() -> list[str]:
    if not SITEMAP_PATH.exists():
        return []
    text = SITEMAP_PATH.read_text(encoding="utf-8")
    return re.findall(r"<loc>(.*?)</loc>", text)


def changed_urls() -> list[str]:
    """目前工作樹相對 HEAD 變更、且可索引的站台 URL。

    推送腳本會在 commit **之前**取一次（commit 後工作樹就乾淨了），
    push 成功後再送出通知。
    """
    return urls_from_changed(_git_changed_files())


def notify_urls(urls: list[str], key: str | None = None) -> int:
    """送出通知（key 未給時自動讀取）。"""
    return notify(urls, key or load_key())


def notify(urls: list[str], key: str) -> int:
    """送出 IndexNow 通知；回傳 0 成功、1 失敗。"""
    if not urls:
        print("ℹ️  沒有要通知的 URL")
        return 0
    if not key:
        print("❌ 缺少 IndexNow key：請設定 INDEXNOW_KEY 或建立 indexnow-key.txt")
        return 1
    urls = urls[:MAX_URLS]
    payload = {
        "host": "taiguanglin.info",
        "key": key,
        "keyLocation": f"{SITE}/indexnow-key.txt",
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "taiguanglin-site-indexnow/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            body = response.read().decode("utf-8", "ignore")[:500]
    except urllib.error.HTTPError as exc:
        print(f"❌ IndexNow 回應 {exc.code}：{exc.read().decode('utf-8', 'ignore')[:300]}")
        return 1
    except urllib.error.URLError as exc:
        print(f"❌ IndexNow 連線失敗：{exc.reason}")
        return 1
    if status in (200, 202):
        print(f"✅ IndexNow 已通知 {len(urls)} 個 URL（HTTP {status}）{body}")
        return 0
    print(f"❌ IndexNow 未成功（HTTP {status}）：{body}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IndexNow 變更通知")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--changed", action="store_true", help="通知本次變更的 URL")
    group.add_argument("--all", action="store_true", help="通知 sitemap 全部 URL")
    group.add_argument("--urls", nargs="+", help="直接指定 URL")
    args = parser.parse_args(argv)

    if args.urls:
        urls = list(args.urls)
    elif args.all:
        urls = urls_from_sitemap()
    else:
        urls = urls_from_changed(_git_changed_files())

    key = load_key()
    if not key:
        print("❌ 找不到 IndexNow key（indexnow-key.txt 或 INDEXNOW_KEY）")
        return 1
    return notify(urls, key)


if __name__ == "__main__":
    raise SystemExit(main())
