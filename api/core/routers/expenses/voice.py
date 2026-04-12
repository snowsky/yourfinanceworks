"""Voice-to-expense: audio transcription and NLP extraction from spoken expense notes."""

import io
import json
import logging
import os
import re
from datetime import date, timedelta
from typing import Optional

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
    if "yesterday" in text:
        expense_date = (today - timedelta(days=1)).isoformat()
    else:
        expense_date = today.isoformat()

    # Category via keyword map
    category = "General"
    _CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
        (("lunch", "dinner", "breakfast", "coffee", "food", "meal", "restaurant", "cafe", "eat", "pizza", "sushi"), "Meals"),
        (("uber", "lyft", "taxi", "cab", "flight", "hotel", "airbnb", "train", "bus", "gas", "fuel", "parking", "transit"), "Travel"),
        (("office", "stationery", "paper", "pen", "printer", "supplies"), "Office Supplies"),
        (("software", "subscription", "saas", "app", "license", "adobe", "notion", "slack", "github"), "Software"),
        (("phone", "internet", "wifi", "data", "telecom", "mobile", "plan"), "Telecommunications"),
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

    confidence = 0.6 if amount else 0.35
    return dict(
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=vendor,
        notes=None,
        confidence=confidence,
        parser_used="heuristic",
    )


@router.post("/parse-voice", response_model=ParsedVoiceExpenseResponse)
async def parse_voice_expense(
    request: ParseVoiceRequest,
    current_user: MasterUser = Depends(get_current_user),
):
    """Parse a spoken expense transcript into structured expense fields.

    Tries LLM extraction first; falls back to rule-based heuristic parser
    when the LLM is unavailable or returns malformed output.
    """
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    try:
        from litellm import acompletion

        model = (
            os.environ.get("LLM_MODEL_EXPENSES")
            or os.environ.get("OLLAMA_MODEL")
            or os.environ.get("AI_MODEL", "gpt-4o-mini")
        )
        api_base = os.environ.get("LLM_API_BASE") or os.environ.get("OLLAMA_API_BASE")
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("AI_API_KEY")

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
        kwargs: dict = dict(model=model, messages=messages, max_tokens=256, temperature=0.1)
        if api_base:
            kwargs["api_base"] = api_base
        if api_key:
            kwargs["api_key"] = api_key

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

    result = _heuristic_parse(transcript)
    return ParsedVoiceExpenseResponse(transcript=transcript, **result)


@router.post("/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: MasterUser = Depends(get_current_user),
):
    """Transcribe a recorded audio file to text using Whisper via LiteLLM.

    Requires an OpenAI-compatible API key with access to the whisper-1 model,
    or a locally hosted Whisper-compatible endpoint.
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

    try:
        from litellm import atranscription

        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("AI_API_KEY")
        api_base = os.environ.get("LLM_API_BASE") or os.environ.get("OLLAMA_API_BASE")
        model = os.environ.get("WHISPER_MODEL", "whisper-1")

        audio_buf = io.BytesIO(contents)
        audio_buf.name = file.filename or "recording.m4a"

        kwargs: dict = dict(model=model, file=audio_buf)
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        response = await atranscription(**kwargs)
        return TranscribeResponse(transcript=response.text, success=True)

    except ImportError:
        raise HTTPException(status_code=503, detail="Transcription service not available (litellm not installed).")
    except Exception as exc:
        logger.error("Audio transcription failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Transcription failed: {exc}. Check that WHISPER_MODEL and LLM_API_KEY are configured.",
        )
