"""Row roles (R0) shared by the Markdown table renderer and the header-alignment check.

Implements R0 of docs/superpowers/specs/2026-10-05-sec2md-table-merge-header-rules-design.md.
R0 is a rule on visible content. It reads a neutral grid: rows of origin slots, where a
slot holds the source cell whose top-left slot it is (an OriginCell, or a plain string
for a td cell's text), and None when another cell's span covers it. Empty rows and
columns are ignored and positions are logical, so the renderer's cleaned grid and the
checker's placed grid reach the same roles, each in its own coordinates. Nothing here
reads renderer merge decisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Pattern, Sequence, Union

from sec2md.quality import _MARKDOWN_LINK_RE


@dataclass(frozen=True)
class OriginCell:
    """A source cell at its top-left slot: its text and whether it is a th element."""

    text: str
    header: bool = False


# A plain string is shorthand for a td cell's text.
OriginSlot = Union[str, OriginCell, None]
OriginGrid = Sequence[Sequence[OriginSlot]]
RowRole = Literal["header", "body", "empty"]

# Zero-width and format characters that are not visible text.
ZERO_WIDTH_CHARACTERS = "\u200b\u200c\u200d\u2060\ufeff"
_ZERO_WIDTH = str.maketrans(dict.fromkeys(ZERO_WIDTH_CHARACTERS))

# The closed currency vocabulary. A cell is a marker only when its whole visible text is one.
CURRENCY_MARKERS = frozenset({
    "$", "€", "£", "¥",
    "US$", "NT$", "HK$", "A$", "C$", "S$",
    "USD", "EUR", "GBP", "JPY", "CNY", "RMB", "CHF", "DKK", "SEK", "NOK", "HKD", "TWD",
    "CAD", "AUD", "INR", "KRW", "SGD",
})
# Longest first, so "US$" is never read as "US" followed by "$".
CURRENCY_PATTERN = "(?:" + "|".join(
    re.escape(marker) for marker in sorted(CURRENCY_MARKERS, key=len, reverse=True)
) + ")"

# Revision 14: digits in thousands groups of three ("1,234,567") or plain digits ("1234"),
# with an optional decimal, or a leading-dot decimal (".75").
_NUMBER = r"(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
_CURRENCY = rf"(?:{CURRENCY_PATTERN}\s*)"
_SIGN = r"[-+−–]"
# A standalone number (revision 14): one currency marker at most, before or inside the
# parentheses; parentheses and a sign, each optional; one trailing "%" at most, inside or
# after the parentheses. "$ $ 5", "$ ($ 120)" and "5 % %" are not standalone numbers.
_STANDALONE = (
    rf"(?:(?:{_CURRENCY}\(\s*|\(\s*{_CURRENCY}?){_SIGN}?\s*{_NUMBER}\s*(?:%\s*\)|\)(?:\s*%)?)"
    rf"|{_CURRENCY}?{_SIGN}?\s*{_NUMBER}(?:\s*%)?)"
)
# Revision 7: footnote markers after a standalone number: (1), (a), [1], *, **, †, ‡.
_FOOTNOTE_MARKER = r"(?:\(\s*(?:\d{1,2}|[A-Za-z])\s*\)|\[\s*\d{1,2}\s*\]|\*{1,2}|[†‡])"
_FOOTNOTED = re.compile(rf"(?P<number>{_STANDALONE})(?P<marks>(?:\s*{_FOOTNOTE_MARKER})*)")
# Revision 7: two standalone numbers joined by "-", "–", "—" or "to".
_RANGE = re.compile(rf"(?P<low>{_STANDALONE})(?:\s*[-–—]\s*|\s+to\s+)(?P<high>{_STANDALONE})")
_BARE_YEAR = re.compile(r"(?:19|20)\d{2}")
# Revision 8: a fiscal-year range written "2024–25".
_FISCAL_YEAR_RANGE = re.compile(r"(?:19|20)\d{2}\s*[-–—]\s*\d{2}")
_NIL_VALUES = frozenset({"—", "–", "-", "−"})
# Split accounting negatives: "(29" + ")", "(3.2" + ")%" and "(" + "29" + ")".
_OPEN_AMOUNT = re.compile(rf"{_CURRENCY}?\(\s*{_CURRENCY}?{_NUMBER}")
_OPEN_ONLY = re.compile(rf"{_CURRENCY}?\(")
_PLAIN_AMOUNT = re.compile(rf"{_CURRENCY}?{_NUMBER}")
_CLOSE = re.compile(r"\)\s*%?")
# Revision 11: R0's own unit captions, beside xlsx_tables._UNIT_LINE's declarations. The
# corpus writes dollar units as "(Dollars in millions)", "(Millions of dollars)" and their
# variants ("($ in millions)", "(Dollars in millions, except per share data)"). The shared
# patterns stay as they are: checks 1-3 and the XLSX export read them.
_UNIT_CAPTION = re.compile(
    r"^\(?\s*(?:u\.?s\.?\s+)?(?:dollars|\$)\s+in\s+(?:thousands|millions|billions)\b"
    r"|^\(?\s*(?:thousands|millions|billions)\s+of\s+(?:u\.?s\.?\s+)?dollars\b",
    re.I,
)
# Revision 11: the audit captions "(Unaudited)" and "(Audited)", as a whole cell.
_AUDIT_CAPTION = re.compile(r"\(\s*(?:un)?audited\s*\)", re.I)
# Revision 13: besides the currency markers, the texts that make a column marker-only for
# main's sparse-row fusion (main merges such columns before it counts). Compared without
# spaces, as split negatives are rebuilt: ") %" is ")%".
_MARKER_TEXTS = frozenset({"%", ")", ")%", "("})


@lru_cache(maxsize=1)
def _caption_patterns() -> tuple[Pattern[str], Pattern[str]]:
    """The shared period and unit patterns: table_completeness._PERIOD_TEXT, xlsx_tables._UNIT_LINE.

    Imported on first use: both modules import table_parser, which imports this module.
    """

    from sec2md.table_completeness import _PERIOD_TEXT
    from sec2md.xlsx_tables import _UNIT_LINE

    return _PERIOD_TEXT, _UNIT_LINE


def is_period_text(text: str | None) -> bool:
    """R0's period text: table_completeness._PERIOD_TEXT (duration words, month-day dates)."""

    return bool(_caption_patterns()[0].search(visible_text(text)))


def is_unit_text(text: str | None) -> bool:
    """R0's unit text: a unit declaration xlsx_tables._UNIT_LINE matches ("(In millions)"),
    a dollar unit caption ("(Dollars in millions)", "(Millions of dollars)"), or an audit
    caption ("(Unaudited)", "(Audited)")."""

    value = visible_text(text)
    return bool(
        _caption_patterns()[1].search(value)
        or _UNIT_CAPTION.search(value)
        or _AUDIT_CAPTION.fullmatch(value)
    )


def _slot_text(slot: OriginSlot) -> str | None:
    """The text of an origin slot; None for a span-covered slot."""

    if isinstance(slot, OriginCell):
        return slot.text
    return slot


def visible_text(text: str | None) -> str:
    """Cell text without zero-width characters, with each Markdown link reduced to its label."""

    if not text:
        return ""
    if text.isascii() and "[" not in text:
        return text.strip()  # no link, zero-width character or no-break space to remove
    text = _MARKDOWN_LINK_RE.sub(r"\1", text.translate(_ZERO_WIDTH))
    return text.replace("\xa0", " ").strip()


def is_currency_marker(text: str | None) -> bool:
    """Whether a cell's whole visible text is one marker of the closed currency list."""

    return visible_text(text) in CURRENCY_MARKERS


def is_bare_year(text: str | None) -> bool:
    """Four digits from 1900 to 2099 and nothing else."""

    return bool(_BARE_YEAR.fullmatch(visible_text(text)))


def is_nil_value(text: str | None) -> bool:
    """A cell whose visible text is only an em dash, en dash, hyphen or minus sign."""

    return visible_text(text) in _NIL_VALUES


# is_year_like, is_complete_number and _caption_label are pure functions of one text,
# cached because a table's rows repeat their values and labels.
@lru_cache(maxsize=65536)
def is_year_like(text: str | None) -> bool:
    """A bare year, a footnoted bare year, a range of two bare years, or a fiscal-year
    range written "2024–25".

    Year-like values count as numbers only where bare years do (counts_bare_years).
    """

    value = visible_text(text)
    if _FISCAL_YEAR_RANGE.fullmatch(value):
        return True
    footnoted = _FOOTNOTED.fullmatch(value)
    if footnoted and _BARE_YEAR.fullmatch(footnoted.group("number").strip()):
        return True
    span = _RANGE.fullmatch(value)
    return bool(span) and all(
        _BARE_YEAR.fullmatch(span.group(side).strip()) for side in ("low", "high")
    )


@lru_cache(maxsize=65536)
def is_complete_number(text: str | None) -> bool:
    """The whole visible text of one value: a standalone number other than a bare year.

    Revision 7: the number may carry footnote markers ("2.1(1)", "3,984 *"), and two
    standalone numbers joined by a dash or "to" form one ("3.5 %- 4.3 %"). Year-like values
    (a bare year, with or without markers, or a range of two) are not complete numbers.
    """

    value = visible_text(text)
    if is_year_like(value):
        return False
    return bool(_FOOTNOTED.fullmatch(value) or _RANGE.fullmatch(value))


def _origin_texts(row: Sequence[OriginSlot]) -> list[tuple[int, str]]:
    """Non-empty visible origin texts of one row as (column, text): the row's origin text,
    one entry per column that holds it, before split negatives are rebuilt."""

    cells: list[tuple[int, str]] = []
    for column, slot in enumerate(row):
        text = slot.text if isinstance(slot, OriginCell) else slot  # _slot_text, inlined
        if text:  # most slots are empty or span-covered
            text = visible_text(text)
            if text:
                cells.append((column, text))
    return cells


def row_values(row: Sequence[OriginSlot]) -> list[tuple[int, str]]:
    """Non-empty visible origin texts of one row as (column, text), split negatives rebuilt.

    A split negative is rebuilt from adjacent non-empty cells, as
    table_completeness.merge_split_negatives does, and keeps the column of the cell
    holding its digits.
    """

    return _rebuild_split_negatives(_origin_texts(row))


def _rebuild_split_negatives(cells: Sequence[tuple[int, str]]) -> list[tuple[int, str]]:
    """row_values over a row's origin texts (_origin_texts)."""

    values: list[tuple[int, str]] = []
    index = 0
    while index < len(cells):
        column, here = cells[index]
        following = cells[index + 1][1] if index + 1 < len(cells) else ""
        after = cells[index + 2][1] if index + 2 < len(cells) else ""
        if "(" not in here:  # both split shapes open with "("
            values.append((column, here))
            index += 1
        elif _OPEN_AMOUNT.fullmatch(here) and _CLOSE.fullmatch(following):
            values.append((column, here + following.replace(" ", "")))
            index += 2
        elif (_OPEN_ONLY.fullmatch(here) and _PLAIN_AMOUNT.fullmatch(following)
              and _CLOSE.fullmatch(after)):
            values.append((cells[index + 1][0], here + following + after.replace(" ", "")))
            index += 3
        else:
            values.append((column, here))
            index += 1
    return values


@dataclass(frozen=True)
class RowRoles:
    """R0 row roles of one grid, in that grid's own coordinates.

    label_column is the leftmost column holding origin text (None for an empty grid).
    header_rows is the header zone; every other row with origin text is body.
    """

    label_column: int | None
    identifier_column: bool
    header_rows: tuple[int, ...]
    data_rows: tuple[int, ...]
    empty_rows: tuple[int, ...]

    def role(self, row: int) -> RowRole:
        if row in self.empty_rows:
            return "empty"
        return "header" if row in self.header_rows else "body"


def is_explicit_header_row(row: Sequence[OriginSlot]) -> bool:
    """Whether every non-empty origin cell of a row is a th element (never a data row)."""

    cells = [slot for slot in row if visible_text(_slot_text(slot))]
    return bool(cells) and all(isinstance(slot, OriginCell) and slot.header for slot in cells)


def _label_text(row: Sequence[OriginSlot], label_column: int) -> str:
    """The visible origin text of a row's label cell ("" when empty or span-covered)."""

    return visible_text(_slot_text(row[label_column])) if label_column < len(row) else ""


@lru_cache(maxsize=65536)
def _caption_label(label: str) -> bool:
    """Whether a label cell's text is period text, unit text or a year-like value."""

    return is_period_text(label) or is_unit_text(label) or is_year_like(label)


def _year_run(values: Sequence[tuple[int, str]], label_column: int) -> bool:
    """is_year_run over a row's values (row_values)."""

    numbers = [
        text
        for column, text in values
        if column != label_column and (is_complete_number(text) or is_year_like(text))
    ]
    if len(numbers) < 2 or not all(_BARE_YEAR.fullmatch(text) for text in numbers):
        return False
    years = [int(text) for text in numbers]
    return all(abs(after - before) <= 1 for before, after in zip(years, years[1:]))


def is_year_run(row: Sequence[OriginSlot], label_column: int) -> bool:
    """Whether a row's numbers outside the label column are all bare years, at least two of
    them, each within one of the next ("2022 | 2023 | 2024", "2025 | 2024 | 2025 | 2024").

    The numbers are the complete numbers and year-like values; text cells and nil values
    are not numbers. "Revenue | 2000 | 1900" is not a year run.
    """

    return _year_run(row_values(row), label_column)


def _counts_bare_years(row: Sequence[OriginSlot], values: Sequence[tuple[int, str]], label_column: int) -> bool:
    """counts_bare_years with the row's values (row_values) already rebuilt."""

    label = _label_text(row, label_column)
    if not label or _caption_label(label):
        return False
    return not _year_run(values, label_column)


def counts_bare_years(row: Sequence[OriginSlot], label_column: int) -> bool:
    """Whether bare years count as numbers in a row.

    They count only when the row's label cell holds origin text that is neither period
    text, unit text nor a year-like value, and the row is not a year run. So
    "Revenue | 2000 | 1900" is data, while "| 2023 | 2022", "Year Ended June 30, | 2025 |
    2024", "(Dollars in millions) | 2024 | 2023", "2023 | 2022" and the year run
    "Function | 2022 | 2023 | 2024" stay header-like.
    """

    return _counts_bare_years(row, row_values(row), label_column)


def _label_only(cells: Sequence[tuple[int, str]], label_column: int) -> bool:
    """is_label_only over a row's origin texts (_origin_texts)."""

    return bool(cells) and all(column == label_column for column, _ in cells)


def is_label_only(row: Sequence[OriginSlot], label_column: int) -> bool:
    """Whether a row has origin text in the label column only: a title line or a section
    label ("CONDENSED CONSOLIDATED BALANCE SHEETS", "Assets:")."""

    return _label_only(_origin_texts(row), label_column)


def _header_like(row: Sequence[OriginSlot], cells: Sequence[tuple[int, str]],
                 values: Sequence[tuple[int, str]], label_column: int) -> bool:
    """is_header_like with the row's origin texts (_origin_texts) and values (row_values)."""

    label = _label_text(row, label_column)
    return (
        not label
        or _caption_label(label)
        or _year_run(values, label_column)
        or is_explicit_header_row(row)
        or _label_only(cells, label_column)
    )


def is_header_like(row: Sequence[OriginSlot], label_column: int) -> bool:
    """Whether a row may continue the header zone past its first row (revisions 11, 12).

    Its label cell has no origin text, or holds period text, unit text or a year-like
    value; or it is a year run; or it is an explicit header row; or it is a label-only row
    (a second title line). A row whose label cell holds any other text beside text in
    another column ("Common Stock | AAPL", "10.5.23 | Plan B") ends the zone, unless it is
    the second row and main's sparse-row fusion applies (fuses_like_main, decided per
    table in row_roles, marker-only columns left out of its count).
    """

    cells = _origin_texts(row)
    return _header_like(row, cells, _rebuild_split_negatives(cells), label_column)


def _is_marker_text(text: str) -> bool:
    """Whether a visible origin text is a currency marker, "%", ")", ")%" or "(" (revision 13)."""

    return text in CURRENCY_MARKERS or text.replace(" ", "") in _MARKER_TEXTS


def _fuses_like_main(cells: Sequence[Sequence[tuple[int, str]]], text_rows: Sequence[int]) -> bool:
    """fuses_like_main over the rows' origin texts (_origin_texts) and the rows holding text."""

    texts: dict[int, list[str]] = {}
    for row in text_rows:
        for column, text in cells[row]:
            texts.setdefault(column, []).append(text)
    counted = {column for column, held in texts.items() if not all(map(_is_marker_text, held))}
    threshold = max(2, len(counted) // 2)
    first = sum(column in counted for column, _ in cells[text_rows[0]])
    second = sum(column in counted for column, _ in cells[text_rows[1]])
    return len(counted) - first >= threshold and second >= threshold


def fuses_like_main(grid: OriginGrid) -> bool:
    """Whether main's sparse-row fusion applies to a grid's first two rows with origin text
    (revisions 12 and 13); main fuses such a pair into its header line ("Exhibit Index" over
    "Exhibit Number | Description | Filed Herewith").

    n is the number of columns holding origin text, leaving out marker-only columns: those
    whose every origin text is a currency marker, "%", ")", ")%" or "(", which main merges
    before it counts. The first row must have no origin text in at least max(2, n // 2) of
    the counted columns, and the second row origin text in at least as many. Empty rows are
    ignored, so the placed and the cleaned grid agree.
    """

    cells = [_origin_texts(row) for row in grid]
    text_rows = [index for index, row_cells in enumerate(cells) if row_cells]
    return len(text_rows) >= 2 and _fuses_like_main(cells, text_rows)


def row_roles(grid: OriginGrid) -> RowRoles:
    """Decide R0's label column, identifier column, data rows and header zone.

    The header zone is the rows before the first data row, through header-like rows only
    (revisions 11 and 12: label-only rows continue it, and so does the second row when
    main's sparse-row fusion applies), without its trailing label-only rows (revision 8);
    with no data row it is the first row with origin text alone.
    """

    cells = [_origin_texts(row) for row in grid]
    rows = [_rebuild_split_negatives(row_cells) for row_cells in cells]
    text_rows = [index for index, row_cells in enumerate(cells) if row_cells]
    empty_rows = tuple(index for index, row_cells in enumerate(cells) if not row_cells)
    if not text_rows:
        return RowRoles(None, False, (), (), empty_rows)

    # Origin columns, not rebuilt values: a "(" cell holds origin text in its own column.
    # The leftmost such column is the least first-text column over the rows with text.
    label_column = min(cells[index][0][0] for index in text_rows)
    years = {index: _counts_bare_years(grid[index], rows[index], label_column) for index in text_rows}

    def number(index: int, text: str) -> bool:
        return is_complete_number(text) or (years[index] and is_year_like(text))

    def label_number(index: int) -> bool:
        # Values come in column order and the label column is the leftmost origin column,
        # so a label-column value can only be a row's first.
        values = rows[index]
        return bool(values) and values[0][0] == label_column and number(index, values[0][1])

    identifier_column = sum(label_number(index) for index in text_rows) >= 2

    def is_data(index: int) -> bool:
        if is_explicit_header_row(grid[index]):
            return False
        for column, text in rows[index]:
            if column == label_column:
                if identifier_column and number(index, text):
                    return True
            elif number(index, text) or is_nil_value(text):
                return True
        return False

    def header_like(position: int, index: int) -> bool:
        if _header_like(grid[index], cells[index], rows[index], label_column):
            return True
        if position != 1:
            return False
        # Revisions 12 and 13: the second row with origin text stays when main's sparse-row
        # fusion applies to the first two ("Exhibit Index" over "Exhibit Number | Description"),
        # marker-only columns left out of the count.
        return _fuses_like_main(cells, text_rows)

    data_rows = tuple(index for index in text_rows if is_data(index))
    if not data_rows:
        header_rows: tuple[int, ...] = (text_rows[0],)
    else:
        candidates = [index for index in text_rows if index < data_rows[0]]
        # Revisions 11 and 12: past its first row the zone continues only through
        # header-like rows; the first other row ("Common Stock | AAPL") and every row
        # below are body.
        end = next(
            (
                position
                for position, index in enumerate(candidates[1:], start=1)
                if not header_like(position, index)
            ),
            len(candidates),
        )
        header_rows = tuple(candidates[:end])
        # Revision 8: trailing label-only rows are section labels ("Accounts Receivable:").
        while header_rows and _label_only(cells[header_rows[-1]], label_column):
            header_rows = header_rows[:-1]
    return RowRoles(label_column, identifier_column, header_rows, data_rows, empty_rows)
