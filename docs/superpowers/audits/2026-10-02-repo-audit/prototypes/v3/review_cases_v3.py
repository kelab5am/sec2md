"""Every review case from rounds 1 and 2, checked in normal and capture rendering modes."""
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])  # this folder
import completeness_v3 as v3

MERGE_LOSS = ("<table><tr><td>2024</td><td>$</td><td>9,943</td></tr>"
              "<tr><td>2025</td><td></td><td>10,775</td></tr><tr><td>Total</td><td>$</td><td>20,718</td></tr></table>")
TWO_BY_TWO = ("<table><tr><th>Item</th><th>2026</th><th>2025</th></tr>"
              "<tr><td>Revenue</td><td>120</td><td>100</td></tr><tr><td>Cost</td><td>50</td><td>40</td></tr></table>")
SPLIT_NEGATIVE = ("<table><tr><th>Item</th><th colspan=\"2\">2026</th></tr>"
                  "<tr><td>Revenue</td><td>120</td><td></td></tr><tr><td>Loss</td><td>(29</td><td>)</td></tr></table>")


def swap_body_rows(segment):
    lines = segment.split("\n")
    lines[2], lines[3] = lines[3], lines[2]
    return "\n".join(lines)


def move_values_between_rows(segment):
    return segment.replace("| 100 |", "| @ |").replace("| 40 |", "| 100 |").replace("| @ |", "| 40 |")


def reverse_numeric_cells(segment):
    import re
    out = []
    for line in segment.split("\n"):
        cells = line.split("|")
        idx = [i for i, c in enumerate(cells) if re.search(r"\d", c)]
        for i, value in zip(idx, [cells[i] for i in idx][::-1]):
            cells[i] = value
        out.append("|".join(cells))
    return "\n".join(out)


CASES = [
    ("R1-1 prose repeats the lost value", "<p>Commitments include $9,943 million due in 2024.</p>" + MERGE_LOSS, None),
    ("R1-2a inline-split number", "<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>1,2<span>34</span></td></tr></table>", None),
    ("R1-2b hidden descendant", "<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>100<span style=\"display:none\">999</span></td></tr></table>", None),
    ("R1-2c euro and pound values", "<table><tr><td>Item</td><td>2026</td></tr><tr><td>Revenue</td><td>€123</td></tr><tr><td>Cost</td><td>£456</td></tr></table>", None),
    ("R1-3 lost single-digit $9", "<table><tr><td>Impairment</td><td>$</td><td>9</td></tr><tr><td>Other</td><td></td><td>12</td></tr><tr><td>Total</td><td>$</td><td>21</td></tr></table>", None),
    ("R1-3b sup footnote marker", "<table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue<sup>(1)</sup></td><td>120</td></tr></table>", None),
    ("R1-4a/R2-4 nested table", "<table><tr><td>Outer<table><tr><td>Inner</td><td>77</td></tr><tr><td>B</td><td>88</td></tr></table></td><td>12</td></tr><tr><td>Outer B</td><td>34</td></tr></table>", None),
    ("R1-4b one-row table before a multi-row table", "<table><tr><td>ITEM 8.</td><td>FINANCIAL STATEMENTS</td></tr></table><table><tr><th>Item</th><th>2026</th></tr><tr><td>Revenue</td><td>120</td></tr></table>", None),
    ("R1-5 numeric cells reversed", TWO_BY_TWO, reverse_numeric_cells),
    ("R2-1 'Note 1 Revenue' row loses its amount", "<table><tr><td>Note 1 Revenue</td><td>$</td><td>9,943</td></tr><tr><td>Other</td><td></td><td>12</td></tr><tr><td>Total</td><td>$</td><td>9,955</td></tr></table>", None),
    ("R2-2a split negative preserved", SPLIT_NEGATIVE, None),
    ("R2-2b split negative deleted", SPLIT_NEGATIVE, lambda s: s.replace("(29", "")),
    ("R2-3a body rows swapped", TWO_BY_TWO, swap_body_rows),
    ("R2-3b values moved between rows", TWO_BY_TWO, move_values_between_rows),
    ("R3 signature date lost (reported only)", "<table><tr><td>Date:</td><td>January 29, 2025</td><td>/s/ Jane Doe</td></tr><tr><td></td><td></td><td>Jane Doe, Chief Financial Officer</td></tr></table>", lambda s: s.replace("January 29, 2025", "")),
    ("R3 stacked statement with repeated section headers (must not be reported)", "<table><tr><td></td><td>Three Months Ended June 30, 2025</td><td>Three Months Ended June 30, 2024</td></tr><tr><td>Balance at beginning</td><td>2,523</td><td>2,537</td></tr><tr><td>Net income</td><td>18,337</td><td>13,465</td></tr><tr><td></td><td>Six Months Ended June 30, 2025</td><td>Six Months Ended June 30, 2024</td></tr><tr><td>Balance at beginning</td><td>2,534</td><td>2,561</td></tr><tr><td>Net income</td><td>34,981</td><td>25,834</td></tr></table>", None),
    ("R2-3c fused multi-row header (must not be reported)", "<table><tr><td></td><td colspan=\"2\">Year ended December 31,</td><td colspan=\"2\">2024 vs. 2023</td></tr><tr><td></td><td>2024</td><td>2023</td><td>$ Change</td><td>% Change</td></tr><tr><td>Revenue</td><td>1,300</td><td>804</td><td>496</td><td>62%</td></tr><tr><td>Cost</td><td>300</td><td>200</td><td>100</td><td>50%</td></tr></table>", None),
]

for name, html, mutate in CASES:
    print(f"== {name}")
    for capture in (False, True):
        for r in v3.analyze(html, capture=capture, mutate=mutate):
            print(f"   {'capture' if capture else 'normal '}: table {r.ordinal} (snapshot {r.snapshot_ordinal}) "
                  f"enforced={dict(r.missing)} {r.missing_tokens} reported={dict(r.reported)} order={r.order}")
