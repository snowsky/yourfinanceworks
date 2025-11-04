import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text
from models.models_per_tenant import AIConfig as AIConfigModel
from settings.ocr_config import get_ocr_config, check_ocr_dependencies, is_ocr_available
from exceptions.bank_ocr_exceptions import (
    OCRUnavailableError,
    OCRDependencyMissingError,
    OCRConfigurationError
)

def _resolve_log_level(name: str) -> int:
    try:
        return getattr(logging, (name or "INFO").upper(), logging.INFO)
    except Exception:
        return logging.INFO

logging.basicConfig(level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger(__name__)


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
        logger.info(f"🎯 track_ai_usage called with: {ai_config}, operation_type: {operation_type}")
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
            # Log all available configs for debugging
            all_configs = db.query(AIConfigModel).all()
            logger.info(f"📋 Available AI configs: {[(c.provider_name, c.model_name, c.is_active) for c in all_configs]}")
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
    logger.info(f"📈 OCR Usage Metrics - Method: {extraction_method}, Time: {processing_time:.2f}s, Text Length: {text_length}")


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
        logger.info(
            f"📊 OCR Metrics - Operation: {operation_type}, Method: {extraction_method}, "
            f"Time: {processing_time:.2f}s, Success: {success}"
        )

        # Example: Could publish to a metrics collection service
        # metrics_client.increment(f"ocr.{operation_type}.{extraction_method}.{'success' if success else 'failure'}")
        # metrics_client.histogram(f"ocr.{operation_type}.processing_time", processing_time)
        
    except Exception as e:
        logger.error(f"Failed to publish OCR usage metrics: {e}")

# Keep producers alive across calls so messages can be delivered before process exit
_PRODUCER_CACHE: dict[str, dict[str, any]] = {}
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
    # Date (prefer YYYY-MM-DD or DD/MM/YYYY)
    m_date = re.search(r"(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[/.-]\d{2}[/.-]\d{4})", text)
    if m_date:
        data["date"] = m_date.group(1)
    # Vendor (first uppercase word line)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
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


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Try to find and parse the first JSON object embedded in a text block."""
    import re
    try:
        # Quick path: whole text is JSON
        return json.loads(text)
    except Exception:
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
                        return json.loads(candidate)
                    except Exception:
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
        remaining = producer.flush(10.0)
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
            pass


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


async def _run_ocr(file_path: str, custom_prompt: Optional[str] = None, ai_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run OCR using the configured AI provider. Supports multiple providers via LiteLLM."""
    try:
        # Use AI config from database if available, otherwise fallback to environment variables
        if ai_config:
            provider_name = ai_config.get("provider_name", "ollama")
            model_name = ai_config.get("model_name", "llama3.2-vision:11b")
            base_url = ai_config.get("provider_url", "http://localhost:11434")
            api_key = ai_config.get("api_key")

            logger.info(f"🔧 OCR using AI config: provider={provider_name} model={model_name} file={file_path}")

            # Check if OCR is enabled for this provider configuration
            if not ai_config.get("ocr_enabled", False):
                logger.warning(f"⚠️ OCR not enabled for provider '{provider_name}'. Please enable OCR in AI configuration settings.")
                return {
                    "error": f"OCR not enabled for provider '{provider_name}'. Please enable OCR in AI configuration settings.",
                    "ocr_not_enabled": True
                }
        else:
            # Fallback to environment variables (legacy behavior)
            # Detect provider from environment variables
            env_api_base = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
            env_api_key = os.getenv("LLM_API_KEY")

            if env_api_base and ("openrouter.ai" in env_api_base or "openrouter" in env_api_base):
                provider_name = "openrouter"
            elif env_api_base and ("api.openai.com" in env_api_base or "openai" in env_api_base):
                provider_name = "openai"
            elif env_api_base and ("anthropic" in env_api_base):
                provider_name = "anthropic"
            elif env_api_base and ("google" in env_api_base):
                provider_name = "google"
            elif env_api_base or os.getenv("OLLAMA_MODEL"):
                provider_name = "ollama"
            elif env_api_key:
                provider_name = "openai"  # Default to OpenAI if API key present
            else:
                provider_name = "ollama"  # Final fallback

            model_name = os.getenv("LLM_MODEL_EXPENSES", os.getenv("OLLAMA_MODEL", "llama3.2-vision:11b"))
            base_url = env_api_base or "http://localhost:11434"
            api_key = env_api_key
            logger.info(f"⚠️ OCR using environment variables: provider={provider_name} model={model_name} endpoint={base_url} file={file_path}")

        # Handle different providers
        if provider_name == "ollama":
            # Use Ollama OCR library for Ollama provider
            # Don't append /api/generate if it's already a non-Ollama provider URL
            if not base_url.endswith("/api/generate") and "openrouter.ai" not in base_url and "api.openai.com" not in base_url:
                ocr_endpoint = f"{base_url}/api/generate"
            else:
                ocr_endpoint = base_url

            from ollama_ocr import OCRProcessor  # type: ignore
            ocr = OCRProcessor(model_name=model_name, base_url=ocr_endpoint)
            prompt = custom_prompt or (
                "You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON. "
                "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes. "
                "If a field is unknown, set it to null. Do not include any prose."
            )
            loop = asyncio.get_running_loop()
            import time
            t0 = time.time()
            result = await loop.run_in_executor(
                None,
                lambda: ocr.process_image(
                    image_path=file_path, format_type="json", custom_prompt=prompt, language="English"
                ),
            )
            dt = (time.time() - t0) * 1000
            if isinstance(result, str):
                logger.info(f"OCR raw result (str) length={len(result)} duration_ms={dt:.0f}")
            else:
                try:
                    logger.info(f"OCR result keys={list(result.keys()) if isinstance(result, dict) else 'n/a'} duration_ms={dt:.0f}")
                except Exception:
                    logger.info(f"OCR result type={type(result)} duration_ms={dt:.0f}")
            if isinstance(result, str):
                parsed = _extract_json_from_text(result)
                if parsed is not None:
                    return parsed
                return {"raw": result}
            return result or {}

        else:
            # Use LiteLLM for other providers (OpenAI, Anthropic, Google, etc.)
            try:
                from litellm import completion

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

                # Encode image to base64
                from utils.file_validation import validate_file_path
                try:
                    safe_path = validate_file_path(file_path)
                except ValueError as e:
                    logger.error(str(e))
                    return {"error": f"Invalid file path: {e}"}
                with open(safe_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')

                # Determine image format
                if file_path.lower().endswith('.png'):
                    image_format = "png"
                elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                    image_format = "jpeg"
                elif file_path.lower().endswith('.webp'):
                    image_format = "webp"
                else:
                    image_format = "png"  # Default fallback

                prompt = custom_prompt or (
                    "You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON. "
                    "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes. "
                    "If a field is unknown, set it to null. Do not include any prose."
                )

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ]

                import time
                t0 = time.time()
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: completion(messages=messages, **kwargs)
                )
                dt = (time.time() - t0) * 1000
                logger.info(f"OCR via LiteLLM result duration_ms={dt:.0f}")

                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if isinstance(content, str):
                        # Try to parse JSON from response
                        parsed = _extract_json_from_text(content)
                        if parsed is not None:
                            return parsed
                        return {"raw": content}
                    else:
                        return {"raw": str(content)}
                else:
                    return {"error": "No response from AI provider"}

            except ImportError:
                return {"error": "LiteLLM not available for non-Ollama providers"}
            except Exception as e:
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


async def process_attachment_inline(db: Session, expense_id: int, attachment_id: int, file_path: str) -> None:
    """Fallback inline processing when Kafka is not configured."""
    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")

    # Check if this is a cloud storage file that needs to be downloaded
    if not os.path.exists(file_path):
        logger.info(f"File path '{file_path}' doesn't exist locally - attempting cloud storage download...")

        try:
            # Use the cloud storage service to retrieve the file
            from services.cloud_storage_service import CloudStorageService
            from settings.cloud_storage_config import get_cloud_storage_config
            from models.database import get_tenant_context
            import tempfile

            # Get tenant context
            tenant_id = get_tenant_context()
            if not tenant_id:
                raise Exception("No tenant context available for cloud storage access")

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

            if retrieve_result.success and retrieve_result.metadata and 'content' in retrieve_result.metadata:
                # Create temporary file with the downloaded content
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{attachment_id}_{os.path.basename(file_path)}") as temp_file:
                    temp_file.write(retrieve_result.metadata['content'])
                    temp_path = temp_file.name

                # Verify the file was created
                if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                    raise Exception(f"Failed to create temporary file or empty content: {temp_path}")

                # Update file_path to use the temporary file
                original_file_path = file_path
                file_path = temp_path
                logger.info(f"Successfully downloaded cloud file from '{original_file_path}' to '{file_path}' for OCR processing")
            else:
                raise Exception(f"Failed to retrieve file from cloud storage: {retrieve_result.error_message}")

        except Exception as e:
            logger.error(f"Failed to download cloud storage file {file_path}: {e}")
            # Update expense status to failed
            try:
                from models.models_per_tenant import Expense
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
    from models.models_per_tenant import Expense, AIConfig as AIConfigModel  # local import to avoid circulars
    from models.database import set_tenant_context  # Import tenant context management
    
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
    ai_config = None
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
    except Exception as e:
        logger.warning(f"Failed to fetch AI config from database: {e}, falling back to environment variables")
        # Don't log full stack trace for encryption errors to avoid leaking sensitive data
        if "decryption" not in str(e).lower() and "encryption" not in str(e).lower():
            logger.debug(f"AI config fetch error details: {str(e)}", exc_info=True)
        else:
            logger.debug("AI config fetch failed due to encryption/decryption error (details not logged for security)")

    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")
    
    # Use UnifiedOCRService for expense processing
    try:
        from services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
        
        # Configure OCR service
        ocr_config = OCRConfig(
            ai_config=ai_config,
            enable_ai_vision=True,
            enable_fallback_parsing=True,
            timeout_seconds=300,
            max_retries=3
        )
        
        ocr_service = UnifiedOCRService(ocr_config)
        
        # Extract structured data from expense receipt
        ocr_result = await ocr_service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT)
        
        if ocr_result.success:
            result = ocr_result.structured_data or {}
            logger.info(f"✅ Unified OCR extraction successful: {len(result)} fields extracted in {ocr_result.processing_time:.2f}s using {ocr_result.method.value}")
        else:
            logger.error(f"❌ Unified OCR extraction failed: {ocr_result.error_message}")
            # Fallback to legacy OCR for backward compatibility
            logger.info("Falling back to legacy OCR processing...")
            result = await _run_ocr(file_path, ai_config=ai_config)
            
    except ImportError as e:
        logger.warning(f"UnifiedOCRService not available, using legacy OCR: {e}")
        result = await _run_ocr(file_path, ai_config=ai_config)
    except Exception as e:
        logger.error(f"UnifiedOCRService failed, using legacy OCR: {e}")
        result = await _run_ocr(file_path, ai_config=ai_config)

    # Track AI usage if ai_config was used and OCR was actually attempted
    if ai_config and not result.get("provider_not_supported"):
        logger.info(f"🔍 About to track AI usage for config: {ai_config}")
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
    elif result.get("provider_not_supported"):
        logger.info(f"⚠️ Skipping AI usage tracking - OCR not supported for provider: {ai_config.get('provider_name') if ai_config else 'unknown'}")
    elif result.get("ocr_not_enabled"):
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
        expense.analysis_updated_at = datetime.now(timezone.utc)
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
            expense.vendor = expense.vendor if expense.vendor else None
            expense.tax_rate = expense.tax_rate if expense.tax_rate not in (None, 0) else None
            expense.tax_amount = expense.tax_amount if expense.tax_amount not in (None, 0) else None
            expense.payment_method = expense.payment_method if expense.payment_method else None
            expense.reference_number = expense.reference_number if expense.reference_number else None
            expense.notes = expense.notes if expense.notes else None

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
            # Map fields robustly
            extracted = result if isinstance(result, dict) else {}
            logger.info(f"OCR extracted keys: {list(extracted.keys()) if isinstance(extracted, dict) else 'non-dict result'}")

            # If we only got raw text, first try to extract embedded JSON, then try heuristics
            if set(extracted.keys()) == {"raw"} and isinstance(extracted.get("raw"), str):
                extracted_text = extracted["raw"]
                # Detect known OCR transport errors and fail early
                if any(err in extracted_text for err in [
                    "Error processing image", "HTTPConnectionPool", "Failed to establish a new connection", "Connection refused"
                ]):
                    expense.analysis_status = "failed"
                    expense.analysis_error = extracted_text[:500]
                    db.commit()
                    logger.error(f"OCR transport error for expense {expense_id}: {expense.analysis_error}")
                    return
                # Try to parse JSON embedded in raw text
                parsed_json = _extract_json_from_text(extracted_text)
                if isinstance(parsed_json, dict):
                    extracted.update(parsed_json)
                    logger.info(f"Parsed embedded JSON keys: {list(parsed_json.keys())}")
                else:
                    try:
                        heur = _heuristic_parse_text(extracted_text)
                        if heur:
                            extracted.update(heur)
                            logger.info(f"Heuristic parse extracted keys: {list(heur.keys())}")
                    except Exception as e:
                        logger.warning(f"Heuristic parse failed: {e}")

            def parse_number(value: Any) -> Optional[float]:
                try:
                    if value is None:
                        return None
                    if isinstance(value, (int, float)):
                        return float(value)
                    s = str(value)
                    # Remove currency symbols and spaces
                    import re
                    s = re.sub(r"[^0-9,.-]", "", s)
                    # If both comma and dot present, assume comma thousands
                    if "," in s and "." in s:
                        s = s.replace(",", "")
                    else:
                        # If only comma present, treat as decimal
                        s = s.replace(",", ".")
                    return float(s)
                except Exception:
                    return None

            def first_key(d: Dict[str, Any], keys: list[str]) -> Any:
                for k in keys:
                    if k in d and d[k] not in (None, ""):
                        return d[k]
                return None

            # Amount/total
            amt = parse_number(first_key(extracted, [
                "total_amount", "total", "amount", "grand_total", "subtotal"
            ]))
            if amt is not None:
                expense.amount = amt if expense.amount in (None, 0) else expense.amount
                # If no explicit total_amount provided, set total_amount equal to amount
                if expense.total_amount in (None, 0):
                    expense.total_amount = amt

            # Currency
            cur = first_key(extracted, ["currency", "currency_code", "iso_currency", "total_currency"]) or None
            if isinstance(cur, str) and len(cur) <= 5:
                expense.currency = cur.upper()

            # Date
            date_str = first_key(extracted, ["expense_date", "date", "transaction_date", "purchase_date"]) or None
            if date_str:
                try:
                    from dateutil import parser as dateparser  # type: ignore
                    parsed_dt = dateparser.parse(str(date_str))
                    if parsed_dt:
                        expense.expense_date = parsed_dt
                except Exception:
                    pass

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
            
            vend = first_key(extracted, ["vendor", "merchant", "seller", "store", "payee"]) or None
            if vend:
                # Ensure vendor is clean text, not encrypted data
                vendor_str = str(vend).strip()
                if vendor_str and not _looks_like_base64_encrypted(vendor_str):
                    expense.vendor = vendor_str
                else:
                    logger.warning(f"Invalid vendor data detected, using default")
                    expense.vendor = "Unknown Vendor"

            # Taxes
            tr = parse_number(first_key(extracted, ["tax_rate", "vat_rate"]))
            ta = parse_number(first_key(extracted, ["tax_amount", "vat_amount"]))
            tt = parse_number(first_key(extracted, ["total_amount", "total"]))
            expense.tax_rate = tr if tr is not None else expense.tax_rate
            expense.tax_amount = ta if ta is not None else expense.tax_amount
            expense.total_amount = tt if tt is not None else expense.total_amount

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
                    
                    expense.analysis_result = sanitized_data if sanitized_data else {"status": "extracted"}
                    logger.info(f"Stored sanitized analysis_result with keys: {list(sanitized_data.keys())}")
                else:
                    expense.analysis_result = {"items": extracted} if extracted else {"status": "no_data"}
                    
            except Exception as e:
                logger.error(f"Failed to set analysis_result for expense {expense_id}: {e}")
                # Store a safe fallback that won't cause encryption issues
                expense.analysis_result = {"error": "Failed to store result", "timestamp": datetime.now(timezone.utc).isoformat()}
            expense.analysis_status = "done"
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
                logger.info(f"Mapped OCR fields for expense {expense_id}: {mapped_preview}")
            except Exception:
                pass
        db.commit()
        logger.info(f"Expense {expense_id} analysis updated: {expense.analysis_status}")
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
    if 'is_temp_file' in locals() and is_temp_file and os.path.exists(file_path):
        try:
            logger.info(f"Cleaning up temporary file: {file_path}")
            os.remove(file_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary file {file_path}: {cleanup_error}")


def queue_or_process_attachment(db: Session, tenant_id: Optional[int], expense_id: int, attachment_id: int, file_path: str) -> None:
    """Publish OCR job to Kafka if available, otherwise process inline in background."""
    from models.database import set_tenant_context  # Import tenant context management
    
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
            asyncio.get_event_loop().create_task(process_attachment_inline(db, expense_id, attachment_id, file_path))
        except RuntimeError:
            # If no running loop (sync context), schedule with new loop via thread
            asyncio.run(process_attachment_inline(db, expense_id, attachment_id, file_path))
