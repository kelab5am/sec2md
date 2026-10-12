"""Disable each header-detection safeguard in turn and check the new tests catch it.

    python -I mutation_check.py <worktree root> <python>

Each mutant edits src/sec2md/xlsx_tables.py in the worktree, runs
tests/test_xlsx_header_detection.py, and restores the file (also on error).
Checks 2's unit half, 4, 5 and 7 are implied by other checks (spec Rule 1), so
no test can fail on them alone; they are expected to survive. Any other
surviving mutant, or an expected survivor that is now caught, exits non-zero.
"""

import os
import subprocess
import sys

EXPECTED_SURVIVORS = {'2 unit-declaration rows', '4 narrow downward', '5 narrower than amount', '7 year label'}

MUTANTS = [
    ('1 data cell', "        if any(_is_data_cell(cell) for cell in cells):\n", "        if False:\n"),
    ('2 unit-declaration rows',
     "        if not headings or all(_UNIT_DECLARATION.fullmatch(cell.text.strip()) for cell in headings):",
     "        if not headings:"),
    ('3 two headings', "(len(headings) < 2 or not _heading_label(label.text))", "(False or not _heading_label(label.text))"),
    ('3b heading-like label', "(len(headings) < 2 or not _heading_label(label.text))", "(len(headings) < 2 or False)"),
    ('4 narrow downward', "            if upper is not None and cell.colspan > upper.colspan:\n", "            if False:\n"),
    ('4b labelled subdivides',
     "            if (label is not None and upper is not None and cell.colspan >= upper.colspan",
     "            if (False and label is not None and upper is not None and cell.colspan >= upper.colspan"),
    ('4c straddle', "            if straddles(cell, index):\n", "            if False:\n"),
    ('5 narrower than amount',
     "            if any(cell.colspan < amount.colspan for amount in amounts_under(cell)):\n", "            if False:\n"),
    ('6 currency narrows',
     "            if _CURRENCY.fullmatch(cell.text.strip()) and upper is not None and cell.colspan < upper.colspan:\n",
     "            if False:\n"),
    ('7 year label', "(_YEAR_TOKEN.fullmatch(label.text.strip()) or (years and not _caption_label(label.text)))",
     "(False or (years and not _caption_label(label.text)))"),
    ('7b caption for years', "(_YEAR_TOKEN.fullmatch(label.text.strip()) or (years and not _caption_label(label.text)))",
     "(_YEAR_TOKEN.fullmatch(label.text.strip()) or False)"),
    ('8 year under period', "        return not all(year_heading_ok(year, index) for year in years)\n", "        return False\n"),
    ('8 equal-width yearless',
     "                     or (upper.colspan == year.colspan and not _HAS_YEAR.search(upper.text))))",
     "                     or False))"),
    ('evidence cut-off',
     "        if any(cell.colspan > amount.colspan for cell in headings for amount in amounts_under(cell)):\n",
     "        if True:\n"),
    ('data row needs digits', "if any(_is_data_cell(cell, digits=True) for cell in _row_origins(grid[r]))",
     "if any(_is_data_cell(cell, digits=False) for cell in _row_origins(grid[r]))"),
    ('caption label whole', "    return bool(_UNIT_DECLARATION.fullmatch(text) or _SCALE_CAPTION.fullmatch(text)",
     "    return bool(_period_heading(text) or _UNIT_DECLARATION.fullmatch(text) or _SCALE_CAPTION.fullmatch(text)"),
    ('period-row guard',
     "    if evidenced > base and any(_period_row(grid[r]) for r in range(evidenced, len(grid))):\n",
     "    if False:\n"),
    ('period row one period origin', "            and (any(_period_text(cell.text) for cell in cells)",
     "            and (all(_period_text(cell.text) for cell in cells)"),
    ('period text footnotes', "    rest = _FOOTNOTE_MARK.sub(' ', text)\n", "    rest = text\n"),
    ('period row heading phrase', "any(_PERIOD_PHRASE.search(cell.text) or _NUMERIC_DATE.search(cell.text)",
     "any(False"),
    ('period row footnote-only cells', "_is_data_cell(cell) and not _FOOTNOTE_MARK.fullmatch(cell.text.strip())",
     "_is_data_cell(cell)"),
    ('period row label phrase', "for cell in cells if cell is not label)))", "for cell in cells)))"),
    ('R2 footnoted year token', "_YEAR_TOKEN = re.compile(r'(?:19|20)\\d{2}(?:\\s*\\(\\d{1,2}\\))?')",
     "_YEAR_TOKEN = re.compile(r'(?:19|20)\\d{2}')"),
    ('R3 note reference', "        if _NOTE_REF.fullmatch(part) or _MATURITY_BUCKET.fullmatch(part):",
     "        if _MATURITY_BUCKET.fullmatch(part):"),
    ('R3 maturity bucket', "        if _NOTE_REF.fullmatch(part) or _MATURITY_BUCKET.fullmatch(part):",
     "        if _NOTE_REF.fullmatch(part):"),
    ('R3 period words', "        if not _IDENTIFIER.search(_PERIOD_WORDS.sub(' ', part)):", "        if False:"),
    ('R3 own quantity', "        if any(pattern.search(part) for pattern in (_VALUE, _ROW_UNIT, _QUANTITY)):", "        if False:"),
    ('R3 wrapped quantity', "        if _WRAPPED_QUANTITY.search(' '.join(parts[index:index + 2])):", "        if False:"),
    ('R3 wrapped join too broad', "        if _WRAPPED_QUANTITY.search(' '.join(parts[index:index + 2])):",
     "        if any(p.search(' '.join(parts[index:index + 2])) for p in (_VALUE, _ROW_UNIT, _QUANTITY)):"),
]


def main():
    root, python = sys.argv[1], sys.argv[2]
    path = os.path.join(root, 'src', 'sec2md', 'xlsx_tables.py')
    original = open(path, encoding='utf-8').read()
    unexpected = []
    try:
        for name, old, new in MUTANTS:
            if original.count(old) != 1:
                raise SystemExit(f'mutant {name!r}: anchor not found exactly once')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(original.replace(old, new))
            run = subprocess.run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-x',
                                  'tests/test_xlsx_header_detection.py'], cwd=root, capture_output=True, text=True)
            caught = run.returncode != 0
            print(f"{'caught  ' if caught else 'survived'} {name}")
            if caught == (name in EXPECTED_SURVIVORS):
                unexpected.append(name)
    finally:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(original)
    if unexpected:
        raise SystemExit(f'unexpected results: {unexpected}')
    print('all mutants behaved as expected')


if __name__ == '__main__':
    main()
