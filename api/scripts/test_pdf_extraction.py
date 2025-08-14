#!/usr/bin/env python3
"""
Script to test PDF text extraction for bank statements.
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bank_statement_service import SimplePDFLoader

def test_pdf_extraction(pdf_path: str):
    """Test PDF text extraction."""
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    print(f"Testing PDF extraction for: {pdf_path}")
    print("=" * 60)
    
    try:
        loader = SimplePDFLoader()
        pages = loader.load(pdf_path)
        
        print(f"Number of pages extracted: {len(pages)}")
        print("=" * 60)
        
        for i, page_text in enumerate(pages):
            print(f"PAGE {i + 1}:")
            print("-" * 40)
            print(f"Length: {len(page_text)} characters")
            print("First 500 characters:")
            print(repr(page_text[:500]))
            print("\nFirst 500 characters (readable):")
            print(page_text[:500])
            print("-" * 40)
            print()
            
        # Test combined text
        combined_text = "\n\n".join([p or "" for p in pages])
        print(f"COMBINED TEXT LENGTH: {len(combined_text)} characters")
        print("First 1000 characters of combined text:")
        print(combined_text[:1000])
        
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Find the bank statement file
    attachments_dir = Path("attachments")
    bank_statement_files = []
    
    for tenant_dir in attachments_dir.glob("tenant_*"):
        bank_dir = tenant_dir / "bank_statements"
        if bank_dir.exists():
            for pdf_file in bank_dir.glob("*.pdf"):
                bank_statement_files.append(str(pdf_file))
    
    if not bank_statement_files:
        print("No bank statement PDF files found in attachments directory")
        sys.exit(1)
    
    print(f"Found {len(bank_statement_files)} bank statement files:")
    for i, file_path in enumerate(bank_statement_files):
        print(f"  {i + 1}. {file_path}")
    
    # Test the most recent one
    latest_file = max(bank_statement_files, key=os.path.getmtime)
    print(f"\nTesting latest file: {latest_file}")
    test_pdf_extraction(latest_file)