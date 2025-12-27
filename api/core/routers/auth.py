from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict, Any
from collections import defaultdict, deque
import time
import os
import secrets
from sqlalchemy import func
from httpx_oauth.clients.google import GoogleOAuth2
import logging
import traceback

logger = logging.getLogger(__name__)

from core.models.database import get_db, get_master_db
from core.models.models import User, Tenant, MasterUser, Invite, PasswordResetToken, Settings  # Add PasswordResetToken, Settings import
from core.schemas.user import UserCreate, UserLogin, Token, UserRead, UserUpdate, InviteCreate, InviteRead, InviteAccept, UserList, UserRoleUpdate, AdminActivateUser
from core.schemas.password_reset import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
from pydantic import BaseModel
from core.services.email_service import EmailService, EmailProviderConfig, EmailProvider
from core.utils.auth import verify_password, get_password_hash
from core.models.models_per_tenant import User as TenantUser
from core.services.tenant_database_manager import tenant_db_manager
from core.middleware.tenant_context_middleware import set_tenant_context
from core.utils.rbac import require_admin
from core.utils.audit import log_audit_event, log_audit_event_master
from core.constants.error_codes import USER_NOT_FOUND, INCORRECT_PASSWORD, INACTIVE_USER, TENANT_CONTEXT_REQUIRED

router = APIRouter(prefix="/auth", tags=["authentication"])

# JWT settings
# Enforce SECRET_KEY in non-debug environments
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in the environment for production use")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Simple in-memory rate limiting (per email) to deter brute-force attacks
# Note: For multi-instance deployments, replace with a shared store (e.g., Redis)
LOGIN_ATTEMPTS: Dict[str, deque] = defaultdict(deque)
PASSWORD_RESET_ATTEMPTS: Dict[str, deque] = defaultdict(deque)
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
MAX_RESET_ATTEMPTS = int(os.getenv("MAX_RESET_ATTEMPTS", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

def _prune_attempts(attempts: deque, window_seconds: int) -> None:
    cutoff = time.time() - window_seconds
    while attempts and attempts[0] < cutoff:
        attempts.popleft()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
security = HTTPBearer()

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_password_reset_token() -> str:
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)

def create_reset_token_entry(db: Session, user_id: int) -> PasswordResetToken:
    """Create a password reset token entry in the database"""
    # Deactivate any existing tokens for this user
    existing_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).all()
    
    for token in existing_tokens:
        token.is_used = True
        token.used_at = datetime.now(timezone.utc)
    
    # Create new token
    token = create_password_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)  # Token expires in 1 hour
    
    reset_token = PasswordResetToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    
    return reset_token

def verify_reset_token(db: Session, token: str) -> Optional[PasswordResetToken]:
    """Verify a password reset token and return the token object if valid"""
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    return reset_token

def get_email_service_for_tenant(db: Session, tenant_id: int) -> Optional[EmailService]:
    """Get configured email service for a tenant"""
    try:
        # Get email configuration from core.settings
        email_settings = db.query(Settings).filter(
            Settings.tenant_id == tenant_id,
            Settings.key == "email_config"
        ).first()
        
        if not email_settings or not email_settings.value:
            return None
        
        email_config_data = email_settings.value
        
        # Check if email service is enabled
        if not email_config_data.get('enabled', False):
            return None
        
        # Create email provider config
        config = EmailProviderConfig(
            provider=EmailProvider(email_config_data['provider']),
            from_email=email_config_data.get('from_email'),
            from_name=email_config_data.get('from_name'),
            aws_access_key_id=email_config_data.get('aws_access_key_id'),
            aws_secret_access_key=email_config_data.get('aws_secret_access_key'),
            aws_region=email_config_data.get('aws_region'),
            azure_connection_string=email_config_data.get('azure_connection_string'),
            mailgun_api_key=email_config_data.get('mailgun_api_key'),
            mailgun_domain=email_config_data.get('mailgun_domain')
        )
        
        return EmailService(config)
        
    except Exception as e:
        print(f"Failed to initialize email service for tenant {tenant_id}: {str(e)}")
        return None

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(MasterUser).filter(MasterUser.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_master_db)
) -> MasterUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=TENANT_CONTEXT_REQUIRED,
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(MasterUser).filter(MasterUser.email == email).first()
    if user is None:
        raise credentials_exception
    
    # Check if we have a tenant context and if the user's role should be updated from tenant database
    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()
    
    if current_tenant_id and current_tenant_id != user.tenant_id:
        # User is accessing a different tenant, get their role from that tenant's database
        try:
            tenant_session = tenant_db_manager.get_tenant_session(current_tenant_id)
            tenant_db = tenant_session()
            try:
                tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
                if tenant_user:
                    # Create a copy of the master user with the tenant-specific role
                    user_copy = MasterUser(
                        id=user.id,
                        email=user.email,
                        hashed_password=user.hashed_password,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        role=tenant_user.role,  # Use role from tenant database
                        tenant_id=current_tenant_id,  # Use current tenant context
                        is_active=user.is_active,
                        is_superuser=user.is_superuser,
                        is_verified=user.is_verified,
                        must_reset_password=bool(getattr(tenant_user, 'must_reset_password', False)),
                        theme=user.theme,
                        google_id=user.google_id,
                        created_at=user.created_at,
                        updated_at=user.updated_at
                    )
                    return user_copy
                else:
                    # Not a member of this tenant: treat as viewer for UI/permissions
                    user_copy = MasterUser(
                        id=user.id,
                        email=user.email,
                        hashed_password=user.hashed_password,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        role='viewer',
                        tenant_id=current_tenant_id,
                        is_active=user.is_active,
                        is_superuser=user.is_superuser,
                        is_verified=user.is_verified,
                        must_reset_password=bool(getattr(user, 'must_reset_password', False)),
                        theme=user.theme,
                        google_id=user.google_id,
                        created_at=user.created_at,
                        updated_at=user.updated_at
                    )
                    return user_copy
            finally:
                tenant_db.close()
        except Exception as e:
            logger.warning(f"Failed to get tenant-specific role for user {email} in tenant {current_tenant_id}: {e}")
            # Fall back to master user if tenant lookup fails
    
    return user

def generate_invite_token() -> str:
    """Generate a secure invite token"""
    return secrets.token_urlsafe(32)

def send_invite_email(email: str, invite_url: str, inviter_name: str, tenant_name: str):
    """Send invite email (placeholder - implement with your email service)"""
    # TODO: Implement with your email service (SendGrid, AWS SES, etc.)
    print(f"Invite email to {email}: {invite_url}")
    # For now, just print to console
    return True

def get_user_organizations(db: Session, user: MasterUser) -> List[Dict[str, Any]]:
    """Get all organizations/tenants for a user"""
    organizations = []
    
    # Get user's primary tenant
    if user.tenant_id:
        primary_tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if primary_tenant:
            organizations.append({
                "id": primary_tenant.id,
                "name": primary_tenant.name,
                "role": user.role,
                "is_primary": True
            })
    
    # Get additional tenant memberships from association table
    from core.models.models import user_tenant_association
    additional_tenants = db.query(Tenant, user_tenant_association.c.role).join(
        user_tenant_association, Tenant.id == user_tenant_association.c.tenant_id
    ).filter(
        user_tenant_association.c.user_id == user.id,
        user_tenant_association.c.is_active == True,
        Tenant.id != user.tenant_id  # Exclude primary tenant
    ).all()
    
    for tenant, role in additional_tenants:
        organizations.append({
            "id": tenant.id,
            "name": tenant.name,
            "role": role,
            "is_primary": False
        })
    
    return organizations

@router.post("/register", response_model=Token, status_code=201)
async def register(user: UserCreate, db: Session = Depends(get_master_db)):
    logger = logging.getLogger("registration")
    logger.info(f"Starting registration for {user.email}")
    
    # Check if user already exists
    existing_user = db.query(MasterUser).filter(MasterUser.email == user.email).first()
    is_existing_user = existing_user is not None
    
    if is_existing_user:
        logger.info(f"Existing user creating new organization: {user.email}")
        # Verify password for existing user
        if not verify_password(user.password, existing_user.hashed_password):
            logger.warning(f"Invalid password for existing user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password for existing user"
            )
        
        # Update user info if provided
        if user.first_name and not existing_user.first_name:
            existing_user.first_name = user.first_name
        if user.last_name and not existing_user.last_name:
            existing_user.last_name = user.last_name
        db.commit()
    else:
        logger.info(f"New user registration: {user.email}")
    
    # If no tenant_id provided, create a new tenant for this user
    if not user.tenant_id:
        # Use organization_name from request or create default name
        tenant_name = getattr(user, 'organization_name', None)
        if not tenant_name:
            # Use existing user's name if available, otherwise fallback
            first_name = existing_user.first_name if is_existing_user and existing_user.first_name else user.first_name
            last_name = existing_user.last_name if is_existing_user and existing_user.last_name else user.last_name
            tenant_name = f"{first_name or 'User'}'s Organization"
            if first_name and last_name:
                tenant_name = f"{first_name} {last_name}'s Organization"

        # Only set address if provided
        tenant_address = getattr(user, 'organization_address', None) or getattr(user, 'address', None)

        # Create tenant
        logger.info(f"Creating new tenant for {user.email} with name {tenant_name}")
        # Ensure unique tenant name to satisfy DB unique constraint
        base_name = tenant_name
        suffix_attempt = 0
        from sqlalchemy.exc import IntegrityError
        while True:
            try:
                db_tenant = Tenant(
                    name=tenant_name,
                    email=user.email,
                    is_active=True,
                    address=tenant_address if tenant_address else None
                )
                db.add(db_tenant)
                db.commit()
                db.refresh(db_tenant)
                break
            except IntegrityError:
                db.rollback()
                suffix_attempt += 1
                import uuid
                # Append a short unique suffix and retry
                short = uuid.uuid4().hex[:6]
                tenant_name = f"{base_name} {short}"
        tenant_id = db_tenant.id
        logger.info(f"Created tenant {tenant_id} for {user.email}")

        # Create tenant database
        from core.services.tenant_database_manager import tenant_db_manager
        success = tenant_db_manager.create_tenant_database(tenant_id, tenant_name)
        logger.info(f"Tenant DB creation for {tenant_id}: {success}")
        if not success:
            logger.error(f"Failed to create tenant database for {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant database"
            )

        # Make user an admin for the new tenant they're creating
        user_role = "admin"
    else:
        # Verify tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant"
            )
        tenant_id = user.tenant_id
        user_role = user.role or "user"
        logger.info(f"Using existing tenant {tenant_id} for {user.email}")

    # Handle user creation/update
    if is_existing_user:
        db_user = existing_user
        logger.info(f"Using existing user {db_user.id} for {user.email}")
    else:
        # Check if this is the first user in the system
        user_count = db.query(MasterUser).count()
        is_first_user = user_count == 0

        # Create user in master database
        logger.info(f"Creating user in master DB: {user.email}")
        hashed_password = get_password_hash(user.password)
        db_user = MasterUser(
            email=user.email,
            hashed_password=hashed_password,
            first_name=user.first_name,
            last_name=user.last_name,
            tenant_id=tenant_id,
            role="admin" if is_first_user else user_role,
            is_active=user.is_active,
            is_superuser=is_first_user or user.is_superuser,
            is_verified=True  # Auto-verify new users during registration
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"Created user {db_user.id} in master DB for {user.email}")

    # Create user-tenant association for existing users creating new organizations
    if is_existing_user and tenant_id != existing_user.tenant_id:
        try:
            from core.models.models import user_tenant_association
            db.execute(
                user_tenant_association.insert().values(
                    user_id=existing_user.id,
                    tenant_id=tenant_id,
                    role=user_role
                )
            )
            db.commit()
            logger.info(f"Created user-tenant association for user {existing_user.id} with tenant {tenant_id}")
            
            # Update user's primary tenant to the new organization
            existing_user.tenant_id = tenant_id
            existing_user.role = user_role
            db.commit()
            logger.info(f"Updated user's primary tenant to {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to create user-tenant association: {str(e)}")
            # Don't fail the registration, but log the error

    # Also create user in tenant database
    from core.models.database import set_tenant_context
    set_tenant_context(tenant_id)

    try:
        logger.info(f"Creating/updating user in tenant DB {tenant_id} for {user.email}")
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()
        try:
            # Check if tenant user already exists
            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == db_user.id).first()

            if existing_tenant_user:
                # Update existing tenant user
                existing_tenant_user.email = user.email
                if not is_existing_user:
                    # Only update password if this is a new user registration
                    existing_tenant_user.hashed_password = db_user.hashed_password
                if user.first_name:
                    existing_tenant_user.first_name = user.first_name
                if user.last_name:
                    existing_tenant_user.last_name = user.last_name
                existing_tenant_user.role = user_role
                existing_tenant_user.is_active = user.is_active
                existing_tenant_user.is_superuser = db_user.is_superuser
                existing_tenant_user.is_verified = True  # Auto-verify new users during registration
                existing_tenant_user.updated_at = datetime.now(timezone.utc)
                tenant_db.commit()
                logger.info(f"Updated existing user {existing_tenant_user.id} in tenant DB {tenant_id} for {user.email}")
            else:
                # Create new tenant user
                if is_existing_user:
                    # Use existing user's hashed password
                    hashed_password = existing_user.hashed_password
                else:
                    # Use new user's hashed password
                    hashed_password = db_user.hashed_password
                
                tenant_user = TenantUser(
                    id=db_user.id,  # Use same ID as master user
                    email=user.email,
                    hashed_password=hashed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=user_role,
                    is_active=user.is_active,
                    is_superuser=db_user.is_superuser,
                    is_verified=True  # Auto-verify new users during registration
                )

                tenant_db.add(tenant_user)
                tenant_db.commit()
                logger.info(f"Created user {tenant_user.id} in tenant DB {tenant_id} for {user.email}")

        finally:
            try:
                tenant_db.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to create/update tenant user for {user.email} in tenant DB {tenant_id}: {str(e)}")
        logger.error(traceback.format_exc())
        # If tenant user creation fails and this was a new user, rollback master user creation
        if not is_existing_user:
            db.delete(db_user)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant user: {str(e)}"
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )

    # Get user organizations for response
    organizations = get_user_organizations(db, db_user)
    
    # Create user response with organizations
    user_response = UserRead.model_validate(db_user)
    user_response.organizations = organizations

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }

# Intentionally no /signup endpoint; /register is the canonical signup route.

# -------------------- Google OAuth (SSO) endpoints --------------------
@router.get("/google/login")
async def google_login(request: Request, next: Optional[str] = None):
    if not google_oauth_client:
        raise HTTPException(status_code=503, detail="Google SSO is not configured")

    # Determine redirect URI (callback)
    # Use UI_BASE_URL for external access (nginx on port 8080)
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
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

    base_url = str(request.base_url).rstrip("/")
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
    callback_url = f"{ui_base}/api/v1/auth/google/callback"

    # Exchange code for token
    try:
        token = await google_oauth_client.get_access_token(code, redirect_uri=callback_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {e}")

    # Fetch user info
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
        # Create a minimal tenant for first user if none exists yet, otherwise attach to the first active tenant
        # Determine if this is the first user in the system
        is_first_user = db.query(MasterUser).count() == 0
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
            first_name=None,
            last_name=None,
            role="admin" if is_first_user else "admin",  # Owner of the new tenant
            tenant_id=db_tenant.id,
            is_active=True,
            is_superuser=is_first_user,
            is_verified=bool(verified_email),
            google_id=str(google_id),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create tenant user mirror
        set_tenant_context(db_tenant.id)
        tenant_session = tenant_db_manager.get_tenant_session(db_tenant.id)
        tenant_db = tenant_session()
        try:
            tenant_user = TenantUser(
                id=user.id,
                email=email,
                hashed_password=user.hashed_password,
                first_name=None,
                last_name=None,
                role="admin",
                is_active=True,
                is_superuser=is_first_user,
                is_verified=True,
                google_id=str(google_id),
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()
        finally:
            tenant_db.close()
    else:
        # Ensure google_id is linked
        if not user.google_id:
            user.google_id = str(google_id)
            db.commit()

    # Issue JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    # Redirect back to UI with token via fragment so it doesn't hit server logs
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
    redirect_next = state_data.get("next") or "/dashboard"
    # Compose URL: e.g., /oauth-callback?token=...&user=...
    import json, base64
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
async def azure_login(request: Request, next: Optional[str] = None):
    if not azure_oauth_client:
        raise HTTPException(status_code=503, detail="Azure AD SSO is not configured")

    # Determine redirect URI (callback)
    # Use UI_BASE_URL for external access (nginx on port 8080)
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
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

    base_url = str(request.base_url).rstrip("/")
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
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
    azure_id = id_token_claims.get("oid")  # Object ID
    email = id_token_claims.get("email") or id_token_claims.get("preferred_username")
    azure_tenant_id = id_token_claims.get("tid")  # Tenant ID
    first_name = id_token_claims.get("given_name")
    last_name = id_token_claims.get("family_name")
    
    if not email:
        raise HTTPException(status_code=400, detail="Azure AD account has no email")
    if not azure_id:
        raise HTTPException(status_code=400, detail="Azure AD account has no object ID")

    # Find or create user in master database
    user = db.query(MasterUser).filter(
        (MasterUser.azure_ad_id == azure_id) | (MasterUser.email == email)
    ).first()
    
    if not user:
        # Create a minimal tenant for first user if none exists yet
        is_first_user = db.query(MasterUser).count() == 0
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
            role="admin" if is_first_user else "admin",  # Owner of the new tenant
            tenant_id=db_tenant.id,
            is_active=True,
            is_superuser=is_first_user,
            is_verified=True,  # Azure AD users are pre-verified
            azure_ad_id=str(azure_id),
            azure_tenant_id=str(azure_tenant_id) if azure_tenant_id else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create tenant user mirror
        set_tenant_context(db_tenant.id)
        tenant_session = tenant_db_manager.get_tenant_session(db_tenant.id)
        tenant_db = tenant_session()
        try:
            from core.models.models_per_tenant import User as TenantUser
            tenant_user = TenantUser(
                id=user.id,
                email=email,
                hashed_password=user.hashed_password,
                first_name=first_name,
                last_name=last_name,
                role="admin",
                is_active=True,
                is_superuser=is_first_user,
                is_verified=True,
                azure_ad_id=str(azure_id),
                azure_tenant_id=str(azure_tenant_id) if azure_tenant_id else None,
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()
        finally:
            tenant_db.close()
    else:
        # Ensure azure_ad_id is linked
        if not user.azure_ad_id:
            user.azure_ad_id = str(azure_id)
            user.azure_tenant_id = str(azure_tenant_id) if azure_tenant_id else None
            db.commit()

    # Issue JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)

    # Redirect back to UI with token
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
    redirect_next = state_data.get("next") or "/dashboard"
    import json, base64
    user_payload = UserRead.model_validate(user).model_dump()
    # Convert datetime objects to strings for JSON serialization
    def datetime_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    user_b64 = base64.urlsafe_b64encode(json.dumps(user_payload, default=datetime_serializer).encode()).decode()
    redirect_url = f"{ui_base}/oauth-callback?token={access_token}&user={user_b64}&next={redirect_next}"
    return RedirectResponse(url=redirect_url)

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_master_db)):
    # Rate limit by email
    email_key = (user_credentials.email or "").lower().strip()
    attempts = LOGIN_ATTEMPTS[email_key]
    _prune_attempts(attempts, RATE_LIMIT_WINDOW_SECONDS)
    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    attempts.append(time.time())
    user = db.query(MasterUser).filter(MasterUser.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND,
        )

    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INCORRECT_PASSWORD,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been disabled. Please contact your administrator."
        )
    
    # Check if tenant is active
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your organization has been disabled. Please contact support."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # Get user organizations for response
    organizations = get_user_organizations(db, user)
    
    # Create user response with organizations
    user_response = UserRead.model_validate(user)
    user_response.organizations = organizations

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }

@router.post("/change-password", response_model=PasswordResetResponse)
async def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Allow a logged-in user to change their password and clear must_reset_password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail=INCORRECT_PASSWORD)
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    current_user.must_reset_password = False
    db.commit()

    # Also update tenant DB
    try:
        tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        tenant_user = tenant_session.query(TenantUser).filter(TenantUser.id == current_user.id).first()
        if tenant_user:
            tenant_user.hashed_password = get_password_hash(payload.new_password)
            tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_user.must_reset_password = False
            tenant_session.commit()
        tenant_session.close()
    except Exception:
        pass

    return PasswordResetResponse(message="Password changed successfully.", success=True)

@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: MasterUser = Depends(get_current_user), db: Session = Depends(get_master_db)):
    # Get user's organizations
    from sqlalchemy.orm import joinedload
    from core.models.models import user_tenant_association

    # Get tenant memberships from association table
    tenant_memberships = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == current_user.id
        )
    ).fetchall()

    # Create a mapping of tenant_id to role from association table
    tenant_role_map = {membership.tenant_id: membership.role for membership in tenant_memberships}

    # Get all tenant IDs user has access to (including primary tenant)
    tenant_ids = [membership.tenant_id for membership in tenant_memberships]
    if current_user.tenant_id and current_user.tenant_id not in tenant_ids:
        tenant_ids.append(current_user.tenant_id)

    # Get tenant details
    organizations = []
    if tenant_ids:
        tenants = db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        # Sort by ID to ensure consistent ordering
        tenants = sorted(tenants, key=lambda t: t.id)
        for tenant in tenants:
            org_data = {'id': tenant.id, 'name': tenant.name}
            # Add role if available from association table, otherwise use master role for primary tenant
            if tenant.id in tenant_role_map:
                org_data['role'] = tenant_role_map[tenant.id]
            elif tenant.id == current_user.tenant_id:
                org_data['role'] = current_user.role
            organizations.append(org_data)
    
    # Create response with organizations
    user_data = UserRead.model_validate(current_user)
    user_dict = user_data.model_dump()
    user_dict['organizations'] = organizations

    return user_dict

@router.put("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update current user's profile (first_name, last_name)"""
    # Only allow updating first_name and last_name for now
    updated = False
    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name
        updated = True
    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name
        updated = True
    if user_update.theme is not None:
        current_user.theme = user_update.theme
        updated = True
    if hasattr(user_update, 'show_analytics') and user_update.show_analytics is not None:
        current_user.show_analytics = user_update.show_analytics
        updated = True
    if not updated:
        raise HTTPException(status_code=400, detail="No updatable fields provided.")
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    # Also update in tenant DB
    from core.models.database import set_tenant_context
    from core.services.tenant_database_manager import tenant_db_manager
    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
        if tenant_user:
            if user_update.first_name is not None:
                tenant_user.first_name = user_update.first_name
            if user_update.last_name is not None:
                tenant_user.last_name = user_update.last_name
            if user_update.theme is not None:
                tenant_user.theme = user_update.theme
            if hasattr(user_update, 'show_analytics') and user_update.show_analytics is not None:
                tenant_user.show_analytics = user_update.show_analytics
            tenant_db.commit()
            tenant_db.refresh(tenant_user)
    finally:
        tenant_db.close()

    return UserRead.model_validate(current_user)

@router.post("/invite", response_model=InviteRead)
async def invite_user(
    invite_data: InviteCreate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Invite a user to the organization (admin only)"""
    # Check if current user is admin
    require_admin(current_user, "invite users")
    
    # Normalize email for comparisons
    invite_email = (invite_data.email or "").strip()
    if not invite_email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Check if a master user with this email already exists globally
    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite_email)
    ).first()

    if existing_master_user:
        # If the user already has membership in this tenant or primary tenant matches, block inviting again
        from core.models.models import user_tenant_association
        membership = db.execute(
            user_tenant_association.select().where(
                user_tenant_association.c.user_id == existing_master_user.id,
                user_tenant_association.c.tenant_id == current_user.tenant_id
            )
        ).first()
        if membership or existing_master_user.tenant_id == current_user.tenant_id:
            raise HTTPException(status_code=400, detail="User already exists in this organization")
    
    # Check if invite already exists and is not expired
    existing_invite = db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(invite_email),
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="User already has a valid pending invite that has not expired")

    # Prevent re-inviting if a previously accepted invite exists for this tenant/email
    accepted_invite = db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(invite_email),
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == True
    ).first()
    if accepted_invite:
        raise HTTPException(status_code=400, detail="User already accepted an invite for this organization")

    # Also check direct existence in tenant database by email as a safeguard
    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
        try:
            tenant_user_exists = tenant_db.query(TenantUser).filter(func.lower(TenantUser.email) == func.lower(invite_email)).first()
            if tenant_user_exists:
                raise HTTPException(status_code=400, detail="User already exists in this organization")
        finally:
            tenant_db.close()
    except Exception:
        # If tenant DB lookup fails, continue; master checks above are sufficient
        pass
    
    # If there's an expired invite, we can create a new one (this will create a duplicate, but that's okay)
    # Alternatively, we could update the existing expired invite, but creating new is simpler
    
    # Create invite
    invite = Invite(
        email=invite_email,
        first_name=invite_data.first_name,
        last_name=invite_data.last_name,
        role=invite_data.role,
        token=generate_invite_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),  # 7 days expiry
        tenant_id=current_user.tenant_id,
        invited_by_id=current_user.id
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    # Send invite email via configured provider if available, otherwise fallback to console
    invite_path = f"/accept-invite?token={invite.token}"
    inviter_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    tenant_name = tenant.name if tenant else "Organization"
    ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
    accept_url = f"{ui_base}{invite_path}"

    # Try tenant-configured email service
    email_service = get_email_service_for_tenant(db, current_user.tenant_id)
    if email_service and tenant:
        try:
            # From details from core.settings
            email_settings = db.query(Settings).filter(
                Settings.tenant_id == current_user.tenant_id,
                Settings.key == "email_config"
            ).first()
            email_config_data = email_settings.value if email_settings else {}
            from_name = email_config_data.get('from_name', tenant_name)
            from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')
            invitee_name = (invite.first_name or "") + (" " + invite.last_name if invite.last_name else "")

            email_service.send_invitation_email(
                invitee_email=invite.email,
                invitee_name=invitee_name.strip() or invite.email,
                accept_url=accept_url,
                company_name=tenant_name,
                inviter_name=inviter_name,
                from_name=from_name,
                from_email=from_email,
                role=invite.role
            )
        except Exception:
            # Fallback to console
            send_invite_email(invite.email, accept_url, inviter_name, tenant_name)
    else:
        # Fallback to console
        send_invite_email(invite.email, accept_url, inviter_name, tenant_name)
    
    # Log audit event in master database
    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="invite",
        resource_id=str(invite.id),
        resource_name=f"Invite for {invite.email}",
        details=invite_data.dict(),
        tenant_id=current_user.tenant_id,
        status="success"
    )
    
    # Log audit event in tenant database as well
    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="invite",
            resource_id=str(invite.id),
            resource_name=f"Invite for {invite.email}",
            details=invite_data.dict(),
            status="success"
        )
    finally:
        tenant_db.close()
    
    # Manually construct response to handle invited_by field
    invite_response = InviteRead(
        id=invite.id,
        email=invite.email,
        first_name=invite.first_name,
        last_name=invite.last_name,
        role=invite.role,
        is_accepted=invite.is_accepted,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        invited_by=current_user.email
    )
    
    return invite_response

@router.get("/invites", response_model=List[InviteRead])
async def list_invites(
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all invites for the organization (admin only)"""
    require_admin(current_user, "view invites")
    
    invites = db.query(Invite).filter(
        Invite.tenant_id == current_user.tenant_id
    ).all()
    
    # Manually construct response to handle invited_by field
    result = []
    for invite in invites:
        inviter = db.query(MasterUser).filter(MasterUser.id == invite.invited_by_id).first()
        invite_dict = {
            "id": invite.id,
            "email": invite.email,
            "first_name": invite.first_name,
            "last_name": invite.last_name,
            "role": invite.role,
            "is_accepted": invite.is_accepted,
            "expires_at": invite.expires_at,
            "created_at": invite.created_at,
            "invited_by": inviter.email if inviter else None
        }
        result.append(InviteRead(**invite_dict))
    
    return result

@router.delete("/invites/{invite_id}", response_model=Dict[str, str])
async def cancel_invite(
    invite_id: int,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Cancel a pending invite (admin only)"""
    # Check if current user is admin
    require_admin(current_user, "cancel invites")
    
    # Find the invite
    invite = db.query(Invite).filter(
        Invite.id == invite_id,
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False
    ).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")
    
    # Check if invite is expired
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot cancel an expired invite")
    
    # Store invite details for audit logging
    invite_email = invite.email
    invite_role = invite.role
    
    # Delete the invite
    db.delete(invite)
    db.commit()
    
    # Log audit event in master database
    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="invite",
        resource_id=str(invite_id),
        resource_name=f"Invite for {invite_email}",
        details={
            "cancelled_invite_id": invite_id,
            "cancelled_email": invite_email,
            "cancelled_role": invite_role,
            "cancelled_by": current_user.email,
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )
    
    # Log audit event in tenant database as well
    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="invite",
            resource_id=str(invite_id),
            resource_name=f"Invite for {invite_email}",
            details={
                "cancelled_invite_id": invite_id,
                "cancelled_email": invite_email,
                "cancelled_role": invite_role,
                "cancelled_by": current_user.email,
                "cancelled_at": datetime.now(timezone.utc).isoformat()
            },
            status="success"
        )
    finally:
        tenant_db.close()
    
    return {"message": f"Invite for {invite_email} has been cancelled"}

@router.post("/accept-invite", response_model=Token)
async def accept_invite(
    invite_data: InviteAccept,
    db: Session = Depends(get_master_db)
):
    """Accept an invite and create user account"""
    # Find the invite
    invite = db.query(Invite).filter(
        Invite.token == invite_data.token,
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")
    
    # Check if user already exists
    existing_user = db.query(MasterUser).filter(
        MasterUser.email == invite.email,
        MasterUser.tenant_id == invite.tenant_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed_password = get_password_hash(invite_data.password)
    
    # Create or reuse a master user record for all invited roles, and mirror in tenant DB
    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite.email)
    ).first()

    if existing_master_user:
        master_user = existing_master_user
        # Do not modify existing global password or primary tenant here
    else:
        master_user = MasterUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=invite_data.first_name or invite.first_name,
            last_name=invite_data.last_name or invite.last_name,
            role=invite.role,
            tenant_id=invite.tenant_id,
            is_verified=True,
            is_superuser=False
        )
        db.add(master_user)
        db.commit()
        db.refresh(master_user)

    # Ensure membership association exists
    from core.models.models import user_tenant_association
    # Ensure membership exists (avoid duplicate insert if already a member)
    existing_membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == master_user.id,
            user_tenant_association.c.tenant_id == invite.tenant_id
        )
    ).first()
    if not existing_membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=invite.tenant_id,
                role=invite.role
            )
        )
        db.commit()

    # Create tenant user with the same ID
    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        # Check if tenant user already exists by ID (preferred) or email
        existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == master_user.id).first()
        if not existing_tenant_user:
            # Also check by email as fallback
            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.email == invite.email).first()

        if existing_tenant_user:
            # Update existing tenant user
            existing_tenant_user.email = invite.email
            existing_tenant_user.hashed_password = master_user.hashed_password
            existing_tenant_user.first_name = invite_data.first_name or invite.first_name
            existing_tenant_user.last_name = invite_data.last_name or invite.last_name
            existing_tenant_user.role = invite.role
            existing_tenant_user.is_verified = True
            existing_tenant_user.is_superuser = False
            existing_tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_db.commit()
        else:
            # Create new tenant user
            tenant_user = TenantUser(
                id=master_user.id,
                email=invite.email,
                hashed_password=master_user.hashed_password,
                first_name=invite_data.first_name or invite.first_name,
                last_name=invite_data.last_name or invite.last_name,
                role=invite.role,
                is_verified=True,
                is_superuser=False
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()
        user = master_user
    except Exception as e:
        # If tenant user creation fails, rollback master user to avoid inconsistent state
        db.delete(master_user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create tenant user: {str(e)}")
    finally:
        tenant_db.close()
    
    # Mark invite as accepted
    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Log audit event in master database for invite acceptance
    log_audit_event_master(
        db=db,
        user_id=0,  # No specific user ID since this is self-registration
        user_email=invite.email,
        action="ACCEPT",
        resource_type="invite",
        resource_id=str(invite.id),
        resource_name=f"Invite accepted by {invite.email}",
        details={
            "invite_id": invite.id,
            "accepted_email": invite.email,
            "role": invite.role,
            "accepted_at": datetime.now(timezone.utc).isoformat()
        },
        tenant_id=invite.tenant_id,
        status="success"
    )
    
    # Log audit event in tenant database as well
    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=0,  # No specific user ID since this is self-registration
            user_email=invite.email,
            action="ACCEPT",
            resource_type="invite",
            resource_id=str(invite.id),
            resource_name=f"Invite accepted by {invite.email}",
            details={
                "invite_id": invite.id,
                "accepted_email": invite.email,
                "role": invite.role,
                "accepted_at": datetime.now(timezone.utc).isoformat()
            },
            status="success"
        )
    finally:
        tenant_db.close()
    
    # Generate access token
    access_token = create_access_token(data={"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.get("/users", response_model=List[UserList])
async def list_users(
    current_user: MasterUser = Depends(get_current_user),
    master_db: Session = Depends(get_master_db)
):
    """List all users who have access to the current organization"""
    # Allow all authenticated users to see other users for assignment purposes
    # Only admins can see the full list for management purposes
    # Regular users can see activated users for reminder assignments
    
    from core.models.database import get_tenant_context
    current_tenant_id = get_tenant_context()
    if not current_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    # Get all users who have access to this tenant via association table
    from core.models.models import user_tenant_association
    
    # Get user IDs that have access to this tenant
    user_tenant_memberships = master_db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.tenant_id == current_tenant_id
        )
    ).fetchall()
    
    user_ids = [membership.user_id for membership in user_tenant_memberships]
    
    # Also include users whose primary tenant is this tenant
    primary_users = master_db.query(MasterUser).filter(
        MasterUser.tenant_id == current_tenant_id
    ).all()
    
    for user in primary_users:
        if user.id not in user_ids:
            user_ids.append(user.id)
    
    # Get all users with access to this tenant
    if user_ids:
        users = master_db.query(MasterUser).filter(MasterUser.id.in_(user_ids)).all()
        
        # Get tenant-specific roles for these users
        try:
            tenant_session = tenant_db_manager.get_tenant_session(current_tenant_id)
            tenant_db = tenant_session()
            try:
                # Get all tenant users for this tenant
                tenant_users = tenant_db.query(TenantUser).filter(
                    TenantUser.id.in_(user_ids)
                ).all()
                
                # Create a mapping of user_id to tenant role
                tenant_role_map = {tu.id: tu.role for tu in tenant_users}
                logger.info(f"Found {len(tenant_role_map)} tenant-specific roles: {tenant_role_map}")
                
                # Update roles for users who exist in tenant database
                for user in users:
                    if user.id in tenant_role_map:
                        # User exists in tenant, update role
                        user.role = tenant_role_map[user.id]
                        logger.info(f"Including user {user.email} with tenant role '{user.role}'")
                    else:
                        # User has access but not activated yet - keep their master role
                        logger.info(f"Including user {user.email} with master role '{user.role}' (not yet activated in tenant)")

            finally:
                tenant_db.close()
        except Exception as e:
            logger.warning(f"Failed to get tenant-specific roles for users in tenant {current_tenant_id}: {e}")
            # If tenant lookup fails, don't return any users to avoid showing unactivated users
            users = []

        logger.info(f"Returning {len(users)} users with roles: {[(u.email, u.role) for u in users]}")
        return users
    else:
        return []

@router.put("/users/{user_id}/role", response_model=UserList)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    tenant_id: Optional[int] = Query(None),
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update user role (admin only)"""
    require_admin(current_user, "update user roles")
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot update your own role")
    
    # Resolve current tenant context (must be provided via X-Tenant-ID or explicit tenant_id query)
    from core.models.database import get_tenant_context
    current_tenant_id = tenant_id or get_tenant_context()
    if not current_tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")

    # Authorization: require super admin or admin in the target tenant
    if not current_user.is_superuser:
        try:
            auth_tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
            try:
                me_in_tenant = auth_tenant_db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
                if not me_in_tenant or me_in_tenant.role != 'admin':
                    raise HTTPException(status_code=403, detail="ROLE_NOT_ALLOWED")
            finally:
                auth_tenant_db.close()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=403, detail="ROLE_NOT_ALLOWED")

    # Find user in master database (by id only), then ensure membership in current tenant
    user = db.query(MasterUser).filter(MasterUser.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent demotion of the organization owner (creator) by non-super-admins
    # A tenant's owner is the master user whose primary tenant_id equals the current tenant
    is_target_owner_of_current_tenant = (user.tenant_id == current_tenant_id)
    if is_target_owner_of_current_tenant and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot change role of the organization owner")
    
    # Ensure membership in current tenant and update role in association table
    from core.models.models import user_tenant_association
    membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == current_tenant_id
        )
    ).first()
    if not membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=user_id,
                tenant_id=current_tenant_id,
                role=role_update.role,
                is_active=True
            )
        )
    else:
        # Update existing membership role
        logger.info(f"Updating EXISTING membership for user {user_id} in tenant {current_tenant_id} to role {role_update.role}")
        db.execute(
            user_tenant_association.update()
            .where(
                user_tenant_association.c.user_id == user_id,
                user_tenant_association.c.tenant_id == current_tenant_id
            )
            .values(role=role_update.role, is_active=True)
        )
    db.commit()

    # Store old role for audit logging
    old_role = user.role
    logger.info(f"Updating role for user {user.email} (ID: {user_id}) from '{old_role}' to '{role_update.role}'")
    
    # Update role in tenant database only; reflect in response
    try:
        tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
        try:
            tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user_id).first()
            if tenant_user:
                tenant_user.role = role_update.role
                tenant_db.commit()
                logger.info(f"Updated role in tenant database for user {user.email}")
            else:
                # Create tenant user mirror if missing
                new_tenant_user = TenantUser(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=role_update.role,
                    is_verified=user.is_verified,
                    is_superuser=False
                )
                tenant_db.add(new_tenant_user)
                tenant_db.commit()
        finally:
            tenant_db.close()
    except Exception as e:
        logger.error(f"Failed to update role in tenant database for user {user.email}: {e}")

    # Create a copy of the user object for response with the tenant role
    # Don't modify the original user object to avoid any accidental persistence
    response_user = MasterUser(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role_update.role,  # Use the tenant role for response
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        tenant_id=user.tenant_id,
        theme=user.theme,
        google_id=user.google_id,
        created_at=user.created_at,
        updated_at=user.updated_at
    )
    
    # Log audit event in master database
    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="user_role",
        resource_id=str(user_id),
        resource_name=f"Role update for {user.email}",
        details={
            "updated_user_id": user_id,
            "updated_user_email": user.email,
            "old_role": old_role,
            "new_role": role_update.role,
            "updated_by": current_user.email
        },
        tenant_id=current_tenant_id,
        status="success"
    )
    
    # Log audit event in tenant database as well
    tenant_db = tenant_db_manager.get_tenant_session(current_tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="user_role",
            resource_id=str(user_id),
            resource_name=f"Role update for {user.email}",
            details={
                "updated_user_id": user_id,
                "updated_user_email": user.email,
                "old_role": old_role,
                "new_role": role_update.role,
                "updated_by": current_user.email
            },
            status="success"
        )
    finally:
        tenant_db.close()
    
    return response_user

@router.post("/invites/{invite_id}/activate", response_model=UserList)
async def admin_activate_user(
    invite_id: int,
    activation_data: AdminActivateUser,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Admin activates a pending invite by setting password and creating user account"""
    # Check if current user is admin
    require_admin(current_user, "activate users")
    
    # Find the invite
    invite = db.query(Invite).filter(
        Invite.id == invite_id,
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False
    ).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")
    
    # Check if invite is expired
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    # Check if user already exists
    existing_user = db.query(MasterUser).filter(
        MasterUser.email == invite.email,
        MasterUser.tenant_id == current_user.tenant_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Determine password strategy
    generated_temp_password: Optional[str] = None
    if activation_data.password and len(activation_data.password) >= 6:
        hashed_password = get_password_hash(activation_data.password)
    else:
        # Generate a secure temporary password and force reset on first login
        generated_temp_password = secrets.token_urlsafe(12)
        hashed_password = get_password_hash(generated_temp_password)
    
    # Mark invite as accepted
    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    
    # Commit invite changes
    db.commit()
    
    # Create or reuse a master user record
    existing_master_user = db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(invite.email)
    ).first()
    if existing_master_user:
        master_user = existing_master_user
        # Do not change global password for an existing user when activating
    else:
        master_user = MasterUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=activation_data.first_name or invite.first_name,
            last_name=activation_data.last_name or invite.last_name,
            role=invite.role,
            tenant_id=invite.tenant_id,
            is_verified=True,
            is_superuser=False
        )
        db.add(master_user)
        db.commit()
        db.refresh(master_user)
        # Require password reset only when password was auto-generated (not provided by admin)
        try:
            master_user.must_reset_password = bool(generated_temp_password is not None)
            db.commit()
        except Exception:
            db.rollback()

    # Ensure membership association exists
    from core.models.models import user_tenant_association
    # Ensure membership exists
    existing_membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == master_user.id,
            user_tenant_association.c.tenant_id == invite.tenant_id
        )
    ).first()
    if not existing_membership:
        db.execute(
            user_tenant_association.insert().values(
                user_id=master_user.id,
                tenant_id=invite.tenant_id,
                role=invite.role
            )
        )
        db.commit()

    # Create tenant user with the same ID
    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        # Check if tenant user already exists by ID (preferred) or email
        existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == master_user.id).first()
        if not existing_tenant_user:
            # Also check by email as fallback
            existing_tenant_user = tenant_db.query(TenantUser).filter(TenantUser.email == invite.email).first()

        if existing_tenant_user:
            # Update existing tenant user
            existing_tenant_user.email = invite.email
            existing_tenant_user.hashed_password = master_user.hashed_password
            existing_tenant_user.first_name = activation_data.first_name or invite.first_name
            existing_tenant_user.last_name = activation_data.last_name or invite.last_name
            existing_tenant_user.role = invite.role
            existing_tenant_user.is_verified = True
            existing_tenant_user.is_superuser = False
            existing_tenant_user.must_reset_password = master_user.must_reset_password
            existing_tenant_user.updated_at = datetime.now(timezone.utc)
            tenant_db.commit()
        else:
            # Create new tenant user
            tenant_user = TenantUser(
                id=master_user.id,
                email=invite.email,
                hashed_password=master_user.hashed_password,
                first_name=activation_data.first_name or invite.first_name,
                last_name=activation_data.last_name or invite.last_name,
                role=invite.role,
                is_verified=True,
                is_superuser=False,
                must_reset_password=master_user.must_reset_password
            )
            tenant_db.add(tenant_user)
            tenant_db.commit()

        # Ensure return user object
        user = master_user

        # If we generated a temp password for a new user, optionally email them a set-password/accept link
        if generated_temp_password:
            try:
                # Reuse invite accept link already generated earlier in this handler; build if missing
                ui_base = os.getenv("UI_BASE_URL") or "http://localhost:8080"
                accept_path = f"/accept-invite?token={invite.token}"
                accept_url = f"{ui_base}{accept_path}"
                tenant = db.query(Tenant).filter(Tenant.id == invite.tenant_id).first()
                email_service = get_email_service_for_tenant(db, invite.tenant_id)
                if email_service and tenant:
                    email_settings = db.query(Settings).filter(
                        Settings.tenant_id == invite.tenant_id,
                        Settings.key == "email_config"
                    ).first()
                    email_config_data = email_settings.value if email_settings else {}
                    from_name = email_config_data.get('from_name', tenant.name)
                    from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')
                    inviter = db.query(MasterUser).filter(MasterUser.id == invite.invited_by_id).first()
                    inviter_name = (f"{inviter.first_name or ''} {inviter.last_name or ''}").strip() or (inviter.email if inviter else tenant.name)
                    invitee_name = (activation_data.first_name or invite.first_name or "") + (" " + (activation_data.last_name or invite.last_name) if (activation_data.last_name or invite.last_name) else "")
                    email_service.send_invitation_email(
                        invitee_email=invite.email,
                        invitee_name=invitee_name.strip() or invite.email,
                        accept_url=accept_url,
                        company_name=tenant.name,
                        inviter_name=inviter_name,
                        from_name=from_name,
                        from_email=from_email,
                        role=invite.role
                    )
            except Exception:
                pass
    except Exception as e:
        # If tenant user creation fails, rollback master user to avoid inconsistent state
        db.delete(master_user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create tenant user: {str(e)}")
    finally:
        tenant_db.close()
    
    # Log audit event in master database (sanitize activation_data)
    activation_details = activation_data.dict()
    if 'password' in activation_details:
        activation_details.pop('password', None)
    log_audit_event_master(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="ACTIVATE",
        resource_type="user",
        resource_id=str(user.id) if hasattr(user, 'id') else None,
        resource_name=f"User {invite.email}",
        details={
            "invite_id": invite.id,
            "activated_email": invite.email,
            "role": invite.role,
            "activation_data": activation_details
        },
        tenant_id=current_user.tenant_id,
        status="success"
    )
    
    # Log audit event in tenant database as well (sanitize activation_data)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    try:
        log_audit_event(
            db=tenant_db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="ACTIVATE",
            resource_type="user",
            resource_id=str(user.id) if hasattr(user, 'id') else None,
            resource_name=f"User {invite.email}",
            details={
                "invite_id": invite.id,
                "activated_email": invite.email,
                "role": invite.role,
                "activation_data": activation_details
            },
            status="success"
        )
    finally:
        tenant_db.close()
    
    return user

@router.get("/check-email-availability")
async def check_email_availability(
    email: str,
    master_db: Session = Depends(get_master_db)
):
    """Check if an email address is available (public endpoint for signup)"""
    if not email or len(email.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be at least 3 characters long"
        )
    
    # Basic email format validation
    import re
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_pattern, email.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Check if email already exists (case-insensitive)
    existing_user = master_db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(email.strip())
    ).first()
    
    # Always return available: True to allow existing users to create new organizations
    # The actual validation will happen in the registration endpoint
    return {
        "available": True,
        "email": email.strip(),
        "user_exists": existing_user is not None
    }

@router.post("/request-password-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    master_db: Session = Depends(get_master_db)
):
    """Request a password reset for a user"""
    # Rate limit by email
    email_key = (request.email or "").lower().strip()
    attempts = PASSWORD_RESET_ATTEMPTS[email_key]
    _prune_attempts(attempts, RATE_LIMIT_WINDOW_SECONDS)
    if len(attempts) >= MAX_RESET_ATTEMPTS:
        # Return success but do not proceed
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )
    attempts.append(time.time())
    user = master_db.query(MasterUser).filter(
        func.lower(MasterUser.email) == func.lower(request.email.strip())
    ).first()
    
    # Always return success to prevent email enumeration
    if not user:
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )
    
    # Check if user is active
    if not user.is_active:
        return PasswordResetResponse(
            message="If the email address exists in our system, you will receive a password reset email shortly.",
            success=True
        )
    
    # Create password reset token
    reset_token = create_reset_token_entry(master_db, user.id)
    
    # Get tenant and email service configuration
    tenant = master_db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    email_service = get_email_service_for_tenant(master_db, user.tenant_id)
    
    # Try to send email if email service is configured
    if email_service and tenant:
        try:
            # Get email configuration for from details
            email_settings = master_db.query(Settings).filter(
                Settings.tenant_id == user.tenant_id,
                Settings.key == "email_config"
            ).first()
            
            email_config_data = email_settings.value if email_settings else {}
            from_name = email_config_data.get('from_name', tenant.name)
            from_email = email_config_data.get('from_email', 'noreply@invoiceapp.com')
            
            # Send password reset email
            user_display_name = f"{user.first_name} {user.last_name}".strip() or user.email
            
            success = email_service.send_password_reset_email(
                user_email=user.email,
                user_name=user_display_name,
                reset_token=reset_token.token,
                company_name=tenant.name,
                from_name=from_name,
                from_email=from_email
            )
            
            if success:
                print(f"Password reset email sent successfully to {user.email}")
            else:
                print(f"Failed to send password reset email to {user.email}")
                
        except Exception as e:
            print(f"Error sending password reset email to {user.email}: {str(e)}")
    else:
        # Fallback: Log token if email service is not configured
        print(f"Email service not configured for tenant {user.tenant_id}")
        print(f"Password reset token for {user.email}: {reset_token.token}")
        print(f"Reset URL: http://localhost:8080/reset-password?token={reset_token.token}")
    
    return PasswordResetResponse(
        message="If the email address exists in our system, you will receive a password reset email shortly.",
        success=True
    )

@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    request: PasswordResetConfirm,
    master_db: Session = Depends(get_master_db)
):
    """Reset user password using a valid token"""
    # Verify token
    reset_token = verify_reset_token(master_db, request.token)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    # Get user
    user = master_db.query(MasterUser).filter(MasterUser.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    # Validate password strength
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    user.updated_at = datetime.now(timezone.utc)
    
    # Mark token as used
    reset_token.is_used = True
    reset_token.used_at = datetime.now(timezone.utc)
    
    # Also update password in tenant database
    try:
        from core.models.database import set_tenant_context
        set_tenant_context(user.tenant_id)
        
        tenant_session = tenant_db_manager.get_tenant_session(user.tenant_id)
        tenant_db = tenant_session()
        try:
            tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user.id).first()
            if tenant_user:
                tenant_user.hashed_password = get_password_hash(request.new_password)
                tenant_user.updated_at = datetime.now(timezone.utc)
                tenant_db.commit()
        finally:
            tenant_db.close()
    except Exception as e:
        # If tenant user update fails, still allow master user password update
        print(f"Warning: Failed to update tenant user password: {str(e)}")
    
    master_db.commit()
    
    return PasswordResetResponse(
        message="Password has been reset successfully. You can now log in with your new password.",
        success=True
    )

@router.delete("/users/{user_id}", response_model=Dict[str, str])
async def remove_user_from_organization(
    user_id: int,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Remove a user from the current organization (admin only)"""
    require_admin(current_user, "remove users")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    from core.models.models import user_tenant_association
    from core.utils.user_sync import remove_user_from_tenant_database

    # Check if user has access to this tenant
    membership = db.execute(
        user_tenant_association.select().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == current_user.tenant_id
        )
    ).first()

    if not membership:
        # Check if it's their primary tenant
        user = db.query(MasterUser).filter(
            MasterUser.id == user_id,
            MasterUser.tenant_id == current_user.tenant_id
        ).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found in this organization")

        # Cannot remove user from their primary tenant
        raise HTTPException(status_code=400, detail="Cannot remove user from their home organization")

    # Get user details for logging
    user = db.query(MasterUser).filter(MasterUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove from association table
    db.execute(
        user_tenant_association.delete().where(
            user_tenant_association.c.user_id == user_id,
            user_tenant_association.c.tenant_id == current_user.tenant_id
        )
    )

    # Remove from tenant database
    remove_user_from_tenant_database(user_id, current_user.tenant_id)

    db.commit()

    return {"message": f"User {user.email} has been removed from the organization"}

@router.get("/sso-status")
async def get_sso_status():
    """Get the status of available SSO providers (public endpoint)"""
    # Check environment variables for SSO enablement
    google_enabled = os.getenv("GOOGLE_SSO_ENABLED", "false").lower() == "true" and google_oauth_client is not None
    azure_enabled = os.getenv("AZURE_SSO_ENABLED", "false").lower() == "true" and azure_oauth_client is not None

    return {
        "google": google_enabled,
        "microsoft": azure_enabled,
        "has_sso": google_enabled or azure_enabled
    }
