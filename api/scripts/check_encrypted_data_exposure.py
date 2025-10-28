#!/usr/bin/env python3
"""
Script to check for encrypted data exposure in history and audit tables.

This script scans the database for encrypted data that may have been
inadvertently stored in non-encrypted fields like history tables.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Tuple
import json

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from models.database import get_master_db
from services.tenant_database_manager import tenant_db_manager
from models.models_per_tenant import InvoiceHistory, AuditLog
from utils.audit_sanitizer import is_likely_encrypted_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_json_field_for_encrypted_data(field_value: Any, field_path: str = "") -> List[str]:
    """
    Recursively check a JSON field for encrypted data.
    
    Args:
        field_value: The JSON field value to check
        field_path: Path to this field (for reporting)
        
    Returns:
        List of paths where encrypted data was found
    """
    issues = []
    
    if isinstance(field_value, dict):
        for key, value in field_value.items():
            current_path = f"{field_path}.{key}" if field_path else key
            if isinstance(value, str) and is_likely_encrypted_data(value):
                issues.append(f"{current_path}: {value[:50]}...")
            elif isinstance(value, (dict, list)):
                issues.extend(check_json_field_for_encrypted_data(value, current_path))
    
    elif isinstance(field_value, list):
        for i, item in enumerate(field_value):
            current_path = f"{field_path}[{i}]" if field_path else f"[{i}]"
            if isinstance(item, str) and is_likely_encrypted_data(item):
                issues.append(f"{current_path}: {item[:50]}...")
            elif isinstance(item, (dict, list)):
                issues.extend(check_json_field_for_encrypted_data(item, current_path))
    
    elif isinstance(field_value, str) and is_likely_encrypted_data(field_value):
        issues.append(f"{field_path}: {field_value[:50]}...")
    
    return issues


def check_invoice_history(db: Session, tenant_id: str) -> Tuple[int, List[str]]:
    """
    Check InvoiceHistory table for encrypted data exposure.
    
    Args:
        db: Database session
        tenant_id: Tenant identifier
        
    Returns:
        Tuple of (total_records, list_of_issues)
    """
    logger.info(f"Checking InvoiceHistory for tenant {tenant_id}")
    
    history_records = db.query(InvoiceHistory).all()
    issues = []
    
    for record in history_records:
        record_issues = []
        
        # Check previous_values
        if record.previous_values:
            prev_issues = check_json_field_for_encrypted_data(
                record.previous_values, "previous_values"
            )
            record_issues.extend(prev_issues)
        
        # Check current_values
        if record.current_values:
            curr_issues = check_json_field_for_encrypted_data(
                record.current_values, "current_values"
            )
            record_issues.extend(curr_issues)
        
        if record_issues:
            issues.append(f"InvoiceHistory ID {record.id} (Invoice {record.invoice_id}):")
            for issue in record_issues:
                issues.append(f"  - {issue}")
    
    return len(history_records), issues


def check_audit_logs(db: Session, tenant_id: str) -> Tuple[int, List[str]]:
    """
    Check AuditLog table for encrypted data exposure.
    
    Args:
        db: Database session
        tenant_id: Tenant identifier
        
    Returns:
        Tuple of (total_records, list_of_issues)
    """
    logger.info(f"Checking AuditLog for tenant {tenant_id}")
    
    # Focus on audit logs that might contain sensitive data
    audit_records = db.query(AuditLog).filter(
        AuditLog.resource_type.in_(['invoice', 'client', 'expense', 'payment'])
    ).all()
    
    issues = []
    
    for record in audit_records:
        record_issues = []
        
        # Check details field
        if record.details:
            detail_issues = check_json_field_for_encrypted_data(
                record.details, "details"
            )
            record_issues.extend(detail_issues)
        
        if record_issues:
            issues.append(f"AuditLog ID {record.id} ({record.action} on {record.resource_type}):")
            for issue in record_issues:
                issues.append(f"  - {issue}")
    
    return len(audit_records), issues


def generate_report(results: Dict[str, Dict[str, Any]]) -> None:
    """Generate a summary report of the findings."""
    
    print("\n" + "="*80)
    print("ENCRYPTED DATA EXPOSURE REPORT")
    print("="*80)
    
    total_tenants = len(results)
    tenants_with_issues = sum(1 for r in results.values() if r['invoice_history_issues'] or r['audit_log_issues'])
    
    print(f"\nSUMMARY:")
    print(f"- Total tenants checked: {total_tenants}")
    print(f"- Tenants with encrypted data exposure: {tenants_with_issues}")
    
    if tenants_with_issues == 0:
        print("\n✅ No encrypted data exposure found!")
        return
    
    print(f"\nDETAILS:")
    
    for tenant_id, result in results.items():
        if result['invoice_history_issues'] or result['audit_log_issues']:
            print(f"\n🔴 TENANT {tenant_id}:")
            
            if result['invoice_history_issues']:
                print(f"  InvoiceHistory issues ({len(result['invoice_history_issues'])} records affected):")
                for issue in result['invoice_history_issues'][:5]:  # Show first 5
                    print(f"    {issue}")
                if len(result['invoice_history_issues']) > 5:
                    print(f"    ... and {len(result['invoice_history_issues']) - 5} more")
            
            if result['audit_log_issues']:
                print(f"  AuditLog issues ({len(result['audit_log_issues'])} records affected):")
                for issue in result['audit_log_issues'][:5]:  # Show first 5
                    print(f"    {issue}")
                if len(result['audit_log_issues']) > 5:
                    print(f"    ... and {len(result['audit_log_issues']) - 5} more")
    
    print(f"\n📋 RECOMMENDATIONS:")
    print(f"1. Run the cleanup script: python api/scripts/cleanup_encrypted_history_data.py")
    print(f"2. Review audit logging code to ensure proper sanitization")
    print(f"3. Consider implementing automated checks in CI/CD pipeline")


def main():
    """Main function to check for encrypted data exposure."""
    logger.info("Starting encrypted data exposure check")
    
    try:
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        
        results = {}
        
        for tenant_id in tenant_ids:
            logger.info(f"Checking tenant {tenant_id}")
            
            try:
                # Get tenant database session
                tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
                tenant_db = tenant_session_factory()
                
                # Check InvoiceHistory
                ih_total, ih_issues = check_invoice_history(tenant_db, tenant_id)
                
                # Check AuditLog
                al_total, al_issues = check_audit_logs(tenant_db, tenant_id)
                
                tenant_db.close()
                
                results[tenant_id] = {
                    'invoice_history_total': ih_total,
                    'invoice_history_issues': ih_issues,
                    'audit_log_total': al_total,
                    'audit_log_issues': al_issues
                }
                
                if ih_issues or al_issues:
                    logger.warning(f"Found encrypted data exposure in tenant {tenant_id}")
                else:
                    logger.info(f"No issues found in tenant {tenant_id}")
                
            except Exception as e:
                logger.error(f"Error checking tenant {tenant_id}: {str(e)}")
                results[tenant_id] = {
                    'error': str(e)
                }
        
        # Generate report
        generate_report(results)
        
    except Exception as e:
        logger.error(f"Error during check: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()