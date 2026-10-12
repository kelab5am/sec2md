import json, os, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
new6, cls = sys.argv[1], sys.argv[2]
C = json.load(open(cls, encoding='utf-8'))
for item in C:
    if not item['block_starts']:
        continue
    caps = []
    for b in item['blocks']:
        texts = [t.split(' @c')[0] for c in b['captions'] for t in c['texts']]
        caps.append(texts)
    if not any(t and not re.search(r'[A-Za-z]{3,}\.? \d{1,2}', t) and re.search(r'(19|20)\d\d', t) for ts in caps for t in ts):
        continue
    export = json.load(open(os.path.join(new6, item['file'] + '.json'), encoding='utf-8'))
    t6 = next(t for t in export['tables'] if t['ordinal'] == item['ordinal'])
    ctx = export['contexts']
    res = collections.Counter(); ex = []
    for b, ts in zip(item['blocks'], caps):
        years = [int(y) for t in ts for y in re.findall(r'(?:19|20)\d\d', t)]
        if len(set(years)) != 1:
            res['caption not one year: ' + '|'.join(ts)[:40]] += 1
            continue
        Y = years[0]
        for f in t6['facts']:
            if not (b['rows'][0] <= f[0] <= b['rows'][1]):
                continue
            c = ctx.get(f[2])
            end = int(c[2][:4]); m = int(c[2][5:7])
            fy_end = end if not (m == 1) else end  # NVDA fiscal years end in late January of the named year
            if c[0] == 'D':
                v = 'ok' if fy_end == Y else 'mismatch'
            else:
                v = 'ok-end' if fy_end == Y else ('ok-opening' if fy_end == Y - 1 or (m == 1 and end == Y - 1) else 'mismatch')
            res[v] += 1
            if v == 'mismatch' and len(ex) < 3:
                ex.append([f[0], f[1], f[4], c, ts])
    print(item['file'][:22], item['ordinal'], dict(res), ex)
