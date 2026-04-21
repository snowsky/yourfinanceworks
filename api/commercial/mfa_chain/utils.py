from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pyotp

from core.models.models import MasterUser
from core.schemas.user import UserRead
from core.utils.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

logger = logging.getLogger(__name__)


try:
    from mfa_chain_orchestrator import MFAChainBreached, MFAOrchestrator, Policy
except ImportError:
    repo_root = Path(__file__).resolve().parents[3]
    local_src = repo_root / "mfa-chain-orchestrator" / "src"
    if local_src.exists():
        sys.path.insert(0, str(local_src))
    from mfa_chain_orchestrator import MFAChainBreached, MFAOrchestrator, Policy


MFA_SESSION_TTL_SECONDS = 600

SUPPORTED_FACTORS = {
    "google_auth": {"id": "google_auth", "label": "Google Authenticator", "type": "totp"},
    "ms_auth": {"id": "ms_auth", "label": "Microsoft Authenticator", "type": "totp"},
}

MFA_LOGIN_SESSIONS: dict[str, dict[str, Any]] = {}


def _prune_sessions() -> None:
    cutoff = time.time() - MFA_SESSION_TTL_SECONDS
    stale_ids = [sid for sid, payload in MFA_LOGIN_SESSIONS.items() if payload.get("created_at", 0) < cutoff]
    for sid in stale_ids:
        MFA_LOGIN_SESSIONS.pop(sid, None)


def normalize_factor_ids(factor_ids: list[str] | None) -> list[str]:
    if not factor_ids:
        return []
    deduped: list[str] = []
    for factor_id in factor_ids:
        if factor_id not in SUPPORTED_FACTORS:
            continue
        if factor_id in deduped:
            continue
        deduped.append(factor_id)
    return deduped


def _get_user_policy(user: MasterUser) -> Optional[Policy]:
    enabled = bool(getattr(user, "mfa_chain_enabled", False))
    if not enabled:
        return None

    factor_ids = normalize_factor_ids(getattr(user, "mfa_chain_factors", None) or [])
    if not factor_ids:
        raise ValueError("MFA setup incomplete: no authenticators selected in sequence.")

    mode = getattr(user, "mfa_chain_mode", "fixed")
    if mode not in ("fixed", "random"):
        mode = "fixed"

    factors = [SUPPORTED_FACTORS[factor_id] for factor_id in factor_ids]
    return Policy(mode=mode, required_steps=len(factors), factors=factors)


def get_user_mfa_settings(user: MasterUser) -> dict[str, Any]:
    factor_ids = normalize_factor_ids(getattr(user, "mfa_chain_factors", None) or [])
    secrets = getattr(user, "mfa_factor_secrets", None) or {}

    return {
        "enabled": bool(getattr(user, "mfa_chain_enabled", False)),
        "mode": getattr(user, "mfa_chain_mode", "fixed"),
        "factors": factor_ids,
        "enrolled_factors": [factor_id for factor_id in factor_ids if secrets.get(factor_id)],
        "supported_factors": list(SUPPORTED_FACTORS.values()),
    }


def create_mfa_enrollment(user: MasterUser, factor_id: str) -> dict[str, Any]:
    if factor_id not in SUPPORTED_FACTORS:
        raise ValueError(f"Unsupported factor_id: {factor_id}")

    secrets = dict(getattr(user, "mfa_factor_secrets", None) or {})
    secret = pyotp.random_base32()
    secrets[factor_id] = secret

    factor = SUPPORTED_FACTORS[factor_id]
    issuer = os.getenv("MFA_ISSUER_NAME", "YourFinanceWORKS")
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=f"{issuer}-{factor['label']}")

    return {
        "factor_id": factor_id,
        "factor_label": factor["label"],
        "secret": secret,
        "otpauth_uri": otpauth_uri,
        "qr_png_base64": _encode_qr_png_base64(otpauth_uri),
        "secrets": secrets,
    }


def validate_settings_payload(payload: dict[str, Any], secrets: dict[str, str]) -> tuple[bool, str]:
    enabled = bool(payload.get("enabled", False))
    if not enabled:
        return True, ""

    factors = normalize_factor_ids(payload.get("factors", []))
    if not factors:
        return False, "Enable at least one authenticator before enabling MFA chain."

    missing = [factor_id for factor_id in factors if not secrets.get(factor_id)]
    if missing:
        return False, f"Missing enrollment for factors: {', '.join(missing)}"

    mode = payload.get("mode", "fixed")
    if mode not in ("fixed", "random"):
        return False, "Invalid mode. Must be 'fixed' or 'random'."

    return True, ""


def maybe_start_mfa_session(user: MasterUser, next_path: str = "/dashboard") -> Optional[dict[str, Any]]:
    _prune_sessions()
    try:
        policy = _get_user_policy(user)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"MFA setup incomplete: {exc}") from exc
    if policy is None:
        return None

    secrets = dict(getattr(user, "mfa_factor_secrets", None) or {})
    for factor in policy.factors:
        if not secrets.get(factor.id):
            logger.warning("MFA enabled for user %s but factor %s is not enrolled", user.email, factor.id)
            raise ValueError(f"MFA setup incomplete: missing enrollment for factor '{factor.id}'")

    try:
        orchestrator = MFAOrchestrator(policy)
        chain = orchestrator.initialize_attempt()
    except Exception as exc:
        raise ValueError(f"MFA setup incomplete: {exc}") from exc
    session_id = str(uuid4())
    MFA_LOGIN_SESSIONS[session_id] = {
        "created_at": time.time(),
        "user_id": user.id,
        "next": next_path,
        "orchestrator": orchestrator,
        "factor_secrets": secrets,
    }
    return {
        "session_id": session_id,
        "current_factor_id": chain[0].id,
        "current_factor_label": chain[0].label,
    }


def get_session_prompt(session_id: str) -> dict[str, str]:
    _prune_sessions()
    state = MFA_LOGIN_SESSIONS.get(session_id)
    if state is None:
        raise KeyError("Unknown or expired MFA session")

    orchestrator: MFAOrchestrator = state["orchestrator"]
    current = orchestrator.current_factor
    return {
        "session_id": session_id,
        "current_factor_id": current.id,
        "current_factor_label": current.label,
    }


def verify_mfa_step(session_id: str, factor_id: str, user_input: str, window: int = 1) -> dict[str, Any]:
    _prune_sessions()
    state = MFA_LOGIN_SESSIONS.get(session_id)
    if state is None:
        raise KeyError("Unknown or expired MFA session")

    orchestrator: MFAOrchestrator = state["orchestrator"]
    secrets: dict[str, str] = state["factor_secrets"]
    try:
        expected_factor_id = orchestrator.current_factor.id
        secret = secrets[expected_factor_id]
        result = orchestrator.verify_step(
            secret=secret,
            user_input=user_input,
            window=max(0, window),
            factor_id=factor_id,
        )
    except MFAChainBreached as exc:
        raise ValueError(str(exc)) from exc

    if not result.success and result.next_factor_label == "RESET":
        chain = orchestrator.initialize_attempt()
        return {
            "success": False,
            "is_complete": False,
            "next_factor_id": chain[0].id,
            "next_factor_label": chain[0].label,
            "reset": True,
        }

    payload: dict[str, Any] = {
        "success": result.success,
        "is_complete": result.is_complete,
        "next_factor_label": result.next_factor_label,
        "reset": False,
    }
    if not result.is_complete:
        payload["next_factor_id"] = orchestrator.current_factor.id
    return payload


def finalize_mfa_login(session_id: str, user: MasterUser) -> dict[str, Any]:
    MFA_LOGIN_SESSIONS.pop(session_id, None)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


def build_user_b64(user: MasterUser) -> str:
    user_payload = UserRead.model_validate(user).model_dump()

    def _datetime_serializer(obj: Any) -> str:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return base64.urlsafe_b64encode(json.dumps(user_payload, default=_datetime_serializer).encode()).decode()


def _encode_qr_png_base64(data: str) -> str:
    try:
        import qrcode  # type: ignore
    except ImportError:
        return ""

    image = qrcode.make(data)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
