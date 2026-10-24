"""Geometry of positioned page layouts: line boxes, their fragments, and page boxes.

Implements docs/superpowers/specs/2026-10-24-sec2md-positioned-page-layout-design.md
(revision 3). Workiva's PDF-like pages are boxes of fixed height. Each line of text is an
absolutely positioned box with a ``top`` (a line box). Its text sits in absolutely positioned
inline fragments, placed by ``left`` and, when written, ``width``.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4.element import NavigableString, PageElement, Tag

# position:absolute as a property, not inside a custom property such as "--position:absolute" (D1).
ABSOLUTE_RE = re.compile(r"(?<![\w-])position\s*:\s*absolute", re.I)
_RELATIVE_RE = re.compile(r"(?<![\w-])position\s*:\s*relative", re.I)
_LENGTH = r"(-?(?:\d+(?:\.\d+)?|\.\d+))\s*(pt|px)?"
_PX_TO_PT = 0.75
# Element children a line box may hold; any other element makes the box a block.
_INLINE_TAGS = frozenset({
    "a", "abbr", "b", "big", "br", "cite", "code", "em", "font", "i", "img", "q", "s",
    "small", "span", "strike", "strong", "sub", "sup", "u",
    "ix:nonfraction", "ix:nonnumeric", "ix:footnote", "nonfraction", "nonnumeric",
})
# Two fragments touch when the gap between them is at most this, in points (D6).
TOUCH_TOLERANCE_PT = 0.5


def _style(tag: Tag) -> str:
    return str(tag.get("style") or "")


def css_length_pt(tag: Tag, prop: str) -> Optional[float]:
    """A length in the tag's inline style, in points: pt as written, px (or a bare number) x 0.75."""

    match = re.search(rf"(?:^|[;\s]){re.escape(prop)}\s*:\s*{_LENGTH}", _style(tag), re.I)
    if not match:
        return None
    value = float(match.group(1))
    return value if (match.group(2) or "").lower() == "pt" else value * _PX_TO_PT


def is_absolute(node: object) -> bool:
    return isinstance(node, Tag) and bool(ABSOLUTE_RE.search(_style(node)))


def is_relative(node: object) -> bool:
    return isinstance(node, Tag) and bool(_RELATIVE_RE.search(_style(node)))


def is_line_box(node: object) -> bool:
    """An absolutely positioned box with a top whose element children are all inline (D5)."""

    if not is_absolute(node) or css_length_pt(node, "top") is None:
        return False
    return all(child.name in _INLINE_TAGS for child in node.children if isinstance(child, Tag))


def is_line_fragment(node: object) -> bool:
    """An absolutely positioned inline child of a line box, without a top of its own (D6)."""

    return (
        is_absolute(node)
        and node.name in _INLINE_TAGS
        and css_length_pt(node, "top") is None
        and is_line_box(node.parent)
    )


def _touches(previous: Tag, fragment: Tag) -> bool:
    left = css_length_pt(fragment, "left")
    previous_left = css_length_pt(previous, "left")
    previous_width = css_length_pt(previous, "width")
    if left is None or previous_left is None or previous_width is None:
        return False
    return left - (previous_left + previous_width) <= TOUCH_TOLERANCE_PT


def space_between(previous: Optional[PageElement], node: PageElement) -> bool:
    """Whether a space separates two adjacent siblings because a line fragment is among them.

    A line fragment is not set apart by its position alone (separates_inline). Next to a
    sibling it is still separated by one space, as all positioned text is, unless both are
    line fragments whose written geometry proves they touch (D6).
    """

    if previous is None:
        return False
    if isinstance(previous, NavigableString) and not str(previous).strip():
        return False  # source whitespace already separates
    fragment_before, fragment_after = is_line_fragment(previous), is_line_fragment(node)
    if not (fragment_before or fragment_after):
        return False
    return not (fragment_before and fragment_after and _touches(previous, node))


def font_size_pt(tag: Tag) -> Optional[float]:
    """The largest font size written on a box or its descendants, in points."""

    sizes = [css_length_pt(node, "font-size") for node in (tag, *tag.find_all(True))]
    sizes = [size for size in sizes if size]
    return max(sizes) if sizes else None
