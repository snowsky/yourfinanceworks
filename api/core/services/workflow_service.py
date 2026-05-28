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

# Trigger registry. Each entry carries the user-facing label/description plus
# runtime metadata the processor needs: the notification event type to emit,
# the default task title template, the task tag, and the per-trigger event-key
# suffix that powers idempotent dedup against ``WorkflowExecutionLog``.
SUPPORTED_TRIGGERS = {
    "invoice_became_overdue": {
        "label": "Invoice becomes overdue",
        "description": "Runs the first time an unpaid invoice passes its due date.",
        "trigger_type": "invoice_became_overdue",
        "conditions": {
            "invoice_statuses": ["sent", "pending", "partially_paid", "overdue"],
            "exclude_statuses": ["paid", "cancelled", "draft"],
        },
        "notification_event_type": "invoice_overdue",
        "default_task_title_template": "Follow up on overdue invoice #{invoice_number}",
        "task_tag": "invoice-overdue",
        "event_key_suffix": "overdue",
    },
    "invoice_created": {
        "label": "Invoice is created",
        "description": "Runs once when a new invoice is created (and not retroactively for invoices that pre-date the workflow).",
        "trigger_type": "invoice_created",
        "conditions": {},
        "notification_event_type": "invoice_created",
        "default_task_title_template": "Review newly created invoice #{invoice_number}",
        "task_tag": "invoice-created",
        "event_key_suffix": "created",
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
                            default_title_template=SUPPORTED_TRIGGERS["invoice_became_overdue"][
                                "default_task_title_template"
                            ],
                            task_tag=SUPPORTED_TRIGGERS["invoice_became_overdue"]["task_tag"],
                            description_template=(
                                "Invoice #{invoice_number} for {client_name} is overdue. "
                                "Reach out and document the follow-up."
                            ),
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

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="invoice",
                            entity_id=str(invoice.id),
                            status="failed",
                            details={
                                "invoice_id": invoice.id,
                                "invoice_number": invoice.number,
                                "error": str(exc),
                                "workflow_key": workflow.key,
                            },
                        )
                        self.db.add(failed_log)
                        self.db.commit()
                    except Exception as log_exc:
                        self.db.rollback()
                        logger.error(f"Failed to record failed workflow execution log: {log_exc}")

        return stats

    def process_invoice_created_workflows(self) -> Dict[str, Any]:
        """Fire `invoice_created` workflows for invoices not yet processed.

        Considers only invoices created on/after the workflow's own
        ``created_at`` so deploying a new workflow doesn't retroactively
        fire for years of pre-existing invoices. The execution-log row
        per (workflow, invoice) keeps the scan idempotent across reruns.
        """
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "invoice_created",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        trigger_meta = SUPPORTED_TRIGGERS["invoice_created"]

        for workflow in workflows:
            invoices = self.db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.created_at.isnot(None),
                Invoice.created_at >= workflow.created_at,
            ).all()

            for invoice in invoices:
                stats["processed_count"] += 1
                event_key = f"invoice:{invoice.id}:{trigger_meta['event_key_suffix']}"

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._resolve_assigned_user(invoice)
                    if assigned_user is None:
                        raise ValueError(
                            f"No eligible user found to own invoice {invoice.id} workflow task"
                        )

                    client = self.db.query(Client).filter(Client.id == invoice.client_id).first()
                    details = {
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.number,
                        "client_name": client.name if client else None,
                        "amount": invoice.amount,
                        "currency": invoice.currency,
                        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type=trigger_meta["notification_event_type"],
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
                            default_title_template=trigger_meta["default_task_title_template"],
                            task_tag=trigger_meta["task_tag"],
                            description_template=(
                                "Invoice #{invoice_number} for {client_name} was just created. "
                                "Review the draft and send to the client if it's ready."
                            ),
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

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="invoice",
                            entity_id=str(invoice.id),
                            status="failed",
                            details={
                                "invoice_id": invoice.id,
                                "invoice_number": invoice.number,
                                "error": str(exc),
                                "workflow_key": workflow.key,
                            },
                        )
                        self.db.add(failed_log)
                        self.db.commit()
                    except Exception as log_exc:
                        self.db.rollback()
                        logger.error(f"Failed to record failed workflow execution log: {log_exc}")

        return stats

    # Dispatch table: trigger_type -> bound processor method. Used by both the
    # background runner and the manual ``run_workflow_now`` endpoint so a new
    # trigger only needs to be added once.
    @property
    def _trigger_processors(self) -> Dict[str, Any]:
        return {
            "invoice_became_overdue": self.process_due_invoice_workflows,
            "invoice_created": self.process_invoice_created_workflows,
        }

    def process_all_workflows(self) -> Dict[str, Any]:
        """Run every registered trigger's processor for the current tenant.

        Called by the per-tenant background runner. Per-trigger stats are
        merged into a single dict for the runner log.
        """
        combined: Dict[str, Any] = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }
        for trigger_type, processor in self._trigger_processors.items():
            try:
                stats = processor()
            except Exception as exc:
                logger.exception("Workflow processor for %s raised", trigger_type)
                combined["errors"].append(f"{trigger_type}: {exc}")
                continue
            for key in ("processed_count", "created_task_count", "notification_count", "skipped_count"):
                combined[key] += stats.get(key, 0)
            combined["errors"].extend(stats.get("errors", []))
        return combined

    def run_workflow_now(self, workflow_id: int) -> Dict[str, Any]:
        workflow = self.db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
        if not workflow:
            raise ValueError("Workflow not found")

        processor = self._trigger_processors.get(workflow.trigger_type)
        if processor is None:
            raise ValueError(f"Manual runs are not supported for trigger {workflow.trigger_type!r}")

        return processor()

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
        *,
        default_title_template: str,
        task_tag: str,
        description_template: str,
    ) -> Reminder:
        now = datetime.now(timezone.utc)
        due_in_days = 1
        if workflow.actions:
            due_in_days = int(workflow.actions.get("task_due_in_days", 1))

        title_template = default_title_template
        if workflow.actions:
            title_template = workflow.actions.get("task_title_template", title_template)

        client_name = details.get("client_name") or "Unknown client"
        reminder = Reminder(
            title=title_template.format(invoice_number=invoice.number),
            description=description_template.format(
                invoice_number=invoice.number, client_name=client_name
            ),
            due_date=now + timedelta(days=due_in_days),
            status=ReminderStatus.PENDING,
            priority=ReminderPriority.HIGH,
            created_by_id=assigned_user.id,
            assigned_to_id=assigned_user.id,
            tags=["workflow-task", task_tag],
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

    def list_execution_logs(
        self,
        *,
        workflow_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        query = self.db.query(WorkflowExecutionLog)

        if workflow_id is not None:
            query = query.filter(WorkflowExecutionLog.workflow_id == workflow_id)
        if status is not None:
            query = query.filter(WorkflowExecutionLog.status == status)

        total = query.count()

        logs = query.order_by(WorkflowExecutionLog.created_at.desc()).offset(offset).limit(limit).all()

        result_logs = []
        for log in logs:
            log.workflow_name = log.workflow.name if log.workflow else None
            log.workflow_key = log.workflow.key if log.workflow else None
            result_logs.append(log)

        return {"total": total, "logs": result_logs}

    def delete_workflow(self, workflow_id: int) -> None:
        workflow = self.db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.is_system:
            raise ValueError("System workflows cannot be deleted")

        self.db.delete(workflow)
        self.db.commit()

    def update_workflow(
        self,
        workflow_id: int,
        *,
        name: str,
        description: Optional[str],
        action_ids: list[str],
    ) -> WorkflowDefinition:
        workflow = self.db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.is_system:
            raise ValueError("System workflows cannot be edited")

        if not name.strip():
            raise ValueError("Workflow name cannot be empty")

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

        workflow.name = name.strip()
        workflow.description = (description or "").strip() or SUPPORTED_TRIGGERS[workflow.trigger_type]["description"]
        workflow.actions = actions
        workflow.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(workflow)
        return workflow

