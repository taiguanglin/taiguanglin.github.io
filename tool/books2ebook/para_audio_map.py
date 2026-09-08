"""講經「段落級」音檔時間對齊（audio_map3）載入器。

由對齊工具產出 ``<repo>/audio_map3/<series>.json``；``<series>`` 與
``audio_map.AUDIO_MAP`` 的主鍵一致（ganen / sishierzhang / lengqie /
liuzutanjing / lengyanjing）。內容是「段落元素 pid → 起訖秒數」的映射，
可接受以下任一常見形狀（寬鬆解析，缺檔/缺段一律回空，不打斷 build）：

* ``{"p-sXXXXXXXX": {"start": 12.3, "end": 45.6}, ...}``
* ``{"p-sXXXXXXXX": [12.3, 45.6], ...}``
* ``{"paragraphs": [{"id"|"pid": "p-sXXX", "start": ..., "end": ...}, ...]}``
* ``{"lectures": {"1": {"paragraphs": [{"pid","start","end",...}, ...]}, ...}}``
  （``tool/jiangjing_para_map`` 產出的正式格式；跨講次展平成單一 pid 映射）
"""

import json
import os

try:
    from config import REPO_ROOT
except ImportError:  # 供 -c 單獨載入等邊界情境
    REPO_ROOT = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".."))

_CACHE = {}


def _norm_entry(pid, val):
    """把單筆對齊資料正規化成 (pid, start, end)；失敗回 None。"""
    if not pid:
        return None
    start = end = None
    if isinstance(val, dict):
        start, end = val.get("start"), val.get("end")
    elif isinstance(val, (list, tuple)) and len(val) >= 2:
        start, end = val[0], val[1]
    try:
        start = float(start)
        end = float(end)
    except (TypeError, ValueError):
        return None
    if start < 0 or end <= start:
        return None
    return pid, start, end


def load_series(series):
    """載入某系列的 pid → (start, end) 映射；無檔/解析失敗回空 dict。"""
    if not series:
        return {}
    if series in _CACHE:
        return _CACHE[series]
    path = os.path.join(REPO_ROOT, "audio_map3", "%s.json" % series)
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = None
    if isinstance(data, dict):
        if isinstance(data.get("lectures"), dict):
            # 主格式（tool/jiangjing_para_map 產出）：
            # {"lectures": {"1": {"reviewed": true, "paragraphs": [{...}]}}}
            # 只有講次 reviewed=true（audio_map3 人工校對完成）才注入時間，
            # --- 這是「人工確認後才啟用跟播功能」的閘門。
            for lect in data["lectures"].values():
                if not isinstance(lect, dict) or not lect.get("reviewed"):
                    continue
                for item in lect.get("paragraphs") or []:
                    if isinstance(item, dict):
                        r = _norm_entry(item.get("pid") or item.get("id"), item)
                        if r:
                            out[r[0]] = (r[1], r[2])
        elif isinstance(data.get("paragraphs"), list):
            for item in data["paragraphs"]:
                if isinstance(item, dict):
                    r = _norm_entry(item.get("pid") or item.get("id"), item)
                    if r:
                        out[r[0]] = (r[1], r[2])
        else:
            for pid, val in data.items():
                r = _norm_entry(pid, val)
                if r:
                    out[r[0]] = (r[1], r[2])
    _CACHE[series] = out
    return out


def para_time_attrs(series, pid):
    """命中時回傳要附加到段落元素上的 HTML 屬性字串，否則回空字串。"""
    if not series or not pid:
        return ""
    hit = load_series(series).get(pid)
    if not hit:
        return ""
    return ' data-start="%.3f" data-end="%.3f"' % hit
