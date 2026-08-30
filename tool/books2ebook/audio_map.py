"""講經系列書本 → 講次 → 音檔 的關聯。

每個新書的「講次編號 N」對應一把 opus 音檔；ebook 章節標題若屬某講次，
就在該標題旁輸出 .qa-play 播放按鈕，data-audio 指向 ../audio/jiangjing/<series>/NN.opus。

音檔實際時間長度在建置時以 ffprobe 讀取，寫進 data-end（播放到檔尾即可）。
"""

# series → {講次 N: 音檔檔名（不含 .opus）}
# 檔名皆為 NN（零填充兩位），放在 /audio/jiangjing/<series>/NN.opus
AUDIO_MAP = {
    "ganen": {1: "01"},          # 感恩与讲经（單一講）
    "sishierzhang": {n: "%02d" % n for n in range(1, 15)},   # 四十二章經 14 講
    "lengqie": {n: "%02d" % n for n in range(1, 43)},        # 楞伽經 42 講
    "liuzutanjing": {n: "%02d" % n for n in range(1, 28)},   # 六祖壇經 27 講
    "lengyanjing": {n: "%02d" % n for n in range(1, 22)},    # 楞嚴經 21 講（未完）
}

AUDIO_BASE = "../audio/jiangjing/"

# 實際音檔所在目錄（本機，供建置時讀取時長）
AUDIO_DIR = "/Users/paul/tai/audio/jiangjing"

_DUR_CACHE = {}


def audio_duration(series, n):
    """用 ffprobe 讀取音檔時長（秒），快取避免重複呼叫。"""
    key = (series, n)
    if key in _DUR_CACHE:
        return _DUR_CACHE[key]
    import subprocess
    fn = AUDIO_MAP.get(series, {}).get(n)
    if not fn:
        _DUR_CACHE[key] = None
        return None
    path = "%s/%s/%s.opus" % (AUDIO_DIR, series, fn)
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True)
        dur = float(out.stdout.strip())
    except Exception:
        dur = None
    _DUR_CACHE[key] = dur
    return dur