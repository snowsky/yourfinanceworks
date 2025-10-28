"""
Utility functions for sanitizing sensitive data before audit logging.

This module provides functions to safely sanitize data that might contain
encrypted fields before storing in audit logs or history records.
"""

from typing import Dict, Any, Optional, List, Union
import logging

logger = logging.getLogger(__name__)

# List of field names that typically contain encrypted data
ENCRYPTED_FIELD_NAMES = {
    'notes', 'description', 'email', 'first_name', 'last_name', 'name', 
    'phone', 'address', 'company', 'vendor', 'reference_number', 
    'attachment_filename', 'receipt_filename', 'provider_url', 'api_key',
    'user_email', 'ip_address', 'user_agent', 'google_id', 'azure_ad_id'
}

# List of field names that contain encrypted JSON data
ENCRYPTED_JSON_FIELD_NAMES = {
    'custom_fields', 'details', 'analysis_result', 'metadata'
}


def sanitize_for_audit(data: Union[Dict[str, Any], Any], 
                      preserve_structure: bool = True) -> Union[Dict[str, Any], Any]:
    """
    Sanitize data for audit logging by replacing encrypted fields with safe placeholders.
    
    Args:
        data: The data to sanitize (dict, list, or primitive)
        preserve_structure: Whether to preserve the original structure or return None for encrypted fields
        
    Returns:
        Sanitized data with encrypted fields replaced by placeholders
    """
    if data is None:
        return None
    
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            sanitized[key] = _sanitize_field(key, value, preserve_structure)
        return sanitized
    
    elif isinstance(data, list):
        return [sanitize_for_audit(item, preserve_structure) for item in data]
    
    else:
        # For primitive types, return as-is
        return data


def _sanitize_field(field_name: str, value: Any, preserve_structure: bool) -> Any:
    """
    Sanitize a single field based on its name and value.
    
    Args:
        field_name: Name of the field
        value: Value of the field
        preserve_structure: Whether to preserve structure
        
    Returns:
        Sanitized field value
    """
    if value is None:
        return None
    
    # Check if this field typically contains encrypted data
    if field_name.lower() in ENCRYPTED_FIELD_NAMES:
        if isinstance(value, str) and value.strip():
            return '[ENCRYPTED]' if preserve_structure else None
        else:
            return value
    
    # Check if this field contains encrypted JSON data
    elif field_name.lower() in ENCRYPTED_JSON_FIELD_NAMES:
        if value and (isinstance(value, dict) or isinstance(value, str)):
            return '[ENCRYPTED_JSON]' if preserve_structure else None
        else:
            return value
    
    # For nested structures, recursively sanitize
    elif isinstance(value, dict):
        return sanitize_for_audit(value, preserve_structure)
    
    elif isinstance(value, list):
        return [sanitize_for_audit(item, preserve_structure) for item in value]
    
    else:
        # For other fields, return as-is
        return value


def sanitize_model_dump(model_data: Dict[str, Any], 
                       additional_encrypted_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Sanitize data from a Pydantic model dump for audit logging.
    
    Args:
        model_data: Dictionary from model.model_dump()
        additional_encrypted_fields: Additional field names to treat as encrypted
        
    Returns:
        Sanitized model data
    """
    # Add any additional encrypted fields to the global set temporarily
    original_encrypted_fields = ENCRYPTED_FIELD_NAMES.copy()
    if additional_encrypted_fields:
        ENCRYPTED_FIELD_NAMES.update(field.lower() for field in additional_encrypted_fields)
    
    try:
        return sanitize_for_audit(model_data, preserve_structure=True)
    finally:
        # Restore original encrypted fields set
        ENCRYPTED_FIELD_NAMES.clear()
        ENCRYPTED_FIELD_NAMES.update(original_encrypted_fields)


def sanitize_history_values(values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize values for storing in history records (like InvoiceHistory).
    
    Args:
        values: Dictionary of field values
        
    Returns:
        Sanitized values safe for history storage
    """
    return sanitize_for_audit(values, preserve_structure=True)


def is_likely_encrypted_data(value: str) -> bool:
    """
    Check if a string value appears to be encrypted data.
    
    Args:
        value: String to check
        
    Returns:
        True if the value appears to be base64 encoded encrypted data
    """
    if not isinstance(value, str) or len(value) < 20:
        return False
    
    try:
        import base64
        import re
        
        # Check for base64 pattern
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(value):
            return False
        
        # Try to decode as base64
        decoded = base64.b64decode(value)
        # Encrypted data should have at least 12 bytes (nonce) + some ciphertext
        return len(decoded) >= 16
    except Exception:
        return False


def log_encrypted_data_warning(field_name: str, context: str = ""):
    """
    Log a warning when encrypted data is detected in audit logs.
    
    Args:
        field_name: Name of the field containing encrypted data
        context: Additional context about where this was detected
    """
    logger.warning(
        f"Encrypted data detected in audit log field '{field_name}'. "
        f"Context: {context}. This should be sanitized before logging."
    )


# Configuration for different audit contexts
AUDIT_SANITIZATION_CONFIGS = {
    'invoice_creation': {
        'preserve_fields': ['number', 'amount', 'currency', 'status', 'due_date'],
        'encrypt_fields': ['notes', 'description', 'custom_fields']
    },
    'invoice_update': {
        'preserve_fields': ['number', 'amount', 'currency', 'status', 'due_date'],
        'encrypt_fields': ['notes', 'description', 'custom_fields']
    },
    'client_creation': {
        'preserve_fields': ['balance', 'created_at'],
        'encrypt_fields': ['name', 'email', 'phone', 'address', 'company']
    },
    'expense_creation': {
        'preserve_fields': ['amount', 'currency', 'category', 'expense_date', 'status'],
        'encrypt_fields': ['vendor', 'notes', 'receipt_filename']
    }
}


def sanitize_for_context(data: Dict[str, Any], context: str) -> Dict[str, Any]:
    """
    Sanitize data based on a specific audit context.
    
    Args:
        data: Data to sanitize
        context: Audit context (e.g., 'invoice_creation')
        
    Returns:
        Sanitized data appropriate for the context
    """
    config = AUDIT_SANITIZATION_CONFIGS.get(context, {})
    preserve_fields = set(config.get('preserve_fields', []))
    encrypt_fields = set(config.get('encrypt_fields', []))
    
    sanitized = {}
    for key, value in data.items():
        if key in preserve_fields:
            # Keep these fields as-is
            sanitized[key] = value
        elif key in encrypt_fields or key.lower() in ENCRYPTED_FIELD_NAMES:
            # Sanitize these fields
            if value and isinstance(value, str):
                sanitized[key] = '[ENCRYPTED]'
            elif value and isinstance(value, dict):
                sanitized[key] = '[ENCRYPTED_JSON]'
            else:
                sanitized[key] = value
        else:
            # For other fields, apply default sanitization
            sanitized[key] = _sanitize_field(key, value, True)
    
    return sanitized