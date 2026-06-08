"""Fire-and-forget trigger for tenant-side anomaly / fraud auditing.

Called after an invoice/expense write to enqueue an out-of-band audit so the
detection engine re-scores the entity (results land in the ``anomalies`` table
and surface on the dashboard). Best-effort by design:

- Never raises into the caller — a failed enqueue must not fail the write.
- No-op when the tenant lacks the ``anomaly_detection`` license.
- No-op when the commercial OCR/audit module is not installed.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def trigger_anomaly_audit(
    tenant_id: int,
    entity_type: str,
    entity_id: int,
    db: Optional[Session] = None,
) -> None:
    """Enqueue an anomaly audit for ``entity_type``/``entity_id`` (best-effort)."""
    try:
        # Skip work for tenants without the feature licensed.
        from core.services.feature_config_service import FeatureConfigService

        if db is not None and not FeatureConfigService.is_enabled(
            "anomaly_detection", db=db
        ):
            return
    except Exception:
        # If the gate check itself fails, fall through and let the consumer gate.
        pass

    try:
        from commercial.ai.services.ocr_service import publish_fraud_audit_task
    except Exception:
        # Commercial audit module not installed — feature unavailable.
        return

    try:
        publish_fraud_audit_task(tenant_id, entity_type, entity_id, reprocess_mode=False)
    except Exception as e:  # pragma: no cover - defensive, must never break writes
        logger.warning(
            f"Anomaly audit trigger failed for {entity_type} {entity_id}: {e}"
        )
