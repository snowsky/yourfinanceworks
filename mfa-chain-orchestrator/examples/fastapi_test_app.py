"""Local FastAPI test app for mfa-chain-orchestrator.

This is intentionally simple and uses in-memory state only.
Do not use this as-is for production deployments.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyotp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from mfa_chain_orchestrator import MFAChainBreached, MFAOrchestrator, Policy

app = FastAPI(title="MFA Chain Orchestrator Test App")
EXAMPLES_DIR = Path(__file__).resolve().parent
UI_FILE = EXAMPLES_DIR / "ui.html"

policy = Policy(
    mode="fixed",
    required_steps=2,
    factors=[
        {"id": "google_auth", "label": "Google Authenticator", "type": "totp"},
        {"id": "ms_auth", "label": "Microsoft Authenticator", "type": "totp"},
    ],
)

factor_by_id = {factor.id: factor for factor in policy.factors}

# user_id -> {factor_secrets: {factor_id: secret}}
users: dict[str, dict[str, Any]] = {}

# session_id -> state
sessions: dict[str, dict[str, Any]] = {}


class EnrollmentResponse(BaseModel):
    user_id: str
    factor_id: str
    factor_label: str
    otpauth_uri: str
    secret: str
    qr_png_base64: str


class StartAttemptResponse(BaseModel):
    session_id: str
    current_factor_id: str
    current_factor_label: str


class VerifyRequest(BaseModel):
    session_id: str = Field(min_length=1)
    factor_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    window: int = Field(default=1, ge=0)


class VerifyResponse(BaseModel):
    success: bool
    is_complete: bool
    next_factor_label: str


def _get_or_create_user(user_id: str) -> dict[str, Any]:
    if user_id not in users:
        users[user_id] = {"factor_secrets": {}}
    return users[user_id]


def _required_factor_ids() -> set[str]:
    return {factor.id for factor in policy.factors[: policy.required_steps]}


def _encode_qr_png_base64(data: str) -> str:
    """Return base64 PNG for QR code if qrcode library is installed; else empty string."""
    try:
        import qrcode  # type: ignore
    except ImportError:
        return ""

    image = qrcode.make(data)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(UI_FILE)


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(UI_FILE)


@app.post("/users/{user_id}/factors/{factor_id}/enroll", response_model=EnrollmentResponse)
def enroll_factor(user_id: str, factor_id: str) -> EnrollmentResponse:
    factor = factor_by_id.get(factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"Unknown factor_id: {factor_id}")

    user = _get_or_create_user(user_id)
    secret = pyotp.random_base32()
    user["factor_secrets"][factor_id] = secret

    issuer = "mfa-chain-orchestrator-test"
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(name=user_id, issuer_name=issuer)
    qr_png_base64 = _encode_qr_png_base64(otpauth_uri)

    return EnrollmentResponse(
        user_id=user_id,
        factor_id=factor.id,
        factor_label=factor.label,
        otpauth_uri=otpauth_uri,
        secret=secret,
        qr_png_base64=qr_png_base64,
    )


@app.post("/users/{user_id}/attempt/start", response_model=StartAttemptResponse)
def start_attempt(user_id: str) -> StartAttemptResponse:
    user = users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Unknown user")

    factor_secrets: dict[str, str] = user["factor_secrets"]
    missing = sorted(_required_factor_ids() - set(factor_secrets.keys()))
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing enrollment for required factors: {', '.join(missing)}",
        )

    session_id = str(uuid4())
    orchestrator = MFAOrchestrator(policy)
    chain = orchestrator.initialize_attempt()

    sessions[session_id] = {
        "user_id": user_id,
        "orchestrator": orchestrator,
        "factor_secrets": factor_secrets,
    }

    return StartAttemptResponse(
        session_id=session_id,
        current_factor_id=chain[0].id,
        current_factor_label=chain[0].label,
    )


@app.get("/attempt/{session_id}/debug/current-code")
def debug_current_code(session_id: str) -> dict[str, str]:
    state = sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session")

    orchestrator: MFAOrchestrator = state["orchestrator"]
    factor_secrets: dict[str, str] = state["factor_secrets"]

    expected_factor_id = orchestrator.current_factor.id
    secret = factor_secrets[expected_factor_id]
    code = pyotp.TOTP(secret).now()
    return {"factor_id": expected_factor_id, "code": code}


@app.post("/attempt/verify", response_model=VerifyResponse)
def verify_attempt(payload: VerifyRequest) -> VerifyResponse:
    state = sessions.get(payload.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session")

    orchestrator: MFAOrchestrator = state["orchestrator"]
    factor_secrets: dict[str, str] = state["factor_secrets"]

    try:
        expected_factor_id = orchestrator.current_factor.id
        secret = factor_secrets[expected_factor_id]
        result = orchestrator.verify_step(
            secret=secret,
            user_input=payload.user_input,
            window=payload.window,
            factor_id=payload.factor_id,
        )
    except MFAChainBreached as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Any failure forces full restart from step 1.
    if not result.success and result.next_factor_label == "RESET":
        chain = orchestrator.initialize_attempt()
        return VerifyResponse(
            success=False,
            is_complete=False,
            next_factor_label=f"RESET -> restart with {chain[0].label}",
        )

    return VerifyResponse(
        success=result.success,
        is_complete=result.is_complete,
        next_factor_label=result.next_factor_label,
    )
