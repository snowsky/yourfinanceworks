#!/usr/bin/env python3
"""
Script to test the improved bank statement extraction.
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bank_statement_service import process_bank_pdf_with_llm, _regex_extract_transactions, SimplePDFLoader

def test_bank_extraction(pdf_path: str):
    """Test bank statement extraction."""
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    print(f"Testing bank statement extraction for: {pdf_path}")
    print("=" * 60)
    
    try:
        # First test raw text extraction
        loader = SimplePDFLoader()
        pages = loader.load(pdf_path)
        combined_text = "\n\n".join([p or "" for p in pages])
        
        print(f"Raw text length: {len(combined_text)} characters")
        print("Raw text sample:")
        print(combined_text[:1000])
        print("\n" + "=" * 60)
        
        # Test regex extraction directly
        print("Testing regex extraction...")
        regex_results = _regex_extract_transactions(combined_text)
        print(f"Regex extracted {len(regex_results)} transactions:")
        for i, txn in enumerate(regex_results):
            print(f"  {i+1}. {txn}")
        print("\n" + "=" * 60)
        
        # Test full LLM processing
        print("Testing full LLM processing...")
        llm_results = process_bank_pdf_with_llm(pdf_path)
        print(f"LLM extracted {len(llm_results)} transactions:")
        for i, txn in enumerate(llm_results):
            print(f"  {i+1}. {txn}")
            
    except Exception as e:
        print(f"Error during extraction: {e}")
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
    
    # Test the most recent one
    latest_file = max(bank_statement_files, key=os.path.getmtime)
    print(f"Testing latest file: {latest_file}")
    test_bank_extraction(latest_file)