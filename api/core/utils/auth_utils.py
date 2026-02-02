from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional
import logging

from core.models.database import get_master_db
from core.models.models import MasterUser
from core.routers.auth import SECRET_KEY, ALGORITHM, security as jwt_security
from core.services.external_api_auth_service import ExternalAPIAuthService, AuthenticationMethod

logger = logging.getLogger(__name__)
external_auth_service = ExternalAPIAuthService()

async def get_current_sync_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(jwt_security),
    db: Session = Depends(get_master_db)
) -> MasterUser:
    """
    Dependency that supports both JWT (Bearer) and Static API Key (Bearer) for sync.
    If the token looks like a JWT, it validates it normally.
    If it looks like an API key (e.g. starts with ak_), it validates via API client.
    """
    token = credentials.credentials if credentials else None
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Try treating as JWT first
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email:
            user = db.query(MasterUser).filter(MasterUser.email == email).first()
            if user and user.is_active:
                return user
    except JWTError:
        # Not a valid JWT, or expired. 
        # If it looks like a JWT (3 parts), we might want to fail fast, 
        # but for sync specifically, we'll try the static key fallback.
        pass

    # 2. Try treating as Static API Key
    # Sync usually expects API keys starting with 'ak_'
    if token.startswith("ak_"):
        client_ip = request.client.host if request.client else "unknown"
        auth_context = await external_auth_service.authenticate_api_key(db, token, client_ip)
        
        if auth_context and auth_context.is_authenticated:
            # Load the user who owns this key
            user = db.query(MasterUser).filter(MasterUser.id == int(auth_context.user_id)).first()
            if user and user.is_active:
                # We return the user object so require_admin works
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again or check your API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )
