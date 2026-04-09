"""Expense-specific OCR application: field mapping, inline processing, and queue routing."""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.utils.currency import CURRENCY_SYMBOL_MAP
from core.utils.timezone import get_tenant_timezone_aware_datetime

from ._shared import _get_ai_config_from_env, first_key, logger, parse_number
from .image_processing import _retry_ocr_with_ai, _run_ocr
from .kafka_publisher import publish_ocr_task
from .setup import release_processing_lock
from .text_parsers import (
    _extract_json_from_text,
    _heuristic_parse_text,
    _looks_like_base64_encrypted,
    _parse_csv_like_response,
    _parse_markdown_formatted_response,
    _validate_timestamp,
)
from .usage_tracking import track_ocr_usage


async def apply_ocr_extraction_to_expense(
    db: Session,
    expense: Any,
    extracted: Dict[str, Any],
    attachment_id: Optional[int] = None,
    ai_extraction_attempted: bool = False,
    file_path: Optional[str] = None,
    ai_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Apply extracted OCR data to an Expense record with robust mapping and normalization.
    This logic is shared between standard reprocessing and batch uploads.
    """
    from core.models.models_per_tenant import ExpenseAttachment

    expense_id = expense.id
    logger.info(f"Applying OCR extraction to expense {expense_id}. Attachment: {attachment_id}")

    extracted = extracted if isinstance(extracted, dict) else {}
    logger.info(
        f"OCR extracted keys: {list(extracted.keys()) if isinstance(extracted, dict) else 'non-dict result'}"
    )

    if isinstance(extracted, dict):
        logger.info(f"OCR extracted data: {json.dumps(extracted, indent=2, default=str)}")

        vendor_value = extracted.get("vendor", "")
        if isinstance(vendor_value, str) and vendor_value.count(",") >= 3:
            logger.warning(f"Detected CSV-like data in vendor field: {vendor_value[:100]}...")
            csv_parsed = _parse_csv_like_response(vendor_value)
            if csv_parsed:
                logger.info("Successfully parsed CSV-like response, replacing extracted data")
                extracted = csv_parsed

    if set(extracted.keys()) == {"raw"} and isinstance(extracted.get("raw"), str):
        extracted_text = extracted["raw"]
        if any(
            err in extracted_text
            for err in [
                "Error processing image",
                "HTTPConnectionPool",
                "Failed to establish a new connection",
                "Connection refused",
            ]
        ):
            expense.analysis_status = "failed"
            expense.analysis_error = extracted_text[:500]
            db.commit()
            logger.error(f"OCR transport error for expense {expense.id}: {expense.analysis_error}")
            return

        parsed_data = None
        parsing_method = None

        parsed_data = _extract_json_from_text(extracted_text)
        if parsed_data and isinstance(parsed_data, dict) and len(parsed_data) > 1:
            parsing_method = "json"
            extracted.update(parsed_data)
            logger.info(f"Parsed embedded JSON keys: {list(parsed_data.keys())}")

        if not parsing_method:
            parsed_data = _parse_markdown_formatted_response(extracted_text)
            if parsed_data and len(parsed_data) > 0:
                parsing_method = "markdown"
                extracted.update(parsed_data)
                logger.info(f"Parsed markdown response keys: {list(parsed_data.keys())}")

        if not parsing_method:
            parsed_data = _heuristic_parse_text(extracted_text)
            if parsed_data:
                parsing_method = "heuristic"
                extracted.update(parsed_data)
                logger.info(f"Heuristic parse extracted keys: {list(parsed_data.keys())}")

                if "receipt_timestamp" in parsed_data:
                    timestamp_str = parsed_data["receipt_timestamp"]
                    try:
                        from dateutil import parser as dateparser

                        parsed_dt = dateparser.parse(str(timestamp_str))
                        now = datetime.now(timezone.utc)
                        year_diff = abs(parsed_dt.year - now.year)

                        if year_diff > 5:
                            logger.warning(
                                f"Heuristic timestamp seems unreasonable: {timestamp_str} "
                                f"(parsed as {parsed_dt})"
                            )

                            if not ai_extraction_attempted:
                                ai_result = await _retry_ocr_with_ai(
                                    file_path, ai_config, db, "questionable timestamp"
                                )

                                if (
                                    ai_result
                                    and isinstance(ai_result, dict)
                                    and "receipt_timestamp" in ai_result
                                ):
                                    ai_timestamp = ai_result["receipt_timestamp"]
                                    try:
                                        ai_parsed_dt = dateparser.parse(str(ai_timestamp))
                                        ai_year_diff = abs(ai_parsed_dt.year - now.year)
                                        if ai_year_diff <= 5:
                                            logger.info(f"✅ AI LLM provided better timestamp: {ai_timestamp}")
                                            extracted.update(ai_result)
                                        else:
                                            logger.warning(
                                                f"❌ AI LLM timestamp also questionable: {ai_timestamp}"
                                            )
                                    except Exception:
                                        logger.warning("❌ AI LLM timestamp parsing failed")
                                else:
                                    logger.warning("❌ AI LLM retry did not provide timestamp")
                    except Exception as e:
                        logger.warning(f"Failed to validate heuristic timestamp '{timestamp_str}': {e}")
            else:
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

    extracted_amount = parse_number(
        first_key(extracted, ["total_amount", "total", "amount", "grand_total", "subtotal"])
    )

    cur = first_key(extracted, ["currency", "currency_code", "iso_currency", "total_currency"]) or None
    if isinstance(cur, str) and len(cur) <= 5:
        cur_upper = cur.upper().strip()
        if cur in CURRENCY_SYMBOL_MAP:
            expense.currency = CURRENCY_SYMBOL_MAP[cur]
        elif len(cur_upper) == 3 and cur_upper.isalpha():
            expense.currency = cur_upper
        else:
            expense.currency = "USD"
    elif not expense.currency:
        expense.currency = "USD"

    date_str = first_key(extracted, ["expense_date", "date", "transaction_date", "purchase_date"]) or None
    if date_str:
        try:
            from dateutil import parser as dateparser  # type: ignore

            parsed_dt = dateparser.parse(str(date_str))
            if parsed_dt:
                expense.expense_date = parsed_dt
        except Exception:
            logger.warning(f"Failed to parse expense_date '{date_str}' from OCR result", exc_info=True)

    timestamp_str = (
        first_key(extracted, ["receipt_timestamp", "timestamp", "transaction_time", "receipt_time"]) or None
    )
    if timestamp_str:
        try:
            if not _validate_timestamp(str(timestamp_str)):
                logger.warning(f"Timestamp validation failed for '{timestamp_str}', skipping")
                expense.receipt_time_extracted = False
            else:
                from dateutil import parser as dateparser  # type: ignore

                parsed_timestamp = dateparser.parse(str(timestamp_str))
                if parsed_timestamp:
                    expense.receipt_timestamp = parsed_timestamp
                    expense.receipt_time_extracted = True
                    logger.info(
                        f"Extracted receipt timestamp: {parsed_timestamp} for expense {expense.id}"
                    )
                else:
                    expense.receipt_time_extracted = False
        except Exception as e:
            logger.warning(f"Failed to parse receipt timestamp '{timestamp_str}': {e}")
            expense.receipt_time_extracted = False
    else:
        expense.receipt_time_extracted = False

    cat = first_key(extracted, ["category", "expense_category"]) or None
    if cat:
        category_str = str(cat).strip()
        if category_str and not _looks_like_base64_encrypted(category_str):
            expense.category = category_str
        else:
            logger.warning("Invalid category data detected, using default")
            expense.category = "General"
    elif not expense.category:
        expense.category = "General"

    vend = first_key(extracted, ["vendor", "merchant", "seller", "store", "payee"]) or None
    if vend:
        vendor_str = str(vend).strip()
        if vendor_str and not _looks_like_base64_encrypted(vendor_str):
            expense.vendor = vendor_str
        else:
            logger.warning("Invalid vendor data detected, using default")
            expense.vendor = "Unknown Vendor"
    elif not expense.vendor:
        expense.vendor = "Unknown Vendor"

    tr = parse_number(first_key(extracted, ["tax_rate", "vat_rate"]))
    ta = parse_number(first_key(extracted, ["tax_amount", "vat_amount"]))
    tt = parse_number(first_key(extracted, ["total_amount", "total"]))

    expense.tax_rate = tr if tr is not None else expense.tax_rate
    expense.tax_amount = ta if ta is not None else expense.tax_amount

    final_attachment_amount = tt if tt is not None else extracted_amount
    if final_attachment_amount is not None:
        final_attachment_amount = round(final_attachment_amount, 4)

    if attachment_id:
        attachment = (
            db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()
        )
        if attachment:
            attachment.analysis_status = "done"
            attachment.extracted_amount = final_attachment_amount
            attachment.analysis_result = extracted
            attachment.analysis_error = None
            db.commit()
            logger.info(
                f"Updated attachment {attachment_id} with extracted amount {final_attachment_amount}"
            )

    all_attachments = (
        db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()
    )

    total_sum = 0
    any_success = False
    for att in all_attachments:
        if att.analysis_status == "done" and att.extracted_amount is not None:
            total_sum += att.extracted_amount
            any_success = True

    if any_success:
        total_sum = round(total_sum, 4)
        logger.info(
            f"Expense {expense.id}: Aggregated total amount from {len(all_attachments)} attachments: {total_sum}"
        )
        expense.amount = total_sum
        expense.total_amount = total_sum
    else:
        if tt is not None:
            tt = round(tt, 4)
            expense.amount = tt
            expense.total_amount = tt
        elif extracted_amount is not None:
            extracted_amount = round(extracted_amount, 4)
            expense.amount = extracted_amount
            if getattr(expense, "total_amount", None) in (None, 0):
                expense.total_amount = extracted_amount

    pm = first_key(extracted, ["payment_method", "payment", "method"]) or None
    if pm:
        payment_str = str(pm).strip()
        if payment_str and not _looks_like_base64_encrypted(payment_str):
            expense.payment_method = payment_str
        else:
            logger.warning("Invalid payment method data detected, skipping")

    ref = (
        first_key(
            extracted, ["reference_number", "reference", "ref", "receipt_number", "invoice_number"]
        )
        or None
    )
    if ref:
        ref_str = str(ref).strip()
        if ref_str and not _looks_like_base64_encrypted(ref_str):
            expense.reference_number = ref_str
        else:
            logger.warning("Invalid reference number data detected, skipping")

    notes = first_key(extracted, ["notes", "memo"]) or None
    if notes:
        notes_str = str(notes).strip()
        if notes_str and not _looks_like_base64_encrypted(notes_str):
            expense.notes = notes_str
        else:
            logger.warning("Invalid notes data detected, skipping")
            expense.notes = None

    try:
        if isinstance(extracted, dict):
            sanitized_data = {}
            for key, value in extracted.items():
                try:
                    json.dumps(value)
                    if isinstance(value, str) and not _looks_like_base64_encrypted(value):
                        sanitized_data[key] = value
                    elif not isinstance(value, str):
                        sanitized_data[key] = value
                    else:
                        logger.warning(f"Skipping potentially corrupted field {key} in analysis_result")
                except (TypeError, ValueError) as ve:
                    logger.warning(f"Skipping non-serializable field {key} in analysis_result: {ve}")

            if sanitized_data:
                sanitized_data["extraction_metadata"] = {
                    "ai_extraction_attempted": ai_extraction_attempted,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            expense.analysis_result = (
                sanitized_data
                if sanitized_data
                else {
                    "status": "extracted",
                    "extraction_metadata": {"ai_extraction_attempted": ai_extraction_attempted},
                }
            )
            logger.info(
                f"Stored sanitized analysis_result with keys: "
                f"{list(sanitized_data.keys()) if sanitized_data else ['status']}"
            )
        else:
            expense.analysis_result = {"items": extracted} if extracted else {"status": "no_data"}

    except Exception as e:
        logger.error(f"Failed to set analysis_result for expense {expense.id}: {e}")
        expense.analysis_result = {
            "error": "Failed to store result",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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


async def process_attachment_inline(
    db: Session,
    expense_id: int,
    attachment_id: int,
    file_path: str,
    tenant_id: int,
    ai_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Fallback inline processing when Kafka is not configured."""
    logger.info(
        f"Processing attachment inline: expense_id={expense_id} "
        f"attachment_id={attachment_id} file={file_path}"
    )
    is_temp_file = False
    original_cloud_path = None

    if not os.path.exists(file_path):
        logger.info(f"File path '{file_path}' doesn't exist locally - attempting cloud storage download...")

        try:
            from core.models.models_per_tenant import ExpenseAttachment

            attachment = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id).first()

            if not attachment:
                logger.error(
                    f"Attachment {attachment_id} not found in database for expense {expense_id}"
                )
                raise Exception(f"Attachment {attachment_id} not found")

            cached_local_path = None
            if hasattr(attachment, "local_cache_path") and attachment.local_cache_path:
                cached_local_path = attachment.local_cache_path
                if os.path.exists(cached_local_path) and os.path.getsize(cached_local_path) > 0:
                    logger.info(f"Using cached local file from previous download: {cached_local_path}")
                    file_path = cached_local_path
                    is_temp_file = True
                else:
                    logger.warning(
                        f"Cached local path exists but file is missing or empty: {cached_local_path}"
                    )
                    attachment.local_cache_path = None
                    db.commit()

            if not is_temp_file:
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config

                    cloud_config = get_cloud_storage_config()
                    cloud_storage_service = CloudStorageService(db, cloud_config)

                    retrieve_result = await cloud_storage_service.retrieve_file(
                        file_key=file_path,
                        tenant_id=str(tenant_id),
                        user_id=1,
                        generate_url=False,
                    )
                except ImportError:
                    logger.warning(
                        "Commercial CloudStorageService not found, cannot download cloud file"
                    )
                    raise Exception("Cloud storage service not available")

                import tempfile

                if retrieve_result.success and retrieve_result.file_content:
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=f"_{attachment_id}_{os.path.basename(file_path)}",
                    ) as temp_file:
                        temp_file.write(retrieve_result.file_content)
                        temp_path = temp_file.name

                    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                        raise Exception(
                            f"Failed to create temporary file or empty content: {temp_path}"
                        )

                    original_cloud_path = file_path
                    file_path = temp_path
                    is_temp_file = True

                    try:
                        attachment.local_cache_path = temp_path
                        db.commit()
                        logger.info(
                            f"Cached local file path for attachment {attachment_id}: {temp_path}"
                        )
                    except Exception as cache_error:
                        logger.warning(
                            f"Failed to cache local file path for attachment {attachment_id}: {cache_error}"
                        )
                        db.rollback()

                    logger.info(
                        f"Successfully downloaded cloud file from '{original_cloud_path}' "
                        f"to '{file_path}' for OCR processing"
                    )
                else:
                    raise Exception(
                        f"Failed to retrieve file from cloud storage: {retrieve_result.error_message}"
                    )

        except Exception as e:
            logger.error(f"Failed to download cloud storage file {file_path}: {e}")
            try:
                from core.models.models_per_tenant import Expense

                expense = db.query(Expense).filter(Expense.id == expense_id).first()
                if expense:
                    expense.analysis_status = "failed"
                    expense.analysis_error = f"Failed to access attachment file: {str(e)}"
                    db.commit()
                logger.error(
                    f"OCR failed - could not download cloud file for expense {expense_id}: {e}"
                )
            except Exception as db_error:
                logger.error(
                    f"Failed to update expense status after cloud download error: {db_error}"
                )
            return
    else:
        logger.info(f"Using local file path: {file_path}")

    from core.models.models_per_tenant import Expense, ExpenseAttachment, AIConfig as AIConfigModel
    from core.models.database import set_tenant_context

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        logger.warning(f"Expense {expense_id} not found, skipping OCR")
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden; skipping OCR.")
        return

    try:
        effective_tenant_id = (
            expense.tenant_id
            if hasattr(expense, "tenant_id") and expense.tenant_id
            else tenant_id
        )
        logger.info(
            f"Setting tenant context to {effective_tenant_id} for expense {expense_id} OCR processing"
        )
        set_tenant_context(effective_tenant_id)
    except Exception as e:
        logger.error(f"Failed to set tenant context for expense {expense_id}: {e}")
        set_tenant_context(tenant_id)
        logger.warning(f"Using passed tenant context ({tenant_id}) for expense {expense_id}")

    try:
        expense.analysis_status = "processing"
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update expense {expense_id} status to processing: {e}")
        db.rollback()
        return

    if not ai_config:
        try:
            ai_row = (
                db.query(AIConfigModel)
                .filter(
                    AIConfigModel.is_active == True,
                    AIConfigModel.ocr_enabled == True,
                )
                .order_by(AIConfigModel.is_default.desc())
                .first()
            )

            if ai_row:
                ai_config = {
                    "provider_name": ai_row.provider_name,
                    "provider_url": ai_row.provider_url,
                    "api_key": ai_row.api_key,
                    "model_name": ai_row.model_name,
                    "ocr_enabled": ai_row.ocr_enabled,
                }
                logger.info(
                    f"Using OCR-enabled AI config from database: "
                    f"provider={ai_row.provider_name}, model={ai_row.model_name}"
                )
            else:
                any_active_config = (
                    db.query(AIConfigModel).filter(AIConfigModel.is_active == True).first()
                )
                if any_active_config:
                    logger.warning(
                        f"No OCR-enabled AI config found. Active config exists for "
                        f"{any_active_config.provider_name} but OCR is not enabled. "
                        "Falling back to environment variables."
                    )
                else:
                    logger.info(
                        "No active AI config found in database, falling back to environment variables"
                    )

                ai_config = _get_ai_config_from_env()
                if ai_config:
                    logger.info(
                        f"Using AI config from environment variables: "
                        f"provider={ai_config.get('provider_name')}, model={ai_config.get('model_name')}"
                    )
                else:
                    logger.warning(
                        "No AI configuration available from database or environment variables"
                    )
        except Exception as e:
            logger.warning(
                f"Failed to fetch AI config from database: {e}, falling back to environment variables"
            )
            if "decryption" not in str(e).lower() and "encryption" not in str(e).lower():
                logger.debug(f"AI config fetch error details: {str(e)}", exc_info=True)
            else:
                logger.debug(
                    "AI config fetch failed due to encryption/decryption error "
                    "(details not logged for security)"
                )

            ai_config = _get_ai_config_from_env()

        if ai_config:
            logger.info(
                f"Using AI config from environment variables: "
                f"provider={ai_config.get('provider_name')}, model={ai_config.get('model_name')}"
            )
        else:
            logger.warning("No AI configuration available from database or environment variables")

    logger.info(
        f"Processing attachment inline: expense_id={expense_id} "
        f"attachment_id={attachment_id} file={file_path}"
    )

    result = None
    ai_extraction_attempted = False
    effective_ai_config = ai_config or _get_ai_config_from_env()

    try:
        from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig

        effective_ai_config = ai_config or _get_ai_config_from_env()

        ocr_config = OCRConfig(
            ai_config=effective_ai_config,
            enable_ai_vision=True,
            enable_fallback_parsing=True,
            timeout_seconds=300,
            max_retries=3,
        )

        ocr_service = UnifiedOCRService(ocr_config)
        ocr_result = await ocr_service.extract_structured_data(
            file_path, DocumentType.EXPENSE_RECEIPT, db_session=db
        )

        if ocr_result.success:
            result = ocr_result.structured_data or {}
            ai_extraction_attempted = True
            time_str = (
                f"{ocr_result.processing_time:.2f}s"
                if ocr_result.processing_time is not None
                else "N/A"
            )
            logger.info(
                f"✅ Unified OCR extraction successful: {len(result)} fields extracted "
                f"in {time_str} using {ocr_result.method.value}"
            )
        else:
            logger.error(f"❌ Unified OCR extraction failed: {ocr_result.error_message}")
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

    if ai_config and result and not result.get("provider_not_supported"):
        safe_config = ai_config.copy()
        if "api_key" in safe_config:
            safe_config["api_key"] = "***masked***"
        logger.info(f"🔍 About to track AI usage for config: {safe_config}")
        text_length = 0
        if isinstance(result, dict):
            text_length = sum(len(str(v)) for v in result.values() if isinstance(v, str))

        track_ocr_usage(
            db=db,
            ai_config=ai_config,
            extraction_method="ocr",
            text_length=text_length,
        )
        logger.info("✅ OCR AI usage tracking completed")
    elif result and result.get("provider_not_supported"):
        logger.info(
            f"⚠️ Skipping AI usage tracking - OCR not supported for provider: "
            f"{ai_config.get('provider_name') if ai_config else 'unknown'}"
        )
    elif result and result.get("ocr_not_enabled"):
        logger.info(
            f"⚠️ Skipping AI usage tracking - OCR not enabled for provider: "
            f"{ai_config.get('provider_name') if ai_config else 'unknown'}"
        )

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        logger.warning(f"Expense {expense_id} not found when updating OCR result")
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden during OCR; not applying result.")
        return

    try:
        expense.analysis_updated_at = get_tenant_timezone_aware_datetime(db)
        logger.info(
            f"Updating expense {expense_id} with OCR result. "
            f"Error present: {'error' in result if isinstance(result, dict) else False}"
        )
        if isinstance(result, dict) and "error" in result:
            try:
                error_msg = str(result.get("error", "unknown"))
                if len(error_msg) > 1000:
                    error_msg = error_msg[:1000] + "... (truncated)"
                expense.analysis_result = {
                    "error": error_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                }
                logger.info(f"Stored error analysis_result for expense {expense_id}")
            except Exception as store_error:
                logger.error(
                    f"Failed to store error analysis_result for expense {expense_id}: {store_error}"
                )
                expense.analysis_result = {
                    "error": "Failed to store error details",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            expense.analysis_status = "failed"
            expense.analysis_error = str(result.get("error"))

            if expense.amount not in (None, 0):
                expense.amount = 0
            expense.total_amount = (
                expense.total_amount if expense.total_amount not in (None, 0) else None
            )
            expense.currency = expense.currency if expense.currency else None
            expense.expense_date = expense.expense_date if expense.expense_date else None
            expense.category = expense.category if expense.category else None
            expense.notes = expense.notes if expense.notes else None

            if attachment_id:
                attachment = (
                    db.query(ExpenseAttachment)
                    .filter(ExpenseAttachment.id == attachment_id)
                    .first()
                )
                if attachment:
                    attachment.analysis_status = "failed"
                    attachment.analysis_error = str(result.get("error"))
                    attachment.analysis_result = {
                        "error": str(result.get("error")),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    db.commit()

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
            await apply_ocr_extraction_to_expense(
                db=db,
                expense=expense,
                extracted=result,
                attachment_id=attachment_id,
                ai_extraction_attempted=ai_extraction_attempted,
                file_path=file_path,
                ai_config=ai_config,
            )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed updating OCR result for expense {expense_id}: {e}")
        try:
            expense.analysis_status = "failed"
            expense.analysis_error = f"Database update failed: {str(e)}"
            db.commit()
            logger.info(f"Reset expense {expense_id} status to failed after update error")
        except Exception as reset_error:
            logger.error(f"Failed to reset expense {expense_id} status: {reset_error}")
            db.rollback()

    if is_temp_file and os.path.exists(file_path):
        try:
            logger.info(f"Cleaning up temporary file: {file_path}")
            os.remove(file_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary file {file_path}: {cleanup_error}")

    try:
        release_processing_lock("expense", expense_id)
    except Exception as lock_error:
        logger.warning(f"Failed to release processing lock for expense {expense_id}: {lock_error}")


def queue_or_process_attachment(
    db: Session,
    tenant_id: Optional[int],
    expense_id: int,
    attachment_id: int,
    file_path: str,
) -> None:
    """Publish OCR job to Kafka if available, otherwise process inline in background."""
    from core.models.database import set_tenant_context

    if tenant_id:
        logger.info(f"Setting tenant context to {tenant_id} for OCR processing")
        set_tenant_context(tenant_id)
    else:
        logger.warning(
            f"No tenant_id provided for OCR processing of expense {expense_id}, using default"
        )
        set_tenant_context(1)

    message = {
        "tenant_id": tenant_id,
        "expense_id": expense_id,
        "attachment_id": attachment_id,
        "file_path": file_path,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        f"Queue/process OCR: tenant_id={tenant_id} expense_id={expense_id} "
        f"attachment_id={attachment_id} path={file_path}"
    )
    published = publish_ocr_task(message)
    if not published:
        try:
            asyncio.get_running_loop().create_task(
                process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id)
            )
        except RuntimeError:
            asyncio.run(
                process_attachment_inline(db, expense_id, attachment_id, file_path, tenant_id)
            )
