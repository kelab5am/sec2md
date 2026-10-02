"""Read-only analysis of RCQWealth META/RDDT primary filings. Writes JSON to argv[2]."""
import glob, json, os, re, sys, time, warnings
from collections import Counter
warnings.filterwarnings("ignore")
import sec2md
from sec2md.parser import Parser
from sec2md.encoding import decode_html
from sec2md.quality import _normalized_numbers, _is_hidden_tag, ParseQualityError
try:
    from sec2md.chunker.blocks import is_separator_row
except ImportError:
    is_separator_row = None

mode, out_path = sys.argv[1], sys.argv[2]   # mode: "full" (branch) or "sections" (any tree)
files = sorted(f for co in ("META", "RDDT") for f in glob.glob(f"E:/RCQWealth/{co}/Originals/SEC/*/*.htm"))

def hidden_ids(soup):
    ids = set()
    for tag in soup.find_all(True):
        if _is_hidden_tag(tag):
            ids.add(id(tag)); ids.update(id(d) for d in tag.find_all(True))
    return ids

def norm(text): return re.sub(r"[^0-9a-z]+", "", text.lower())

results = []
for path in files:
    name = os.path.basename(path)[:-4]
    form = "10-K" if "__10-K__" in name else "10-Q"
    raw = open(path, "rb").read()
    rec = {"doc": name, "form": form}
    pages = sec2md.convert_to_markdown(raw, return_pages=True, quality_policy="off")
    secs = sec2md.extract_sections(pages, filing_type=form)
    rec["sections"] = len(secs)
    ratios = []
    for s in secs:
        md_len = len(norm(s.markdown()))
        ch_len = len(norm(" ".join(c.content for c in sec2md.chunk_section(s, chunk_overlap=0))))
        ratios.append((round(ch_len / max(1, md_len), 2), str(s.item), md_len, ch_len))
    ratios.sort(reverse=True)
    rec["chunk_ratio_top"] = ratios[:3]
    rec["sections_over_1_5x"] = sum(r[0] > 1.5 for r in ratios)
    if mode == "full":
        try:
            sec2md.convert_to_markdown(raw); rec["strict"] = "pass"
        except ParseQualityError as e:
            rec["strict"] = "FAIL: " + str(e)[:160]
        p = Parser(decode_html(raw)[0]); ppages = p.get_pages()
        elements = {e.id: e for pg in ppages for e in (pg.elements or [])}
        by_node = {}
        for eid, nodes in p.block_nodes_map.items():
            for n in nodes: by_node.setdefault(id(n), set()).add(eid)
        hid = hidden_ids(p.soup)
        tables = [t for t in p.soup.find_all("table") if id(t) not in hid]
        checked = flagged = material = minor = order_diffs = 0; examples = []
        for ordinal, t in enumerate(tables, 1):
            src_rows = []
            for tr in t.find_all("tr"):
                if tr.find_parent("table") is not t or id(tr) in hid: continue
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]) if c.find_parent("table") is t and id(c) not in hid]
                nums = tuple(_normalized_numbers(" ".join(cells)))
                if nums: src_rows.append((nums, cells))
            if not src_rows: continue
            checked += 1
            eids = set()
            for node in [t] + t.find_all(True): eids |= by_node.get(id(node), set())
            out = Counter()
            for eid in eids: out.update(_normalized_numbers(elements[eid].content.replace("|", " ")))
            missing = Counter(x for r, _ in src_rows for x in r) - out
            if missing:
                flagged += 1
                mat = [m for m in missing.elements() if len(m.lstrip("-").replace(".", "")) >= 2 or "." in m]
                material += len(mat); minor += sum(missing.values()) - len(mat)
                if len(examples) < 6:
                    row = next((cells for r, cells in src_rows if set(r) & set(missing)), [])
                    examples.append({"table": ordinal, "missing": sorted(missing.elements())[:8], "mapped": bool(eids),
                                     "source_row": [c for c in row if c][:8]})
            body = []
            for eid in sorted(eids):
                lines = elements[eid].content.split("\n")
                sep = next((i for i, l in enumerate(lines) if is_separator_row(l)), None)
                if sep is None: continue
                for l in lines[sep + 1:]:
                    nums = tuple(_normalized_numbers(l.replace("|", " ")))
                    if l.lstrip().startswith("|") and nums: body.append(nums)
            tail = [r for r, _ in src_rows][-len(body):] if body else []
            if body and len(body) <= len(src_rows) and tail != body and not missing:
                order_diffs += 1
        rec.update(tables_checked=checked, tables_flagged=flagged, missing_material=material,
                   missing_minor=minor, order_diffs=order_diffs, examples=examples)
    results.append(rec)
    print(name[:40], {k: v for k, v in rec.items() if k in ("strict", "sections", "sections_over_1_5x", "tables_checked", "tables_flagged", "missing_material", "order_diffs")}, flush=True)
json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1)
