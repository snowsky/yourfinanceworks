#!/usr/bin/env python3
"""
Production script to fix encrypted data display issues.
This script should be run after deploying the code fixes to clean up any existing corrupted data.
"""

import sys
import os
import logging
from datetime import datetime, timezone

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_encrypted_data_display():
    """Fix encrypted data display issues in production."""
    logger.info("Starting encrypted data display fix...")
    
    try:
        from core.services.encryption_service import get_encryption_service
        from core.services.key_management_service import get_key_management_service
        from core.models.database import set_tenant_context
        from core.models.models_per_tenant import Expense
        from core.services.tenant_database_manager import tenant_db_manager
        
        # Get services
        encryption = get_encryption_service()
        key_mgmt = get_key_management_service()
        
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        logger.info(f"Found {len(tenant_ids)} tenants to process")
        
        total_fixed = 0
        
        for tenant_id in tenant_ids:
            logger.info(f"Processing tenant {tenant_id}...")
            
            try:
                # Set tenant context
                set_tenant_context(tenant_id)
                
                # Get tenant session
                SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
                db = SessionLocalTenant()
                
                try:
                    # Ensure tenant has encryption key
                    try:
                        key_mgmt.retrieve_tenant_key(tenant_id)
                    except Exception:
                        logger.info(f"Generating encryption key for tenant {tenant_id}")
                        key_mgmt.generate_tenant_key(tenant_id)
                    
                    # Clear encryption cache
                    encryption.clear_cache(tenant_id)
                    
                    # Get all expenses
                    expenses = db.query(Expense).all()
                    logger.info(f"Processing {len(expenses)} expenses for tenant {tenant_id}")
                    
                    tenant_fixed = 0
                    
                    for expense in expenses:
                        expense_updated = False
                        
                        # Check and fix vendor field
                        if expense.vendor and _looks_like_corrupted_encrypted_data(expense.vendor):
                            logger.warning(f"Fixing corrupted vendor data for expense {expense.id}")
                            expense.vendor = "Unknown Vendor"
                            expense_updated = True
                        
                        # Check and fix notes field
                        if expense.notes and _looks_like_corrupted_encrypted_data(expense.notes):
                            logger.warning(f"Fixing corrupted notes data for expense {expense.id}")
                            expense.notes = None
                            expense_updated = True
                        
                        # Check and fix category field
                        if expense.category and _looks_like_corrupted_encrypted_data(expense.category):
                            logger.warning(f"Fixing corrupted category data for expense {expense.id}")
                            expense.category = "General"
                            expense_updated = True
                        
                        # Check and fix analysis_result field
                        if (expense.analysis_result and 
                            isinstance(expense.analysis_result, str) and 
                            _looks_like_corrupted_encrypted_data(expense.analysis_result)):
                            logger.warning(f"Fixing corrupted analysis_result for expense {expense.id}")
                            expense.analysis_result = {
                                "error": "Previous analysis data was corrupted and has been reset",
                                "fixed_at": datetime.now(timezone.utc).isoformat()
                            }
                            expense_updated = True
                        
                        if expense_updated:
                            expense.updated_at = datetime.now(timezone.utc)
                            tenant_fixed += 1
                    
                    if tenant_fixed > 0:
                        db.commit()
                        logger.info(f"Fixed {tenant_fixed} expenses for tenant {tenant_id}")
                        total_fixed += tenant_fixed
                    else:
                        logger.info(f"No corrupted data found for tenant {tenant_id}")
                
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error processing tenant {tenant_id}: {str(e)}")
                continue
        
        logger.info(f"Completed fix: {total_fixed} expenses fixed across {len(tenant_ids)} tenants")
        return True
        
    except Exception as e:
        logger.error(f"Fix script failed: {str(e)}")
        return False


def _looks_like_corrupted_encrypted_data(value: str) -> bool:
    """Check if a value looks like corrupted encrypted data."""
    if not isinstance(value, str) or len(value) < 20:
        return False
    
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/=]+$')
    
    # Check if it looks like base64 encoded data that's too long for normal text
    return (
        base64_pattern.match(value) and 
        len(value) > 40 and  # Longer than normal text
        len(value) < 2000 and  # But not too long
        '=' in value[-4:]  # Has base64 padding
    )


def verify_fix():
    """Verify that the fix worked correctly."""
    logger.info("Verifying fix...")
    
    try:
        from core.models.database import set_tenant_context
        from core.models.models_per_tenant import Expense
        from core.services.tenant_database_manager import tenant_db_manager
        
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        corrupted_found = 0
        
        for tenant_id in tenant_ids:
            set_tenant_context(tenant_id)
            SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
            db = SessionLocalTenant()
            
            try:
                expenses = db.query(Expense).all()
                
                for expense in expenses:
                    if (expense.vendor and _looks_like_corrupted_encrypted_data(expense.vendor)):
                        corrupted_found += 1
                        logger.warning(f"Still found corrupted vendor in expense {expense.id}")
                    
                    if (expense.notes and _looks_like_corrupted_encrypted_data(expense.notes)):
                        corrupted_found += 1
                        logger.warning(f"Still found corrupted notes in expense {expense.id}")
            
            finally:
                db.close()
        
        if corrupted_found == 0:
            logger.info("✅ Verification passed: No corrupted encrypted data found")
            return True
        else:
            logger.warning(f"⚠️ Verification found {corrupted_found} remaining corrupted fields")
            return False
            
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        return False


if __name__ == "__main__":
    logger.info("🚀 Starting encrypted data display fix script")
    
    success = fix_encrypted_data_display()
    
    if success:
        logger.info("✅ Fix completed successfully")
        
        # Verify the fix
        if verify_fix():
            logger.info("🎉 All encrypted data display issues have been resolved!")
            sys.exit(0)
        else:
            logger.warning("⚠️ Some issues may remain, manual review recommended")
            sys.exit(1)
    else:
        logger.error("❌ Fix script failed")
        sys.exit(1)