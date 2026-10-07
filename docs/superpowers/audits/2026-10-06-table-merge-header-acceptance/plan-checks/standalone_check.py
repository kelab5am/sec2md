"""Random strings: table_roles._STANDALONE against a procedural reading of revision 14's definition.

Reference reading: optional currency marker (at most one, before the parenthesis or right after it),
optional parentheses, optional sign, a number (thousands in groups of three or plain digits, optional
decimal, or a leading-dot decimal), at most one "%" (inside or after the parentheses); whitespace
between tokens. The two open readings (a "%" inside the parentheses, the marker before the sign)
follow the code, so this checks everything else.
"""
import random, re
from sec2md import table_roles
from sec2md.table_roles import CURRENCY_MARKERS

MARKERS = sorted(CURRENCY_MARKERS, key=len, reverse=True)
NUM = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+")


def reference(s):
    s = s.strip()
    i = 0
    def ws():
        nonlocal i
        while i < len(s) and s[i].isspace():
            i += 1
    def marker():
        nonlocal i
        for m in MARKERS:
            if s.startswith(m, i):
                i += len(m)
                return True
        return False
    markers = percents = 0
    paren = False
    if marker():
        markers += 1
        ws()
    if i < len(s) and s[i] == "(":
        paren = True
        i += 1
        ws()
        if markers == 0 and marker():
            markers += 1
            ws()
    if i < len(s) and s[i] in "-+−–":
        i += 1
        ws()
    m = NUM.match(s, i)
    if not m:
        return False
    i = m.end()
    ws()
    if i < len(s) and s[i] == "%":
        percents += 1
        i += 1
        ws()
    if paren:
        if i >= len(s) or s[i] != ")":
            return False
        i += 1
        ws()
        if percents == 0 and i < len(s) and s[i] == "%":
            percents += 1
            i += 1
            ws()
    return i == len(s)


tokens = ["$", "€", "RMB", "US$", "(", ")", "-", "–", "+", "%", " ", "1", "12", "123", "1,234", "12,34", "1,,2",
          "1,234,567", ".75", "0.5", "1,2345", "0,5", "9"]
rng = random.Random(14)
pattern = re.compile(table_roles._STANDALONE)
cases = disagree = accepted = 0
for _ in range(200000):
    s = "".join(rng.choice(tokens) for _ in range(rng.randint(1, 7)))
    code = bool(pattern.fullmatch(s.strip()))
    ref = reference(s)
    cases += 1
    accepted += code
    if code != ref:
        disagree += 1
        if disagree <= 10:
            print("DISAGREE", repr(s), "code", code, "reference", ref)
print(f"cases {cases}; accepted by the code {accepted}; disagreements {disagree}")
