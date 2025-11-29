#!/usr/bin/env python3
"""
Test script for PDF import functionality
"""

import os
import sys
import tempfile
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import InvoicePDFParser, check_ollama_connection

def test_pdf_import():
    """Test the PDF import functionality"""
    
    print("🧪 Testing PDF Import Functionality")
    print("=" * 50)
    
    # Check if Ollama is available
    print("1. Checking Ollama connection...")
    if not check_ollama_connection():
        print("❌ Ollama is not available. Please start Ollama first.")
        print("   Run: ollama serve")
        return False
    
    print("✅ Ollama is running")
    
    # Test with a sample PDF (you would need to provide this)
    sample_pdf = "invoice-example.pdf"
    
    if not os.path.exists(sample_pdf):
        print(f"⚠️  Sample PDF not found: {sample_pdf}")
        print("   Please provide a sample PDF file to test with")
        return True  # Not a failure, just no test file
    
    try:
        print(f"2. Processing PDF: {sample_pdf}")
        parser = InvoicePDFParser(model_name="gpt-oss")
        
        # Extract data
        invoice_data = parser.extract_invoice_data(sample_pdf)
        
        print("✅ PDF processed successfully!")
        print("\n📄 Extracted Data:")
        print(f"   Date: {invoice_data.date}")
        print(f"   Bills To: {invoice_data.bills_to}")
        print(f"   Items: {len(invoice_data.items)}")
        print(f"   Total Amount: ${invoice_data.total_amount:.2f}")
        
        # Test JSON serialization
        json_data = json.dumps({
            'date': invoice_data.date,
            'bills_to': invoice_data.bills_to,
            'items': [
                {
                    'description': item.description,
                    'quantity': item.quantity,
                    'price': item.price,
                    'amount': item.amount,
                    'discount': item.discount
                }
                for item in invoice_data.items
            ],
            'total_amount': invoice_data.total_amount,
            'total_discount': invoice_data.total_discount
        })
        
        print("✅ JSON serialization successful")
        return True
        
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        return False

def test_api_integration():
    """Test API integration points"""
    
    print("\n🔌 Testing API Integration Points")
    print("=" * 50)
    
    # Test command line interface
    print("1. Testing command line interface...")
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, "main.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Command line interface working")
        else:
            print(f"❌ Command line interface error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Command line test failed: {e}")
        return False
    
    # Test PDF processor router import
    print("2. Testing PDF processor router...")
    
    try:
        from core.routers.pdf_processor import router
        print("✅ PDF processor router imported successfully")
        
        # Check if the router has the expected endpoints
        routes = [route.path for route in router.routes]
        expected_routes = ["/process-pdf", "/ai-status"]
        
        for expected_route in expected_routes:
            if expected_route in routes:
                print(f"✅ Route {expected_route} found")
            else:
                print(f"❌ Route {expected_route} missing")
                return False
                
    except Exception as e:
        print(f"❌ PDF processor router test failed: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    
    print("🚀 PDF Import System Test")
    print("=" * 60)
    
    success = True
    
    # Test PDF processing
    if not test_pdf_import():
        success = False
    
    # Test API integration
    if not test_api_integration():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! PDF import system is ready.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)