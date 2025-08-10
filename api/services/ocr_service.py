import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

def _resolve_log_level(name: str) -> int:
    try:
        return getattr(logging, (name or "INFO").upper(), logging.INFO)
    except Exception:
        return logging.INFO

logging.basicConfig(level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger(__name__)
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
        producer = Producer(conf)
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
        logger.info(f"Publishing OCR message: expense_id={message.get('expense_id')} tenant_id={message.get('tenant_id')} attachment_id={message.get('attachment_id')}")
        producer.produce(topic, value=payload, key=str(message.get("expense_id")))
        producer.flush(1.0)
        logger.info(f"Published OCR task to Kafka topic={topic} expense_id={message.get('expense_id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish OCR task: {e}")
        return False


def cancel_ocr_tasks_for_expense(expense_id: int) -> None:
    """Best-effort cancelation placeholder. Real systems may use a cancel topic or outbox table."""
    logger.info(f"Request to cancel OCR tasks for expense_id={expense_id}")
    # No-op: If using Kafka, consider producing a cancel message or managing an outbox/processing table.


async def _run_ollama_ocr(file_path: str, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
    """Run OCR using Ollama OCR library if available, else return empty result."""
    try:
        from ollama_ocr import OCRProcessor  # type: ignore

        model_name = os.getenv("OCR_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2-vision:11b"))
        base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        logger.info(f"Starting OCR: file={file_path} model={model_name} base_url={base_url}")
        ocr = OCRProcessor(model_name=model_name, base_url=base_url)
        prompt = custom_prompt or (
            "You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON. "
            "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes. "
            "If a field is unknown, set it to null. Do not include any prose."
        )
        loop = asyncio.get_running_loop()
        # Run blocking call in thread to avoid blocking event loop
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
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return {"error": str(e)}


async def process_attachment_inline(db: Session, expense_id: int, attachment_id: int, file_path: str) -> None:
    """Fallback inline processing when Kafka is not configured."""
    from models.models_per_tenant import Expense  # local import to avoid circulars
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

    logger.info(f"Processing attachment inline: expense_id={expense_id} attachment_id={attachment_id} file={file_path}")
    result = await _run_ollama_ocr(file_path)

    # Update DB with result if still not overridden
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        return
    if expense.manual_override:
        logger.info(f"Expense {expense_id} manually overridden during OCR; not applying result.")
        return
    try:
        expense.analysis_result = result
        expense.analysis_updated_at = datetime.now(timezone.utc)
        if "error" in result:
            expense.analysis_status = "failed"
            expense.analysis_error = str(result.get("error"))
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


