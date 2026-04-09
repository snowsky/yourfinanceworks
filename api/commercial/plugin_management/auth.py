from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Any
import time
import secrets
import json
import base64
from pydantic import BaseModel
import os

from core.models.database import get_db, get_master_db
from core.models.models import Tenant, PluginUser, TenantPluginSettings
from core.utils.auth import create_access_token, get_password_hash, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from config import config
import logging

try:
    from httpx_oauth.clients.google import GoogleOAuth2
except ImportError:
    GoogleOAuth2 = None

logger = logging.getLogger(__name__)

router = APIRouter(tags=["plugin_auth"])

# --- Google OAuth2 (SSO) setup ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

google_oauth_client: Optional[GoogleOAuth2] = None
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GoogleOAuth2:
    google_oauth_client = GoogleOAuth2(client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET)

# --- Azure AD OAuth2 (SSO) setup ---
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "common")
AZURE_OAUTH_SCOPES = []

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


OAUTH_STATE_STORE: Dict[str, Dict[str, Any]] = {}

class PluginLoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: int

class PluginSignupRequest(BaseModel):
    email: str
    password: str
    tenant_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@router.post("/{plugin_id}/public-auth/signup")
async def plugin_local_signup(
    plugin_id: str,
    payload: PluginSignupRequest,
    db: Session = Depends(get_master_db)
):
    # Check if tenant has the plugin enabled and public access
    settings = db.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == payload.tenant_id).first()
    if not settings or plugin_id not in settings.enabled_plugins:
        raise HTTPException(status_code=403, detail="Plugin not available")
        
    cfg = settings.plugin_config or {}
    p_cfg = cfg.get(plugin_id, {})
    pa = p_cfg.get("public_access", {})
    if not pa.get("enabled", False):
        raise HTTPException(status_code=403, detail="Plugin not public")

    existing_user = db.query(PluginUser).filter(
        PluginUser.tenant_id == payload.tenant_id,
        PluginUser.plugin_id == plugin_id,
        PluginUser.email == payload.email
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
        
    user = PluginUser(
        tenant_id=payload.tenant_id,
        plugin_id=plugin_id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"sub": user.email, "type": "plugin", "plugin_id": plugin_id, "tenant_id": payload.tenant_id, "plugin_user_id": user.id}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@router.post("/{plugin_id}/public-auth/login")
async def plugin_local_login(
    plugin_id: str,
    payload: PluginLoginRequest,
    db: Session = Depends(get_master_db)
):
    user = db.query(PluginUser).filter(
        PluginUser.tenant_id == payload.tenant_id,
        PluginUser.plugin_id == plugin_id,
        PluginUser.email == payload.email
    ).first()
    
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        data={"sub": user.email, "type": "plugin", "plugin_id": plugin_id, "tenant_id": payload.tenant_id, "plugin_user_id": user.id}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@router.get("/{plugin_id}/public-auth/google/login")
async def plugin_google_login(plugin_id: str, tenant_id: int, request: Request, next: Optional[str] = None):
    if not google_oauth_client:
        raise HTTPException(status_code=503, detail="Google SSO is not configured")
        
    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/plugins/{plugin_id}/public-auth/google/callback"
    
    state = secrets.token_urlsafe(32)
    OAUTH_STATE_STORE[state] = {"ts": time.time(), "next": next or f"/p/{plugin_id}", "tenant_id": tenant_id}
    
    authorization_url = await google_oauth_client.get_authorization_url(
        redirect_uri=callback_url,
        scope=GOOGLE_OAUTH_SCOPES,
        state=state
    )
    return RedirectResponse(url=authorization_url)

@router.get("/{plugin_id}/public-auth/google/callback")
async def plugin_google_callback(plugin_id: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not google_oauth_client:
        raise HTTPException(status_code=503, detail="Google SSO not configured")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
        
    state_data = OAUTH_STATE_STORE.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid state")
        
    tenant_id = state_data["tenant_id"]
    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/plugins/{plugin_id}/public-auth/google/callback"
    
    try:
        token = await google_oauth_client.get_access_token(code, redirect_uri=callback_url)
        user_info = await google_oauth_client.get_id_email(token["access_token"])
        google_id, email, verified_email = user_info
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        raise HTTPException(status_code=400, detail="Failed to fetch Google info")
        
    user = db.query(PluginUser).filter(
        PluginUser.tenant_id == tenant_id,
        PluginUser.plugin_id == plugin_id,
        PluginUser.email == email
    ).first()
    
    if not user:
        user = PluginUser(
            tenant_id=tenant_id,
            plugin_id=plugin_id,
            email=email,
            google_id=str(google_id),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.google_id:
        user.google_id = str(google_id)
        db.commit()
        
    access_token = create_access_token(
        data={"sub": user.email, "type": "plugin", "plugin_id": plugin_id, "tenant_id": tenant_id, "plugin_user_id": user.id}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Return to UI so frontend can grab the token and set it in localStorage
    redirect_next = state_data.get("next") or f"/p/{plugin_id}"
    token_url_encoded = base64.urlsafe_b64encode(json.dumps({
        "access_token": access_token, 
        "user": {"id": user.id, "email": user.email}
    }).encode()).decode()
    
    redirect_url = f"{ui_base}/p/{plugin_id}/auth-callback?token_data={token_url_encoded}&next={redirect_next}"
    return RedirectResponse(url=redirect_url)

@router.get("/{plugin_id}/public-auth/azure/login")
async def plugin_azure_login(plugin_id: str, tenant_id: int, request: Request, next: Optional[str] = None):
    if not azure_oauth_client:
        raise HTTPException(status_code=503, detail="Azure AD SSO is not configured")

    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/plugins/{plugin_id}/public-auth/azure/callback"

    state = secrets.token_urlsafe(32)
    OAUTH_STATE_STORE[state] = {"ts": time.time(), "next": next or f"/p/{plugin_id}", "tenant_id": tenant_id}

    authorization_url = azure_oauth_client.get_authorization_request_url(
        scopes=AZURE_OAUTH_SCOPES,
        state=state,
        redirect_uri=callback_url
    )
    return RedirectResponse(url=authorization_url)

@router.get("/{plugin_id}/public-auth/azure/callback")
async def plugin_azure_callback(plugin_id: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_master_db)):
    if not azure_oauth_client:
        raise HTTPException(status_code=503, detail="Azure AD SSO not configured")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_data = OAUTH_STATE_STORE.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid state")

    tenant_id = state_data["tenant_id"]
    ui_base = config.UI_BASE_URL
    callback_url = f"{ui_base}/api/v1/plugins/{plugin_id}/public-auth/azure/callback"

    try:
        result = azure_oauth_client.acquire_token_by_authorization_code(
            code=code,
            scopes=AZURE_OAUTH_SCOPES,
            redirect_uri=callback_url
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result.get('error_description', result['error']))
        
        id_token_claims = result.get("id_token_claims", {})
        email = id_token_claims.get("email") or id_token_claims.get("preferred_username")
        oid = id_token_claims.get("oid")
    except Exception as e:
        logger.error(f"Azure AD error: {e}")
        raise HTTPException(status_code=400, detail="Failed to fetch Azure info")

    if not email:
        raise HTTPException(status_code=400, detail="Azure account has no email")

    user = db.query(PluginUser).filter(
        PluginUser.tenant_id == tenant_id,
        PluginUser.plugin_id == plugin_id,
        PluginUser.email == email
    ).first()

    if not user:
        user = PluginUser(
            tenant_id=tenant_id,
            plugin_id=plugin_id,
            email=email,
            azure_ad_id=str(oid),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.azure_ad_id:
        user.azure_ad_id = str(oid)
        db.commit()

    access_token = create_access_token(
        data={"sub": user.email, "type": "plugin", "plugin_id": plugin_id, "tenant_id": tenant_id, "plugin_user_id": user.id}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    redirect_next = state_data.get("next") or f"/p/{plugin_id}"
    token_url_encoded = base64.urlsafe_b64encode(json.dumps({
        "access_token": access_token, 
        "user": {"id": user.id, "email": user.email}
    }).encode()).decode()

    redirect_url = f"{ui_base}/p/{plugin_id}/auth-callback?token_data={token_url_encoded}&next={redirect_next}"
    return RedirectResponse(url=redirect_url)
