from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Any
import time
import os
import secrets
from httpx_oauth.clients.google import GoogleOAuth2
import logging
import traceback
import json
import base64

from core.models.database import get_db, get_master_db
from core.models.models import Tenant, MasterUser, Invite
from core.schemas.user import UserRead
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.middleware.tenant_context_middleware import set_tenant_context
from core.utils.feature_gate import require_feature, check_feature
from core.utils.auth import create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from config import config
from sqlalchemy import func
from core.utils.rbac import require_admin
from core.services.license_service import LicenseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# --- Google OAuth2 (SSO) setup ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

google_oauth_client: Optional[GoogleOAuth2] = None
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    google_oauth_client = GoogleOAuth2(client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET)

# --- Azure AD OAuth2 (SSO) setup ---
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "common")  # 'common' for multi-tenant, or specific tenant ID
AZURE_OAUTH_SCOPES = []  # Azure AD automatically includes openid, email, profile

# Azure AD OAuth client using MSAL
azure_oauth_client = None
if AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
    try:
        from msal import ConfidentialClientApplication
        azure_oauth_client = ConfidentialClientApplication(
            client_id=AZURE_CLIENT_ID,
            client_credential=AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
        )
    except ImportError:
        logger.warning("MSAL library not available. Azure AD SSO will be disabled.")

# In-memory state store for CSRF protection and to carry 'next' parameter
OAUTH_STATE_STORE: Dict[str, Dict[str, Any]] = {}
OAUTH_STATE_TTL_SECONDS = 600

def _oauth_prune_states() -> None:
    cutoff = time.time() - OAUTH_STATE_TTL_SECONDS
    stale = [s for s, v in OAUTH_STATE_STORE.items() if v.get("ts", 0) < cutoff]
    for s in stale:
        OAUTH_STATE_STORE.pop(s, None)

def check_user_has_valid_invite(db: Session, email: str) -> Optional[Invite]:
    """Check if email has valid invitation for any tenant"""
    return db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(email),
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()

# -------------------- Google OAuth (SSO) endpoints --------------------
@router.get("/google/login")
async def google_login(request: Request, next: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not google_oauth_client:
        raise HTTPException(status_code=503, detail="Google SSO is not configured")

    # Feature gating check - requires master DB since we don't have tenant context yet
    # But usually SSO is a system-wide enabled feature or per-tenant.
    # If it's licensed, it should be enabled.
    # For now, let's just use a simple check.
    # Actually, we'll check it after we identify the user/tenant in the callback.
    # BUT, to prevent even starting the flow if not licensed, we can check it here too if we have a way.
    # Since we don't have a tenant yet in google_login (usually), we might skip gating here
    # and enforce it in the callback once we know who they are.

    # Determine redirect URI (callback)
    # Use UI_BASE_URL from config
    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/auth/google/callback"

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    OAUTH_STATE_STORE[state] = {"ts": time.time(), "next": next or "/dashboard"}
    _oauth_prune_states()

    authorization_url = await google_oauth_client.get_authorization_url(
        redirect_uri=callback_url,
        scope=GOOGLE_OAUTH_SCOPES,
        state=state
    )
    return RedirectResponse(url=authorization_url)

@router.get("/google/callback")
async def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not google_oauth_client:
        raise HTTPException(status_code=503, detail="Google SSO is not configured")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Validate state
    state_data = OAUTH_STATE_STORE.pop(state, None)
    _oauth_prune_states()
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/auth/google/callback"

    # Exchange code for token
    try:
        token = await google_oauth_client.get_access_token(code, redirect_uri=callback_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {e}")

    # Fetch user info
    first_name = None
    last_name = None
    try:
        user_info = await google_oauth_client.get_id_email(token["access_token"])  # returns tuple (id, email, verified)
        google_id, email, verified_email = user_info
        logger.info(f"Successfully fetched Google user info: {email}")
    except Exception as e:
        logger.error(f"get_id_email failed: {e}")
        # Fallback to userinfo endpoint if needed
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token['access_token']}"}
                )
                if response.status_code == 200:
                    user_data = response.json()
                    google_id = user_data.get("id")
                    email = user_data.get("email")
                    verified_email = user_data.get("verified_email", False)
                    first_name = user_data.get("given_name")
                    last_name = user_data.get("family_name")
                    logger.info(f"Successfully fetched Google user info via userinfo endpoint: {email}")
                else:
                    logger.error(f"Userinfo endpoint failed: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=400, detail="Failed to fetch Google user info")
        except Exception as e2:
            logger.error(f"Both methods failed: {e2}")
            raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    # Find or create user in master database
    user = db.query(MasterUser).filter((MasterUser.google_id == google_id) | (MasterUser.email == email)).first()
    if not user:
        # Determine if this is the first user in the entire system (Global Super Admin)
        is_global_first_user = db.query(MasterUser).count() == 0

        # Check if user has a valid invitation first
        valid_invite = check_user_has_valid_invite(db, email)

        if valid_invite:
            # User has invitation, assign to inviting tenant
            db_tenant = db.query(Tenant).filter(Tenant.id == valid_invite.tenant_id).first()
            if not db_tenant:
                raise HTTPException(status_code=400, detail="Invited organization not found")
            tenant_name = db_tenant.name
            is_org_first_user = False
        else:
            # No invitation, create a new tenant for first user of organization
            is_org_first_user = True

            # IMPORTANT: Only the first user in the entire system can create a new organization
            # without a license. This "Global and Early" rejection strategy prevents
            # resource waste (Tenant/DB creation) for unlicensed users.
            # See docs/SSO_LICENSE_GATING.md for full rationale.
            if not is_global_first_user:
                # Check for an active Global License before rejecting
                license_service = LicenseService(db, master_db=db)
                status = license_service.get_license_status()

                if not status.get("is_licensed"):
                    # This is not the first user globally, and no global license is active
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=sso_license_required")

                # Check global signup controls
                if not status.get("allow_sso_signup", True):
                    # We already checked is_global_first_user is False
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=sso_registration_disabled")

                # Check global capacity (tenant limit)
                max_tenants = license_service.get_max_tenants()
                # Count tenants that count against the license
                current_tenants_count = db.query(Tenant).filter(Tenant.count_against_license == True).count()

                if current_tenants_count >= max_tenants:
                    logger.error(f"Global tenant limit reached: {current_tenants_count} >= {max_tenants}")
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=tenant_limit_reached")

            # Create tenant for first user
            tenant_name = f"{email.split('@')[0]}'s Organization"
            db_tenant = Tenant(name=tenant_name, email=email, is_active=True)
            db.add(db_tenant)
            db.commit()
            db.refresh(db_tenant)

            # Provision tenant DB
            success = tenant_db_manager.create_tenant_database(db_tenant.id, tenant_name)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to create tenant database")

        # Create master user
        user = MasterUser(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(16)),
            first_name=first_name,
            last_name=last_name,
            role="admin" if is_org_first_user else (valid_invite.role if valid_invite else "admin"),
            tenant_id=db_tenant.id,
            is_active=True,
            is_superuser=is_global_first_user,
            is_verified=bool(verified_email),
            google_id=str(google_id),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Mark invitation as accepted if there was one
        if valid_invite:
            valid_invite.is_accepted = True
            valid_invite.accepted_at = datetime.now(timezone.utc)
            db.commit()

        # Create tenant user mirror
        set_tenant_context(db_tenant.id)
        tenant_session = tenant_db_manager.get_tenant_session(db_tenant.id)
        tenant_db = tenant_session()
        try:
            tenant_user = TenantUser(
                id=user.id,
                email=email,
                hashed_password=user.hashed_password,
                first_name=first_name,
                last_name=last_name,
                role="admin" if is_org_first_user else (valid_invite.role if valid_invite else "admin"),
                is_active=True,
                is_superuser=is_global_first_user,
                is_verified=True,
                google_id=str(google_id),
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()

            # License check for NEW users who are not the global first user
            # This covers users joining via invitation.
            if not is_global_first_user:
                check_feature("sso", tenant_db)
        finally:
            tenant_db.close()
    else:
        # Ensure google_id is linked
        if not user.google_id:
            user.google_id = str(google_id)
            db.commit()

        # License check for EXISTING users who are not the global first user
        if not user.is_superuser:
            set_tenant_context(user.tenant_id)
            tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
            tenant_db = tenant_session()
            try:
                check_feature("sso", tenant_db)
            finally:
                tenant_db.close()

    # Issue JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    # Redirect back to UI with token via fragment so it doesn't hit server logs
    ui_base = config.UI_BASE_URL
    redirect_next = state_data.get("next") or "/dashboard"
    # Compose URL: e.g., /oauth-callback?token=...&user=...
    user_payload = UserRead.model_validate(user).model_dump()
    # Convert datetime objects to strings for JSON serialization
    def datetime_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    user_b64 = base64.urlsafe_b64encode(json.dumps(user_payload, default=datetime_serializer).encode()).decode()
    redirect_url = f"{ui_base}/oauth-callback?token={access_token}&user={user_b64}&next={redirect_next}"
    return RedirectResponse(url=redirect_url)

# -------------------- Azure AD OAuth (SSO) endpoints --------------------
@router.get("/azure/login")
async def azure_login(request: Request, next: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not azure_oauth_client:
        raise HTTPException(status_code=503, detail="Azure AD SSO is not configured")

    # Determine redirect URI (callback)
    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/auth/azure/callback"

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    OAUTH_STATE_STORE[state] = {"ts": time.time(), "next": next or "/dashboard"}
    _oauth_prune_states()

    # Build authorization URL using MSAL
    authorization_url = azure_oauth_client.get_authorization_request_url(
        scopes=AZURE_OAUTH_SCOPES,
        state=state,
        redirect_uri=callback_url
    )
    return RedirectResponse(url=authorization_url)

@router.get("/azure/callback")
async def azure_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not azure_oauth_client:
        raise HTTPException(status_code=503, detail="Azure AD SSO is not configured")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Validate state
    state_data = OAUTH_STATE_STORE.pop(state, None)
    _oauth_prune_states()
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/auth/azure/callback"

    # Exchange code for token using MSAL
    try:
        result = azure_oauth_client.acquire_token_by_authorization_code(
            code=code,
            scopes=AZURE_OAUTH_SCOPES,
            redirect_uri=callback_url
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=f"Azure AD error: {result.get('error_description', result['error'])}")

        access_token = result["access_token"]
        id_token_claims = result.get("id_token_claims", {})

    except Exception as e:
        logger.error(f"Azure AD token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {e}")

    # Extract user info from ID token claims
    email = id_token_claims.get("email") or id_token_claims.get("preferred_username")
    oid = id_token_claims.get("oid")  # Object ID (unique identifier)
    first_name = id_token_claims.get("given_name")
    last_name = id_token_claims.get("family_name")

    if not email:
        raise HTTPException(status_code=400, detail="Azure account has no email")

    logger.info(f"Successfully authenticated Azure user: {email}")

    # Find or create user in master database
    # For now, we don't have an azure_id field, so we'll match by email or maybe rely on google_id if we want to share
    # Or ideally, add an azure_id field. For now, matching by email is the safest best-effort.
    # Note: We should probably add azure_id to the User model, but for minimal changes we'll stick to email matching for now.
    user = db.query(MasterUser).filter(MasterUser.email == email).first()

    if not user:
        # Determine if this is the first user in the entire system (Global Super Admin)
        is_global_first_user = db.query(MasterUser).count() == 0

        # Check if user has a valid invitation first
        valid_invite = check_user_has_valid_invite(db, email)

        if valid_invite:
            # User has invitation, assign to inviting tenant
            db_tenant = db.query(Tenant).filter(Tenant.id == valid_invite.tenant_id).first()
            if not db_tenant:
                raise HTTPException(status_code=400, detail="Invited organization not found")
            tenant_name = db_tenant.name
            is_org_first_user = False
        else:
            # No invitation, create a new tenant for first user of organization
            is_org_first_user = True

            # IMPORTANT: Only the first user in the entire system can create a new organization
            # without a license. This "Global and Early" rejection strategy prevents
            # resource waste (Tenant/DB creation) for unlicensed users.
            # See docs/SSO_LICENSE_GATING.md for full rationale.
            if not is_global_first_user:
                # Check for an active Global License before rejecting
                license_service = LicenseService(db, master_db=db)
                status = license_service.get_license_status()

                if not status.get("is_licensed"):
                    # This is not the first user globally, and no global license is active
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=sso_license_required")

                # Check global signup controls
                if not status.get("allow_sso_signup", True):
                    # We already checked is_global_first_user is False
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=sso_registration_disabled")

                # Check global capacity (tenant limit)
                max_tenants = license_service.get_max_tenants()
                # Count tenants that count against the license
                current_tenants_count = db.query(Tenant).filter(Tenant.count_against_license == True).count()

                if current_tenants_count >= max_tenants:
                    logger.error(f"Global tenant limit reached: {current_tenants_count} >= {max_tenants}")
                    ui_base = config.UI_BASE_URL
                    return RedirectResponse(url=f"{ui_base}/login?error=tenant_limit_reached")

            # Create tenant for first user
            tenant_name = f"{email.split('@')[0]}'s Organization"
            db_tenant = Tenant(name=tenant_name, email=email, is_active=True)
            db.add(db_tenant)
            db.commit()
            db.refresh(db_tenant)

            # Provision tenant DB
            success = tenant_db_manager.create_tenant_database(db_tenant.id, tenant_name)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to create tenant database")

        # Create master user
        user = MasterUser(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(16)),
            first_name=first_name,
            last_name=last_name,
            role="admin" if is_org_first_user else (valid_invite.role if valid_invite else "admin"),
            tenant_id=db_tenant.id,
            is_active=True,
            is_superuser=is_global_first_user,
            is_verified=True,
            # google_id=str(oid), # Do NOT reuse google_id for azure OID
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Mark invitation as accepted if there was one
        if valid_invite:
            valid_invite.is_accepted = True
            valid_invite.accepted_at = datetime.now(timezone.utc)
            db.commit()

        # Create tenant user mirror
        set_tenant_context(db_tenant.id)
        tenant_session = tenant_db_manager.get_tenant_session(db_tenant.id)
        tenant_db = tenant_session()
        try:
            tenant_user = TenantUser(
                id=user.id,
                email=email,
                hashed_password=user.hashed_password,
                first_name=first_name,
                last_name=last_name,
                role="admin" if is_org_first_user else (valid_invite.role if valid_invite else "admin"),
                is_active=True,
                is_superuser=is_global_first_user,
                is_verified=True,
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()

            # License check for NEW users who are not the global first user
            # This covers users joining via invitation.
            if not is_global_first_user:
                check_feature("sso", tenant_db)
        finally:
            tenant_db.close()
    else:
        # License check for EXISTING users who are not the global first user
        if not user.is_superuser:
            set_tenant_context(user.tenant_id)
            tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
            tenant_db = tenant_session()
            try:
                check_feature("sso", tenant_db)
            finally:
                tenant_db.close()

    # Issue JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    # Redirect back to UI...
    ui_base = config.UI_BASE_URL
    redirect_next = state_data.get("next") or "/dashboard"
    # Serialize user data to JSON and then base64 encode
    user_payload = UserRead.model_validate(user).model_dump()
    def datetime_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    user_b64 = base64.urlsafe_b64encode(json.dumps(user_payload, default=datetime_serializer).encode()).decode()
    redirect_url = f"{ui_base}/oauth-callback?token={access_token}&user={user_b64}&next={redirect_next}"
    return RedirectResponse(url=redirect_url)
