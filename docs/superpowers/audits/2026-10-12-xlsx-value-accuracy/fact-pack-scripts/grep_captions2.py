"""Any short percent caption in the 60 source filings (tag-stripped text)."""
import collections, html, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\einstein\kelab5am\sec2md\src')
from sec2md.xlsx_tables import _UNIT_DECLARATION

ROOT = r'C:\Users\einstein\kelab5am\sec2md'
files = [l.strip() for l in open(os.path.join(ROOT, r'docs\superpowers\audits\2026-10-11-xlsx-header-detection\filings.txt'),
                                 encoding='utf-8') if l.strip()]
PAT = re.compile(r'\([^()]{0,60}\bpercent\w*[^()]{0,40}\)'
                 r'|(?:the following table [^.!?\d]{0,80})?(?:items |amounts )?expressed as a percentage of [a-z ]{0,30}'
                 r'|\bpercentages? of (?:total )?(?:net )?revenues?\b|\(\s*%\s*\)|\bin percent(?:ages?)?\b', re.I)


def company(path):
    name = os.path.basename(path)
    return name.split('__')[0] if '__' in name else name.split('-')[0]


wording = collections.defaultdict(collections.Counter)
for f in files:
    path = f if ':' in f else os.path.join(ROOT, f)
    raw = open(path, 'rb').read().decode('utf-8', 'replace')
    raw = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', raw)
    raw = re.sub(r'(?is)<ix:header>.*?</ix:header>', ' ', raw)
    text = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', raw)).split())
    co = company(path)
    for m in PAT.finditer(text):
        t = m.group(0).strip()
        wording[t][co] += 1
for t, c in sorted(wording.items(), key=lambda x: -sum(x[1].values())):
    print(sum(c.values()), 'FULLMATCH' if _UNIT_DECLARATION.fullmatch(t) else 'no-match', repr(t), dict(c))
