"""
External API authentication and authorization routes.
"""

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from core.models.database import get_master_db, get_db
from core.models.models import MasterUser, Tenant
from core.models.api_models import APIClient
from core.schemas.api_schemas import (
    APIKeyCreateRequest, APIKeyResponse, APIClientResponse, APIClientUpdateRequest,
    OAuthClientCreateRequest, OAuthClientResponse, UserPermissionsRequest
)
from core.services.external_api_auth_service import ExternalAPIAuthService, Permission
from core.routers.auth import get_current_user
from core.utils.rbac import require_admin
from core.utils.feature_gate import require_feature


router = APIRouter(prefix="/external-auth", tags=["external-api-auth"])
security = HTTPBearer()
auth_service = ExternalAPIAuthService()


def require_admin_permissions(current_user: MasterUser = Depends(get_current_user)) -> MasterUser:
    """Require admin permissions for the current user."""
    # Check if user has admin role
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required"
        )
    
    return current_user


def _generate_api_key() -> str:
    """Generate a secure API key."""
    return f"ak_{secrets.token_urlsafe(32)}"


def _hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def _get_api_key_prefix(api_key: str) -> str:
    """Get the first 7 characters of API key for identification."""
    return api_key[:7] + "..."


def _resolve_api_tier(tenant_db: Session) -> dict:
    """Resolve API access config from tenant's licensed features."""
    return {
        "domains": ["invoice", "expense", "statement", "portfolio"],
        "rate_limit_per_minute": 120,
        "rate_limit_per_hour": 2000,
        "rate_limit_per_day": 20000,
    }


@router.post("/api-keys", response_model=APIKeyResponse)
@require_feature("external_api")
async def create_api_key(
    request_data: APIKeyCreateRequest,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db)  # Use tenant DB for feature checking
):
    """
    Create a new API key for external system integration.

    **Business License Required**: This feature is only available with a business license.
    """
    # Resolve the tier from the tenant's license
    tier_config = _resolve_api_tier(tenant_db)
    tier_domains = tier_config["domains"]

    # Validate and normalize document types
    valid_types = ["invoice", "expense", "statement", "portfolio"]
    normalized_types = []
    for doc_type in request_data.allowed_document_types:
        # Normalize to lowercase for consistency
        normalized = doc_type.lower().strip() if isinstance(doc_type, str) else doc_type
        if normalized not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type: {doc_type}. Must be one of: {valid_types}"
            )
        # Strip domains not allowed by tier
        if normalized in tier_domains:
            normalized_types.append(normalized)

    # Use normalized types (remove duplicates while preserving order)
    seen = set()
    unique_normalized = []
    for doc_type in normalized_types:
        if doc_type not in seen:
            seen.add(doc_type)
            unique_normalized.append(doc_type)
    request_data.allowed_document_types = unique_normalized

    # Check API key limit (max 2 per user)
    existing_clients = db.query(APIClient).filter(
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id,
        APIClient.is_active == True
    ).count()

    if existing_clients >= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 2 API keys allowed per user"
        )

    # Generate API key and client ID
    api_key = _generate_api_key()
    api_key_hash = _hash_api_key(api_key)
    api_key_prefix = _get_api_key_prefix(api_key)
    client_id = f"client_{secrets.token_urlsafe(16)}"

    # Set expiration if specified
    expires_at = None
    if request_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request_data.expires_in_days)

    custom_quotas = {
        "allowed_domains": tier_domains,
        "rate_limit_per_minute": tier_config["rate_limit_per_minute"],
        "rate_limit_per_hour": tier_config["rate_limit_per_hour"],
        "rate_limit_per_day": tier_config["rate_limit_per_day"],
    }

    # Create API client record
    api_client = APIClient(
        client_id=client_id,
        client_name=request_data.client_name,
        client_description=request_data.client_description,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key_prefix,
        allowed_document_types=request_data.allowed_document_types,
        max_transaction_amount=request_data.max_transaction_amount,
        rate_limit_per_minute=tier_config["rate_limit_per_minute"],
        rate_limit_per_hour=tier_config["rate_limit_per_hour"],
        rate_limit_per_day=tier_config["rate_limit_per_day"],
        allowed_ip_addresses=request_data.allowed_ip_addresses,
        webhook_url=request_data.webhook_url,
        is_sandbox=request_data.is_sandbox,
        custom_quotas=custom_quotas,
        created_by=current_user.id,
        terms_accepted_at=datetime.now(timezone.utc),
        privacy_policy_accepted_at=datetime.now(timezone.utc)
    )

    db.add(api_client)
    db.commit()
    db.refresh(api_client)

    return APIKeyResponse(
        client_id=client_id,
        api_key=api_key,  # Only returned once during creation
        api_key_prefix=api_key_prefix,
        client_name=request_data.client_name,
        allowed_document_types=request_data.allowed_document_types,
        rate_limits={
            "per_minute": tier_config["rate_limit_per_minute"],
            "per_hour": tier_config["rate_limit_per_hour"],
            "per_day": tier_config["rate_limit_per_day"]
        },
        expires_at=expires_at,
        created_at=api_client.created_at
    )


@router.get("/api-keys", response_model=List[APIClientResponse])
@require_feature("external_api")
async def list_api_keys(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db),  # Use tenant DB for feature checking
    include_inactive: bool = False
):
    """List API keys owned by the current user."""
    
    query = db.query(APIClient).filter(
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id
    )
    
    if not include_inactive:
        query = query.filter(APIClient.is_active == True)
    
    api_clients = query.order_by(APIClient.created_at.desc()).all()
    
    return [
        APIClientResponse(
            id=client.id,
            client_id=client.client_id,
            client_name=client.client_name,
            client_description=client.client_description,
            user_id=client.user_id,
            api_key_prefix=client.api_key_prefix,
            allowed_document_types=client.allowed_document_types,
            max_transaction_amount=float(client.max_transaction_amount) if client.max_transaction_amount else None,
            rate_limit_per_minute=client.rate_limit_per_minute,
            rate_limit_per_hour=client.rate_limit_per_hour,
            rate_limit_per_day=client.rate_limit_per_day,
            is_active=client.is_active,
            is_sandbox=client.is_sandbox,
            total_requests=client.total_requests,
            total_transactions_submitted=client.total_transactions_submitted,
            last_used_at=client.last_used_at,
            created_at=client.created_at,
            updated_at=client.updated_at,
            custom_quotas=client.custom_quotas
        )
        for client in api_clients
    ]


@router.get("/api-keys/{client_id}", response_model=APIClientResponse)
@require_feature("external_api")
async def get_api_key(
    client_id: str,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db)  # Use tenant DB for feature checking
):
    """Get details of a specific API key."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    return APIClientResponse(
        id=api_client.id,
        client_id=api_client.client_id,
        client_name=api_client.client_name,
        client_description=api_client.client_description,
        user_id=api_client.user_id,
        api_key_prefix=api_client.api_key_prefix,
        allowed_document_types=api_client.allowed_document_types,
        max_transaction_amount=float(api_client.max_transaction_amount) if api_client.max_transaction_amount else None,
        rate_limit_per_minute=api_client.rate_limit_per_minute,
        rate_limit_per_hour=api_client.rate_limit_per_hour,
        rate_limit_per_day=api_client.rate_limit_per_day,
        is_active=api_client.is_active,
        is_sandbox=api_client.is_sandbox,
        total_requests=api_client.total_requests,
        total_transactions_submitted=api_client.total_transactions_submitted,
        last_used_at=api_client.last_used_at,
        created_at=api_client.created_at,
        updated_at=api_client.updated_at,
        custom_quotas=api_client.custom_quotas
    )


@router.put("/api-keys/{client_id}", response_model=APIClientResponse)
@require_feature("external_api")
async def update_api_key(
    client_id: str,
    request_data: APIClientUpdateRequest,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db)  # Use tenant DB for feature checking
):
    """Update an existing API key configuration."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    # Update fields if provided
    update_data = request_data.dict(exclude_unset=True)
    
    # Validate document types if provided
    if "allowed_document_types" in update_data:
        valid_types = ["invoice", "expense", "statement", "portfolio"]
        for doc_type in update_data["allowed_document_types"]:
            if doc_type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document type: {doc_type}. Must be one of: {valid_types}"
                )
    
    for field, value in update_data.items():
        setattr(api_client, field, value)
    
    api_client.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(api_client)
    
    return APIClientResponse(
        id=api_client.id,
        client_id=api_client.client_id,
        client_name=api_client.client_name,
        client_description=api_client.client_description,
        user_id=api_client.user_id,
        api_key_prefix=api_client.api_key_prefix,
        allowed_document_types=api_client.allowed_document_types,
        max_transaction_amount=float(api_client.max_transaction_amount) if api_client.max_transaction_amount else None,
        rate_limit_per_minute=api_client.rate_limit_per_minute,
        rate_limit_per_hour=api_client.rate_limit_per_hour,
        rate_limit_per_day=api_client.rate_limit_per_day,
        is_active=api_client.is_active,
        is_sandbox=api_client.is_sandbox,
        total_requests=api_client.total_requests,
        total_transactions_submitted=api_client.total_transactions_submitted,
        last_used_at=api_client.last_used_at,
        created_at=api_client.created_at,
        updated_at=api_client.updated_at,
        custom_quotas=api_client.custom_quotas
    )


@router.delete("/api-keys/{client_id}")
@require_feature("external_api")
async def revoke_api_key(
    client_id: str,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db)  # Use tenant DB for feature checking
):
    """Revoke (deactivate) an API key."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    api_client.is_active = False
    api_client.revoked_at = datetime.now(timezone.utc)
    api_client.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": f"API key {client_id} has been revoked"}


@router.post("/api-keys/{client_id}/regenerate", response_model=APIKeyResponse)
@require_feature("external_api")
async def regenerate_api_key(
    client_id: str,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_master_db),
    tenant_db: Session = Depends(get_db)  # Use tenant DB for feature checking
):
    """Regenerate an API key (creates new key, invalidates old one)."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.user_id == current_user.id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    # Generate new API key
    new_api_key = _generate_api_key()
    new_api_key_hash = _hash_api_key(new_api_key)
    new_api_key_prefix = _get_api_key_prefix(new_api_key)
    
    # Update client with new key
    api_client.api_key_hash = new_api_key_hash
    api_client.api_key_prefix = new_api_key_prefix
    api_client.key_rotated_at = datetime.now(timezone.utc)
    api_client.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(api_client)
    
    return APIKeyResponse(
        client_id=api_client.client_id,
        api_key=new_api_key,  # Only returned once during regeneration
        api_key_prefix=new_api_key_prefix,
        client_name=api_client.client_name,
        allowed_document_types=api_client.allowed_document_types,
        rate_limits={
            "per_minute": api_client.rate_limit_per_minute,
            "per_hour": api_client.rate_limit_per_hour,
            "per_day": api_client.rate_limit_per_day
        },
        expires_at=None,  # Regenerated keys don't have expiration by default
        created_at=api_client.updated_at  # Use update time as creation time for new key
    )


# OAuth 2.0 endpoints for enterprise clients
@router.post("/oauth/clients", response_model=OAuthClientResponse)
async def create_oauth_client(
    request_data: OAuthClientCreateRequest,
    current_user: MasterUser = Depends(require_admin_permissions),
    db: Session = Depends(get_master_db)
):
    """Create a new OAuth 2.0 client for enterprise integration."""
    
    # Validate and normalize document types
    valid_types = ["invoice", "expense", "statement", "portfolio"]
    normalized_types = []
    for doc_type in request_data.allowed_document_types:
        # Normalize to lowercase for consistency
        normalized = doc_type.lower().strip() if isinstance(doc_type, str) else doc_type
        if normalized not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type: {doc_type}. Must be one of: {valid_types}"
            )
        normalized_types.append(normalized)

    # Use normalized types (remove duplicates while preserving order)
    seen = set()
    unique_normalized = []
    for doc_type in normalized_types:
        if doc_type not in seen:
            seen.add(doc_type)
            unique_normalized.append(doc_type)
    request_data.allowed_document_types = unique_normalized

    # Generate OAuth client credentials
    oauth_client_id = f"oauth_{secrets.token_urlsafe(16)}"
    oauth_client_secret = secrets.token_urlsafe(32)
    oauth_client_secret_hash = _hash_api_key(oauth_client_secret)
    
    # Generate regular client ID for tracking
    client_id = f"client_{secrets.token_urlsafe(16)}"
    
    # Create API client with OAuth configuration
    api_client = APIClient(
        client_id=client_id,
        client_name=request_data.client_name,
        client_description=request_data.client_description,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        api_key_hash="",  # OAuth clients don't use API keys
        api_key_prefix="oauth",
        oauth_client_id=oauth_client_id,
        oauth_client_secret_hash=oauth_client_secret_hash,
        oauth_redirect_uris=request_data.redirect_uris,
        oauth_scopes=request_data.scopes,
        allowed_document_types=request_data.allowed_document_types,
        rate_limit_per_minute=request_data.rate_limit_per_minute,
        rate_limit_per_hour=request_data.rate_limit_per_hour,
        rate_limit_per_day=request_data.rate_limit_per_day,
        created_by=current_user.id,
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
        terms_accepted_at=datetime.now(timezone.utc),
        privacy_policy_accepted_at=datetime.now(timezone.utc)
    )
    
    db.add(api_client)
    db.commit()
    db.refresh(api_client)
    
    return OAuthClientResponse(
        client_id=client_id,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,  # Only returned once
        client_name=request_data.client_name,
        redirect_uris=request_data.redirect_uris,
        scopes=request_data.scopes,
        created_at=api_client.created_at
    )


# Admin endpoints for managing API keys
@router.get("/admin/api-keys", response_model=List[APIClientResponse])
async def admin_list_all_api_keys(
    current_user: MasterUser = Depends(require_admin_permissions),
    db: Session = Depends(get_master_db),
    user_id: Optional[int] = None,
    include_inactive: bool = False
):
    """Admin endpoint to list all API keys in the tenant."""
    
    query = db.query(APIClient).filter(APIClient.tenant_id == current_user.tenant_id)
    
    if user_id:
        query = query.filter(APIClient.user_id == user_id)
    
    if not include_inactive:
        query = query.filter(APIClient.is_active == True)
    
    api_clients = query.order_by(APIClient.created_at.desc()).all()
    
    return [
        APIClientResponse(
            id=client.id,
            client_id=client.client_id,
            client_name=client.client_name,
            client_description=client.client_description,
            user_id=client.user_id,
            api_key_prefix=client.api_key_prefix,
            allowed_document_types=client.allowed_document_types,
            max_transaction_amount=float(client.max_transaction_amount) if client.max_transaction_amount else None,
            rate_limit_per_minute=client.rate_limit_per_minute,
            rate_limit_per_hour=client.rate_limit_per_hour,
            rate_limit_per_day=client.rate_limit_per_day,
            is_active=client.is_active,
            is_sandbox=client.is_sandbox,
            total_requests=client.total_requests,
            total_transactions_submitted=client.total_transactions_submitted,
            last_used_at=client.last_used_at,
            created_at=client.created_at,
            updated_at=client.updated_at,
            custom_quotas=client.custom_quotas
        )
        for client in api_clients
    ]


@router.post("/admin/api-keys/{client_id}/approve")
async def admin_approve_api_key(
    client_id: str,
    current_user: MasterUser = Depends(require_admin_permissions),
    db: Session = Depends(get_master_db)
):
    """Admin endpoint to approve an API key."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    api_client.approved_by = current_user.id
    api_client.approved_at = datetime.now(timezone.utc)
    api_client.is_active = True
    api_client.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": f"API key {client_id} has been approved"}


@router.post("/admin/api-keys/{client_id}/revoke")
async def admin_revoke_api_key(
    client_id: str,
    current_user: MasterUser = Depends(require_admin_permissions),
    db: Session = Depends(get_master_db)
):
    """Admin endpoint to revoke any API key."""
    
    api_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.tenant_id == current_user.tenant_id
    ).first()
    
    if not api_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found"
        )
    
    api_client.is_active = False
    api_client.revoked_at = datetime.now(timezone.utc)
    api_client.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": f"API key {client_id} has been revoked by admin"}


@router.get("/permissions")
async def list_available_permissions(
    current_user: MasterUser = Depends(get_current_user)
):
    """List all available permissions in the system."""
    
    return {
        "permissions": [
            {"name": Permission.READ, "description": "Read Access"},
            {"name": Permission.WRITE, "description": "Write Access"},
            {"name": Permission.DELETE, "description": "Delete Access"},
            {"name": Permission.ADMIN, "description": "Admin Access"},
            {"name": Permission.USER_MANAGEMENT, "description": "User Management"},
            {"name": Permission.INVOICE_READ, "description": "Invoice Read Access"},
            {"name": Permission.INVOICE_WRITE, "description": "Invoice Write Access"},
            {"name": Permission.EXPENSE_READ, "description": "Expense Read Access"},
            {"name": Permission.EXPENSE_WRITE, "description": "Expense Write Access"},
            {"name": Permission.TRANSACTION_PROCESSING, "description": "Transaction Processing"},
            {"name": Permission.DOCUMENT_PROCESSING, "description": "Document Processing"}
        ]
    }
