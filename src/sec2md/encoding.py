"""Deterministic decoding and legacy character normalization for SEC HTML."""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DecodeDiagnostics:
    """The codec selected for an input and the reason it was selected."""

    encoding: str
    reason: str


_ENCODING_TOKEN = rb"([A-Za-z][A-Za-z0-9._:-]*)"
_META_CHARSET_RE = re.compile(
    rb"<meta\b[^>]*?\bcharset\s*=\s*[\"']?\s*" + _ENCODING_TOKEN,
    re.IGNORECASE | re.DOTALL,
)
_META_CONTENT_CHARSET_RE = re.compile(
    rb"<meta\b[^>]*?\bcontent\s*=\s*[\"'][^\"']*?\bcharset\s*=\s*[\"']?\s*"
    + _ENCODING_TOKEN,
    re.IGNORECASE | re.DOTALL,
)
_XML_ENCODING_RE = re.compile(
    rb"<\?xml\b[^>]*?\bencoding\s*=\s*[\"']\s*" + _ENCODING_TOKEN,
    re.IGNORECASE | re.DOTALL,
)
_NUMERIC_REFERENCE_RE = re.compile(
    r"&#(?:x(?P<hex>[0-9a-f]+)|(?P<decimal>[0-9]+));?", re.IGNORECASE
)
_C1_RE = re.compile(r"[\x80-\x9f]")
_UNDEFINED_WINDOWS_1252 = {0x81, 0x8D, 0x8F, 0x90, 0x9D}


def _detect_bom(data: bytes) -> tuple[str, bytes] | None:
    """Return the endian-specific codec and BOM for a Unicode byte-order mark."""

    # The four-byte marks must be checked before the two-byte marks because
    # UTF-32 little-endian begins with the UTF-16 little-endian mark.
    for encoding, prefix in (
        ("utf-32-le", b"\xff\xfe\x00\x00"),
        ("utf-32-be", b"\x00\x00\xfe\xff"),
        ("utf-8", b"\xef\xbb\xbf"),
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ):
        if data.startswith(prefix):
            return encoding, prefix
    return None


def _canonical_explicit_encoding(label: str) -> str:
    """Resolve a declared codec through Python's codec registry."""

    candidate = label.strip().strip("\"'").strip()
    try:
        return codecs.lookup(candidate).name
    except LookupError as exc:
        raise ValueError(f"unknown encoding: {label}") from exc


def _find_declared_encoding(prefix: bytes) -> str | None:
    """Find the first supported HTML/XML declaration in a byte prefix."""

    matches = []
    for pattern in (_META_CHARSET_RE, _META_CONTENT_CHARSET_RE, _XML_ENCODING_RE):
        match = pattern.search(prefix)
        if match is not None:
            matches.append((match.start(), match.group(1).decode("ascii")))
    if not matches:
        return None
    return min(matches, key=lambda item: item[0])[1]


def _decode_windows_1252_preserving_undefined(data: bytes) -> str:
    """Decode Windows-1252 while retaining undefined bytes as C1 code points."""

    chunks: list[str] = []
    start = 0
    for index, value in enumerate(data):
        if value not in _UNDEFINED_WINDOWS_1252:
            continue
        if start < index:
            chunks.append(data[start:index].decode("cp1252"))
        # Keep the exact byte visible to normalize_legacy_characters so it can
        # raise a useful error instead of silently dropping or replacing it.
        chunks.append(chr(value))
        start = index + 1
    if start < len(data):
        chunks.append(data[start:].decode("cp1252"))
    return "".join(chunks)


def decode_html(
    data: bytes, *, http_charset: str | None = None
) -> tuple[str, DecodeDiagnostics]:
    """Decode HTML bytes using deterministic SEC-friendly precedence."""

    bom = _detect_bom(data)
    if bom is not None:
        encoding, prefix = bom
        return data[len(prefix) :].decode(encoding), DecodeDiagnostics(encoding, "bom")
    if http_charset is not None:
        encoding = _canonical_explicit_encoding(http_charset)
        return data.decode(encoding), DecodeDiagnostics(encoding, "http-charset")
    declared = _find_declared_encoding(data[:8192])
    if declared is not None:
        encoding = _canonical_explicit_encoding(declared)
        return data.decode(encoding), DecodeDiagnostics(encoding, "document-declaration")
    try:
        return data.decode("utf-8"), DecodeDiagnostics("utf-8", "strict-utf-8")
    except UnicodeDecodeError:
        decoded = _decode_windows_1252_preserving_undefined(data)
        return decoded, DecodeDiagnostics("windows-1252", "windows-1252-fallback")


def _windows_1252_character(value: int) -> str:
    if value in _UNDEFINED_WINDOWS_1252:
        raise ValueError(f"undefined Windows-1252 byte 0x{value:02x}")
    return bytes([value]).decode("cp1252")


def normalize_legacy_characters(text: str) -> str:
    """Normalize Windows-1252 numeric references and literal C1 characters."""

    def replace_reference(match: re.Match[str]) -> str:
        raw_value = match.group("hex") or match.group("decimal")
        value = int(raw_value, 16) if match.group("hex") else int(raw_value)
        if 0x80 <= value <= 0x9F:
            return _windows_1252_character(value)
        return match.group(0)

    normalized = _NUMERIC_REFERENCE_RE.sub(replace_reference, text)

    def replace_control(match: re.Match[str]) -> str:
        return _windows_1252_character(ord(match.group(0)))

    return _C1_RE.sub(replace_control, normalized)
