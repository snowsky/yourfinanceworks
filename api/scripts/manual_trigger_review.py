
import os
import sys
sys.path.append('/app')

from core.models.database import SessionLocal, set_tenant_context, get_tenant_context
from core.models.models_per_tenant import Invoice, Expense, BankStatement
from core.services.review_event_service import get_review_event_service
from core.services.tenant_database_manager import tenant_db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def manual_trigger(tenant_id: int):
    logger.info(f"Manually triggering full review for tenant {tenant_id}")
    set_tenant_context(tenant_id)
    
    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
    db = SessionLocal_tenant()
    
    try:
        # Reset Invoices
        invoice_count = db.query(Invoice).filter(Invoice.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)
        
        # Reset Expenses
        expense_count = db.query(Expense).filter(Expense.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)
        
        # Reset Bank Statements
        statement_count = db.query(BankStatement).filter(BankStatement.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)
        
        db.commit()
        logger.info(f"Reset {invoice_count} invoices, {expense_count} expenses, {statement_count} statements")
        
        # Publish Kafka event
        event_service = get_review_event_service()
        event_service.publish_full_review_trigger(tenant_id)
        logger.info("Published Kafka event")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    manual_trigger(1)
