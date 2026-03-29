import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import (
    Client,
    Invoice,
    Reminder,
    ReminderPriority,
    ReminderStatus,
    User,
    WorkflowDefinition,
    WorkflowExecutionLog,
)
from core.services.feature_config_service import FeatureConfigService
from core.utils.notifications import send_notification

logger = logging.getLogger(__name__)


DEFAULT_OVERDUE_WORKFLOW_KEY = "invoice-overdue-reminder-task"

SUPPORTED_TRIGGERS = {
    "invoice_became_overdue": {
        "label": "Invoice becomes overdue",
        "description": "Runs the first time an unpaid invoice passes its due date.",
        "trigger_type": "invoice_became_overdue",
        "conditions": {
            "invoice_statuses": ["sent", "pending", "partially_paid", "overdue"],
            "exclude_statuses": ["paid", "cancelled", "draft"],
        },
    },
}

SUPPORTED_ACTIONS = {
    "send_internal_notification": {
        "label": "Send internal reminder",
        "description": "Notify the responsible teammate that the invoice needs follow-up.",
    },
    "create_internal_task": {
        "label": "Create internal task",
        "description": "Create a reminder-backed task assigned to the responsible teammate.",
    },
}


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_default_workflows(self) -> None:
        if not FeatureConfigService.is_enabled("workflow_automation", db=self.db):
            return

        existing = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.key == DEFAULT_OVERDUE_WORKFLOW_KEY
        ).first()

        if existing:
            return

        workflow = WorkflowDefinition(
            name="Overdue invoice follow-up",
            key=DEFAULT_OVERDUE_WORKFLOW_KEY,
            description="When an invoice first becomes overdue, notify the responsible teammate and create an internal follow-up task.",
            trigger_type="invoice_became_overdue",
            conditions={
                "invoice_statuses": ["sent", "pending", "partially_paid", "overdue"],
                "exclude_statuses": ["paid", "cancelled", "draft"],
            },
            actions={
                "send_internal_notification": True,
                "create_internal_task": True,
                "task_type": "reminder",
                "task_title_template": "Follow up on overdue invoice #{invoice_number}",
                "task_due_in_days": 1,
            },
            is_enabled=True,
            is_system=True,
            is_default=True,
        )
        self.db.add(workflow)
        self.db.commit()

    def list_workflows(self) -> list[WorkflowDefinition]:
        self.ensure_default_workflows()
        return self.db.query(WorkflowDefinition).order_by(
            WorkflowDefinition.is_system.desc(),
            WorkflowDefinition.created_at.asc(),
        ).all()

    def get_catalog(self) -> Dict[str, Any]:
        return {
            "triggers": [
                {"id": key, "label": value["label"], "description": value["description"]}
                for key, value in SUPPORTED_TRIGGERS.items()
            ],
            "actions": [
                {"id": key, "label": value["label"], "description": value["description"]}
                for key, value in SUPPORTED_ACTIONS.items()
            ],
        }

    def create_workflow(
        self,
        *,
        name: str,
        description: Optional[str],
        trigger_type: str,
        action_ids: list[str],
    ) -> WorkflowDefinition:
        self.ensure_default_workflows()

        if trigger_type not in SUPPORTED_TRIGGERS:
            raise ValueError("Unsupported workflow trigger")

        normalized_actions = []
        for action_id in action_ids:
            if action_id not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported workflow action: {action_id}")
            if action_id not in normalized_actions:
                normalized_actions.append(action_id)

        if not normalized_actions:
            raise ValueError("Select at least one workflow action")

        actions = {
            "send_internal_notification": "send_internal_notification" in normalized_actions,
            "create_internal_task": "create_internal_task" in normalized_actions,
            "task_type": "reminder",
            "task_title_template": "Follow up on overdue invoice #{invoice_number}",
            "task_due_in_days": 1,
        }

        workflow = WorkflowDefinition(
            name=name.strip(),
            key=self._build_workflow_key(name),
            description=(description or "").strip() or SUPPORTED_TRIGGERS[trigger_type]["description"],
            trigger_type=SUPPORTED_TRIGGERS[trigger_type]["trigger_type"],
            conditions=SUPPORTED_TRIGGERS[trigger_type]["conditions"],
            actions=actions,
            is_enabled=True,
            is_system=False,
            is_default=False,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def process_due_invoice_workflows(self) -> Dict[str, Any]:
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        if not FeatureConfigService.is_enabled("workflow_automation", db=self.db):
            return stats

        self.ensure_default_workflows()

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "invoice_became_overdue",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.is_deleted == False,
            Invoice.due_date.isnot(None),
            Invoice.due_date < now,
            Invoice.status.in_(["sent", "pending", "partially_paid", "overdue"]),
        ).all()

        for workflow in workflows:
            for invoice in overdue_invoices:
                stats["processed_count"] += 1
                event_key = f"invoice:{invoice.id}:overdue"

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._resolve_assigned_user(invoice)
                    if assigned_user is None:
                        raise ValueError(f"No eligible user found to own invoice {invoice.id} workflow task")

                    client = self.db.query(Client).filter(Client.id == invoice.client_id).first()
                    details = {
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.number,
                        "client_name": client.name if client else None,
                        "amount": invoice.amount,
                        "currency": invoice.currency,
                        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                        "days_overdue": max((now.date() - invoice.due_date.date()).days, 0) if invoice.due_date else None,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type="invoice_overdue",
                            user_id=assigned_user.id,
                            resource_type="invoice",
                            resource_id=str(invoice.id),
                            resource_name=invoice.number,
                            details=details,
                        )
                        stats["notification_count"] += 1

                    task_id = None
                    if workflow.actions and workflow.actions.get("create_internal_task", True):
                        reminder = self._create_internal_task(
                            workflow=workflow,
                            invoice=invoice,
                            assigned_user=assigned_user,
                            details=details,
                        )
                        task_id = reminder.id
                        stats["created_task_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="invoice",
                        entity_id=str(invoice.id),
                        status="success",
                        details={**details, "task_id": task_id, "assigned_user_id": assigned_user.id},
                    )
                    self.db.add(execution_log)
                    workflow.last_run_at = now
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    error = f"Workflow {workflow.key} failed for invoice {invoice.id}: {exc}"
                    logger.error(error)
                    stats["errors"].append(error)

        return stats

    def run_workflow_now(self, workflow_id: int) -> Dict[str, Any]:
        workflow = self.db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.trigger_type != "invoice_became_overdue":
            raise ValueError("Manual runs are only supported for invoice overdue workflows")

        return self.process_due_invoice_workflows()

    def _has_execution_log(self, workflow_id: int, event_key: str) -> bool:
        return self.db.query(WorkflowExecutionLog).filter(
            WorkflowExecutionLog.workflow_id == workflow_id,
            WorkflowExecutionLog.event_key == event_key,
        ).first() is not None

    def _resolve_assigned_user(self, invoice: Invoice) -> Optional[User]:
        if invoice.created_by_user_id:
            user = self.db.query(User).filter(
                User.id == invoice.created_by_user_id,
                User.is_active == True,
            ).first()
            if user:
                return user

        admin_user = self.db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).order_by(User.id.asc()).first()
        if admin_user:
            return admin_user

        return self.db.query(User).filter(User.is_active == True).order_by(User.id.asc()).first()

    def _create_internal_task(
        self,
        workflow: WorkflowDefinition,
        invoice: Invoice,
        assigned_user: User,
        details: Dict[str, Any],
    ) -> Reminder:
        now = datetime.now(timezone.utc)
        due_in_days = 1
        if workflow.actions:
            due_in_days = int(workflow.actions.get("task_due_in_days", 1))

        title_template = "Follow up on overdue invoice #{invoice_number}"
        if workflow.actions:
            title_template = workflow.actions.get("task_title_template", title_template)

        reminder = Reminder(
            title=title_template.format(invoice_number=invoice.number),
            description=(
                f"Invoice #{invoice.number} for {details.get('client_name') or 'Unknown client'} "
                f"is overdue. Reach out and document the follow-up."
            ),
            due_date=now + timedelta(days=due_in_days),
            status=ReminderStatus.PENDING,
            priority=ReminderPriority.HIGH,
            created_by_id=assigned_user.id,
            assigned_to_id=assigned_user.id,
            tags=["workflow-task", "invoice-overdue"],
            extra_metadata={
                "workflow_key": workflow.key,
                "workflow_id": workflow.id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.number,
                "task_kind": "internal_follow_up",
            },
        )
        self.db.add(reminder)
        self.db.flush()
        return reminder

    def _build_workflow_key(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not base:
            base = "workflow"

        candidate = base
        suffix = 1
        while self.db.query(WorkflowDefinition).filter(WorkflowDefinition.key == candidate).first():
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate
