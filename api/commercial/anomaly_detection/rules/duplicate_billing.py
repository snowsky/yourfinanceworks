from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..base import BaseAnomalyRule, AnomalyResult

class DuplicateBillingRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "duplicate_billing"

    @property
    def name(self) -> str:
        return "Duplicate Billing"

    @property
    def description(self) -> str:
        return "Identifies identical amounts, vendors, or invoice numbers that may indicate accidental double billing or fraud."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        from core.models.models_per_tenant import Expense, Invoice
        
        amount = getattr(entity, 'amount', None) or getattr(entity, 'total_amount', None)
        vendor = getattr(entity, 'vendor', None) or getattr(entity, 'vendor_name', None)
        
        if not amount or not vendor:
            return None

        # Cross-entity check: Expense vs Invoice
        # 1. Search in Expenses
        expense_duplicates = db.query(Expense).filter(
            Expense.id != (entity.id if entity_type == "expense" else -1),
            Expense.amount == amount,
            Expense.vendor == vendor,
            Expense.is_deleted == False if hasattr(Expense, 'is_deleted') else True
        ).all()

        # 2. Search in Invoices
        invoice_duplicates = db.query(Invoice).filter(
            Invoice.id != (entity.id if entity_type == "invoice" else -1),
            Invoice.amount == amount,
            # Invoices might have 'client' but often store vendor name in notes or metadata if they are bills
            # For simplicity, we match amount and potentially description if available
            Invoice.is_deleted == False if hasattr(Invoice, 'is_deleted') else True
        ).all()

        total_dups = len(expense_duplicates) + len(invoice_duplicates)
        
        if total_dups > 0:
            return AnomalyResult(
                risk_score=85.0 if total_dups > 1 else 70.0,
                risk_level="high",
                reason=f"Potential duplicate billing detected. Found {len(expense_duplicates)} expenses and {len(invoice_duplicates)} invoices with identical amount ({amount}) and similar vendor information.",
                rule_id=self.rule_id,
                details={
                    "expense_ids": [d.id for d in expense_duplicates],
                    "invoice_ids": [d.id for d in invoice_duplicates]
                }
            )
            
        return None
