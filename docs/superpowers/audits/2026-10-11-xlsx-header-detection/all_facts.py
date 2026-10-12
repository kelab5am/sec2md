"""Check every inline XBRL fact in every exported table against its column header's period.

    python -I all_facts.py EXPORT_DIR --report all-facts.md --details all-facts.json

Reads an export_tables.py output directory (spec Acceptance 3b). Run it once per
export directory, on `main` and on the branch.

1. Every inline XBRL fact in every table that is not source_text_only gets one
   verdict, from the fact inside its own source cell:
   - label column: the fact is in column 0, which has no period header;
   - not placed: no copy cell holds the fact's source cell;
   - no header date: the column header names no month, day and year;
   - mismatch, ok or unparsed length: period_verdict() against the column header.
   Verdict counts are reported per group (META, NVDA, RDDT, Others), every
   mismatch is listed with its source cell, context and header, and every
   header with an unparsed length is listed with the verdicts of its facts.
2. Every table whose column headers carry period wording (a month and day,
   `... ended`, `... ending` or `as of`) without a year is listed: a yearless
   period header. Column 0 is included.
3. Every table with is_numeric_fact source cells but no located facts is listed
   with its fact-cell count. export_tables.py could not match its source
   element, so this script cannot check it.

period_verdict() reads the header's date and its stated length: N months or
N weeks (N in digits, or in words up to fifty-nine; weeks count as
round(N * 7 / 30.4375) months), `quarter` or `quarterly period` (3), or `year`
or `fiscal year` (12), followed by `ended` or `ending` after a space, hyphen or
parenthesis, optionally with `then`: `Three Months Ended`, `Year-Ended`,
`Fourteen Weeks Ended`, `Three Months (Ended`. A dated header without length
wording (months, weeks, quarter(ly), year(s), YTD, to date, or period but not
period-end) is a bare date. A dated header with length wording but no parsed
length (`Year to Date Ended`, `Less than 12 months`, `(in years)`) has an
unparsed length.
- Instants are ok within 7 days of the header date (52/53-week years), or
  within 7 days of the start of a stated period (an opening balance). Under an
  unparsed length, any other instant is `unparsed length`.
- Durations are ok ending within 7 days of the header date, with the stated
  length when there is one; under an unparsed length they are `unparsed
  length`. A duration starting the day after the header date is ok only under
  a bare date (`December 31, 2024` over the next year's activity). Any other
  duration is a mismatch.
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
VERDICTS = ('ok', 'mismatch', 'unparsed length', 'no header date', 'label column', 'not placed')
MONTHS = {m: i for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split(), 1)}
DATE = re.compile(r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?'
                  r'|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})\b'
                  r',?(?:\s+((?:19|20)\d{2})\b)?', re.I)
YEARS = re.compile(r'\b(?:19|20)\d{2}\b')
UNITS = ('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
         'seventeen eighteen nineteen').split()
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50}
NUMBER = rf'(?:\d{{1,2}}|(?:{"|".join(TENS)})(?:[- ](?:{"|".join(UNITS[:9])}))?|{"|".join(UNITS)})'
STATED = re.compile(rf'\b(?:({NUMBER})[- ](months?|weeks?)|(quarter|quarterly period|year)s?)'
                    r'(?:[- ]period)?[\s(-]+(?:then\s+)?(?:ended|ending)\b', re.I)
LENGTH_WORDING = re.compile(r'\b(?:months?|weeks?|quarters?|quarterly|years?|ytd|to[- ]date'
                            r'|periods?(?![- ]end\b))\b', re.I)
UNPARSED = 'unparsed'
PERIOD_WORDING = re.compile(DATE.pattern + r'|\b(?:ended|ending|as of)\b', re.I)
NEAR = 7  # days: 52/53-week fiscal years end within a week of the month end


def number(text):
    """An int from digits or English words up to fifty-nine (`14`, `fourteen`, `fifty-two`)."""
    if text.isdigit():
        return int(text)
    return sum(TENS.get(word) or UNITS.index(word) + 1 for word in re.split(r'[- ]', text.lower()))


def stated_months(text):
    """The months a header states: an int, None without length wording, or UNPARSED."""
    stated = STATED.search(text)
    if not stated:
        return UNPARSED if LENGTH_WORDING.search(text) else None
    count, unit, word = stated.groups()
    if word:
        return 12 if word.lower() == 'year' else 3
    return number(count) if unit.lower().startswith('month') else round(number(count) * 7 / (365.25 / 12))


def header_period(header):
    """(stated months: an int, None for a bare date, or UNPARSED; header date), or None without a dated year."""
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
    return stated_months(text), date


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
    """'ok', 'mismatch', 'unparsed length' or 'no header date' for a context ([type, start, end, dims])."""
    period = header_period(header)
    if period is None:
        return 'no header date'
    if context is None:
        return 'mismatch'
    months, date = period
    end = datetime.date.fromisoformat(context[2])
    if context[0] == 'I':
        if near(end, date):
            return 'ok'
        if months == UNPARSED:
            return 'unparsed length'
        return 'ok' if months is not None and near(end, months_before(date, months)) else 'mismatch'
    start = datetime.date.fromisoformat(context[1])
    if near(end, date):
        if months == UNPARSED:
            return 'unparsed length'
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
                  table_counts=[], mismatches=[], not_placed=[], unparsed=[], yearless=[], unlocated=[])
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
        by_column = collections.defaultdict(collections.Counter)
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
                by_column[ci][verdict] += 1
                if verdict == 'mismatch':
                    result['mismatches'].append(dict(
                        about, cell=[row, col], label=table['rows'][ri][0][1], text=text, concept=concept,
                        context=show_context(context_id, context), header=table['headers'][ci],
                        copy=table['rows'][ri][ci]))
            counts[verdict] += 1
        result['counts'].update(counts)
        if counts:
            result['table_counts'].append(dict(about, counts=dict(counts)))
        for ci, header in enumerate(table['headers'][1:], 1):
            period = header_period(header)
            if period and period[0] == UNPARSED:
                result['unparsed'].append(dict(about, column=ci, header=header, verdicts=dict(by_column[ci])))
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

    unparsed = [(r['file'], u) for r in results for u in r['unparsed']]
    lines += ['', f'## Headers with an unparsed length: {len(unparsed)} headers in '
              f'{len({(f, u["ordinal"]) for f, u in unparsed})} tables', '',
              'A dated header with length wording but no length this script reads. Its facts are not checked for '
              'length.', '', '| Filing | Table | Status | Title | Column: header | Verdicts of its facts |',
              '|---|---|---|---|---|---|']
    lines += [f'| {cell(f)} | #{u["ordinal"]} | {u["status"]} | {cell(u["title"])} | {u["column"]}: '
              f'{cell(u["header"])} | {cell(json.dumps(u["verdicts"])) if u["verdicts"] else "no facts"} |'
              for f, u in unparsed]

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
          '| unparsed-length headers:', sum(len(r['unparsed']) for r in results),
          '| yearless tables:', sum(len(r['yearless']) for r in results),
          '| unlocated tables:', sum(len(r['unlocated']) for r in results))


if __name__ == '__main__':
    main()
