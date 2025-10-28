#!/usr/bin/env python3
"""
Script to clean up encrypted data that may have been stored in history tables.

This script identifies and sanitizes encrypted data in InvoiceHistory and other
history tables to prevent exposure of sensitive information in logs and UI.
"""

import os
import sys
import logging
from typing import Dict, Any, List
import json

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from models.database import get_master_db
from services.tenant_database_manager import tenant_db_manager
from models.models_per_tenant import InvoiceHistory, AuditLog
from utils.audit_sanitizer import is_likely_encrypted_data, sanitize_history_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_encrypted_json_field(value: Any) -> bool:
    """Check if a JSON field contains encrypted data."""
    if not isinstance(value, dict):
        return False
    
    # Check if any string values in the dict look like encrypted data
    for v in value.values():
        if isinstance(v, str) and is_likely_encrypted_data(v):
            return True
    
    return False


def sanitize_json_field(value: Any) -> Any:
    """Sanitize a JSON field that may contain encrypted data."""
    if not isinstance(value, dict):
        return value
    
    sanitized = {}
    for k, v in value.items():
        if isinstance(v, str) and is_likely_encrypted_data(v):
            sanitized[k] = '[ENCRYPTED]'
        elif isinstance(v, dict):
            sanitized[k] = sanitize_json_field(v)
        else:
            sanitized[k] = v
    
    return sanitized


def cleanup_invoice_history(db: Session, tenant_id: str) -> int:
    """
    Clean up encrypted data in InvoiceHistory table.
    
    Args:
        db: Database session
        tenant_id: Tenant identifier for logging
        
    Returns:
        Number of records updated
    """
    logger.info(f"Cleaning up InvoiceHistory for tenant {tenant_id}")
    
    # Get all invoice history records
    history_records = db.query(InvoiceHistory).all()
    updated_count = 0
    
    for record in history_records:
        updated = False
        
        # Check and sanitize previous_values
        if record.previous_values:
            original_previous = record.previous_values.copy()
            sanitized_previous = sanitize_history_values(record.previous_values)
            if sanitized_previous != original_previous:
                record.previous_values = sanitized_previous
                updated = True
                logger.debug(f"Sanitized previous_values for InvoiceHistory ID {record.id}")
        
        # Check and sanitize current_values
        if record.current_values:
            original_current = record.current_values.copy()
            sanitized_current = sanitize_history_values(record.current_values)
            if sanitized_current != original_current:
                record.current_values = sanitized_current
                updated = True
                logger.debug(f"Sanitized current_values for InvoiceHistory ID {record.id}")
        
        if updated:
            updated_count += 1
    
    if updated_count > 0:
        db.commit()
        logger.info(f"Updated {updated_count} InvoiceHistory records for tenant {tenant_id}")
    else:
        logger.info(f"No InvoiceHistory records needed updating for tenant {tenant_id}")
    
    return updated_count


def cleanup_audit_logs(db: Session, tenant_id: str) -> int:
    """
    Clean up encrypted data in AuditLog table.
    
    Args:
        db: Database session
        tenant_id: Tenant identifier for logging
        
    Returns:
        Number of records updated
    """
    logger.info(f"Cleaning up AuditLog for tenant {tenant_id}")
    
    # Get audit log records that might contain encrypted data
    audit_records = db.query(AuditLog).filter(
        AuditLog.resource_type.in_(['invoice', 'client', 'expense', 'payment'])
    ).all()
    
    updated_count = 0
    
    for record in audit_records:
        updated = False
        
        # Check and sanitize details field
        if record.details and isinstance(record.details, dict):
            original_details = record.details.copy()
            
            # Check for encrypted data in the details
            for key, value in record.details.items():
                if isinstance(value, str) and is_likely_encrypted_data(value):
                    record.details[key] = '[ENCRYPTED]'
                    updated = True
                elif isinstance(value, dict) and is_encrypted_json_field(value):
                    record.details[key] = sanitize_json_field(value)
                    updated = True
            
            if updated:
                logger.debug(f"Sanitized details for AuditLog ID {record.id}")
        
        if updated:
            updated_count += 1
    
    if updated_count > 0:
        db.commit()
        logger.info(f"Updated {updated_count} AuditLog records for tenant {tenant_id}")
    else:
        logger.info(f"No AuditLog records needed updating for tenant {tenant_id}")
    
    return updated_count


def main():
    """Main function to clean up encrypted data across all tenants."""
    logger.info("Starting encrypted data cleanup in history tables")
    
    try:
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        
        total_invoice_history_updated = 0
        total_audit_logs_updated = 0
        
        for tenant_id in tenant_ids:
            logger.info(f"Processing tenant {tenant_id}")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
                tenant_db = tenant_session_factory()
                
                # Clean up InvoiceHistory
                invoice_history_count = cleanup_invoice_history(tenant_db, tenant_id)
                total_invoice_history_updated += invoice_history_count
                
                # Clean up AuditLog
                audit_log_count = cleanup_audit_logs(tenant_db, tenant_id)
                total_audit_logs_updated += audit_log_count
                
                tenant_db.close()
                
            except Exception as e:
                logger.error(f"Error processing tenant {tenant_id}: {str(e)}")
                continue
        
        logger.info("Cleanup completed successfully")
        logger.info(f"Total InvoiceHistory records updated: {total_invoice_history_updated}")
        logger.info(f"Total AuditLog records updated: {total_audit_logs_updated}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()