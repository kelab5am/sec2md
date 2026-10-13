"""Corpus scan for the shapes that the checker's three unmodelled outcomes would decide.

    python -I unmodelled_scan.py EXPORT_DIR --src <branch checkout>/src

Run it from the checkout root. dispositions.py does not model three outcomes of Rulings 21-23
(spec Revision 3). If the branch applied one of them to a cell, the gates would fail, because
the checker expects the earlier outcome; but if the branch failed to apply one, the gates would
not notice. This scan counts the cells either case could concern, read from the export JSON:

(i)   Ruling 21 (A2): a copy column holding a digit cell with its own complete '$' token or an
      amount fact, while a percent declaration in its header or an in-table table-wide caption
      covers it: every other digit cell of that column.
(ii)  Ruling 8 as amended by Ruling 21: an in-table table-wide caption over an amount heading
      (today's _VALUE): every digit cell of that column.
(iii) Ruling 23: a '%' or ')%' source cell spanning two or more rows in the body of a table that
      is not source_text_only (a source-text table joins nothing).

Context-line declarations (NVDA's) are not in the export JSON, so (i) and (ii) cover in-table
captions only; NVDA's 495 context-declared cells are held to the baseline by the all-cells sweep
in dispositions.py. Adapted from the acceptance reviewer's scan_unmodelled.py.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('export_dir')
    parser.add_argument('--src', required=True)
    args = parser.parse_args()
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.abspath(args.src))
    import dispositions as D
    import sec2md.xlsx_tables as M
    from sec2md.xlsx_values import convert_cell
    assert os.path.realpath(M.__file__).startswith(os.path.realpath(args.src)), M.__file__
    D.M, D.convert_cell = M, convert_cell

    captions, money, amount_heading, spanning = [], [], [], []
    for name in sorted(n[:-5] for n in os.listdir(args.export_dir)):
        data = json.load(open(os.path.join(args.export_dir, name + '.json'), encoding='utf-8'))
        for t in data['tables']:
            if t['status'] == 'source_text_only':
                continue
            table = D.Table(name, t, {})
            for c in t['source_cells']:
                if c[4].strip() in ('%', ')%') and c[2] >= 2 and c[0] >= table.header_count:
                    spanning.append((name, t['ordinal'], t['status'], c[:5]))
            caption = table.table_wide()
            if caption:
                captions.append((name, t['ordinal']))
            for ci in range(1, len(t['headers'])):
                rows = [ri for ri, row in enumerate(t['rows']) if ci < len(row) and D.has_digit(row[ci][2])]
                if not rows:
                    continue
                evidence = {ri: D.evidence(table, ri, ci) for ri in rows}
                own = {ri for ri, e in evidence.items()
                       if (e['d'] is not None and '$' in e['token'])
                       or any(m.lower().startswith('iso4217:') or m.lower() == 'xbrli:shares'
                              for f in e['facts'] for m in f['unit'])}
                declared = any(D.percent_declaration(p) for p in table.header_labels(ci))
                if own and (declared or caption):
                    money.extend((name, t['ordinal'], ri, ci, t['headers'][ci][:50], evidence[ri]['token'])
                                 for ri in rows if ri not in own)
                if caption and M._VALUE.search(t['headers'][ci]):
                    amount_heading.extend((name, t['ordinal'], ri, ci, t['headers'][ci][:50], evidence[ri]['token'])
                                          for ri in rows)
    print(f'Tables with an in-table table-wide caption: {len(captions)} {captions}')
    print(f'(i) other digit cells of a $ / amount-fact column under a percent declaration or caption: {len(money)}')
    for x in money:
        print('   ', x)
    print(f'(ii) digit cells under an amount heading with a table-wide caption: {len(amount_heading)}')
    for x in amount_heading:
        print('   ', x)
    print(f'(iii) % or )% source cells spanning two or more body rows: {len(spanning)}')
    for x in spanning:
        print('   ', x)


if __name__ == '__main__':
    main()
