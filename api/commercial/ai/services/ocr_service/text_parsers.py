"""Text parsing utilities for OCR output: JSON, markdown, CSV, heuristic, and validation."""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

from core.utils.currency import CURRENCY_SYMBOL_MAP

from ._shared import logger


def _validate_timestamp(timestamp_str: str) -> bool:
    """Validate that a timestamp string has valid time components (hours 0-23, minutes 0-59, seconds 0-59)."""
    time_match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", timestamp_str)
    if not time_match:
        return True  # No time component, so it's valid

    hours = int(time_match.group(1))
    minutes = int(time_match.group(2))
    seconds = int(time_match.group(3)) if time_match.group(3) else 0

    if not (0 <= hours <= 23):
        logger.warning(f"Invalid hours in timestamp '{timestamp_str}': {hours}")
        return False
    if not (0 <= minutes <= 59):
        logger.warning(f"Invalid minutes in timestamp '{timestamp_str}': {minutes}")
        return False
    if not (0 <= seconds <= 59):
        logger.warning(f"Invalid seconds in timestamp '{timestamp_str}': {seconds}")
        return False

    return True


def _looks_like_base64_encrypted(value: str) -> bool:
    """Check if a value looks like base64 encoded encrypted data."""
    if not isinstance(value, str) or len(value) < 20:
        return False

    base64_pattern = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")

    if "@" in value and "." in value:
        return False
    if value.isalpha() or value.isdigit():
        return False
    if len(value) < 30:
        return False

    return bool(base64_pattern.match(value)) and len(value) > 30


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Try to find and parse the first JSON object embedded in a text block."""
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text)

    text = re.sub(
        r"^(page\s+\d+:|response:|here is the json:|json:|analysis\s*result:)\s*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    text = re.sub(r"^\*\*[^*]+\*\*\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[#\*]+\s+.*?:.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-\*]\s+", "", text, flags=re.MULTILINE)

    try:
        return json.loads(text)
    except Exception:
        log_text = text if len(text) < 500 else f"{text[:250]}...{text[-250:]}"
        logger.warning(f"Failed to parse JSON from text: {log_text}")

    start_idx = text.find("{")
    while start_idx != -1:
        brace = 0
        for i in range(start_idx, len(text)):
            if text[i] == "{":
                brace += 1
            elif text[i] == "}":
                brace -= 1
                if brace == 0:
                    candidate = text[start_idx : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            return parsed
                    except Exception:
                        pass
                    break
        start_idx = text.find("{", start_idx + 1)

    return None


def _parse_markdown_formatted_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse markdown-formatted OCR responses that some AI models return instead of JSON.

    Handles formats like:
    **Key Fields:**
    * **Amount:** $24.45
    * **Currency:** USD
    * **Vendor:** Walmart
    """
    data: Dict[str, Any] = {}

    pattern = r"^\*\s+\*\*([^*:]+)\*\*[:\s]+(.+?)$"
    matches = re.finditer(pattern, text, re.MULTILINE)

    key_mapping = {
        "amount": "amount",
        "currency": "currency",
        "currency code": "currency",
        "expense date": "expense_date",
        "date": "expense_date",
        "transaction date": "expense_date",
        "category": "category",
        "vendor": "vendor",
        "merchant": "vendor",
        "store": "vendor",
        "tax rate": "tax_rate",
        "vat rate": "tax_rate",
        "tax amount": "tax_amount",
        "vat amount": "tax_amount",
        "total amount": "total_amount",
        "total": "total_amount",
        "payment method": "payment_method",
        "payment": "payment_method",
        "reference number": "reference_number",
        "reference": "reference_number",
        "receipt number": "reference_number",
        "invoice number": "reference_number",
        "notes": "notes",
        "memo": "notes",
        "receipt timestamp": "receipt_timestamp",
        "timestamp": "receipt_timestamp",
        "transaction time": "receipt_timestamp",
        "receipt time": "receipt_timestamp",
    }

    for match in matches:
        key = match.group(1).strip().lower()
        value = match.group(2).strip()

        if key in ("key fields", "note", "notes", "important", "example", "receipt json extraction"):
            continue

        if not value or value.lower() in ("none", "null", "n/a", "", "unknown"):
            continue

        if key not in key_mapping:
            continue

        standard_key = key_mapping[key]

        if standard_key in ("amount", "tax_rate", "tax_amount", "total_amount"):
            try:
                numeric_str = re.sub(r"[^0-9.,\-]", "", value)
                if "," in numeric_str and "." in numeric_str:
                    numeric_str = numeric_str.replace(",", "")
                else:
                    numeric_str = numeric_str.replace(",", ".")
                data[standard_key] = float(numeric_str)
                continue
            except (ValueError, AttributeError):
                pass

        if standard_key == "receipt_timestamp":
            if _validate_timestamp(value):
                data[standard_key] = value
            else:
                logger.warning(f"Skipping invalid timestamp from markdown: {value}")
            continue

        data[standard_key] = value

    logger.info(f"Parsed markdown response into {len(data)} fields: {list(data.keys())}")
    return data if data else None


def _parse_csv_like_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse CSV-like responses that some AI models return instead of JSON."""
    if "," not in text or "{" in text:
        return None

    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        return None

    data: Dict[str, Any] = {}

    for value in parts:
        value = value.strip()

        if value.lower() in ("null", "none", "n/a", ""):
            continue

        if re.match(r"^[A-Z]{3}$", value):
            if "currency" not in data:
                data["currency"] = value
                continue

        if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", value):
            if "expense_date" not in data:
                data["expense_date"] = value
                continue

        if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}", value):
            if "receipt_timestamp" not in data:
                data["receipt_timestamp"] = value
                continue

        amount_match = re.search(r"([$€£¥₹])\s*([0-9.,]+)", value)
        if amount_match:
            try:
                amount_str = amount_match.group(2).replace(",", "")
                amount_val = float(amount_str)
                if "amount" not in data:
                    data["amount"] = amount_val
                elif "total_amount" not in data:
                    data["total_amount"] = amount_val
                if "currency" not in data:
                    symbol = amount_match.group(1)
                    data["currency"] = CURRENCY_SYMBOL_MAP.get(symbol, "USD")
                continue
            except Exception:
                pass

        try:
            num_val = float(re.sub(r"[^0-9.-]", "", value))
            if "amount" not in data and num_val > 0:
                data["amount"] = num_val
            elif "tax_amount" not in data and num_val > 0:
                data["tax_amount"] = num_val
            elif "total_amount" not in data and num_val > 0:
                data["total_amount"] = num_val
            continue
        except Exception:
            pass

        if len(value) > 2 and not value.replace(".", "").replace("-", "").isdigit():
            if "vendor" not in data:
                data["vendor"] = value
            elif "category" not in data:
                data["category"] = value

    logger.info(f"Parsed CSV-like response into {len(data)} fields: {list(data.keys())}")
    return data if data else None


def _heuristic_parse_text(text: str) -> Optional[Dict[str, Any]]:
    """Heuristic parser for plain OCR text to extract likely fields."""
    data: Dict[str, Any] = {}

    m_total = re.search(r"\btotal\s*[:\-]?\s*([$€£R$]?\s*[0-9.,]+)\b", text, flags=re.IGNORECASE)
    if m_total:
        data["total"] = m_total.group(1)
    m_amt = re.search(r"\bamount\s*[:\-]?\s*([$€£R$]?\s*[0-9.,]+)\b", text, flags=re.IGNORECASE)
    if m_amt and "total" not in data:
        data["amount"] = m_amt.group(1)

    m_cur = re.search(r"\b(USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|INR|BRL)\b", text, flags=re.IGNORECASE)
    if m_cur:
        data["currency"] = m_cur.group(1).upper()

    timestamp_found = False

    combined_patterns = [
        r"(\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",
        r"(\d{4}[-/.]\d{2}[-/.]\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",
        r"(\d{2}[-/.]\d{2}[-/.]\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",
    ]

    for pattern in combined_patterns:
        m_combined = re.search(pattern, text)
        if m_combined:
            candidate_timestamp = m_combined.group(1)
            if _validate_timestamp(candidate_timestamp):
                data["receipt_timestamp"] = candidate_timestamp
                timestamp_found = True
                break
            else:
                logger.warning(f"Skipping invalid timestamp candidate: {candidate_timestamp}")

    if not timestamp_found:
        m_date = re.search(r"(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[/.-]\d{2}[/.-]\d{2,4})", text)
        if m_date:
            data["date"] = m_date.group(1)

        m_time = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)", text)

        if m_time and m_date:
            try:
                date_str = m_date.group(1)
                time_str = m_time.group(1)
                candidate_timestamp = f"{date_str} {time_str}"
                if _validate_timestamp(candidate_timestamp):
                    data["receipt_timestamp"] = candidate_timestamp
                    timestamp_found = True
                else:
                    logger.warning(f"Skipping invalid combined timestamp: {candidate_timestamp}")
            except Exception:
                logger.debug("Failed to build combined date+time timestamp from heuristic match", exc_info=True)
        elif m_time:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                time_str = m_time.group(1)
                candidate_timestamp = f"{today} {time_str}"
                if _validate_timestamp(candidate_timestamp):
                    data["receipt_timestamp"] = candidate_timestamp
                    timestamp_found = True
                else:
                    logger.warning(f"Skipping invalid time-only timestamp: {candidate_timestamp}")
            except Exception:
                logger.debug("Failed to build time-only timestamp from heuristic match", exc_info=True)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        skip_headers = [
            "**receipt data**",
            "**key fields**",
            "**summary**",
            "**receipt**",
            "receipt details",
            "transaction details",
            "extraction results",
        ]

        for line in lines:
            curr_line = line.strip().lower()
            if curr_line.startswith(("**", "#", "##")) or any(h in curr_line for h in skip_headers):
                continue
            data["vendor"] = line[:80]
            break

        if "vendor" not in data and lines:
            data["vendor"] = lines[0][:80]

    return data if data else None
