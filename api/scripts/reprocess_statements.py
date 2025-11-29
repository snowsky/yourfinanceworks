#!/usr/bin/env python3
"""
Script to manually reprocess bank statements for testing improvements.
"""
import os
import sys
import json
from datetime import datetime

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.statement_service import process_bank_pdf_with_llm
from core.services.ocr_service import publish_bank_statement_task
from core.models.database import get_tenant_context, set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models_per_tenant import BankStatement, BankStatementTransaction
from sqlalchemy.orm import Session

def reprocess_statement(tenant_id: int, statement_id: int):
    """Reprocess a specific statement."""
    try:
        set_tenant_context(tenant_id)
        SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
        db = SessionLocalTenant()
        
        try:
            # Get the bank statement
            stmt = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
            if not stmt:
                print(f"Bank statement {statement_id} not found in tenant {tenant_id}")
                return
            
            print(f"Reprocessing bank statement {statement_id}: {stmt.original_filename}")
            print(f"File path: {stmt.file_path}")
            
            if not os.path.exists(stmt.file_path):
                print(f"File not found: {stmt.file_path}")
                return
            
            # Publish to Kafka for reprocessing
            message = {
                "tenant_id": tenant_id,
                "statement_id": statement_id,
                "file_path": stmt.file_path,
                "ts": datetime.utcnow().isoformat(),
            }
            
            success = publish_bank_statement_task(message)
            if success:
                print(f"Successfully queued bank statement {statement_id} for reprocessing")
            else:
                print(f"Failed to queue bank statement {statement_id} - processing inline")
                # Process inline as fallback
                txns = process_bank_pdf_with_llm(stmt.file_path)
                print(f"Extracted {len(txns)} transactions")
                
                # Update database
                db.query(BankStatementTransaction).filter(BankStatementTransaction.statement_id == statement_id).delete()
                count = 0
                for t in txns:
                    try:
                        dt = datetime.fromisoformat(t.get("date", "")).date()
                    except Exception:
                        dt = datetime.utcnow().date()
                    db.add(BankStatementTransaction(
                        statement_id=statement_id,
                        date=dt,
                        description=t.get("description", ""),
                        amount=float(t.get("amount", 0)),
                        transaction_type=(t.get("transaction_type") if t.get("transaction_type") in ("debit", "credit") else ("debit" if float(t.get("amount", 0)) < 0 else "credit")),
                        balance=(float(t["balance"]) if t.get("balance") is not None else None),
                        category=t.get("category"),
                    ))
                    count += 1
                
                stmt.status = "processed"
                stmt.extracted_count = count
                db.commit()
                print(f"Updated database with {count} transactions")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error reprocessing statement: {e}")
        import traceback
        traceback.print_exc()

def list_statements(tenant_id: int):
    """List all statements for a tenant."""
    try:
        set_tenant_context(tenant_id)
        SessionLocalTenant = tenant_db_manager.get_tenant_session(tenant_id)
        db = SessionLocalTenant()
        
        try:
            statements = db.query(BankStatement).filter(BankStatement.tenant_id == tenant_id).all()
            print(f"\nBank statements for tenant {tenant_id}:")
            for stmt in statements:
                print(f"  ID: {stmt.id}, File: {stmt.original_filename}, Status: {stmt.status}, Count: {stmt.extracted_count}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error listing statements: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python reprocess_statements.py list <tenant_id>")
        print("  python reprocess_statements.py reprocess <tenant_id> <statement_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        if len(sys.argv) != 3:
            print("Usage: python reprocess_statements.py list <tenant_id>")
            sys.exit(1)
        tenant_id = int(sys.argv[2])
        list_statements(tenant_id)
        
    elif command == "reprocess":
        if len(sys.argv) != 4:
            print("Usage: python reprocess_statements.py reprocess <tenant_id> <statement_id>")
            sys.exit(1)
        tenant_id = int(sys.argv[2])
        statement_id = int(sys.argv[3])
        reprocess_statement(tenant_id, statement_id)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)