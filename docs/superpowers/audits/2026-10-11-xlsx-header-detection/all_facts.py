"""Check every inline XBRL fact in every exported table against its column header's period.

    python -I all_facts.py EXPORT_DIR --report all-facts.md --details all-facts.json

Reads an export_tables.py output directory (spec Acceptance 3b). Run it once per
export directory, on `main` and on the branch.

1. Every inline XBRL fact in every table that is not source_text_only gets one
   verdict, from the fact inside its own source cell:
   - label column: the fact is in column 0, which has no period header;
   - not placed: no copy cell holds the fact's source cell;
   - no header date: the column header names no month, day and year;
   - mismatch or ok: period_verdict() against the column header.
   Verdict counts are reported per group (META, NVDA, RDDT, Others), and every
   mismatch is listed with its source cell, context and header.
2. Every table whose column headers carry period wording (a month and day,
   `... ended`, `... ending` or `as of`) without a year is listed: a yearless
   period header. Column 0 is included.
3. Every table with is_numeric_fact source cells but no located facts is listed
   with its fact-cell count. export_tables.py could not match its source
   element, so this script cannot check it.

period_verdict() reads the header's date and its stated length: `three`, `six`,
`nine` or `twelve months`, `quarter`, `year` or `fiscal year`, or 13, 26, 39, 52
or 53 weeks, followed by `ended` or `ending`. A header with a date and no stated
length is a bare date. `Less than 12 months` and `(in years)` state no length.
- Instants are ok within 7 days of the header date (52/53-week years), or
  within 7 days of the start of a stated period (an opening balance).
- Durations are ok ending within 7 days of the header date, with the stated
  length when there is one. A duration starting the day after the header date
  is ok only under a bare date (`December 31, 2024` over the next year's
  activity); under a stated length it is a mismatch.
Numeric dates (`1/31/2020`) are not read: such a header has no header date.
"""

import argparse
import calendar
import collections
import datetime
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

GROUPS = ('META', 'NVDA', 'RDDT', 'Others')
VERDICTS = ('ok', 'mismatch', 'no header date', 'label column', 'not placed')
MONTHS = {m: i for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split(), 1)}
DATE = re.compile(r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?'
                  r'|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})\b'
                  r',?(?:\s+((?:19|20)\d{2})\b)?', re.I)
YEARS = re.compile(r'\b(?:19|20)\d{2}\b')
LENGTHS = {'three': 3, '3': 3, 'quarter': 3, 'six': 6, '6': 6, 'nine': 9, '9': 9, 'twelve': 12, '12': 12,
           'year': 12, 'thirteen': 3, '13': 3, 'twenty-six': 6, '26': 6, 'thirty-nine': 9, '39': 9,
           'fifty-two': 12, '52': 12, 'fifty-three': 12, '53': 12}
STATED = re.compile(r'\b(?:(three|six|nine|twelve|3|6|9|12)[- ]months?'
                    r'|(thirteen|twenty-six|thirty-nine|fifty-two|fifty-three|13|26|39|52|53)[- ]weeks?'
                    r'|(quarter|year)s?)(?:[- ]period)?\s+(?:ended|ending)\b', re.I)
PERIOD_WORDING = re.compile(DATE.pattern + r'|' + STATED.pattern + r'|\b(?:ended|ending|as of)\b', re.I)
NEAR = 7  # days: 52/53-week fiscal years end within a week of the month end


def header_period(header):
    """(stated length in months, or None for a bare date; header date), or None without a dated year."""
    text = header.replace(' — ', ' ')
    match = DATE.search(text)
    if not match:
        return None
    years = YEARS.findall(text[match.end():]) or YEARS.findall(text)
    year = match.group(3) or (years[0] if years else None)
    if not year:
        return None
    try:
        date = datetime.date(int(year), MONTHS[match.group(1).lower()[:3]], int(match.group(2)))
    except ValueError:
        return None
    stated = STATED.search(text)
    months = LENGTHS[next(g for g in stated.groups() if g).lower()] if stated else None
    return months, date


def months_before(date, months):
    """The date `months` calendar months earlier; a month end maps to a month end."""
    year, month = divmod(date.year * 12 + date.month - 1 - months, 12)
    last = calendar.monthrange(year, month + 1)[1]
    month_end = date.day == calendar.monthrange(date.year, date.month)[1]
    return datetime.date(year, month + 1, last if month_end else min(date.day, last))


def length_in_months(start, end):
    return round(((end - start).days + 1) / (365.25 / 12))


def near(a, b):
    return abs((a - b).days) <= NEAR


def period_verdict(context, header):
    """'ok', 'mismatch' or 'no header date' for a fact's context ([type, start, end, dims]) under a header."""
    period = header_period(header)
    if period is None:
        return 'no header date'
    if context is None:
        return 'mismatch'
    months, date = period
    end = datetime.date.fromisoformat(context[2])
    if context[0] == 'I':
        if near(end, date) or months is not None and near(end, months_before(date, months)):
            return 'ok'
        return 'mismatch'
    start = datetime.date.fromisoformat(context[1])
    if near(end, date):
        return 'ok' if months is None or length_in_months(start, end) == months else 'mismatch'
    if months is None and start == date + datetime.timedelta(days=1):
        return 'ok'
    return 'mismatch'


def group(file):
    company = file.split('__')[0]
    return company if company in ('META', 'NVDA', 'RDDT') else 'Others'


def show_context(context_id, context):
    if context is None:
        return f'{context_id}: missing'
    kind, start, end, dims = context
    period = f'I {end}' if kind == 'I' else f'D {start}..{end}'
    return f'{context_id}: {period}' + (' (dims)' if dims else '')


def check(path):
    with open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    result = dict(file=data['file'], group=group(data['file']), tables=0, counts=collections.Counter(),
                  table_counts=[], mismatches=[], not_placed=[], yearless=[], unlocated=[])
    for table in data['tables']:
        if table['status'] == 'source_text_only':
            continue
        result['tables'] += 1
        about = dict(ordinal=table['ordinal'], title=table['title'][:60], status=table['status'])
        where = {}
        for ri, sources in enumerate(table['cell_sources']):
            for ci, cell_sources in enumerate(sources):
                for source in cell_sources:
                    where[tuple(source)] = (ri, ci)
        counts = collections.Counter()
        for row, col, context_id, concept, text, sign in table['facts']:
            placed = where.get((row, col))
            if col == 0 or placed is not None and placed[1] == 0:
                verdict = 'label column'
            elif placed is None:
                verdict = 'not placed'
                result['not_placed'].append(dict(about, cell=[row, col], text=text, concept=concept))
            else:
                ri, ci = placed
                context = data['contexts'].get(context_id)
                verdict = period_verdict(context, table['headers'][ci])
                if verdict == 'mismatch':
                    result['mismatches'].append(dict(
                        about, cell=[row, col], label=table['rows'][ri][0][1], text=text, concept=concept,
                        context=show_context(context_id, context), header=table['headers'][ci],
                        copy=table['rows'][ri][ci]))
            counts[verdict] += 1
        result['counts'].update(counts)
        if counts:
            result['table_counts'].append(dict(about, counts=dict(counts)))
        yearless = [[ci, header] for ci, header in enumerate(table['headers'])
                    if PERIOD_WORDING.search(header) and not YEARS.search(header)]
        if yearless:
            result['yearless'].append(dict(about, headers=yearless))
        fact_cells = sum(1 for cell in table['source_cells'] if cell[5])
        if fact_cells and not table['facts']:
            result['unlocated'].append(dict(about, provenance=table['provenance'], fact_cells=fact_cells))
    result['counts'] = dict(result['counts'])
    return result


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def report(export_dir, results):
    totals = {g: collections.Counter() for g in GROUPS}
    for r in results:
        totals[r['group']]['tables'] += r['tables']
        totals[r['group']].update(r['counts'])
    lines = [f'# All-table XBRL period check: `{os.path.basename(os.path.normpath(export_dir))}`', '',
             f'{len(results)} filings. Every inline XBRL fact in every table that is not `source_text_only`.', '',
             '## Verdicts per group', '',
             '| Group | Tables | Facts | ' + ' | '.join(VERDICTS) + ' |', '|---|---|---|' + '---|' * len(VERDICTS)]
    grand = collections.Counter()
    for g in GROUPS:
        grand.update(totals[g])
        facts = sum(totals[g][v] for v in VERDICTS)
        lines.append(f'| {g} | {totals[g]["tables"]} | {facts} | ' + ' | '.join(str(totals[g][v]) for v in VERDICTS)
                     + ' |')
    lines.append(f'| Total | {grand["tables"]} | {sum(grand[v] for v in VERDICTS)} | '
                 + ' | '.join(str(grand[v]) for v in VERDICTS) + ' |')

    tables = [(r['file'], t) for r in results for t in r['table_counts'] if t['counts'].get('mismatch')]
    lines += ['', f'## Mismatches: {grand["mismatch"]} facts in {len(tables)} tables', '']
    lines += [f'- {cell(f)} #{t["ordinal"]} ({t["status"]}) {cell(t["title"])}: {t["counts"]["mismatch"]}'
              for f, t in tables]
    for r in results:
        by_table = collections.OrderedDict()
        for m in r['mismatches']:
            by_table.setdefault((m['ordinal'], m['title'], m['status']), []).append(m)
        for (ordinal, title, status), items in by_table.items():
            lines += ['', f'### {cell(r["file"])} #{ordinal} ({status}): {cell(title)}', '',
                      '| Source cell | Row label | Fact | Concept | Context | Header |', '|---|---|---|---|---|---|']
            lines += [f'| r{m["cell"][0]}c{m["cell"][1]} | {cell(m["label"])[:50]} | {cell(m["text"])} | '
                      f'{cell(m["concept"].split(":")[-1])} | {cell(m["context"])} | {cell(m["header"])} |'
                      for m in items]

    yearless = [(r['file'], t) for r in results for t in r['yearless']]
    lines += ['', f'## Yearless period headers: {len(yearless)} tables', '',
              '| Filing | Table | Status | Title | Headers (column: header) |', '|---|---|---|---|---|']
    lines += [f'| {cell(f)} | #{t["ordinal"]} | {t["status"]} | {cell(t["title"])} | '
              + '; '.join(f'{ci}: {cell(h)}' for ci, h in t['headers']) + ' |' for f, t in yearless]

    unlocated = [(r['file'], t) for r in results for t in r['unlocated']]
    lines += ['', f'## Tables with numeric-fact cells but no located facts: {len(unlocated)}', '',
              '| Filing | Table | Status | Provenance | Title | Fact cells |', '|---|---|---|---|---|---|']
    lines += [f'| {cell(f)} | #{t["ordinal"]} | {t["status"]} | {t["provenance"]} | {cell(t["title"])} | '
              f'{t["fact_cells"]} |' for f, t in unlocated]
    return '\n'.join(lines) + '\n', totals


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('export_dir')
    parser.add_argument('--report', required=True)
    parser.add_argument('--details', required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    paths = [os.path.join(args.export_dir, name) for name in sorted(os.listdir(args.export_dir))]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check, paths))
    text, totals = report(args.export_dir, results)
    with open(args.report, 'w', encoding='utf-8') as handle:
        handle.write(text)
    with open(args.details, 'w', encoding='utf-8') as handle:
        json.dump(results, handle, indent=1, ensure_ascii=False)
    for g in GROUPS:
        print(g, {k: totals[g][k] for k in ('tables', *VERDICTS)})
    print('mismatch tables:', sum(1 for r in results for t in r['table_counts'] if t['counts'].get('mismatch')),
          '| yearless tables:', sum(len(r['yearless']) for r in results),
          '| unlocated tables:', sum(len(r['unlocated']) for r in results))


if __name__ == '__main__':
    main()
