
import os
import sys
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add api directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'api'))

from core.models.database import set_tenant_context
from core.services.tenant_database_manager import tenant_db_manager
from core.models.models_per_tenant import Invoice

def check_invoice_review():
    tenant_id = 1
    # Ensure encryption is configured as in the app
    os.environ["ENCRYPTION_ENABLED"] = "true"

    set_tenant_context(tenant_id)
    SessionLocal = tenant_db_manager.get_tenant_session(tenant_id)
    db = SessionLocal()

    try:
        invoice = db.query(Invoice).filter(Invoice.id == 1).first()
        if not invoice:
            print("Invoice 1 not found")
            return

        print(f"Invoice ID: {invoice.id}")
        print(f"Review Status: {invoice.review_status}")
        print(f"Review Result Type: {type(invoice.review_result)}")
        print(f"Review Result: {json.dumps(invoice.review_result, indent=2)}")

        # Check if dates are valid in review_result
        for key in ['date', 'due_date', 'expense_date', 'period_start', 'period_end']:
            if invoice.review_result and key in invoice.review_result:
                val = invoice.review_result[key]
                print(f"Checking field '{key}': '{val}'")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_invoice_review()
