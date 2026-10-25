"""audio_dates_supplement: question_id → date mapping from audio file names.

當原始 PDF/Word 文字中沒有日期戳時，從音頻映射推導的日期補充表查找，
讓產出的 HTML 也有 question-time span。

SoT: tool/word2ebook/data/audio_dates_supplement.json
"""
import json
from functools import lru_cache
from pathlib import Path

_SUPPLEMENT_FILE = Path(__file__).resolve().parents[1] / "data" / "audio_dates_supplement.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    """載入補充日期映射（模組級快取，一次載入）"""
    try:
        data = json.loads(_SUPPLEMENT_FILE.read_text(encoding="utf-8"))
        return data.get("dates", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def lookup_date(question_id: str) -> str:
    """查 question_id 的補充日期；沒有則回傳空字串。

    支援 -N 後綴的追問/拆分子題：先查完整 ID，查不到再剝 -N 後綴查母條目。
    """
    dates = _load()
    # 先查完整 ID
    date = dates.get(question_id, "")
    if date:
        return date
    # 剝 -N 後綴查母條目（如 question-xxx-2 → question-xxx）
    parts = question_id.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return dates.get(parts[0], "")
    return ""


# ── qa_split_ebook 共用接口 ──
_loaded = None

def get_dates():
    """取得整份映射 dict（供 qa_split_ebook 等外部管線直接使用）"""
    global _loaded
    if _loaded is None:
        _loaded = _load()
    return _loaded
