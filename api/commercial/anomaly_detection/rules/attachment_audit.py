import logging
from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session
from ..base import BaseAnomalyRule, AnomalyResult

logger = logging.getLogger(__name__)

class AttachmentAuditRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "attachment_audit"

    @property
    def name(self) -> str:
        return "Attachment Integrity Audit"

    @property
    def description(self) -> str:
        return "Uses multimodal AI to inspect file attachments for manual alterations, suspicious formatting, or digital inconsistencies."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        vendor = getattr(entity, 'vendor', None) or getattr(entity, 'vendor_name', None) or getattr(entity, 'client', None)
        if hasattr(vendor, 'name'): vendor = vendor.name
        
        amount = getattr(entity, 'amount', None) or getattr(entity, 'total_amount', None)
        
        attachment_paths = context.get("attachment_paths", []) if context else []
        if not attachment_paths:
            return None

        # AI-powered multimodal audit
        ai_config = context.get("ai_config") if context else None
        if ai_config:
            result = await self._run_ai_audit(
                db=db,
                prompt_name="forensic_auditor_attachment",
                variables={
                    "vendor": str(vendor),
                    "amount": str(amount)
                },
                ai_config=ai_config,
                attachment_paths=attachment_paths
            )
            
            if result and result.get("is_tampered"):
                return AnomalyResult(
                    risk_score=float(result.get("risk_score", 80.0)),
                    risk_level=result.get("risk_level", "high"),
                    reason=result.get("reasoning", "AI Auditor detected signs of document tampering or inconsistencies."),
                    rule_id=self.rule_id,
                    details={
                        "ai_analysis": result,
                        "detected_anomalies": result.get("detected_anomalies", [])
                    }
                )
        
        return None
