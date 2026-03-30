import asyncio
import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from commercial.ai.services.ai_config_service import AIConfigService
from core.constants.expense_status import ExpenseStatus
from core.schemas.expense import ExpenseVoiceParseResponse
from core.utils.currency import CURRENCY_SYMBOL_MAP

logger = logging.getLogger(__name__)

VOICE_PARSE_PROMPT = """Convert the spoken personal-finance note below into compact JSON.

Return ONLY a JSON object with these keys:
- amount: number or null
- currency: 3-letter ISO currency code like USD or CAD
- expense_date: YYYY-MM-DD
- category: one of General, Travel, Meals, Transportation, Software, Supplies
- vendor: string or null
- notes: string
- confidence: number from 0.0 to 1.0

Rules:
- Use the transcript as the source of truth.
- Normalize currency symbols like $ into a likely ISO code.
- If the transcript does not specify a date, use today's date.
- Keep vendor short and clean.
- Do not invent details.

Today: {today}
Currency hint: {currency_hint}
Transcript: {transcript}
"""

KNOWN_CATEGORIES = ["General", "Travel", "Meals", "Transportation", "Software", "Supplies"]
_AMOUNT_PATTERN = re.compile(r"(?<!\d)(?:[$€£¥]\s*)?(-?\d+(?:[.,]\d{1,2})?)")
_CURRENCY_CODE_PATTERN = re.compile(r"\b(USD|CAD|EUR|GBP|JPY|AUD|NZD|CHF|CNY|INR)\b", re.IGNORECASE)


def _today_iso(base_date: Optional[date]) -> str:
    return (base_date or date.today()).isoformat()


def _normalize_currency(raw: Optional[str], currency_hint: Optional[str] = None) -> str:
    candidate = (raw or "").strip()
    if not candidate and currency_hint:
        candidate = currency_hint.strip()

    if candidate in CURRENCY_SYMBOL_MAP:
        return CURRENCY_SYMBOL_MAP[candidate]

    upper = candidate.upper()
    if len(upper) == 3 and upper.isalpha():
        return upper

    return "USD"


def _parse_amount(transcript: str) -> Optional[float]:
    match = _AMOUNT_PATTERN.search(transcript.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _detect_currency(transcript: str, currency_hint: Optional[str]) -> str:
    code_match = _CURRENCY_CODE_PATTERN.search(transcript)
    if code_match:
        return _normalize_currency(code_match.group(1))

    for symbol, code in CURRENCY_SYMBOL_MAP.items():
        if symbol and symbol in transcript:
            return code

    lowered = transcript.lower()
    if "cad" in lowered or "canadian" in lowered:
        return "CAD"
    if "eur" in lowered or "euro" in lowered:
        return "EUR"
    if "gbp" in lowered or "pound" in lowered:
        return "GBP"

    return _normalize_currency(None, currency_hint)


def _detect_date(transcript: str, base_date: Optional[date]) -> date:
    anchor = base_date or date.today()
    lowered = transcript.lower()

    if "yesterday" in lowered:
        return anchor - timedelta(days=1)
    if "today" in lowered:
        return anchor
    if "tomorrow" in lowered:
        return anchor + timedelta(days=1)

    explicit = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", transcript)
    if explicit:
        try:
            return date.fromisoformat(explicit.group(1))
        except ValueError:
            pass

    return anchor


def _detect_category(transcript: str) -> str:
    lowered = transcript.lower()
    category_rules = {
        "Meals": ["meal", "lunch", "dinner", "coffee", "breakfast", "restaurant", "food"],
        "Transportation": ["uber", "lyft", "taxi", "bus", "train", "subway", "parking", "gas", "fuel"],
        "Travel": ["flight", "hotel", "airbnb", "trip", "travel"],
        "Software": ["software", "subscription", "saas", "notion", "figma", "slack", "chatgpt"],
        "Supplies": ["supplies", "office", "paper", "printer", "notebook", "pens"],
    }

    for category, keywords in category_rules.items():
        if any(keyword in lowered for keyword in keywords):
            return category

    return "General"


def _clean_vendor(value: str) -> Optional[str]:
    candidate = value.strip(" .,!?:;")
    if not candidate:
        return None
    candidate = re.split(r"\b(today|yesterday|for|on|using|with)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0]
    return candidate.strip(" .,!?:;") or None


def _detect_vendor(transcript: str) -> Optional[str]:
    patterns = [
        r"\bat\s+([A-Za-z][A-Za-z0-9 '&.-]{1,60})",
        r"\bfrom\s+([A-Za-z][A-Za-z0-9 '&.-]{1,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return _clean_vendor(match.group(1))
    return None


def _coerce_response(data: Dict[str, Any], transcript: str, currency_hint: Optional[str], date_hint: Optional[date], parser_used: str) -> ExpenseVoiceParseResponse:
    amount = data.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    currency = _normalize_currency(data.get("currency"), currency_hint)
    category = data.get("category") if data.get("category") in KNOWN_CATEGORIES else _detect_category(transcript)

    expense_date = _detect_date(transcript, date_hint)
    if data.get("expense_date"):
        try:
            expense_date = date.fromisoformat(str(data["expense_date"]))
        except ValueError:
            pass

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    return ExpenseVoiceParseResponse(
        transcript=transcript,
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=_clean_vendor(str(data.get("vendor"))) if data.get("vendor") else _detect_vendor(transcript),
        notes=str(data.get("notes") or transcript),
        confidence=max(0.0, min(1.0, confidence)),
        parser_used=parser_used,
    )


def parse_voice_expense_heuristic(
    transcript: str,
    currency_hint: Optional[str] = None,
    date_hint: Optional[date] = None,
) -> ExpenseVoiceParseResponse:
    amount = _parse_amount(transcript)
    category = _detect_category(transcript)
    vendor = _detect_vendor(transcript)
    expense_date = _detect_date(transcript, date_hint)
    currency = _detect_currency(transcript, currency_hint)

    confidence = 0.45
    if amount is not None:
        confidence += 0.2
    if vendor:
        confidence += 0.15
    if category != "General":
        confidence += 0.1
    if transcript.lower().find("today") != -1 or transcript.lower().find("yesterday") != -1:
        confidence += 0.05

    return ExpenseVoiceParseResponse(
        transcript=transcript,
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=vendor,
        notes=transcript,
        confidence=min(0.95, confidence),
        parser_used="heuristic",
    )


async def _parse_with_ai(
    db: Session,
    transcript: str,
    currency_hint: Optional[str],
    date_hint: Optional[date],
) -> Optional[ExpenseVoiceParseResponse]:
    ai_config = AIConfigService.get_ai_config(db, component="ocr", require_ocr=False)
    if not ai_config:
        return None

    try:
        from litellm import completion
    except Exception as exc:
        logger.warning("LiteLLM unavailable for voice parsing: %s", exc)
        return None

    provider_name = ai_config.get("provider_name", "openai")
    model_name = ai_config.get("model_name")
    if not model_name:
        return None

    if provider_name == "ollama":
        model = f"ollama/{model_name}"
    elif provider_name == "openrouter":
        model = f"openrouter/{model_name}" if "/" not in model_name else model_name
    elif provider_name == "anthropic":
        model = f"anthropic/{model_name}" if "/" not in model_name else model_name
    elif provider_name == "google":
        model = f"google/{model_name}" if "/" not in model_name else model_name
    else:
        model = model_name

    prompt = VOICE_PARSE_PROMPT.format(
        today=_today_iso(date_hint),
        currency_hint=currency_hint or "USD",
        transcript=transcript,
    )

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "timeout": 30,
    }
    if ai_config.get("api_key"):
        kwargs["api_key"] = ai_config["api_key"]
    if ai_config.get("provider_url") and provider_name != "openai":
        kwargs["api_base"] = ai_config["provider_url"]

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: completion(**kwargs))
    content = response.choices[0].message.content if response and response.choices else None
    if not content:
        return None

    if not isinstance(content, str):
        content = json.dumps(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))

    return _coerce_response(parsed, transcript, currency_hint, date_hint, "ai")


async def parse_voice_expense(
    db: Session,
    transcript: str,
    currency_hint: Optional[str] = None,
    date_hint: Optional[date] = None,
) -> ExpenseVoiceParseResponse:
    cleaned = transcript.strip()
    if not cleaned:
        raise ValueError("Transcript is required")

    try:
        ai_result = await _parse_with_ai(db, cleaned, currency_hint, date_hint)
        if ai_result:
            return ai_result
    except Exception as exc:
        logger.warning("AI voice parsing failed, falling back to heuristics: %s", exc)

    return parse_voice_expense_heuristic(cleaned, currency_hint=currency_hint, date_hint=date_hint)


def build_expense_create_payload_from_voice(parsed: ExpenseVoiceParseResponse) -> Dict[str, Any]:
    return {
        "amount": parsed.amount,
        "currency": parsed.currency,
        "expense_date": parsed.expense_date,
        "category": parsed.category,
        "vendor": parsed.vendor,
        "notes": parsed.notes,
        "status": ExpenseStatus.RECORDED.value,
    }
