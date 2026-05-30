"""Unit tests for parse_number locale-aware amount parsing.

Regression coverage for the bank-statement money-parsing bug where European-formatted
amounts (dot=thousands, comma=decimal) were parsed ~1000x too small because the parser
unconditionally treated the comma as a thousands separator.

Pure-function tests: no DB / external services required.
"""

import pytest

from commercial.ai.services.ocr_service._shared import parse_number


@pytest.mark.unit
class TestParseNumberPassthrough:
    def test_none_returns_none(self):
        assert parse_number(None) is None

    def test_int_passthrough(self):
        assert parse_number(1234) == 1234.0

    def test_float_passthrough(self):
        assert parse_number(1234.56) == 1234.56

    def test_empty_string_returns_none(self):
        assert parse_number("") is None

    def test_garbage_returns_none(self):
        assert parse_number("abc") is None
        assert parse_number(".") is None


@pytest.mark.unit
class TestParseNumberDecimalSeparator:
    def test_plain_decimal(self):
        assert parse_number("1234.56") == 1234.56

    def test_us_thousands_and_decimal(self):
        # comma=thousands, dot=decimal
        assert parse_number("1,234.56") == 1234.56

    def test_us_multi_thousands_and_decimal(self):
        assert parse_number("1,234,567.89") == 1234567.89

    def test_eu_thousands_and_decimal(self):
        # dot=thousands, comma=decimal  (the core regression)
        assert parse_number("1.234,56") == 1234.56

    def test_eu_multi_thousands_and_decimal(self):
        assert parse_number("1.234.567,89") == 1234567.89

    def test_eu_decimal_only(self):
        assert parse_number("123,45") == 123.45

    def test_eu_decimal_one_digit(self):
        assert parse_number("1234,5") == 1234.5


@pytest.mark.unit
class TestParseNumberThousandsGrouping:
    def test_us_thousands_only(self):
        # 3 trailing digits after a single comma => thousands group, not decimal
        assert parse_number("1,234") == 1234.0

    def test_us_multi_thousands_only(self):
        assert parse_number("1,234,567") == 1234567.0

    def test_eu_thousands_only(self):
        # multiple dots, no comma => thousands grouping
        assert parse_number("1.234.567") == 1234567.0

    def test_single_dot_treated_as_decimal(self):
        # Ambiguous (could be EU thousands) but dot-as-decimal is the dominant default.
        assert parse_number("1.234") == 1.234


@pytest.mark.unit
class TestParseNumberSignsAndSymbols:
    def test_parentheses_negative(self):
        assert parse_number("(1.234,56)") == -1234.56

    def test_leading_minus(self):
        assert parse_number("-1,234.56") == -1234.56

    def test_currency_symbol_us(self):
        assert parse_number("$1,234.56") == 1234.56

    def test_currency_symbol_eu(self):
        assert parse_number("€1.234,56") == 1234.56

    def test_space_thousands_separator_eu(self):
        # Some locales group with spaces: "1 234,56"
        assert parse_number("1 234,56") == 1234.56
