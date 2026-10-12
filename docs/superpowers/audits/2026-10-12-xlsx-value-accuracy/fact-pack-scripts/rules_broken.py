import collections, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
exec(open('rules.py', encoding='utf-8').read().split('score = collections')[0])
br = collections.Counter(); ex = collections.defaultdict(list)
for x in cls:
    t = tables[(x['file'], x['ordinal'])]
    for e in x['cells']:
        if e['cls'] == 'amt' and symbol_above(t['rows'], x['col'], e['r'], False) == 'pct':
            k = (x['file'][:30], x['ordinal'])
            br[k] += 1
            ex[k].append(e['label'][:25] + '=' + e['orig'])
for k, v in br.items():
    print(k, v, ex[k][:4])
