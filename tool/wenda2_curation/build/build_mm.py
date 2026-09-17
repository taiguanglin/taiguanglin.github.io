# -*- coding: utf-8 -*-
import json, re, os

# 以腳本位置推算路徑：build/ -> wenda2_curation/ -> repo root
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
CUR_DIR = os.path.dirname(BUILD_DIR)
out = os.path.join(CUR_DIR, 'data')          # data/ (ch01..21.json, curation, stats)
REPO = os.path.dirname(CUR_DIR)              # = tool/
REPO = os.path.dirname(REPO)                  # repo root
os.chdir(REPO)

cur = json.load(open(f'{out}/curation_terms.json', encoding='utf-8'))
quotes = json.load(open(f'{out}/quotes.json', encoding='utf-8'))
stats = json.load(open(f'{out}/term_stats.json', encoding='utf-8'))
site = json.load(open(f'{out}/site_data.json', encoding='utf-8'))
per_ch = {int(k): v for k, v in stats['per_ch'].items()}
# invert to term -> {chapter: count}
term_pc = {}
for ch_i, counts in per_ch.items():
    for tname, c in counts.items():
        term_pc.setdefault(tname, {})[ch_i] = c

# extra stats for terms missing from the original scan
EXTRA = ['淫慾', '幻覺', '發願']
for t in EXTRA:
    counts = {}
    for i in range(1, 22):
        d = json.load(open(f'{out}/ch{i:02d}.json', encoding='utf-8'))
        counts[i] = sum(x['a'].count(t) for x in d['qa'] if x['a'])
    term_pc[t] = counts

ch_short = {}
for c in site['chapters']:
    t = c['title']
    m = re.match(r'\d+(.+)', t)
    ch_short[c['ch']] = m.group(1).strip() if m else t

def src_line(term):
    pc = term_pc.get(term, {})
    total = sum(pc.values())
    top = sorted(pc.items(), key=lambda kv: -kv[1])[:2]
    tops = '、'.join(f'第{i:02d}章（{v:,}）' for i, v in top if v > 0)
    return f'全書出現 {total:,} 次；高頻：{tops}'

# root quote (verbatim from corpus)
qa_index = {}
for i in range(1, 22):
    d = json.load(open(f'{out}/ch{i:02d}.json', encoding='utf-8'))
    for x in d['qa']:
        qa_index[x['id']] = (i, x['a'], x['time'])
ra = qa_index['question-e63b651dbef9'][1]
p = ra.find('所有的眾生，都有自己獨立的自性')
L = 0
for m in re.finditer(r'[。！？!?；;\n]', ra[:p]):
    L = m.end()
R = len(ra)
for m in re.finditer(r'[。！？!?；;\n]', ra[p:]):
    R = p + m.end()
    break
root_quote = ra[L:R].strip()

BRANCHES = []
EBOOK_LINKS = {}
for b in cur['branches']:
    leaves = []
    for t in b['terms']:
        q = quotes[t['id']]
        s = f'《坐禪之問答錄2》第{q["ch"]:02d}章 {ch_short[q["ch"]]}'
        leaves.append({
            'id': t['id'], 'label': t['term'], 'desc': t['desc'],
            'points': t['points'],
            'quote': {'t': q['quote'], 's': s},
            'src': src_line(t['term']),
            'rel': t['rel'],
        })
        EBOOK_LINKS[t['id']] = f'wenda2_ebook/{q["ch"]:02d}_trad.html#{q["qid"]}'
    BRANCHES.append({'id': b['id'], 'side': b['side'], 'label': b['label'],
                     'desc': b['desc'], 'leaves': leaves})

ROOT = {
    'id': 'root',
    'label': '坐禪之問答錄2',
    'desc': 'Tai 師父 2024 年 2 月至 2026 年 3 月在貼吧與公眾號的問答結集，共 21 章、9,231 個回答。第 01–12 章按主題編排：自性與意識、羯磨、發心、世界起源、戒行、修福積功德、唪誦經咒、腹式呼吸、磕大頭、雙盤、禪定、佛門修行；第 13 章起按月份收錄。這張圖把全書最常被問到的名詞串成一張可以互動的關聯網。',
    'points': [
        '前 12 章按主題彙編（2024.02–2025.05 的問答）；第 13–21 章按月份收錄 2025.06–2026.03 的問答。',
        '9,231 個回答全部收錄於《坐禪之問答錄2》電子書，可全文檢索、逐題對照原文。',
        '57 個名詞、11 條主幹：右側五條講義理與世界（自性與意識、果位與聖眾、世界與輪迴、羯磨、功德與福報），左側六條講實修與生活（發心與戒行、淨土與往生、入門功課、禪定次第、唪誦法門、境界與現象）。',
        '每個名詞節點都附：AI 整理的定義與要點、逐字摘錄的引文、全書出現次數統計，以及連到電子書原文的連結。',
    ],
    'quote': {'t': root_quote, 's': '《坐禪之問答錄2》第01章 自性與意識'},
    'src': '《坐禪之問答錄2》全書 21 章・9,231 個回答（2024.02–2026.03）',
    'rel': ['zixing', 'ye', 'dazuo'],
}
EBOOK_LINKS['root'] = 'wenda2_ebook/01_trad.html#' + 'question-e971784bcf55'
ROOT_QID = None
for qid, (ch, a, tm) in qa_index.items():
    pass
EBOOK_LINKS['root'] = 'wenda2_ebook/01_trad.html#question-e63b651dbef9'

INTRO_CARDS = [
    {'id': 'intro-read', 'label': '一張圖看懂全書',
     'desc': '點任何名詞，右側展開定義、書中要點、逐字引文與出處統計；虛線是關聯名詞，點一下就能跳過去，把整本問答錄串著讀。'},
    {'id': 'intro-pick', 'label': '名詞怎麼選的',
     'desc': '用程式對全書 9,231 個回答逐字統計，選出 57 個高頻名詞，按問答錄自己的主題分成 11 條主幹；每個節點的出現次數都是實際統計數字。'},
    {'id': 'intro-quote', 'label': '引文與出處',
     'desc': '每句引文都從《坐禪之問答錄2》原文逐字摘錄（省略以……標示），並連結到電子書原文位置，方便對照上下文、聽 Tai 師父的完整回答。'},
]

NODE_ICON_SVG = {
    'root': '<circle cx="12" cy="12" r="7" fill="currentColor"/>',
    'b-mind': '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.7" fill="none"/><circle cx="12" cy="12" r="3.4" fill="currentColor"/><circle cx="12" cy="12" r="6" stroke="currentColor" stroke-width="1" fill="none" opacity=".4"/>',
    'b-sages': '<path d="M12 3.5l4.5 4.5-4.5 4.5-4.5-4.5z" fill="currentColor" opacity=".85"/><path d="M12 11.5l4.5 4.5-4.5 4.5-4.5-4.5z" fill="currentColor" opacity=".5"/>',
    'b-world': '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.7" fill="none"/><ellipse cx="12" cy="12" rx="3.5" ry="8.5" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M3.5 12h17" stroke="currentColor" stroke-width="1.4"/>',
    'b-karma': '<path d="M12 4v16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M5 8l7-4 7 4" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M5 8a3.5 3.5 0 007 0M12 4a3.5 3.5 0 017 0" stroke="currentColor" stroke-width="1.4" fill="none"/><circle cx="5" cy="8" r="1.6" fill="currentColor"/><circle cx="19" cy="8" r="1.6" fill="currentColor"/><circle cx="12" cy="19" r="1.8" fill="currentColor" opacity=".5"/>',
    'b-merit': '<path d="M12 20c-4.5 0-8-3-8.5-7 3.5.5 6.5 2.5 8.5 6.2C14 15.5 17 13.5 20.5 13c-.5 4-4 7-8.5 7z" fill="currentColor" opacity=".8"/><path d="M12 12.2c-1.8-3-4.5-5-7.8-5.4C4.8 3.8 8.1 1.8 12 3c3.9-1.2 7.2.8 7.8 3.8-3.3.4-6 2.4-7.8 5.4z" fill="currentColor" opacity=".45"/>',
    'b-vow': '<path d="M12 3.2c2.6 3 4 5.6 4 8a4 4 0 11-8 0c0-2.4 1.4-5 4-8z" fill="currentColor" opacity=".8"/><path d="M7.5 14.5c-1.8 1-2.7 2.4-2.7 4 1.6-.2 2.9-.9 3.8-2.2M16.5 14.5c1.8 1 2.7 2.4 2.7 4-1.6-.2-2.9-.9-3.8-2.2" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
    'b-pure': '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M12 3.5v17M3.9 9.2h16.2M3.9 14.8h16.2" stroke="currentColor" stroke-width="1.4"/>',
    'b-basic': '<path d="M4 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M4 11c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" opacity=".45"/>',
    'b-jhana': '<path d="M4 19h5v-4h5v-4h5V7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/><circle cx="19" cy="5.5" r="2" fill="currentColor"/>',
    'b-recite': '<path d="M8 12a4 4 0 018 0v5.5a4 4 0 01-8 0z" stroke="currentColor" stroke-width="1.7" fill="none"/><path d="M16 11c1.8.4 3 1.8 3 3.6M17.5 6.5c2.8 1 4.5 3.4 4.5 6.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/><circle cx="12" cy="14.5" r="1.8" fill="currentColor"/>',
    'b-phenom': '<path d="M20.5 14.5A8.5 8.5 0 1111 3.7a7 7 0 109.5 10.8z" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linejoin="round"/><circle cx="17" cy="6" r="1.4" fill="currentColor"/>',
}

BOOKS = [
    {'name': '第01–04章 義理', 'color': '#cf6b96'},
    {'name': '第05–08章 戒修', 'color': '#b54d78'},
    {'name': '第09–12章 禪定', 'color': '#953a60'},
    {'name': '第13–17章 月度（25 下）', 'color': '#c9a86a'},
    {'name': '第18–21章 月度（25 末–26）', 'color': '#8d6e63'},
]
GROUPS = [(1, 4), (5, 8), (9, 12), (13, 17), (18, 21)]
def group_counts(term):
    pc = term_pc.get(term, {})
    return [sum(pc.get(i, 0) for i in range(a, b + 1)) for a, b in GROUPS]

CHART_TERMS = ['業', '打坐', '妄想', '功德', '佛菩薩', '執著', '迴向', '極樂世界', '唸佛', '福報', '冤親債主', '命運']
TERM_COUNTS = [{'term': t, 'data': group_counts(t)} for t in CHART_TERMS]

# ---- extract engine from mindmap.html ----
src = open('mindmap.html', encoding='utf-8').read()
i0 = src.index('var CX = 540')
i1 = src.index('/* ------------------------------------------------------ 其它區塊 */')
engine_core = src[i0:i1]
# patch icons
j0 = engine_core.index('var NODE_ICON_SVG = {')
j1 = engine_core.index('};', j0) + 2
icons_js = 'var NODE_ICON_SVG = ' + json.dumps(NODE_ICON_SVG, ensure_ascii=False) + ';'
engine_core = engine_core[:j0] + icons_js + engine_core[j1:]
# patch chips root label
engine_core = engine_core.replace("label: T('自性（中心）')", "label: T(ROOT.label + '（中心）')")
# patch aria
engine_core = engine_core.replace("'TaiGuangLin 禪師九本著作關鍵名詞心智圖'", "'TaiGuangLin 坐禪之問答錄2 名詞心智圖'")

k0 = src.index('function renderChart() {')
k1 = src.index('})();', k0) + len('})();')
engine_chart = src[k0:k1]
engine_chart = engine_chart.replace("《' + T(b.name) + '》'", "' + T(b.name) + '")
engine_chart = engine_chart.replace("'九書合計出現次數（次）'", "'全書合計出現次數（次）'")
assert '九書合計' not in engine_chart and '《坐禪' not in engine_chart

AXIOM_ICONS = {
    'intro-read': '<svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="28" cy="28" r="17" stroke="currentColor" stroke-width="2"/><circle cx="28" cy="28" r="3" fill="currentColor"/><path d="M28 11v-5M28 50v-5M11 28H6M50 28h-5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    'intro-pick': '<svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 10h28a4 4 0 014 4v28a4 4 0 01-4 4H14a4 4 0 01-4-4V14a4 4 0 014-4z" stroke="currentColor" stroke-width="2"/><path d="M20 22h16M20 30h16M20 38h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    'intro-quote': '<svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 16c0-4 3-7 7-7h2v10h-6c-2 0-3 1-3 3v14c0 2 1 3 3 3h14c2 0 3-1 3-3V16c0-4 3-7 7-7h2v10" stroke="currentColor" stroke-width="2" stroke-linejoin="round" opacity=".0"/><path d="M18 12c-4 0-7 3-7 7v18c0 4 3 7 7 7h20c4 0 7-3 7-7V19c0-4-3-7-7-7H18z" stroke="currentColor" stroke-width="2"/><path d="M20 24h16M20 32h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
}
middle = (
    '        var AXIOM_ICONS = ' + json.dumps(AXIOM_ICONS, ensure_ascii=False) + ';\n\n'
    '        function renderAxioms() {\n'
    '            var host = document.getElementById(\'mm-axioms\');\n'
    '            if (!host) return;\n'
    '            host.innerHTML = INTRO_CARDS.map(function (a) {\n'
    '                return \'<div class="mm-axiom-card">\' +\n'
    '                       \'<div class="mm-axiom-icon" aria-hidden="true">\' + (AXIOM_ICONS[a.id] || \'\') + \'</div>\' +\n'
    '                       \'<h3>\' + T(a.label) + \'</h3><p>\' + T(a.desc) + \'</p></div>\';\n'
    '            }).join(\'\');\n'
    '        }\n\n'
    '        var BOOKS = ' + json.dumps(BOOKS, ensure_ascii=False) + ';\n'
    '        var TERM_COUNTS = ' + json.dumps(TERM_COUNTS, ensure_ascii=False) + ';\n\n'
)

data_js = (
    '        var ROOT = ' + json.dumps(ROOT, ensure_ascii=False) + ';\n'
    '        var BRANCHES = ' + json.dumps(BRANCHES, ensure_ascii=False) + ';\n'
    '        var EBOOK_LINKS = ' + json.dumps(EBOOK_LINKS, ensure_ascii=False) + ';\n'
    '        var INTRO_CARDS = ' + json.dumps(INTRO_CARDS, ensure_ascii=False) + ';\n\n'
    '        var NODES = { root: ROOT };\n'
    '        BRANCHES.forEach(function (b) {\n'
    '            NODES[b.id] = b;\n'
    '            b.leaves.forEach(function (l) {\n'
    '                l.branch = b.label;\n'
    '                NODES[l.id] = l;\n'
    '            });\n'
    '        });\n\n'
)

with open(os.path.join(BUILD_DIR, 'mm_data.js'), 'w', encoding='utf-8') as f:
    f.write(data_js + engine_core + middle + engine_chart)
print('engine assembled:', len(data_js) + len(engine_core) + len(middle) + len(engine_chart), 'chars')
print('branches:', len(BRANCHES), 'leaves:', sum(len(b['leaves']) for b in BRANCHES))
