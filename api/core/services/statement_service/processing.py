"""Main entry-point functions and legacy wrappers for bank statement processing."""
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests
from core.utils.file_validation import validate_file_path

from ._shared import BankLLMUnavailableError, _clean_and_deduplicate_transactions
from .csv_processing import _parse_csv_file_basic, _preprocess_bank_text
from .extraction import BankTransactionExtractor, UniversalBankTransactionExtractor

logger = logging.getLogger(__name__)


def process_bank_pdf_with_llm(
    pdf_path: str,
    ai_config: Optional[Dict[str, Any]] = None,
    db: Optional[Any] = None,
    card_type: str = "auto",
) -> List[Dict[str, Any]]:
    """Enhanced LLM-based extraction using BankTransactionExtractor from test-main.py

    Raises BankLLMUnavailableError if LLM is unavailable and fallback extraction yields no transactions,
    so callers can implement retries/backoff.
    """
    from commercial.ai.services.ocr_service import track_ai_usage, track_ocr_usage

    logger.info(f"Processing bank PDF: {pdf_path}")

    try:
        # Configure model based on ai_config or environment
        model_name = "gpt-oss:latest"
        base_url = "http://localhost:11434"

        if ai_config:
            provider_name = ai_config.get("provider_name", "ollama")
            model_name = ai_config.get("model_name", "gpt-oss:latest")
            logger.info(f"🔧 Using AI config from database: {provider_name} model={model_name}")

            # Use the new UniversalBankTransactionExtractor for all providers
            try:
                extractor = UniversalBankTransactionExtractor(
                    ai_config=ai_config,
                    db_session=db,
                    temperature=0.1,
                    chunk_size=6000,
                    chunk_overlap=150,
                    request_timeout=120,
                    card_type=card_type
                )
            except Exception as e:
                logger.warning(f"Failed to initialize UniversalBankTransactionExtractor: {e}")
                logger.info("Falling back to regex extraction")
                # Fallback to regex extraction
                try:
                    from pathlib import Path as _P
                    try:
                        safe_path = validate_file_path(pdf_path)
                    except ValueError as ve:
                        logger.error(str(ve))
                        return []
                    ext = _P(safe_path).suffix.lower()
                    if ext == ".csv":
                        return _parse_csv_file_basic(safe_path)
                    else:
                        raise BankLLMUnavailableError(f"LLM extraction failed for non-CSV file: {pdf_path}")
                except Exception as fallback_e:
                    logger.error(f"Fallback extraction failed: {fallback_e}")
                    raise BankLLMUnavailableError(f"LLM extraction failed and no transactions found: {fallback_e}")
        else:
            # Fallback to environment variables - create ai_config from env vars
            model_name = os.getenv("LLM_MODEL_BANK_STATEMENTS") or os.getenv("LLM_MODEL_EXPENSES") or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
            base_url = os.getenv("LLM_API_BASE", "http://localhost:11434")
            logger.info(f"⚠️ Using environment variables: model={model_name} base_url={base_url}")

            # Create ai_config from environment variables
            ai_config = {
                "provider_name": "ollama",
                "model_name": model_name,
                "provider_url": base_url,
                "api_key": None
            }

            try:
                extractor = UniversalBankTransactionExtractor(
                    ai_config=ai_config,
                    db_session=db,
                    temperature=0.1,
                    chunk_size=6000,
                    chunk_overlap=150,
                    request_timeout=120,
                    card_type=card_type
                )
            except Exception as e:
                logger.warning(f"Failed to initialize UniversalBankTransactionExtractor: {e}")
                # Fallback to simple PDF loading or CSV parsing
                try:
                    from pathlib import Path as _P
                    try:
                        safe_path = validate_file_path(pdf_path)
                    except ValueError as ve:
                        logger.error(str(ve))
                        raise BankLLMUnavailableError(f"Invalid file path: {ve}")
                    ext = _P(safe_path).suffix.lower()
                    if ext == ".csv":
                        # Robust CSV fallback parser that skips preamble lines
                        return _parse_csv_file_basic(safe_path)
                    else:
                        # For PDF files, we no longer fall back to regex.
                        # Signal to caller to retry later or mark as failed.
                        logger.warning(f"LLM initialization failed for {pdf_path}; regex fallback disabled.")
                        raise BankLLMUnavailableError(f"LLM initialization failed for non-CSV file: {e}")
                except BankLLMUnavailableError:
                    raise
                except Exception as fallback_e:
                    logger.error(f"Fallback check failed: {fallback_e}")
                    raise BankLLMUnavailableError(f"LLM initialization failed and fallback check failed: {fallback_e}")

        # Dispatch based on file extension (supports PDF and CSV)
        from pathlib import Path as _P
        # Validate pdf_path to prevent path traversal
        try:
            safe_path = validate_file_path(pdf_path)
        except ValueError as e:
            logger.error(str(e))
            return []
        _ext = _P(safe_path).suffix.lower()
        if _ext == ".csv":
            df = extractor.process_csv(safe_path, categorize=True, save_debug=False)
        else:
            df = extractor.process_pdf(
                safe_path,
                loader_names=['pymupdf', 'pdfplumber', 'pdfium2', 'pypdf'],
                categorize=True,
                save_debug=False
            )

        # Convert pandas DataFrame back to list of dicts for compatibility
        if not df.empty:
            transactions = df.to_dict('records')
            # Convert datetime objects to strings for JSON serialization
            for txn in transactions:
                if 'date' in txn and hasattr(txn['date'], 'strftime'):
                    txn['date'] = txn['date'].strftime('%Y-%m-%d')

            # Track AI usage if ai_config was used and we have a db session
            if ai_config and db:
                # Get extraction method information from extractor if available
                extraction_method = getattr(extractor, 'last_extraction_method', 'unknown')
                processing_time = getattr(extractor, 'last_processing_time', 0.0)
                text_length = getattr(extractor, 'last_text_length', 0)

                # Use enhanced OCR tracking with extraction method metadata
                if extraction_method == 'ocr':
                    track_ocr_usage(
                        db=db,
                        ai_config=ai_config,
                        extraction_method=extraction_method,
                        processing_time=processing_time,
                        text_length=text_length
                    )
                else:
                    # Track regular AI usage for PDF extraction
                    track_ai_usage(
                        db=db,
                        ai_config=ai_config,
                        operation_type="pdf_extraction",
                        metadata={
                            "extraction_method": extraction_method,
                            "processing_time": processing_time,
                            "text_length": text_length,
                            "transaction_count": len(transactions)
                        }
                    )

            return transactions
        else:
            return []

    except Exception as e:
        # Handle OCR-specific exceptions with proper error messages
        try:
            if isinstance(e, BankLLMUnavailableError):
                raise

            from commercial.ai.exceptions.bank_ocr_exceptions import (
                OCRUnavailableError,
                OCRTimeoutError,
                OCRProcessingError,
                OCRInvalidFileError,
                is_retryable_ocr_error,
                get_retry_delay
            )

            if isinstance(e, OCRUnavailableError):
                logger.warning(f"OCR unavailable for {pdf_path}: {e}")
                # Continue to fallback extraction
            elif isinstance(e, OCRTimeoutError):
                logger.error(f"OCR timeout for {pdf_path}: {e}")
                if is_retryable_ocr_error(e):
                    retry_delay = get_retry_delay(e)
                    logger.info(f"OCR timeout is retryable, suggested retry delay: {retry_delay}s")
                    raise BankLLMUnavailableError(f"OCR processing timed out, retry recommended: {e}")
            elif isinstance(e, OCRProcessingError):
                logger.error(f"OCR processing failed for {pdf_path}: {e}")
                if is_retryable_ocr_error(e):
                    retry_delay = get_retry_delay(e)
                    logger.info(f"OCR error is retryable, suggested retry delay: {retry_delay}s")
                    raise BankLLMUnavailableError(f"OCR processing failed temporarily, retry recommended: {e}")
            elif isinstance(e, OCRInvalidFileError):
                logger.error(f"Invalid file for OCR processing {pdf_path}: {e}")
                return []  # Don't retry for invalid files
            else:
                logger.error(f"Processing failed: {e}")

        except ImportError:
            logger.error(f"Processing failed: {e}")

        # Final fallback check
        try:
            from pathlib import Path as _P
            # Validate pdf_path to prevent path traversal
            try:
                safe_path = validate_file_path(pdf_path)
            except ValueError as ve:
                logger.error(str(ve))
                return []
            _ext = _P(safe_path).suffix.lower()
            if _ext == ".csv":
                # Robust CSV fallback
                return _parse_csv_file_basic(safe_path)
            else:
                # For PDF files, strictly require LLM or fail.
                logger.warning(f"PDF extraction failed for {pdf_path}; LLM and OCR both failed/unavailable.")
                raise BankLLMUnavailableError("PDF extraction failed (LLM and OCR failed/unavailable). Silent regex fallback disabled.")
        except BankLLMUnavailableError:
            raise
        except Exception as final_e:
            logger.error(f"Final fallback check failed: {final_e}")
            return []


def extract_transactions_from_pdf_paths(pdf_paths: List[str]) -> List[Dict[str, Any]]:
    """Extract transactions from PDF paths using BankTransactionExtractor"""
    all_transactions = []

    # Try to use the new BankTransactionExtractor first
    try:
        model_name = os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        extractor = BankTransactionExtractor(
            model_name=model_name,
            ollama_base_url=base_url,
            temperature=0.1,
            chunk_size=6000,
            chunk_overlap=150,
            request_timeout=120
        )

        for pdf_path in pdf_paths:
            try:
                logger.info(f"Processing {pdf_path} with BankTransactionExtractor")
                df = extractor.process_pdf(pdf_path, categorize=False, save_debug=False)

                if not df.empty:
                    transactions = df.to_dict('records')
                    # Convert datetime objects to strings
                    for txn in transactions:
                        if 'date' in txn and hasattr(txn['date'], 'strftime'):
                            txn['date'] = txn['date'].strftime('%Y-%m-%d')
                    all_transactions.extend(transactions)

            except Exception as e:
                logger.error(f"Failed to process {pdf_path} with BankTransactionExtractor: {e}")
                # Fallback to regex extraction for this file
                try:
                    try:
                        from pypdf import PdfReader
                    except ImportError:
                        logger.error(f"pypdf not available for {pdf_path}")
                        continue

                    texts = []
                    with open(pdf_path, "rb") as f:
                        reader = PdfReader(f)
                        for page in reader.pages:
                            texts.append(page.extract_text() or "")
                    raw_text = "\n\n".join(texts)
                    _preprocess_bank_text(raw_text)
                    # Removed automatic regex fallback for PDFs.
                    logger.warning(f"Failed to process {pdf_path} with LLM; regex fallback disabled.")
                    continue
                except Exception as regex_e:
                    logger.error(f"Regex fallback also failed for {pdf_path}: {regex_e}")
                    continue

    except Exception as e:
        logger.error(f"Failed to initialize BankTransactionExtractor: {e}")
        # Fallback to simple regex extraction for all files
        for pdf_path in pdf_paths:
            try:
                try:
                    from pypdf import PdfReader
                except ImportError:
                    logger.error(f"pypdf not available for {pdf_path}")
                    continue

                # Validate pdf_path to prevent path traversal
                try:
                    safe_path = validate_file_path(pdf_path)
                except ValueError as ve:
                    logger.error(str(ve))
                    continue

                texts = []
                with open(safe_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        texts.append(page.extract_text() or "")
                raw_text = "\n\n".join(texts)
                _preprocess_bank_text(raw_text)
                # Removed automatic regex fallback for PDFs.
                logger.warning(f"Failed to process {pdf_path}; regex fallback disabled.")
                continue
            except Exception as file_e:
                logger.error(f"Failed to process {pdf_path}: {file_e}")
                continue

    return _clean_and_deduplicate_transactions(all_transactions)


class BankStatementExtractor:
    """Legacy extractor wrapper - uses new BankTransactionExtractor internally"""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_available = self._check_ollama()

        # Initialize the new extractor if possible
        try:
            self._extractor = BankTransactionExtractor(
                model_name=self.model_name,
                ollama_base_url=self.base_url,
                temperature=0.1,
                chunk_size=6000,
                chunk_overlap=150,
                request_timeout=120
            )
        except Exception as e:
            logger.warning(f"Could not initialize BankTransactionExtractor: {e}")
            self._extractor = None

    def _check_ollama(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            models = [m.get("name") for m in (resp.json().get("models") or [])]
            return self.model_name in models
        except Exception:
            return False

    def extract_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        return process_bank_pdf_with_llm(pdf_path)

    def extract_from_files(self, files: List[str]) -> List[Dict[str, Any]]:
        return extract_transactions_from_pdf_paths(files)


def is_bank_llm_reachable(ai_config: Optional[Dict[str, Any]] = None) -> bool:
    """Lightweight reachability check for the bank LLM endpoint/model.

    Returns True if the configured provider is reachable. Supports all LiteLLM-compatible providers.
    """
    try:
        if not ai_config:
            # Fallback to environment variables (assume Ollama)
            ai_config = {
                "provider_name": "ollama",
                "model_name": os.getenv("OLLAMA_MODEL", "gpt-oss:latest"),
                "provider_url": os.getenv("LLM_API_BASE", "http://localhost:11434"),
                "api_key": None
            }

        provider_name = ai_config.get("provider_name", "ollama")
        logger.info(f"🔍 Testing reachability for provider: {provider_name}")

        # For Ollama, test the /api/tags endpoint
        if provider_name == "ollama":
            model_name = ai_config.get("model_name", "gpt-oss:latest")
            provider_url = ai_config.get("provider_url", "http://localhost:11434")

            if provider_url:
                # Clean up the URL and extract base URL
                url = provider_url.strip().rstrip('/')
                m = re.match(r"^(https?://[^/]+)(/api.*)?$", url)
                base_url = m.group(1) if m else url
            else:
                base_url = "http://localhost:11434"

            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            data = resp.json() or {}
            models = [m.get("name") for m in (data.get("models") or [])]
            return model_name in models

        else:
            # For other providers, use LiteLLM to test connection
            try:
                from core.models.database import get_db

                # Create a temporary extractor to test connection
                # Use a temporary database session for the connection test
                temp_db = next(get_db())
                try:
                    UniversalBankTransactionExtractor(
                        ai_config=ai_config,
                        db_session=temp_db,
                        temperature=0.1
                    )
                    # If initialization succeeds, the connection test passed
                    return True
                finally:
                    temp_db.close()

            except Exception as e:
                logger.warning(f"LiteLLM connection test failed for {provider_name}: {e}")
                return False

    except Exception as e:
        logger.warning(f"Reachability check failed: {e}")
        return False


# Alias for compatibility with ReviewProcessorWorker
StatementService = UniversalBankTransactionExtractor
