"""search_index*.json 與 .hash 檔輸出（格式與 wenda2_ebook 相容）。"""

import hashlib
import json
import os


def write_search_index(out_dir, items, is_trad):
    """把搜尋項目寫成 search_index[_trad].json + .hash。"""
    name = "search_index_trad.json" if is_trad else "search_index.json"
    path = os.path.join(out_dir, name)
    data = json.dumps(items, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    digest = hashlib.md5(data.encode("utf-8")).hexdigest()
    hash_path = path + ".hash"
    with open(hash_path, "w", encoding="utf-8") as f:
        json.dump({
            "hash": digest,
            "algorithm": "md5",
            "size": len(data.encode("utf-8")),
        }, f, indent=2)
    return path
