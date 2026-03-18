import asyncio
import concurrent.futures
from sqlalchemy.orm import Session
from core.models.models_per_tenant import AuditLog
from core.models.models import AuditLog as MasterAuditLog
from typing import Optional, Dict, Any
from datetime import datetime, date, timezone
import logging

logger = logging.getLogger(__name__)

_audit_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit")

# Import encryption services for decryption
try:
    from core.services.encryption_service import get_encryption_service
    from core.models.database import get_tenant_context
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger.warning("Encryption services not available for audit decryption")

def _looks_like_encrypted_data(value: str) -> bool:
    """
    Check if a string looks like encrypted data (base64 encoded and long).
    """
    if not isinstance(value, str) or len(value) < 30:
        return False
    
    # Check for base64 characteristics
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
    
    # If it contains common plain text patterns, it's probably not encrypted
    if '@' in value and '.' in value:  # Looks like email
        return False
    if value.isalpha() or value.isdigit():  # Simple text or numbers
        return False
    
    # Check if it matches base64 pattern and is long enough
    return base64_pattern.match(value) and len(value) > 30


def _safely_decrypt_data(encrypted_value: str, tenant_id: Optional[int] = None) -> str:
    """
    Safely attempt to decrypt encrypted data for audit logging.
    """
    if not ENCRYPTION_AVAILABLE:
        return "[ENCRYPTED_DATA_NO_SERVICE]"
    
    try:
        # Get tenant context if not provided
        if tenant_id is None:
            tenant_id = get_tenant_context()
        
        if tenant_id is None:
            return "[ENCRYPTED_DATA_NO_CONTEXT]"
        
        # Get encryption service and decrypt
        encryption_service = get_encryption_service()
        decrypted_value = encryption_service.decrypt_data(encrypted_value, tenant_id)
        
        logger.debug(f"Successfully decrypted audit data for tenant {tenant_id}")
        return decrypted_value
        
    except Exception as e:
        logger.debug(f"Failed to decrypt audit data: {str(e)}")
        return "[ENCRYPTED_DATA_DECRYPT_FAILED]"


def safe_extract_audit_data(data: Any, tenant_id: Optional[int] = None) -> Any:
    """
    Safely extract audit data by decrypting encrypted fields when possible.
    """
    if data is None:
        return None
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and _looks_like_encrypted_data(value):
                # Try to decrypt the encrypted value
                decrypted_value = _safely_decrypt_data(value, tenant_id)
                result[key] = decrypted_value
            else:
                result[key] = safe_extract_audit_data(value, tenant_id)
        return result
    
    elif isinstance(data, list):
        result = []
        for item in data:
            if isinstance(item, str) and _looks_like_encrypted_data(item):
                # Try to decrypt the encrypted value
                decrypted_value = _safely_decrypt_data(item, tenant_id)
                result.append(decrypted_value)
            else:
                result.append(safe_extract_audit_data(item, tenant_id))
        return result
    
    elif isinstance(data, str):
        # Check if this looks like encrypted data
        if _looks_like_encrypted_data(data):
            # Try to decrypt the string
            decrypted_value = _safely_decrypt_data(data, tenant_id)
            
            # If decryption failed, wrap in proper structure for JSON compatibility
            if decrypted_value.startswith("[ENCRYPTED_DATA_"):
                return {"encrypted_data": decrypted_value}
            else:
                return decrypted_value
        return data
    
    elif isinstance(data, (int, float, bool)):
        return data
    
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    
    else:
        # For other types, convert to string but check if it looks encrypted
        str_value = str(data)
        if _looks_like_encrypted_data(str_value):
            decrypted_value = _safely_decrypt_data(str_value, tenant_id)
            return {"encrypted_data": decrypted_value}
        return str_value


# Helper to convert all datetime objects in a dict/list to ISO strings
def convert_datetimes(obj):
    if isinstance(obj, dict):
        return {k: convert_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetimes(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    else:
        return obj


def _write_audit_log_sync(
    tenant_id: Optional[int],
    user_id: int,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    resource_name: Optional[str],
    details: Optional[Dict[str, Any]],
    ip_address: Optional[str],
    user_agent: Optional[str],
    status: str,
    error_message: Optional[str],
) -> None:
    """Write an audit log entry in its own DB session (safe for background thread use)."""
    try:
        from core.models.database import set_tenant_context
        from core.services.tenant_database_manager import tenant_db_manager

        if tenant_id:
            set_tenant_context(tenant_id)
            session_factory = tenant_db_manager.get_tenant_session(tenant_id)
            db = session_factory()
        else:
            from core.models.database import get_db as _get_db
            db = next(_get_db())

        try:
            if details is not None:
                details = safe_extract_audit_data(details, tenant_id)
                details = convert_datetimes(details)

            audit_log = AuditLog(
                user_id=user_id,
                user_email=user_email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message,
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            logger.error(f"Background audit log write failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Background audit log setup failed: {e}")


def log_audit_event(
    db: Session,
    user_id: int,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
):
    tenant_id = None
    try:
        tenant_id = get_tenant_context()
    except Exception:
        pass

    try:
        loop = asyncio.get_running_loop()
        # We're inside an async request — offload the write to avoid blocking
        loop.run_in_executor(
            _audit_executor,
            _write_audit_log_sync,
            tenant_id, user_id, user_email, action, resource_type,
            resource_id, resource_name, details,
            ip_address, user_agent, status, error_message,
        )
        return None
    except RuntimeError:
        # No running event loop (e.g. tests, CLI) — write synchronously
        if details is not None:
            details = safe_extract_audit_data(details, tenant_id)
            details = convert_datetimes(details)

        audit_log = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log


def log_audit_event_master(
    db: Session,
    user_id: int,
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    tenant_id: Optional[int] = None,
):
    """Log audit event in master database"""
    # Ensure details is JSON serializable and decrypt encrypted data
    if details is not None:
        # Use provided tenant_id or try to get from context
        if tenant_id is None:
            try:
                tenant_id = get_tenant_context()
            except:
                pass
        
        details = safe_extract_audit_data(details, tenant_id)
        details = convert_datetimes(details)
    
    audit_log = MasterAuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        error_message=error_message,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log 