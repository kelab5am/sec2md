"""Conservative, source-preserving conversion for spreadsheet cells."""

from decimal import Decimal, localcontext

import pytest

from sec2md.xlsx_values import convert_cell


@pytest.mark.parametrize(
    "text,role,expected,number_format",
    [
        ("$ 215,938", "number", Decimal("215938"), '"$"#,##0'),
        ("( 259 )", "number", Decimal("-259"), "#,##0;(#,##0)"),
        ("12.3 %", "percent", Decimal("0.123"), "0.0%"),
        ("12.3 %", "number", Decimal("0.123"), "0.0%"),
        ("12.30", "percent", Decimal("0.1230"), "0.00%"),
        ("0.00", "number", Decimal("0.00"), "#,##0.00"),
        ("0.00%", "percent", Decimal("0.0000"), "0.00%"),
        ("−12.50", "number", Decimal("-12.50"), "#,##0.00"),
        ("+12", "number", Decimal("12"), "#,##0"),
        ("($ 1,234.50)", "number", Decimal("-1234.50"), '"$"#,##0.00;("$"#,##0.00)'),
        ("(12.3%)", "percent", Decimal("-0.123"), "0.0%;(0.0%)"),
        ("1.25", "number", Decimal("1.25"), "#,##0.00"),
        ("999999999999999", "number", Decimal("999999999999999"), "#,##0"),
        (" 1,234.00\u00a0", "number", Decimal("1234.00"), "#,##0.00"),
    ],
)
def test_complete_numeric_tokens_preserve_value_and_display(text, role, expected, number_format):
    result = convert_cell(text, role=role)
    assert result.value == expected
    assert result.value.as_tuple().exponent == expected.as_tuple().exponent
    assert result.number_format == number_format
    assert result.original == text
    assert result.review_reason is None


@pytest.mark.parametrize("text", ["", " \t\u00a0", "—", "–", "-", "Revenue", "N/A"])
@pytest.mark.parametrize("role", ["text", "number", "percent"])
def test_blanks_dashes_and_ordinary_text_have_no_warning(text, role):
    result = convert_cell(text, role=role)
    assert result.value == (None if not text.strip() else text)
    assert result.original == text
    assert result.review_reason is None


@pytest.mark.parametrize("text", ["00123", "Jul 26, 2026", "(1)", "12.3%", "=1+1", "123"])
def test_text_role_never_coerces_source(text):
    result = convert_cell(text, role="text")
    assert result.value == text
    assert result.original == text
    assert result.number_format == "@"
    assert result.review_reason is None


@pytest.mark.parametrize(
    "text",
    [
        "1,23",
        "12,34,567",
        "1 234",
        "1,234,",
        "1.234,56",
        "1.2.3",
        "1234567890123456",
        "0.1234567890123456",
        "00123",
        "00.12",
        "Jul 26, 2026",
        "2026-07-26",
        "€123",
        "£123",
        "USD 123",
        "123$",
        "1–2",
        "1-2",
        ">12",
        "≤12",
        "123*",
        "123(a)",
        "123[1]",
        "123¹",
        "(123",
        "123)",
        "((123))",
        "(-123)",
        "(+123)",
        "--123",
        "+-123",
        "-0",
        "−0.00",
        "(0)",
        "-0%",
        "=1+1",
        "1e3",
        "12%%",
        "$12%",
        "1\n2",
        "１２３",
        "1" + "0" * 308,
        "0." + "0" * 308 + "1",
    ],
)
def test_ambiguous_numeric_candidates_remain_text_with_review_reason(text):
    result = convert_cell(text, role="number")
    assert result.value == text
    assert result.original == text
    assert result.number_format == "@"
    assert result.review_reason


def test_percentage_conversion_does_not_depend_on_decimal_context():
    with localcontext() as context:
        context.prec = 3
        result = convert_cell("12.3456789012345%", role="percent")
    assert result.value == Decimal("0.123456789012345")
    assert result.number_format == "0.0000000000000%"


def test_percentage_underflow_stays_text():
    text = "0." + "0" * 306 + "3%"
    result = convert_cell(text, role="percent")
    assert result.value == text
    assert result.review_reason


@pytest.mark.parametrize(
    "prefix,suffix,places,expected_value",
    [
        ("", "", 249, Decimal("1")),
        ("$", "", 246, Decimal("1")),
        ("(", ")", 120, Decimal("-1")),
        ("($", ")", 117, Decimal("-1")),
        ("", "%", 252, Decimal("0.01")),
        ("(", "%)", 123, Decimal("-0.01")),
    ],
)
def test_complete_format_length_boundary(prefix, suffix, places, expected_value):
    supported = prefix + "1." + "0" * places + suffix
    result = convert_cell(supported, role="number")
    assert result.value == expected_value
    assert result.original == supported
    assert len(result.number_format) == 255
    assert result.review_reason is None

    unsupported = prefix + "1." + "0" * (places + 1) + suffix
    result = convert_cell(unsupported, role="number")
    assert result.value == unsupported
    assert result.original == unsupported
    assert result.number_format == "@"
    assert result.review_reason


@pytest.mark.parametrize("text", ["1." + "0" * 260, "0." + "0" * 306 + "3"])
def test_in_range_values_with_unsupported_display_precision_stay_text(text):
    result = convert_cell(text, role="number")
    assert result.value == text
    assert result.original == text
    assert result.number_format == "@"
    assert result.review_reason
