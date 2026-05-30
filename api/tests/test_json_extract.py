"""Unit tests for extract_json_payload.

Regression coverage for silent transaction loss: the previous non-greedy regex
(\\[[\\s\\S]*?\\]) stopped at the first ']', so a ']' inside a value or a nested array
truncated the parse and dropped transactions.

Pure-function tests: no DB / heavy imports.
"""

import pytest

from core.utils.json_extract import extract_json_payload


@pytest.mark.unit
class TestExtractJsonPayload:
    def test_none_and_empty(self):
        assert extract_json_payload("") is None
        assert extract_json_payload(None) is None
        assert extract_json_payload("no json here") is None

    def test_flat_array(self):
        out = extract_json_payload('[{"date": "2024-01-01"}, {"date": "2024-01-02"}]')
        assert out == [{"date": "2024-01-01"}, {"date": "2024-01-02"}]

    def test_bracket_inside_value_is_not_truncated(self):
        # The core regression: ']' inside a description must NOT cut the array short.
        text = '[{"date": "2024-01-01", "description": "ATM withdrawal [branch 5]"}, {"date": "2024-01-02", "description": "Card"}]'
        out = extract_json_payload(text)
        assert isinstance(out, list)
        assert len(out) == 2
        assert out[0]["description"] == "ATM withdrawal [branch 5]"

    def test_nested_array_value(self):
        out = extract_json_payload('[{"date": "2024-01-01", "tags": [1, 2, 3]}]')
        assert out == [{"date": "2024-01-01", "tags": [1, 2, 3]}]

    def test_markdown_fenced(self):
        text = '```json\n[{"date": "2024-01-01"}]\n```'
        assert extract_json_payload(text) == [{"date": "2024-01-01"}]

    def test_leading_and_trailing_prose(self):
        text = 'Sure, here are the transactions: [{"date": "2024-01-01"}] Hope that helps!'
        assert extract_json_payload(text) == [{"date": "2024-01-01"}]

    def test_single_object(self):
        assert extract_json_payload('{"date": "2024-01-01"}') == {"date": "2024-01-01"}

    def test_array_preferred_over_object(self):
        # Stray object before the real array -> the array wins.
        text = '{"note": "meta"} then [{"date": "2024-01-01"}]'
        assert extract_json_payload(text) == [{"date": "2024-01-01"}]

    def test_first_bracket_is_prose_not_json(self):
        text = 'see line [42] -> [{"date": "2024-01-01"}]'
        assert extract_json_payload(text) == [{"date": "2024-01-01"}]
