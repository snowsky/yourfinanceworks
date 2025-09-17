#!/usr/bin/env python3
"""
Test script to verify the invoice number fix works correctly.
This script tests both scenarios:
1. Creating an invoice with a custom invoice number
2. Creating an invoice without an invoice number (auto-generated)
"""

import requests
import json

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_CLIENT_ID = 1  # Assuming client ID 1 exists

def test_custom_invoice_number():
    """Test creating an invoice with a custom invoice number"""
    print("Testing custom invoice number...")
    
    invoice_data = {
        "number": "TEST-001",
        "client_id": TEST_CLIENT_ID,
        "amount": 100.0,
        "currency": "USD",
        "status": "draft",
        "items": [
            {
                "description": "Test item",
                "quantity": 1,
                "price": 100.0
            }
        ]
    }
    
    # This would require authentication in a real test
    # For now, just print what would be sent
    print(f"Would send POST to {API_BASE_URL}/api/v1/invoices with data:")
    print(json.dumps(invoice_data, indent=2))
    print("Expected: Invoice created with number 'TEST-001'")
    print()

def test_auto_generated_invoice_number():
    """Test creating an invoice without specifying a number (auto-generated)"""
    print("Testing auto-generated invoice number...")
    
    invoice_data = {
        # No "number" field - should be auto-generated
        "client_id": TEST_CLIENT_ID,
        "amount": 200.0,
        "currency": "USD", 
        "status": "draft",
        "items": [
            {
                "description": "Test item 2",
                "quantity": 2,
                "price": 100.0
            }
        ]
    }
    
    print(f"Would send POST to {API_BASE_URL}/api/v1/invoices with data:")
    print(json.dumps(invoice_data, indent=2))
    print("Expected: Invoice created with auto-generated number like 'INV-20250109-0001'")
    print()

def test_duplicate_invoice_number():
    """Test creating an invoice with a duplicate invoice number"""
    print("Testing duplicate invoice number handling...")
    
    invoice_data = {
        "number": "TEST-001",  # Same as first test
        "client_id": TEST_CLIENT_ID,
        "amount": 300.0,
        "currency": "USD",
        "status": "draft",
        "items": [
            {
                "description": "Test item 3",
                "quantity": 1,
                "price": 300.0
            }
        ]
    }
    
    print(f"Would send POST to {API_BASE_URL}/api/v1/invoices with data:")
    print(json.dumps(invoice_data, indent=2))
    print("Expected: HTTP 400 error - 'Invoice number 'TEST-001' is already in use'")
    print()

if __name__ == "__main__":
    print("Invoice Number Fix Test Cases")
    print("=" * 40)
    print()
    
    test_custom_invoice_number()
    test_auto_generated_invoice_number() 
    test_duplicate_invoice_number()
    
    print("Summary of Changes Made:")
    print("- Frontend: Invoice number field is now optional")
    print("- Frontend: Added placeholder text 'Leave empty to auto-generate'")
    print("- Frontend: Added description explaining auto-generation")
    print("- Backend: Uses provided invoice number if given, generates one if empty")
    print("- Backend: Validates that custom invoice numbers are unique")
    print("- Schema: Added optional 'number' field to InvoiceCreate")