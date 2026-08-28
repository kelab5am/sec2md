"""Utility functions."""

import re
import requests
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

_ws = re.compile(r"\s+")
_CONTENT_TYPE_CHARSET = re.compile(
    r"(?:^|;)\s*charset\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^;\s]+))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FetchedHtml:
    """Raw HTTP HTML bytes and the server-declared charset, if provided."""

    content: bytes
    charset: str | None


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\xa0", " ")
    return _ws.sub(" ", text).strip()


NUMERIC_RE = re.compile(r"""
    ^\s*
    [\(\[]?                      # optional opening paren/bracket
    [\-—–]?\s*                   # optional dash
    [$€£¥]?\s*                   # optional currency
    \d+(?:[.,]\d{3})*           # integer part (with thousands)
    (?:[.,]\d+)?                # decimals
    \s*%?                       # optional percent
    [\)\]]?\s*$                 # optional closing paren/bracket
""", re.X)


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 0:
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
    return sorted_vals[n // 2]


def is_url(source: str) -> bool:
    """
    Check if source is a valid URL using urllib.parse.

    Args:
        source: String to check

    Returns:
        True if source is a valid URL with http/https scheme
    """
    try:
        result = urlparse(source)
        return all([result.scheme, result.netloc]) and result.scheme in ('http', 'https')
    except Exception:
        return False


def is_edgar_url(url: str) -> bool:
    """Check if URL is an SEC EDGAR URL."""
    return "sec.gov" in url.lower()


def _content_type_charset(content_type: str | None) -> str | None:
    """Extract an optional charset parameter from a Content-Type header."""

    if not content_type:
        return None
    match = _CONTENT_TYPE_CHARSET.search(content_type)
    if match is None:
        return None
    return next(value for value in match.groups() if value is not None).strip()


def fetch(url: str, user_agent: str | None = None) -> FetchedHtml:
    """
    Fetch HTML content from a URL.

    Args:
        url: The URL to fetch
        user_agent: User agent string (required for EDGAR URLs)

    Returns:
        Raw HTML bytes and the optional Content-Type charset.

    Raises:
        ValueError: If EDGAR URL is accessed without user_agent
        requests.RequestException: If request fails
    """
    if is_edgar_url(url) and not user_agent:
        raise ValueError(
            "SEC EDGAR requires a User-Agent header. "
            "Pass user_agent='YourName your@email.com'"
        )

    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return FetchedHtml(
        response.content,
        _content_type_charset(response.headers.get("Content-Type")),
    )


def flatten_note(content: str) -> Optional[str]:
    """
    Flatten note structure by removing the outer table wrapper.

    Notes to financial statements are often wrapped in an unnecessary outer table
    with a single cell containing the actual content. This function unwraps that
    outer table to reveal the properly structured content inside.

    Args:
        content: HTML string containing the note content

    Returns:
        Flattened HTML string, or None if flattening fails

    Example:
        >>> from edgar import Company, set_identity
        >>> import sec2md
        >>>
        >>> set_identity("Your Name <you@example.com>")
        >>> company = Company('AAPL')
        >>> filing = company.get_filings(form="10-K").latest()
        >>> notes = filing.reports.get_by_category("Notes")
        >>> note = notes.get_by_short_name("Revenue")
        >>>
        >>> # Flatten the note wrapper
        >>> flattened_html = sec2md.flatten_note(note.content)
        >>> md = sec2md.convert_to_markdown(flattened_html)
    """
    soup = BeautifulSoup(content, 'lxml')
    elements = []

    body = soup.find("body")
    if not body:
        return None

    table = body.find("table")
    if table is None:
        return None

    for row in table.find_all('tr', recursive=False):
        cells = row.find_all(['th', 'td'], recursive=False)

        for cell in cells:
            elements.append(cell)

    if len(elements) == 0:
        return None

    return ''.join([str(element) for element in elements])
