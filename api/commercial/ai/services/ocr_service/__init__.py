"""OCR service package.

Split from the original monolithic ocr_service.py into focused modules:
  - _shared: logger, parse_number, first_key, _get_ai_config_from_env
  - text_parsers: markdown/CSV/JSON/heuristic parsers, timestamp validation
  - image_processing: _run_ocr, PDF conversion, AI retry logic
  - expense_extraction: apply_ocr_extraction_to_expense, process_attachment_inline, queue_or_process_attachment
  - kafka_publisher: all Kafka producer and publish functions
  - usage_tracking: track_ai_usage, track_ocr_usage, get_ai_usage_stats
  - setup: OCR initialization, validation, processing locks

All public symbols are re-exported here for backward compatibility.
"""

from ._shared import (
    first_key,
    logger,
    parse_number,
    _get_ai_config_from_env,
)

from .text_parsers import (
    _extract_json_from_text,
    _heuristic_parse_text,
    _looks_like_base64_encrypted,
    _parse_csv_like_response,
    _parse_markdown_formatted_response,
    _validate_timestamp,
)

from .image_processing import (
    _convert_raw_ocr_to_json,
    _pdf_pages_to_png_bytes,
    _retry_ocr_with_ai,
    _run_ocr,
)

from .expense_extraction import (
    apply_ocr_extraction_to_expense,
    process_attachment_inline,
    queue_or_process_attachment,
)

from .kafka_publisher import (
    _get_kafka_producer,
    _get_kafka_producer_for,
    _PRODUCER_CACHE,
    flush_all_producers,
    publish_bank_statement_task,
    publish_fraud_audit_task,
    publish_invoice_result,
    publish_invoice_task,
    publish_ocr_result,
    publish_ocr_task,
)

from .usage_tracking import (
    get_ai_usage_stats,
    publish_ocr_usage_metrics,
    track_ai_usage,
    track_ocr_usage,
)

from .setup import (
    acquire_processing_lock,
    cancel_ocr_tasks_for_expense,
    cleanup_expired_processing_locks,
    initialize_ocr_dependencies,
    release_processing_lock,
    validate_ocr_setup,
)

__all__ = [
    # _shared
    "first_key",
    "logger",
    "parse_number",
    "_get_ai_config_from_env",
    # text_parsers
    "_extract_json_from_text",
    "_heuristic_parse_text",
    "_looks_like_base64_encrypted",
    "_parse_csv_like_response",
    "_parse_markdown_formatted_response",
    "_validate_timestamp",
    # image_processing
    "_convert_raw_ocr_to_json",
    "_pdf_pages_to_png_bytes",
    "_retry_ocr_with_ai",
    "_run_ocr",
    # expense_extraction
    "apply_ocr_extraction_to_expense",
    "process_attachment_inline",
    "queue_or_process_attachment",
    # kafka_publisher
    "_get_kafka_producer",
    "_get_kafka_producer_for",
    "_PRODUCER_CACHE",
    "flush_all_producers",
    "publish_bank_statement_task",
    "publish_fraud_audit_task",
    "publish_invoice_result",
    "publish_invoice_task",
    "publish_ocr_result",
    "publish_ocr_task",
    # usage_tracking
    "get_ai_usage_stats",
    "publish_ocr_usage_metrics",
    "track_ai_usage",
    "track_ocr_usage",
    # setup
    "acquire_processing_lock",
    "cancel_ocr_tasks_for_expense",
    "cleanup_expired_processing_locks",
    "initialize_ocr_dependencies",
    "release_processing_lock",
    "validate_ocr_setup",
]
