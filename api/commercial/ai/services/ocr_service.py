import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text
from core.models.models_per_tenant import AIConfig as AIConfigModel
from commercial.ai.settings.ocr_config import get_ocr_config, check_ocr_dependencies, is_ocr_available
from commercial.ai.exceptions.bank_ocr_exceptions import (
    OCRUnavailableError,
    OCRDependencyMissingError,
    OCRConfigurationError
)
from core.utils.timezone import get_tenant_timezone_aware_datetime

def _resolve_log_level(name: str) -> int:
    try:
        return getattr(logging, (name or "INFO").upper(), logging.INFO)
    except Exception:
        return logging.INFO

def parse_number(value: Any) -> Optional[float]:
    """Robust number parsing for OCR results."""
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()

        # Detect sign notations on the original string before stripping non-numeric chars.
        # Only treat as negative when the minus is clearly a sign, not part of a date/ID:
        #   - parenthetical: "(100.00)"
        #   - leading minus: "-100" or trailing minus: "100-"
        #   - minus immediately after a currency symbol: "$-100", "USD-100"
        import re
        is_negative = False
        if s.startswith('(') and s.endswith(')'):
            is_negative = True
        elif s.startswith('-') or s.endswith('-'):
            is_negative = True
        elif re.search(r'[^0-9]-', s) and re.search(r'-[0-9]', s):
            # minus surrounded by non-digit on left and digit on right → currency prefix like "$-100"
            is_negative = True

        # Remove everything except digits, comma, and dot
        s = re.sub(r"[^0-9,.]", "", s)
        
        # Determine if comma is thousands or decimal
        if "," in s and "." in s:
            # Both present: assume comma is thousands separator
            s = s.replace(",", "")
        elif "," in s:
            # Only comma present: assume it's the decimal separator
            s = s.replace(",", ".")
            
        if not s or s == ".":
            return None
            
        val = float(s)
        return -val if is_negative else val
    except Exception:
        return None

def first_key(d: Dict[str, Any], keys: list[str]) -> Any:
    """Find the first key in a dictionary that exists and has a value."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return None

async def apply_ocr_extraction_to_expense(
    db: Session,
    expense: Any,
    extracted: Dict[str, Any],
    attachment_id: Optional[int] = None,
    ai_extraction_attempted: bool = False,
    file_path: Optional[str] = None,
    ai_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Apply extracted OCR data to an Expense record with robust mapping and normalization.
    This logic is shared between standard reprocessing and batch uploads.
    """
    from core.models.models_per_tenant import Expense, ExpenseAttachment, AIConfig as AIConfigModel
    from core.utils.timezone import get_tenant_timezone_aware_datetime
    from datetime import datetime, timezone
    import json

    expense_id = expense.id
    logger.info(f"Applying OCR extraction to expense {expense_id}. Attachment: {attachment_id}")

    # Map fields robustly
    extracted = extracted if isinstance(extracted, dict) else {}
    logger.info(f"OCR extracted keys: {list(extracted.keys()) if isinstance(extracted, dict) else 'non-dict result'}")

    # Debug: Log the actual extracted data to see what the AI returned
    if isinstance(extracted, dict):
        logger.info(f"OCR extracted data: {json.dumps(extracted, indent=2, default=str)}")

        # Check if vendor field contains CSV-like data (common AI model error)
        vendor_value = extracted.get('vendor', '')
        if isinstance(vendor_value, str) and vendor_value.count(',') >= 3:
            logger.warning(f"Detected CSV-like data in vendor field: {vendor_value[:100]}...")
            # Try to parse as CSV
            csv_parsed = _parse_csv_like_response(vendor_value)
            if csv_parsed:
                logger.info(f"Successfully parsed CSV-like response, replacing extracted data")
                extracted = csv_parsed

    # If we only got raw text, first try to extract embedded JSON, then try markdown, then heuristics
    if set(extracted.keys()) == {"raw"} and isinstance(extracted.get("raw"), str):
        extracted_text = extracted["raw"]
        # Detect known OCR transport errors and fail early
        if any(err in extracted_text for err in [
            "Error processing image", "HTTPConnectionPool", "Failed to establish a new connection", "Connection refused"
        ]):
            expense.analysis_status = "failed"
            expense.analysis_error = extracted_text[:500]
            db.commit()
            logger.error(f"OCR transport error for expense {expense.id}: {expense.analysis_error}")
            return

        # Attempt to parse structrued data from raw text using multiple strategies
        parsed_data = None
        parsing_method = None

        # Strategy 1: JSON extraction
        parsed_data = _extract_json_from_text(extracted_text)
        if parsed_data and isinstance(parsed_data, dict) and len(parsed_data) > 1:
            parsing_method = "json"
            extracted.update(parsed_data)
            logger.info(f"Parsed embedded JSON keys: {list(parsed_data.keys())}")

        # Strategy 2: Markdown extraction
        if not parsing_method:
            parsed_data = _parse_markdown_formatted_response(extracted_text)
            if parsed_data and len(parsed_data) > 0:
                parsing_method = "markdown"
                extracted.update(parsed_data)
                logger.info(f"Parsed markdown response keys: {list(parsed_data.keys())}")

        # Strategy 3: Heuristic extraction & AI Fallback
        if not parsing_method:
            parsed_data = _heuristic_parse_text(extracted_text)
            if parsed_data:
                parsing_method = "heuristic"
                extracted.update(parsed_data)
                logger.info(f"Heuristic parse extracted keys: {list(parsed_data.keys())}")

                # Quality Control: Check for suspicious timestamp if using heuristics
                if "receipt_timestamp" in parsed_data:
                    timestamp_str = parsed_data["receipt_timestamp"]
                    try:
                        from dateutil import parser as dateparser
                        parsed_dt = dateparser.parse(str(timestamp_str))
                        # Check if the parsed date is reasonable (not too far in future/past)
                        now = datetime.now(timezone.utc)
                        year_diff = abs(parsed_dt.year - now.year)

                        if year_diff > 5:  # More than 5 years difference seems suspicious
                            logger.warning(f"Heuristic timestamp seems unreasonable: {timestamp_str} (parsed as {parsed_dt})")

                            # Retry with AI if needed
                            if not ai_extraction_attempted:
                                ai_result = await _retry_ocr_with_ai(
                                    file_path, ai_config, db, "questionable timestamp"
                                )

                                if ai_result and isinstance(ai_result, dict) and "receipt_timestamp" in ai_result:
                                    # Validate AI result timestamp
                                    ai_timestamp = ai_result["receipt_timestamp"]
                                    try:
                                        ai_parsed_dt = dateparser.parse(str(ai_timestamp))
                                        ai_year_diff = abs(ai_parsed_dt.year - now.year)
                                        if ai_year_diff <= 5:
                                            logger.info(f"✅ AI LLM provided better timestamp: {ai_timestamp}")
                                            extracted.update(ai_result)
                                        else:
                                            logger.warning(f"❌ AI LLM timestamp also questionable: {ai_timestamp}")
                                    except Exception:
                                        logger.warning("❌ AI LLM timestamp parsing failed")
                                else:
                                    logger.warning("❌ AI LLM retry did not provide timestamp")
                    except Exception as e:
                         logger.warning(f"Failed to validate heuristic timestamp '{timestamp_str}': {e}")
            else:
                # Heuristic failed completely
                logger.info("Heuristic parsing returned no data, attempting AI LLM extraction...")
                if not ai_extraction_attempted:
                    ai_result = await _retry_ocr_with_ai(
                        file_path, ai_config, db, "failed heuristic parsing"
                    )
                    if ai_result:
                        logger.info("✅ AI LLM retry successful, using AI results")
                        extracted.update(ai_result)
                    else:
                        logger.warning("❌ AI LLM retry also failed")
                else:
                    logger.info("AI LLM retry not available (already attempted)")
    # Extract amount/total from receipt
    # Note: We'll handle amount updates after extracting all fields
    extracted_amount = parse_number(first_key(extracted, [
        "total_amount", "total", "amount", "grand_total", "subtotal"
    ]))

    # Currency - convert symbols to ISO codes
    cur = first_key(extracted, ["currency", "currency_code", "iso_currency", "total_currency"]) or None
    if isinstance(cur, str) and len(cur) <= 5:
        # Map common currency symbols to ISO codes
        currency_symbol_map = {
            '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₹': 'INR',
            'C$': 'CAD', 'A$': 'AUD', 'NZ$': 'NZD', 'HK$': 'HKD', 'S$': 'SGD',
            'R$': 'BRL', 'R': 'ZAR', '₽': 'RUB', '₩': 'KRW', '₺': 'TRY',
            'kr': 'SEK', 'CHF': 'CHF',
        }
        # If it's a symbol, convert it; otherwise use as-is (assuming it's already an ISO code)
        cur_upper = cur.upper().strip()
        if cur in currency_symbol_map:
            expense.currency = currency_symbol_map[cur]
        elif len(cur_upper) == 3 and cur_upper.isalpha():
            # Looks like a valid ISO code
            expense.currency = cur_upper
        else:
            # Unknown format, default to USD
            expense.currency = 'USD'
    elif not expense.currency:
        expense.currency = 'USD' # Default if missing

    # Date
    date_str = first_key(extracted, ["expense_date", "date", "transaction_date", "purchase_date"]) or None
    if date_str:
        try:
            from dateutil import parser as dateparser  # type: ignore
            parsed_dt = dateparser.parse(str(date_str))
            if parsed_dt:
                expense.expense_date = parsed_dt
        except Exception:
            logger.warning(f"Failed to parse expense_date '{date_str}' from OCR result", exc_info=True)

    # Receipt timestamp (exact time from receipt)
    timestamp_str = first_key(extracted, ["receipt_timestamp", "timestamp", "transaction_time", "receipt_time"]) or None
    if timestamp_str:
        try:
            # First validate the timestamp format
            if not _validate_timestamp(str(timestamp_str)):
                logger.warning(f"Timestamp validation failed for '{timestamp_str}', skipping")
                expense.receipt_time_extracted = False
            else:
                from dateutil import parser as dateparser  # type: ignore
                parsed_timestamp = dateparser.parse(str(timestamp_str))
                if parsed_timestamp:
                    expense.receipt_timestamp = parsed_timestamp
                    expense.receipt_time_extracted = True
                    logger.info(f"Extracted receipt timestamp: {parsed_timestamp} for expense {expense.id}")
                else:
                    expense.receipt_time_extracted = False
        except Exception as e:
            logger.warning(f"Failed to parse receipt timestamp '{timestamp_str}': {e}")
            expense.receipt_time_extracted = False
    else:
        expense.receipt_time_extracted = False

    # Category and vendor
    cat = first_key(extracted, ["category", "expense_category"]) or None
    if cat:
        # Ensure category is clean text, not encrypted data
        category_str = str(cat).strip()
        if category_str and not _looks_like_base64_encrypted(category_str):
            expense.category = category_str
        else:
            logger.warning(f"Invalid category data detected, using default")
            expense.category = "General"
    elif not expense.category:
        expense.category = "General"

    vend = first_key(extracted, ["vendor", "merchant", "seller", "store", "payee"]) or None
    if vend:
        # Ensure vendor is clean text, not encrypted data
        vendor_str = str(vend).strip()
        if vendor_str and not _looks_like_base64_encrypted(vendor_str):
            expense.vendor = vendor_str
        else:
            logger.warning(f"Invalid vendor data detected, using default")
            expense.vendor = "Unknown Vendor"
    elif not expense.vendor:
        expense.vendor = "Unknown Vendor"

    # Taxes and total
    tr = parse_number(first_key(extracted, ["tax_rate", "vat_rate"]))
    ta = parse_number(first_key(extracted, ["tax_amount", "vat_amount"]))
    tt = parse_number(first_key(extracted, ["total_amount", "total"]))

    expense.tax_rate = tr if tr is not None else expense.tax_rate
    expense.tax_amount = ta if ta is not None else expense.tax_amount

    # Amount update logic:
    # 1. Update individual attachment first
    # 2. Then sum all attachments to update expense total

    # Use the most specific amount found for this attachment
    final_attachment_amount = tt if tt is not None else extracted_amount
    if final_attachment_amount is not None:
        final_attachment_amount = round(final_attachment_amount, 4)

    if attachment_id:
        attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()
        if attachment:
            attachment.analysis_status = "done"
            attachment.extracted_amount = final_attachment_amount
            attachment.analysis_result = extracted
            attachment.analysis_error = None
            db.commit()
            logger.info(f"Updated attachment {attachment_id} with extracted amount {final_attachment_amount}")

    # Aggregate all attachments for this expense
    all_attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()

    # Check if this expense was imported from email and has multiple attachments
    # Or just generally sum up all successful OCR results
    total_sum = 0
    any_success = False
    for att in all_attachments:
        if att.analysis_status == "done" and att.extracted_amount is not None:
            total_sum += att.extracted_amount
            any_success = True

    if any_success:
        total_sum = round(total_sum, 4)
        logger.info(f"Expense {expense.id}: Aggregated total amount from {len(all_attachments)} attachments: {total_sum}")
        expense.amount = total_sum
        expense.total_amount = total_sum
    else:
        # Fallback to single extraction if aggregation didn't find anything
        if tt is not None:
            tt = round(tt, 4)
            expense.amount = tt
            expense.total_amount = tt
        elif extracted_amount is not None:
            extracted_amount = round(extracted_amount, 4)
            expense.amount = extracted_amount
            if getattr(expense, 'total_amount', None) in (None, 0):
                expense.total_amount = extracted_amount

    # Other details
    pm = first_key(extracted, ["payment_method", "payment", "method"]) or None
    if pm:
        payment_str = str(pm).strip()
        if payment_str and not _looks_like_base64_encrypted(payment_str):
            expense.payment_method = payment_str
        else:
            logger.warning(f"Invalid payment method data detected, skipping")

    ref = first_key(extracted, ["reference_number", "reference", "ref", "receipt_number", "invoice_number"]) or None
    if ref:
        ref_str = str(ref).strip()
        if ref_str and not _looks_like_base64_encrypted(ref_str):
            expense.reference_number = ref_str
        else:
            logger.warning(f"Invalid reference number data detected, skipping")

    notes = first_key(extracted, ["notes", "memo"]) or None
    if notes:
        notes_str = str(notes).strip()
        if notes_str and not _looks_like_base64_encrypted(notes_str):
            expense.notes = notes_str
        else:
            logger.warning(f"Invalid notes data detected, skipping")
            expense.notes = None

    # Persist normalized extraction as dict
    try:
        # Validate and sanitize the extracted data before storing
        if isinstance(extracted, dict):
            # Ensure all values are JSON serializable and not corrupted
            sanitized_data = {}
            for key, value in extracted.items():
                try:
                    # Test JSON serialization
                    json.dumps(value)
                    # Ensure it's not encrypted data being stored as plain text
                    if isinstance(value, str) and not _looks_like_base64_encrypted(value):
                        sanitized_data[key] = value
                    elif not isinstance(value, str):
                        sanitized_data[key] = value
                    else:
                        logger.warning(f"Skipping potentially corrupted field {key} in analysis_result")
                except (TypeError, ValueError) as ve:
                    logger.warning(f"Skipping non-serializable field {key} in analysis_result: {ve}")

            # Add metadata about extraction method
            if sanitized_data:
                sanitized_data["extraction_metadata"] = {
                    "ai_extraction_attempted": ai_extraction_attempted,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            expense.analysis_result = sanitized_data if sanitized_data else {"status": "extracted", "extraction_metadata": {"ai_extraction_attempted": ai_extraction_attempted}}
            logger.info(f"Stored sanitized analysis_result with keys: {list(sanitized_data.keys()) if sanitized_data else ['status']}")
        else:
            expense.analysis_result = {"items": extracted} if extracted else {"status": "no_data"}

    except Exception as e:
        logger.error(f"Failed to set analysis_result for expense {expense.id}: {e}")
        # Store a safe fallback that won't cause encryption issues
        expense.analysis_result = {"error": "Failed to store result", "timestamp": datetime.now(timezone.utc).isoformat()}

    expense.analysis_status = "done"
    expense.analysis_updated_at = get_tenant_timezone_aware_datetime(db)

    try:
        mapped_preview = {
            "amount": expense.amount,
            "currency": expense.currency,
            "expense_date": str(expense.expense_date),
            "category": expense.category,
            "vendor": expense.vendor,
            "tax_rate": expense.tax_rate,
            "tax_amount": expense.tax_amount,
            "total_amount": expense.total_amount,
        }
        logger.info(f"Mapped OCR fields for expense {expense.id}: {mapped_preview}")
    except Exception:
        logger.debug(f"Could not log OCR field preview for expense {expense.id}", exc_info=True)

    db.commit()
    logger.info(f"Expense {expense.id} analysis updated: {expense.analysis_status}")

logging.basicConfig(level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger(__name__)


# Import unified AI configuration service
from commercial.ai.services.ai_config_service import AIConfigService
from commercial.prompt_management.services.prompt_service import get_prompt_service

def _get_ai_config_from_env() -> Optional[Dict[str, Any]]:
    """
    Legacy function for backward compatibility.
    Use AIConfigService.get_ai_config() for new implementations.
    """
    return AIConfigService._get_env_config("ocr")


def track_ai_usage(db: Session, ai_config: Dict[str, Any], operation_type: str = "general", metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Track AI usage by incrementing the usage_count for the given AI config.

    Args:
        db: Database session
        ai_config: AI configuration dictionary
        operation_type: Type of operation (e.g., 'ocr', 'pdf_extraction', 'general')
        metadata: Additional metadata about the operation
    """
    try:
        # Create a masked version of ai_config for logging
        masked_config = {}
        if ai_config:
            masked_config = {k: (v if k not in ('api_key', 'provider_url', 'api_secret') else '********') for k, v in ai_config.items()}
            
        logger.info(f"🎯 track_ai_usage called with: {masked_config}, operation_type: {operation_type}")
        if not ai_config or 'provider_name' not in ai_config:
            logger.warning("❌ ai_config is None or missing provider_name")
            return

        # Find the AI config by provider_name and model_name to match the one being used
        provider_name = ai_config.get('provider_name')
        model_name = ai_config.get('model_name')
        logger.info(f"🔍 Looking for AI config: {provider_name}/{model_name}")

        db_config = db.query(AIConfigModel).filter(
            AIConfigModel.provider_name == provider_name,
            AIConfigModel.model_name == model_name,
            AIConfigModel.is_active == True
        ).first()

        if db_config:
            old_count = db_config.usage_count
            db_config.usage_count += 1
            db_config.last_used_at = datetime.now(timezone.utc)

            # Track OCR-specific usage if this is an OCR operation
            if operation_type == "ocr":
                # Initialize OCR usage count if not present
                if not hasattr(db_config, 'ocr_usage_count') or db_config.ocr_usage_count is None:
                    db_config.ocr_usage_count = 0
                db_config.ocr_usage_count += 1
                logger.info(f"🔍 Tracked OCR usage for {provider_name}/{model_name}: OCR count = {db_config.ocr_usage_count}")

            db.commit()
            logger.info(f"✅ Tracked AI usage for {provider_name}/{model_name}: {old_count} → {db_config.usage_count} (operation: {operation_type})")

            # Log additional metadata if provided
            if metadata:
                logger.info(f"📊 Operation metadata: {metadata}")

        else:
            logger.warning(f"❌ Could not find AI config to track usage: {provider_name}/{model_name}")
            # Avoid querying all configs to prevent crashing if the table is large or issues exist
            logger.debug("Skipping full config dump for stability")
    except Exception as e:
        logger.error(f"❌ Failed to track AI usage: {e}")
        # Don't raise exception to avoid breaking the main functionality


def track_ocr_usage(db: Session, ai_config: Dict[str, Any], extraction_method: str, processing_time: Optional[float] = None, text_length: Optional[int] = None) -> None:
    """
    Track OCR-specific usage with detailed metadata.

    Args:
        db: Database session
        ai_config: AI configuration dictionary
        extraction_method: Method used ('pdf_loader' or 'ocr')
        processing_time: Time taken for processing in seconds
        text_length: Length of extracted text
    """
    metadata = {
        "extraction_method": extraction_method,
        "processing_time": processing_time,
        "text_length": text_length,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Track general AI usage with OCR-specific metadata
    track_ai_usage(db, ai_config, operation_type="ocr", metadata=metadata)

    # Log OCR-specific metrics for monitoring
    time_str = f"{processing_time:.2f}s" if processing_time is not None else "N/A"
    logger.info(f"📈 OCR Usage Metrics - Method: {extraction_method}, Time: {time_str}, Text Length: {text_length}")


def get_ai_usage_stats(db: Session, provider_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get AI usage statistics including OCR-specific metrics.

    Args:
        db: Database session
        provider_name: Optional filter by provider name

    Returns:
        Dictionary with usage statistics
    """
    try:
        query = db.query(AIConfigModel).filter(AIConfigModel.is_active == True)
        if provider_name:
            query = query.filter(AIConfigModel.provider_name == provider_name)

        configs = query.all()
        stats = {
            "total_configs": len(configs),
            "total_usage": sum(c.usage_count or 0 for c in configs),
            "total_ocr_usage": sum(getattr(c, 'ocr_usage_count', 0) or 0 for c in configs),
            "configs": []
        }

        for config in configs:
            config_stats = {
                "provider_name": config.provider_name,
                "model_name": config.model_name,
                "usage_count": config.usage_count or 0,
                "ocr_usage_count": getattr(config, 'ocr_usage_count', 0) or 0,
                "ocr_enabled": getattr(config, 'ocr_enabled', False),
                "last_used_at": config.last_used_at.isoformat() if config.last_used_at else None
            }
            stats["configs"].append(config_stats)

        return stats
    except Exception as e:
        logger.error(f"Failed to get AI usage stats: {e}")
        return {"error": str(e)}


def publish_ocr_usage_metrics(db: Session, operation_type: str, extraction_method: str, processing_time: float, success: bool) -> None:
    """
    Publish OCR usage metrics for monitoring and analytics.

    Args:
        db: Database session
        operation_type: Type of operation ('bank_statement', 'expense', 'invoice')
        extraction_method: Method used ('pdf_loader', 'ocr')
        processing_time: Processing time in seconds
        success: Whether the operation was successful
    """
    try:
        # This could be extended to publish to monitoring systems like Prometheus, CloudWatch, etc.
        time_str = f"{processing_time:.2f}s" if processing_time is not None else "N/A"
        logger.info(
            f"📊 OCR Metrics - Operation: {operation_type}, Method: {extraction_method}, "
            f"Time: {time_str}, Success: {success}"
        )

        # Example: Could publish to a metrics collection service
        # metrics_client.increment(f"ocr.{operation_type}.{extraction_method}.{'success' if success else 'failure'}")
        # metrics_client.histogram(f"ocr.{operation_type}.processing_time", processing_time)

    except Exception as e:
        logger.error(f"Failed to publish OCR usage metrics: {e}")

# Keep producers alive across calls so messages can be delivered before process exit
_PRODUCER_CACHE: dict[str, dict[str, any]] = {}
def _parse_markdown_formatted_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse markdown-formatted OCR responses that some AI models return instead of JSON.

    Handles formats like:
    **Key Fields:**
    * **Amount:** $24.45
    * **Currency:** USD
    * **Vendor:** Walmart
    """
    import re

    data: Dict[str, Any] = {}

    # Pattern to match markdown list items with key-value pairs
    # Matches: * **Key:** value or * **Key**: value
    # Only match lines that start with * (list marker)
    pattern = r'^\*\s+\*\*([^*:]+)\*\*[:\s]+(.+?)$'

    matches = re.finditer(pattern, text, re.MULTILINE)

    # Map markdown keys to our standard field names
    key_mapping = {
        'amount': 'amount',
        'currency': 'currency',
        'currency code': 'currency',
        'expense date': 'expense_date',
        'date': 'expense_date',
        'transaction date': 'expense_date',
        'category': 'category',
        'vendor': 'vendor',
        'merchant': 'vendor',
        'store': 'vendor',
        'tax rate': 'tax_rate',
        'vat rate': 'tax_rate',
        'tax amount': 'tax_amount',
        'vat amount': 'tax_amount',
        'total amount': 'total_amount',
        'total': 'total_amount',
        'payment method': 'payment_method',
        'payment': 'payment_method',
        'reference number': 'reference_number',
        'reference': 'reference_number',
        'receipt number': 'reference_number',
        'invoice number': 'reference_number',
        'notes': 'notes',
        'memo': 'notes',
        'receipt timestamp': 'receipt_timestamp',
        'timestamp': 'receipt_timestamp',
        'transaction time': 'receipt_timestamp',
        'receipt time': 'receipt_timestamp',
    }

    for match in matches:
        key = match.group(1).strip().lower()
        value = match.group(2).strip()

        # Skip header-like keys that aren't actual data fields
        if key in ('key fields', 'note', 'notes', 'important', 'example', 'receipt json extraction'):
            continue

        # Skip empty values and common null indicators
        if not value or value.lower() in ('none', 'null', 'n/a', '', 'unknown'):
            continue

        # Only process keys that are in our mapping
        if key not in key_mapping:
            continue

        standard_key = key_mapping[key]

        # Parse numeric values
        if standard_key in ('amount', 'tax_rate', 'tax_amount', 'total_amount'):
            try:
                # Remove currency symbols and parse
                numeric_str = re.sub(r'[^0-9.,\-]', '', value)
                if ',' in numeric_str and '.' in numeric_str:
                    numeric_str = numeric_str.replace(',', '')
                else:
                    numeric_str = numeric_str.replace(',', '.')
                data[standard_key] = float(numeric_str)
                continue
            except (ValueError, AttributeError):
                pass

        # Validate timestamp before storing
        if standard_key == 'receipt_timestamp':
            if _validate_timestamp(value):
                data[standard_key] = value
            else:
                logger.warning(f"Skipping invalid timestamp from markdown: {value}")
            continue

        # Store as string for other fields
        data[standard_key] = value

    logger.info(f"Parsed markdown response into {len(data)} fields: {list(data.keys())}")
    return data if data else None


def _parse_csv_like_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse CSV-like responses that some AI models return instead of JSON."""
    import re

    # Check if this looks like a CSV response (comma-separated values)
    if ',' not in text or '{' in text:
        return None

    # Try to parse as comma-separated values
    parts = [p.strip() for p in text.split(',')]

    if len(parts) < 3:
        return None

    data: Dict[str, Any] = {}

    # Smart parsing: detect what each field contains
    for i, value in enumerate(parts):
        value = value.strip()

        # Skip null/empty values
        if value.lower() in ('null', 'none', 'n/a', ''):
            continue

        # Check for currency code (3 uppercase letters)
        if re.match(r'^[A-Z]{3}$', value):
            if 'currency' not in data:
                data['currency'] = value
                continue

        # Check for date (YYYY-MM-DD or similar)
        if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}$', value):
            if 'expense_date' not in data:
                data['expense_date'] = value
                continue

        # Check for timestamp (YYYY-MM-DD HH:MM:SS)
        if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}', value):
            if 'receipt_timestamp' not in data:
                data['receipt_timestamp'] = value
                continue

        # Check for amount with currency symbol ($13.97, €10.00, etc.)
        amount_match = re.search(r'([$€£¥₹])\s*([0-9.,]+)', value)
        if amount_match:
            try:
                amount_str = amount_match.group(2).replace(',', '')
                amount_val = float(amount_str)

                # Determine if this is total_amount or regular amount
                if 'amount' not in data:
                    data['amount'] = amount_val
                elif 'total_amount' not in data:
                    data['total_amount'] = amount_val

                # Extract currency from symbol if not already set
                if 'currency' not in data:
                    symbol = amount_match.group(1)
                    currency_map = {
                        '$': 'USD',
                        '€': 'EUR',
                        '£': 'GBP',
                        '¥': 'JPY',
                        '₹': 'INR',
                        'C$': 'CAD',
                        'A$': 'AUD',
                        'NZ$': 'NZD',
                        'HK$': 'HKD',
                        'S$': 'SGD',
                        'R$': 'BRL',
                        'R': 'ZAR',
                        '₽': 'RUB',
                        '₩': 'KRW',
                        '₺': 'TRY',
                        'kr': 'SEK',
                        'CHF': 'CHF',
                        '¥': 'CNY',
                    }
                    data['currency'] = currency_map.get(symbol, 'USD')
                continue
            except:
                pass

        # Check for plain number (could be amount, tax, etc.)
        try:
            num_val = float(re.sub(r'[^0-9.-]', '', value))
            if 'amount' not in data and num_val > 0:
                data['amount'] = num_val
            elif 'tax_amount' not in data and num_val > 0:
                data['tax_amount'] = num_val
            elif 'total_amount' not in data and num_val > 0:
                data['total_amount'] = num_val
            continue
        except:
            pass

        # If we haven't categorized it yet, it might be vendor or category
        if len(value) > 2 and not value.replace('.', '').replace('-', '').isdigit():
            if 'vendor' not in data:
                data['vendor'] = value
            elif 'category' not in data:
                data['category'] = value

    logger.info(f"Parsed CSV-like response into {len(data)} fields: {list(data.keys())}")
    return data if data else None


def _validate_timestamp(timestamp_str: str) -> bool:
    """Validate that a timestamp string has valid time components (hours 0-23, minutes 0-59, seconds 0-59)."""
    import re

    # Extract time components (HH:MM:SS or HH:MM)
    time_match = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', timestamp_str)
    if not time_match:
        return True  # No time component, so it's valid

    hours = int(time_match.group(1))
    minutes = int(time_match.group(2))
    seconds = int(time_match.group(3)) if time_match.group(3) else 0

    # Validate ranges
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


def _heuristic_parse_text(text: str) -> Optional[Dict[str, Any]]:
    """Heuristic parser for plain OCR text to extract likely fields."""
    import re
    data: Dict[str, Any] = {}

    # Amount / total
    m_total = re.search(r"\btotal\s*[:\-]?\s*([$€£R$]?\s*[0-9.,]+)\b", text, flags=re.IGNORECASE)
    if m_total:
        data["total"] = m_total.group(1)
    m_amt = re.search(r"\bamount\s*[:\-]?\s*([$€£R$]?\s*[0-9.,]+)\b", text, flags=re.IGNORECASE)
    if m_amt and "total" not in data:
        data["amount"] = m_amt.group(1)

    # Currency
    m_cur = re.search(r"\b(USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|INR|BRL)\b", text, flags=re.IGNORECASE)
    if m_cur:
        data["currency"] = m_cur.group(1).upper()

    # Enhanced timestamp parsing - try multiple patterns
    timestamp_found = False

    # Pattern 1: Combined datetime formats (MM/DD/YY HH:MM:SS, YYYY-MM-DD HH:MM:SS, etc.)
    combined_patterns = [
        r"(\d{2}/\d{2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",  # MM/DD/YY HH:MM:SS
        r"(\d{4}[-/.]\d{2}[-/.]\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",  # YYYY-MM-DD HH:MM:SS
        r"(\d{2}[-/.]\d{2}[-/.]\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)",  # DD/MM/YYYY HH:MM:SS
    ]

    for pattern in combined_patterns:
        m_combined = re.search(pattern, text)
        if m_combined:
            candidate_timestamp = m_combined.group(1)
            # Validate the timestamp before accepting it
            if _validate_timestamp(candidate_timestamp):
                data["receipt_timestamp"] = candidate_timestamp
                timestamp_found = True
                break
            else:
                logger.warning(f"Skipping invalid timestamp candidate: {candidate_timestamp}")

    # If no combined timestamp found, try separate date and time
    if not timestamp_found:
        # Date patterns
        m_date = re.search(r"(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[/.-]\d{2}[/.-]\d{2,4})", text)
        if m_date:
            data["date"] = m_date.group(1)

        # Time patterns
        m_time = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)", text)

        if m_time and m_date:
            # Combine date and time if both found
            try:
                date_str = m_date.group(1)
                time_str = m_time.group(1)
                candidate_timestamp = f"{date_str} {time_str}"
                # Validate before accepting
                if _validate_timestamp(candidate_timestamp):
                    data["receipt_timestamp"] = candidate_timestamp
                    timestamp_found = True
                else:
                    logger.warning(f"Skipping invalid combined timestamp: {candidate_timestamp}")
            except Exception:
                logger.debug("Failed to build combined date+time timestamp from heuristic match", exc_info=True)
        elif m_time:
            # Just time found, use today's date
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                time_str = m_time.group(1)
                candidate_timestamp = f"{today} {time_str}"
                # Validate before accepting
                if _validate_timestamp(candidate_timestamp):
                    data["receipt_timestamp"] = candidate_timestamp
                    timestamp_found = True
                else:
                    logger.warning(f"Skipping invalid time-only timestamp: {candidate_timestamp}")
            except Exception:
                logger.debug("Failed to build time-only timestamp from heuristic match", exc_info=True)

    # Vendor
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        # Define common headers to skip for vendor extraction
        skip_headers = [
            "**receipt data**", "**key fields**", "**summary**", "**receipt**",
            "receipt details", "transaction details", "extraction results"
        ]

        for line in lines:
            curr_line = line.strip().lower()
            # Skip common markdown headers and logical headers
            if curr_line.startswith(("**", "#", "##")) or any(h in curr_line for h in skip_headers):
                continue

            data["vendor"] = line[:80]
            break

        # Fallback to first line if everything was skipped
        if "vendor" not in data and lines:
            data["vendor"] = lines[0][:80]

    return data if data else None


def _looks_like_base64_encrypted(value: str) -> bool:
    """Check if a value looks like base64 encoded encrypted data."""
    if not isinstance(value, str) or len(value) < 20:
        return False

    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')

    # If it contains common plain text patterns, it's probably not encrypted
    if '@' in value and '.' in value:  # Looks like email
        return False
    if value.isalpha() or value.isdigit():  # Simple text or numbers
        return False
    if len(value) < 30:  # Encrypted data is usually longer
        return False

    # Check if it matches base64 pattern and is long enough
    return base64_pattern.match(value) and len(value) > 30


async def _convert_raw_ocr_to_json(
    raw_content: str,
    model_name: str,
    provider_name: str,
    kwargs: Dict[str, Any],
    db_session: Session,
    custom_prompt: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to convert raw OCR output (markdown, text, etc.) to structured JSON.
    This is a second-pass conversion when the first OCR attempt returns non-JSON format.
    """
    try:
        logger.info(f"Converting raw OCR output to JSON using {provider_name}/{model_name}")

        if custom_prompt:
            conversion_prompt = custom_prompt.replace("{{raw_content}}", raw_content)
        else:
            # Define fallback prompt once to avoid duplication
            fallback_ocr_prompt = (
                "You are a data extraction expert. The following is OCR output from a receipt or invoice in various formats (markdown, text, etc.). "
                "Convert it to a compact JSON object with these keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). "
                "For receipt_timestamp, use the exact time from the receipt if visible. "
                "If a field is unknown or not present, set it to null. "
                "Return ONLY the JSON object, no markdown, no explanations.\n\n"
                "OCR Output:\n{{raw_content}}"
            )

            # Try to get prompt from service
            try:
                prompt_service = get_prompt_service(db_session)
                conversion_prompt = prompt_service.get_prompt(
                    name="ocr_data_conversion",
                    variables={"raw_content": raw_content},
                    provider_name=provider_name,
                    fallback_prompt=fallback_ocr_prompt
                )
            except Exception as e:
                logger.warning(f"Failed to get OCR conversion prompt from service: {e}")
                conversion_prompt = fallback_ocr_prompt.replace("{{raw_content}}", raw_content)

        messages = [
            {
                "role": "user",
                "content": conversion_prompt
            }
        ]

        # Use the same LLM provider to convert
        if provider_name.lower() == "ollama":
            try:
                import ollama
                # Get base_url from kwargs or use default
                base_url = kwargs.get("base_url") or os.environ.get("OLLAMA_API_BASE") or "http://localhost:11434"

                # Create Ollama client with custom host
                client = ollama.Client(host=base_url)
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.chat(model=model_name, messages=messages, stream=False)
                    ),
                    timeout=90.0
                )
                content = response.get("message", {}).get("content", "")
            except Exception as e:
                logger.warning(f"Ollama conversion failed: {type(e).__name__}: {e!r} - {str(e)}")
                return None
        else:
            # Use LiteLLM for other providers
            try:
                from litellm import completion
                # Sanitize kwargs for LiteLLM to prevent duplicate 'model' argument
                if "model" in kwargs:
                    del kwargs["model"]
                # Set 90s timeout for LiteLLM requests
                kwargs["request_timeout"] = 90.0
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: completion(model=f"{provider_name}/{model_name}", messages=messages, **kwargs)
                )
                content = response.choices[0].message.content if response.choices else ""
            except Exception as e:
                logger.warning(f"LiteLLM conversion failed: {e}")
                return None

        if not content:
            logger.warning("Conversion LLM returned empty content")
            return None

        # Try to extract JSON from the conversion response
        parsed = _extract_json_from_text(content)
        if parsed:
            logger.info("Successfully extracted JSON from conversion response")
            return parsed

        logger.warning(f"Conversion response did not contain valid JSON: {content[:100]}")
        return None

    except Exception as e:
        logger.error(f"Failed to convert raw OCR to JSON: {e}")
        return None


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Try to find and parse the first JSON object embedded in a text block."""
    import re

    # Strip markdown code blocks if present
    text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)

    # Strip common prefixes from LLMs that can interfere with parsing
    text = re.sub(r'^(page\s+\d+:|response:|here is the json:|json:|analysis\s*result:)\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)

    # Strip markdown headers, formatting, and list bullets
    text = re.sub(r'^\*\*[^*]+\*\*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[#\*]+\s+.*?:.*$', '', text, flags=re.MULTILINE) # Handle "## Vendor: ..."
    text = re.sub(r'^[-\*]\s+', '', text, flags=re.MULTILINE) # Handle bullets

    try:
        # Quick path: whole text is JSON
        return json.loads(text)
    except Exception:
        # If text is too long, don't log the full version in warning
        log_text = text if len(text) < 500 else f"{text[:250]}...{text[-250:]}"
        logger.warning(f"Failed to parse JSON from text: {log_text}")
        pass

    # Find the first balanced {...} block
    start_idx = text.find('{')
    while start_idx != -1:
        brace = 0
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace += 1
            elif text[i] == '}':
                brace -= 1
                if brace == 0:
                    candidate = text[start_idx:i+1]
                    try:
                        parsed = json.loads(candidate)
                        # Validate that we got a reasonable result (not just {"raw": "..."})
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            return parsed
                    except Exception:
                        pass
                    break
        start_idx = text.find('{', start_idx + 1)

    return None


def _get_kafka_producer():
    """Return a Kafka producer if Kafka is configured and library is available, else None."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.getenv("KAFKA_OCR_TOPIC", "expenses_ocr")
    if not bootstrap:
        logger.info("Kafka disabled: KAFKA_BOOTSTRAP_SERVERS not set; will use inline OCR")
        return None, topic
    try:
        # Prefer confluent_kafka if installed
        from confluent_kafka import Producer  # type: ignore

        conf = {
            "bootstrap.servers": bootstrap,
            "client.id": os.getenv("KAFKA_CLIENT_ID", "invoice-app-api"),
        }
        key = f"{bootstrap}|{topic}"
        cached = _PRODUCER_CACHE.get(key)
        if cached:
            return cached["producer"], topic
        producer = Producer(conf)
        _PRODUCER_CACHE[key] = {"producer": producer, "topic": topic}
        logger.info(f"Initialized Kafka producer to {bootstrap}, topic={topic}")
        return producer, topic
    except Exception as e:
        logger.warning(f"Kafka not available ({e}); will fallback to inline OCR processing.")
        return None, topic


def publish_ocr_task(message: Dict[str, Any]) -> bool:
    """Publish an OCR task to Kafka if available. Returns True if published."""
    producer, topic = _get_kafka_producer()
    if not producer:
        return False
    try:
        payload = json.dumps(message).encode("utf-8")
        attempt = int(message.get("attempt", 0))
        logger.info(
            f"Publishing OCR message: expense_id={message.get('expense_id')} tenant_id={message.get('tenant_id')} attachment_id={message.get('attachment_id')} attempt={attempt}"
        )
        headers = [("attempt", str(attempt))]
        # Use a combination of tenant_id and expense_id for better distribution
        key = f"{message.get('tenant_id')}_{message.get('expense_id')}"
        producer.produce(topic, value=payload, key=key, headers=headers)
        producer.flush(10.0)
        logger.info(f"Published OCR task to Kafka topic={topic} expense_id={message.get('expense_id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish OCR task: {e}")
        return False


def publish_fraud_audit_task(tenant_id: int, entity_type: str, entity_id: int, reprocess_mode: bool = False) -> bool:
    """Publish a fraud audit task to Kafka. Returns True if published."""
    producer, topic = _get_kafka_producer_for("KAFKA_FRAUD_AUDIT_TOPIC", "fraud_audit")
    if not producer:
        return False
    try:
        message = {
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "reprocess_mode": reprocess_mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        payload = json.dumps(message).encode("utf-8")
        key = f"{tenant_id}_{entity_type}_{entity_id}"
        producer.produce(topic, value=payload, key=key)
        producer.flush(5.0)
        logger.info(f"Published Fraud Audit task to Kafka topic={topic}: {entity_type} {entity_id} (reprocess_mode: {reprocess_mode})")
        return True
    except Exception as e:
        logger.error(f"Failed to publish Fraud Audit task: {e}")
        return False


def _get_kafka_producer_for(env_name: str, default_topic: str):
    """Return a Kafka producer and a topic for a specific stream based on env var name."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.getenv(env_name, default_topic)
    if not bootstrap:
        logger.info("Kafka disabled: KAFKA_BOOTSTRAP_SERVERS not set; will use inline processing")
        return None, topic
    try:
        from confluent_kafka import Producer  # type: ignore
        conf = {
            "bootstrap.servers": bootstrap,
            "client.id": os.getenv("KAFKA_CLIENT_ID", "invoice-app-api"),
        }
        key = f"{bootstrap}|{topic}"
        cached = _PRODUCER_CACHE.get(key)
        if cached:
            return cached["producer"], topic
        producer = Producer(conf)
        _PRODUCER_CACHE[key] = {"producer": producer, "topic": topic}
        logger.info(f"Initialized Kafka producer to {bootstrap}, topic={topic}")
        return producer, topic
    except Exception as e:
        logger.warning(f"Kafka not available ({e}); will fallback to inline processing.")
        return None, topic


def publish_bank_statement_task(message: Dict[str, Any]) -> bool:
    """Publish a bank statement extraction task to Kafka if available. Returns True if published.
    Expected message keys: tenant_id, statement_id, file_path, attempt (optional)
    """
    producer, topic = _get_kafka_producer_for("KAFKA_BANK_TOPIC", "bank_statements_ocr")
    if not producer:
        logger.error("Kafka producer unavailable for bank statements. Check KAFKA_BOOTSTRAP_SERVERS.")
        return False
    try:
        payload = json.dumps(message).encode("utf-8")
        key = str(message.get("statement_id") or "")
        attempt = int(message.get("attempt", 0))
        headers = [("attempt", str(attempt))]
        try:
            producer.produce(topic, value=payload, key=key, headers=headers)
        except TypeError as e:
            # Older client may not support headers
            logger.debug(f"Produce with headers failed, retrying without headers: {e}")
            producer.produce(topic, value=payload, key=key)
        remaining = producer.flush(1.0)
        if remaining == 0:
            logger.info(f"Published bank statement task to Kafka topic={topic} statement_id={message.get('statement_id')}")
            return True
        logger.error(f"Kafka flush returned remaining={remaining} for bank topic={topic} key={key}")
        return False
    except Exception as e:
        logger.error(f"Failed to publish bank statement task: {e}", exc_info=True)
        return False


def publish_invoice_task(message: Dict[str, Any]) -> bool:
    """Publish an invoice OCR task to Kafka. Expected keys: tenant_id, task_id, file_path."""
    producer, topic = _get_kafka_producer_for("KAFKA_INVOICE_TOPIC", "invoices_ocr")
    if not producer:
        return False
    try:
        payload = json.dumps(message).encode("utf-8")
        key = str(message.get("task_id") or "")
        attempt = int(message.get("attempt", 0))
        headers = [("attempt", str(attempt))]
        producer.produce(topic, value=payload, key=key, headers=headers)
        producer.flush(10.0)
        logger.info(f"Published invoice task to Kafka topic={topic} task_id={message.get('task_id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish invoice task: {e}")
        return False


def publish_invoice_result(task_id: str, tenant_id: Optional[int], data: Dict[str, Any]) -> bool:
    """Publish invoice OCR result keyed by task_id."""
    producer, _ = _get_kafka_producer_for("KAFKA_INVOICE_RESULT_TOPIC", "invoices_ocr_result")
    if not producer:
        return False
    try:
        topic = os.getenv("KAFKA_INVOICE_RESULT_TOPIC", "invoices_ocr_result")
        event = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        producer.produce(topic, key=str(task_id), value=json.dumps(event).encode("utf-8"))
        producer.flush(10.0)
        return True
    except Exception as e:
        logger.warning(f"Failed to publish invoice result event: {e}")
        return False


def publish_ocr_result(expense_id: int, tenant_id: Optional[int], status: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """Publish a compact result event keyed by expense_id to a result topic (suitable for compaction)."""
    producer, _ = _get_kafka_producer()
    if not producer:
        return False
    try:
        topic = os.getenv("KAFKA_OCR_RESULT_TOPIC", "expenses_ocr_result")
        event = {
            "expense_id": expense_id,
            "tenant_id": tenant_id,
            "status": status,
            "ts": datetime.now(timezone.utc).isoformat(),
            **({"details": details} if details else {}),
        }
        producer.produce(topic, key=str(expense_id), value=json.dumps(event).encode("utf-8"))
        producer.flush(10.0)
        return True
    except Exception as e:
        logger.warning(f"Failed to publish OCR result event: {e}")
        return False


def flush_all_producers(timeout_sec: float = 10.0) -> None:
    """Flush all cached Kafka producers. Call this on shutdown."""
    for entry in list(_PRODUCER_CACHE.values()):
        try:
            entry["producer"].flush(timeout_sec)
        except Exception:
            logger.warning("Failed to flush Kafka producer on shutdown", exc_info=True)


def initialize_ocr_dependencies() -> Dict[str, Any]:
    """
    Initialize and check OCR dependencies for bank statement processing.

    Returns:
        Dictionary with initialization status and available components
    """
    logger.info("Initializing OCR dependencies for bank statement processing...")

    try:
        # Get OCR configuration
        ocr_config = get_ocr_config()
        logger.info(f"OCR Configuration loaded: enabled={ocr_config.enabled}")

        # Check dependencies
        dependencies = check_ocr_dependencies()
        logger.info(f"OCR Dependencies: {dependencies}")

        # Check overall availability
        available = is_ocr_available()
        logger.info(f"OCR Available: {available}")

        # Initialize components based on configuration
        components = {}

        if ocr_config.enabled and available:
            # Try to initialize UnstructuredLoader
            try:
                if ocr_config.use_unstructured_api:
                    logger.info("Initializing Unstructured API client...")
                    components["unstructured_api"] = True
                else:
                    logger.info("Initializing local Tesseract OCR...")
                    # Test tesseract availability
                    import pytesseract
                    version = pytesseract.get_tesseract_version()
                    logger.info(f"Tesseract version: {version}")
                    components["tesseract"] = True

            except Exception as e:
                logger.error(f"Failed to initialize OCR components: {e}")
                components["error"] = str(e)

        return {
            "status": "success",
            "config": ocr_config.to_dict(),
            "dependencies": dependencies,
            "available": available,
            "components": components
        }

    except Exception as e:
        logger.error(f"OCR initialization failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "available": False
        }


def validate_ocr_setup() -> None:
    """
    Validate OCR setup and raise appropriate exceptions if not configured properly.

    Raises:
        OCRUnavailableError: If OCR is not available
        OCRDependencyMissingError: If required dependencies are missing
        OCRConfigurationError: If configuration is invalid
    """
    try:
        ocr_config = get_ocr_config()

        if not ocr_config.enabled:
            raise OCRUnavailableError("OCR is disabled in configuration")

        dependencies = check_ocr_dependencies()

        # Check for required dependencies
        if not dependencies["unstructured"]:
            raise OCRDependencyMissingError(
                "unstructured package is required",
                missing_dependency="unstructured"
            )

        # Check specific configuration requirements
        if ocr_config.use_unstructured_api:
            if not ocr_config.unstructured_api_key:
                raise OCRConfigurationError(
                    "Unstructured API key is required when using API mode",
                    config_key="unstructured_api_key"
                )
        else:
            if not dependencies["pytesseract"]:
                raise OCRDependencyMissingError(
                    "pytesseract package is required for local OCR",
                    missing_dependency="pytesseract"
                )

            if not dependencies["tesseract_binary"]:
                raise OCRDependencyMissingError(
                    "Tesseract binary is required for local OCR",
                    missing_dependency="tesseract"
                )

        logger.info("OCR setup validation passed")

    except (OCRUnavailableError, OCRDependencyMissingError, OCRConfigurationError):
        raise
    except Exception as e:
        raise OCRConfigurationError(f"OCR setup validation failed: {e}")


def cancel_ocr_tasks_for_expense(expense_id: int) -> None:
    """Best-effort cancelation placeholder. Real systems may use a cancel topic or outbox table."""
    logger.info(f"Request to cancel OCR tasks for expense_id={expense_id}")
    # No-op: If using Kafka, consider producing a cancel message or managing an outbox/processing table.


async def _retry_ocr_with_ai(
    file_path: Optional[str], 
    ai_config: Optional[Dict[str, Any]], 
    db_session: Session, 
    reason: str
) -> Optional[Dict[str, Any]]:
    """
    Retry OCR extraction using AI LLM when initial extraction is poor.
    Returns the parsed result dict or None.
    """
    if not file_path:
        return None

    retry_ai_config = ai_config or _get_ai_config_from_env()
    if not retry_ai_config:
        logger.info("AI LLM retry not available (no config)")
        return None

    try:
        logger.info(f"🔄 Retrying with AI LLM due to {reason}...")
        ai_result = await _run_ocr(file_path, ai_config=retry_ai_config, db_session=db_session)
        if ai_result and isinstance(ai_result, dict) and len(ai_result) > 1:
             return ai_result
        else:
             return None
    except Exception as retry_error:
        logger.error(f"AI LLM retry failed: {retry_error}")
        return None


async def _run_ocr(file_path: str, custom_prompt: Optional[str] = None, ai_config: Optional[Dict[str, Any]] = None, db_session: Optional[Session] = None) -> Dict[str, Any]:
    """Run OCR using the configured AI provider. Supports multiple providers via LiteLLM."""
    OCR_VERSION = "2024.01.24.03"  # Updated for prompt management logging

    # Initialize prompt service if db session is available
    prompt_service = None
    if db_session:
        try:
            prompt_service = get_prompt_service(db_session)
        except Exception as e:
            logger.warning(f"Failed to initialize prompt service: {e}")

    try:
        # 1. Resolve configuration (Priority: ai_config > environment variables)
        provider_name = None
        model_name = None
        base_url = None
        api_key = None
        ocr_enabled = True # Default to true for env fallback

        if ai_config:
            provider_name = ai_config.get("provider", ai_config.get("provider_name"))
            model_name = ai_config.get("model", ai_config.get("model_name"))
            base_url = ai_config.get("api_base", ai_config.get("provider_url"))
            api_key = ai_config.get("api_key")
            ocr_enabled = ai_config.get("ocr_enabled", False)

            if provider_name:
                provider_name = provider_name.lower()

        # 2. Resolve missing fields from environment variables
        # 2. Resolve missing fields from environment variables
        env_api_base = os.getenv("LLM_API_BASE")
        env_ollama_base = os.getenv("OLLAMA_API_BASE")
        env_api_key = os.getenv("LLM_API_KEY")

        if not provider_name:
            if env_api_base and ("openrouter" in env_api_base or "openrouter.ai" in env_api_base):
                provider_name = "openrouter"
            elif env_api_base and ("api.openai.com" in env_api_base or "openai" in env_api_base):
                provider_name = "openai"
            elif env_api_base and ("anthropic" in env_api_base or "claude" in env_api_base):
                provider_name = "anthropic"
            elif env_api_base and ("google" in env_api_base or "gemini" in env_api_base):
                provider_name = "google"
            elif env_ollama_base or os.getenv("OLLAMA_MODEL"):
                provider_name = "ollama"
            elif env_api_key:
                provider_name = "openai"
            else:
                provider_name = "ollama"

        if not model_name:
            model_name = os.getenv("LLM_MODEL_EXPENSES", os.getenv("OLLAMA_MODEL", "llama3.2-vision:11b"))

        if not base_url:
            # Only default to local Ollama if provider is ollama or generic
            if provider_name == "ollama":
                base_url = env_ollama_base or env_api_base or "http://localhost:11434"
            elif provider_name in ["anthropic", "google", "bedrock", "vertex_ai"]:
                # Do NOT use generic env_api_base for Cloud providers to avoid accidental local proxying
                base_url = None
            else:
                base_url = env_api_base

        if not api_key:
            api_key = env_api_key

        if ai_config:
            logger.info(f"[OCR {OCR_VERSION}] Using explicit config with env fallbacks: {provider_name}/{model_name} at {base_url}")
        else:
            logger.info(f"[OCR {OCR_VERSION}] Using environment fallback: {provider_name}/{model_name} at {base_url}")

        # 3. Capability Check (Respect provided configuration directly)
        if not ocr_enabled:
            logger.warning(f"⚠️ OCR not enabled for provider '{provider_name}'. Please enable OCR in AI configuration settings.")
            return {
                "error": f"OCR not enabled for provider '{provider_name}'.",
                "ocr_not_enabled": True
            }

        # Prepare Prompt
        template_name = "expense_receipt_vision_extraction"
        prompt_text = custom_prompt

        # fallback prompt if service fails or not available
        fallback_prompt = (
            "You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON. "
            "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes, receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). "
            "For receipt_timestamp, extract the exact time from the receipt if visible (not just the date). Look for timestamps like '14:32', '2:45 PM', etc. "
            "If a field is unknown, set it to null. "
            "IMPORTANT: Return ONLY the JSON object, no markdown formatting, no explanations, no headers like '**Receipt Data Extraction**'."
        )

        if not prompt_text and prompt_service:
            try:
                # Try to get managed prompt
                prompt_text = prompt_service.get_prompt(
                    name=template_name,
                    provider_name=provider_name,
                    fallback_prompt=fallback_prompt
                )
            except Exception as e:
                logger.warning(f"Failed to get managed prompt, using fallback: {e}")
                prompt_text = fallback_prompt
        elif not prompt_text:
            prompt_text = fallback_prompt

        # Handle different providers
        if provider_name == "ollama":
            import ollama
            # Use direct Ollama client for better vision support and JSON mode

            try:
                # Use base_url to create client
                client = ollama.Client(host=base_url)

                # Load image as bytes
                with open(file_path, "rb") as f:
                    img_bytes = f.read()

                messages = [
                    {
                        "role": "user",
                        "content": prompt_text,
                        "images": [img_bytes]
                    }
                ]

                # Use format="json" if requested
                options = {"temperature": 0.1}
                t0 = time.time()
                # Wrap in wait_for to prevent indefinite hangs
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.chat(
                            model=model_name,
                            messages=messages,
                            format="json" if custom_prompt is None else None, # Only force JSON for standard extraction
                            options=options,
                            stream=False
                        )
                    ),
                    timeout=90.0
                )

                result = response.get("message", {}).get("content", "")
                dt = (time.time() - t0) * 1000
                processing_time_ms = int(dt)
                logger.info(f"Ollama OCR raw result length={len(result)} duration_ms={dt:.0f}")

                # Log usage
                if prompt_service and not custom_prompt:
                    prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=bool(result),
                        processing_time_ms=processing_time_ms,
                        token_count=len(result) // 4, # Rough estimate for Ollama
                        error_message=None if result else "Empty result"
                    )

                if result:
                    parsed = _extract_json_from_text(result)
                    if parsed is not None:
                        return parsed
                    return {"raw": result}
                return {}

            except Exception as e:
                logger.error(f"Ollama direct OCR processing failed: {type(e).__name__}: {e!r} - {str(e)}")

                # Log failure
                if prompt_service and not custom_prompt:
                     prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=False,
                        processing_time_ms=0,
                        token_count=0,
                        error_message=f"{type(e).__name__}: {str(e) or repr(e)}"
                    )

                return {"error": f"{type(e).__name__}: {str(e)}"}


        # Use LiteLLM for other providers (OpenAI, Anthropic, Google, etc.)
        t0 = time.time()
        try:
            from litellm import completion
            import litellm
            litellm.suppress_debug_info = True

            # Format model name for LiteLLM
            if provider_name == "openai":
                litellm_model = model_name
            elif provider_name == "anthropic":
                litellm_model = f"anthropic/{model_name}"
            elif provider_name == "google":
                litellm_model = f"google/{model_name}"
            elif provider_name == "openrouter":
                # Check if model supports vision capabilities
                if "gpt-oss-20b" in model_name or "free" in model_name:
                    logger.warning(f"Model {model_name} may not support vision. Consider using a vision-capable model like 'openai/gpt-4-vision-preview' or 'anthropic/claude-3-haiku'")
                    # Try to suggest a better model if this one fails
                    return {"error": f"Model '{model_name}' does not support vision capabilities. Please configure a vision-capable model like 'openai/gpt-4-vision-preview', 'anthropic/claude-3-haiku', or 'google/gemini-pro-vision'."}
                litellm_model = f"openrouter/{model_name}"
            else:
                litellm_model = f"{provider_name}/{model_name}"

            # Prepare API key and base URL
            kwargs = {"model": litellm_model}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url and provider_name != "openai":  # OpenAI has default base URL
                kwargs["api_base"] = base_url

            # Encode file to base64
            from core.utils.file_validation import validate_file_path
            try:
                safe_path = validate_file_path(file_path)
            except ValueError as e:
                logger.error(str(e))
                return {"error": f"Invalid file path: {e}"}
            with open(safe_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            is_pdf = file_path.lower().endswith('.pdf')

            # Determine image format for non-PDF files
            if file_path.lower().endswith('.png'):
                image_format = "png"
            elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                image_format = "jpeg"
            elif file_path.lower().endswith('.webp'):
                image_format = "webp"
            else:
                image_format = "png"  # Default fallback for unknown image types

            prompt = prompt_text

            # PDFs must be sent as documents (Anthropic format); images use image_url
            if is_pdf and provider_name == "anthropic":
                file_content_block = {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": image_data,
                    }
                }
            else:
                file_content_block = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{image_format};base64,{image_data}"
                    }
                }

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        file_content_block,
                    ]
                }
            ]

            # Update t0 right before request for accuracy
            t0 = time.time()
            # Set 90s timeout for LiteLLM requests
            kwargs["request_timeout"] = 90.0
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: completion(messages=messages, **kwargs)
            )
            dt = (time.time() - t0) * 1000
            processing_time_ms = int(dt)
            logger.info(f"OCR via LiteLLM result duration_ms={dt:.0f}")

            # Calculate token usage
            total_tokens = 0
            if response and hasattr(response, 'usage') and response.usage:
                total_tokens = getattr(response.usage, 'total_tokens', 0)

            success = False
            error_msg = None

            if response and response.choices and len(response.choices) > 0:
                success = True
                content = response.choices[0].message.content

                # Log usage
                if prompt_service and not custom_prompt:
                     try:
                         prompt_service.log_usage(
                            template_name=template_name,
                            provider_name=provider_name,
                            model_name=model_name,
                            success=True,
                            processing_time_ms=processing_time_ms,
                            token_count=total_tokens,
                            error_message=None
                        )
                         logger.info("Successfully logged usage for OCR success")
                     except Exception as log_error:
                         logger.error(f"Failed to log usage: {log_error}")

                if isinstance(content, str):
                    # Try to parse JSON from response
                    parsed = _extract_json_from_text(content)
                    if parsed is not None:
                        return parsed

                    # If we got raw markdown/text, try a second-pass LLM call to convert to JSON
                    logger.info("First-pass OCR returned non-JSON format, attempting second-pass conversion...")
                    json_conversion_result = await _convert_raw_ocr_to_json(content, model_name, provider_name, kwargs, db_session)
                    if json_conversion_result and "error" not in json_conversion_result:
                        logger.info("Successfully converted raw OCR output to JSON via second-pass LLM")
                        return json_conversion_result

                    # If conversion failed, try heuristic parsing as fallback
                    logger.info("Second-pass LLM conversion failed, attempting heuristic parsing...")
                    heuristic_result = _heuristic_parse_text(content)
                    if heuristic_result:
                        logger.info(f"Heuristic parsing extracted {len(heuristic_result)} fields")
                        return heuristic_result

                    # Last resort: return raw
                    logger.warning("All parsing methods failed, returning raw content")
                    return {"raw": content}
                else:
                    return {"raw": str(content)}
            else:
                if prompt_service and not custom_prompt:
                     try:
                         prompt_service.log_usage(
                            template_name=template_name,
                            provider_name=provider_name,
                            model_name=model_name,
                            success=False,
                            processing_time_ms=processing_time_ms,
                            token_count=total_tokens,
                            error_message="No response from AI provider"
                        )
                     except Exception:
                         logger.warning("Failed to log OCR usage metrics", exc_info=True)
                return {"error": "No response from AI provider"}

        except ImportError:
            return {"error": "LiteLLM not available for non-Ollama providers"}
        except Exception as e:
            # Log failure
            logger.error(f"LiteLLM exception caught: {e}")
            if prompt_service and not custom_prompt:
                try:
                    prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=False,
                        processing_time_ms=int((time.time() - t0) * 1000),
                        token_count=0,
                        error_message=str(e)
                    )
                except Exception as log_error:
                     logger.error(f"Failed to log failure usage: {log_error}")

            logger.error(f"LiteLLM OCR processing failed: {e}")
            error_msg = str(e)
            # Check for specific vision model errors
            if "No endpoints found that support image input" in error_msg:
                logger.warning(f"Vision model '{litellm_model}' does not support image input. Consider switching to a vision-capable model.")
                return {"error": f"Vision model '{model_name}' does not support image input. Please configure a vision-capable model like 'gpt-4-vision-preview' or 'claude-3-haiku'."}
            return {"error": f"LiteLLM OCR failed: {error_msg}"}

    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return {"error": str(e)}

    return {"error": "Unknown error (execution fell through)"}


async def process_attachment_inline(db: Session, expense_id: int, attachment_id: int, file_path: str, tenant_id: int, ai_config: Optional[Dict[str, Any]] = None) -> None:
    """Fallback inline processing when Kafka is not configured."""
    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")
    is_temp_file = False  # Track if we created a temporary file from cloud storage
    original_cloud_path = None  # Track the original cloud storage path

    # Check if this is a cloud storage file that needs to be downloaded
    if not os.path.exists(file_path):
        logger.info(f"File path '{file_path}' doesn't exist locally - attempting cloud storage download...")

        try:
            # First, check if attachment has a cached local file path from a previous download
            from core.models.models_per_tenant import ExpenseAttachment
            attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()

            if not attachment:
                logger.error(f"Attachment {attachment_id} not found in database for expense {expense_id}")
                raise Exception(f"Attachment {attachment_id} not found")

            cached_local_path = None
            if hasattr(attachment, 'local_cache_path') and attachment.local_cache_path:
                cached_local_path = attachment.local_cache_path
                if os.path.exists(cached_local_path) and os.path.getsize(cached_local_path) > 0:
                    logger.info(f"Using cached local file from previous download: {cached_local_path}")
                    file_path = cached_local_path
                    is_temp_file = True
                else:
                    logger.warning(f"Cached local path exists but file is missing or empty: {cached_local_path}")
                    # Clear the invalid cache
                    attachment.local_cache_path = None
                    db.commit()

            # If no valid cache, download from cloud storage
            if not is_temp_file:
                # Use the cloud storage service to retrieve the file
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config

                    # Initialize cloud storage service
                    cloud_config = get_cloud_storage_config()
                    cloud_storage_service = CloudStorageService(db, cloud_config)

                    # Try to retrieve the file using the stored file_path as the key
                    retrieve_result = await cloud_storage_service.retrieve_file(
                        file_key=file_path,
                        tenant_id=str(tenant_id),
                        user_id=1,  # System user for OCR processing
                        generate_url=False  # We want the actual file content
                    )
                except ImportError:
                    logger.warning("Commercial CloudStorageService not found, cannot download cloud file")
                    raise Exception("Cloud storage service not available")

                from core.models.database import get_tenant_context
                import tempfile

                if retrieve_result.success and retrieve_result.file_content:
                    # Create temporary file with the downloaded content
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{attachment_id}_{os.path.basename(file_path)}") as temp_file:
                        temp_file.write(retrieve_result.file_content)
                        temp_path = temp_file.name

                    # Verify the file was created
                    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                        raise Exception(f"Failed to create temporary file or empty content: {temp_path}")

                    # Store the original cloud path and update file_path to use the temporary file
                    original_cloud_path = file_path
                    file_path = temp_path
                    is_temp_file = True

                    # Cache the local path in the attachment record to avoid re-downloading on retry
                    try:
                        attachment.local_cache_path = temp_path
                        db.commit()
                        logger.info(f"Cached local file path for attachment {attachment_id}: {temp_path}")
                    except Exception as cache_error:
                        logger.warning(f"Failed to cache local file path for attachment {attachment_id}: {cache_error}")
                        db.rollback()

                    logger.info(f"Successfully downloaded cloud file from '{original_cloud_path}' to '{file_path}' for OCR processing")
                else:
                    raise Exception(f"Failed to retrieve file from cloud storage: {retrieve_result.error_message}")

        except Exception as e:
            logger.error(f"Failed to download cloud storage file {file_path}: {e}")
            # Update expense status to failed
            try:
                from core.models.models_per_tenant import Expense
                expense = db.query(Expense).filter(Expense.id == expense_id).first()
                if expense:
                    expense.analysis_status = "failed"
                    expense.analysis_error = f"Failed to access attachment file: {str(e)}"
                    db.commit()
                logger.error(f"OCR failed - could not download cloud file for expense {expense_id}: {e}")
            except Exception as db_error:
                logger.error(f"Failed to update expense status after cloud download error: {db_error}")
            return
    else:
        logger.info(f"Using local file path: {file_path}")
    from core.models.models_per_tenant import Expense, ExpenseAttachment, AIConfig as AIConfigModel  # local import to avoid circulars
    from core.models.database import set_tenant_context  # Import tenant context management

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        logger.warning(f"Expense {expense_id} not found, skipping OCR")
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden; skipping OCR.")
        return

    # Set tenant context for encryption - determine tenant from database connection
    try:
        # In this multi-tenant setup, the tenant_id is determined by which database we're connected to
        # Since we're connected to tenant_1 database, the tenant_id is 1
        # We can infer this from the database connection or use a more robust method

        # Check if expense has direct tenant_id (if the model supports it)
        if hasattr(expense, 'tenant_id') and expense.tenant_id:
            tenant_id = expense.tenant_id
        else:
            # Since we're already connected to the tenant database, we know the tenant_id
            # In this case, we're connected to tenant_1, so tenant_id = 1
            # This avoids the circular dependency of accessing user data
            tenant_id = 1  # This should be determined from the database connection context

        logger.info(f"Setting tenant context to {tenant_id} for expense {expense_id} OCR processing")
        set_tenant_context(tenant_id)
    except Exception as e:
        logger.error(f"Failed to set tenant context for expense {expense_id}: {e}")
        # Set a default tenant context to prevent encryption errors
        set_tenant_context(1)
        logger.warning(f"Using default tenant context (1) for expense {expense_id}")
    try:
        expense.analysis_status = "processing"
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update expense {expense_id} status to processing: {e}")
        db.rollback()
        return

    # Fetch AI config from database (same pattern as bank statement service)
    # If ai_config is passed (e.g. from consumer), use it directly instead of DB lookup
    if not ai_config:
        try:
            # First try to find an AI config with OCR enabled
            ai_row = db.query(AIConfigModel).filter(
                AIConfigModel.is_active == True,
                AIConfigModel.tested == True,
                AIConfigModel.ocr_enabled == True
            ).order_by(AIConfigModel.is_default.desc()).first()

            if ai_row:
                ai_config = {
                    "provider_name": ai_row.provider_name,
                    "provider_url": ai_row.provider_url,
                    "api_key": ai_row.api_key,
                    "model_name": ai_row.model_name,
                    "ocr_enabled": ai_row.ocr_enabled,
                }
                logger.info(f"Using OCR-enabled AI config from database: provider={ai_row.provider_name}, model={ai_row.model_name}")
            else:
                # If no OCR-enabled config found, check if any active config exists and log the issue
                any_active_config = db.query(AIConfigModel).filter(
                    AIConfigModel.is_active == True,
                    AIConfigModel.tested == True
                ).first()
                if any_active_config:
                    logger.warning(f"No OCR-enabled AI config found. Active config exists for {any_active_config.provider_name} but OCR is not enabled. Falling back to environment variables.")
                else:
                    logger.info("No active AI config found in database, falling back to environment variables")

                # Fallback to environment variables
                ai_config = _get_ai_config_from_env()
                if ai_config:
                    logger.info(f"Using AI config from environment variables: provider={ai_config.get('provider_name')}, model={ai_config.get('model_name')}")
                else:
                    logger.warning("No AI configuration available from database or environment variables")
        except Exception as e:
            logger.warning(f"Failed to fetch AI config from database: {e}, falling back to environment variables")
            # Don't log full stack trace for encryption errors to avoid leaking sensitive data
            if "decryption" not in str(e).lower() and "encryption" not in str(e).lower():
                logger.debug(f"AI config fetch error details: {str(e)}", exc_info=True)
            else:
                logger.debug("AI config fetch failed due to encryption/decryption error (details not logged for security)")

            # Fallback to environment variables
            ai_config = _get_ai_config_from_env()
        if ai_config:
            logger.info(f"Using AI config from environment variables: provider={ai_config.get('provider_name')}, model={ai_config.get('model_name')}")
        else:
            logger.warning("No AI configuration available from database or environment variables")

    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")

    # Use UnifiedOCRService for expense processing
    result = None
    ai_extraction_attempted = False

    try:
        from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig

        # Use AI config from database or fallback to environment variables
        effective_ai_config = ai_config or _get_ai_config_from_env()

        # Configure OCR service
        ocr_config = OCRConfig(
            ai_config=effective_ai_config,
            enable_ai_vision=True,
            enable_fallback_parsing=True,
            timeout_seconds=300,
            max_retries=3
        )

        ocr_service = UnifiedOCRService(ocr_config)

        # Extract structured data from expense receipt
        ocr_result = await ocr_service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT, db_session=db)

        if ocr_result.success:
            result = ocr_result.structured_data or {}
            ai_extraction_attempted = True
            time_str = f"{ocr_result.processing_time:.2f}s" if ocr_result.processing_time is not None else "N/A"
            logger.info(f"✅ Unified OCR extraction successful: {len(result)} fields extracted in {time_str} using {ocr_result.method.value}")
        else:
            logger.error(f"❌ Unified OCR extraction failed: {ocr_result.error_message}")
            # Fallback to legacy OCR for backward compatibility
            logger.info("Falling back to legacy OCR processing...")
            result = await _run_ocr(file_path, ai_config=effective_ai_config, db_session=db)
            ai_extraction_attempted = True

    except ImportError as e:
        logger.warning(f"UnifiedOCRService not available, using legacy OCR: {e}")
        result = await _run_ocr(file_path, ai_config=effective_ai_config, db_session=db)
        ai_extraction_attempted = True
    except Exception as e:
        logger.error(f"UnifiedOCRService failed, using legacy OCR: {e}")
        result = await _run_ocr(file_path, ai_config=effective_ai_config, db_session=db)
        ai_extraction_attempted = True

    # Track AI usage if ai_config was used and OCR was actually attempted
    if ai_config and result and not result.get("provider_not_supported"):
        # Mask sensitive info in logs
        safe_config = ai_config.copy()
        if 'api_key' in safe_config:
            safe_config['api_key'] = '***masked***'
        logger.info(f"🔍 About to track AI usage for config: {safe_config}")
        # Calculate processing metadata
        text_length = len(result.get("raw", "")) if isinstance(result, dict) and "raw" in result else 0
        if isinstance(result, dict):
            # Count total characters in all string values
            text_length = sum(len(str(v)) for v in result.values() if isinstance(v, str))

        # Track OCR-specific usage with metadata
        track_ocr_usage(
            db=db,
            ai_config=ai_config,
            extraction_method="ocr",
            text_length=text_length
        )
        logger.info("✅ OCR AI usage tracking completed")
    elif result and result.get("provider_not_supported"):
        logger.info(f"⚠️ Skipping AI usage tracking - OCR not supported for provider: {ai_config.get('provider_name') if ai_config else 'unknown'}")
    elif result and result.get("ocr_not_enabled"):
        logger.info(f"⚠️ Skipping AI usage tracking - OCR not enabled for provider: {ai_config.get('provider_name') if ai_config else 'unknown'}")

    # Update DB with result if still not overridden
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        logger.warning(f"Expense {expense_id} not found when updating OCR result")
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden during OCR; not applying result.")
        return
    try:
        expense.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
        logger.info(f"Updating expense {expense_id} with OCR result. Error present: {'error' in result if isinstance(result, dict) else False}")
        if isinstance(result, dict) and "error" in result:
            # Persist error payload as a dict
            try:
                error_msg = str(result.get("error", "unknown"))
                # Ensure error message is safe to store and encrypt
                if len(error_msg) > 1000:  # Truncate very long error messages
                    error_msg = error_msg[:1000] + "... (truncated)"
                expense.analysis_result = {
                    "error": error_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "failed"
                }
                logger.info(f"Stored error analysis_result for expense {expense_id}")
            except Exception as store_error:
                logger.error(f"Failed to store error analysis_result for expense {expense_id}: {store_error}")
                expense.analysis_result = {
                    "error": "Failed to store error details",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            expense.analysis_status = "failed"
            expense.analysis_error = str(result.get("error"))

            # Clear any previous successful analysis data to avoid confusion
            # For amount (not nullable), set to 0 instead of None
            if expense.amount not in (None, 0):
                expense.amount = 0
            expense.total_amount = expense.total_amount if expense.total_amount not in (None, 0) else None
            expense.currency = expense.currency if expense.currency else None
            expense.expense_date = expense.expense_date if expense.expense_date else None
            expense.category = expense.category if expense.category else None
            expense.notes = expense.notes if expense.notes else None

            # Update attachment result if present
            if attachment_id:
                attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()
                if attachment:
                    attachment.analysis_status = "failed"
                    attachment.analysis_error = str(result.get("error"))
                    attachment.analysis_result = {
                        "error": str(result.get("error")),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    db.commit()

            # Ensure NOT NULL fields have valid values
            if expense.amount is None:
                expense.amount = 0
            if expense.currency is None:
                expense.currency = "USD"
            if expense.expense_date is None:
                expense.expense_date = datetime.now(timezone.utc)
            if expense.category is None:
                expense.category = "General"
            if expense.status is None:
                expense.status = "recorded"
        else:
            # Success! Mark as done so consumer knows to commit.
            await apply_ocr_extraction_to_expense(
                db=db,
                expense=expense,
                extracted=result,
                attachment_id=attachment_id,
                ai_extraction_attempted=ai_extraction_attempted,
                file_path=file_path,
                ai_config=ai_config
            )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed updating OCR result for expense {expense_id}: {e}")
        # CRITICAL FIX: Ensure expense status is reset if update failed
        try:
            expense.analysis_status = "failed"
            expense.analysis_error = f"Database update failed: {str(e)}"
            db.commit()
            logger.info(f"Reset expense {expense_id} status to failed after update error")
        except Exception as reset_error:
            logger.error(f"Failed to reset expense {expense_id} status: {reset_error}")
            db.rollback()

    # Clean up temporary files if we downloaded from cloud storage
    if is_temp_file and os.path.exists(file_path):
        try:
            logger.info(f"Cleaning up temporary file: {file_path}")
            os.remove(file_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary file {file_path}: {cleanup_error}")

    # Release processing lock for expense
    try:
        release_processing_lock("expense", expense_id)
    except Exception as lock_error:
        logger.warning(f"Failed to release processing lock for expense {expense_id}: {lock_error}")


def queue_or_process_attachment(db: Session, tenant_id: Optional[int], expense_id: int, attachment_id: int, file_path: str) -> None:
    """Publish OCR job to Kafka if available, otherwise process inline in background."""
    from core.models.database import set_tenant_context  # Import tenant context management

    # Ensure tenant context is set for the current operation
    if tenant_id:
        logger.info(f"Setting tenant context to {tenant_id} for OCR processing")
        set_tenant_context(tenant_id)
    else:
        logger.warning(f"No tenant_id provided for OCR processing of expense {expense_id}, using default")
        set_tenant_context(1)  # Default fallback

    message = {
        "tenant_id": tenant_id,
        "expense_id": expense_id,
        "attachment_id": attachment_id,
        "file_path": file_path,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"Queue/process OCR: tenant_id={tenant_id} expense_id={expense_id} attachment_id={attachment_id} path={file_path}")
    published = publish_ocr_task(message)
    if not published:
        try:
            # Inline background processing
            asyncio.get_event_loop().create_task(process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id))
        except RuntimeError:
            # If no running loop (sync context), schedule with new loop via thread
            asyncio.run(process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id))


def acquire_processing_lock(resource_type: str, resource_id: int, timeout_minutes: int = 30) -> bool:
    """Acquire processing lock for a resource. Returns True if lock was acquired, False if already locked."""
    try:
        from core.models.processing_lock import ProcessingLock
        from core.models.database import get_db

        db_gen = get_db()
        try:
            session = next(db_gen)
            acquired = ProcessingLock.acquire_lock(session, resource_type, resource_id, lock_duration_minutes=timeout_minutes)
            if acquired:
                session.commit()
                logger.info(f"Acquired processing lock for {resource_type} {resource_id}")
            return acquired
        except StopIteration:
            logger.error(f"Failed to get database session for lock acquisition")
            return False
        except Exception as e:
            logger.error(f"Failed to acquire processing lock for {resource_type} {resource_id}: {e}")
            return False
        finally:
            try:
                # Trigger generator cleanup (finally block in get_db)
                db_gen.close()
            except:
                pass
    except Exception as e:
        logger.error(f"Error in acquire_processing_lock for {resource_type} {resource_id}: {e}")
        return False

def release_processing_lock(resource_type: str, resource_id: int) -> bool:
    """Release processing lock for a resource after OCR processing completion."""
    try:
        from core.models.processing_lock import ProcessingLock
        from core.models.database import get_db

        db_gen = get_db()
        try:
            session = next(db_gen)
            released = ProcessingLock.release_lock(session, resource_type, resource_id)
            if released:
                session.commit()
                logger.info(f"Released processing lock for {resource_type} {resource_id}")
            return released
        except StopIteration:
            logger.error(f"Failed to get database session for lock release")
            return False
        except Exception as e:
            logger.error(f"Failed to release processing lock for {resource_type} {resource_id}: {e}")
            return False
        finally:
            try:
                db_gen.close()
            except:
                pass
    except Exception as e:
        logger.error(f"Error in release_processing_lock for {resource_type} {resource_id}: {e}")
        return False


def cleanup_expired_processing_locks() -> int:
    """Clean up expired processing locks. Returns number of locks cleaned up."""
    try:
        from core.models.processing_lock import ProcessingLock
        from core.models.database import get_db

        # Get a new database session for cleanup
        db = get_db()
        try:
            with next(db) as session:
                cleaned_count = ProcessingLock.cleanup_expired_locks(session)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired processing locks")
                return cleaned_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired processing locks: {e}")
            return 0
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in cleanup_expired_processing_locks: {e}")
        return 0
