import json
import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from ..base import BaseAnomalyRule, AnomalyResult

logger = logging.getLogger(__name__)

class PhantomVendorRule(BaseAnomalyRule):
    @property
    def rule_id(self) -> str:
        return "phantom_vendor"

    @property
    def name(self) -> str:
        return "Phantom Vendor detection"

    @property
    def description(self) -> str:
        return "Uses AI to identify suspicious vendor names, potential typos, or generic 'phantom' vendors that lack legitimate business characteristics."

    async def analyze(self, db: Session, entity: Any, entity_type: str, context: Optional[Dict[str, Any]] = None) -> Optional[AnomalyResult]:
        vendor_name = (
            getattr(entity, 'vendor', None) or 
            getattr(entity, 'vendor_name', None) or
            # Invoices might have a client, but we care about vendor-like entities
            (entity.client.name if hasattr(entity, 'client') and entity.client else None)
        )
        if not vendor_name:
            return None

        # Clean up vendor name if it's an encrypted column or complex object
        vendor_str = str(vendor_name)
        
        # Generic suspicious patterns
        suspicious_keywords = ["generic", "cash", "miscellaneous", "unknown", "admin", "test"]
        temp_score = 0.0
        if any(keyword in vendor_str.lower() for keyword in suspicious_keywords):
            temp_score = 50.0

        # AI-enhanced check (similar to OCR/Email workers)
        ai_config = context.get("ai_config") if context else None
        if ai_config:
            return await self._analyze_with_ai(db, vendor_str, ai_config)
        
        if temp_score > 0:
            return AnomalyResult(
                risk_score=temp_score,
                risk_level="medium",
                reason=f"Suspicious vendor name detected: '{vendor_str}'.",
                rule_id=self.rule_id
            )
            
        return None

    async def _analyze_with_ai(self, db: Session, vendor_name: str, ai_config: Dict[str, Any]) -> Optional[AnomalyResult]:
        """Perform deep AI analysis for phantom vendor characteristics."""
        result = await self._run_ai_audit(
            db=db,
            prompt_name="forensic_auditor_phantom_vendor",
            variables={"vendor_name": vendor_name},
            ai_config=ai_config
        )
        
        if result and result.get("is_phantom"):
            return AnomalyResult(
                risk_score=float(result.get("risk_score", 70.0)),
                risk_level=result.get("risk_level", "high"),
                reason=result.get("reasoning", f"AI Auditor identified '{vendor_name}' as a potential phantom vendor."),
                rule_id=self.rule_id,
                details={"ai_analysis": result}
            )
            
        return None
