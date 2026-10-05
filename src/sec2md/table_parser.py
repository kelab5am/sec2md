from __future__ import annotations

import re
import logging
from bs4 import Tag
from bs4.element import NavigableString
from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Optional, Sequence, cast
from urllib.parse import urljoin

from sec2md.quality import normalize_numeric_token
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

        self.cells = self._extract_cells()
        self.grid = self._create_grid()

    def _extract_cells(self) -> List[List[Cell]]:
        rows = []
        for tr in self.table_element.find_all('tr'):
            row = []
            for td in tr.find_all(['td', 'th']):
                if td.find("a"):
                    text = render_cell_content(td, base_url=self.base_url)
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
                if not text:
                    if td.find('img'):
                        text = '●'  # or '•' depending on your BULLETS set
                rowspan = self._safe_parse_int(td.get('rowspan'))
                colspan = self._safe_parse_int(td.get('colspan'))
                row.append(Cell(text=text, rowspan=rowspan, colspan=colspan,
                                header=td.name == "th"))
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
        """Create grid with spanning cells handled"""
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

        grid = self._clean_grid(grid)
        grid = self._merge_grid(grid, policy=EXTENDED)

        return grid

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
        return row_roles(_origin_cells(grid)).label_column

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
    def _header_merge_target(
        source: int,
        value: str,
        source_actions: dict[int, int],
        removed: set[int],
        column_count: int,
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> int | None:
        """Keep header fragments on the same side as their body actions."""

        targets = sorted(set(source_actions.values()))
        if len(targets) == 1 and targets[0] not in removed:
            return targets[0]
        marker_class = _marker_class(value, policy=policy)
        if marker_class is not None:
            target = TableParser._structural_target(source, marker_class)
            if 0 <= target < column_count and target not in removed:
                return target
        for target in targets:
            if target not in removed:
                return target
        return None

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

    def _merge_structural_columns(
        self,
        grid: List[List[GridCell]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> List[List[GridCell]]:
        """Merge only proven accounting marker columns into numeric neighbors."""

        actions = self._safe_structural_actions(grid, policy=policy)
        if not actions:
            return grid

        removed = set(actions)
        column_count = len(grid[0])
        result: List[List[GridCell]] = []
        body_rows = set(self._body_rows(grid, policy=policy))
        for row_index, row in enumerate(grid):
            rebuilt: List[GridCell] = []
            for target in range(column_count):
                if target in removed:
                    continue

                prefixes: list[str] = []
                suffixes: list[str] = []
                for source, source_actions in actions.items():
                    cell = row[source]
                    value = _cell_value(cell.text, policy=policy) if cell is not None else ""
                    if not value:
                        continue
                    merge_target = source_actions.get(row_index)
                    if merge_target is None and row_index not in body_rows:
                        merge_target = self._header_merge_target(
                            source,
                            value,
                            source_actions,
                            removed,
                            column_count,
                            policy=policy,
                        )
                    if merge_target != target:
                        continue
                    if source < target:
                        prefixes.append(value)
                    else:
                        suffixes.append(value)

                original = row[target]
                original_text = original.text.strip() if original else ""
                merged_text = self._join_structural_text(
                    prefixes, original_text, suffixes, policy=policy
                )
                if merged_text != original_text:
                    rebuilt.append(GridCell(Cell(text=merged_text)))
                elif original is not None:
                    rebuilt.append(original)
                else:
                    rebuilt.append(GridCell(Cell(text="")))
            result.append(rebuilt)
        return result

    def _merge_grid(
        self,
        grid: List[List[GridCell]],
        *,
        policy: StructuralPolicy = LEGACY,
    ) -> List[List[GridCell]]:
        """Merge columns in one clean pass"""
        if not grid or not grid[0]:
            return grid

        # R4, revision 17: R0's own label-column cells, which the structural pass keeps by
        # identity; there only "$" is a currency marker.
        label_column = self._label_column(grid, policy=policy)
        label_cells = [row[label_column] if label_column is not None else None for row in grid]
        grid = self._merge_structural_columns(grid, policy=policy)
        if not grid or not grid[0]:
            return grid

        result = []
        current_col = None

        for col_idx in range(len(grid[0])):
            col = [row[col_idx] for row in grid]

            if current_col is None:
                current_col = col
                continue

            cell_pairs = list(zip(current_col[1:], col[1:]))
            should_merge = all(
                self._should_merge_cells(
                    c1, c2, policy=policy,
                    label=c1 is not None and c1 is label_cells[row],
                )
                for row, (c1, c2) in enumerate(cell_pairs, start=1)
            )

            if should_merge:
                merged = [current_col[0]]  # Keep header
                for c1, c2 in cell_pairs:
                    if not c1:
                        merged.append(c2)
                    elif not c2:
                        merged.append(c1)
                    else:
                        text = f"{c1.text} {c2.text}".strip()
                        merged_cell = Cell(text=text)
                        merged.append(GridCell(merged_cell))
                current_col = merged
            else:
                result.append(current_col)
                current_col = col

        if current_col is not None:
            result.append(current_col)

        return list(map(list, zip(*result)))

    def to_matrix(self) -> List[List[str]]:
        """Convert grid to text matrix"""
        return [[cell.text if cell else "" for cell in row] for row in self.grid]

    def _normalize_text(self, text: str) -> str:
        """Normalize text while preserving deliberate blanks"""
        if text is None:
            return ""
        return str(text).replace("\xa0", " ").strip()

    def _process_headers(self, matrix: List[List[str]]) -> tuple[List[str], List[List[str]]]:
        """
        Process table headers with smart header fusion.

        Returns:
            Tuple of (headers, data_rows)
        """
        if not matrix or len(matrix) < 1:
            return [], []

        nrows = len(matrix)
        ncols = len(matrix[0]) if matrix else 0

        if nrows < 2:
            # Single row - treat as header with no data
            return [self._normalize_text(v) for v in matrix[0]], []

        # Get first two rows
        row0 = [self._normalize_text(v) for v in matrix[0]]
        row1 = [self._normalize_text(v) for v in matrix[1]]

        # Check if we should fuse headers
        nonempty_row1 = sum(1 for v in row1 if v)
        many_blanks_in_row0 = sum(1 for v in row0 if v == "") >= max(2, ncols // 2)

        if nonempty_row1 >= max(2, ncols // 2) and many_blanks_in_row0:
            # Fuse the two header rows
            fused = []
            for j in range(ncols):
                top = row0[j] if j < len(row0) else ""
                bot = row1[j] if j < len(row1) else ""
                if top and bot:
                    fused.append(f"{top} — {bot}")
                elif top:
                    fused.append(top)
                elif bot:
                    fused.append(bot)
                else:
                    fused.append("")
            return fused, matrix[2:]
        else:
            # Use row0 as header, rest as data
            return row0, matrix[1:]

    def _clean_empty_rows_and_cols(self, headers: List[str], data: List[List[str]]) -> tuple[List[str], List[List[str]]]:
        """Remove completely empty rows and columns"""
        if not data:
            return headers, data

        ncols = len(headers)

        # Remove empty rows
        cleaned_data = [row for row in data if any(self._normalize_text(cell) for cell in row)]

        if not cleaned_data:
            return headers, []

        # Identify empty columns
        cols_with_content = set()
        for row in cleaned_data:
            for j, cell in enumerate(row):
                if j < ncols and self._normalize_text(cell):
                    cols_with_content.add(j)

        # Keep columns with content
        if not cols_with_content:
            return [], []

        cols_to_keep = sorted(cols_with_content)
        new_headers = [headers[j] for j in cols_to_keep if j < len(headers)]
        new_data = [[row[j] if j < len(row) else "" for j in cols_to_keep] for row in cleaned_data]

        return new_headers, new_data

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

        # Clean empty rows/columns
        headers, data = self._clean_empty_rows_and_cols(headers, data)

        if not headers and not data:
            return ""

        # Build markdown table
        lines = []

        # Header row
        if headers:
            escaped_headers = [_escape_table_pipes(str(h)) for h in headers]
            lines.append("| " + " | ".join(escaped_headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Data rows
        for row in data:
            # Pad row to match header length
            while len(row) < len(headers):
                row.append("")
            # Escape pipe characters
            escaped_row = [_escape_table_pipes(str(cell)) for cell in row[:len(headers)]]
            lines.append("| " + " | ".join(escaped_row) + " |")

        return "\n".join(lines)

    def md(self) -> str:
        """Alias for to_markdown() for backwards compatibility"""
        return self.to_markdown()
