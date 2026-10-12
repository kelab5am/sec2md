"""Score candidate mixed-scale rules against the classification in cls-new6.json (pct = should be a fraction)."""
import collections, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
D = r'C:\Users\einstein\kelab5am\sec2md\outputs\xlsx-header-detection\new6'
cls = json.load(open('cls-new6.json', encoding='utf-8'))
tables = {}
for n in os.listdir(D):
    for t in json.load(open(os.path.join(D, n), encoding='utf-8'))['tables']:
        tables[(n, t['ordinal'])] = t
PCT_CONCEPT = re.compile(r'To[A-Z]\w*Assets$|Ratio|Percent|Percentage|Margin|Yield|Rate')


def symbol_above(rows, ci, ri, stop_at_label_only):
    for k in range(ri - 1, -1, -1):
        text = rows[k][ci][2] or ''
        if re.search(r'\d', text):
            if '%' in text:
                return 'pct'
            if '$' in text:
                return 'amt'
            continue
        if stop_at_label_only and (rows[k][0][2] or '').strip() and not any(re.search(r'\d', c[2] or '') for c in rows[k][1:]):
            return None
    return None


score = collections.defaultdict(collections.Counter)
for x in cls:
    t = tables[(x['file'], x['ordinal'])]
    rows = t['rows']
    for e in x['cells']:
        truth = e['cls']
        if truth not in ('pct', 'amt') or e['outcome'] not in ('unscaled', 'text'):
            continue
        g = x['group']
        preds = {
            'R1 column has a % cell -> all plain cells percent': 'pct',
            'R2 nearest symbol above ($ or %), any distance': symbol_above(rows, x['col'], e['r'], False),
            'R3 nearest symbol above, stop at a label-only row': symbol_above(rows, x['col'], e['r'], True),
        }
        fact = None
        if e['concepts']:
            fact = 'pct' if any(PCT_CONCEPT.search(c.split(':')[-1]) for c in e['concepts']) else 'amt'
        preds['R4 XBRL fact scale (approx by concept) else R2'] = fact or preds['R2 nearest symbol above ($ or %), any distance']
        for name, p in preds.items():
            if p == 'pct' and truth == 'pct':
                r = 'fixed'
            elif p == 'pct' and truth == 'amt':
                r = 'BROKEN (amount scaled /100)'
            elif truth == 'pct':
                r = 'missed'
            else:
                r = 'amount kept'
            score[name][(g, r)] += 1
            score[name][('ALL', r)] += 1
for name, c in score.items():
    print('##', name)
    for g in ('META', 'NVDA', 'RDDT', 'Others', 'ALL'):
        print('   ', g, {k[1]: v for k, v in sorted(c.items()) if k[0] == g})
