import json, re, sys, collections
from decimal import Decimal
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_values import convert_cell
TRUE_PARTS = {'Incorporated by Reference', 'Exhibit Description', 'Notes', 'Maturities (calendar year)', 'Issue date',
              'Earliest redemption date(b)', 'Issuance Date', 'Maturity Date', 'Payment Date', 'Contractual Maturity Date',
              'Transaction Date', 'Date of Issuance', 'Grant Date'}
ident = json.load(open('ident-new6.json', encoding='utf-8'))
def amountish(c):
    o = c['orig'].strip()
    if c['nonfraction']:
        return 'ix fact'
    v = convert_cell(o.replace(' %', '%'), role='number')
    if isinstance(v.value, Decimal) and re.search(r'[$%,(]', o):
        return 'formatted number'
    if re.fullmatch(r'\(?[\d.,]+\)?\s*%|\(?[\d.,]+\)?\s*pts', o):
        return 'percent/pts'
    return None
res = collections.Counter(); ex = collections.defaultdict(list)
for x in ident:
    true = re.sub(r'\s+', ' ', x['part']) in TRUE_PARTS
    reasons = [amountish(c) for c in x['cells']]
    hit = [r for r in reasons if r]
    plain_int = sum(bool(re.fullmatch(r'\d{1,3}', c['orig'].strip())) for c in x['cells'])
    k = ('true' if true else 'misread', 'vetoed' if hit else 'kept')
    res[k] += 1
    if len(ex[k]) < 40:
        ex[k].append((x['file'][:24], x['ordinal'], x['header'][:50], collections.Counter(hit), len(x['cells']), sum(not r for r in reasons)))
for k, v in res.items():
    print(k, v)
for k in ex:
    if k != ('true', 'kept'):
        for e in ex[k]:
            print('  ', k, e)
