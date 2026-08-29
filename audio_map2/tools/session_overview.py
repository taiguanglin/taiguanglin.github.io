#!/usr/bin/env python3
"""Print segment list + SRT skeleton for a session (thematic alignment aid).

Usage (from tool/word_audio_map2):
    .venv/bin/python path/to/session_overview.py <month.json> <date> [source]
"""
import sys
import json
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bm', REPO / 'tool/word_audio_map2/build_maps.py')
bm = importlib.util.module_from_spec(spec)
sys.modules['bm'] = bm
spec.loader.exec_module(bm)
from common import parse_srt, normalize, get_converter  # noqa: E402


def main():
    json_path, date = sys.argv[1], sys.argv[2]
    src = sys.argv[3] if len(sys.argv) > 3 else 'main'
    data = json.load(open(json_path))
    s = [x for x in data['sessions'] if x['date'] == date and x['source'] == src][0]
    conv = get_converter()
    cues = parse_srt(Path(s['media_parts'][0]['srt_file']), conv)
    dur = s['media_parts'][0]['duration_est']
    print(f'=== {date} {src} dur={dur:.0f}s cues={len(cues)} segs={len(s["segments"])} ===')
    op = s.get('opening') or {}
    print(f'opening {op.get("start")}-{op.get("end")}')
    print(f'closing {s.get("closing")}')
    print('\n-- SEGMENTS --')
    for g in s['segments']:
        a = (g.get('answer_text') or '').replace('\n', ' ')
        q = (g.get('q_text') or '').replace('\n', ' ')
        print(f"#{g['index']:02d} conf={g.get('confidence')} {g.get('start')}-{g.get('end')} "
              f"achars={len(a)} q={g.get('questioner')}")
        print(f"   Q: {q[:100]}")
        print(f"   A: {a[:120]}")
        print(f"   notes: {(g.get('notes') or '')[:80]}")
    print('\n-- SRT SKELETON --')
    markers = ('问题', '第一', '第二', '第三', '第四', '还有', '然后', '好吧', '下一个', '下面', '有人问')
    last_sample = -999.0
    for t0, t1, t in cues:
        n = normalize(t, conv)
        is_mark = any(m in n[:12] for m in markers) or (t0 - last_sample >= 25)
        if is_mark and t.strip():
            print(f'{t0:7.1f}  {t.strip()[:80]}')
            if t0 - last_sample >= 25:
                last_sample = t0


if __name__ == '__main__':
    main()
