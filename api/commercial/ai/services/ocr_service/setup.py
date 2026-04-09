"""OCR dependency initialization, setup validation, and processing lock management."""

from typing import Any, Dict

from commercial.ai.settings.ocr_config import check_ocr_dependencies, get_ocr_config, is_ocr_available
from commercial.ai.exceptions.bank_ocr_exceptions import (
    OCRConfigurationError,
    OCRDependencyMissingError,
    OCRUnavailableError,
)

from ._shared import logger


def initialize_ocr_dependencies() -> Dict[str, Any]:
    """Initialize and check OCR dependencies for bank statement processing.

    Returns:
        Dictionary with initialization status and available components
    """
    logger.info("Initializing OCR dependencies for bank statement processing...")

    try:
        ocr_config = get_ocr_config()
        logger.info(f"OCR Configuration loaded: enabled={ocr_config.enabled}")

        dependencies = check_ocr_dependencies()
        logger.info(f"OCR Dependencies: {dependencies}")

        available = is_ocr_available()
        logger.info(f"OCR Available: {available}")

        components = {}

        if ocr_config.enabled and available:
            try:
                if ocr_config.use_unstructured_api:
                    logger.info("Initializing Unstructured API client...")
                    components["unstructured_api"] = True
                else:
                    logger.info("Initializing local Tesseract OCR...")
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
            "components": components,
        }

    except Exception as e:
        logger.error(f"OCR initialization failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "available": False,
        }


def validate_ocr_setup() -> None:
    """Validate OCR setup and raise appropriate exceptions if not configured properly.

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

        if not dependencies["unstructured"]:
            raise OCRDependencyMissingError(
                "unstructured package is required",
                missing_dependency="unstructured",
            )

        if ocr_config.use_unstructured_api:
            if not ocr_config.unstructured_api_key:
                raise OCRConfigurationError(
                    "Unstructured API key is required when using API mode",
                    config_key="unstructured_api_key",
                )
        else:
            if not dependencies["pytesseract"]:
                raise OCRDependencyMissingError(
                    "pytesseract package is required for local OCR",
                    missing_dependency="pytesseract",
                )

            if not dependencies["tesseract_binary"]:
                raise OCRDependencyMissingError(
                    "Tesseract binary is required for local OCR",
                    missing_dependency="tesseract",
                )

        logger.info("OCR setup validation passed")

    except (OCRUnavailableError, OCRDependencyMissingError, OCRConfigurationError):
        raise
    except Exception as e:
        raise OCRConfigurationError(f"OCR setup validation failed: {e}")


def cancel_ocr_tasks_for_expense(expense_id: int) -> None:
    """Best-effort cancelation placeholder. Real systems may use a cancel topic or outbox table."""
    logger.info(f"Request to cancel OCR tasks for expense_id={expense_id}")


def acquire_processing_lock(resource_type: str, resource_id: int, timeout_minutes: int = 30) -> bool:
    """Acquire processing lock for a resource. Returns True if lock was acquired, False if already locked."""
    try:
        from core.models.processing_lock import ProcessingLock
        from core.models.database import get_db

        db_gen = get_db()
        try:
            session = next(db_gen)
            acquired = ProcessingLock.acquire_lock(
                session, resource_type, resource_id, lock_duration_minutes=timeout_minutes
            )
            if acquired:
                session.commit()
                logger.info(f"Acquired processing lock for {resource_type} {resource_id}")
            return acquired
        except StopIteration:
            logger.error("Failed to get database session for lock acquisition")
            return False
        except Exception as e:
            logger.error(f"Failed to acquire processing lock for {resource_type} {resource_id}: {e}")
            return False
        finally:
            try:
                db_gen.close()
            except Exception:
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
            logger.error("Failed to get database session for lock release")
            return False
        except Exception as e:
            logger.error(f"Failed to release processing lock for {resource_type} {resource_id}: {e}")
            return False
        finally:
            try:
                db_gen.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error in release_processing_lock for {resource_type} {resource_id}: {e}")
        return False


def cleanup_expired_processing_locks() -> int:
    """Clean up expired processing locks. Returns number of locks cleaned up."""
    try:
        from core.models.processing_lock import ProcessingLock
        from core.models.database import get_db

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
