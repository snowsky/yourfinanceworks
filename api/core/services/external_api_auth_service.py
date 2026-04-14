"""
External API authentication service for managing API keys and OAuth tokens.
"""

import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
import httpx

from core.models.models import MasterUser, Tenant
from core.models.api_models import APIClient
from core.routers.auth import SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)


class AuthContext:
    """Authentication context for API requests."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[set] = None,
        api_key_id: Optional[str] = None,
        authentication_method: Optional[str] = None,
        is_authenticated: bool = False,
        is_admin: bool = False,
        tenant_id: Optional[int] = None,
        is_sandbox: bool = False,
        allowed_document_types: Optional[List[str]] = None,
        custom_quotas: Optional[Dict[str, Any]] = None,
        user: Optional[MasterUser] = None,
        client_id: Optional[str] = None,
        api_key_prefix: Optional[str] = None,
    ):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.roles = roles or []
        self.permissions = permissions or set()
        self.api_key_id = api_key_id
        self.authentication_method = authentication_method
        self.is_authenticated = is_authenticated
        self.is_admin = is_admin
        self.tenant_id = tenant_id
        self.is_sandbox = is_sandbox
        self.allowed_document_types = allowed_document_types or []
        self.custom_quotas = custom_quotas or {}
        self.user = user
        self.client_id = client_id
        self.api_key_prefix = api_key_prefix or "api"


class Permission:
    """Permission constants."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    USER_MANAGEMENT = "user_management"
    INVOICE_READ = "invoice_read"
    INVOICE_WRITE = "invoice_write"
    EXPENSE_READ = "expense_read"
    EXPENSE_WRITE = "expense_write"
    TRANSACTION_PROCESSING = "transaction_processing"
    DOCUMENT_PROCESSING = "document_processing"


class AuthenticationMethod:
    """Authentication method constants."""

    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    INTERNAL_SECRET = "internal_secret"


class ExternalAPIAuthService:
    """Service for external API authentication and authorization."""

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash."""
        return self.hash_api_key(api_key) == hashed_key

    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        return f"ak_{secrets.token_urlsafe(32)}"

    def get_api_key_prefix(self, api_key: str) -> str:
        """Get the first 8 characters of API key for identification."""
        return api_key[:8] + "..."

    async def authenticate_jwt(
        self, db: Session, token: str
    ) -> Optional[AuthContext]:
        """Authenticate using a User JWT token (session fallback)."""
        try:
            from jose import jwt
            
            # Decode using the system secret (same as core auth)
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_email = payload.get("sub")
            if not user_email:
                return None
                
            # Look up the master user
            user = db.query(MasterUser).filter(MasterUser.email == user_email).first()
            if not user or not user.is_active:
                return None
                
            # Create auth context as a user
            return AuthContext(
                user_id=str(user.id),
                username=user.email,
                email=user.email,
                roles=["user"],
                permissions={
                    Permission.READ, 
                    Permission.WRITE, 
                    Permission.INVOICE_READ, 
                    Permission.INVOICE_WRITE, 
                    Permission.EXPENSE_READ, 
                    Permission.EXPENSE_WRITE, 
                    Permission.DOCUMENT_PROCESSING, 
                    Permission.TRANSACTION_PROCESSING
                },
                api_key_id="jwt_session",
                authentication_method=AuthenticationMethod.JWT,
                is_authenticated=True,
                is_admin=user.role == "admin" or user.is_superuser,
                tenant_id=user.tenant_id,
                allowed_document_types=["invoice", "expense", "statement"],
                user=user,
                client_id="jwt_session",
                api_key_prefix="jwt"
            )
        except Exception as e:
            logger.debug(f"JWT authentication failed in service: {e}")
            return None

    async def authenticate_api_key(
        self, db: Session, api_key: str, client_ip: str
    ) -> Optional[AuthContext]:
        """Authenticate using API key and return auth context."""

        if not api_key:
            return None

        # Hash the provided API key
        api_key_hash = self.hash_api_key(api_key)

        # Find matching API client
        api_client = (
            db.query(APIClient)
            .filter(APIClient.api_key_hash == api_key_hash, APIClient.is_active == True)
            .first()
        )

        if not api_client:
            return None

        # Check IP address restrictions
        if api_client.allowed_ip_addresses:
            if client_ip not in api_client.allowed_ip_addresses:
                # Check if IP is in any allowed ranges (basic CIDR support could be added)
                return None

        # Update usage statistics
        api_client.last_used_at = datetime.now(timezone.utc)
        api_client.total_requests += 1
        db.commit()

        # Get user information
        user = db.query(MasterUser).filter(MasterUser.id == api_client.user_id).first()
        if not user or not user.is_active:
            return None

        # Create auth context
        permissions = self._get_api_client_permissions(api_client)

        return AuthContext(
            user_id=str(user.id),
            username=f"api_client:{api_client.client_name}",
            email=user.email,
            roles=["api_client"],
            permissions=permissions,
            api_key_id=api_client.client_id,
            authentication_method=AuthenticationMethod.API_KEY,
            is_authenticated=True,
            is_admin=user.role == "admin" or user.is_superuser,
            tenant_id=user.tenant_id,
            is_sandbox=api_client.is_sandbox,
            allowed_document_types=api_client.allowed_document_types,
            custom_quotas=api_client.custom_quotas,
            user=user,
            client_id=api_client.client_id,
            api_key_prefix=api_client.api_key_prefix,
        )

    async def authenticate_internal_secret(
        self, db: Session, secret_key: str, tenant_id: Optional[int], user_email: Optional[str], plugin_id: Optional[str] = None
    ) -> Optional[AuthContext]:
        """Authenticate using an internal shared secret (sidecar trust)."""
        if not self.secret_key:
            logger.warning(
                "YFW_SECRET_KEY is not configured — internal-secret authentication is disabled. "
                "Set YFW_SECRET_KEY to enable sidecar plugin trust."
            )
            return None
        if not secret_key or not hmac.compare_digest(secret_key, self.secret_key):
            return None

        # 1. Start with provided context
        logger.debug(
            f"authenticate_internal_secret: plugin_id={plugin_id}, "
            f"tenant_id={tenant_id}, user_email={user_email}"
        )

        user = None
        
        # 2. Try to resolve User immediately if email is provided
        if user_email:
            if user_email == "admin@standalone":
                logger.warning(
                    f"Trusted plugin '{plugin_id}' is identifying as 'admin@standalone'. "
                    "This usually indicates the plugin is in fallback/dev mode."
                )
            
            user = db.query(MasterUser).filter(MasterUser.email == user_email).first()
            if user:
                logger.debug(f"Resolved user {user.id} from email {user_email}")
                # Supplement missing tenant_id from the resolved user
                if not tenant_id:
                    tenant_id = user.tenant_id
                    logger.debug(f"Supplemented missing tenant_id {tenant_id} from user {user.id}")

        # 3. Fallback to Service User Email if still no user/email but we have a tenant_id
        if not user and not user_email and tenant_id and plugin_id:
            from core.models.models import TenantPluginSettings
            settings = db.query(TenantPluginSettings).filter(TenantPluginSettings.tenant_id == tenant_id).first()
            if settings and settings.plugin_config:
                plugin_cfg = settings.plugin_config.get(plugin_id, {})
                fallback_email = plugin_cfg.get("public_access", {}).get("service_user_email")
                if fallback_email:
                    user_email = fallback_email
                    logger.info(f"Using fallback service user email '{user_email}' for plugin '{plugin_id}'")
                    # Try to resolve user again with the fallback email
                    user = db.query(MasterUser).filter(MasterUser.email == user_email).first()
                    if user:
                        logger.debug(f"Resolved service user {user.id} from fallback email {user_email}")

        # 4. If we still have no user:
        #    - If an email *was* supplied but not found, refuse (avoid silent misrouting).
        #    - If no email was supplied (public visitor, no JWT), fall back to the
        #      tenant's first active admin as a service account.  This lets public
        #      visitors upload files without requiring service_user_email config.
        if not user and tenant_id:
            if user_email:
                logger.warning(
                    f"Trusted plugin '{plugin_id}' supplied unresolvable email "
                    f"'{user_email}' for tenant {tenant_id}."
                )
                return None
            # Public visitor fallback — use tenant admin as service account
            admin = db.query(MasterUser).filter(
                MasterUser.tenant_id == tenant_id,
                MasterUser.role.in_(["admin", "superuser"]),
                MasterUser.is_active == True,
            ).first()
            if not admin:
                logger.warning(
                    f"Trusted plugin '{plugin_id}': no active admin found for "
                    f"tenant {tenant_id}, cannot service public visitor request."
                )
                return None
            user = admin
            user_email = admin.email
            logger.info(
                f"Public visitor for plugin '{plugin_id}': using tenant admin "
                f"'{admin.email}' (id={admin.id}) as service account."
            )

        # 5. Determine final tenant context
        resolved_tenant_id = tenant_id or (user.tenant_id if user else None)
        
        if not resolved_tenant_id:
             logger.warning(
                 f"No tenant context found for trusted plugin '{plugin_id}'. "
                 f"User: {user_email or 'None'}, Header Tenant: {tenant_id or 'None'}"
             )

        # Create trusted auth context
        return AuthContext(
            user_id=str(user.id) if user else "system",
            username=f"trusted_plugin:{user_email or 'system'}",
            email=user_email or (user.email if user else ""),
            roles=["trusted_plugin"],
            permissions={Permission.READ, Permission.WRITE, Permission.DOCUMENT_PROCESSING, Permission.TRANSACTION_PROCESSING},
            api_key_id="internal_trust",
            authentication_method=AuthenticationMethod.INTERNAL_SECRET,
            is_authenticated=True,
            is_admin=user.role == "admin" if user else True,
            tenant_id=resolved_tenant_id,
            is_sandbox=False,
            allowed_document_types=["invoice", "expense", "statement"],
            custom_quotas={},
            user=user,
            client_id="internal_trust",
            api_key_prefix="internal",
        )

    def _get_api_client_permissions(self, api_client: APIClient) -> set:
        """Get permissions for an API client based on its configuration."""
        permissions = {Permission.READ, Permission.WRITE}

        # Add specific permissions based on allowed document types
        if "invoice" in api_client.allowed_document_types:
            permissions.add(Permission.INVOICE_READ)
            permissions.add(Permission.INVOICE_WRITE)

        if "expense" in api_client.allowed_document_types:
            permissions.add(Permission.EXPENSE_READ)
            permissions.add(Permission.EXPENSE_WRITE)

        # Add transaction processing permission
        permissions.add(Permission.TRANSACTION_PROCESSING)
        permissions.add(Permission.DOCUMENT_PROCESSING)

        return permissions

    async def check_api_client_permissions(
        self,
        db: Session,
        api_client: APIClient,
        transaction_type: str,
        amount: float,
        currency: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if API client has permission for the requested operation."""

        # Normalize transaction type to lowercase for case-insensitive comparison
        normalized_type = (
            transaction_type.lower().strip()
            if isinstance(transaction_type, str)
            else transaction_type
        )

        # Check document type permissions (maps to transaction type validation)
        document_to_transaction = {
            "invoice": "invoice",
            "expense": "expense",
            "statement": "statement",
        }

        # Check if the transaction type is allowed based on document types
        allowed = False
        for doc_type in api_client.allowed_document_types:
            required_tx_type = document_to_transaction.get(doc_type)

            if doc_type == "statement":
                # For statements, allow both income and expense
                if normalized_type in ["income", "expense"]:
                    allowed = True
                    break
            elif required_tx_type == normalized_type:
                allowed = True
                break

        if not allowed:
            allowed_doc_types = ", ".join(api_client.allowed_document_types)
            return (
                False,
                f"Document type for transaction type '{transaction_type}' not allowed. Allowed document types: {allowed_doc_types}",
            )

        # Check amount limits
        if (
            api_client.max_transaction_amount
            and amount > api_client.max_transaction_amount
        ):
            return (
                False,
                f"Transaction amount {amount} exceeds maximum allowed {api_client.max_transaction_amount}",
            )

        return True, None

    async def check_rate_limits(
        self,
        db: Session,
        api_client: APIClient,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Check rate limits for an API client."""

        if not current_time:
            current_time = datetime.now(timezone.utc)

        # This is a simplified rate limiting check
        # In production, you'd want to use Redis or a proper rate limiting service

        # For now, we'll implement a basic check based on request counts
        # This should be replaced with a proper rate limiter in production

        # Check if we have recent usage data (this would be stored in Redis in production)
        # For now, we'll allow all requests and rely on middleware rate limiting

        return True, None, None

    def create_oauth_access_token(
        self, client_id: str, user_id: int, scopes: List[str], expires_in: int = 3600
    ) -> str:
        """Create an OAuth 2.0 access token."""

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "client_id": client_id,
            "scopes": scopes,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "type": "access_token",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_oauth_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode an OAuth 2.0 access token."""

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != "access_token":
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def authenticate_oauth_token(
        self, db: Session, token: str, required_scopes: Optional[List[str]] = None
    ) -> Optional[AuthContext]:
        """Authenticate using OAuth 2.0 access token."""

        payload = self.verify_oauth_token(token)
        if not payload:
            return None

        client_id = payload.get("client_id")
        user_id = payload.get("sub")
        token_scopes = payload.get("scopes", [])

        # Check required scopes
        if required_scopes:
            if not all(scope in token_scopes for scope in required_scopes):
                return None

        # Find API client
        api_client = (
            db.query(APIClient)
            .filter(APIClient.oauth_client_id == client_id, APIClient.is_active == True)
            .first()
        )

        if not api_client:
            return None

        # Get user
        user = db.query(MasterUser).filter(MasterUser.id == int(user_id)).first()
        if not user or not user.is_active:
            return None

        # Update usage statistics
        api_client.last_used_at = datetime.now(timezone.utc)
        api_client.total_requests += 1
        db.commit()

        # Create auth context
        permissions = self._get_oauth_permissions(token_scopes)

        return AuthContext(
            user_id=str(user.id),
            username=f"oauth_client:{api_client.client_name}",
            email=user.email,
            roles=["oauth_client"],
            permissions=permissions,
            api_key_id=api_client.client_id,
            authentication_method=AuthenticationMethod.OAUTH2,
            is_authenticated=True,
            is_admin=False,
            tenant_id=api_client.tenant_id,
            allowed_document_types=api_client.allowed_document_types,
            custom_quotas=api_client.custom_quotas,
            user=user,
            client_id=api_client.client_id,
            api_key_prefix=api_client.api_key_prefix,
        )

    def _get_oauth_permissions(self, scopes: List[str]) -> set:
        """Convert OAuth scopes to internal permissions."""
        permissions = set()

        scope_permission_map = {
            "read": Permission.READ,
            "write": Permission.WRITE,
            "invoices:read": Permission.INVOICE_READ,
            "invoices:write": Permission.INVOICE_WRITE,
            "expenses:read": Permission.EXPENSE_READ,
            "expenses:write": Permission.EXPENSE_WRITE,
            "transactions:read": Permission.READ,
            "transactions:write": Permission.WRITE,
            "documents:process": Permission.DOCUMENT_PROCESSING,
            "admin": Permission.ADMIN,
        }

        for scope in scopes:
            if scope in scope_permission_map:
                permissions.add(scope_permission_map[scope])

        return permissions

    def create_oauth_refresh_token(
        self, client_id: str, user_id: int, scopes: List[str]
    ) -> str:
        """Create an OAuth 2.0 refresh token."""

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "client_id": client_id,
            "scopes": scopes,
            "iat": now,
            "exp": now + timedelta(days=30),  # Refresh tokens last longer
            "type": "refresh_token",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def refresh_oauth_token(
        self, db: Session, refresh_token: str, client_id: str, client_secret: str
    ) -> Optional[Dict[str, Any]]:
        """Refresh an OAuth 2.0 access token using a refresh token."""

        # Verify refresh token
        payload = self.verify_oauth_token(refresh_token)
        if not payload or payload.get("type") != "refresh_token":
            return None

        token_client_id = payload.get("client_id")
        if token_client_id != client_id:
            return None

        # Find and verify OAuth client
        api_client = (
            db.query(APIClient)
            .filter(APIClient.oauth_client_id == client_id, APIClient.is_active == True)
            .first()
        )

        if not api_client:
            return None

        # Verify client secret
        if not self.pwd_context.verify(
            client_secret, api_client.oauth_client_secret_hash
        ):
            return None

        # Create new access token
        user_id = int(payload.get("sub"))
        scopes = payload.get("scopes", [])

        access_token = self.create_oauth_access_token(
            client_id=client_id, user_id=user_id, scopes=scopes, expires_in=3600
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": " ".join(scopes),
        }

    async def validate_webhook_signature(
        self, payload: bytes, signature: str, webhook_secret: str
    ) -> bool:
        """Validate webhook signature for secure webhook delivery."""

        if not webhook_secret:
            return False

        # Create HMAC signature
        import hmac

        expected_signature = hmac.new(
            webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant time comparison)
        return hmac.compare_digest(f"sha256={expected_signature}", signature)

    async def send_webhook_notification(
        self,
        webhook_url: str,
        webhook_secret: Optional[str],
        event_type: str,
        data: Dict[str, Any],
    ) -> bool:
        """Send webhook notification to external system."""

        if not webhook_url:
            return False

        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        import json

        payload_bytes = json.dumps(payload).encode()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "InvoiceApp-Webhook/1.0",
        }

        # Add signature if webhook secret is provided
        if webhook_secret:
            import hmac

            signature = hmac.new(
                webhook_secret.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url, content=payload_bytes, headers=headers
                )

                # Consider 2xx responses as successful
                return 200 <= response.status_code < 300

        except Exception:
            # Log the error in production
            return False
