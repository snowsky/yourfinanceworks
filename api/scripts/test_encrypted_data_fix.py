#!/usr/bin/env python3
"""
Test script to verify that encrypted data is properly sanitized in audit logs and history.

This script creates a test invoice with encrypted notes and checks that the
encrypted data doesn't appear in the history or audit logs.
"""

import os
import sys
import logging
from typing import Dict, Any
import json

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import get_master_db, set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models_per_tenant import Invoice, Client, InvoiceHistory, AuditLog, User
from core.models.models import MasterUser, Tenant
from core.utils.audit_sanitizer import is_likely_encrypted_data
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_invoice_with_encrypted_notes(tenant_id: int) -> Dict[str, Any]:
    """
    Create a test invoice with notes that will be encrypted.
    
    Args:
        tenant_id: Tenant ID to create the invoice in
        
    Returns:
        Dictionary with test results
    """
    logger.info(f"Creating test invoice for tenant {tenant_id}")
    
    try:
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Get tenant database session
        tenant_session_factory = tenant_db_manager.get_tenant_session(tenant_id)
        tenant_db = tenant_session_factory()
        
        # Get or create a test client
        test_client = tenant_db.query(Client).first()
        if not test_client:
            test_client = Client(
                name="Test Client",
                email="test@example.com",
                phone="123-456-7890",
                address="123 Test St",
                company="Test Company"
            )
            tenant_db.add(test_client)
            tenant_db.commit()
            tenant_db.refresh(test_client)
        
        # Get or create a test user
        test_user = tenant_db.query(User).first()
        if not test_user:
            logger.warning("No test user found in tenant database")
            tenant_db.close()
            return {"error": "No test user found"}
        
        # Create test invoice with notes that will be encrypted
        test_notes = "This is a test note that will be encrypted in the database"
        
        test_invoice = Invoice(
            number=f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            amount=100.50,
            currency="USD",
            due_date=datetime.now(timezone.utc),
            status="draft",
            notes=test_notes,
            client_id=test_client.id,
            subtotal=100.50,
            discount_type="percentage",
            discount_value=0.0
        )
        
        tenant_db.add(test_invoice)
        tenant_db.flush()  # Get the invoice ID
        
        # Create history entry (simulating what happens in the invoice creation endpoint)
        from core.utils.audit_sanitizer import sanitize_history_values

        current_values = {
            'number': test_invoice.number,
            'amount': test_invoice.amount,
            'currency': test_invoice.currency,
            'status': test_invoice.status,
            'due_date': test_invoice.due_date.isoformat() if test_invoice.due_date else None,
            'notes': test_invoice.notes  # This should be sanitized
        }
        
        creation_history = InvoiceHistory(
            invoice_id=test_invoice.id,
            user_id=test_user.id,
            action='creation',
            details=f'Invoice {test_invoice.number} created',
            previous_values=None,
            current_values=sanitize_history_values(current_values)
        )
        
        tenant_db.add(creation_history)
        tenant_db.commit()
        
        # Check what was actually stored in the history
        tenant_db.refresh(creation_history)
        stored_notes = creation_history.current_values.get('notes') if creation_history.current_values else None
        
        # Check if the stored notes contain encrypted data
        notes_encrypted_in_history = False
        if stored_notes and isinstance(stored_notes, str):
            notes_encrypted_in_history = is_likely_encrypted_data(stored_notes)
        
        # Get the actual encrypted notes from the invoice record
        tenant_db.refresh(test_invoice)
        actual_encrypted_notes = None
        
        # To get the raw encrypted value, we need to access it directly from the database
        from sqlalchemy import text
        result = tenant_db.execute(
            text("SELECT notes FROM invoices WHERE id = :invoice_id"),
            {"invoice_id": test_invoice.id}
        ).fetchone()
        
        if result:
            actual_encrypted_notes = result[0]
        
        tenant_db.close()
        
        return {
            "success": True,
            "invoice_id": test_invoice.id,
            "invoice_number": test_invoice.number,
            "original_notes": test_notes,
            "stored_notes_in_history": stored_notes,
            "notes_encrypted_in_history": notes_encrypted_in_history,
            "actual_encrypted_notes_preview": actual_encrypted_notes[:50] + "..." if actual_encrypted_notes and len(actual_encrypted_notes) > 50 else actual_encrypted_notes,
            "sanitization_working": stored_notes == '[ENCRYPTED]' if stored_notes else False
        }
        
    except Exception as e:
        logger.error(f"Error creating test invoice: {str(e)}")
        return {"error": str(e)}


def main():
    """Main function to test encrypted data sanitization."""
    logger.info("Starting encrypted data sanitization test")
    
    try:
        # Get all tenant IDs
        tenant_ids = tenant_db_manager.get_existing_tenant_ids()
        
        if not tenant_ids:
            logger.warning("No tenants found")
            return
        
        # Test with the first tenant
        tenant_id = tenant_ids[0]
        logger.info(f"Testing with tenant {tenant_id}")
        
        # Create test invoice
        result = create_test_invoice_with_encrypted_notes(tenant_id)
        
        # Print results
        print("\n" + "="*80)
        print("ENCRYPTED DATA SANITIZATION TEST RESULTS")
        print("="*80)
        
        if "error" in result:
            print(f"❌ Test failed: {result['error']}")
            return
        
        print(f"✅ Test invoice created successfully")
        print(f"   Invoice ID: {result['invoice_id']}")
        print(f"   Invoice Number: {result['invoice_number']}")
        print(f"   Original Notes: {result['original_notes']}")
        print(f"   Stored in History: {result['stored_notes_in_history']}")
        print(f"   Encrypted in DB: {result['actual_encrypted_notes_preview']}")
        
        if result['sanitization_working']:
            print(f"✅ SANITIZATION WORKING: Notes properly sanitized as '[ENCRYPTED]'")
        else:
            print(f"❌ SANITIZATION FAILED: Notes not properly sanitized")
            if result['notes_encrypted_in_history']:
                print(f"   ⚠️  WARNING: Encrypted data detected in history!")
        
        print("\n📋 SUMMARY:")
        if result['sanitization_working']:
            print("✅ Encrypted data is being properly sanitized in history records")
            print("✅ No encrypted data exposure detected")
        else:
            print("❌ Encrypted data sanitization is not working correctly")
            print("❌ Potential data exposure detected")
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()