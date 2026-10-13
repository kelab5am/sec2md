"""Check every manifest entry in the branch export, and every percent-fact cell (spec Acceptance 3 and 6).

    python -I dispositions.py BASE_DIR NEW_DIR --manifest manifest.json --src <branch checkout>/src
                              [--details dispositions.json]

Run it from the checkout root: each export JSON names its filing by a path relative to it.
BASE_DIR is main's export (the manifest's baseline) and NEW_DIR the branch's, both written by
export_tables.py of the header-detection audit. --src is the branch's src. From it the script
imports the patterns the spec names as today's (_ROW_UNIT, _PERCENT, _PERCENT_UNIT,
_FOOTNOTE_MARK, _UNIT_LINE, _VALUE), the header-detection helpers _identifier_heading,
_period_row and _period_text (Rule 3 and the period-row guard, which the branch leaves
unchanged), and convert_cell, whose own review reasons the spec keeps. It also reads the
branch's own output: NEW_DIR's headers, joined copy text and cell_sources are the evidence it
judges. What it does not take from the branch are the value-accuracy decisions: every Rule P
and Rule I decision below (proofs, conflicts, percent columns, the attachment rules, the safety
net, the dispositions) is written again from the spec and the ledger's rulings, so a
disagreement with the branch's decisions shows up as a failure. A defect in a shared helper, the
converter or the export's headers is outside what it can see; changes.py checks headers and row
labels against the baseline.

Locating an entry. The copy cell whose cell_sources hold (source_row, source_column), in the
same filing and table ordinal. The script asserts that no source coordinate sits in two copy
cells of one table, in both exports.

The evidence for a digit copy cell, read from the export JSON (spec Definitions, P1, P2):
- token: the copy cell's joined text in NEW_DIR, after the attachment pass; D, its displayed
  number: the digits, negated by accounting parentheses or a leading minus, when the token is
  one complete number with optional '$', '%', sign and parentheses ((x) %, (x)% and (x %) too).
- own %: D exists and the token holds '%'. own $: D exists and the token holds '$'.
- percent fact: the cell has exactly one origin holding digits, that origin holds exactly one
  ix:nonFraction (a nested fact counts as a second one, Ruling 3; export_tables.py drops
  nested facts, so the filing's own tags are read for them, see nested_facts), its unit is
  xbrli:pure alone, its scale is "-2", its format is absent, ixt:num-dot-decimal or ixt:numdotdecimal,
  its displayed digits equal the token's, and sign="-" exactly when D is negative.
- amount fact: a fact on an origin holding digits whose unit has an iso4217 or xbrli:shares
  measure. A pure fact with another scale under a displayed '%' is a disagreeing percent proof.
- percent header: a part of the copy column's header (headers split on ' — ') is a percent
  declaration, unless the column shares its leaf header with another copy column holding a
  value in the same row (Ruling 7); the withheld declaration still feeds the conflict test
  and makes the column a percent column (Rulings 10, 11).
- percent row label: the text of the source cell covering column 0 of the source row is a
  percent declaration (Ruling 21, completed: a label spanning two rows labels both).
- table-wide declaration: a spanning in-table caption before the first body row matching the
  spec's table-wide forms. The context lines before a table are not in the export JSON, so a
  number scaled by a context declaration has no proof this script can see: it would be reported
  as an entry without a valid disposition (or, in changes.py, a changed cell not as the spec
  gives) and must then be checked by hand (see the README).
- non-percent unit: today's _ROW_UNIT in the header or the row label.

Expected outcome of a digit cell under Rule P (P3, P4, rulings 4, 8-12, 21, 24-27):
1. conflict (a percent proof, a withheld declaration or today's shown percent, beside own $, an
   amount fact, _ROW_UNIT or a '$' in the header or row label; or, Ruling 21, any percent claim
   or a table-wide caption beside contrary evidence: a fact neither pure at scale -2 nor an
   amount fact, or a row or header label naming another unit, OTHER_UNIT) -> text,
   'Conflicting explicit units; ...' or the converter's 'Currency and percent conflict; ...';
2. a points value -> text, 'Percentage points; verify the unit.';
3. a percent proof -> a number equal to D / 100, its format derived from the token's decimals,
   or the converter's own reason when it rejects the token;
4. a non-percent proof -> a number equal to D;
   (before 3: a value whose split '%' was refused is P4 text, see Split percent signs below;
   so is a cell without a proof of its own under a heading naming a percent, Ruling 21)
5. no proof, in a percent column (some digit cell of the copy column has own %, a percent fact
   or a percent row label, or the column holds a withheld declaration) -> text with
   'Percent sign on other rows of this column; verify the scale.', except a token the converter
   accepts as zero (a number 0) or rejects (its own reason);
6. otherwise the cell has no proof and is outside any percent column.

Dispositions (spec Acceptance 3):
- percent_row_joined / percent_row_split: 'proven percent' (rule 3, proof named), 'text' with the
  expected reason (rules 1, 2, 5), 'zero'. Rule 4 and rule 6 numbers are invalid for a percent
  row unless they are text (a percent row may not be an unflagged number at the wrong scale).
- identifier_misread: a digit cell that proves a quantity itself (a fact on its digit origin, or
  a complete token with '$' or '%') takes Rule P: 'proven percent' or 'proven quantity'
  (a number equal to D). Any other digit cell is text: the points or conflict reason first
  (Rulings 4, 12), else 'Identifier heading over quantities; verify the column.' when another
  cell of its copy column proves a quantity, else 'Identifier heading over amount-formatted
  values; verify the column.' when the whole cell is a thousands-separated number or a number
  in accounting parentheses that is not a footnote mark (user decision, 2026-10-13). Spec I2
  leaves any other such cell unflagged, but unflagged text is never a valid disposition for a
  manifest digit cell, of any kind (Acceptance 3: no manifest cell may be unflagged text that
  holds an amount); the same holds for a percent row under an identifier heading. A cell
  without digits must equal the baseline.
- identifier_true: the copy cell equals the baseline's in type, value, original, format and reason.

Percent facts (spec Acceptance 6): every digit copy cell of NEW_DIR, in every table that is not
source_text_only, whose percent-fact evidence holds is listed. A number must equal the fact's
own displayed number / 100, negated when sign="-"; text is listed with its reason. Cells that
would hold a percent fact but for a nested fact are listed as 'not proof: nested fact'.

Ruling 34 (a caption proves nothing in a table with unit or currency evidence in its cells, and
every column there becomes a percent column), with Ruling 36's search of every cell and every
non-percent fact, is encoded for the table's own cells; Ruling 35's
caption-shaped context lines are not in the export JSON. The table-wide forms now require the
parentheses of the final review fix. Rulings 32 and 33 (any currency symbol or listed ISO code in
a label under a table-wide caption is a conflict; they replace the currency keep-value exception of Rulings 29-31) and Ruling 29's
points part (a bare or glued 'pp' as points, 'PP&E' excepted) are encoded as well, for the in-table captions this script can see. Ruling 28 (a
sign disagreement between display and fact is not flagged) needs no encoding: a sign-mismatched
fact is no percent-fact proof here either, and it is not contrary evidence.
Rulings 21-27 (spec Revision 3) are encoded where they decide a corpus cell: contrary evidence
(facts and unit-naming labels, read on the covering row label too) and percent-named headings.
Three of their outcomes are not modelled: a copy column holding a '$' or amount fact withholding
its percent heading and a table-wide declaration, an amount heading under a table-wide
declaration flagging its unproven cells, and a '%' spanning two rows never joining a value. If the
branch applied one of them to a cell, the gates would fail (the checker expects the earlier
outcome); if the branch failed to apply one, they would not notice. unmodelled_scan.py counts the
corpus cells of those shapes (0 in this corpus). The export of ecc5990 differs from that of
732544d in 13 cells, all decided by the two encoded outcomes, and b7bd072's export equals
ecc5990's (see the README).

Split percent signs (user decision 2026-10-13, Rulings 13-18a): every '%' / ')%' marker the
attachment pass reaches is judged by the rules (see audit_splits) and compared with NEW_DIR. A
value whose marker was refused is P4 text by the safety net (Ruling 13): a zero converts, a token
the converter rejects keeps its reason, and the conflict, points and identifier reasons come first.

All-cells sweep: every digit copy cell of NEW_DIR, manifest entries or not, is held against the
checker's expectation; see sweep_cells for the two stated exceptions, both identical to base.

Exit status 1 when any entry has no valid disposition, any percent-fact number differs, the
branch and the split rules disagree on any marker or refused value, or the sweep finds a
mismatch (or other than 495 NVDA context-declaration cells).
"""

import argparse
import collections
import json
import os
import re
import sys
from decimal import Decimal

CONFLICT = 'Conflicting explicit units; verify the row, column and displayed value units.'
CURRENCY_PERCENT = 'Currency and percent conflict; verify the source units.'
POINTS_REASON = 'Percentage points; verify the unit.'
UNPROVEN = 'Percent sign on other rows of this column; verify the scale.'
QUANTITIES = 'Identifier heading over quantities; verify the column.'
AMOUNT_FORMATTED = 'Identifier heading over amount-formatted values; verify the column.'
PERCENT_KINDS = ('percent_row_joined', 'percent_row_split')
KINDS = (*PERCENT_KINDS, 'identifier_misread', 'identifier_true')
FACT_FORMATS = {None, 'ixt:num-dot-decimal', 'ixt:numdotdecimal'}
GROUPS = ('META', 'NVDA', 'RDDT', 'Others')
# The dispositions that convert a cell on a named proof (expected_outcome names it).
PROVEN = ('proven percent', 'proven not a percent', 'proven quantity')
SPLIT_MARKERS = {'%', ')%'}
CLOSING_FRAGMENTS = {')', '%)'}  # Ruling 18a
# A source cell, with the attribute names the header-detection helpers read.
Source = collections.namedtuple('Source', 'row column rowspan colspan text is_numeric_fact')

# A complete token: optional '(', sign, '$', the number, '%', ')' and a '%' after the ')'. A '$'
# may also precede the '(': the structural join gives '$ (120)', which the exporter converts.
TOKEN = re.compile(r'(?P<cur0>\$)?\s*(?P<open>\()?\s*(?P<sign>[+\-−])?\s*(?P<cur>\$)?\s*'
                   r'(?P<num>(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?)\s*(?P<pct1>%)?\s*(?P<close>\))?\s*(?P<pct2>%)?')
# ix:nonFraction tags in document order, to find facts nested in facts (see nested_facts).
FACT_TAG = re.compile(r'<(/?)ix:nonFraction\b([^>]*?)(/?)>', re.I)
FACT_ATTR = re.compile(r'\b(contextRef|name)\s*=\s*"([^"]*)"', re.I)
# Spec P4: a value in percentage points.
POINTS = re.compile(r'[+\-−]?\(?(?:\d[\d,]*)?\.?\d+\)?\s*(?:pts|pt|points)', re.I)
# Spec I2: a thousands-separated number, or a number in accounting parentheses.
AMOUNT_FORMAT = re.compile(r'[+\-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\(\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*\)')
# Spec Definitions, percent declaration.
NOT_DECLARATION = re.compile(r'\$|\bpoints?\b|\bpts\b', re.I)
NUMBER_PERCENT = re.compile(r'(?<![\d.,])(?!(?:19|20)\d{2}\s?%)\d[\d,.]*\s?%')  # '80 %' is a value, '2023 %' is not
SYMBOL_FORMS = (re.compile(r'^%'), re.compile(r'%\s+(?:of|change)\b', re.I), re.compile(r'(?:\(\s*%\s*\)|%)$'))
BASE = r'(?:revenues?|total revenues?|net revenues?|total net revenues?|net sales|sales)'
WORD_FORMS = re.compile(rf'(?:percent|percentage|percentages|percent change|percentage change'
                        rf'|percent of {BASE}|percentage of {BASE}|as a percent(?:age)? of {BASE}'
                        rf'|percent of retained loans to total retained loans)(?:\s*(?:\([a-z\d]{{1,2}}\)|\*+))?', re.I)
# Spec Definitions, table-wide percent declaration (spanning in-table captions only, see above).
# Rulings 21 and 24-27 (spec Revision 3): a row or header label naming a unit other than a
# percent. Written from the rulings' text: a unit word in parentheses ('(in years)', '(times)',
# '(x)', '(mos.)', '(ppt)'), after 'in' ('in years'), after a separator closing the label
# (', years'), as the first word ('Days …', 'Months of supply', 'Years …', 'Weeks …', 'Times …',
# 'Number of days'), a trailing ' x', 'duration', 'years to maturity', or a points unit in any
# spelling and position, glued to a number too (Rulings 26, 27: no letter before it). Period
# wording (today's _PERIOD_WORDS) is stripped first, and a leading bucket over a digit range on
# the raw label ('Years 1-5', 'Days 31-60', Ruling 25) names no unit.
POINTS_WORD = r'(?:bps|bp|basis[- ]points?|percentage[- ]points?|ppts?|points|pts)'
UNIT_WORD = rf'(?:years|yrs|months|mos|days|weeks|times|x|pp|{POINTS_WORD})'
UNIT_BUCKET = re.compile(r'^(?:years|months|days|weeks)\s*\d[\d,.]*\s*(?:[-–—]|to|through)\s*\d', re.I)
OTHER_UNIT = re.compile(
    rf'\(\s*(?:in\s+)?{UNIT_WORD}\.?\s*\)'
    rf'|\bin\s+(?:years|yrs|months|mos|days|weeks|{POINTS_WORD})\b'
    rf'|[,:;–—-]\s*{UNIT_WORD}\.?$'
    r'|^(?:number of\s+)?(?:days|months|years|weeks)\b|^times\b|\sx$'
    r'|\bduration\b|\byears to maturity\b'
    rf'|(?<![a-z]){POINTS_WORD}\b'
    # Ruling 29: a bare 'pp', glued to a number too ('Change 25pp'), but not 'PP&E'.
    r'|(?<![a-z&])pp(?![a-z0-9_&])', re.I)
# Rulings 32 and 33 (spec Revision 3; they replace the currency keep-value exception of Rulings
# 29-31): under a table-wide declaration any currency in a row or header label makes the cell
# conflict text, and no currency label keeps a displayed value there; word units (today's
# _ROW_UNIT: 'per share', 'dollars' …) keep spec P3. A currency is a symbol ('$', '€', '£', '¥',
# so 'US$', 'NT$', 'HK$' too) anywhere in the label, or an ISO 4217 code from Ruling 33's closed
# list as a whole, case-sensitive, upper-case word ('Price (USD)', 'Amount, TWD'; not 'CEO',
# 'EPS' or 'USDA').
CURRENCY_MARK = re.compile(r'[$€£¥]|\b(?:USD|EUR|GBP|JPY|CNY|RMB|TWD|NTD|HKD|CHF|CAD|AUD|INR|KRW|SGD|BRL'
                           r'|MXN|SEK|NOK|DKK|ZAR)\b')
# Ruling 21: a header label naming a percent without declaring one ('% Change in NT$ from …',
# 'Percent Change 2024 versus 2023'): a '%' or the word percent or percentage(s), outside a
# number's own '%' and an except clause, in a label that is neither a percent declaration nor
# a table-wide declaration and names no points or percentage-of-completion (spec Testing 7).
PERCENT_NAME = re.compile(r'%|\bpercent(?:ages?)?\b', re.I)
NOT_PERCENT_NAME = re.compile(r'\bpoints?\b|\bpts\b|\bpercentage[- ]of[- ]completion\b', re.I)
# Spec Definitions with the final review fix (Revision 3): _UNIT_DECLARATION's alternatives 2
# and 3, or one of the four parenthesised forms, parentheses required.
TABLE_WIDE = re.compile(r'\(?(?:(?:(?:items |amounts )?expressed as a )?percentage of revenue'
                        r'|the following table [^.!?\d]*expressed as a percentage of revenue)\)?\.?'
                        r'|\((?:in percent(?:ages)?|as a percentage of (?:total )?revenue)\)', re.I)
# Ruling 34 (user decision 2026-10-13): unit or currency evidence anywhere in a table withholds a
# table-wide declaration. Currency evidence is wider than CURRENCY_MARK: also '₹ ₩ ₽ ₺ ₪', 'Fr.',
# and a listed ISO code glued to an amount ('USD500m', '500mUSD').
ISO_CODES = r'(?:USD|EUR|GBP|JPY|CNY|RMB|TWD|NTD|HKD|CHF|CAD|AUD|INR|KRW|SGD|BRL|MXN|SEK|NOK|DKK|ZAR)'
CURRENCY_EVIDENCE = re.compile(rf'[$€£¥₹₩₽₺₪]|\bFr\.|(?<![A-Z]){ISO_CODES}(?![A-Z])')
# Ruling 36 (completes Ruling 34's "anywhere"): a currency word, dollar(s), euro(s), yen, yuan,
# renminbi, rupee(s), franc(s) or pound(s) sterling anywhere, and won, real(s) or pound(s) only as
# a unit ('(in won)', '(reals)', 'in pounds'), so 'Real estate' is none.
CURRENCY_WORD = re.compile(r'\b(?:dollars?|euros?|yen|yuan|renminbi|rupees?|francs?|pounds? sterling)\b'
                           r'|\(\s*(?:in\s+)?(?:won|reals?|pounds?)\s*\)|\bin (?:won|reals?|pounds?)\b', re.I)
# Ruling 36: a unit after the number in a value cell ('5.5 years', '45 days', '5.5x', '+100bps').
VALUE_UNIT = re.compile(r'\d\s*(?:years?|yrs?|months?|mos|days?|weeks?|times|x|bps|bp|basis[- ]points?'
                        r'|percentage[- ]points?|ppts?|pp|points?|pts?)\.?(?![a-z])', re.I)


def group(name):
    company = name.split('__')[0]
    return company if company in GROUPS[:3] else 'Others'


def has_digit(text):
    return bool(text and re.search(r'\d', text))


def displayed(token):
    """D: the token's displayed number with its sign, or None when it is not one complete number."""
    m = TOKEN.fullmatch((token or '').strip())
    if not m or (m['open'] is None) != (m['close'] is None) or (m['pct1'] and m['pct2']):
        return None
    if (m['open'] and m['sign']) or (m['cur0'] and m['cur']):
        return None
    if m['pct2'] and not m['open']:
        return None
    value = Decimal(m['num'].replace(',', ''))
    if m['open'] or m['sign'] in ('-', '−'):
        value = value.copy_negate()
    return value


def token_parts(token):
    m = TOKEN.fullmatch(token.strip())
    places = len(m['num'].partition('.')[2])
    return dict(percent=bool(m['pct1'] or m['pct2']), currency=bool(m['cur'] or m['cur0']), accounting=bool(m['open']),
                places=places)


def expected_format(token, percent):
    """The display format derived from the token: decimals, '%', '$' and accounting parentheses."""
    p = token_parts(token)
    base = ('0' if percent else '#,##0') + ('.' + '0' * p['places'] if p['places'] else '') + ('%' if percent else '')
    if p['currency']:
        base = '"$"' + base
    return base + ';(' + base + ')' if p['accounting'] else base


def digits_of(text):
    return re.sub(r'[^\d.]', '', text or '')


def nested_facts(path):
    """{(contextRef, name) of an outermost ix:nonFraction: the number of facts nested inside it}.

    export_tables.py marks each fact by clearing it, so a fact nested in another is cleared with
    it and never reaches the facts list: only the outer fact is recorded. The filing's own tags
    restore the count (Ruling 3: a nested fact is a second fact on the cell)."""
    html = open(path, 'rb').read().decode('utf-8', 'replace')
    stack, nested = [], collections.Counter()
    for m in FACT_TAG.finditer(html):
        closing, attrs, empty = m.groups()
        if closing:
            if stack:
                stack.pop()
            continue
        attributes = {k.lower(): v for k, v in FACT_ATTR.findall(attrs)}
        if stack:
            nested[stack[0]] += 1
        if not empty:
            stack.append((attributes.get('contextref'), attributes.get('name')))
    return nested


def names_other_unit(label):
    """Rulings 21, 24-27: the label names a unit other than a percent (see OTHER_UNIT)."""
    text = UNIT_BUCKET.sub(' ', (label or '').strip())
    return bool(OTHER_UNIT.search(M._PERIOD_WORDS.sub(' ', text).strip()))


def percent_heading(label):
    """Ruling 21: a header label that names a percent without declaring one."""
    text = re.sub(r'\s+', ' ', label or '').strip()
    named = NUMBER_PERCENT.sub(' ', re.sub(r'\bexcept\b[^)]*', ' ', text, flags=re.I))
    return (bool(PERCENT_NAME.search(named)) and not NOT_PERCENT_NAME.search(text)
            and not percent_declaration(text) and not TABLE_WIDE.fullmatch(text))


def percent_declaration(label):
    """Spec Definitions: a header or row label declaring its values percents."""
    label = re.sub(r'\s+', ' ', label or '').strip()
    if not label or NOT_DECLARATION.search(label):
        return False
    words = NUMBER_PERCENT.sub(' ', label).strip()
    return (any(p.search(words) for p in SYMBOL_FORMS) or bool(WORD_FORMS.fullmatch(label))
            or bool(M._PERCENT_UNIT.fullmatch(label)))


class Table:
    """One exported table with the lookups the checks need."""

    def __init__(self, filing, t, nested=None):
        self.filing, self.t = filing, t
        self.ordinal = t['ordinal']
        self.text_at = {(c[0], c[1]): c[4] for c in t['source_cells']}
        self.facts = collections.defaultdict(list)
        for f, a in zip(t['facts'], t['fact_attributes']):
            self.facts[(f[0], f[1])].append(dict(context=f[2], concept=f[3], displayed=f[4], sign=f[5], scale=a[0],
                                                 format=a[1], unit=list(a[3]),
                                                 nested=(nested or {}).get((f[2], f[3]), 0)))
        self.where = {}
        for ri, row in enumerate(t['cell_sources']):
            for ci, sources in enumerate(row):
                for s in sources:
                    assert tuple(s) not in self.where, (filing, self.ordinal, s, 'coordinate in two copy cells')
                    self.where[tuple(s)] = (ri, ci)
        cells = [Source(*c) for c in t['source_cells']]
        self.height = max((c[0] + max(c[2], 1) for c in cells), default=0)
        self.width = max((c[1] + max(c[3], 1) for c in cells), default=0)
        self.header_count = self.height - len(t['rows'])
        self.grid = [[None] * self.width for _ in range(self.height)]
        for c in cells:
            for r in range(c[0], c[0] + max(c[2], 1)):
                for col in range(c[1], c[1] + max(c[3], 1)):
                    self.grid[r][col] = c
        self.refused = set()  # value origins whose split '%' was refused (set by audit_splits)
        self._shared = None
        self._table_wide = None
        self._unit_evidence = None
        self.columns = {}

    def cell(self, ri, ci):
        kind, value, original = self.t['rows'][ri][ci]
        return dict(type=kind, value=value, original=original or '', format=self.t['cell_formats'][ri][ci],
                    reason=self.t['cell_reasons'][ri][ci], sources=[tuple(s) for s in self.t['cell_sources'][ri][ci]])

    def digit_origins(self, ri, ci):
        return [tuple(s) for s in self.t['cell_sources'][ri][ci] if has_digit(self.text_at.get(tuple(s)))]

    def row_label(self, ri):
        """The source cell covering column 0 of the copy row's source row, so a label spanning
        two rows labels both (Ruling 21, completed)."""
        r = self.header_count + ri
        c = self.grid[r][0] if self.width else None
        return c[4] if c is not None else ''

    def header_labels(self, ci):
        header = self.t['headers'][ci]
        return [] if re.fullmatch(r'Column \d+', header) else [p for p in header.split(' — ') if p.strip()]

    def leaf(self, col):
        """The lowest header cell with text above a source column, unit lines excluded."""
        for r in reversed(range(self.header_count)):
            c = self.grid[r][col]
            if c is not None and c[4] and not M._UNIT_LINE.search(c[4]):
                return (c[0], c[1])
        return None

    def shared(self):
        """Ruling 7: copy columns whose value origins' leaf header also heads another copy column
        holding a value in the same row."""
        if self._shared is None:
            self._shared = set()
            for ri, row in enumerate(self.t['rows']):
                leaves = collections.defaultdict(set)
                for ci in range(1, len(row)):
                    if not has_digit(row[ci][2]):
                        continue
                    for o in self.digit_origins(ri, ci):
                        leaf = self.leaf(o[1])
                        if leaf is not None:
                            leaves[leaf].add(ci)
                for columns in leaves.values():
                    if len(columns) > 1:
                        self._shared |= columns
        return self._shared

    def unit_evidence(self):
        """Rulings 34 and 36: unit or currency evidence anywhere in the table's own cells. Every
        source cell, header rows, sub-headers, row labels and value cells, with digits or without,
        is read for: a currency symbol or code (CURRENCY_EVIDENCE, '$' cells and markers included)
        or word (CURRENCY_WORD); a word or scale unit (today's _ROW_UNIT); another unit
        (names_other_unit, period words stripped: '2025 (in years)', 'Years 2025', '2025 (x)');
        and, in a body value cell (column > 0), a unit after the number (VALUE_UNIT: '5.5
        years'). Every fact that is not a pure scale -2 percent fact (an amount fact, a fact in
        years) is evidence too. The table's context unit lines and caption-shaped context lines
        (Ruling 35) are not in the export JSON, so this reads the cells only."""
        if self._unit_evidence is None:
            facts = {o for o, items in self.facts.items()
                     if any(not (f['unit'] == ['xbrli:pure'] and f['scale'] == '-2') for f in items)}
            self._unit_evidence = False
            for c in self.t['source_cells']:
                text = c[4] or ''
                if (CURRENCY_EVIDENCE.search(text) or CURRENCY_WORD.search(text) or M._ROW_UNIT.search(text)
                        or names_other_unit(text) or (c[0], c[1]) in facts
                        or (c[0] >= self.header_count and c[1] > 0 and VALUE_UNIT.search(text))):
                    self._unit_evidence = True
                    break
        return self._unit_evidence

    def table_wide(self):
        """A spanning in-table caption before the first body row matching a table-wide declaration."""
        if self._table_wide is None:
            first_body = next((r for r in range(self.header_count, self.height)
                               if any(c is not None and (c[0], c[1]) == (r, col) and c[4]
                                      for col, c in enumerate(self.grid[r]))), self.height)
            self._table_wide = False
            for c in self.t['source_cells']:
                label = self.grid[c[0]][0]
                if (c[0] <= first_body and (c[1] == 0 or (label is not None and c[1] == label[3]))
                        and c[1] + c[3] == self.width and c[3] > 1 and TABLE_WIDE.fullmatch(c[4].strip())):
                    self._table_wide = True
        return self._table_wide


def unit_caption_row(row, columns):
    """Ruling 18a: a body row whose only content is digitless unit captions (today's _UNIT_LINE),
    one of them spanning more than one column over one of the given columns."""
    cells = [c for c in dict.fromkeys(c for c in row if c is not None) if c.text.strip()]
    return (bool(cells) and all(not has_digit(c.text) and M._UNIT_LINE.search(c.text) for c in cells)
            and any(c.colspan > 1 and any(c.column <= k < c.column + c.colspan for k in columns) for c in cells))


def audit_splits(base, new):
    """Every split '%' marker the attachment pass reaches, judged by the rules and found in NEW_DIR.

    The search (spec P4, as built in Task 3): in a body row that is not a period row (today's
    _period_row), a source origin whose whole text is '%' or ')%' looks left, across empty origins
    and '$' or '(' fragments, for the nearest other origin. It is reached when that origin starts
    in this row, is not in column 0, holds a digit and no '%', and is not period text (today's
    _period_text). The marker may attach only when (user decision 2026-10-13, Rulings 16, 18, 18a):
    - adjacent: the value ends in the column just left of the marker (Ruling 16);
    - covered: the marker's leaf heading is absent, or spans the value's last column (the user
      decision, amending Ruling 5);
    - marker-only: in every other body row, period rows included, whatever occupies the marker's
      columns is empty, '%', ')%', ')' or '%)', a unit-caption row aside (Rulings 18, 18a).
    In NEW_DIR the marker is joined when it sits in its value's copy cell. Outcomes:
    - 'joined on main too': the baseline copy cell already held both (column grouping, unchanged);
    - 'attached': the rules allow it and NEW_DIR joined it;
    - 'joined by column grouping under one leaf' (Ruling 19): the rules refuse the attachment, but
      value and marker sit under the same leaf heading and _column_groups merged that leaf's
      columns into one copy column, as main does whenever every row of the span converts cleanly
      (spec P4 lets '(x) %' rows pass that test). It holds only when, in addition, the value is
      the row's one digit origin under that leaf, the joined token is one complete number ending
      in its own '%', and the cell is a valid proven percent by its own '%'; otherwise the
      marker is 'JOINED AGAINST THE RULES'. This outcome was added after the first form of this
      audit flagged these 144 joins (see the README);
    - 'refused': the rules forbid it and NEW_DIR did not join it; the value goes to the safety net;
    - 'JOINED AGAINST THE RULES' or 'REFUSED AGAINST THE RULES': the branch disagrees with the rules.
    Sets new.refused and returns one record per reached marker."""
    records = []
    grid = new.grid
    for r in range(new.header_count, new.height):
        row = grid[r]
        if M._period_row(row):
            continue
        for col, marker in enumerate(row):
            if marker is None or (marker.row, marker.column) != (r, col) or marker.text not in SPLIT_MARKERS:
                continue
            value = next((c for c in reversed(row[:col]) if c is not None and c.text not in {'', '$', '('}), None)
            if (value is None or value.row != r or value.column == 0 or not has_digit(value.text)
                    or '%' in value.text or M._period_text(value.text)):
                continue
            last = value.column + value.colspan - 1
            leaf = new.leaf(col)
            leaf_cell = grid[leaf[0]][leaf[1]] if leaf else None
            columns = range(marker.column, marker.column + marker.colspan)
            rules = dict(
                adjacent=last + 1 == col,
                covered=leaf_cell is None or leaf_cell.column <= last < leaf_cell.column + leaf_cell.colspan,
                marker_only=all(c is None or c is marker or not c.text or c.text in SPLIT_MARKERS | CLOSING_FRAGMENTS
                                for k in range(new.header_count, new.height) if not unit_caption_row(grid[k], columns)
                                for c in (grid[k][j] for j in columns)))
            allowed = all(rules.values())
            v, m = (value.row, value.column), (marker.row, marker.column)
            joined = new.where.get(v) is not None and new.where.get(v) == new.where.get(m)
            on_main = base.where.get(v) is not None and base.where.get(v) == base.where.get(m)
            if on_main and joined:
                outcome = 'joined on main too'
            elif joined and allowed:
                outcome = 'attached'
            elif joined and leaf is not None and leaf == new.leaf(last):
                # Not the attachment pass: _column_groups merged the one leaf heading's span, which
                # spec P4 now lets a '(x) %' row pass (main's merge test refused it). Ruling 19's
                # exact conditions are checked below, once every refusal is known.
                outcome = 'joined by column grouping under one leaf'
            elif joined:
                outcome = 'JOINED AGAINST THE RULES'
            else:
                outcome = 'refused' if not allowed else 'REFUSED AGAINST THE RULES'
                new.refused.add(v)
            records.append(dict(filing=new.filing, ordinal=new.ordinal, value=list(v), marker=list(m),
                                value_text=value.text, marker_text=marker.text, rules=rules, outcome=outcome,
                                copy=list(new.where[v]) if v in new.where else None, leaf=leaf, row=r))
    for record in records:
        if record['outcome'] != 'joined by column grouping under one leaf':
            continue
        # Ruling 19: one digit origin in the row under that leaf (the value), the joined token is
        # one complete number ending in its own '%', and the cell's disposition is valid.
        leaf_cell = grid[record['leaf'][0]][record['leaf'][1]]
        under = {c for c in grid[record['row']][leaf_cell.column:leaf_cell.column + leaf_cell.colspan]
                 if c is not None and has_digit(c.text)}
        cell = new.cell(*record['copy'])
        token = cell['original'].strip()
        disposition, expected, proofs = expected_outcome(new, *record['copy'])
        checks = dict(one_digit_origin=len(under) == 1, own_percent=displayed(token) is not None and token.endswith('%'),
                      valid=disposition == 'proven percent' and 'own %' in proofs and matches(cell, expected))
        record['grouping_checks'] = checks
        if not all(checks.values()):
            record['outcome'] = 'JOINED AGAINST THE RULES'
    for record in records:
        record.pop('leaf'), record.pop('row')
    return records


def evidence(table, ri, ci):
    """The Rule P and Rule I evidence of a digit copy cell (see the module docstring)."""
    cell = table.cell(ri, ci)
    token = cell['original'].strip()
    d = displayed(token)
    # A '$' before the parenthesis is the structural join of a standalone '$' fragment
    # ('$ (120)'), which the exporter converts; '$(1,732)' or '$ (11.0)' in one source cell is no
    # complete token, and the converter rejects it.
    if d is not None and re.match(r'\$\s*\(', token) and not (
            token.startswith('$ (') and any(table.text_at.get(s) == '$' for s in cell['sources'])):
        d = None
    origins = table.digit_origins(ri, ci)
    facts = [f for o in origins for f in table.facts.get(o, [])]
    label = table.row_label(ri)
    labels = table.header_labels(ci)
    header = table.t['headers'][ci]
    own_pct = d is not None and '%' in token
    own_dollar = d is not None and '$' in token
    # The fact test without the count, then the count with nested facts (Ruling 3).
    single = (d is not None and len(origins) == 1 and len(facts) == 1 and facts[0]['unit'] == ['xbrli:pure']
              and facts[0]['scale'] == '-2' and facts[0]['format'] in FACT_FORMATS
              and digits_of(facts[0]['displayed']) == digits_of(token) and (facts[0]['sign'] == '-') == (d < 0 or d.is_signed()))
    pct_fact = single and not facts[0]['nested']
    amount_fact = any(m.lower().startswith('iso4217:') or m.lower() == 'xbrli:shares' for f in facts for m in f['unit'])
    # Ruling 21: a fact neither pure at scale -2 nor measured in a currency or shares is contrary
    # evidence (a pure fact at another scale, a fact in years, a unit the filing leaves undefined).
    contrary_fact = any(not (f['unit'] == ['xbrli:pure'] and f['scale'] == '-2')
                        and not any(m.lower().startswith('iso4217:') or m.lower() == 'xbrli:shares' for m in f['unit'])
                        for f in facts)
    declared = any(percent_declaration(part) for part in labels)
    shared = ci in table.shared()
    # Rulings 10, 11; Ruling 34: a caption in a table with unit evidence proves nothing, and every
    # column of such a table is a percent column, so values nothing else proves are P4 text.
    withheld = ((declared or table.table_wide()) and shared) or (table.table_wide() and table.unit_evidence())
    header_proof = declared and not shared
    row_proof = percent_declaration(label)
    row_unit = bool(M._ROW_UNIT.search(header) or M._ROW_UNIT.search(label))
    dollar_axis = '$' in header or '$' in label
    shown_percent = bool(M._PERCENT.search(token)) or any(M._PERCENT_UNIT.fullmatch(p.strip()) for p in (*labels, label))
    percent = [name for name, on in (('own %', own_pct), ('percent fact', pct_fact), ('percent header', header_proof),
                                     ('percent row label', row_proof)) if on]
    # Rulings 32, 33: a currency label under a table-wide caption (the in-table captions this
    # script sees; context-line declarations are not in the export JSON) is a conflict.
    table_wide_caption = table.table_wide()
    currency_label = any(CURRENCY_MARK.search(part or '') for part in (label, *labels))
    not_percent = [name for name, on in (('own $', own_dollar), ('amount fact', amount_fact),
                                         ('non-percent unit', row_unit)) if on]
    claimed = bool(percent) or declared or shown_percent
    # Ruling 21: no percent claim, a table-wide declaration included, overrides contrary evidence:
    # a contrary fact, or a row or header label naming another unit (Rulings 24-27).
    contrary = contrary_fact or any(names_other_unit(part) for part in (label, *labels))
    conflict = (((claimed or table_wide_caption) and contrary)
                or (table_wide_caption and currency_label)
                or (claimed and (amount_fact or row_unit or '$' in token or dollar_axis)))
    return dict(cell=cell, token=token, d=d, facts=facts, label=label, header=header, percent=percent,
                not_percent=not_percent, conflict=conflict, withheld=withheld,
                table_wide=(table.table_wide() and not table.unit_evidence() and not shared
                            and not M._VALUE.search(header)),
                nested_fact=single and not pct_fact,
                refused=any(s in table.refused for s in cell['sources']),
                # Ruling 21: under a heading naming a percent, a cell without a proof of its own
                # (own '%' or '$', a percent fact or an amount fact) is P4 text.
                percent_named=(any(percent_heading(part) for part in labels)
                               and not (own_pct or '$' in token or pct_fact or amount_fact)),
                points=bool(POINTS.fullmatch(token)), quantity=bool(facts) or own_pct or own_dollar,
                marks_column=(own_pct or pct_fact or row_proof) and not POINTS.fullmatch(token))


def column_flags(table, ci):
    """(percent column, quantity column) for a copy column.
    Spec P4 with Rulings 10 and 11: a digit cell of the column has own %, a percent fact or a
    percent row label, or the column holds a withheld declaration.
    Spec I2: some digit cell of the column proves a quantity itself."""
    if ci not in table.columns:
        cells = [evidence(table, ri, ci) for ri, row in enumerate(table.t['rows'])
                 if ci < len(row) and has_digit(row[ci][2])]
        table.columns[ci] = (any(e['marks_column'] or e['withheld'] for e in cells),
                             any(e['quantity'] for e in cells))
    return table.columns[ci]


def converter_reason(token, role):
    value = convert_cell(token, role=role)
    return value.review_reason


def rule_p(table, ci, e):
    """(disposition, expected, proofs) for a digit cell under Rule P: expected is a dict with the
    type and the value and format, or the allowed reasons."""
    token, d = e['token'], e['d']
    if e['conflict']:
        return 'text: conflict', dict(type='text', reasons={CONFLICT, CURRENCY_PERCENT}), []
    if e['points']:
        return 'text: points', dict(type='text', reasons={POINTS_REASON}), []
    if e['refused'] or e['percent_named']:
        # User decision (2026-10-13), Ruling 13: a value whose split '%' was refused is P4 text,
        # whatever its proofs; Ruling 21: so is a cell without a proof of its own under a heading
        # naming a percent. A zero converts and a token the converter rejects keeps its reason.
        reason = converter_reason(token, 'number')
        if reason:
            return 'text: converter', dict(type='text', reasons={reason}), []
        if d is not None and d.is_zero():
            return 'zero', dict(type='number', value=Decimal(0), format=expected_format(token, False)), []
        if e['refused']:
            return 'text: refused split % (P4)', dict(type='text', reasons={UNPROVEN}), []
        return 'text: percent-named heading (P4)', dict(type='text', reasons={UNPROVEN}), []
    proofs = e['percent'] or (['table-wide caption'] if e['table_wide'] and not e['not_percent'] else [])
    if proofs:
        reason = converter_reason(token, 'percent')
        if reason:
            return 'text: converter', dict(type='text', reasons={reason}), []
        return 'proven percent', dict(type='number', value=d / 100, format=expected_format(token, True)), proofs
    if e['not_percent']:
        if d is None:
            # Converted as today: a token the converter rejects keeps the converter's reason.
            return 'proven not a percent', dict(type='text', reasons={converter_reason(token, 'number')}), e['not_percent']
        return 'proven not a percent', dict(type='number', value=d, format=expected_format(token, False)), e['not_percent']
    if column_flags(table, ci)[0]:
        reason = converter_reason(token, 'number')
        if reason:
            return 'text: converter', dict(type='text', reasons={reason}), []
        if d is not None and d.is_zero():
            return 'zero', dict(type='number', value=Decimal(0), format=expected_format(token, False)), []
        return 'text: unproven (P4)', dict(type='text', reasons={UNPROVEN}), []
    return 'no proof outside a percent column', None, []


def identifier_named_reason(e):
    """Ruling 21, completed: under an identifier heading that names a percent, a cell without a
    proof of its own stays text with the P4 reason (or the converter's own reason), ranking below
    the conflict and points reasons and above the I2 reasons; a zero the converter accepts takes
    no P4 reason and falls through to I2. None when the rule does not apply."""
    if not e['percent_named']:
        return None
    reason = converter_reason(e['token'], 'number')
    if reason:
        return 'text: converter', dict(type='text', reasons={reason}), []
    if e['d'] is not None and e['d'].is_zero():
        return None
    return 'text: percent-named heading (P4)', dict(type='text', reasons={UNPROVEN}), []


def expected_outcome(table, ri, ci):
    """(disposition, expected, proofs) the spec's rules give any digit cell of NEW_DIR: Rule I under
    an identifier heading, else Rule P; a cell without proof outside a percent column keeps today's
    behaviour, its displayed number (a quantity proven under an identifier heading likewise)."""
    e = evidence(table, ri, ci)
    if M._identifier_heading(e['header']) and not e['quantity']:
        if e['conflict']:
            return 'text: conflict', dict(type='text', reasons={CONFLICT}), []
        if e['points']:
            return 'text: points', dict(type='text', reasons={POINTS_REASON}), []
        named = identifier_named_reason(e)
        if named:
            return named
        if column_flags(table, ci)[1]:
            return 'text: identifier over quantities', dict(type='text', reasons={QUANTITIES}), []
        if AMOUNT_FORMAT.fullmatch(e['token']) and not M._FOOTNOTE_MARK.fullmatch(e['token']):
            return 'text: identifier over amount-formatted', dict(type='text', reasons={AMOUNT_FORMATTED}), []
        return 'text: identifier, no reason', dict(type='text', reasons={None}), []
    disposition, expected, proofs = rule_p(table, ci, e)
    if (disposition in ('proven not a percent', 'no proof outside a percent column') and e['quantity']
            and M._identifier_heading(e['header'])):
        # Spec I1: the cell proves a quantity itself (its fact, or its own '$').
        disposition, proofs = 'proven quantity', e['not_percent'] or ['fact']
    if disposition in ('proven not a percent', 'proven quantity', 'no proof outside a percent column') \
            and e['d'] is not None:
        expected = dict(type='number', value=e['d'], format=expected_format(e['token'], False))
    return disposition, expected, proofs


def named_proof(disposition, proofs):
    """Whether a number converts on a named proof: own '%' or '$', a percent or amount fact, a
    percent header or row label, a table-wide caption, a non-percent unit, or (under an
    identifier heading) the cell's own quantity proof. A zero converted under spec P4's exception
    and a number with no proof outside a percent column have none."""
    return disposition in PROVEN and bool(proofs)


def matches(cell, expected):
    if expected is None:
        return False
    if expected['type'] == 'text':
        return (cell['type'] == 'text' and cell['reason'] in expected['reasons'] and cell['value'] == cell['original']
                and cell['format'] == '@')
    return (cell['type'] == 'number' and Decimal(cell['value']) == expected['value']
            and cell['reason'] is None and (expected['format'] is None or cell['format'] == expected['format']))


def same(a, b):
    return all(a[k] == b[k] for k in ('type', 'value', 'original', 'format', 'reason'))


def check_entry(entry, base, new):
    """One manifest entry: its disposition, the proofs named, and whether it is valid."""
    key = (entry['source_row'], entry['source_column'])
    ri, ci = new.where[key]
    e = evidence(new, ri, ci)
    cell = e['cell']
    out = dict(entry, new=dict(type=cell['type'], value=cell['value'], original=cell['original'],
                               format=cell['format'], reason=cell['reason']), copy=[ri, ci], header=e['header'],
               label=e['label'])
    if entry['kind'] == 'identifier_true' or not has_digit(cell['original']):
        b = base.cell(*base.where[key])
        valid = same(b, cell)
        out.update(disposition='unchanged' if valid else 'changed', proofs=[], valid=valid)
        return out
    # The cell is the manifest's cell: its digits did not change.
    assert digits_of(cell['original']) == digits_of(entry['displayed']), (entry, cell['original'])
    identifier = M._identifier_heading(e['header'])
    out['identifier_heading'] = identifier
    if not identifier or e['quantity']:
        # Spec I1: under an identifier heading only a cell proving a quantity itself takes the
        # ordinary role path, Rule P included.
        disposition, expected, proofs = rule_p(new, ci, e)
        if entry['kind'] in PERCENT_KINDS:
            # A percent row may be a proven percent or flagged text; a plain number keeps the wrong scale.
            valid = (disposition not in ('proven not a percent', 'no proof outside a percent column')
                     and matches(cell, expected))
        else:
            if disposition in ('proven not a percent', 'no proof outside a percent column') and e['quantity']:
                disposition, proofs = 'proven quantity', e['not_percent'] or ['fact']
                expected = (dict(type='number', value=e['d'], format=expected_format(e['token'], False))
                            if e['d'] is not None else None)
            # A misread cell no longer under an identifier heading, without proof, is not a disposition.
            valid = disposition != 'no proof outside a percent column' and matches(cell, expected)
    else:
        if e['conflict']:
            disposition, reasons = 'text: conflict', {CONFLICT}
        elif e['points']:
            disposition, reasons = 'text: points', {POINTS_REASON}
        elif identifier_named_reason(e):
            disposition, expected, _ = identifier_named_reason(e)
            reasons = expected['reasons']
        elif column_flags(new, ci)[1]:
            disposition, reasons = 'text: identifier over quantities', {QUANTITIES}
        elif AMOUNT_FORMAT.fullmatch(e['token']) and not M._FOOTNOTE_MARK.fullmatch(e['token']):
            disposition, reasons = 'text: identifier over amount-formatted', {AMOUNT_FORMATTED}
        else:
            disposition, reasons = 'text: identifier, no reason', {None}
        expected, proofs = dict(type='text', reasons=reasons), []
        # Spec Acceptance 3: no manifest cell may be unflagged text that holds an amount. Spec I2
        # leaves a plain cell of a column without quantity evidence unflagged; for a manifest
        # cell (a percent row or a misread amount) that is not a valid disposition.
        valid = disposition != 'text: identifier, no reason' and matches(cell, expected)
    out.update(disposition=disposition, proofs=proofs, valid=valid,
               expected=None if expected is None else {k: (sorted(v, key=str) if isinstance(v, set) else str(v))
                                                       for k, v in expected.items()})
    return out


def sweep_cells(name, base, new):
    """The all-cells sweep: every digit copy cell of NEW_DIR (column 0 aside) against the checker's
    expectation (expected_outcome). Two stated cases are judged against the baseline cell instead
    (same value origin; type, value, original, format and reason must be identical):
    - "today's behaviour": every cell where the checker finds no proof and no percent column must
      be identical to base, whether or not it equals the displayed number (spec: plain numbers in
      columns without evidence of another scale keep today's behaviour; the checker does not model
      main's role rules, such as 'Numeric role unresolved', or a footnote-marker reason);
    - "NVDA context declaration": an NVDA number equal to the displayed number / 100 in a table
      with no in-table table-wide caption, whose declaration sits in the context lines before the
      table, which the export JSON does not hold (spec: NVDA's 495 percent-of-revenue values stay
      as they are). The gate requires exactly 495 such cells.
    Any other cell is a mismatch and fails the gate."""
    out = []
    for ri, row in enumerate(new.t['rows']):
        for ci in range(1, len(row)):
            if not has_digit(row[ci][2]):
                continue
            disposition, expected, proofs = expected_outcome(new, ri, ci)
            cell = new.cell(ri, ci)
            origins = new.digit_origins(ri, ci)
            b = base.where.get(origins[0]) if origins else None
            unchanged = b is not None and same(base.cell(*b), cell)
            if disposition == 'no proof outside a percent column':
                # Today's behaviour is main's own output: such a cell must be identical to base,
                # even where it would equal the checker's displayed-number approximation.
                category = "today's behaviour (identical to base)" if unchanged else 'MISMATCH'
            elif matches(cell, expected):
                category = 'as the checker expects'
            else:
                d = displayed(cell['original'])
                if (unchanged and group(name) == 'NVDA' and cell['type'] == 'number' and d is not None
                      and Decimal(cell['value']) == d / 100 and not new.table_wide()):
                    category = 'NVDA context declaration (identical to base)'
                else:
                    category = 'MISMATCH'
            out.append(dict(filing=name, ordinal=new.ordinal, copy=[ri, ci], disposition=disposition,
                            category=category, type=cell['type'], value=cell['value'], original=cell['original'],
                            reason=cell['reason'], header=new.t['headers'][ci], label=new.row_label(ri)))
    return out


def percent_fact_cells(name, table):
    """Spec Acceptance 6: every digit cell whose percent-fact evidence holds."""
    out = []
    for ri, row in enumerate(table.t['rows']):
        for ci in range(1, len(row)):
            if not has_digit(row[ci][2]):
                continue
            e = evidence(table, ri, ci)
            if e['nested_fact']:
                cell = e['cell']
                out.append(dict(filing=name, ordinal=table.ordinal, copy=[ri, ci], token=e['token'], fact=e['facts'][0],
                                new=dict(type=cell['type'], value=cell['value'], reason=cell['reason']),
                                outcome='not proof: nested fact'))
            if 'percent fact' not in e['percent']:
                continue
            fact = e['facts'][0]
            fact_value = Decimal(digits_of(fact['displayed'])) / 100
            if fact['sign'] == '-':
                fact_value = -fact_value
            cell = e['cell']
            ok = cell['type'] == 'number' and Decimal(cell['value']) == fact_value
            out.append(dict(filing=name, ordinal=table.ordinal, copy=[ri, ci], token=e['token'], fact=fact,
                            fact_value=str(fact_value), new=dict(type=cell['type'], value=cell['value'],
                                                                  reason=cell['reason']),
                            other_proofs=[p for p in e['percent'] if p != 'percent fact'],
                            outcome='equal' if ok else 'text' if cell['type'] == 'text' else 'DIFFERENT'))
    return out


def load(directory, name):
    data = json.load(open(os.path.join(directory, name + '.json'), encoding='utf-8'))
    return {t['ordinal']: t for t in data['tables']}


def main():
    global M, convert_cell
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('new')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--src', required=True)
    parser.add_argument('--details')
    args = parser.parse_args()
    sys.path.insert(0, os.path.abspath(args.src))
    import sec2md.xlsx_tables as M
    from sec2md.xlsx_values import convert_cell
    assert os.path.realpath(M.__file__).startswith(os.path.realpath(args.src)), M.__file__

    manifest = json.load(open(args.manifest, encoding='utf-8'))
    by_filing = collections.defaultdict(list)
    for entry in manifest:
        by_filing[entry['filing']].append(entry)
    results, facts, splits, swept = [], [], [], []
    names = sorted(n[:-5] for n in os.listdir(args.new))
    assert names == sorted(n[:-5] for n in os.listdir(args.base)), 'the two exports hold different filings'
    nested_total = collections.Counter()
    for name in names:
        base_tables, new_tables = load(args.base, name), load(args.new, name)
        assert sorted(base_tables) == sorted(new_tables), (name, 'table ordinals differ')
        nested = nested_facts(json.load(open(os.path.join(args.new, name + '.json'), encoding='utf-8'))['path'])
        nested_total[group(name)] += sum(nested.values())
        # Building a Table asserts that its source coordinates are unique, on both sides.
        base = {o: Table(name, t, nested) for o, t in base_tables.items()}
        new = {o: Table(name, t, nested) for o, t in new_tables.items()}
        for ordinal, t in new.items():
            if t.t['status'] == 'source_text_only':
                continue
            for record in audit_splits(base[ordinal], t):
                if record['outcome'] == 'refused' and record['copy']:
                    disposition, expected, _ = expected_outcome(t, *record['copy'])
                    record.update(disposition=disposition, new=t.cell(*record['copy']),
                                  cell_valid=matches(t.cell(*record['copy']), expected))
                splits.append(record)
        for ordinal, t in new.items():
            if t.t['status'] != 'source_text_only':
                facts.extend(percent_fact_cells(name, t))
                swept.extend(sweep_cells(name, base[ordinal], t))
        for entry in by_filing.get(name, []):
            assert new[entry['ordinal']].t['status'] != 'source_text_only', (entry, 'table fell back to source text')
            results.append(check_entry(entry, base[entry['ordinal']], new[entry['ordinal']]))
    assert len(results) == len(manifest), (len(results), len(manifest))

    print(f'Manifest entries: {len(results)}')
    print('Facts nested in another fact, from the filings tags: ' + ', '.join(f'{g} {nested_total[g]}' for g in GROUPS))
    print('\nDispositions per kind (valid / all):')
    for kind in KINDS:
        chosen = [r for r in results if r['kind'] == kind]
        print(f'  {kind}: {len(chosen)}')
        for disposition, n in sorted(collections.Counter(r['disposition'] for r in chosen).items()):
            valid = sum(r['valid'] for r in chosen if r['disposition'] == disposition)
            print(f'    {disposition}: {valid} / {n}')
            proofs = collections.Counter(' + '.join(r['proofs']) for r in chosen
                                         if r['disposition'] == disposition and r['proofs'])
            for proof, m in sorted(proofs.items()):
                print(f'        proof {proof}: {m}')
    print('\nPer kind and group (disposition: cells):')
    for kind in KINDS:
        for g in GROUPS:
            chosen = [r for r in results if r['kind'] == kind and group(r['filing']) == g]
            if chosen:
                counts = collections.Counter(r['disposition'] for r in chosen)
                print(f'  {kind} {g}: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    invalid = [r for r in results if not r['valid']]
    print(f'\nEntries without a valid disposition: {len(invalid)}')
    for r in invalid:
        print(f"  {r['filing']} #{r['ordinal']} ({r['source_row']}, {r['source_column']}) {r['kind']} "
              f"{r['displayed']!r} -> {r['new']} [{r['disposition']}] expected {r.get('expected')} "
              f"header {r['header']!r} label {r['label']!r}")
    true_changed = [r for r in results if r['kind'] == 'identifier_true' and not r['valid']]
    print(f'identifier_true cells changed: {true_changed and len(true_changed) or 0}')

    print(f'\nPercent-fact cells in the branch export: {len(facts)}')
    for outcome, n in sorted(collections.Counter(f['outcome'] for f in facts).items()):
        print(f'  {outcome}: {n}')
    for k, n in sorted(collections.Counter((group(f['filing']), f['outcome']) for f in facts).items()):
        print(f'    {k[0]} {k[1]}: {n}')
    for f in facts:
        if f['outcome'] != 'equal':
            print(f"  {f['outcome']}: {f['filing']} #{f['ordinal']} {f['copy']} {f['token']!r} fact "
                  f"{f['fact']['displayed']!r} sign {f['fact']['sign']} -> {f['new']}")
    different = [f for f in facts if f['outcome'] == 'DIFFERENT']
    print(f'Percent-fact numbers that differ from the fact: {len(different)}')

    print(f'\nSplit % markers the attachment pass reaches: {len(splits)}')
    for outcome, n in sorted(collections.Counter(x['outcome'] for x in splits).items()):
        print(f'  {outcome}: {n}')
    for k, n in sorted(collections.Counter((group(x['filing']), x['outcome']) for x in splits).items()):
        print(f'    {k[0]} {k[1]}: {n}')
    grouped = [x for x in splits if 'grouping_checks' in x]
    print(f'  same-leaf grouping joins checked against Ruling 19: {len(grouped)}; '
          + ', '.join(f'{k} {sum(x["grouping_checks"][k] for x in grouped)}'
                      for k in ('one_digit_origin', 'own_percent', 'valid')))
    refusals = collections.Counter(' + '.join(r for r, ok in x['rules'].items() if not ok)
                                   for x in splits if x['outcome'] == 'refused')
    print('  refused, by failed rule: ' + ', '.join(f'{k} {v}' for k, v in sorted(refusals.items())))
    print('  refused values, by outcome: ' + ', '.join(
        f'{k} {v}' for k, v in sorted(collections.Counter(x.get('disposition') for x in splits
                                                           if x['outcome'] == 'refused').items())))
    disagree = [x for x in splits if x['outcome'].isupper() or x.get('cell_valid') is False]
    print(f'Split markers where the branch and the rules disagree, or a refused value is not as the rules give: '
          f'{len(disagree)}')
    for x in disagree:
        print(f"  {x['filing']} #{x['ordinal']} value {x['value']} {x['value_text']!r} marker {x['marker']} "
              f"{x['marker_text']!r} {x['rules']} {x['outcome']} {x.get('disposition')} {x.get('new')}")
    print(f'\nAll-cells sweep: {len(swept)} digit cells of NEW_DIR (column 0 aside), every table not source text')
    for category, n in sorted(collections.Counter(x['category'] for x in swept).items()):
        print(f'  {category}: {n}')
    for k, n in sorted(collections.Counter((x['category'], x['disposition']) for x in swept).items()):
        print(f'    {k[0]} / {k[1]}: {n}')
    nvda = sum(x['category'] == 'NVDA context declaration (identical to base)' for x in swept)
    mismatched = [x for x in swept if x['category'] == 'MISMATCH']
    print(f'  NVDA context-declaration cells: {nvda} (the spec\'s 495: {"yes" if nvda == 495 else "NO"}); '
          f'mismatches: {len(mismatched)}')
    for x in mismatched:
        print(f"  MISMATCH {x['filing']} #{x['ordinal']} {x['copy']} {x['original']!r} -> {x['type']} {x['value']!r} "
              f"{x['reason']} [{x['disposition']}] header {x['header']!r} label {x['label']!r}")
    sweep_ok = not mismatched and nvda == 495
    gate = not invalid and not different and not disagree and sweep_ok
    print(f'\nGATE (Acceptance 3 and 6, split audit, all-cells sweep): {"pass" if gate else "FAIL"}')
    if args.details:
        with open(args.details, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(dict(entries=results, percent_facts=facts, splits=splits,
                           sweep=[x for x in swept if x['category'] != 'as the checker expects']),
                      handle, ensure_ascii=False, indent=1, default=str)
    sys.exit(0 if gate else 1)


if __name__ == '__main__':
    main()
