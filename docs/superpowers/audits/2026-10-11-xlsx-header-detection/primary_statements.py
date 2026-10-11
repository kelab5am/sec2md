"""Check the balance sheet, income statement and cash flow statement of each filing.

    python -I primary_statements.py NEW_DIR --report statements.md --details statements.json

Reads an export_tables.py output directory. For each statement:

1. Identify the statement from its source rows, not its export result: the
   candidate table (row labels such as 'Total assets') with the most inline
   XBRL facts. A close second candidate is reported as ambiguous.
2. Give every XBRL fact in the statement a verdict, using the fact inside that
   exact source cell (see export_tables.py):
   - fallback: the table exported as source text;
   - not in body: the fact's cell did not reach the copy table's body;
   - not numeric: the copy cell holding it is text;
   - value: the copy number differs from the fact's displayed amount;
   - sign: the copy number's sign differs from the displayed brackets;
   - period unresolved: the column header names no parseable period;
   - period: the fact's context is not the header's period. Balance sheets
     need instants at the header date. Income statements need durations
     ending at the header date, with the header's length when it states one.
     Cash flow statements need durations, except opening balances (an instant
     at the period's start) and closing balances and their breakdown (an
     instant at its end);
   - ok.
   Nil facts shown as a dash are ok when the copy cell keeps the dash (with or
   without its '$').
3. Count numbers with no fact behind them (untagged), apart from a repeated
   total equal to a tagged number in its column (repeated), and value columns
   whose header has no year (yearless).
4. Arithmetic, in Decimal: total assets equals total liabilities and equity in
   every column; closing cash equals opening cash plus the net change, with or
   without the exchange-rate effect. A missing or non-numeric operand fails.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal, InvalidOperation

MONTHS = {m: i for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split(), 1)}
DATE = re.compile(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2}),?(?: ((?:19|20)\d{2}))?', re.I)
YEARS = re.compile(r'\b((?:19|20)\d{2})\b')
SPANS = {'three': 3, 'six': 6, 'nine': 9, 'twelve': 12}
MARKERS = {
    'BS': (r'total assets', r"total liabilities(,| and)? .*(stockholders|shareholders|equity).*"),
    'IS': (r'net (income|loss|income \(loss\)|\(loss\) income|earnings)( attributable to .*)?',
           r'(total )?(net )?(revenues?|sales)|total net revenue'),
    'CF': (r'net cash (provided by|used in|provided by \(used in\)|\(used in\) provided by|used for'
           r'|provided by \(used for\)|from) operating activities', r'.*end of (the )?(period|year).*'),
}
OPENING = re.compile(r'beginning of (the )?(period|year)')
CLOSING = re.compile(r'end of (the )?(period|year)')


def norm(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip().lower()


def labels(table):
    return {norm(c[4]) for c in table['source_cells'] if c[1] == 0}


def is_kind(table, kind):
    first, second = MARKERS[kind]
    found = labels(table)
    return any(re.fullmatch(first, label) for label in found) and any(re.fullmatch(second, label) for label in found)


def header_period(header):
    """(months, or None for a bare date; end date) named by a flattened header, or None."""
    text = header.replace(' — ', ' ')
    match = DATE.search(text)
    if not match:
        return None
    year = match.group(3) or next(iter(YEARS.findall(text[match.end():])), None) or next(iter(YEARS.findall(text)), None)
    if not year:
        return None
    end = datetime.date(int(year), MONTHS[match.group(1).lower()[:3]], int(match.group(2)))
    lower = text.lower()
    months = next((v for k, v in SPANS.items() if f'{k} months' in lower), None)
    if months is None and re.search(r'\byears? ended\b|\bfiscal year\b', lower):
        months = 12
    return months, end


def period_ok(kind, row_label, context, period):
    ctype, start, end = context[0], context[1], context[2]
    end = datetime.date.fromisoformat(end)
    months, header_end = period

    def near(a, b, days=7):
        return abs((a - b).days) <= days  # 52/53-week fiscal years

    if kind == 'BS':
        return ctype == 'I' and near(end, header_end)
    if kind == 'CF' and OPENING.search(row_label):
        if ctype != 'I':
            return False
        if months is None:
            return 28 <= (header_end - end).days <= 380
        return near(end, header_end - datetime.timedelta(days=round(months * 30.44)), 10)
    if kind == 'CF' and ctype == 'I':
        # Closing balances and their breakdown ('Cash and cash equivalents' under the
        # reconciliation) are instants at the column's end date.
        return near(end, header_end)
    if ctype != 'D' or not near(end, header_end):
        return False
    span = round((end - datetime.date.fromisoformat(start)).days / 30.44)
    return span == months if months is not None else span in (3, 6, 9, 12)


def displayed(text):
    cleaned = re.sub(r'[,$\s]', '', text or '')
    try:
        return Decimal(cleaned) if re.fullmatch(r'\d+(\.\d+)?', cleaned) else None
    except InvalidOperation:
        return None


def verdicts(table, kind, contexts):
    result = dict(kind=kind, ordinal=table['ordinal'], title=table['title'][:60], status=table['status'],
                  provenance=table['provenance'], facts=len(table['facts']), ok=0, failures=collections.Counter(),
                  examples=[], untagged=0, repeated=0, yearless=[], arithmetic=[])
    where = {}
    for ri, sources in enumerate(table['cell_sources']):
        for ci, cell_sources in enumerate(sources):
            for source in cell_sources:
                where[tuple(source)] = (ri, ci)

    def fail(reason, detail):
        result['failures'][reason] += 1
        if len(result['examples']) < 40:
            result['examples'].append([reason, *detail])

    if table['provenance'] != 'unique':
        fail('no provenance', [table['provenance']])
    fact_cells = set()
    for row, col, context_id, concept, text, sign in table['facts']:
        fact_cells.add((row, col))
        if col == 0:
            continue
        if table['status'] == 'source_text_only':
            fail('fallback', [row, col, text])
            continue
        if (row, col) not in where:
            fail('not in body', [row, col, text])
            continue
        ri, ci = where[(row, col)]
        kind_, value, original = table['rows'][ri][ci]
        amount = displayed(text)
        if amount is None or amount == 0:
            shown = re.sub(r'[$\s]', '', original or '')
            if kind_ == 'number' and Decimal(value) == 0 or shown == re.sub(r'\s', '', text or ''):
                result['ok'] += 1
            else:
                fail('nil', [row, col, text, original])
            continue
        if kind_ != 'number':
            fail('not numeric', [row, col, text, original])
            continue
        number = Decimal(value)
        if abs(number) != amount and not ('%' in (original or '') and abs(number) * 100 == amount):
            fail('value', [row, col, text, value])
            continue
        if (number < 0) != bool(re.search(r'[(−-]', original or '')):
            fail('sign', [row, col, original, value])
            continue
        header = table['headers'][ci]
        period = header_period(header)
        if period is None:
            fail('period unresolved', [header])
            continue
        context = contexts.get(context_id)
        row_label = norm(table['rows'][ri][0][1])
        if context is None or not period_ok(kind, row_label, context, period):
            fail('period', [row_label[:40], header, text, context])
            continue
        result['ok'] += 1
    if table['status'] != 'source_text_only':
        texts = {(c[0], c[1]): c[4] for c in table['source_cells']}
        value_columns = set()
        tagged = collections.defaultdict(set)  # column -> values of tagged numbers
        untagged = []
        for ri, row in enumerate(table['rows']):
            for ci, (kind_, value, original) in enumerate(row):
                if ci == 0 or kind_ != 'number':
                    continue
                value_columns.add(ci)
                sources = [tuple(s) for s in table['cell_sources'][ri][ci]]
                if any(s in fact_cells for s in sources):
                    tagged[ci].add(Decimal(value))
                elif any(re.search(r'\d', texts.get(s, '')) for s in sources):
                    untagged.append((ci, Decimal(value), norm(row[0][1])[:40]))
        for ci, value, row_label in untagged:
            # A repeated total the filer tagged once ('Total cash, cash equivalents, and
            # restricted cash' under the reconciliation) is reported separately.
            if value in tagged[ci]:
                result['repeated'] += 1
            else:
                result['untagged'] += 1
                if len(result['examples']) < 40:
                    result['examples'].append(['untagged', row_label, table['headers'][ci], str(value)])
        result['yearless'] = [table['headers'][ci] for ci in sorted(value_columns) if not YEARS.search(table['headers'][ci])]
        result['arithmetic'] = arithmetic(table, kind)
    result['failures'] = dict(result['failures'])
    return result


def arithmetic(table, kind):
    problems = []

    def find(pattern):
        return [row for row in table['rows'] if re.fullmatch(pattern, norm(row[0][1]))]

    def number(cell):
        return Decimal(cell[1]) if cell[0] == 'number' else None

    columns = [ci for ci in range(1, len(table['headers'])) if any(row[ci][0] == 'number' for row in table['rows'])]
    if kind == 'BS':
        assets, equity = find(MARKERS['BS'][0]), find(MARKERS['BS'][1])
        if not assets or not equity:
            return ['total assets or total liabilities and equity row not found']
        for ci in columns:
            a, e = number(assets[0][ci]), number(equity[0][ci])
            if a is None or e is None or a != e:
                problems.append(f'{table["headers"][ci]}: assets {assets[0][ci][2]!r} vs L+E {equity[0][ci][2]!r}')
    if kind == 'CF':
        opening = find(r'.*beginning of (the )?(period|year).*')
        closing = find(r'.*end of (the )?(period|year).*')
        change = find(r'(net )?(increase|decrease|change|\(decrease\) increase|increase \(decrease\)'
                      r'|decrease \(increase\)) in cash.*')
        fx = find(r'effect of (foreign )?(currency )?exchange rate.*')
        if not (opening and closing and change):
            return ['opening, change or closing cash row not found']
        for ci in columns:
            o, c, e = number(opening[0][ci]), number(change[0][ci]), number(closing[0][ci])
            f = number(fx[0][ci]) if fx else Decimal(0)
            if None in (o, c, e):
                problems.append(f'{table["headers"][ci]}: non-numeric operand')
            elif o + c != e and o + c + (f or 0) != e:
                problems.append(f'{table["headers"][ci]}: {o} + {c} (fx {f}) != {e}')
    return problems


def check(path):
    data = json.load(open(path, encoding='utf-8'))
    statements = []
    for kind in ('BS', 'IS', 'CF'):
        candidates = sorted((t for t in data['tables'] if is_kind(t, kind)), key=lambda t: -len(t['facts']))
        if not candidates:
            statements.append(dict(kind=kind, missing=True))
            continue
        result = verdicts(candidates[0], kind, data['contexts'])
        if len(candidates) > 1 and len(candidates[1]['facts']) >= 0.8 * len(candidates[0]['facts']) > 0:
            result['ambiguous_with'] = [candidates[1]['ordinal'], candidates[1]['title'][:60]]
        statements.append(result)
    return dict(file=data['file'], statements=statements)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('new')
    parser.add_argument('--report', required=True)
    parser.add_argument('--details', required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    paths = [os.path.join(args.new, name) for name in sorted(os.listdir(args.new))]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check, paths))
    with open(args.details, 'w', encoding='utf-8') as handle:
        json.dump(results, handle, indent=1, default=str)
    lines = ['| Filing | Statement | Status | Facts | OK | Failures | Untagged | Repeated | Yearless | Arithmetic '
             '| Ambiguous |', '|---|---|---|---|---|---|---|---|---|---|---|']
    totals = collections.Counter()
    for r in results:
        for s in r['statements']:
            if s.get('missing'):
                lines.append(f"| {r['file'][:44]} | {s['kind']} | not found | | | | | | | | |")
                totals['not found'] += 1
                continue
            failures = sum(s['failures'].values())
            for key, value in (('facts', s['facts']), ('ok', s['ok']), ('failures', failures),
                               ('untagged', s['untagged']), ('repeated', s['repeated']),
                               ('yearless', len(s['yearless'])),
                               ('arithmetic', len(s['arithmetic'])), ('ambiguous', 'ambiguous_with' in s)):
                totals[key] += value
            lines.append(f"| {r['file'][:44]} | {s['kind']} | {s['status']} | {s['facts']} | {s['ok']} | "
                         f"{json.dumps(s['failures']) if failures else 0} | {s['untagged']} | {s['repeated']} | "
                         f"{len(s['yearless'])} | "
                         f"{len(s['arithmetic'])} | {s.get('ambiguous_with', '')} |")
    lines += ['', 'Totals: ' + json.dumps(dict(totals)), '', '## Problems', '']
    for r in results:
        for s in r['statements']:
            for item in s.get('examples', []):
                lines.append(f"- {r['file']} {s['kind']} #{s.get('ordinal')}: {json.dumps(item, ensure_ascii=False)}")
            for item in s.get('yearless', []):
                lines.append(f"- {r['file']} {s['kind']} #{s.get('ordinal')}: yearless header {item!r}")
            for item in s.get('arithmetic', []):
                lines.append(f"- {r['file']} {s['kind']} #{s.get('ordinal')}: arithmetic {item}")
    with open(args.report, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('Totals:', dict(totals))


if __name__ == '__main__':
    main()
