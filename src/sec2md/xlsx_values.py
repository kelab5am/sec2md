"""Conservative numeric values for the optional spreadsheet exporter."""

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Literal


@dataclass(frozen=True)
class CellValue:
    value: str | Decimal | None
    number_format: str
    original: str
    review_reason: str | None = None


# Spaces may separate a sign/currency marker from its number, never digits.
_TOKEN = re.compile(
    r"(?P<sign>[+\-−]?)\s*(?P<currency>\$?)\s*"
    r"(?P<number>(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)"
    r"(?:\.[0-9]+)?)\s*(?P<percent>%?)"
)
_EXCEL_MAX = Decimal("9.99999999999999E+307")
_EXCEL_MIN = Decimal("2.2250738585072014E-308")


def convert_cell(text: str, *, role: Literal["text", "number", "percent"]) -> CellValue:
    """Convert only a complete token with a source-supported numeric role."""
    token = text.strip()
    if not token:
        return CellValue(None, "@", text)
    if role == "text" or token in {"-", "–", "—"}:
        return CellValue(text, "@", text)
    if not any(character.isdigit() for character in token):
        return CellValue(text, "@", text)

    accounting = token.startswith("(") and token.endswith(")")
    if accounting:
        token = token[1:-1].strip()
    match = _TOKEN.fullmatch(token)
    if match is None:
        return CellValue(
            text,
            "@",
            text,
            "Not a complete supported US numeric token; verify the source value and markers.",
        )
    sign, currency, number, explicit_percent = match.group("sign", "currency", "number", "percent")
    if accounting and sign:
        return CellValue(text, "@", text, "Conflicting signs; verify the source sign.")
    percent = bool(explicit_percent) or role == "percent"
    if currency and percent:
        return CellValue(text, "@", text, "Currency and percent conflict; verify the source units.")

    value = Decimal(number.replace(",", ""))
    if accounting or sign in {"-", "−"}:
        value = value.copy_negate()
    if value.is_zero() and value.is_signed():
        return CellValue(text, "@", text, "Negative zero retained; verify the source meaning.")

    # Tuple construction shifts the exponent exactly, independent of Decimal context.
    parts = value.as_tuple()
    significant = "".join(str(digit) for digit in parts.digits).rstrip("0")
    if len(significant) > 15:
        return CellValue(
            text, "@", text, "Exceeds Excel's 15 significant digits; retain source text."
        )
    if percent:
        value = Decimal((parts.sign, parts.digits, parts.exponent - 2))
    magnitude = value.copy_abs()
    if magnitude and (magnitude > _EXCEL_MAX or magnitude < _EXCEL_MIN):
        return CellValue(text, "@", text, "Outside Excel's numeric range; retain source text.")

    places = len(number.partition(".")[2])
    number_format = "0" if percent else "#,##0"
    if places:
        number_format += "." + "0" * places
    if percent:
        number_format += "%"
    if currency:
        number_format = '"$"' + number_format
    if accounting:
        number_format += ";(" + number_format + ")"
    return CellValue(value, number_format, text)
