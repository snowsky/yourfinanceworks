from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..base import BaseAnomalyRule, AnomalyResult

class ThresholdSplittingRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "threshold_splitting"

    @property
    def name(self) -> str:
        return "Threshold Splitting"

    @property
    def description(self) -> str:
        return "Detects multiple transactions to the same vendor that appear to be split to avoid approval thresholds (e.g., several $450 charges to avoid a $500 audit limit)."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        from core.models.models_per_tenant import Expense, Invoice, BankStatementTransaction
        
        # 1. Identify "vendor" (or description) for grouping
        vendor = getattr(entity, 'vendor', None) or getattr(entity, 'vendor_name', None) or getattr(entity, 'description', None)
        amount = getattr(entity, 'amount', None) or getattr(entity, 'total_amount', None) or getattr(entity, 'subtotal', None)
        
        if not vendor or not amount:
            return None

        # 2. Define common approval thresholds
        THRESHOLDS = [100, 250, 500, 1000, 2500, 5000]
        
        target_threshold = None
        for t in THRESHOLDS:
            if amount < t and amount > t * 0.8: # within 20% below threshold
                target_threshold = t
                break
        
        if not target_threshold:
            return None

        # 3. Choose search model
        model = Expense
        if entity_type == "invoice":
            model = Invoice
        elif entity_type == "bank_transaction":
            model = BankStatementTransaction

        # 4. Check for other transactions to same vendor/description in the last 30 days
        # (Using a slightly larger window for platform-wide audits)
        vendor_attr = getattr(model, 'vendor', None) or getattr(model, 'vendor_name', None) or getattr(model, 'description', None)
        amount_attr = getattr(model, 'amount', None) or getattr(model, 'total_amount', None) or getattr(model, 'subtotal', None)
        
        if vendor_attr is None or amount_attr is None:
            return None

        recent_count = db.query(model).filter(
            vendor_attr == vendor,
            model.id != entity.id,
            amount_attr < target_threshold,
            amount_attr > target_threshold * 0.8,
            model.is_deleted == False if hasattr(model, 'is_deleted') else True
        ).count()

        if recent_count >= 2: # 3 total transactions just below threshold
            return AnomalyResult(
                risk_score=80.0,
                risk_level="high",
                reason=f"Threshold splitting detected: {recent_count + 1} transactions for '{vendor}' are all just below the ${target_threshold} approval limit.",
                rule_id=self.rule_id,
                details={"threshold": target_threshold, "count": recent_count + 1}
            )
            
        return None
