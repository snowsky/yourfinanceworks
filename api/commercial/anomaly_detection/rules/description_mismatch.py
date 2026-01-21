import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from ..base import BaseAnomalyRule, AnomalyResult

logger = logging.getLogger(__name__)

class DescriptionMismatchRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "description_mismatch"

    @property
    def name(self) -> str:
        return "Description Mismatch"

    @property
    def description(self) -> str:
        return "AI-powered detection of discrepancies between the vendor's known business activity and the items described in the transaction."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        vendor = getattr(entity, 'vendor', None) or getattr(entity, 'vendor_name', None) or getattr(entity, 'client', None)
        if hasattr(vendor, 'name'): vendor = vendor.name # Handle client object
        
        category = getattr(entity, 'category', None)
        description = (
            getattr(entity, 'description', None) or 
            getattr(entity, 'notes', None) or 
            getattr(entity, 'memo', None)
        )
        
        if not vendor or (not category and not description):
            return None

        # AI-powered audit (Senior Forensic Auditor)
        ai_config = context.get("ai_config") if context else None
        if ai_config:
            result = await self._run_ai_audit(
                db=db,
                prompt_name="forensic_auditor_description_mismatch",
                variables={
                    "vendor": vendor,
                    "category": category,
                    "description": description
                },
                ai_config=ai_config
            )
            
            if result and result.get("is_mismatch"):
                return AnomalyResult(
                    risk_score=float(result.get("risk_score", 60.0)),
                    risk_level=result.get("risk_level", "medium"),
                    reason=result.get("reasoning", f"AI Auditor identified a mismatch for {vendor}."),
                    rule_id=self.rule_id,
                    details={"ai_analysis": result}
                )
        
        return None
