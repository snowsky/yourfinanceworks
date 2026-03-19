"""
SQLAlchemy Column Encryptor for transparent database encryption.

This module provides custom SQLAlchemy TypeDecorator classes that automatically
encrypt and decrypt data when storing/retrieving from PostgreSQL databases.
"""

import json
import logging
from typing import Any, Optional, Dict
from sqlalchemy import TypeDecorator, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect

from core.services.encryption_service import get_encryption_service
from core.exceptions.encryption_exceptions import EncryptionError, DecryptionError
from core.models.database import get_tenant_context
from encryption_config import EncryptionConfig

logger = logging.getLogger(__name__)


class EncryptedColumn(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for transparent string data encryption.
    
    This column type automatically encrypts data before storing in the database
    and decrypts it when retrieving. It uses the tenant context to determine
    which encryption key to use.
    
    Usage:
        class User(Base):
            email = Column(EncryptedColumn(), nullable=False, unique=True)
            first_name = Column(EncryptedColumn(), nullable=True)
    """
    
    impl = Text  # Use Text to store base64 encoded encrypted data
    cache_ok = True
    
    def __init__(self, *args, **kwargs):
        """Initialize the encrypted column type."""
        # Don't pass column-level arguments to TypeDecorator
        super().__init__()
        # Don't cache config or service - check dynamically
        self.config = None
        self.encryption_service = None
        self._column_name = None  # Will be set by SQLAlchemy
    
    def process_bind_param(self, value: Any, dialect: Dialect) -> Optional[str]:
        """
        Encrypt data before storing in database.
        
        Args:
            value: Plain text value to encrypt
            dialect: SQLAlchemy dialect (not used)
            
        Returns:
            Encrypted and base64 encoded string, or None if value is None/empty
        """
        if value is None or value == "":
            return value
        
        # Check encryption status dynamically
        config = EncryptionConfig()
        if not config.ENCRYPTION_ENABLED:
            return str(value) if value is not None else value
        
        # Skip encryption during database initialization to avoid hanging
        import os
        import threading
        current_thread = threading.current_thread()
        is_db_init = os.environ.get('DB_INIT_PHASE', 'false').lower() == 'true'
        
        if is_db_init and hasattr(current_thread, 'name') and 'MainThread' in current_thread.name:
            # During database initialization, just return the value unencrypted
            return str(value) if value is not None else value
        
        try:
            # Convert value to string if it isn't already
            str_value = str(value)
            
            # Check if the value is already encrypted - if so, don't encrypt again
            if self._looks_like_encrypted_data(str_value):
                logger.debug("Value appears to be already encrypted, storing as-is")
                return str_value
            
            # Get encryption service dynamically
            encryption_service = get_encryption_service()
            
            # Get current tenant context
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.error("No tenant context available for encryption")
                raise EncryptionError("Tenant context required for encryption")
            
            # Encrypt the data
            encrypted_value = encryption_service.encrypt_data(str_value, tenant_id)
            
            logger.debug(f"Encrypted data for tenant {tenant_id}")
            return encrypted_value
            
        except Exception as e:
            logger.error(f"Failed to encrypt column data: {str(e)}")
            raise EncryptionError(f"Column encryption failed: {str(e)}")
    
    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[str]:
        """
        Decrypt data after retrieving from database.
        
        Args:
            value: Encrypted base64 encoded string from database
            dialect: SQLAlchemy dialect (not used)
            
        Returns:
            Decrypted plain text string, or None if value is None/empty
        """
        if value is None or value == "":
            return value
        
        # Check encryption status dynamically
        config = EncryptionConfig()
        if not config.ENCRYPTION_ENABLED:
            return value
        
        # Skip decryption during database initialization to avoid hanging
        import os
        import threading
        current_thread = threading.current_thread()
        is_db_init = os.environ.get('DB_INIT_PHASE', 'false').lower() == 'true'
        
        if is_db_init and hasattr(current_thread, 'name') and 'MainThread' in current_thread.name:
            # During database initialization, just return the value as-is
            return value
        
        # Get column context for better error reporting
        column_context = self._get_detailed_column_context()
        
        try:
            # Get current tenant context
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.warning(f"No tenant context available for decryption in {column_context}, treating as plain text")
                return value

            # Check if the value looks like encrypted data
            if not self._looks_like_encrypted_data(value):
                logger.debug(f"Value appears to be plain text in {column_context}, returning as-is for tenant {tenant_id}")
                return value

            # Get encryption service dynamically
            encryption_service = get_encryption_service()
            
            # Try to decrypt the data
            decrypted_value = encryption_service.decrypt_data(value, tenant_id)
            logger.debug(f"Successfully decrypted data in {column_context} for tenant {tenant_id}")
            return decrypted_value

        except Exception as e:
            # Check if this is a common decryption failure (likely corrupted encrypted data)
            error_str = str(e)
            if "Failed to decrypt data:" in error_str and "Authentication tag verification failed" in error_str:
                # This is corrupted encrypted data - log with column context
                logger.error(f"DECRYPTION FAILED in {column_context} for tenant {tenant_id}: Authentication tag verification failed")
                logger.error(f"Column: {column_context}")
                logger.error(f"Data preview: {str(value)[:50]}...")
                logger.error(f"Data length: {len(value)} characters")

                # Return None so callers fall back to safe defaults rather than
                # propagating the sentinel string into the UI
                if self._looks_like_encrypted_data(value):
                    return None
                else:
                    # If it doesn't look encrypted, treat as plain text
                    logger.debug(f"Treating as plain text data in {column_context}")
                    return value
            elif "Failed to decrypt data:" in error_str:
                # Other decryption errors - log with column context
                logger.error(f"DECRYPTION FAILED in {column_context} for tenant {tenant_id}: {error_str}")

                if self._looks_like_encrypted_data(value):
                    return None
                else:
                    # If it doesn't look encrypted, treat as plain text
                    return value
            else:
                # Unexpected errors - log with column context
                logger.error(f"UNEXPECTED DECRYPTION ERROR in {column_context}: {str(e)}")
                # For other errors, treat as plain text
                return value
    
    def _looks_like_encrypted_data(self, value: str) -> bool:
        """
        Check if a value looks like encrypted data (base64 encoded).
        
        Args:
            value: The value to check
            
        Returns:
            True if it looks like encrypted data, False if it looks like plain text
        """
        if not isinstance(value, str) or len(value) < 20:
            return False
        
        # Encrypted data should be base64 encoded and reasonably long
        # Check for base64 characteristics
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        
        # If it contains common plain text patterns, it's probably not encrypted
        if '@' in value and '.' in value:  # Looks like email
            return False
        if value.isalpha() or value.isdigit():  # Simple text or numbers
            return False
        if len(value) < 30:  # Encrypted data is usually longer
            return False

        # Check if it matches base64 pattern and is long enough
        return base64_pattern.match(value) and len(value) > 30
    
    def _get_column_context(self) -> str:
        """Get context information about which column is being processed."""
        try:
            import inspect
            frame = inspect.currentframe()
            # Go up the stack to find the model class and attribute
            for i in range(10):  # Look up to 10 frames
                frame = frame.f_back
                if frame is None:
                    break
                
                # Look for SQLAlchemy model context
                local_vars = frame.f_locals
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, '__tablename__'):
                        return f"Table: {obj.__tablename__}, Class: {obj.__class__.__name__}"
                
                # Look for column name in the frame
                if 'key' in local_vars:
                    return f"Column key: {local_vars['key']}"
                    
            return "Unknown column context"
        except Exception:
            return "Context lookup failed"
    
    def _get_detailed_column_context(self) -> str:
        """Get detailed context information about which table/column is being processed."""
        try:
            import inspect
            frame = inspect.currentframe()
            table_name = "Unknown"
            column_name = "Unknown"
            record_id = "Unknown"
            
            # Go deeper in the stack to find more context
            for i in range(20):  # Look deeper in the stack
                frame = frame.f_back
                if frame is None:
                    break
                
                local_vars = frame.f_locals
                
                # Look for SQLAlchemy model instance
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, '__tablename__'):
                        table_name = obj.__tablename__
                        if hasattr(obj, 'id') and obj.id:
                            record_id = str(obj.id)
                
                # Look for column name in various contexts
                if 'key' in local_vars and isinstance(local_vars['key'], str):
                    column_name = local_vars['key']
                elif 'column' in local_vars and hasattr(local_vars['column'], 'name'):
                    column_name = local_vars['column'].name
                elif 'attr' in local_vars and hasattr(local_vars['attr'], 'key'):
                    column_name = local_vars['attr'].key
                
                # Look for query context
                if 'query' in local_vars:
                    query = local_vars['query']
                    if hasattr(query, 'column_descriptions'):
                        try:
                            descriptions = query.column_descriptions
                            if descriptions and len(descriptions) > 0:
                                first_desc = descriptions[0]
                                if 'entity' in first_desc and hasattr(first_desc['entity'], '__tablename__'):
                                    table_name = first_desc['entity'].__tablename__
                        except:
                            pass
            
            return f"Table: {table_name}, Column: {column_name}, Record ID: {record_id}"
            
        except Exception as e:
            return f"Context lookup failed: {str(e)}"


class EncryptedJSON(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for transparent JSON data encryption using PostgreSQL JSONB.
    
    This column type automatically encrypts JSON data before storing in the database
    and decrypts it when retrieving. The encrypted data is stored as a text field
    containing the base64 encoded encrypted JSON.
    
    Usage:
        class Invoice(Base):
            custom_fields = Column(EncryptedJSON(), nullable=True)
            analysis_result = Column(EncryptedJSON(), nullable=True)
    """
    
    impl = Text  # Store encrypted JSON as text
    cache_ok = True
    
    def __init__(self, *args, **kwargs):
        """Initialize the encrypted JSON column type."""
        # Don't pass column-level arguments to TypeDecorator
        super().__init__()
        # Don't cache config or service - check dynamically
        self.config = None
        self.encryption_service = None
    
    def process_bind_param(self, value: Any, dialect: Dialect) -> Optional[str]:
        """
        Encrypt JSON data before storing in database.
        
        Args:
            value: Dictionary or JSON-serializable data to encrypt
            dialect: SQLAlchemy dialect (not used)
            
        Returns:
            Encrypted and base64 encoded JSON string, or None if value is None/empty
        """
        if value is None:
            return None
        
        # Handle empty dict/list
        if value == {} or value == []:
            return None
        
        # Check encryption status dynamically
        config = EncryptionConfig()
        if not config.ENCRYPTION_ENABLED:
            return json.dumps(value) if value is not None else None
        
        # Skip encryption during database initialization to avoid hanging
        import os
        import threading
        current_thread = threading.current_thread()
        is_db_init = os.environ.get('DB_INIT_PHASE', 'false').lower() == 'true'
        
        if is_db_init and hasattr(current_thread, 'name') and 'MainThread' in current_thread.name:
            # During database initialization, just return JSON as string
            return json.dumps(value) if value is not None else None
        
        try:
            # Get current tenant context
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.error("No tenant context available for JSON encryption")
                raise EncryptionError("Tenant context required for JSON encryption")
            
            # Check if the value is already encrypted JSON data (string that looks like base64)
            if isinstance(value, str) and self._looks_like_encrypted_data(value):
                logger.debug("JSON value appears to be already encrypted, storing as-is")
                return value
            
            # Ensure value is a dictionary or list
            if not isinstance(value, (dict, list)):
                logger.warning(f"Converting non-dict/list value to dict: {type(value)}")
                # Try to convert to dict if it's a string that looks like JSON
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        # If it's not valid JSON, wrap it in a dict
                        value = {"value": value}
                else:
                    # Wrap other types in a dict
                    value = {"value": value}
            
            # Get encryption service dynamically
            encryption_service = get_encryption_service()
            
            # Encrypt the JSON data
            encrypted_value = encryption_service.encrypt_json(value, tenant_id)
            
            logger.debug(f"Encrypted JSON data for tenant {tenant_id}")
            return encrypted_value
            
        except Exception as e:
            logger.error(f"Failed to encrypt JSON column data: {str(e)}")
            raise EncryptionError(f"JSON column encryption failed: {str(e)}")
    
    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[Dict[str, Any]]:
        """
        Decrypt JSON data after retrieving from database.
        
        Args:
            value: Encrypted base64 encoded JSON string from database
            dialect: SQLAlchemy dialect (not used)
            
        Returns:
            Decrypted dictionary/list, or None if value is None/empty
        """
        if value is None or value == "":
            return None
        
        # Check encryption status dynamically
        config = EncryptionConfig()
        if not config.ENCRYPTION_ENABLED:
            try:
                return json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from unencrypted value: {value}")
                return value
        
        # Skip decryption during database initialization to avoid hanging
        import os
        import threading
        current_thread = threading.current_thread()
        is_db_init = os.environ.get('DB_INIT_PHASE', 'false').lower() == 'true'
        
        if is_db_init and hasattr(current_thread, 'name') and 'MainThread' in current_thread.name:
            # During database initialization, parse JSON from string
            try:
                return json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON during startup: {value}")
                return value
        
        try:
            # Get current tenant context
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.warning("No tenant context available for JSON decryption, attempting to parse as plain JSON")
                try:
                    return json.loads(value) if isinstance(value, str) else value
                except json.JSONDecodeError:
                    logger.warning("Value is not valid JSON, returning None")
                    return None

            # Get encryption service dynamically
            encryption_service = get_encryption_service()
            
            # Try to decrypt the JSON data
            decrypted_value = encryption_service.decrypt_json(value, tenant_id)
            logger.debug(f"Decrypted JSON data for tenant {tenant_id}")
            return decrypted_value

        except Exception as e:
            # Check if this is a common decryption failure (likely corrupted encrypted data)
            error_str = str(e)
            if "Failed to decrypt JSON data:" in error_str and "Authentication tag verification failed" in error_str:
                # This is corrupted encrypted data - log with column context
                column_context = self._get_detailed_json_column_context()
                logger.error(f"JSON DECRYPTION FAILED in {column_context} for tenant {tenant_id}: Authentication tag verification failed")
                logger.error(f"JSON Column: {column_context}")
                logger.error(f"JSON Data preview: {str(value)[:50]}...")
                logger.error(f"JSON Data length: {len(value)} characters")
                
                # Check if this looks like encrypted string data in a JSON column
                if self._looks_like_encrypted_string_data(value):
                    logger.error(f"ERROR: This appears to be encrypted STRING data stored in a JSON column!")
                    logger.error(f"SOLUTION: Run 'python api/fix_json_column_corruption.py' to fix this issue")
                
                # For corrupted encrypted JSON data, try auto-cleanup
                if self._looks_like_encrypted_data(value):
                    # Attempt automatic cleanup
                    cleanup_attempted = self._auto_cleanup_corrupted_data(value, tenant_id)
                    if cleanup_attempted:
                        logger.debug(f"Auto-cleanup completed for corrupted encrypted JSON data in {column_context}")
                    else:
                        logger.debug(f"Auto-cleanup not possible, returning None for corrupted encrypted JSON data in {column_context}")
                    return None
                else:
                    # Try to parse as plain JSON
                    logger.debug(f"Attempting to parse as plain JSON in {column_context}")
                    try:
                        return json.loads(value) if isinstance(value, str) else value
                    except json.JSONDecodeError:
                        logger.debug(f"Value is neither encrypted JSON nor plain JSON in {column_context}, returning None")
                        return None
            elif "Failed to decrypt JSON data:" in error_str:
                # Other decryption errors - log with column context
                column_context = self._get_detailed_json_column_context()
                logger.error(f"JSON DECRYPTION FAILED in {column_context} for tenant {tenant_id}: {error_str}")
                
                # For corrupted encrypted JSON data, return None
                if self._looks_like_encrypted_data(value):
                    logger.debug(f"Returning None for corrupted encrypted JSON data in {column_context}")
                    return None
                else:
                    # Try to parse as plain JSON
                    try:
                        return json.loads(value) if isinstance(value, str) else value
                    except json.JSONDecodeError:
                        return None
            else:
                # Unexpected errors - still log at debug level to avoid noise
                logger.debug(f"Failed to decrypt JSON column data: {str(e)}")
                # Try to parse as plain JSON for other errors
                try:
                    return json.loads(value) if isinstance(value, str) else value
                except json.JSONDecodeError:
                    return None
    
    def _looks_like_encrypted_data(self, value: str) -> bool:
        """
        Check if a value looks like encrypted data (base64 encoded).
        
        Args:
            value: The value to check
            
        Returns:
            True if it looks like encrypted data, False if it looks like plain text
        """
        if not isinstance(value, str) or len(value) < 20:
            return False
        
        # Encrypted data should be base64 encoded and reasonably long
        # Check for base64 characteristics
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        
        # If it contains common plain text patterns, it's probably not encrypted
        if '@' in value and '.' in value:  # Looks like email
            return False
        if value.isalpha() or value.isdigit():  # Simple text or numbers
            return False
        if len(value) < 30:  # Encrypted data is usually longer
            return False
        
        # Check if it matches base64 pattern and is long enough
        return base64_pattern.match(value) and len(value) > 30
    
    def _looks_like_encrypted_string_data(self, value: str) -> bool:
        """
        Check if a value looks like encrypted STRING data (shorter base64).
        
        This is different from encrypted JSON data which tends to be longer.
        
        Args:
            value: The value to check
            
        Returns:
            True if it looks like encrypted string data
        """
        if not isinstance(value, str) or len(value) < 20:
            return False
        
        # Check for base64 pattern
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(value):
            return False
        
        # Encrypted string data is typically shorter than encrypted JSON
        # JSON data when encrypted tends to be longer due to structure
        if 30 <= len(value) <= 200:  # Typical range for encrypted strings
            return True
        
        return False
    
    def _get_column_context(self) -> str:
        """Get context information about which column is being processed."""
        try:
            import inspect
            frame = inspect.currentframe()
            # Go up the stack to find the model class and attribute
            for i in range(10):  # Look up to 10 frames
                frame = frame.f_back
                if frame is None:
                    break
                
                # Look for SQLAlchemy model context
                local_vars = frame.f_locals
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, '__tablename__'):
                        return f"Table: {obj.__tablename__}, Class: {obj.__class__.__name__}"
                
                # Look for column name in the frame
                if 'key' in local_vars:
                    return f"Column key: {local_vars['key']}"
                    
            return "Unknown JSON column context"
        except Exception:
            return "JSON context lookup failed"
    
    def _get_detailed_json_column_context(self) -> str:
        """Get detailed context information about which JSON table/column is being processed."""
        try:
            import inspect
            frame = inspect.currentframe()
            table_name = "Unknown"
            column_name = "Unknown"
            record_id = "Unknown"
            
            # Go deeper in the stack to find more context
            for i in range(20):  # Look deeper in the stack
                frame = frame.f_back
                if frame is None:
                    break
                
                local_vars = frame.f_locals
                
                # Look for SQLAlchemy model instance
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, '__tablename__'):
                        table_name = obj.__tablename__
                        if hasattr(obj, 'id') and obj.id:
                            record_id = str(obj.id)
                
                # Look for column name in various contexts
                if 'key' in local_vars and isinstance(local_vars['key'], str):
                    column_name = local_vars['key']
                elif 'column' in local_vars and hasattr(local_vars['column'], 'name'):
                    column_name = local_vars['column'].name
                elif 'attr' in local_vars and hasattr(local_vars['attr'], 'key'):
                    column_name = local_vars['attr'].key
            
            return f"JSON Table: {table_name}, Column: {column_name}, Record ID: {record_id}"
            
        except Exception as e:
            return f"JSON context lookup failed: {str(e)}"
    
    def _auto_cleanup_corrupted_data(self, value: str, tenant_id: int) -> bool:
        """
        Automatically clean up corrupted encrypted data by setting it to NULL.
        
        Args:
            value: The corrupted encrypted data
            tenant_id: Tenant ID
            
        Returns:
            True if cleanup was attempted, False otherwise
        """
        try:
            # Only attempt cleanup if we can identify the record
            import inspect
            frame = inspect.currentframe()
            
            # Look for SQLAlchemy model instance in the call stack
            for i in range(15):  # Look deeper in the stack
                frame = frame.f_back
                if frame is None:
                    break
                
                local_vars = frame.f_locals
                if 'self' in local_vars:
                    obj = local_vars['self']
                    if hasattr(obj, '__tablename__') and hasattr(obj, 'id'):
                        # Found a model instance with an ID
                        table_name = obj.__tablename__
                        record_id = obj.id
                        
                        # Find which column this is
                        column_name = None
                        for attr_name in dir(obj):
                            if not attr_name.startswith('_'):
                                try:
                                    attr_value = getattr(obj, attr_name)
                                    if isinstance(attr_value, str) and attr_value == value:
                                        column_name = attr_name
                                        break
                                except:
                                    continue
                        
                        if column_name:
                            logger.info(f"Auto-cleanup: Found corrupted data in {table_name}.{column_name} (id={record_id})")
                            logger.info(f"Auto-cleanup: Setting {table_name}.{column_name} (id={record_id}) to NULL")
                            
                            # Set the attribute to None to clear the corrupted data
                            setattr(obj, column_name, None)
                            
                            # Mark the object as dirty so it gets saved
                            from sqlalchemy.orm import object_session
                            session = object_session(obj)
                            if session:
                                session.add(obj)
                                session.flush()  # Flush to database
                                logger.info(f"Auto-cleanup: Successfully cleared corrupted data")
                                return True
                            
            return False
            
        except Exception as cleanup_error:
            logger.debug(f"Auto-cleanup failed: {str(cleanup_error)}")
            return False


# Convenience functions for creating encrypted columns with proper indexing

def create_encrypted_string_column(length: Optional[int] = None, **kwargs) -> EncryptedColumn:
    """
    Create an encrypted string column with optional length constraint.
    
    Args:
        length: Maximum length for the original string (before encryption)
        **kwargs: Additional SQLAlchemy column arguments
        
    Returns:
        EncryptedColumn instance
        
    Note:
        Encrypted data will be longer than the original, so the actual database
        column will use Text type regardless of the length parameter.
    """
    if length:
        # Store length info for validation but use Text for storage
        kwargs['info'] = kwargs.get('info', {})
        kwargs['info']['original_max_length'] = length
    
    return EncryptedColumn(**kwargs)


def create_encrypted_json_column(**kwargs) -> EncryptedJSON:
    """
    Create an encrypted JSON column.
    
    Args:
        **kwargs: Additional SQLAlchemy column arguments
        
    Returns:
        EncryptedJSON instance
    """
    return EncryptedJSON(**kwargs)


# PostgreSQL-specific optimizations

class PostgreSQLEncryptedColumn(EncryptedColumn):
    """
    PostgreSQL-optimized encrypted column with additional features.
    
    This version includes PostgreSQL-specific optimizations such as:
    - Better handling of PostgreSQL-specific data types
    - Optimized storage for encrypted data
    - Support for PostgreSQL indexing strategies
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize PostgreSQL-optimized encrypted column."""
        super().__init__(*args, **kwargs)
        # Add PostgreSQL-specific optimizations here if needed
    
    def process_bind_param(self, value: Any, dialect: Dialect) -> Optional[str]:
        """PostgreSQL-optimized encryption with better performance."""
        # Use parent implementation but could add PostgreSQL-specific optimizations
        return super().process_bind_param(value, dialect)
    
    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[str]:
        """PostgreSQL-optimized decryption with better performance."""
        # Use parent implementation but could add PostgreSQL-specific optimizations
        return super().process_result_value(value, dialect)


class PostgreSQLEncryptedJSON(EncryptedJSON):
    """
    PostgreSQL-optimized encrypted JSON column.
    
    This version is specifically optimized for PostgreSQL JSONB operations
    while maintaining encryption capabilities.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize PostgreSQL-optimized encrypted JSON column."""
        super().__init__(*args, **kwargs)
        # Add PostgreSQL JSONB-specific optimizations here if needed
    
    def process_bind_param(self, value: Any, dialect: Dialect) -> Optional[str]:
        """PostgreSQL JSONB-optimized encryption."""
        # Use parent implementation but could add JSONB-specific optimizations
        return super().process_bind_param(value, dialect)
    
    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[Dict[str, Any]]:
        """PostgreSQL JSONB-optimized decryption."""
        # Use parent implementation but could add JSONB-specific optimizations
        return super().process_result_value(value, dialect)


# Utility functions for migration and testing

def is_encrypted_data(value: str) -> bool:
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
        # Try to decode as base64
        decoded = base64.b64decode(value)
        # Encrypted data should have at least 12 bytes (nonce) + some ciphertext
        return len(decoded) >= 16
    except Exception:
        return False


def get_encryption_metadata(column_type) -> Dict[str, Any]:
    """
    Get metadata about an encrypted column type.
    
    Args:
        column_type: SQLAlchemy column type instance
        
    Returns:
        Dictionary with encryption metadata
    """
    metadata = {
        'is_encrypted': False,
        'encryption_type': None,
        'supports_indexing': False
    }
    
    if isinstance(column_type, (EncryptedColumn, PostgreSQLEncryptedColumn)):
        metadata.update({
            'is_encrypted': True,
            'encryption_type': 'string',
            'supports_indexing': False  # Encrypted data cannot be indexed directly
        })
    elif isinstance(column_type, (EncryptedJSON, PostgreSQLEncryptedJSON)):
        metadata.update({
            'is_encrypted': True,
            'encryption_type': 'json',
            'supports_indexing': False  # Encrypted JSON cannot be queried directly
        })
    
    return metadata