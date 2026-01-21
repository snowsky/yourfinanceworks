import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from commercial.ai.services.ai_config_service import AIConfigService
from core.services.feature_config_service import FeatureConfigService
from core.models.models_per_tenant import Anomaly
from .base import BaseAnomalyRule, AnomalyResult

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """
    Service for orchestrating AI-powered anomaly detection analysis.
    Acts as a Senior Forensic Auditor by running a suite of modular rules.
    """

    _rules: List[BaseAnomalyRule] = []

    def __init__(self, db: Session):
        self.db = db
        self._initialize_rules()

    def _initialize_rules(self):
        """Register all available detection rules."""
        # Rules will be lazily loaded or manually registered here
        # To be implemented as rules are created
        if not self._rules:
            from .rules.duplicate_billing import DuplicateBillingRule
            from .rules.rounding_anomaly import RoundingAnomalyRule
            from .rules.phantom_vendor import PhantomVendorRule
            from .rules.threshold_splitting import ThresholdSplittingRule
            from .rules.temporal_anomaly import TemporalAnomalyRule
            from .rules.description_mismatch import DescriptionMismatchRule
            from .rules.attachment_audit import AttachmentAuditRule

            self._rules = [
                DuplicateBillingRule(),
                RoundingAnomalyRule(),
                PhantomVendorRule(),
                ThresholdSplittingRule(),
                TemporalAnomalyRule(),
                DescriptionMismatchRule(),
                AttachmentAuditRule(),
            ]

    def _is_super_admin_context(self) -> bool:
        """
        Check if there are any super admin tenants in the system.
        Anomaly detection should run for super admin operations regardless
        of individual tenant licensing status.
        """
        try:
            from core.models.database import get_master_db
            from core.models.models import MasterUser

            # Check if any superuser exists in the system
            master_db = next(get_master_db())
            try:
                super_user_count = master_db.query(MasterUser).filter(
                    MasterUser.is_superuser == True
                ).count()
                return super_user_count > 0
            finally:
                master_db.close()
        except Exception as e:
            logger.warning(f"Error checking super admin context: {e}")
            return False

    async def analyze_entity(self, entity: Any, entity_type: str, reprocess_mode: bool = False) -> List[Anomaly]:
        """
        Run all registered anomaly detection rules against an entity.

        Args:
            entity: The Expense, Invoice, or BankTransaction object.
            entity_type: 'expense', 'invoice', or 'bank_transaction'.
            reprocess_mode: If True, process entity regardless of audit status.

        Returns:
            List of created Anomaly records.
        """
        # 1. Check if feature is enabled (bypass for super admin tenants)
        if not self._is_super_admin_context() and not FeatureConfigService.is_enabled("anomaly_detection", db=self.db):
            logger.info(
                f"Anomaly detection skipped: feature not enabled for this license."
            )
            return []

        # 2. Check if entity was already audited (skip unless in reprocess mode)
        if not reprocess_mode and hasattr(entity, 'is_audited') and entity.is_audited:
            logger.info(
                f"Skipping audit for {entity_type} ID: {entity.id} - already audited on {entity.last_audited_at}"
            )
            return []

        logger.info(f"Starting audit for {entity_type} ID: {entity.id} (reprocess_mode: {reprocess_mode})")

        # 2. Get AI config for the "Auditor" persona
        ai_config = AIConfigService.get_ai_config(
            self.db, component="chat"
        )  # Reuse chat AI config

        # 3. Fetch attachments for the entity
        attachment_paths = self._get_attachment_paths(entity, entity_type)

        context = {
            "ai_config": ai_config,
            "attachment_paths": attachment_paths,
            "audit_timestamp": datetime.now(timezone.utc),
            "forensic_persona": "Senior Forensic Auditor and Fraud Detection Specialist",
        }

        created_anomalies = []

        # 3. Run all rules
        for rule in self._rules:
            try:
                result = await rule.analyze(self.db, entity, entity_type, context)
                if result:
                    anomaly = self._save_anomaly(entity, entity_type, result)
                    created_anomalies.append(anomaly)
                    logger.warning(
                        f"🚩 Anomaly detected by {rule.rule_id} for {entity_type} {entity.id}: {result.reason}"
                    )
            except Exception as e:
                logger.error(
                    f"Error running anomaly rule {rule.rule_id}: {e}", exc_info=True
                )

        if created_anomalies:
            # Mark entity as audited
            if hasattr(entity, 'is_audited'):
                entity.is_audited = True
                entity.last_audited_at = datetime.now(timezone.utc)

            self.db.commit()

        return created_anomalies

    def _get_attachment_paths(self, entity: Any, entity_type: str) -> List[str]:
        """Fetch all physical file paths for attachments linked to an entity."""
        paths = []
        try:
            if entity_type == "expense":
                if hasattr(entity, 'receipt_path') and entity.receipt_path:
                    paths.append(entity.receipt_path)
                # Check for multiple attachments
                from core.models.models_per_tenant import ExpenseAttachment
                attachments = self.db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == entity.id).all()
                for att in attachments:
                    if att.file_path: paths.append(att.file_path)

            elif entity_type == "invoice":
                if hasattr(entity, 'attachment_path') and entity.attachment_path:
                    paths.append(entity.attachment_path)
                # Check for multiple attachments
                from core.models.models_per_tenant import InvoiceAttachment
                attachments = self.db.query(InvoiceAttachment).filter(InvoiceAttachment.invoice_id == entity.id).all()
                for att in attachments:
                    if att.file_path: paths.append(att.file_path)

            elif entity_type == "bank_transaction":
                # Bank transactions are linked to a statement, which has attachments
                from core.models.models_per_tenant import BankStatement, BankStatementAttachment
                statement = self.db.query(BankStatement).filter(BankStatement.id == entity.statement_id).first()
                if statement:
                    attachments = self.db.query(BankStatementAttachment).filter(BankStatementAttachment.statement_id == statement.id).all()
                    for att in attachments:
                        if att.file_path: paths.append(att.file_path)

        except Exception as e:
            logger.error(f"Error fetching attachment paths for {entity_type} {entity.id}: {e}")
            
        return list(set(paths)) # Remove duplicates

    def _save_anomaly(
        self, entity: Any, entity_type: str, result: AnomalyResult
    ) -> Anomaly:
        """Persist the anomaly detection result to the database."""
        anomaly = Anomaly(
            entity_type=entity_type,
            entity_id=entity.id,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            reason=result.reason,
            rule_id=result.rule_id,
            details=result.details,
        )
        self.db.add(anomaly)
        return anomaly
