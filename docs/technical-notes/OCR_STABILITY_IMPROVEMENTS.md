# OCR Stability Improvements

## Problem Statement

The OCR service was experiencing instability when processing receipts and invoices:

1. **Inconsistent Response Formats**: Sometimes the AI model returns structured JSON with individual fields, other times it returns raw markdown-formatted text that needs parsing
2. **Invalid Timestamp Handling**: When OCR extracted invalid timestamps like "12:08:69" (with 69 seconds), the service would fail with "second must be in 0..59" errors
3. **Fallback Chain Issues**: When heuristic parsing failed, the retry logic didn't always work properly

## Solutions Implemented

### 1. Timestamp Validation (`_validate_timestamp`)

Added a dedicated timestamp validation function that checks time components before attempting to parse:

```python
def _validate_timestamp(timestamp_str: str) -> bool:
    """Validate that a timestamp string has valid time components (hours 0-23, minutes 0-59, seconds 0-59)."""
```

**Benefits:**
- Prevents invalid timestamps from reaching the parser
- Logs warnings for invalid timestamps so they can be debugged
- Allows graceful fallback when timestamps are malformed

**Example:**
- `"2023-11-26 12:08:69"` → Rejected (seconds = 69)
- `"2023-11-26 12:08:59"` → Accepted (valid)

### 2. Markdown Response Parser (`_parse_markdown_formatted_response`)

Added a dedicated parser for markdown-formatted OCR responses that some AI models return:

```python
def _parse_markdown_formatted_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse markdown-formatted OCR responses that some AI models return instead of JSON."""
```

**Features:**
- Handles markdown list format: `* **Key:** value`
- Maps markdown keys to standard field names
- Parses numeric values correctly (removes currency symbols)
- Validates timestamps before storing
- Filters out header lines and null values

**Example Input:**
```
**Key Fields:**
* **Amount:** $24.45
* **Currency:** USD
* **Vendor:** Walmart
* **Receipt Timestamp:** 11/26/2023 12:08:59
```

**Example Output:**
```python
{
    'amount': 24.45,
    'currency': 'USD',
    'vendor': 'Walmart',
    'receipt_timestamp': '11/26/2023 12:08:59'
}
```

### 3. Enhanced JSON Extraction (`_extract_json_from_text`)

Improved the JSON extraction logic to:
- Strip markdown formatting before parsing
- Handle markdown headers and bullet points
- Validate that extracted JSON is reasonable (not just `{"raw": "..."}`)

### 4. Improved Heuristic Parsing (`_heuristic_parse_text`)

Enhanced heuristic parsing to:
- Validate timestamps before accepting them
- Skip invalid timestamps instead of failing
- Provide better fallback behavior

### 5. Multi-Stage Extraction Pipeline

Updated the main extraction logic to use a multi-stage approach:

1. **Try structured JSON extraction** - If the AI returns proper JSON
2. **Try markdown parsing** - If the AI returns markdown-formatted text
3. **Try heuristic parsing** - If the AI returns plain text
4. **Validate timestamps** - Check all extracted timestamps for validity
5. **Fallback to AI retry** - If heuristic parsing fails, retry with AI LLM

## Testing

A comprehensive test suite (`api/scripts/test_ocr_stability.py`) validates:

- ✓ Timestamp validation with various formats
- ✓ Markdown response parsing
- ✓ JSON extraction from mixed content
- ✓ Heuristic parsing with invalid timestamps
- ✓ OCR response stability across different formats

**Test Results:**
```
✓ PASS: Timestamp Validation (9/9 tests)
✓ PASS: Markdown Parsing
✓ PASS: JSON Extraction (4/4 tests)
✓ PASS: Heuristic Parsing
✓ PASS: OCR Response Stability

Total: 5/5 test groups passed
```

## Impact

### Before
- OCR failures when timestamps had invalid seconds (e.g., "12:08:69")
- Inconsistent handling of markdown-formatted responses
- Fallback logic didn't always work properly

### After
- Invalid timestamps are detected and skipped gracefully
- Both JSON and markdown-formatted responses are handled correctly
- Multi-stage extraction pipeline ensures maximum compatibility
- Better logging for debugging OCR issues

## Files Modified

- `api/services/ocr_service.py` - Core OCR service with new parsers and validators
- `api/scripts/test_ocr_stability.py` - Comprehensive test suite

## Usage

The improvements are transparent to existing code. The OCR service automatically:

1. Detects the response format (JSON, markdown, or plain text)
2. Applies the appropriate parser
3. Validates all extracted data
4. Falls back gracefully if parsing fails

No changes needed to code that calls the OCR service.
