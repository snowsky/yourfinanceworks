#!/usr/bin/env python3
"""
Test script to verify that invoice update with encrypted data sanitization works.
"""

import os
import sys
import logging
from typing import Dict, Any

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models_per_tenant import Invoice, Client, InvoiceHistory, User
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_invoice_update_sanitization(tenant_id: int) -> Dict[str, Any]:
    """
    Test that invoice updates properly sanitize encrypted data in history.
    
    Args:
        tenant_id: Tenant ID to test with
        
    Returns:
        Dictionary with test results
    """
    logger.info(f"Testing invoice update sanitization for tenant {tenant_id}")
    
    try:
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Get tenant database session
        tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session_factory()
        
        # Get an existing invoice or create one
        test_invoice = tenant_db.query(Invoice).first()
        if not test_invoice:
            logger.warning("No test invoice found")
            tenant_db.close()
            return {"error": "No test invoice found"}
        
        # Get a test user
        test_user = tenant_db.query(User).first()
        if not test_user:
            logger.warning("No test user found")
            tenant_db.close()
            return {"error": "No test user found"}
        
        # Update the invoice notes (this will trigger the sanitization)
        original_notes = test_invoice.notes
        new_notes = f"Updated test note at {datetime.now().isoformat()}"
        
        # Simulate the update process that happens in the router
        from core.utils.audit_sanitizer import sanitize_history_values
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

        # Store old values
        old_notes = test_invoice.notes
        
        # Update the invoice
        test_invoice.notes = new_notes
        test_invoice.updated_at = datetime.now(timezone.utc)
        
        # Create history entry (simulating what happens in the update endpoint)
        changes = ["Notes updated"]
        
        previous_values = {
            'notes': old_notes,  # This should be sanitized
            'amount': test_invoice.amount,
        }
        
        current_values = {
            'notes': test_invoice.notes,  # This should be sanitized
            'amount': test_invoice.amount,
        }
        
        history_entry = InvoiceHistoryModel(
            invoice_id=test_invoice.id,
            user_id=test_user.id,
            action='update',
            details='; '.join(changes),
            previous_values=sanitize_history_values(previous_values),
            current_values=sanitize_history_values(current_values)
        )
        
        tenant_db.add(history_entry)
        tenant_db.commit()
        
        # Check what was stored in the history
        tenant_db.refresh(history_entry)
        stored_previous_notes = history_entry.previous_values.get('notes') if history_entry.previous_values else None
        stored_current_notes = history_entry.current_values.get('notes') if history_entry.current_values else None
        
        # Store values before closing session
        invoice_id = test_invoice.id
        
        tenant_db.close()
        
        return {
            "success": True,
            "invoice_id": invoice_id,
            "original_notes": original_notes,
            "new_notes": new_notes,
            "stored_previous_notes": stored_previous_notes,
            "stored_current_notes": stored_current_notes,
            "sanitization_working": (
                stored_previous_notes == '[ENCRYPTED]' and 
                stored_current_notes == '[ENCRYPTED]'
            )
        }
        
    except Exception as e:
        logger.error(f"Error testing invoice update: {str(e)}")
        return {"error": str(e)}


def main():
    """Main function to test invoice update sanitization."""
    logger.info("Starting invoice update sanitization test")
    
    try:
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        
        if not tenant_ids:
            logger.warning("No tenants found")
            return
        
        # Test with the first tenant
        tenant_id = tenant_ids[0]
        logger.info(f"Testing with tenant {tenant_id}")
        
        # Test invoice update
        result = test_invoice_update_sanitization(tenant_id)
        
        # Print results
        print("\n" + "="*80)
        print("INVOICE UPDATE SANITIZATION TEST RESULTS")
        print("="*80)
        
        if "error" in result:
            print(f"❌ Test failed: {result['error']}")
            return
        
        print(f"✅ Test invoice update completed successfully")
        print(f"   Invoice ID: {result['invoice_id']}")
        print(f"   Original Notes: {result['original_notes']}")
        print(f"   New Notes: {result['new_notes']}")
        print(f"   Stored Previous Notes: {result['stored_previous_notes']}")
        print(f"   Stored Current Notes: {result['stored_current_notes']}")
        
        if result['sanitization_working']:
            print(f"✅ SANITIZATION WORKING: Notes properly sanitized in update history")
        else:
            print(f"❌ SANITIZATION FAILED: Notes not properly sanitized in update history")
        
        print("\n📋 SUMMARY:")
        if result['sanitization_working']:
            print("✅ Invoice update encrypted data sanitization is working correctly")
            print("✅ No encrypted data exposure in update history")
        else:
            print("❌ Invoice update sanitization is not working correctly")
            print("❌ Potential encrypted data exposure detected")
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()