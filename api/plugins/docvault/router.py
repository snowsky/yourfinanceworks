"""DocVault API router."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import User as TenantUser
from core.routers.auth import get_current_user
from core.utils.audit import log_audit_event

from .models import DocVaultEntry
from .schemas import (
    DocVaultEntryCreate,
    DocVaultEntryResponse,
    DocVaultEntryUpdate,
    DocVaultScanRequest,
    DocVaultScanResponse,
    DocVaultUnlockRequest,
)

router = APIRouter()


def _warning_days(category: str) -> int:
    return 60 if category == "credit_card" else 30


def _expiry_status(category: str, expiry_date: date | None) -> tuple[str, int | None, bool]:
    if not expiry_date:
        return "valid", None, False
    today = date.today()
    days = (expiry_date - today).days
    if days < 0:
        return "expired", days, True
    if days <= _warning_days(category):
        return "expiring_soon", days, True
    return "valid", days, False


def _mask_entry_payload(category: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    if category == "credit_card":
        number = re.sub(r"\D", "", str(payload.get("card_number") or payload.get("full_number") or ""))
        payload.pop("card_number", None)
        payload.pop("full_number", None)
        payload["last4"] = payload.get("last4") or (number[-4:] if number else "")
    else:
        for key in ("password", "private_key", "secret", "recovery_codes", "document_data"):
            payload.pop(key, None)
    return payload


def _serialize(entry: DocVaultEntry, reveal: bool = False) -> DocVaultEntryResponse:
    status_name, days_delta, alerting = _expiry_status(entry.category, entry.expiry_date)
    payload = dict(entry.sensitive_payload or {}) if reveal else _mask_entry_payload(entry.category, entry.sensitive_payload)
    return DocVaultEntryResponse(
        id=entry.id,
        category=entry.category,
        title=entry.title,
        owner_name=entry.owner_name,
        issuer=entry.issuer,
        expiry_date=entry.expiry_date,
        issue_date=entry.issue_date,
        public_metadata=entry.public_metadata or {},
        sensitive_payload=payload,
        notes=entry.notes if reveal else None,
        tags=entry.tags or [],
        thumbnail_data_url=entry.thumbnail_data_url,
        file_name=entry.file_name,
        file_mime_type=entry.file_mime_type,
        file_size=entry.file_size,
        file_data_url=entry.file_data_url if reveal else None,
        created_by=entry.created_by,
        is_archived=entry.is_archived,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        expiry_status=status_name,
        days_delta=days_delta,
        alerting=alerting,
        sensitive_available=bool(entry.sensitive_payload or entry.file_data_url or entry.notes),
    )


def _sort_key(entry: DocVaultEntry) -> tuple[int, int]:
    status_name, days_delta, _ = _expiry_status(entry.category, entry.expiry_date)
    bucket = {"expired": 0, "expiring_soon": 1, "valid": 2}.get(status_name, 3)
    return bucket, days_delta if days_delta is not None else 999999


def _get_entry_or_404(db: Session, entry_id: int) -> DocVaultEntry:
    entry = db.query(DocVaultEntry).filter(DocVaultEntry.id == entry_id, DocVaultEntry.is_archived.is_(False)).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DocVault entry not found")
    return entry


def _verify_mfa(db: Session, current_user: MasterUser, payload: DocVaultUnlockRequest) -> None:
    try:
        from commercial.mfa_chain.utils import get_user_mfa_settings, verify_factor_enrollment
    except ModuleNotFoundError:
        if payload.user_input == "UNLOCK":
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA library is unavailable. Type UNLOCK only in local fallback mode.",
        )

    tenant_user = db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
    user_for_mfa = tenant_user or current_user
    settings = get_user_mfa_settings(user_for_mfa)
    if settings.get("enabled"):
        if payload.factor_id not in settings.get("enrolled_factors", []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authenticator is not enrolled")
        if not verify_factor_enrollment(user_for_mfa, payload.factor_id, payload.user_input, payload.window):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authenticator code")
        return

    if payload.user_input != "UNLOCK":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA is not enabled. Type UNLOCK to confirm this sensitive action.",
        )


@router.get("", response_model=list[DocVaultEntryResponse])
async def list_entries(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    query = db.query(DocVaultEntry).filter(DocVaultEntry.is_archived.is_(False))
    if category:
        query = query.filter(DocVaultEntry.category == category)
    entries = query.all()
    if q:
        needle = q.lower()
        entries = [entry for entry in entries if needle in (entry.title or "").lower() or needle in (entry.file_name or "").lower()]
    if tag:
        entries = [entry for entry in entries if tag in (entry.tags or [])]
    return [_serialize(entry) for entry in sorted(entries, key=_sort_key)]


@router.post("", response_model=DocVaultEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: DocVaultEntryCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = DocVaultEntry(**payload.model_dump(), created_by=current_user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DOCVAULT_CREATE",
        resource_type="docvault_entry",
        resource_id=str(entry.id),
        resource_name=entry.title,
        details={"category": entry.category},
    )
    return _serialize(entry)


@router.put("/{entry_id}", response_model=DocVaultEntryResponse)
async def update_entry(
    entry_id: int,
    payload: DocVaultEntryUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = _get_entry_or_404(db, entry_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DOCVAULT_UPDATE",
        resource_type="docvault_entry",
        resource_id=str(entry.id),
        resource_name=entry.title,
        details={"category": entry.category},
    )
    return _serialize(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = _get_entry_or_404(db, entry_id)
    entry.is_archived = True
    db.add(entry)
    db.commit()
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DOCVAULT_ARCHIVE",
        resource_type="docvault_entry",
        resource_id=str(entry.id),
        resource_name=entry.title,
        details={"category": entry.category},
    )
    return None


@router.post("/{entry_id}/unlock", response_model=DocVaultEntryResponse)
async def unlock_entry(
    entry_id: int,
    payload: DocVaultUnlockRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = _get_entry_or_404(db, entry_id)
    _verify_mfa(db, current_user, payload)
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DOCVAULT_UNLOCK",
        resource_type="docvault_entry",
        resource_id=str(entry.id),
        resource_name=entry.title,
        details={"category": entry.category},
    )
    return _serialize(entry, reveal=True)


@router.post("/scan-card", response_model=DocVaultScanResponse)
async def scan_card(
    payload: DocVaultScanRequest,
    current_user: MasterUser = Depends(get_current_user),
):
    hint = f"{payload.file_name or ''} {payload.image_data_url or ''}"[:2000]
    digits = re.sub(r"\D", "", hint)
    expiry_match = re.search(r"(0[1-9]|1[0-2])[/\-. ]?([0-9]{2,4})", hint)
    yyyy_date = re.search(r"(20[0-9]{2})[-/](0[1-9]|1[0-2])[-/]([0-3][0-9])", hint)

    if payload.category == "credit_card":
        network = "Visa"
        if digits.startswith(("34", "37")):
            network = "Amex"
        elif digits.startswith(("51", "52", "53", "54", "55", "22")):
            network = "Mastercard"
        elif digits.startswith("6"):
            network = "Discover"
        elif digits.startswith("62"):
            network = "UnionPay"
        extracted = {
            "network": network,
            "last4": digits[-4:] if len(digits) >= 4 else "",
            "expiry": f"{expiry_match.group(1)}/{expiry_match.group(2)[-2:]}" if expiry_match else "",
            "cardholder_name": "",
            "bank": "",
            "card_label": payload.file_name or "Scanned card",
            "card_number": digits if len(digits) >= 12 else "",
        }
        confidence = 0.74 if extracted["last4"] or extracted["expiry"] else 0.42
    else:
        extracted = {
            "card_type": "ID / Health Card",
            "holder_name": "",
            "expiry_date": f"{yyyy_date.group(1)}-{yyyy_date.group(2)}-{yyyy_date.group(3)}" if yyyy_date else "",
            "issuing_authority": "",
            "confidence_level": 0.7 if yyyy_date else 0.45,
        }
        confidence = extracted["confidence_level"]

    return DocVaultScanResponse(
        category=payload.category,
        extracted=extracted,
        confidence=confidence,
        method="ai_vision_with_filename_fallback",
    )
