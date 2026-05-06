# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Core module of YourFinanceWORKS.
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
# See LICENSE-AGPLv3.txt for details.

"""Device/browser login flow for first-party CLI clients."""

from __future__ import annotations

import os
import secrets
import string
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models.database import get_master_db
from core.models.models import MasterUser, Tenant
from core.routers.auth._shared import AUTH_COOKIE_NAME
from core.utils.auth import ALGORITHM, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

router = APIRouter(prefix="/device")

DEVICE_CODE_TTL_SECONDS = 600
DEVICE_POLL_INTERVAL_SECONDS = 5
_device_sessions: dict[str, dict[str, Any]] = {}
_device_lock = Lock()


class DeviceTokenRequest(BaseModel):
    device_code: str


def _prune_expired_sessions() -> None:
    now = datetime.now(timezone.utc)
    expired = [
        device_code
        for device_code, session in _device_sessions.items()
        if session["expires_at"] <= now or session.get("consumed_at")
    ]
    for device_code in expired:
        _device_sessions.pop(device_code, None)


def _generate_user_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(2)
    )


def _api_base_url(request: Request) -> str:
    configured = os.getenv("INVOICE_API_BASE_URL") or os.getenv("API_BASE_URL")
    if configured:
        return configured.rstrip("/").removesuffix("/api/v1").removesuffix("/api")
    return str(request.base_url).rstrip("/").removesuffix("/api/v1")


def _ui_base_url() -> str:
    return (os.getenv("UI_BASE_URL") or "http://localhost:8080").rstrip("/")


def _current_browser_user(request: Request, db: Session) -> MasterUser | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        return None
    if not email:
        return None
    return db.query(MasterUser).filter(MasterUser.email == email).first()


@router.post("/start")
async def start_device_login(request: Request):
    """Start a CLI browser/device login session."""
    with _device_lock:
        _prune_expired_sessions()
        device_code = secrets.token_urlsafe(32)
        user_code = _generate_user_code()
        while any(session["user_code"] == user_code for session in _device_sessions.values()):
            user_code = _generate_user_code()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEVICE_CODE_TTL_SECONDS)
        _device_sessions[device_code] = {
            "user_code": user_code,
            "expires_at": expires_at,
            "approved_email": None,
            "approved_at": None,
            "consumed_at": None,
        }

    api_base = _api_base_url(request)
    verification_uri = f"{api_base}/api/v1/auth/device/verify"
    verification_uri_complete = f"{verification_uri}?user_code={user_code}"
    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": verification_uri_complete,
        "expires_in": DEVICE_CODE_TTL_SECONDS,
        "interval": DEVICE_POLL_INTERVAL_SECONDS,
    }


@router.get("/verify", response_class=HTMLResponse)
async def verify_device_login(
    request: Request,
    user_code: str,
    db: Session = Depends(get_master_db),
):
    """Approve a device login from an already-authenticated browser session."""
    normalized_code = user_code.strip().upper()
    with _device_lock:
        _prune_expired_sessions()
        session = next(
            (item for item in _device_sessions.values() if item["user_code"] == normalized_code),
            None,
        )
    if not session:
        return HTMLResponse("<h1>Device login expired</h1><p>Return to the CLI and start login again.</p>", status_code=404)

    user = _current_browser_user(request, db)
    if not user:
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        login_url = f"{_ui_base_url()}/login?next={quote(next_path, safe='')}"
        return HTMLResponse(
            f"""
            <h1>Sign in to approve CLI access</h1>
            <p>Device code: <strong>{normalized_code}</strong></p>
            <p><a href="{login_url}">Continue to login</a>, then return to this page.</p>
            """,
            status_code=401,
        )

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not user.is_active or not tenant or not tenant.is_active:
        return HTMLResponse("<h1>Device login denied</h1><p>Your account or organization is disabled.</p>", status_code=403)

    with _device_lock:
        session["approved_email"] = user.email
        session["approved_at"] = datetime.now(timezone.utc)

    return HTMLResponse(
        """
        <h1>CLI login approved</h1>
        <p>You can close this browser tab and return to the CLI.</p>
        """
    )


@router.post("/token")
async def exchange_device_token(
    request: DeviceTokenRequest,
    db: Session = Depends(get_master_db),
):
    """Poll for the token after the browser approves a device login."""
    with _device_lock:
        _prune_expired_sessions()
        session = _device_sessions.get(request.device_code)
        if not session:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expired_token")
        if not session.get("approved_email"):
            raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="authorization_pending")
        session["consumed_at"] = datetime.now(timezone.utc)

    user = db.query(MasterUser).filter(MasterUser.email == session["approved_email"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_user")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
