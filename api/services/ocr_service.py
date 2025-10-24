import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from models.models_per_tenant import AIConfig as AIConfigModel

def _resolve_log_level(name: str) -> int:
    try:
        return getattr(logging, (name or "INFO").upper(), logging.INFO)
    except Exception:
        return logging.INFO

logging.basicConfig(level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger(__name__)


def track_ai_usage(db: Session, ai_config: Dict[str, Any]) -> None:
    """Track AI usage by incrementing the usage_count for the given AI config."""
    try:
        logger.info(f"🎯 track_ai_usage called with: {ai_config}")
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
            db.commit()
            logger.info(f"✅ Tracked AI usage for {provider_name}/{model_name}: {old_count} → {db_config.usage_count}")
        else:
            logger.warning(f"❌ Could not find AI config to track usage: {provider_name}/{model_name}")
            # Log all available configs for debugging
            all_configs = db.query(AIConfigModel).all()
            logger.info(f"📋 Available AI configs: {[(c.provider_name, c.model_name, c.is_active) for c in all_configs]}")
    except Exception as e:
        logger.error(f"❌ Failed to track AI usage: {e}")
        # Don't raise exception to avoid breaking the main functionality

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
        producer.produce(topic, value=payload, key=str(message.get("expense_id")), headers=headers)
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
                with open(file_path, "rb") as image_file:
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
                return {"error": f"LiteLLM OCR failed: {str(e)}"}

    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return {"error": str(e)}


async def process_attachment_inline(db: Session, expense_id: int, attachment_id: int, file_path: str) -> None:
    """Fallback inline processing when Kafka is not configured."""
    print(f"🔴 DEBUG: process_attachment_inline called for expense {expense_id}")  # DEBUG
    from models.models_per_tenant import Expense, AIConfig as AIConfigModel  # local import to avoid circulars
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden; skipping OCR.")
        return
    try:
        expense.analysis_status = "processing"
        db.commit()
    except Exception:
        db.rollback()

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

    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")
    result = await _run_ocr(file_path, ai_config=ai_config)

    # Track AI usage if ai_config was used and OCR was actually attempted
    if ai_config and not result.get("provider_not_supported"):
        logger.info(f"🔍 About to track AI usage for config: {ai_config}")
        track_ai_usage(db, ai_config)
        logger.info("✅ AI usage tracking completed")
    elif result.get("provider_not_supported"):
        logger.info(f"⚠️ Skipping AI usage tracking - OCR not supported for provider: {ai_config.get('provider_name') if ai_config else 'unknown'}")

    # Update DB with result if still not overridden
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden during OCR; not applying result.")
        return
    try:
        expense.analysis_updated_at = datetime.now(timezone.utc)
        if "error" in result:
            # Persist error payload as a dict
            try:
                expense.analysis_result = {"error": str(result.get("error"))}
            except Exception:
                expense.analysis_result = {"error": "unknown"}
            expense.analysis_status = "failed"
            expense.analysis_error = str(result.get("error"))
            # Clear any previous successful analysis data to avoid confusion
            expense.amount = expense.amount if expense.amount not in (None, 0) else None
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
        else:
            # Map fields robustly
            extracted = result if isinstance(result, dict) else {}
            logger.info(f"OCR extracted keys: {list(extracted.keys())}")

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
                expense.category = str(cat)
            vend = first_key(extracted, ["vendor", "merchant", "seller", "store", "payee"]) or None
            if vend:
                expense.vendor = str(vend)

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
                expense.payment_method = str(pm)
            ref = first_key(extracted, ["reference_number", "reference", "ref", "receipt_number", "invoice_number"]) or None
            if ref:
                expense.reference_number = str(ref)
            notes = first_key(extracted, ["notes", "memo"]) or None
            if notes:
                expense.notes = str(notes)

            # Persist normalized extraction as dict
            try:
                expense.analysis_result = extracted if isinstance(extracted, dict) else {"items": extracted}
            except Exception:
                expense.analysis_result = extracted
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


def queue_or_process_attachment(db: Session, tenant_id: Optional[int], expense_id: int, attachment_id: int, file_path: str) -> None:
    """Publish OCR job to Kafka if available, otherwise process inline in background."""
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


