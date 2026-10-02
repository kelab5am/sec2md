import gzip, warnings
warnings.filterwarnings("ignore")
import sec2md
from sec2md.section_extractor import _normalize_for_match as n
FIX = [("aapl-2023-10k","10-K"),("nvda-2026-10k","10-K"),("nvda-2026-q2-10q","10-Q"),("nvda-2002-10k","10-K"),("nvda-2026-08-26-8k","8-K")]
for name, form in FIX:
    html = gzip.open(f"tests/fixtures/sec/{name}.html.gz","rb").read()
    pages = sec2md.convert_to_markdown(html, return_pages=True, quality_policy="off")
    secs = sec2md.extract_sections(pages, filing_type=form)
    foreign = 0; foreign_chars = 0; examples = []
    for s in secs:
        sec_n = n(s.markdown())
        # also allow page-level content (links stripped differences) by comparing against raw page content of the section's pages
        for c in sec2md.chunk_section(s, chunk_overlap=0):
            for para in c.content.split("\n"):
                pn = n(para)
                if len(pn) >= 40 and pn not in sec_n:
                    foreign += 1; foreign_chars += len(pn)
                    if len(examples) < 2: examples.append((s.item, para[:100]))
    print(f"{name}: foreign paragraphs={foreign} chars={foreign_chars}", examples)
