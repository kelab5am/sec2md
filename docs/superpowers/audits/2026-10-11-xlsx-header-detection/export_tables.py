"""Prepare every export table of each filing with one sec2md checkout and save it as JSON.

Run it once with the baseline checkout and once with the change, then compare the
two output directories with compare.py and check primary statements with
primary_statements.py.

    python -I export_tables.py --src <checkout>/src --out <dir> FILE [FILE ...]

Each filing becomes <dir>/<file name>.json holding the filing's XBRL contexts and
a list of tables. Each table records its ordinal, title, status, issues, headers,
typed copy rows ([kind, value, original]), cell sources, its source cells
([row, column, rowspan, colspan, text, is_numeric_fact]) and the inline XBRL facts
inside each source cell ([row, column, context, concept, displayed text, sign]).

Three lists were added for the value-accuracy audit; every other field is unchanged:
- fact_attributes, parallel to facts (same order): [scale, format, unitref,
  unit_measures]. scale, format and unitref are the raw attribute values (None when
  absent). unit_measures resolves unitref through the filing's xbrli:unit
  definitions: the sorted measures, or for a divide unit the sorted numerator
  measures, '/', then the sorted denominator measures, e.g.
  ['iso4217:USD', '/', 'xbrli:shares']. It is [] when unitref does not resolve.
- cell_formats, parallel to rows: each copy cell's number_format.
- cell_reasons, parallel to rows: each copy cell's review_reason, or None.

Fact provenance comes from the filing itself: the source table is found by
matching sec2md's own snapshot of every <table> element to the export table, and
each ix:nonFraction is located by replacing its text with a marker in a copy of
that element. Tables whose snapshot matches no element, or several, get no facts
and are reported as such.
"""

import argparse
import copy
import json
import os
import re
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal

MARKER = re.compile(r'IXFACT(\d+)Z')


def _value(value):
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return ['number', str(value)]
    return ['text', None if value is None else str(value)]


def _signature(cells):
    return tuple((c.row, c.column, c.rowspan, c.colspan, c.text) for c in cells)


def _contexts(soup):
    contexts = {}
    for context in soup.find_all('xbrli:context'):
        dims = bool(context.find('xbrldi:explicitmember') or context.find('xbrldi:typedmember'))
        instant = context.find('xbrli:instant')
        start, end = context.find('xbrli:startdate'), context.find('xbrli:enddate')
        if instant:
            contexts[context.get('id')] = ['I', None, instant.text.strip()[:10], dims]
        elif start and end:
            contexts[context.get('id')] = ['D', start.text.strip()[:10], end.text.strip()[:10], dims]
    return contexts


def _measures(node):
    return sorted(measure.get_text().strip() for measure in node.find_all('xbrli:measure'))


def _units(soup):
    """{unit id: measures} from the filing's xbrli:unit definitions; a divide keeps its two sides apart."""
    units = {}
    for unit in soup.find_all('xbrli:unit'):
        divide = unit.find('xbrli:divide')
        if divide:
            numerator, denominator = divide.find('xbrli:unitnumerator'), divide.find('xbrli:unitdenominator')
            measures = [*_measures(numerator), '/', *_measures(denominator)] if numerator and denominator else []
        else:
            measures = _measures(unit)
        units[unit.get('id')] = measures
    return units


def _facts(tag, snapshot_html_table, units):
    """The facts in a table element and their attributes, two parallel lists:
    [[row, column, context, concept, displayed text, sign], ...] and [[scale, format, unitref, unit_measures], ...]."""
    marked = copy.copy(tag)
    found = []
    for index, fact in enumerate(marked.find_all('ix:nonfraction')):
        unitref = fact.get('unitref')
        found.append(([fact.get('contextref'), fact.get('name'), fact.get_text(), fact.get('sign')],
                      [fact.get('scale'), fact.get('format'), unitref, list(units.get(unitref, []))]))
        fact.clear()
        fact.append(f'IXFACT{index}Z')
    facts, attributes = [], []
    for cell in snapshot_html_table(marked, ordinal=0, page=1, source_url=None).source_cells:
        for index in MARKER.findall(cell.text):
            fact, attribute = found[int(index)]
            facts.append([cell.row, cell.column, *fact])
            attributes.append(attribute)
    return facts, attributes


def export(job):
    src, out, path = job
    sys.path.insert(0, src)
    warnings.filterwarnings('ignore')
    from bs4 import BeautifulSoup
    import sec2md
    from sec2md.parser import Parser
    from sec2md.xlsx_tables import prepare_table, select_export_tables, snapshot_html_table

    assert os.path.realpath(sec2md.__file__).startswith(os.path.realpath(src)), sec2md.__file__
    html = open(path, 'rb').read().decode('utf-8', 'replace')
    parser = Parser(html, capture_tables=True, table_checks=True)
    parser.get_pages(include_images=False)
    soup = BeautifulSoup(html, 'lxml')
    units = _units(soup)
    elements = {}
    for tag in soup.find_all('table'):
        try:
            cells = snapshot_html_table(tag, ordinal=0, page=1, source_url=None).source_cells
        except Exception:
            continue
        elements.setdefault(_signature(cells), []).append(tag)
    tables = []
    for snapshot in select_export_tables(parser.table_snapshots):
        table = prepare_table(snapshot)
        matches = elements.get(_signature(snapshot.source_cells), [])
        facts, attributes = _facts(matches[0], snapshot_html_table, units) if len(matches) == 1 else ([], [])
        tables.append(dict(
            ordinal=snapshot.ordinal, title=table.title, status=table.status, issues=list(table.issues),
            headers=list(table.headers),
            rows=[[[*_value(cell.value), cell.original] for cell in row] for row in table.rows],
            cell_sources=[[[list(source) for source in sources] for sources in row] for row in table.cell_sources],
            source_cells=[[c.row, c.column, c.rowspan, c.colspan, c.text, c.is_numeric_fact]
                          for c in snapshot.source_cells],
            provenance='unique' if len(matches) == 1 else ('ambiguous' if matches else 'unmatched'),
            facts=facts, fact_attributes=attributes,
            cell_formats=[[cell.number_format for cell in row] for row in table.rows],
            cell_reasons=[[cell.review_reason for cell in row] for row in table.rows]))
    name = os.path.basename(path)
    with open(os.path.join(out, name + '.json'), 'w', encoding='utf-8') as handle:
        json.dump(dict(file=name, path=path, contexts=_contexts(soup), tables=tables), handle)
    return name, len(tables)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, help="the checkout's src directory")
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = [(os.path.abspath(args.src), os.path.abspath(args.out), path) for path in args.files]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for name, count in pool.map(export, jobs):
            print(f'{count:4} tables  {name}', flush=True)


if __name__ == '__main__':
    main()
