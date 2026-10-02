import gzip, re, warnings, sys
warnings.filterwarnings("ignore")
import sec2md
from sec2md.section_extractor import _normalize_for_match as n
FIX = [("aapl-2023-10k","10-K"),("nvda-2026-10k","10-K"),("nvda-2026-q2-10q","10-Q"),("nvda-2002-10k","10-K"),("nvda-2026-08-26-8k","8-K")]
for name, form in FIX:
    html = gzip.open(f"tests/fixtures/sec/{name}.html.gz","rb").read()
    pages = sec2md.convert_to_markdown(html, return_pages=True, quality_policy="off")
    orig = {p.number: p for p in pages}
    secs = sec2md.extract_sections(pages, filing_type=form)
    slices = fallback = keepall = 0; worst = []
    for s in secs:
        for p in s.pages:
            o = orig[p.number]
            if not o.elements: continue
            slices += 1
            if p.elements == []: fallback += 1
            elif len(p.elements) == len(o.elements): keepall += 1
        chunk_txt = n(" ".join(c.content for c in sec2md.chunk_section(s, chunk_overlap=0)))
        sec_txt = n(s.markdown())
        ratio = len(chunk_txt) / max(1, len(sec_txt))
        worst.append((round(ratio, 2), str(s.item)))
    worst.sort()
    print(f"{name}: sections={len(secs)} slices={slices} text_fallback={fallback} keep_all={keepall} chunk/section len ratio min={worst[0]} max={worst[-1]}")
