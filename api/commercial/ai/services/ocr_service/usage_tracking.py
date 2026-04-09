"""AI and OCR usage tracking and metrics."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import AIConfig as AIConfigModel

from ._shared import logger


def track_ai_usage(
    db: Session,
    ai_config: Dict[str, Any],
    operation_type: str = "general",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Track AI usage by incrementing the usage_count for the given AI config.

    Args:
        db: Database session
        ai_config: AI configuration dictionary
        operation_type: Type of operation (e.g., 'ocr', 'pdf_extraction', 'general')
        metadata: Additional metadata about the operation
    """
    try:
        masked_config = {}
        if ai_config:
            masked_config = {
                k: (v if k not in ("api_key", "provider_url", "api_secret") else "********")
                for k, v in ai_config.items()
            }

        logger.info(f"🎯 track_ai_usage called with: {masked_config}, operation_type: {operation_type}")
        if not ai_config or "provider_name" not in ai_config:
            logger.warning("❌ ai_config is None or missing provider_name")
            return

        provider_name = ai_config.get("provider_name")
        model_name = ai_config.get("model_name")
        logger.info(f"🔍 Looking for AI config: {provider_name}/{model_name}")

        db_config = (
            db.query(AIConfigModel)
            .filter(
                AIConfigModel.provider_name == provider_name,
                AIConfigModel.model_name == model_name,
                AIConfigModel.is_active == True,
            )
            .first()
        )

        if db_config:
            old_count = db_config.usage_count
            db_config.usage_count += 1
            db_config.last_used_at = datetime.now(timezone.utc)

            if operation_type == "ocr":
                if not hasattr(db_config, "ocr_usage_count") or db_config.ocr_usage_count is None:
                    db_config.ocr_usage_count = 0
                db_config.ocr_usage_count += 1
                logger.info(
                    f"🔍 Tracked OCR usage for {provider_name}/{model_name}: "
                    f"OCR count = {db_config.ocr_usage_count}"
                )

            db.commit()
            logger.info(
                f"✅ Tracked AI usage for {provider_name}/{model_name}: "
                f"{old_count} → {db_config.usage_count} (operation: {operation_type})"
            )

            if metadata:
                logger.info(f"📊 Operation metadata: {metadata}")
        else:
            logger.warning(f"❌ Could not find AI config to track usage: {provider_name}/{model_name}")
            logger.debug("Skipping full config dump for stability")
    except Exception as e:
        logger.error(f"❌ Failed to track AI usage: {e}")


def track_ocr_usage(
    db: Session,
    ai_config: Dict[str, Any],
    extraction_method: str,
    processing_time: Optional[float] = None,
    text_length: Optional[int] = None,
) -> None:
    """Track OCR-specific usage with detailed metadata.

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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    track_ai_usage(db, ai_config, operation_type="ocr", metadata=metadata)

    time_str = f"{processing_time:.2f}s" if processing_time is not None else "N/A"
    logger.info(
        f"📈 OCR Usage Metrics - Method: {extraction_method}, Time: {time_str}, Text Length: {text_length}"
    )


def get_ai_usage_stats(db: Session, provider_name: Optional[str] = None) -> Dict[str, Any]:
    """Get AI usage statistics including OCR-specific metrics.

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
            "total_ocr_usage": sum(getattr(c, "ocr_usage_count", 0) or 0 for c in configs),
            "configs": [],
        }

        for config in configs:
            config_stats = {
                "provider_name": config.provider_name,
                "model_name": config.model_name,
                "usage_count": config.usage_count or 0,
                "ocr_usage_count": getattr(config, "ocr_usage_count", 0) or 0,
                "ocr_enabled": getattr(config, "ocr_enabled", False),
                "last_used_at": config.last_used_at.isoformat() if config.last_used_at else None,
            }
            stats["configs"].append(config_stats)

        return stats
    except Exception as e:
        logger.error(f"Failed to get AI usage stats: {e}")
        return {"error": str(e)}


def publish_ocr_usage_metrics(
    db: Session,
    operation_type: str,
    extraction_method: str,
    processing_time: float,
    success: bool,
) -> None:
    """Publish OCR usage metrics for monitoring and analytics.

    Args:
        db: Database session
        operation_type: Type of operation ('bank_statement', 'expense', 'invoice')
        extraction_method: Method used ('pdf_loader', 'ocr')
        processing_time: Processing time in seconds
        success: Whether the operation was successful
    """
    try:
        time_str = f"{processing_time:.2f}s" if processing_time is not None else "N/A"
        logger.info(
            f"📊 OCR Metrics - Operation: {operation_type}, Method: {extraction_method}, "
            f"Time: {time_str}, Success: {success}"
        )
    except Exception as e:
        logger.error(f"Failed to publish OCR usage metrics: {e}")
