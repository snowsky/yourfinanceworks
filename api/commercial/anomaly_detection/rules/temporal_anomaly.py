from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from ..base import BaseAnomalyRule, AnomalyResult

class TemporalAnomalyRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "temporal_anomaly"

    @property
    def name(self) -> str:
        return "Temporal Anomaly"

    @property
    def description(self) -> str:
        return "Identifies transactions filed on weekends, holidays, or at unusual hours, which might indicate circumventing standard business processes."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        # Try different date attributes depending on entity type
        dt = (
            getattr(entity, 'expense_date', None) or 
            getattr(entity, 'date', None) or 
            getattr(entity, 'due_date', None) or 
            getattr(entity, 'created_at', None)
        )
        
        if not dt:
            return None
            
        # Ensure we have a datetime object
        if not isinstance(dt, datetime):
            return None

        is_weekend = dt.weekday() >= 5 # 5=Saturday, 6=Sunday
        is_odd_hours = dt.hour < 7 or dt.hour > 20 # Before 7am or after 8pm
        
        reasons = []
        if is_weekend:
            reasons.append("transaction occurred on a weekend")
        if is_odd_hours:
            reasons.append(f"transaction occurred at an unusual hour ({dt.hour}:00)")
            
        if reasons:
            risk_score = 30.0 + (20.0 if is_weekend and is_odd_hours else 0.0)
            return AnomalyResult(
                risk_score=risk_score,
                risk_level="low" if risk_score < 40 else "medium",
                reason=f"Temporal anomaly: {' and '.join(reasons)}.",
                rule_id=self.rule_id,
                details={"weekday": dt.weekday(), "hour": dt.hour}
            )
            
        return None
