from __future__ import annotations

import re
import logging
from collections import Counter
from bs4 import Tag
from bs4.element import NavigableString
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Callable, List, Literal, Optional, Sequence, cast
from urllib.parse import urljoin

from sec2md.quality import _normalized_numbers, normalize_numeric_token
from sec2md.table_roles import (
    CURRENCY_MARKERS,
    CURRENCY_PATTERN,
    ZERO_WIDTH_CHARACTERS,
    OriginCell,
    row_roles,
    visible_text,
)

logger = logging.getLogger(__name__)

BULLETS = {"•", "●", "◦", "–", "-", "—", "·", ""}

StructuralColumn = Literal["currency", "open_paren", "close_paren", "percent"]
STRUCTURAL_MARKERS: dict[str, StructuralColumn] = {
    "$": "currency",
    "(": "open_paren",
    ")": "close_paren",
    "%": "percent",
}
# EXTENDED (R3.4, R4): ")%" closes a percentage negative and every marker of the closed
# currency list behaves as "$".
EXTENDED_MARKERS: dict[str, StructuralColumn] = {
    **STRUCTURAL_MARKERS,
    ")%": "close_paren",
    **{marker: "currency" for marker in CURRENCY_MARKERS},
}
# Local numeric rules for EXTENDED validation (R3.3, R4); strict's normalizer is unchanged.
_CURRENCY_PREFIX = re.compile(rf"^(\(?\s*){CURRENCY_PATTERN}\s*")
_LEADING_DOT = re.compile(r"(?<!\d)\.(?=\d)")


class StructuralPolicy(Enum):
    """Vocabulary and thresholds of the structural helpers (spec R9).

    LEGACY keeps today's rules; xlsx_tables.prepare_table relies on them through a bare
    ``object.__new__(TableParser)``. EXTENDED adds the Markdown render's rules (R3, R4).
    """

    LEGACY = "legacy"
    EXTENDED = "extended"


LEGACY = StructuralPolicy.LEGACY
EXTENDED = StructuralPolicy.EXTENDED

_ZERO_WIDTH = str.maketrans(dict.fromkeys(ZERO_WIDTH_CHARACTERS))

_BLOCK_DESCENDANT_TAGS = {
    "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p"
}
_STRUCTURAL_BOUNDARY = "\x00"


@dataclass(frozen=True)
class InlineFragment:
    """A rendered text fragment with optional link and structural boundary."""

    text: str
    href: str | None = None
    boundary: bool = False


def _inline_fragments(
    node: Tag,
    *,
    base_url: str | None = None,
    inherited_href: str | None = None,
) -> list[InlineFragment]:
    """Walk a cell's descendants in DOM order without inventing inline spaces."""

    fragments: list[InlineFragment] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).replace("\xa0", " ").translate(_ZERO_WIDTH)
            if text:
                fragments.append(InlineFragment(text=text, href=inherited_href))
            continue
        if not isinstance(child, Tag):
            continue

        tag_name = child.name.lower()
        if tag_name in _BLOCK_DESCENDANT_TAGS:
            fragments.append(InlineFragment(text=" ", boundary=True))
            if tag_name != "br":
                fragments.extend(
                    _inline_fragments(
                        child,
                        base_url=base_url,
                        inherited_href=inherited_href,
                    )
                )
            fragments.append(InlineFragment(text=" ", boundary=True))
            continue

        href = inherited_href
        if tag_name == "a":
            raw_href = child.get("href")
            if raw_href is not None:
                href = urljoin(base_url, raw_href) if base_url else raw_href
        fragments.extend(
            _inline_fragments(
                child,
                base_url=base_url,
                inherited_href=href,
            )
        )
    return fragments


def _coalesce_same_href(fragments: Sequence[InlineFragment]) -> list[InlineFragment]:
    """Coalesce only adjacent, non-boundary fragments sharing the same href."""

    merged: list[InlineFragment] = []
    for fragment in fragments:
        if (
            merged
            and not merged[-1].boundary
            and not fragment.boundary
            and merged[-1].href == fragment.href
        ):
            previous = merged[-1]
            merged[-1] = InlineFragment(
                text=previous.text + fragment.text,
                href=previous.href,
            )
        else:
            merged.append(fragment)
    return merged


def _collapse_structural_whitespace(text: str) -> str:
    """Collapse whitespace introduced by block boundaries after rendering."""

    boundary = re.escape(_STRUCTURAL_BOUNDARY)
    text = re.sub(rf"\s*{boundary}(?:\s*{boundary})*\s*", " ", text)
    return text.replace(_STRUCTURAL_BOUNDARY, "")


def render_cell_content(cell: Tag, *, base_url: str | None = None) -> str:
    """Render visible table-cell content, retaining links as Markdown."""

    fragments = _coalesce_same_href(_inline_fragments(cell, base_url=base_url))
    rendered: list[str] = []
    for fragment in fragments:
        if fragment.boundary:
            rendered.append(_STRUCTURAL_BOUNDARY)
            continue
        text = fragment.text.replace("|", r"\|")
        rendered.append(f"[{text}]({fragment.href})" if fragment.href else text)

    joined = "".join(rendered).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return _collapse_structural_whitespace(joined).strip()


def has_descendant(node: Tag, name: str) -> bool:
    """Whether a tag has a descendant tag with this name: ``node.find(name)`` without the
    cost of bs4's filter machinery, which dominates on tables with many cells. Strings
    and comments have no name (None), so only tags can match."""

    return any(child.name == name for child in node.descendants)


def extract_cell_text(td: Tag, *, base_url: str | None = None) -> str:
    """A td or th cell's text as the Markdown render reads it (the spec's extracted text).

    A cell with a link keeps it as Markdown (render_cell_content); any other cell joins its
    strings with single spaces. Zero-width characters are removed, and a cell holding only
    an image reads as a bullet. The header-alignment check reads source cells through this
    same function, so its labels match the header line text R6 writes.
    """

    if has_descendant(td, "a"):
        text = render_cell_content(td, base_url=base_url)
    else:
        text = (
            td.get_text(separator=" ", strip=True)
            .replace('\xa0', ' ')
            .replace('\r\n', ' ')
            .replace('\r', ' ')
            .replace('\n', ' ')
            .translate(_ZERO_WIDTH)
            .strip()
        )
    if not text and has_descendant(td, 'img'):
        text = '●'  # or '•' depending on your BULLETS set
    return text


def _escape_table_pipes(text: str) -> str:
    """Escape visible, unescaped pipes without changing Markdown link URLs."""

    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "[":
            close_label = text.find("](", index + 1)
            if close_label != -1:
                close_url = text.find(")", close_label + 2)
                if close_url != -1:
                    output.append(text[index : close_url + 1])
                    index = close_url + 1
                    continue
        if text[index] == "|" and (index == 0 or text[index - 1] != "\\"):
            output.append(r"\|")
        else:
            output.append(text[index])
        index += 1
    return "".join(output)


@lru_cache(maxsize=1)
def _snapshot_hidden_rule() -> Callable[[Tag], bool]:
    """xlsx_tables._hidden, the snapshot builder's rule for a hidden element.

    Imported on first use: xlsx_tables imports this module.
    """

    from sec2md.xlsx_tables import _hidden

    return _hidden


def _grid_hidden_within(node: Tag, table: Tag, known: dict) -> bool:
    """Whether a row or cell is grid-hidden: the snapshot builder's rule holds for it or
    for an ancestor inside the table (spec "Grid-hidden").

    known memoizes, across one table's rows and cells, the answer per element id and the
    rule's verdict per (style attribute, hidden attribute present): the rule reads only
    those two attributes, and most cells of a table share their style.
    """

    hidden = _snapshot_hidden_rule()
    chain: list[Tag] = []
    current: Tag | None = node
    inherited = False
    while current is not None and current is not table:
        found = known.get(id(current))
        if found is not None:
            inherited = found
            break
        chain.append(current)
        current = current.parent
    for element in reversed(chain):
        if not inherited:
            attributes = element.attrs
            key = (attributes.get("style"), "hidden" in attributes)
            verdict = known.get(key)
            if verdict is None:
                verdict = known[key] = hidden(element)
            inherited = verdict
        known[id(element)] = inherited
    return inherited


def _descendants_named(node: Tag, names: tuple[str, ...]) -> list[Tag]:
    """The descendant tags with one of these names, in document order: ``node.find_all``
    without the cost of bs4's filter machinery."""

    return [child for child in node.descendants if child.name in names]


def _cell_value(text: str, *, policy: StructuralPolicy = LEGACY) -> str:
    """The cell text a structural rule reads: visible text under EXTENDED (R3.1)."""

    if policy is EXTENDED:
        return visible_text(text)
    return text.strip()


def _origin_cells(
    grid: Sequence[Sequence[Optional["GridCell"]]],
) -> list[list[OriginCell | None]]:
    """The neutral R0 grid: each origin slot's text and th markup, None where a span covers it."""

    return [
        [
            None if cell is None or cell.is_spanning else OriginCell(cell.cell.text, cell.cell.header)
            for cell in row
        ]
        for row in grid
    ]


def _marker_class(
    value: str,
    *,
    policy: StructuralPolicy = LEGACY,
    label: bool = False,
) -> StructuralColumn | None:
    """The structural marker class of one whole, stripped cell text.

    ``label`` says the cell lies in R0's label column. There, under EXTENDED, only "$" is a
    currency marker, which keeps main's rule: a row label such as "EUR" or "JPY" is text
    (R4, revision 17). LEGACY ignores it.
    """

    if policy is EXTENDED:
        text = visible_text(value)
        marker_class = EXTENDED_MARKERS.get(text)
        if label and marker_class == "currency" and text != "$":
            return None
        return marker_class
    return STRUCTURAL_MARKERS.get(value)


def _classify_structural_column(
    values: Sequence[str],
    *,
    policy: StructuralPolicy = LEGACY,
    label: bool = False,
) -> StructuralColumn | None:
    """Classify a column only when its marker evidence is uniform.

    LEGACY needs the marker repeated; EXTENDED accepts a single marker (R3.4), which
    final validation must still accept. ``label`` marks R0's label column (_marker_class).
    """

    nonempty = [text for text in (_cell_value(value, policy=policy) for value in values) if text]
    if len(nonempty) < (1 if policy is EXTENDED else 2):
        return None
    classes = {_marker_class(value, policy=policy, label=label) for value in nonempty}
    if None in classes or len(classes) != 1:
        return None
    return cast(StructuralColumn, classes.pop())


@dataclass
class Cell:
    """A single cell in a table, potentially containing XBRL data"""
    text: str
    rowspan: int = 1
    colspan: int = 1
    header: bool = False  # a th element (R0's explicit header rows)
    node: Optional[Tag] = field(default=None, repr=False, compare=False)

    def __bool__(self) -> bool:
        return bool(self.text.strip())

    def __repr__(self) -> str:
        return f"Cell(text={self.text!r}, rowspan={self.rowspan}, colspan={self.colspan})"


class GridCell:
    """A cell in the final grid, possibly part of a spanning cell"""

    def __init__(self, cell: Cell, is_spanning: bool = False):
        self.cell = cell
        self.is_spanning = is_spanning

    @property
    def text(self) -> str:
        return self.cell.text if not self.is_spanning else ""

    def __bool__(self) -> bool:
        return bool(self.text.strip())

    def __repr__(self) -> str:
        return f"GridCell(cell={self.cell!r}, is_spanning={self.is_spanning})"


@dataclass(frozen=True)
class BodySlot:
    """One output column's body text in one source row, with the source cells it holds."""

    text: str = ""
    cells: tuple[Cell, ...] = ()


@dataclass
class OutputColumn:
    """An output column and its membership in source-grid columns (spec R1-R3).

    Owning members carry header ownership. Marker members are marker columns the
    structural pass removed; they feed body text and never own a header.
    """

    owners: list[int]
    markers: list[int]
    slots: list[BodySlot]


def _contains_cells(container: Sequence[Cell], cells: Sequence[Cell]) -> bool:
    """Whether every cell is among container, compared by source-cell identity."""

    return all(any(cell is held for held in container) for cell in cells)


# A Markdown link's destination, as render_cell_content writes it: "[label](destination)".
_LINK_DESTINATION = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")


def _header_key(text: str) -> tuple[str, tuple[str, ...]]:
    """Header text for R6's equality test: the visible text (whitespace collapsed, case
    folded) and the link destinations, so equal labels with different links are both kept."""

    return " ".join(visible_text(text).split()).casefold(), tuple(_LINK_DESTINATION.findall(text))


@dataclass(frozen=True)
class TableHeaderRecord:
    """What one render wrote as a table's header line (spec R6a's inputs).

    header_line is the exact Markdown header line written, or None when it holds no text.
    header_source counts the numeric tokens of the header-zone source cells, each cell
    once: their nodes' ``get_text(" ", strip=True)`` joined in document order with single
    spaces, as strict's source pool is built, then tokenized once with strict's tokenizer.
    header_capacity multiplies each cell's own tokens by the number of output columns
    whose header that cell covers. Counts are sorted (token, count) pairs.
    """

    header_line: str | None
    header_source: tuple[tuple[str, int], ...] = ()
    header_capacity: tuple[tuple[str, int], ...] = ()


class TableParser:
    """A table within a filing document"""

    def __init__(self, table_element: Tag, *, base_url: str | None = None):
        """
        Initialize table from a BS4 table tag

        Args:
            table_element: The specific table BS4 tag
        """
        if not isinstance(table_element, Tag) or table_element.name != 'table':
            raise ValueError("table_element must be a table tag")

        self.table_element = table_element
        self.base_url = base_url
        # Set by each to_markdown() call; None until a render writes a table.
        self.header_record: TableHeaderRecord | None = None

        self.cells = self._extract_cells()
        self.grid = self._create_grid()

    def _extract_cells(self) -> List[List[Cell]]:
        """Source cells by row: every td and th that is not grid-hidden (spec "Source cell").

        Grid-hidden rows and cells are left out before placement, so spans and positions
        are those a reader sees, as in the snapshot builder and the checker's placed grid.
        """
        rows = []
        hidden: dict = {}
        for tr in _descendants_named(self.table_element, ("tr",)):
            if _grid_hidden_within(tr, self.table_element, hidden):
                continue
            row = []
            cells = _descendants_named(tr, ("td", "th"))
            if cells and all(_grid_hidden_within(td, self.table_element, hidden) for td in cells):
                # Every cell is grid-hidden: the row stays, empty, so spans from the rows
                # above still end on it, as in the snapshot builder.
                rows.append(row)
                continue
            for td in cells:
                if _grid_hidden_within(td, self.table_element, hidden):
                    continue
                text = extract_cell_text(td, base_url=self.base_url)
                rowspan = self._safe_parse_int(td.get('rowspan'))
                colspan = self._safe_parse_int(td.get('colspan'))
                row.append(Cell(text=text, rowspan=rowspan, colspan=colspan,
                                header=td.name == "th", node=td))
            if row:
                rows.append(row)
        return rows or [[Cell(text="")]]

    @staticmethod
    def _safe_parse_int(value: str, default: int = 1) -> int:
        """Safely parse an integer value, returning default if parsing fails"""
        try:
            if not value or not isinstance(value, str):
                return default
            cleaned = ''.join(c for c in value if c.isdigit())
            return int(cleaned) if cleaned else default
        except (ValueError, TypeError):
            return default

    def _create_grid(self) -> List[List[GridCell]]:
        """Build the source grid, decide row roles (R0) and merge columns with membership.

        The source grid (span expansion plus ``_clean_grid``) and the row roles are kept
        unchanged for the whole render; every later rule refers to their coordinates.
        """
        self.source_grid: List[List[Optional[GridCell]]] = []
        self.roles = row_roles([])
        self.columns: list[OutputColumn] = []
        if not self.cells:
            return []

        # Calculate grid dimensions
        max_cols = max(sum(cell.colspan for cell in row) for row in self.cells)
        grid = [[None for _ in range(max_cols)] for _ in range(len(self.cells))]

        for i, row in enumerate(self.cells):
            col = 0
            for cell in row:
                # Find next empty cell
                while col < max_cols and grid[i][col] is not None:
                    col += 1

                if col >= max_cols:
                    break

                grid[i][col] = GridCell(cell)

                for r in range(cell.rowspan):
                    for c in range(cell.colspan):
                        if r == 0 and c == 0:  # Skip main cell
                            continue
                        ri, ci = i + r, col + c
                        if ri < len(grid) and ci < max_cols:
                            grid[ri][ci] = GridCell(cell, is_spanning=True)

                col += cell.colspan

        self.source_grid = self._clean_grid(grid)
        self.roles = row_roles(_origin_cells(self.source_grid))
        self.columns = self._merge_grid(
            self.source_grid, self.roles.header_rows, policy=EXTENDED
        )
        return self._output_grid()

    def _should_merge_cells(
        self,
        val1: Optional[GridCell],
        val2: Optional[GridCell],
        *,
        policy: StructuralPolicy = LEGACY,
        label: bool = False,
    ) -> bool:
        """Check if two cells should be merged based on the rules.

        ``label`` says val1 is R0's label-column cell, where only "$" is a currency
        marker under EXTENDED (_marker_class).
        """
        s1 = _cell_value(val1.text, policy=policy) if val1 is not None else ""
        s2 = _cell_value(val2.text, policy=policy) if val2 is not None else ""

        # Handle empty cells
        if not s1 or not s2:
            return True

        if self.is_footnote(s2):
            return True

        if _marker_class(s1, policy=policy, label=label) == "currency":
            return True

        if s2 == '%':
            return True

        return False

    @staticmethod
    def is_footnote(text: str) -> bool:
        """Check if string is a number or letter within square brackets and nothing else, e.g., [1], [b]"""
        pattern = r'^\[[a-zA-Z0-9]+\]$'
        return bool(re.match(pattern, text))

    @staticmethod
    def _clean_grid(grid: List[List[GridCell]]) -> List[List[GridCell]]:
        """Drop rows and columns that contain only empty cells (no text and no XBRL data)"""
        if not grid:
            return grid

        rows_to_keep = [
            i for i, row in enumerate(grid)
            if any(
                cell is not None and cell.text.strip()
                for cell in row
            )
        ]

        columns_to_keep = [
            j for j in range(len(grid[0]))
            if any(
                grid[i][j] is not None and
                (grid[i][j].text.strip())
                for i in range(len(grid))
            )
        ]

        filtered_grid = [
            [grid[i][j] for j in columns_to_keep]
            for i in rows_to_keep
        ]

        return filtered_grid

    @staticmethod
    def _numeric_token(value: str, *, policy: StructuralPolicy = LEGACY) -> str | None:
        """Validate one complete rebuilt numeric token under a structural policy.

        EXTENDED reads visible text, strips one leading currency marker of the closed list
        and accepts leading-dot decimals (R3.3, R4). The result is for validation only;
        strict's normalize_numeric_token is unchanged.
        """

        if policy is EXTENDED:
            text = _CURRENCY_PREFIX.sub(r"\1", visible_text(value), count=1)
            return normalize_numeric_token(_LEADING_DOT.sub("0.", text))
        return normalize_numeric_token(value)

    @staticmethod
    def _is_numeric_fragment(value: str, *, policy: StructuralPolicy = LEGACY) -> bool:
        """Return whether a cell contains a complete or accounting numeric fragment."""

        if policy is EXTENDED:
            value = _CURRENCY_PREFIX.sub(r"\1", visible_text(value), count=1).strip()
        if TableParser._numeric_token(value, policy=policy) is not None:
            return True
        if value.startswith("(") and not value.endswith(")"):
            return TableParser._numeric_token(value[1:].strip(), policy=policy) is not None
        if value.endswith(")") and not value.startswith("("):
            return TableParser._numeric_token(value[:-1].strip(), policy=policy) is not None
        return False

    @staticmethod
    def _body_start(grid: List[List[GridCell]], *, policy: StructuralPolicy = LEGACY) -> int:
        """Skip leading nonnumeric header rows before classifying structural columns."""

        body_start = 1
        while body_start < len(grid) - 1:
            if any(
                TableParser._is_numeric_fragment(cell.text, policy=policy)
                for cell in grid[body_start]
                if cell is not None and cell.text.strip()
            ):
                break
            body_start += 1
        return body_start

    def _body_rows(
        self,
        grid: List[List[GridCell]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> Sequence[int]:
        """Rows the careful marker merge reads as body: R0's body rows under EXTENDED (R3.2)."""

        if policy is EXTENDED:
            # The Markdown render decided the roles of its source grid once (R0); any other
            # grid (a bare parser's) gets its own.
            if grid is getattr(self, "source_grid", None):
                roles = self.roles
            else:
                roles = row_roles(_origin_cells(grid))
            return tuple(row for row in range(len(grid)) if roles.role(row) == "body")
        return range(self._body_start(grid, policy=policy), len(grid))

    def _label_column(
        self,
        grid: List[List[GridCell]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> int | None:
        """R0's label column under EXTENDED (R4, revision 17); None under LEGACY or for an
        empty grid, so LEGACY never reads it."""

        if policy is not EXTENDED:
            return None
        if grid is getattr(self, "source_grid", None):
            return self.roles.label_column
        return row_roles(_origin_cells(grid)).label_column

    @staticmethod
    def _holds_label_cell(
        grid: Sequence[Sequence[Optional[GridCell]]],
        label_column: int | None,
        slot: BodySlot,
        row: int,
    ) -> bool:
        """Whether a body slot holds R0's label-column cell of its row, by identity."""

        if label_column is None:
            return False
        source = grid[row][label_column]
        if source is None or source.is_spanning:
            return False
        return any(cell is source.cell for cell in slot.cells)

    @staticmethod
    def _structural_target(
        column: int,
        marker_class: StructuralColumn,
    ) -> int:
        if marker_class in {"currency", "open_paren"}:
            return column + 1
        return column - 1

    def _safe_structural_actions(
        self,
        grid: List[List[GridCell]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> dict[int, dict[int, int]]:
        """Find column removals whose fully rebuilt rows are numeric tokens."""

        if not grid or not grid[0]:
            return {}

        column_count = len(grid[0])
        body_rows = self._body_rows(grid, policy=policy)
        # R4, revision 17: in R0's label column only "$" is a currency marker.
        label_column = self._label_column(grid, policy=policy)
        values_by_column = {
            column: [
                grid[row][column].text if grid[row][column] is not None else ""
                for row in body_rows
            ]
            for column in range(column_count)
        }
        candidate_actions: dict[int, dict[int, int]] = {}

        for column, values in values_by_column.items():
            label = column == label_column
            marker_class = _classify_structural_column(values, policy=policy, label=label)
            nonempty = [
                text for text in (_cell_value(value, policy=policy) for value in values) if text
            ]
            if marker_class is None:
                classes = [_marker_class(value, policy=policy, label=label) for value in nonempty]
                legacy_mixed = (
                    set(classes) == {"currency", "close_paren"}
                    and classes.count("currency") >= 2
                    and classes.count("close_paren") >= 2
                )
                if not legacy_mixed:
                    continue

            row_actions: dict[int, int] = {}
            for row in body_rows:
                cell = grid[row][column]
                value = _cell_value(cell.text, policy=policy) if cell is not None else ""
                if not value:
                    continue
                row_marker_class = marker_class or cast(
                    StructuralColumn, _marker_class(value, policy=policy, label=label)
                )
                target = self._structural_target(column, row_marker_class)
                if not 0 <= target < column_count:
                    row_actions = {}
                    break
                target_value = grid[row][target].text if grid[row][target] else ""
                if not self._is_numeric_fragment(target_value, policy=policy):
                    row_actions = {}
                    break
                row_actions[row] = target
            if row_actions:
                candidate_actions[column] = row_actions

        actions = self._validated_structural_actions(grid, candidate_actions, policy=policy)

        # The legacy NVIDIA table has two repeated close-marker columns and
        # at least one validated currency column, followed by one final close
        # marker. Keep this exception explicit and require the paired numeric
        # token to validate as well.
        repeated_close_columns = {
            column
            for column in actions
            if _classify_structural_column(values_by_column[column], policy=policy) == "close_paren"
        }
        currency_columns = {
            column
            for column in actions
            if _classify_structural_column(values_by_column[column], policy=policy) == "currency"
        }
        if len(repeated_close_columns) < 2 or not currency_columns:
            return actions

        for column, values in values_by_column.items():
            nonempty = [
                text for text in (_cell_value(value, policy=policy) for value in values) if text
            ]
            if column in actions or len(nonempty) != 1 or column != column_count - 1:
                continue
            marker_class = _marker_class(nonempty[0], policy=policy)
            if marker_class != "close_paren":
                continue
            row = next(
                row
                for row in body_rows
                if grid[row][column] is not None
                and _cell_value(grid[row][column].text, policy=policy)
            )
            target = self._structural_target(column, marker_class)
            target_cell = grid[row][target]
            target_value = (
                _cell_value(target_cell.text, policy=policy) if target_cell is not None else ""
            )
            if not target_value.startswith("("):
                continue
            if self._numeric_token(f"{target_value})", policy=policy) is None:
                continue
            trial_actions = dict(actions)
            trial_actions[column] = {row: target}
            validated = self._validated_structural_actions(grid, trial_actions, policy=policy)
            if column in validated:
                actions = validated

        return actions

    def _validated_structural_actions(
        self,
        grid: List[List[GridCell]],
        actions: dict[int, dict[int, int]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> dict[int, dict[int, int]]:
        """Keep only actions whose complete rebuilt numeric token is valid."""

        while actions:
            invalid_sources: set[int] = set()
            for source, source_actions in actions.items():
                for row, target in source_actions.items():
                    prefixes: list[str] = []
                    suffixes: list[str] = []
                    for other_source, other_actions in actions.items():
                        if other_actions.get(row) != target:
                            continue
                        value = _cell_value(grid[row][other_source].text, policy=policy)
                        if other_source < target:
                            prefixes.append(value)
                        else:
                            suffixes.append(value)
                    target_value = grid[row][target].text if grid[row][target] else ""
                    merged = self._join_structural_text(
                        prefixes, target_value, suffixes, policy=policy
                    )
                    if self._numeric_token(merged, policy=policy) is None:
                        invalid_sources.add(source)
                        break
            if not invalid_sources:
                return actions
            actions = {
                source: source_actions
                for source, source_actions in actions.items()
                if source not in invalid_sources
            }
        return {}

    @staticmethod
    def _join_structural_text(
        prefixes: Sequence[str],
        target: str,
        suffixes: Sequence[str],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> str:
        parts = [part for part in [*prefixes, target, *suffixes] if part]
        if not parts:
            return ""
        if not all(
            _marker_class(part, policy=policy) is not None or part == target for part in parts
        ):
            return " ".join(parts)

        merged = target
        for marker in reversed(prefixes):
            if _marker_class(marker, policy=policy) == "currency":
                merged = f"{marker} {merged}"
            else:
                merged = f"{marker}{merged}"
        for marker in suffixes:
            merged = f"{merged} %" if marker == "%" else f"{merged}{marker}"
        return merged

    @staticmethod
    def _header_cells(
        grid: Sequence[Sequence[Optional[GridCell]]],
        owners: Sequence[int],
        row: int,
    ) -> list[Cell]:
        """The distinct header cells of owning members in one header-zone row, by identity."""

        cells: list[Cell] = []
        for column in owners:
            slot = grid[row][column]
            if slot is None or not visible_text(slot.cell.text):
                continue
            if not any(slot.cell is held for held in cells):
                cells.append(slot.cell)
        return cells

    @staticmethod
    def _independent_header_veto(
        grid: Sequence[Sequence[Optional[GridCell]]],
        header_rows: Sequence[int],
        actions: dict[int, dict[int, int]],
    ) -> dict[int, dict[int, int]]:
        """Keep a marker column whose header cell covers no surviving column (R3.6).

        Mirrors prepare_table's veto: a marker column carrying independent header text
        must remain visible. Callers revalidate the remaining actions.
        """

        surviving = [column for column in range(len(grid[0]) if grid else 0) if column not in actions]
        kept: dict[int, dict[int, int]] = {}
        for source, moves in actions.items():
            independent = False
            for row in header_rows:
                slot = grid[row][source]
                if slot is None or not visible_text(slot.cell.text):
                    continue
                if not any(
                    grid[row][column] is not None and grid[row][column].cell is slot.cell
                    for column in surviving
                ):
                    independent = True
                    break
            if not independent:
                kept[source] = moves
        return kept

    def _structural_columns(
        self,
        grid: List[List[Optional[GridCell]]],
        header_rows: Sequence[int],
        *,
        policy: StructuralPolicy,
    ) -> list[OutputColumn]:
        """Remove proven marker columns, routing body markers only (R3.5, R3.6).

        Header text never moves: each surviving column owns only itself, and a removed
        column becomes a marker member of the columns it fed.
        """

        actions = self._safe_structural_actions(grid, policy=policy)
        actions = self._independent_header_veto(grid, header_rows, actions)
        actions = self._validated_structural_actions(grid, actions, policy=policy)
        header = set(header_rows)
        columns: list[OutputColumn] = []
        for target in range(len(grid[0])):
            if target in actions:
                continue
            markers = sorted(
                source for source, moves in actions.items() if target in moves.values()
            )
            slots: list[BodySlot] = []
            for row_index, row in enumerate(grid):
                if row_index in header:
                    slots.append(BodySlot())
                    continue
                original = row[target]
                original_text = original.text.strip() if original is not None else ""
                cells: list[Cell] = [original.cell] if original_text else []
                if not markers:  # nothing routes into this column: its own text
                    slots.append(BodySlot(original_text, tuple(cells)))
                    continue
                prefixes: list[str] = []
                suffixes: list[str] = []
                for source in markers:
                    if actions[source].get(row_index) != target:
                        continue
                    source_slot = row[source]
                    value = _cell_value(source_slot.text, policy=policy)
                    (prefixes if source < target else suffixes).append(value)
                    cells.append(source_slot.cell)
                text = self._join_structural_text(
                    prefixes, original_text, suffixes, policy=policy
                )
                slots.append(BodySlot(text, tuple(cells)))
            columns.append(OutputColumn([target], markers, slots))
        return columns

    def _merge_allowed(
        self,
        grid: List[List[Optional[GridCell]]],
        header_rows: Sequence[int],
        group: OutputColumn,
        column: OutputColumn,
        *,
        policy: StructuralPolicy,
    ) -> bool:
        """R2: may column merge into the group on its left?"""

        header = set(header_rows)
        body_rows = [row for row in range(len(grid)) if row not in header]
        label_column = self._label_column(grid, policy=policy)
        if not all(
            self._should_merge_cells(
                GridCell(Cell(group.slots[row].text)),
                GridCell(Cell(column.slots[row].text)),
                policy=policy,
                label=self._holds_label_cell(grid, label_column, group.slots[row], row),
            )
            for row in body_rows
        ):
            return False
        if all(
            _contains_cells(
                self._header_cells(grid, group.owners, row),
                self._header_cells(grid, column.owners, row),
            )
            for row in header_rows
        ):
            return True
        return self._marker_exception(grid, header_rows, body_rows, group, column, policy=policy)

    def _marker_exception(
        self,
        grid: List[List[Optional[GridCell]]],
        header_rows: Sequence[int],
        body_rows: Sequence[int],
        group: OutputColumn,
        column: OutputColumn,
        *,
        policy: StructuralPolicy,
    ) -> bool:
        """R2's marker exception: a headerless group of currency markers.

        Every non-empty body slot of the group must be a currency marker, with at least
        one, and the column must hold a value that validates when joined in each of those
        rows. An empty group never qualifies. "(" columns are left to the careful merge,
        because _should_merge_cells can never pass for them. In R0's label column only "$"
        is a currency marker (R4, revision 17).
        """

        if any(self._header_cells(grid, group.owners, row) for row in header_rows):
            return False
        marker_rows = [row for row in body_rows if group.slots[row].text]
        if not marker_rows:
            return False
        label_column = self._label_column(grid, policy=policy)
        for row in marker_rows:
            marker = _cell_value(group.slots[row].text, policy=policy)
            label = self._holds_label_cell(grid, label_column, group.slots[row], row)
            if _marker_class(marker, policy=policy, label=label) != "currency":
                return False
            value = column.slots[row].text.strip()
            joined = self._join_structural_text([marker], value, [], policy=policy)
            if not value or self._numeric_token(joined, policy=policy) is None:
                return False
        return True

    @staticmethod
    def _merged_column(group: OutputColumn, column: OutputColumn) -> OutputColumn:
        """R1: combine every body row; a source cell already in the group counts once."""

        slots: list[BodySlot] = []
        for mine, theirs in zip(group.slots, column.slots):
            if not theirs.text:
                slots.append(mine)
            elif not mine.text:
                slots.append(theirs)
            elif theirs.cells and _contains_cells(mine.cells, theirs.cells):
                slots.append(mine)
            else:
                added = tuple(cell for cell in theirs.cells if not _contains_cells(mine.cells, [cell]))
                slots.append(BodySlot(f"{mine.text} {theirs.text}", mine.cells + added))
        return OutputColumn(
            group.owners + column.owners, group.markers + column.markers, slots
        )

    def _merge_grid(
        self,
        grid: List[List[Optional[GridCell]]],
        header_rows: Sequence[int],
        *,
        policy: StructuralPolicy,
    ) -> list[OutputColumn]:
        """The careful marker merge, then the left-to-right legacy merge under R1 and R2."""

        if not grid or not grid[0]:
            return []
        merged: list[OutputColumn] = []
        for column in self._structural_columns(grid, header_rows, policy=policy):
            if merged and self._merge_allowed(grid, header_rows, merged[-1], column, policy=policy):
                merged[-1] = self._merged_column(merged[-1], column)
            else:
                merged.append(column)
        return merged

    def column_header_cells(self, index: int) -> list[list[Cell]]:
        """Per header-zone row, the distinct header cells of an output column's owners."""

        owners = self.columns[index].owners
        return [self._header_cells(self.source_grid, owners, row) for row in self.roles.header_rows]

    def _output_grid(self) -> List[List[GridCell]]:
        """One row per source row: header rows hold each column's header-cell text, body
        rows its merged body text."""

        header = set(self.roles.header_rows)
        rows: List[List[GridCell]] = []
        for row_index in range(len(self.source_grid)):
            if row_index in header:
                texts = [
                    " ".join(
                        cell.text
                        for cell in self._header_cells(self.source_grid, column.owners, row_index)
                    )
                    for column in self.columns
                ]
            else:
                texts = [column.slots[row_index].text for column in self.columns]
            rows.append([GridCell(Cell(text=text)) for text in texts])
        return rows

    def to_matrix(self) -> List[List[str]]:
        """Convert grid to text matrix"""
        return [[cell.text if cell else "" for cell in row] for row in self.grid]

    def _normalize_text(self, text: str) -> str:
        """Normalize text while preserving deliberate blanks"""
        if text is None:
            return ""
        return str(text).replace("\xa0", " ").strip()

    def _process_headers(self, matrix: List[List[str]]) -> tuple[List[str], List[List[str]]]:
        """Fuse the R0 header zone into one header line per output column (R5, R6).

        Each header-zone row contributes its text, top to bottom, joined with " — ";
        empty texts and a text equal to the one kept before it are skipped. Equality
        compares link destinations too, so equal labels with different links are both
        kept. A header cell is written at most once per column: a cell already met in an
        earlier row of the column (a rowspan, or a span that overlapping markup interrupts)
        is left out, so the line stays within R6a's header_capacity. With an empty header
        zone the header cells are empty and every row is body.

        Returns:
            Tuple of (headers, data_rows)
        """
        if not matrix:
            return [], []

        header_rows = [row for row in self.roles.header_rows if row < len(matrix)]
        ncols = len(matrix[0])
        headers = []
        for column in range(ncols):
            parts: list[str] = []
            previous = None
            met: list[Cell] = []
            for row in header_rows:
                text = self._normalize_text(matrix[row][column]) if column < len(matrix[row]) else ""
                if column < len(self.columns):
                    cells = self._header_cells(self.source_grid, self.columns[column].owners, row)
                    new = [cell for cell in cells if not any(cell is held for held in met)]
                    met.extend(new)
                    if len(new) < len(cells):
                        text = self._normalize_text(" ".join(cell.text for cell in new))
                key = _header_key(text)
                if not key[0] or key == previous:
                    continue
                parts.append(text)
                previous = key
            headers.append(" — ".join(parts))
        header = set(header_rows)
        data = [row for index, row in enumerate(matrix) if index not in header]
        return headers, data

    def _kept_columns(self, headers: List[str], data: List[List[str]]) -> List[int]:
        """Columns holding header text or body text (R7)."""

        return [
            column
            for column in range(len(headers))
            if self._normalize_text(headers[column])
            or any(column < len(row) and self._normalize_text(row[column]) for row in data)
        ]

    def _clean_empty_rows_and_cols(self, headers: List[str], data: List[List[str]]) -> tuple[List[str], List[List[str]]]:
        """Remove empty rows, and columns with neither header text nor body text (R7)."""

        cleaned_data = [row for row in data if any(self._normalize_text(cell) for cell in row)]
        keep = self._kept_columns(headers, cleaned_data)
        if not keep:
            return [], []
        new_headers = [headers[column] for column in keep]
        new_data = [[row[column] if column < len(row) else "" for column in keep] for row in cleaned_data]
        return new_headers, new_data

    def _inside_zone_cell(self, cell: Cell, zone_nodes: set[int]) -> bool:
        """Whether a cell's node lies inside another header-zone cell's node (a nested table)."""

        parent = cell.node.parent if cell.node is not None else None
        while parent is not None and parent is not self.table_element:
            if id(parent) in zone_nodes:
                return True
            parent = parent.parent
        return False

    def _header_record(self, header_line: str | None, kept: Sequence[int]) -> TableHeaderRecord:
        """R6a's inputs for the header line this render wrote; each source cell counts once.

        A nested table's cells are read for the outer row that holds the table and again for
        their own rows. When the table sits in a cell, that cell's text already holds them, so
        a zone cell inside another zone cell is left out. When lxml keeps the table in the
        ``<tr>`` itself, directly or in a wrapper such as ``<div>``, no zone cell holds them,
        so each remaining node is read once, at its first read in document order. Both rules
        apply to header_source and header_capacity alike.
        """

        zone_cells: list[Cell] = []
        for row in self.roles.header_rows:
            for slot in self.source_grid[row]:
                if slot is not None and not any(slot.cell is held for held in zone_cells):
                    zone_cells.append(slot.cell)
        document_order = {id(cell): index for index, cell in enumerate(
            cell for row in self.cells for cell in row
        )}
        zone_cells.sort(key=lambda cell: document_order[id(cell)])
        zone_nodes = {id(cell.node) for cell in zone_cells if cell.node is not None}
        zone_cells = [cell for cell in zone_cells if not self._inside_zone_cell(cell, zone_nodes)]
        first_reads: dict[int, Cell] = {}
        for cell in zone_cells:
            first_reads.setdefault(id(cell.node) if cell.node is not None else id(cell), cell)
        zone_cells = list(first_reads.values())
        texts = [
            cell.node.get_text(" ", strip=True) if cell.node is not None else cell.text
            for cell in zone_cells
        ]
        source = Counter(_normalized_numbers(" ".join(text for text in texts if text)))
        covering = [
            [cell for cells in self.column_header_cells(index) for cell in cells] for index in kept
        ]
        capacity: Counter[str] = Counter()
        for cell, text in zip(zone_cells, texts):
            columns = sum(1 for cells in covering if any(cell is held for held in cells))
            for token, count in Counter(_normalized_numbers(text)).items():
                capacity[token] += count * columns
        return TableHeaderRecord(
            header_line,
            tuple(sorted(source.items())),
            tuple(sorted((token, count) for token, count in capacity.items() if count)),
        )

    def _looks_like_list_table(self) -> bool:
        """Special case - some quirky files format lists as tables"""
        if len(self.cells) != 1:
            return False
        row = self.cells[0]
        texts = [c.text.strip() for c in row]
        has_bullet = any(t in BULLETS for t in texts)
        has_payload = any(t for t in texts[1:])
        return has_bullet and has_payload

    def to_markdown(self) -> str:
        """
        Convert table to markdown format.

        Returns:
            Markdown table string
        """
        self.header_record = None
        # Special-case list tables
        if self._looks_like_list_table():
            row = self.cells[0]
            payload = ""
            for c in reversed(row):
                t = c.text.strip()
                if t and t not in BULLETS:
                    payload = t
                    break
            return f"- {payload}" if payload else ""

        # Get the matrix
        matrix = self.to_matrix()
        if not matrix:
            return ""

        # Process headers
        headers, data = self._process_headers(matrix)
        kept = self._kept_columns(headers, data)

        # Clean empty rows/columns
        headers, data = self._clean_empty_rows_and_cols(headers, data)

        if not headers and not data:
            return ""

        # Build markdown table
        lines = []

        # Header row
        header_line = None
        if headers:
            escaped_headers = [_escape_table_pipes(str(h)) for h in headers]
            lines.append("| " + " | ".join(escaped_headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            if any(self._normalize_text(h) for h in headers):
                header_line = lines[0]

        # Data rows
        for row in data:
            # Pad row to match header length
            while len(row) < len(headers):
                row.append("")
            # Escape pipe characters
            escaped_row = [_escape_table_pipes(str(cell)) for cell in row[:len(headers)]]
            lines.append("| " + " | ".join(escaped_row) + " |")

        self.header_record = self._header_record(header_line, kept)
        return "\n".join(lines)

    def md(self) -> str:
        """Alias for to_markdown() for backwards compatibility"""
        return self.to_markdown()
