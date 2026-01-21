from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from ..base import BaseAnomalyRule, AnomalyResult

class RoundingAnomalyRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "rounding_anomaly"

    @property
    def name(self) -> str:
        return "Rounding Anomaly"

    @property
    def description(self) -> str:
        return "Detects transactions with perfectly round numbers, which can sometimes indicate falsified expenses or lack of exact documentation."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        amount = (
            getattr(entity, 'amount', None) or 
            getattr(entity, 'total_amount', None) or
            getattr(entity, 'subtotal', None)
        )
        
        if amount is None or amount == 0:
            return None

        # Check if amount is perfectly round (e.g., 100.00, 500.00, 1000.00)
        # We define "perfectly round" as significant round numbers like multiples of 50 or 100 for higher amounts
        is_round = False
        if amount >= 100 and amount % 100 == 0:
            is_round = True
        elif amount >= 50 and amount % 50 == 0:
            is_round = True
        
        if is_round and amount > 250: # Only flag significant round numbers above a threshold
            return AnomalyResult(
                risk_score=40.0,
                risk_level="medium",
                reason=f"Rounding anomaly: Perfect round amount of {amount} detected. This may indicate a lack of precise documentation or potential falsification.",
                rule_id=self.rule_id,
                details={"amount": amount}
            )
        return None
