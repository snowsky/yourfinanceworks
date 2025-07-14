from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import os
import secrets
import hashlib
from sqlalchemy import func

from models.database import get_db, get_master_db
from models.models import User, Tenant, MasterUser, Invite, PasswordResetToken, Settings  # Add PasswordResetToken, Settings import
from schemas.user import UserCreate, UserLogin, Token, UserRead, UserUpdate, InviteCreate, InviteRead, InviteAccept, UserList, UserRoleUpdate, AdminActivateUser
from schemas.password_reset import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
from services.email_service import EmailService, EmailProviderConfig, EmailProvider
from utils.auth import verify_password, get_password_hash
from models.models_per_tenant import User as TenantUser
from services.tenant_database_manager import tenant_db_manager
from middleware.tenant_context_middleware import set_tenant_context
from utils.rbac import require_admin

router = APIRouter(prefix="/auth", tags=["authentication"])

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
security = HTTPBearer()

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
        # Get email configuration from settings
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

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_master_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
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

@router.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_master_db)):
    # Check if user already exists
    db_user = db.query(MasterUser).filter(MasterUser.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # If no tenant_id provided, create a new tenant for this user
    if not user.tenant_id:
        # Use organization_name from request or create default name
        tenant_name = getattr(user, 'organization_name', None)
        if not tenant_name:
            tenant_name = f"{user.first_name or 'User'}'s Organization"
            if user.first_name and user.last_name:
                tenant_name = f"{user.first_name} {user.last_name}'s Organization"

        # Only set address if provided
        tenant_address = getattr(user, 'organization_address', None) or getattr(user, 'address', None)

        # Create tenant
        db_tenant = Tenant(
            name=tenant_name,
            email=user.email,
            is_active=True,
            address=tenant_address if tenant_address else None
        )
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        tenant_id = db_tenant.id

        # Create tenant database
        from services.tenant_database_manager import tenant_db_manager
        success = tenant_db_manager.create_tenant_database(tenant_id, tenant_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant database"
            )

        # Make first user of tenant an admin
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

    # Create user in master database
    hashed_password = get_password_hash(user.password)
    db_user = MasterUser(
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        tenant_id=tenant_id,
        role=user_role,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Also create user in tenant database
    from models.database import set_tenant_context
    set_tenant_context(tenant_id)
    
    try:
        tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session()
        
        try:
            # Import the tenant-specific User model (without tenant_id column)
            # from models.models_per_tenant import User as TenantUser
            
            # Create tenant user using the tenant-specific User model
            tenant_user = TenantUser(
                id=db_user.id,  # Use same ID as master user
                email=user.email,
                hashed_password=hashed_password,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user_role,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                is_verified=user.is_verified
            )
            
            tenant_db.add(tenant_user)
            tenant_db.commit()
            
        finally:
            tenant_db.close()
    except Exception as e:
        # If tenant user creation fails, rollback master user creation
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

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.from_orm(db_user)
    }

@router.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_master_db)):
    user = db.query(MasterUser).filter(MasterUser.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist. Please sign up first.",
        )

    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.from_orm(user)
    }

@router.get("/me", response_model=UserRead)
def read_users_me(current_user: MasterUser = Depends(get_current_user)):
    return UserRead.from_orm(current_user)

@router.put("/me", response_model=UserRead)
def update_current_user(
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
    if not updated:
        raise HTTPException(status_code=400, detail="No updatable fields provided.")
    db.commit()
    db.refresh(current_user)

    # Also update in tenant DB
    from models.database import set_tenant_context
    from services.tenant_database_manager import tenant_db_manager
    set_tenant_context(current_user.tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)
    tenant_db = tenant_session()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == current_user.id).first()
        if tenant_user:
            if user_update.first_name is not None:
                tenant_user.first_name = user_update.first_name
            if user_update.last_name is not None:
                tenant_user.last_name = user_update.last_name
            tenant_db.commit()
            tenant_db.refresh(tenant_user)
    finally:
        tenant_db.close()

    return UserRead.from_orm(current_user)

@router.post("/invite", response_model=InviteRead)
def invite_user(
    invite_data: InviteCreate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Invite a user to the organization (admin only)"""
    # Check if current user is admin
    require_admin(current_user, "invite users")
    
    # Check if user already exists
    existing_user = db.query(MasterUser).filter(
        MasterUser.email == invite_data.email,
        MasterUser.tenant_id == current_user.tenant_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in this organization")
    
    # Check if invite already exists and is not expired
    existing_invite = db.query(Invite).filter(
        Invite.email == invite_data.email,
        Invite.tenant_id == current_user.tenant_id,
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="User already has a valid pending invite that has not expired")
    
    # If there's an expired invite, we can create a new one (this will create a duplicate, but that's okay)
    # Alternatively, we could update the existing expired invite, but creating new is simpler
    
    # Create invite
    invite = Invite(
        email=invite_data.email,
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
    
    # Send invite email
    invite_url = f"/accept-invite?token={invite.token}"
    inviter_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    tenant_name = tenant.name if tenant else "Organization"
    
    send_invite_email(invite_data.email, invite_url, inviter_name, tenant_name)
    
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
def list_invites(
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

@router.post("/accept-invite", response_model=Token)
def accept_invite(
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
    
    # Create user in master database
    hashed_password = get_password_hash(invite_data.password)
    user = MasterUser(
        email=invite.email,
        hashed_password=hashed_password,
        first_name=invite_data.first_name or invite.first_name,
        last_name=invite_data.last_name or invite.last_name,
        role=invite.role,
        tenant_id=invite.tenant_id,
        is_verified=True
    )
    
    db.add(user)
    
    # Create user in tenant database
    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    
    try:
        tenant_user = TenantUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=invite_data.first_name or invite.first_name,
            last_name=invite_data.last_name or invite.last_name,
            role=invite.role,
            is_verified=True
        )
        
        tenant_db.add(tenant_user)
        tenant_db.commit()
    finally:
        tenant_db.close()
    
    # Mark invite as accepted
    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    # Generate access token
    access_token = create_access_token(data={"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.get("/users", response_model=List[UserList])
def list_users(
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all users in the organization (admin only)"""
    require_admin(current_user, "view users")
    
    users = db.query(MasterUser).filter(
        MasterUser.tenant_id == current_user.tenant_id
    ).all()
    
    return users

@router.put("/users/{user_id}/role", response_model=UserList)
def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update user role (admin only)"""
    require_admin(current_user, "update user roles")
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot update your own role")
    
    # Find user in master database
    user = db.query(MasterUser).filter(
        MasterUser.id == user_id,
        MasterUser.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update role in master database
    user.role = role_update.role
    db.commit()
    db.refresh(user)
    
    # Update role in tenant database
    set_tenant_context(current_user.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        tenant_user = tenant_db.query(TenantUser).filter(TenantUser.id == user_id).first()
        
        if tenant_user:
            tenant_user.role = role_update.role
            tenant_db.commit()
    finally:
        tenant_db.close()
    
    return user

@router.post("/invites/{invite_id}/activate", response_model=UserList)
def admin_activate_user(
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
    
    # Create user in master database
    hashed_password = get_password_hash(activation_data.password)
    user = MasterUser(
        email=invite.email,
        hashed_password=hashed_password,
        first_name=activation_data.first_name or invite.first_name,
        last_name=activation_data.last_name or invite.last_name,
        role=invite.role,
        tenant_id=invite.tenant_id,
        is_verified=True
    )
    
    db.add(user)
    
    # Mark invite as accepted
    invite.is_accepted = True
    invite.accepted_at = datetime.now(timezone.utc)
    
    # Commit master database changes first
    db.commit()
    db.refresh(user)
    
    # Create user in tenant database
    set_tenant_context(invite.tenant_id)
    tenant_db = tenant_db_manager.get_tenant_session(invite.tenant_id)()
    
    # Check if user already exists in tenant database
    existing_tenant_user = tenant_db.query(TenantUser).filter(
        TenantUser.email == invite.email
    ).first()
    
    if not existing_tenant_user:
        tenant_user = TenantUser(
            email=invite.email,
            hashed_password=hashed_password,
            first_name=activation_data.first_name or invite.first_name,
            last_name=activation_data.last_name or invite.last_name,
            role=invite.role,
            is_verified=True
        )
        
        tenant_db.add(tenant_user)
        tenant_db.commit()
    
    return user

@router.get("/check-email-availability")
def check_email_availability(
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
    
    return {
        "available": existing_user is None,
        "email": email.strip()
    }

@router.post("/request-password-reset", response_model=PasswordResetResponse)
def request_password_reset(
    request: PasswordResetRequest,
    master_db: Session = Depends(get_master_db)
):
    """Request a password reset for a user"""
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
def reset_password(
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
        from models.database import set_tenant_context
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
