"""
Shared dependencies and utilities for approval routers.
"""

import logging
from fastapi import Depends
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.services.notification_service import NotificationService
from commercial.workflows.approvals.services.approval_service import ApprovalService
from commercial.workflows.approvals.services.approval_permission_service import ApprovalPermissionService

logger = logging.getLogger(__name__)


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    """Get approval service instance with notification service."""
    notification_service = NotificationService(db, None)
    return ApprovalService(db, notification_service)


def get_approval_permission_service(db: Session = Depends(get_db)) -> ApprovalPermissionService:
    """Get approval permission service instance."""
    return ApprovalPermissionService(db)
