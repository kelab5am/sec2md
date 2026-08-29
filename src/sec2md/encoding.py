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
_META_START_RE = re.compile(rb"<meta(?=[\s/>])", re.IGNORECASE)
_XML_START_RE = re.compile(rb"<\?xml\b", re.IGNORECASE)
_RAW_TEXT_CLOSE_RE = re.compile(rb"</\s*(?:script|style)\b[^>]*>", re.IGNORECASE)
_CONTENT_CHARSET_RE = re.compile(
    rb"(?:^|;)\s*charset\s*=\s*[\"']?\s*" + _ENCODING_TOKEN,
    re.IGNORECASE,
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


def _meta_attributes(tag: bytes) -> dict[bytes, bytes | None]:
    """Parse one meta tag's attributes without decoding arbitrary bytes."""

    attributes: dict[bytes, bytes | None] = {}
    index = len(b"<meta")
    length = len(tag)
    while index < length:
        while index < length and (tag[index] in b" \t\r\n" or tag[index] == ord("/")):
            index += 1
        if index >= length or tag[index] == ord(">"):
            break
        name_start = index
        while index < length and tag[index] not in b" \t\r\n=>/":
            index += 1
        if name_start == index:
            index += 1
            continue
        name = tag[name_start:index].lower()
        while index < length and tag[index] in b" \t\r\n":
            index += 1
        value: bytes | None = None
        if index < length and tag[index] == ord("="):
            index += 1
            while index < length and tag[index] in b" \t\r\n":
                index += 1
            if index < length and tag[index] in (ord('"'), ord("'")):
                quote = tag[index]
                index += 1
                value_start = index
                while index < length and tag[index] != quote:
                    index += 1
                value = tag[value_start:index]
                if index < length:
                    index += 1
            else:
                value_start = index
                while index < length and tag[index] not in b" \t\r\n>":
                    index += 1
                value = tag[value_start:index].rstrip(b"/")
        attributes[name] = value
    return attributes


def _markup_tags(prefix: bytes):
    """Yield actual markup tags, skipping comments and raw-text contents."""

    index = 0
    length = len(prefix)
    while index < length:
        if prefix[index] != ord("<"):
            index += 1
            continue

        if prefix.startswith(b"<!--", index):
            comment_end = prefix.find(b"-->", index + 4)
            if comment_end < 0:
                return
            index = comment_end + 3
            continue

        tag_end = index + 1
        quote: int | None = None
        while tag_end < length:
            value = prefix[tag_end]
            if quote is not None:
                if value == quote:
                    quote = None
            elif value in (ord('"'), ord("'")):
                quote = value
            elif value == ord(">"):
                break
            tag_end += 1
        if tag_end >= length:
            return

        tag = prefix[index : tag_end + 1]
        yield index, tag

        tag_name_match = re.match(rb"<([A-Za-z][A-Za-z0-9:-]*)\b", tag)
        if tag_name_match is not None:
            tag_name = tag_name_match.group(1).lower()
            if tag_name in {b"script", b"style"} and not tag.rstrip().endswith(b"/>"):
                raw_close = _RAW_TEXT_CLOSE_RE.search(prefix, tag_end + 1)
                if raw_close is None:
                    return
                index = raw_close.start()
                continue

        index = tag_end + 1


def _find_meta_declared_encodings(prefix: bytes) -> list[tuple[int, str]]:
    """Return real charset-bearing meta declarations in source order."""

    declarations: list[tuple[int, str]] = []
    for tag_start, tag in _markup_tags(prefix):
        if _META_START_RE.match(tag) is None:
            continue
        attributes = _meta_attributes(tag)
        declared: bytes | None = None
        charset = attributes.get(b"charset")
        if charset:
            declared = charset.strip()
        elif attributes.get(b"http-equiv", b"").strip().lower() == b"content-type":
            content = attributes.get(b"content")
            if content:
                content_match = _CONTENT_CHARSET_RE.search(content)
                if content_match is not None:
                    declared = content_match.group(1)
        if declared:
            declarations.append((tag_start, declared.decode("ascii")))
    return declarations


def _find_declared_encoding(prefix: bytes) -> str | None:
    """Find the first supported HTML/XML declaration in a byte prefix."""

    matches = _find_meta_declared_encodings(prefix)
    prolog_start = len(prefix) - len(prefix.lstrip(b" \t\r\n"))
    for tag_start, tag in _markup_tags(prefix):
        if tag_start != prolog_start or _XML_START_RE.match(tag) is None:
            continue
        xml_match = _XML_ENCODING_RE.match(tag)
        if xml_match is not None:
            matches.append((tag_start, xml_match.group(1).decode("ascii")))
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
