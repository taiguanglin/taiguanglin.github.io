import json,sys,os
for slug in sys.argv[1:]:
    bs=json.load(open(f'build/{slug}.json'))
    print("#"*20, slug)
    for b in bs:
        t=b["t"]
        if t=="img": print(f"    [IMG {b['src']} {b['w']}x{b['h']}]")
        elif t=="caption": print(f"    (圖說) {b['text']}")
        elif t=="table": print(f"    [TABLE {len(b['rows'])}x{len(b['rows'][0])}] {b['rows'][:2]}")
        elif t.startswith("h"): print(f"\n== {b['text']}  (sz={b.get('size')})")
        else: print(("Q> " if b.get('quote') else ("B> " if b.get('bold') else ""))+b["text"])
