#!/usr/bin/env python3
"""
Test script to verify OCR stability improvements.
Tests the new timestamp validation and markdown parsing capabilities.
"""

import sys
import json
from datetime import datetime

# Add parent directory to path
import os
api_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, api_dir)

from services.ocr_service import (
    _validate_timestamp,
    _parse_markdown_formatted_response,
    _extract_json_from_text,
    _heuristic_parse_text,
)


def test_timestamp_validation():
    """Test timestamp validation with various formats."""
    print("\n=== Testing Timestamp Validation ===")

    test_cases = [
        ("2023-11-26 12:08:59", True, "Valid timestamp"),
        ("2023-11-26 12:08:69", False, "Invalid seconds (69)"),
        ("2023-11-26 25:30:00", False, "Invalid hours (25)"),
        ("2023-11-26 12:75:00", False, "Invalid minutes (75)"),
        ("11/26/2023 14:32:00", True, "Valid MM/DD/YYYY format"),
        ("11/26/2023 14:32", True, "Valid MM/DD/YYYY without seconds"),
        ("14:32", True, "Valid time only"),
        ("25:99:99", False, "All invalid"),
        ("2023-11-26", True, "Date only (no time)"),
    ]

    passed = 0
    failed = 0

    for timestamp, expected, description in test_cases:
        result = _validate_timestamp(timestamp)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} {description}: '{timestamp}' -> {result} (expected {expected})")
    
    print(f"\nTimestamp validation: {passed} passed, {failed} failed")
    return failed == 0


def test_markdown_parsing():
    """Test markdown-formatted response parsing."""
    print("\n=== Testing Markdown Parsing ===")

    markdown_response = """**Receipt JSON Extraction**

**Key Fields:**

*   **Amount:** $24.45
*   **Currency:** USD
*   **Expense Date:** 11/26/2023
*   **Category:** Grocery
*   **Vendor:** Walmart
*   **Tax Rate:** 0.0%
*   **Tax Amount:** $0.00
*   **Total Amount:** $24.45
*   **Payment Method:** Cash
*   **Reference Number:** 0000000000000000
*   **Notes:** None
*   **Receipt Timestamp:** 11/26/2023 12:08:59

**Note:** The receipt timestamp is based on the visible time on the receipt."""

    result = _parse_markdown_formatted_response(markdown_response)

    if result and len(result) > 0:
        print(f"✓ Successfully parsed markdown response")
        print(f"  Extracted fields: {list(result.keys())}")
        print(f"  Amount: {result.get('amount')}")
        print(f"  Currency: {result.get('currency')}")
        print(f"  Vendor: {result.get('vendor')}")
        print(f"  Receipt Timestamp: {result.get('receipt_timestamp')}")
        
        # Verify key fields
        expected_fields = ['amount', 'currency', 'vendor', 'receipt_timestamp']
        missing = [f for f in expected_fields if f not in result]
        if missing:
            print(f"✗ Missing fields: {missing}")
            return False
        return True
    else:
        print(f"✗ Failed to parse markdown response (result={result})")
        return False


def test_json_extraction():
    """Test JSON extraction from mixed content."""
    print("\n=== Testing JSON Extraction ===")

    test_cases = [
        (
            '{"amount": 24.45, "currency": "USD", "vendor": "Walmart"}',
            True,
            "Pure JSON"
        ),
        (
            '```json\n{"amount": 24.45, "currency": "USD"}\n```',
            True,
            "JSON in markdown code block"
        ),
        (
            'Some text before\n{"amount": 24.45, "currency": "USD"}\nSome text after',
            True,
            "JSON embedded in text"
        ),
        (
            '**Receipt Data**\n{"amount": 24.45, "currency": "USD"}',
            True,
            "JSON with markdown headers"
        ),
    ]

    passed = 0
    failed = 0

    for content, should_parse, description in test_cases:
        result = _extract_json_from_text(content)
        success = result is not None
        status = "✓" if success == should_parse else "✗"
        if success == should_parse:
            passed += 1
        else:
            failed += 1
        print(f"{status} {description}: parsed={success}")
        if result:
            print(f"    Fields: {list(result.keys())}")
    
    print(f"\nJSON extraction: {passed} passed, {failed} failed")
    return failed == 0


def test_heuristic_parsing():
    """Test heuristic parsing with invalid timestamps."""
    print("\n=== Testing Heuristic Parsing ===")

    # Test with invalid timestamp that should be skipped
    text_with_invalid_timestamp = """
    Walmart Receipt
    Amount: $24.45
    Currency: USD
    Date: 11/26/2023
    Time: 12:08:69
    Vendor: Walmart
    """

    result = _heuristic_parse_text(text_with_invalid_timestamp)

    if result:
        print(f"✓ Heuristic parsing completed")
        print(f"  Extracted fields: {list(result.keys())}")
        
        # Check that invalid timestamp was skipped
        if 'receipt_timestamp' not in result:
            print(f"✓ Invalid timestamp correctly skipped")
            return True
        else:
            print(f"✗ Invalid timestamp was not skipped: {result.get('receipt_timestamp')}")
            return False
    else:
        print(f"✗ Heuristic parsing failed")
        return False


def test_ocr_response_stability():
    """Test handling of different OCR response formats."""
    print("\n=== Testing OCR Response Stability ===")

    # Simulate the two different response formats mentioned in the issue

    # Format 1: Structured JSON (stable)
    structured_response = {
        "amount": 24.45,
        "currency": "USD",
        "expense_date": "2023-11-26",
        "category": None,
        "vendor": "Walmart",
        "tax_rate": 0.0,
        "tax_amount": 0.0,
        "total_amount": 24.45,
        "payment_method": None,
        "reference_number": None,
        "notes": None,
        "receipt_timestamp": "2023-11-26 12:08:59"
    }

    # Format 2: Raw markdown (unstable, needs parsing)
    markdown_response = """**Receipt JSON Extraction**

**Key Fields:**

*   **Amount:** $24.45
*   **Currency:** USD
*   **Expense Date:** 11/26/2023
*   **Category:** Grocery
*   **Vendor:** Walmart
*   **Tax Rate:** 0.0%
*   **Tax Amount:** $0.00
*   **Total Amount:** $24.45
*   **Payment Method:** Cash
*   **Reference Number:** 0000000000000000
*   **Notes:** None
*   **Receipt Timestamp:** 11/26/2023 12:08:59"""

    print("Testing Format 1: Structured JSON")
    if isinstance(structured_response, dict) and 'amount' in structured_response:
        print(f"✓ Structured response is valid JSON")
        print(f"  Fields: {list(structured_response.keys())}")
    else:
        print(f"✗ Structured response parsing failed")
        return False

    print("\nTesting Format 2: Markdown Response")
    parsed_markdown = _parse_markdown_formatted_response(markdown_response)
    if parsed_markdown and 'amount' in parsed_markdown:
        print(f"✓ Markdown response parsed successfully")
        print(f"  Fields: {list(parsed_markdown.keys())}")
        print(f"  Amount: {parsed_markdown.get('amount')}")
        print(f"  Vendor: {parsed_markdown.get('vendor')}")
    else:
        print(f"✗ Markdown response parsing failed")
        return False

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("OCR Stability Test Suite")
    print("=" * 60)

    results = []

    results.append(("Timestamp Validation", test_timestamp_validation()))
    results.append(("Markdown Parsing", test_markdown_parsing()))
    results.append(("JSON Extraction", test_json_extraction()))
    results.append(("Heuristic Parsing", test_heuristic_parsing()))
    results.append(("OCR Response Stability", test_ocr_response_stability()))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} test groups passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
