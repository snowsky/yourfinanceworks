"""Unit tests for CSV formula-injection escaping.

Bank statement CSV exports contain LLM-extracted text (description, category) sourced
from arbitrary uploaded files. A cell beginning with =, +, -, @, tab or CR is interpreted
as a formula by Excel/LibreOffice/Sheets, enabling code/data exfiltration when the victim
opens the export. escape_csv_formula() neutralises that while leaving plain numbers intact.

Pure-function tests: no DB / external services required.
"""

import pytest

from core.utils.csv_safety import escape_csv_formula


@pytest.mark.unit
class TestEscapeCsvFormula:
    def test_none_becomes_empty(self):
        assert escape_csv_formula(None) == ""

    def test_empty_string_unchanged(self):
        assert escape_csv_formula("") == ""

    def test_plain_text_unchanged(self):
        assert escape_csv_formula("Coffee shop") == "Coffee shop"

    @pytest.mark.parametrize("payload", [
        "=HYPERLINK(\"http://evil\",\"x\")",
        "+1+1",
        "@SUM(A1:A9)",
        "=cmd|' /C calc'!A0",
        "\tinjected",
        "\rinjected",
    ])
    def test_formula_prefixes_are_neutralised(self, payload):
        out = escape_csv_formula(payload)
        assert out.startswith("'")
        assert out == "'" + payload

    def test_plain_negative_number_not_mangled(self):
        # Legitimate negative amounts must stay numeric, not become "'-45.67"
        assert escape_csv_formula("-45.67") == "-45.67"
        assert escape_csv_formula(-45.67) == "-45.67"

    def test_plain_positive_number_unchanged(self):
        assert escape_csv_formula("1234.56") == "1234.56"
        assert escape_csv_formula(1234) == "1234"

    def test_dash_text_is_escaped(self):
        # Starts with '-' but is not a number -> treat as potential formula
        assert escape_csv_formula("-1+cmd") == "'-1+cmd"

    def test_plus_phone_number_is_escaped(self):
        # "+44 7700..." is not a valid float -> escaped (safe default)
        assert escape_csv_formula("+44 7700 900900") == "'+44 7700 900900"
