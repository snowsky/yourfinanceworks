#!/usr/bin/env python3
"""
Trigger OCR reprocessing for an expense.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the api directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.models.database import get_db, set_tenant_context
from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.services.ocr_service import queue_or_process_attachment

def trigger_ocr_reprocess(expense_id: int):
    """Trigger OCR reprocessing for an expense."""
    
    print(f"🔄 Triggering OCR reprocessing for expense {expense_id}...")
    
    try:
        # Set tenant context
        set_tenant_context(1)
        
        # Get database session
        db = next(get_db())
        
        # Get the expense
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            print(f"❌ Expense {expense_id} not found")
            return
        
        # Get the most recent attachment
        attachment = db.query(ExpenseAttachment).filter(
            ExpenseAttachment.expense_id == expense_id
        ).order_by(ExpenseAttachment.uploaded_at.desc()).first()
        
        if not attachment:
            print(f"❌ No attachment found for expense {expense_id}")
            return
        
        print(f"📄 Found attachment:")
        print(f"    ID: {attachment.id}")
        print(f"    File path: {attachment.file_path}")
        print(f"    Filename: {attachment.filename}")
        
        # Reset expense status
        expense.analysis_status = "queued"
        expense.analysis_error = None
        expense.manual_override = False
        db.commit()
        
        print(f"✅ Reset expense status to 'queued'")
        
        # Queue OCR processing
        queue_or_process_attachment(
            db=db,
            tenant_id=1,
            expense_id=expense_id,
            attachment_id=attachment.id,
            file_path=attachment.file_path
        )
        
        print(f"✅ Queued OCR processing for expense {expense_id}")
        
    except Exception as e:
        print(f"❌ Error triggering OCR reprocess: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    trigger_ocr_reprocess(10)