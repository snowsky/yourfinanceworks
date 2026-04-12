"""Voice-to-expense: audio transcription and NLP extraction from spoken expense notes."""

import io
import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_AUDIO_TYPES = {
    "audio/m4a", "audio/mp4", "audio/mpeg", "audio/wav",
    "audio/x-m4a", "audio/ogg", "audio/webm",
}
_MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Whisper limit


# ── Pydantic models ───────────────────────────────────────────────────────────

class ParseVoiceRequest(BaseModel):
    transcript: str


class ParsedVoiceExpenseResponse(BaseModel):
    transcript: str
    amount: Optional[float] = None
    currency: str = "USD"
    expense_date: str
    category: str
    vendor: Optional[str] = None
    notes: Optional[str] = None
    confidence: float
    parser_used: str


class TranscribeResponse(BaseModel):
    transcript: str
    success: bool


# ── Config helper ─────────────────────────────────────────────────────────────

def _get_ai_config(db: Session) -> Optional[Any]:
    """Return an AI config object (DB first, env-var fallback) for voice/OCR use."""
    try:
        from commercial.ai.services.ai_config_service import AIConfigService

        config_dict = AIConfigService.get_ai_config(db, component="ocr", require_ocr=False)
        if not config_dict:
            return None

        class _AIConfig:
            def __init__(self, d: Dict[str, Any]) -> None:
                self.provider_name: str = d.get("provider_name", "")
                self.model_name: str = d.get("model_name", "")
                self.api_key: Optional[str] = d.get("api_key")
                self.provider_url: Optional[str] = d.get("provider_url")

        return _AIConfig(config_dict)
    except Exception as exc:
        logger.warning("Could not load AI config for voice parsing: %s", exc)
        return None


def _build_litellm_kwargs(ai_config: Any, model_name: str, **extra: Any) -> Dict[str, Any]:
    """Build litellm call kwargs from an AI config object, mirroring the chat/OCR pattern."""
    kwargs: Dict[str, Any] = {"model": model_name, **extra}
    if ai_config.provider_name == "ollama" and ai_config.provider_url:
        kwargs["api_base"] = ai_config.provider_url
    elif ai_config.api_key:
        kwargs["api_key"] = ai_config.api_key
    if ai_config.provider_url and ai_config.provider_name != "ollama":
        kwargs["api_base"] = ai_config.provider_url
    return kwargs


# ── Heuristic fallback parser ─────────────────────────────────────────────────

def _heuristic_parse(transcript: str) -> dict:
    """Rule-based fallback parser for common expense phrases."""
    text = transcript.lower().strip()

    # Amount + currency
    amount: Optional[float] = None
    currency = "USD"
    m = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text) or re.search(
        r"(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd)\b", text
    )
    if m:
        amount = float(m.group(1))
    eur = re.search(r"€\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:euros?|eur)\b", text)
    if eur:
        amount = float(eur.group(1) or eur.group(2))
        currency = "EUR"
    gbp = re.search(r"£\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:pounds?|gbp)\b", text)
    if gbp:
        amount = float(gbp.group(1) or gbp.group(2))
        currency = "GBP"

    # Date
    today = date.today()
    expense_date = (today - timedelta(days=1)).isoformat() if "yesterday" in text else today.isoformat()

    # Category via keyword map
    category = "General"
    _CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
        (("lunch", "dinner", "breakfast", "coffee", "food", "meal", "restaurant", "cafe", "eat", "pizza", "sushi"), "Meals"),
        (("uber", "lyft", "taxi", "cab", "flight", "hotel", "airbnb", "train", "bus", "gas", "fuel", "parking", "transit"), "Travel"),
        (("office", "stationery", "paper", "pen", "printer", "supplies"), "Office Supplies"),
        (("software", "subscription", "saas", "app", "license", "adobe", "notion", "slack", "github"), "Software"),
        (("phone", "internet", "wifi", "data", "telecom", "mobile"), "Telecommunications"),
        (("aws", "azure", "gcp", "hosting", "server", "cloud", "infra"), "Infrastructure"),
        (("client", "meeting", "entertainment", "event", "conference"), "Entertainment"),
    ]
    for keywords, cat in _CATEGORY_KEYWORDS:
        if any(kw in text for kw in keywords):
            category = cat
            break

    # Vendor via "at <Vendor>" pattern
    vendor: Optional[str] = None
    vm = re.search(
        r"\bat\s+([A-Z][A-Za-z\s'&.-]+?)(?:\s+(?:today|yesterday|for|on|with)\b|[,.]|$)",
        transcript,
    )
    if vm:
        vendor = vm.group(1).strip()

    return dict(
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=vendor,
        notes=None,
        confidence=0.6 if amount else 0.35,
        parser_used="heuristic",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/parse-voice", response_model=ParsedVoiceExpenseResponse)
async def parse_voice_expense(
    request: ParseVoiceRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Parse a spoken expense transcript into structured expense fields.

    Uses the active AI provider from Settings first, falls back to environment
    variables (LLM_MODEL_EXPENSES / OLLAMA_MODEL), then to a rule-based heuristic
    parser if no LLM is reachable.
    """
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    ai_config = _get_ai_config(db)

    if ai_config:
        try:
            from litellm import acompletion
            from commercial.ai.services.ai_config_service import AIConfigService

            model_name = (
                f"ollama/{ai_config.model_name}"
                if ai_config.provider_name == "ollama"
                else ai_config.model_name
            )
            today_str = date.today().isoformat()
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are an expense parser. Today is {today_str}. "
                        "Extract expense fields from natural language. "
                        "Reply ONLY with a compact JSON object — no markdown, no code fences:\n"
                        '{"amount":<number|null>,"currency":"<ISO-4217>","expense_date":"<YYYY-MM-DD>",'
                        '"category":"<string>","vendor":<string|null>,"notes":<string|null>,'
                        '"confidence":<0.0-1.0>}'
                    ),
                },
                {"role": "user", "content": f"Parse this expense: {transcript}"},
            ]
            base_params = AIConfigService.get_model_parameters(model_name, max_tokens=256, temperature=0.1)
            kwargs = _build_litellm_kwargs(ai_config, model_name, messages=messages, **base_params)

            response = await acompletion(**kwargs)
            raw = (response.choices[0].message.content or "").strip()
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)

            return ParsedVoiceExpenseResponse(
                transcript=transcript,
                amount=parsed.get("amount"),
                currency=parsed.get("currency", "USD"),
                expense_date=parsed.get("expense_date", date.today().isoformat()),
                category=parsed.get("category", "General"),
                vendor=parsed.get("vendor"),
                notes=parsed.get("notes"),
                confidence=float(parsed.get("confidence", 0.85)),
                parser_used="llm",
            )
        except Exception as exc:
            logger.warning("LLM voice parsing failed, using heuristic fallback: %s", exc)
    else:
        logger.info("No AI config available for voice parsing, using heuristic fallback")

    result = _heuristic_parse(transcript)
    return ParsedVoiceExpenseResponse(transcript=transcript, **result)


@router.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Transcribe a recorded audio file to text using Whisper via LiteLLM.

    Uses the API key from the active AI provider in Settings (or env-var fallback).
    Requires an OpenAI-compatible endpoint with access to a Whisper model, or a
    locally hosted Whisper-compatible endpoint.
    """
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_AUDIO_TYPES and not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type '{content_type}'. Supported: m4a, mp4, mp3, wav, ogg, webm.",
        )

    contents = await file.read()
    if len(contents) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large. Maximum size is 25 MB.")

    ai_config = _get_ai_config(db)

    try:
        from litellm import atranscription
        import os

        # Whisper model: allow override via env, default to whisper-1
        whisper_model = os.environ.get("WHISPER_MODEL", "whisper-1")

        audio_buf = io.BytesIO(contents)
        audio_buf.name = file.filename or "recording.m4a"

        kwargs: Dict[str, Any] = dict(model=whisper_model, file=audio_buf)

        # Whisper always runs against an OpenAI-compatible endpoint.
        # Resolution order:
        #   1. OPENAI_API_KEY  — dedicated key for Whisper (works alongside Ollama for parse-voice)
        #   2. Active AI config key from Settings (if provider is not Ollama)
        #   3. LLM_API_KEY / AI_API_KEY env vars
        import os as _os
        whisper_key = (
            _os.environ.get("OPENAI_API_KEY")
            or (ai_config.api_key if ai_config and ai_config.provider_name != "ollama" else None)
            or _os.environ.get("LLM_API_KEY")
            or _os.environ.get("AI_API_KEY")
        )
        if whisper_key:
            kwargs["api_key"] = whisper_key

        # Custom API base (e.g. local Whisper endpoint) if configured
        if ai_config and ai_config.provider_url and ai_config.provider_name != "ollama":
            kwargs["api_base"] = ai_config.provider_url

        response = await atranscription(**kwargs)
        return TranscribeResponse(transcript=response.text, success=True)

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Transcription service not available (litellm not installed).",
        )
    except Exception as exc:
        logger.error("Audio transcription failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Transcription failed: {exc}. Ensure WHISPER_MODEL and an API key are configured.",
        )
