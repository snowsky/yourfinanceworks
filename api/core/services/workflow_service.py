import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import (
    Client,
    ClientNote,
    Expense,
    ExpenseApproval,
    Invoice,
    Payment,
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
        "client_note_template": (
            "[Workflow {workflow_key}] Invoice #{invoice_number} is now overdue."
        ),
        "client_email_subject_template": (
            "Reminder: invoice #{invoice_number} is overdue"
        ),
        "client_email_body_template": (
            "Hi {client_name},\n\nOur records show invoice #{invoice_number} is "
            "past its due date. Please get in touch if you need help arranging "
            "payment.\n\nThanks."
        ),
        "slack_message_template": (
            ":warning: Invoice #{invoice_number} for {client_name} is overdue "
            "(workflow {workflow_key})."
        ),
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
        "client_note_template": (
            "[Workflow {workflow_key}] Invoice #{invoice_number} was created."
        ),
        "client_email_subject_template": "Your new invoice #{invoice_number}",
        "client_email_body_template": (
            "Hi {client_name},\n\nInvoice #{invoice_number} has just been "
            "created on your account. The full details are available in your "
            "client portal.\n\nThanks."
        ),
        "slack_message_template": (
            ":memo: Invoice #{invoice_number} created for {client_name} "
            "(workflow {workflow_key})."
        ),
    },
    "payment_received": {
        "label": "Payment is received",
        "description": "Runs once when a payment is recorded against an invoice (and not retroactively for payments that pre-date the workflow).",
        "trigger_type": "payment_received",
        "conditions": {},
        "notification_event_type": "payment_created",
        "default_task_title_template": "Acknowledge payment on invoice #{invoice_number}",
        "task_tag": "payment-received",
        "event_key_suffix": "payment_received",
        "client_note_template": (
            "[Workflow {workflow_key}] Payment of {payment_amount} {payment_currency} "
            "received on invoice #{invoice_number}."
        ),
        "client_email_subject_template": (
            "Payment received for invoice #{invoice_number}"
        ),
        "client_email_body_template": (
            "Hi {client_name},\n\nWe've received your payment of "
            "{payment_amount} {payment_currency} on invoice "
            "#{invoice_number}. Thank you."
        ),
        "slack_message_template": (
            ":moneybag: Payment of {payment_amount} {payment_currency} received "
            "on invoice #{invoice_number} from {client_name} "
            "(workflow {workflow_key})."
        ),
    },
    "client_created": {
        "label": "Client is created",
        "description": "Runs once when a new client is added (and not retroactively for clients that pre-date the workflow).",
        "trigger_type": "client_created",
        "conditions": {},
        "notification_event_type": "client_created",
        "default_task_title_template": "Onboard new client {client_name}",
        "task_tag": "client-created",
        "event_key_suffix": "client_created",
        "client_note_template": (
            "[Workflow {workflow_key}] Client record opened — onboarding workflow fired."
        ),
        "client_email_subject_template": "Welcome, {client_name}",
        "client_email_body_template": (
            "Hi {client_name},\n\nYour account has been set up. Please reach "
            "out if you have any questions getting started."
        ),
        "slack_message_template": (
            ":wave: New client {client_name} was added "
            "(workflow {workflow_key})."
        ),
    },
    "expense_created": {
        "label": "Expense is recorded",
        "description": "Runs once when a new expense is recorded (and not retroactively for expenses that pre-date the workflow).",
        "trigger_type": "expense_created",
        "conditions": {},
        "notification_event_type": "expense_created",
        "default_task_title_template": "Review newly recorded expense from {vendor}",
        "task_tag": "expense-created",
        "event_key_suffix": "expense_created",
        "client_note_template": (
            "[Workflow {workflow_key}] Expense from {vendor} ({amount} {currency}) "
            "was recorded."
        ),
        "client_email_subject_template": (
            "Expense recorded: {vendor}"
        ),
        "client_email_body_template": (
            "Hi {client_name},\n\nAn expense of {amount} {currency} from "
            "{vendor} has been recorded against your account."
        ),
        "slack_message_template": (
            ":receipt: Expense {amount} {currency} from {vendor} was recorded "
            "(workflow {workflow_key})."
        ),
    },
    "expense_submitted_for_approval": {
        "label": "Expense is submitted for approval",
        "description": "Runs once when an expense is submitted for approval (one fire per ExpenseApproval row; multi-level approvals fire per level).",
        "trigger_type": "expense_submitted_for_approval",
        "conditions": {},
        "notification_event_type": "expense_submitted_for_approval",
        "default_task_title_template": "Approve expense from {vendor}",
        "task_tag": "expense-approval-pending",
        "event_key_suffix": "submitted_for_approval",
        "client_note_template": (
            "[Workflow {workflow_key}] Expense from {vendor} ({amount} {currency}) "
            "submitted for approval (level {approval_level})."
        ),
        "client_email_subject_template": (
            "Expense from {vendor} submitted for approval"
        ),
        "client_email_body_template": (
            "Hi {client_name},\n\nAn expense of {amount} {currency} from "
            "{vendor} has been submitted for approval (level "
            "{approval_level})."
        ),
        "slack_message_template": (
            ":eyes: Expense {amount} {currency} from {vendor} is awaiting "
            "approval (level {approval_level}, workflow {workflow_key})."
        ),
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
    "add_client_note": {
        "label": "Add a note to the client record",
        "description": (
            "Append an audit-trail note on the affected client. Skipped when the "
            "trigger has no client context (e.g. expenses without a linked client)."
        ),
    },
    "assign_to_specific_user": {
        "label": "Assign to a specific teammate",
        "description": (
            "Override the auto-resolved owner with a specific user. The workflow "
            "must declare the target via ``assigned_user_id`` in its actions dict; "
            "if the target user is missing or inactive at execution time, the "
            "default resolver (creator → admin → any active user) is used instead."
        ),
    },
    "send_client_email": {
        "label": "Send an email to the client",
        "description": (
            "Send a per-trigger email to the affected client via the tenant's "
            "configured email provider. Silently skipped when the trigger has no "
            "client context (e.g. expenses without a linked client), when the "
            "client has no email address, or when the tenant has not configured "
            "an email provider."
        ),
    },
    "send_slack_notification": {
        "label": "Send a Slack notification",
        "description": (
            "POST a per-trigger message to the tenant's Slack incoming webhook. "
            "Silently skipped when the tenant has not configured a "
            "``slack_webhook_config`` Settings row. Plain-text payload only "
            "(no Block Kit); the message template can be customized per trigger."
        ),
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
        assigned_user_id: Optional[int] = None,
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

        if "assign_to_specific_user" in normalized_actions and not assigned_user_id:
            raise ValueError(
                "assign_to_specific_user requires assigned_user_id to be set"
            )

        actions = {
            "send_internal_notification": "send_internal_notification" in normalized_actions,
            "create_internal_task": "create_internal_task" in normalized_actions,
            "add_client_note": "add_client_note" in normalized_actions,
            "assign_to_specific_user": "assign_to_specific_user" in normalized_actions,
            "send_client_email": "send_client_email" in normalized_actions,
            "send_slack_notification": "send_slack_notification" in normalized_actions,
            "assigned_user_id": assigned_user_id,
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
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
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
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_assigned_user(invoice))
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

                    client_note_id = None
                    if workflow.actions and workflow.actions.get("add_client_note", False):
                        note = self._add_client_note(
                            client=client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=SUPPORTED_TRIGGERS["invoice_became_overdue"][
                                "client_note_template"
                            ],
                            note_vars={"invoice_number": invoice.number},
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if workflow.actions and workflow.actions.get("send_client_email", False):
                        client_email_sent = self._send_client_email(
                            client=client,
                            workflow=workflow,
                            subject_template=SUPPORTED_TRIGGERS["invoice_became_overdue"][
                                "client_email_subject_template"
                            ],
                            body_template=SUPPORTED_TRIGGERS["invoice_became_overdue"][
                                "client_email_body_template"
                            ],
                            template_vars={"invoice_number": invoice.number},
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=SUPPORTED_TRIGGERS["invoice_became_overdue"][
                                "slack_message_template"
                            ],
                            template_vars={
                                "invoice_number": invoice.number,
                                "client_name": (client.name if client else "Unknown client"),
                            },
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="invoice",
                        entity_id=str(invoice.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
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
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
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
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_assigned_user(invoice))
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

                    client_note_id = None
                    if workflow.actions and workflow.actions.get("add_client_note", False):
                        note = self._add_client_note(
                            client=client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=trigger_meta["client_note_template"],
                            note_vars={"invoice_number": invoice.number},
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if workflow.actions and workflow.actions.get("send_client_email", False):
                        client_email_sent = self._send_client_email(
                            client=client,
                            workflow=workflow,
                            subject_template=trigger_meta["client_email_subject_template"],
                            body_template=trigger_meta["client_email_body_template"],
                            template_vars={"invoice_number": invoice.number},
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=trigger_meta["slack_message_template"],
                            template_vars={
                                "invoice_number": invoice.number,
                                "client_name": (client.name if client else "Unknown client"),
                            },
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="invoice",
                        entity_id=str(invoice.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
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

    def process_payment_received_workflows(self) -> Dict[str, Any]:
        """Fire `payment_received` workflows for payments not yet processed.

        Considers only payments created on/after the workflow's own
        ``created_at`` so deploying a new workflow doesn't retroactively
        fire for years of pre-existing payments. The execution-log row
        per (workflow, payment) keeps the scan idempotent across reruns.

        Payments without a linked invoice are skipped — the existing
        notification + task templates reference the invoice number, and
        an orphan payment has no actionable owner anyway.
        """
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "payment_received",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        trigger_meta = SUPPORTED_TRIGGERS["payment_received"]

        for workflow in workflows:
            payments = self.db.query(Payment).filter(
                Payment.created_at.isnot(None),
                Payment.created_at >= workflow.created_at,
            ).all()

            for payment in payments:
                stats["processed_count"] += 1
                event_key = f"payment:{payment.id}:{trigger_meta['event_key_suffix']}"

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                invoice = (
                    self.db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
                    if payment.invoice_id is not None
                    else None
                )
                if invoice is None:
                    # No actionable owner without an invoice; skip silently.
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_assigned_user(invoice))
                    if assigned_user is None:
                        raise ValueError(
                            f"No eligible user found to own payment {payment.id} workflow task"
                        )

                    client = self.db.query(Client).filter(Client.id == invoice.client_id).first()
                    details = {
                        "payment_id": payment.id,
                        "payment_amount": payment.amount,
                        "payment_currency": payment.currency,
                        "payment_method": payment.payment_method,
                        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.number,
                        "client_name": client.name if client else None,
                        "amount": invoice.amount,
                        "currency": invoice.currency,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type=trigger_meta["notification_event_type"],
                            user_id=assigned_user.id,
                            resource_type="payment",
                            resource_id=str(payment.id),
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
                                "Payment of {payment_amount} {payment_currency} received "
                                "on invoice #{invoice_number} for {client_name}. "
                                "Acknowledge with the client and reconcile."
                            ),
                            template_vars={
                                "payment_amount": payment.amount,
                                "payment_currency": payment.currency,
                            },
                            extra_metadata={"payment_id": payment.id},
                        )
                        task_id = reminder.id
                        stats["created_task_count"] += 1

                    client_note_id = None
                    if workflow.actions and workflow.actions.get("add_client_note", False):
                        note = self._add_client_note(
                            client=client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=trigger_meta["client_note_template"],
                            note_vars={
                                "invoice_number": invoice.number,
                                "payment_amount": payment.amount,
                                "payment_currency": payment.currency,
                            },
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if workflow.actions and workflow.actions.get("send_client_email", False):
                        client_email_sent = self._send_client_email(
                            client=client,
                            workflow=workflow,
                            subject_template=trigger_meta["client_email_subject_template"],
                            body_template=trigger_meta["client_email_body_template"],
                            template_vars={
                                "invoice_number": invoice.number,
                                "payment_amount": payment.amount,
                                "payment_currency": payment.currency,
                            },
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=trigger_meta["slack_message_template"],
                            template_vars={
                                "invoice_number": invoice.number,
                                "payment_amount": payment.amount,
                                "payment_currency": payment.currency,
                                "client_name": (client.name if client else "Unknown client"),
                            },
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="payment",
                        entity_id=str(payment.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
                    )
                    self.db.add(execution_log)
                    workflow.last_run_at = now
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    error = f"Workflow {workflow.key} failed for payment {payment.id}: {exc}"
                    logger.error(error)
                    stats["errors"].append(error)

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="payment",
                            entity_id=str(payment.id),
                            status="failed",
                            details={
                                "payment_id": payment.id,
                                "invoice_id": invoice.id if invoice else None,
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

    def process_client_created_workflows(self) -> Dict[str, Any]:
        """Fire `client_created` workflows for clients not yet processed.

        Same retroactive guard as the invoice/payment triggers: only
        clients created on/after the workflow's own ``created_at`` are
        considered. The (workflow, client) execution log keeps reruns
        idempotent. Owner resolution uses ``Client.owner_user_id`` with
        the standard admin / any-active-user fallback.
        """
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "client_created",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        trigger_meta = SUPPORTED_TRIGGERS["client_created"]

        for workflow in workflows:
            clients = self.db.query(Client).filter(
                Client.created_at.isnot(None),
                Client.created_at >= workflow.created_at,
            ).all()

            for client in clients:
                stats["processed_count"] += 1
                event_key = f"client:{client.id}:{trigger_meta['event_key_suffix']}"

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_user_for_client(client))
                    if assigned_user is None:
                        raise ValueError(
                            f"No eligible user found to own client {client.id} workflow task"
                        )

                    details = {
                        "client_id": client.id,
                        "client_name": client.name,
                        "client_email": getattr(client, "email", None),
                        "client_stage": getattr(client, "stage", None),
                        "created_at": client.created_at.isoformat() if client.created_at else None,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type=trigger_meta["notification_event_type"],
                            user_id=assigned_user.id,
                            resource_type="client",
                            resource_id=str(client.id),
                            resource_name=client.name,
                            details=details,
                        )
                        stats["notification_count"] += 1

                    task_id = None
                    if workflow.actions and workflow.actions.get("create_internal_task", True):
                        reminder = self._create_internal_task(
                            workflow=workflow,
                            invoice=None,
                            assigned_user=assigned_user,
                            details=details,
                            default_title_template=trigger_meta["default_task_title_template"],
                            task_tag=trigger_meta["task_tag"],
                            description_template=(
                                "New client {client_name} was just added. "
                                "Reach out to introduce yourself and confirm contact details."
                            ),
                            extra_metadata={"client_id": client.id},
                        )
                        task_id = reminder.id
                        stats["created_task_count"] += 1

                    client_note_id = None
                    if workflow.actions and workflow.actions.get("add_client_note", False):
                        # For client_created, the trigger entity *is* the client.
                        note = self._add_client_note(
                            client=client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=trigger_meta["client_note_template"],
                            note_vars={},
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if workflow.actions and workflow.actions.get("send_client_email", False):
                        client_email_sent = self._send_client_email(
                            client=client,
                            workflow=workflow,
                            subject_template=trigger_meta["client_email_subject_template"],
                            body_template=trigger_meta["client_email_body_template"],
                            template_vars={},
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=trigger_meta["slack_message_template"],
                            template_vars={"client_name": client.name or ""},
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="client",
                        entity_id=str(client.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
                    )
                    self.db.add(execution_log)
                    workflow.last_run_at = now
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    error = f"Workflow {workflow.key} failed for client {client.id}: {exc}"
                    logger.error(error)
                    stats["errors"].append(error)

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="client",
                            entity_id=str(client.id),
                            status="failed",
                            details={
                                "client_id": client.id,
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

    def process_expense_created_workflows(self) -> Dict[str, Any]:
        """Fire `expense_created` workflows for expenses not yet processed.

        Same retroactive guard as the other entity-scan triggers: only
        non-deleted expenses with ``created_at >= workflow.created_at`` are
        considered. The (workflow, expense) execution log keeps reruns
        idempotent. Owner resolution prefers ``Expense.created_by_user_id``
        with admin fallback.
        """
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "expense_created",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        trigger_meta = SUPPORTED_TRIGGERS["expense_created"]

        for workflow in workflows:
            expenses = self.db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.created_at.isnot(None),
                Expense.created_at >= workflow.created_at,
            ).all()

            for expense in expenses:
                stats["processed_count"] += 1
                event_key = f"expense:{expense.id}:{trigger_meta['event_key_suffix']}"

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_user_for_expense(expense))
                    if assigned_user is None:
                        raise ValueError(
                            f"No eligible user found to own expense {expense.id} workflow task"
                        )

                    vendor = expense.vendor or "Unknown vendor"
                    details = {
                        "expense_id": expense.id,
                        "vendor": vendor,
                        "category": expense.category,
                        "amount": expense.amount,
                        "currency": expense.currency,
                        "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
                        "created_at": expense.created_at.isoformat() if expense.created_at else None,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type=trigger_meta["notification_event_type"],
                            user_id=assigned_user.id,
                            resource_type="expense",
                            resource_id=str(expense.id),
                            resource_name=vendor,
                            details=details,
                        )
                        stats["notification_count"] += 1

                    task_id = None
                    if workflow.actions and workflow.actions.get("create_internal_task", True):
                        reminder = self._create_internal_task(
                            workflow=workflow,
                            invoice=None,
                            assigned_user=assigned_user,
                            details=details,
                            default_title_template=trigger_meta["default_task_title_template"],
                            task_tag=trigger_meta["task_tag"],
                            description_template=(
                                "New expense from {vendor} in category {category} "
                                "({amount} {currency}) was just recorded. Verify the "
                                "receipt and assign the correct accounting code."
                            ),
                            template_vars={
                                "vendor": vendor,
                                "category": expense.category or "Uncategorized",
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                            },
                            extra_metadata={"expense_id": expense.id},
                        )
                        task_id = reminder.id
                        stats["created_task_count"] += 1

                    expense_client = None
                    if getattr(expense, "client_id", None) is not None:
                        expense_client = (
                            self.db.query(Client).filter(Client.id == expense.client_id).first()
                        )

                    client_note_id = None
                    if (
                        workflow.actions
                        and workflow.actions.get("add_client_note", False)
                        and expense_client is not None
                    ):
                        note = self._add_client_note(
                            client=expense_client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=trigger_meta["client_note_template"],
                            note_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                            },
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if (
                        workflow.actions
                        and workflow.actions.get("send_client_email", False)
                        and expense_client is not None
                    ):
                        client_email_sent = self._send_client_email(
                            client=expense_client,
                            workflow=workflow,
                            subject_template=trigger_meta["client_email_subject_template"],
                            body_template=trigger_meta["client_email_body_template"],
                            template_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                            },
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=trigger_meta["slack_message_template"],
                            template_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                            },
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="expense",
                        entity_id=str(expense.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
                    )
                    self.db.add(execution_log)
                    workflow.last_run_at = now
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    error = f"Workflow {workflow.key} failed for expense {expense.id}: {exc}"
                    logger.error(error)
                    stats["errors"].append(error)

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="expense",
                            entity_id=str(expense.id),
                            status="failed",
                            details={
                                "expense_id": expense.id,
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

    def process_expense_submitted_for_approval_workflows(self) -> Dict[str, Any]:
        """Fire `expense_submitted_for_approval` workflows for new approval rows.

        Status-change semantics, scan-poll implementation: the trigger fires
        once per ``ExpenseApproval`` row (the per-level row is created when
        the expense is submitted). The (workflow, expense_approval_id)
        execution log keeps reruns idempotent across the background tick,
        so a multi-level approval naturally fires once per level as each
        new row appears.

        Retroactive guard uses ``ExpenseApproval.submitted_at`` (when the
        request was created — not ``created_at`` on the row, which is the
        bookkeeping insert time and matches in practice but the trigger is
        a workflow-domain event so we key off the submission timestamp).

        Approvals whose underlying expense was deleted are silently
        skipped — without an expense there's no actionable owner or
        meaningful template payload.
        """
        stats = {
            "processed_count": 0,
            "created_task_count": 0,
            "notification_count": 0,
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        workflows = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.trigger_type == "expense_submitted_for_approval",
            WorkflowDefinition.is_enabled == True,
        ).all()

        if not workflows:
            return stats

        now = datetime.now(timezone.utc)
        trigger_meta = SUPPORTED_TRIGGERS["expense_submitted_for_approval"]

        for workflow in workflows:
            approvals = self.db.query(ExpenseApproval).filter(
                ExpenseApproval.submitted_at.isnot(None),
                ExpenseApproval.submitted_at >= workflow.created_at,
            ).all()

            for approval in approvals:
                stats["processed_count"] += 1
                event_key = (
                    f"expense_approval:{approval.id}:{trigger_meta['event_key_suffix']}"
                )

                if self._has_execution_log(workflow.id, event_key):
                    stats["skipped_count"] += 1
                    continue

                expense = (
                    self.db.query(Expense).filter(Expense.id == approval.expense_id).first()
                    if approval.expense_id is not None
                    else None
                )
                if expense is None or getattr(expense, "is_deleted", False):
                    stats["skipped_count"] += 1
                    continue

                try:
                    assigned_user = self._apply_assignment_override(workflow, self._resolve_user_for_expense_approval(approval))
                    if assigned_user is None:
                        raise ValueError(
                            f"No eligible user found to own approval {approval.id} workflow task"
                        )

                    vendor = expense.vendor or "Unknown vendor"
                    details = {
                        "expense_approval_id": approval.id,
                        "expense_id": expense.id,
                        "vendor": vendor,
                        "category": expense.category,
                        "amount": expense.amount,
                        "currency": expense.currency,
                        "approval_level": approval.approval_level,
                        "is_current_level": approval.is_current_level,
                        "approval_status": approval.status,
                        "submitted_at": approval.submitted_at.isoformat() if approval.submitted_at else None,
                        "workflow_key": workflow.key,
                    }

                    if workflow.actions and workflow.actions.get("send_internal_notification", True):
                        send_notification(
                            db=self.db,
                            event_type=trigger_meta["notification_event_type"],
                            user_id=assigned_user.id,
                            resource_type="expense",
                            resource_id=str(expense.id),
                            resource_name=vendor,
                            details=details,
                        )
                        stats["notification_count"] += 1

                    task_id = None
                    if workflow.actions and workflow.actions.get("create_internal_task", True):
                        reminder = self._create_internal_task(
                            workflow=workflow,
                            invoice=None,
                            assigned_user=assigned_user,
                            details=details,
                            default_title_template=trigger_meta["default_task_title_template"],
                            task_tag=trigger_meta["task_tag"],
                            description_template=(
                                "Expense from {vendor} in category {category} "
                                "({amount} {currency}) is awaiting your approval "
                                "(level {approval_level}). Review and decide."
                            ),
                            template_vars={
                                "vendor": vendor,
                                "category": expense.category or "Uncategorized",
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                                "approval_level": approval.approval_level,
                            },
                            extra_metadata={
                                "expense_id": expense.id,
                                "expense_approval_id": approval.id,
                                "approval_level": approval.approval_level,
                            },
                        )
                        task_id = reminder.id
                        stats["created_task_count"] += 1

                    expense_client = None
                    if getattr(expense, "client_id", None) is not None:
                        expense_client = (
                            self.db.query(Client).filter(Client.id == expense.client_id).first()
                        )

                    client_note_id = None
                    if (
                        workflow.actions
                        and workflow.actions.get("add_client_note", False)
                        and expense_client is not None
                    ):
                        note = self._add_client_note(
                            client=expense_client,
                            workflow=workflow,
                            assigned_user=assigned_user,
                            note_template=trigger_meta["client_note_template"],
                            note_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                                "approval_level": approval.approval_level,
                            },
                        )
                        if note is not None:
                            client_note_id = note.id
                            stats["client_note_count"] += 1

                    client_email_sent = False
                    if (
                        workflow.actions
                        and workflow.actions.get("send_client_email", False)
                        and expense_client is not None
                    ):
                        client_email_sent = self._send_client_email(
                            client=expense_client,
                            workflow=workflow,
                            subject_template=trigger_meta["client_email_subject_template"],
                            body_template=trigger_meta["client_email_body_template"],
                            template_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                                "approval_level": approval.approval_level,
                            },
                        )
                        if client_email_sent:
                            stats["client_email_count"] += 1

                    slack_notification_sent = False
                    if workflow.actions and workflow.actions.get("send_slack_notification", False):
                        slack_notification_sent = self._send_slack_notification(
                            workflow=workflow,
                            message_template=trigger_meta["slack_message_template"],
                            template_vars={
                                "vendor": vendor,
                                "amount": expense.amount if expense.amount is not None else 0,
                                "currency": expense.currency or "USD",
                                "approval_level": approval.approval_level,
                            },
                        )
                        if slack_notification_sent:
                            stats["slack_notification_count"] += 1

                    execution_log = WorkflowExecutionLog(
                        workflow_id=workflow.id,
                        event_key=event_key,
                        entity_type="expense_approval",
                        entity_id=str(approval.id),
                        status="success",
                        details={
                            **details,
                            "task_id": task_id,
                            "client_note_id": client_note_id,
                            "client_email_sent": client_email_sent,
                            "slack_notification_sent": slack_notification_sent,
                            "assigned_user_id": assigned_user.id,
                        },
                    )
                    self.db.add(execution_log)
                    workflow.last_run_at = now
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    error = (
                        f"Workflow {workflow.key} failed for expense approval "
                        f"{approval.id}: {exc}"
                    )
                    logger.error(error)
                    stats["errors"].append(error)

                    try:
                        failed_log = WorkflowExecutionLog(
                            workflow_id=workflow.id,
                            event_key=event_key,
                            entity_type="expense_approval",
                            entity_id=str(approval.id),
                            status="failed",
                            details={
                                "expense_approval_id": approval.id,
                                "expense_id": expense.id if expense else None,
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
            "payment_received": self.process_payment_received_workflows,
            "client_created": self.process_client_created_workflows,
            "expense_created": self.process_expense_created_workflows,
            "expense_submitted_for_approval": self.process_expense_submitted_for_approval_workflows,
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
            "client_note_count": 0,
            "client_email_count": 0,
            "slack_notification_count": 0,
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
            for key in (
                "processed_count",
                "created_task_count",
                "notification_count",
                "client_note_count",
                "client_email_count",
                "slack_notification_count",
                "skipped_count",
            ):
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

        return self._fallback_admin_user()

    def _resolve_user_for_client(self, client: Client) -> Optional[User]:
        """Resolve the responsible user for a client-scoped workflow.

        Mirrors ``_resolve_assigned_user`` but keys off ``Client.owner_user_id``.
        Falls back to the same admin / any-active-user chain so a new tenant
        with no explicit owners still surfaces tasks to someone.
        """
        owner_id = getattr(client, "owner_user_id", None)
        if owner_id:
            user = self.db.query(User).filter(
                User.id == owner_id,
                User.is_active == True,
            ).first()
            if user:
                return user

        return self._fallback_admin_user()

    def _resolve_user_for_expense(self, expense: Expense) -> Optional[User]:
        """Resolve the responsible user for an expense-scoped workflow.

        Uses ``Expense.created_by_user_id`` (legacy rows that pre-date this
        attribution column will fall through to the admin / any-active-user
        fallback so the task still lands on a real owner).
        """
        created_by = getattr(expense, "created_by_user_id", None)
        if created_by:
            user = self.db.query(User).filter(
                User.id == created_by,
                User.is_active == True,
            ).first()
            if user:
                return user

        return self._fallback_admin_user()

    def _resolve_user_for_expense_approval(self, approval: ExpenseApproval) -> Optional[User]:
        """Resolve the responsible user for an expense-approval workflow.

        The approver is the natural owner of "approve this expense" tasks —
        they're the one who has to act. Falls back to the standard admin
        chain if the approver row is missing or the user is inactive
        (rare, but a workflow shouldn't silently fail because of it).
        """
        approver_id = getattr(approval, "approver_id", None)
        if approver_id:
            user = self.db.query(User).filter(
                User.id == approver_id,
                User.is_active == True,
            ).first()
            if user:
                return user

        return self._fallback_admin_user()

    def _fallback_admin_user(self) -> Optional[User]:
        admin_user = self.db.query(User).filter(
            User.role == "admin",
            User.is_active == True,
        ).order_by(User.id.asc()).first()
        if admin_user:
            return admin_user

        return self.db.query(User).filter(User.is_active == True).order_by(User.id.asc()).first()

    def _apply_assignment_override(
        self,
        workflow: WorkflowDefinition,
        default_user: Optional[User],
    ) -> Optional[User]:
        """Honor the ``assign_to_specific_user`` action when it's enabled.

        Wraps every processor's per-entity resolver call. The override is
        applied only when:
          * ``workflow.actions["assign_to_specific_user"]`` is truthy
          * ``workflow.actions["assigned_user_id"]`` resolves to an active user

        Inactive or missing override targets silently fall through to the
        default resolver so a deleted user can't break a long-lived workflow.
        ``create_workflow`` / ``update_workflow`` already reject enabling the
        action without an ``assigned_user_id``, so seeing one here means the
        target was active at edit time but has since been deactivated.
        """
        if not workflow.actions:
            return default_user
        if not workflow.actions.get("assign_to_specific_user"):
            return default_user
        override_id = workflow.actions.get("assigned_user_id")
        if not override_id:
            return default_user

        override_user = self.db.query(User).filter(
            User.id == override_id,
            User.is_active == True,
        ).first()
        if override_user is None:
            logger.warning(
                "Workflow %s assign_to_specific_user target %s is missing or inactive; "
                "falling back to default resolver.",
                workflow.key,
                override_id,
            )
            return default_user
        return override_user

    def _create_internal_task(
        self,
        workflow: WorkflowDefinition,
        invoice: Optional[Invoice],
        assigned_user: User,
        details: Dict[str, Any],
        *,
        default_title_template: str,
        task_tag: str,
        description_template: str,
        template_vars: Optional[Dict[str, Any]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Reminder:
        """Create a Reminder-backed task for a workflow execution.

        ``invoice`` is optional so non-invoice triggers (currently
        ``client_created``; later ``expense_*``) can reuse this helper. When
        an invoice is supplied, ``{invoice_number}`` is added to the default
        format vars and ``invoice_id``/``invoice_number`` are written into
        ``extra_metadata`` automatically; otherwise those keys are omitted.
        """
        now = datetime.now(timezone.utc)
        due_in_days = 1
        if workflow.actions:
            due_in_days = int(workflow.actions.get("task_due_in_days", 1))

        title_template = default_title_template
        if workflow.actions:
            title_template = workflow.actions.get("task_title_template", title_template)

        client_name = details.get("client_name") or "Unknown client"
        # Default vars cover the invoice-only triggers; per-trigger callers can
        # extend (or override) via ``template_vars`` to thread in payment-side
        # context like {payment_amount} / {currency}.
        format_vars: Dict[str, Any] = {"client_name": client_name}
        if invoice is not None:
            format_vars["invoice_number"] = invoice.number
        if template_vars:
            format_vars.update(template_vars)

        metadata: Dict[str, Any] = {
            "workflow_key": workflow.key,
            "workflow_id": workflow.id,
            "task_kind": "internal_follow_up",
        }
        if invoice is not None:
            metadata["invoice_id"] = invoice.id
            metadata["invoice_number"] = invoice.number
        if extra_metadata:
            metadata.update(extra_metadata)

        reminder = Reminder(
            title=title_template.format(**format_vars),
            description=description_template.format(**format_vars),
            due_date=now + timedelta(days=due_in_days),
            status=ReminderStatus.PENDING,
            priority=ReminderPriority.HIGH,
            created_by_id=assigned_user.id,
            assigned_to_id=assigned_user.id,
            tags=["workflow-task", task_tag],
            extra_metadata=metadata,
        )
        self.db.add(reminder)
        self.db.flush()
        return reminder

    def _add_client_note(
        self,
        client: Optional[Client],
        workflow: WorkflowDefinition,
        assigned_user: User,
        note_template: str,
        note_vars: Dict[str, Any],
    ) -> Optional[ClientNote]:
        """Append a workflow-attributed note to the client record.

        Returns the new ``ClientNote`` on success, or ``None`` if there's no
        client to attach to (the action is silently skipped for triggers
        whose entity doesn't have a client association). Attribution
        (``ClientNote.user_id``) is the workflow's resolved assigned user —
        same actor who owns the notification + task — so the note shows up
        in their activity feed and the existing CRM permission checks work
        without modification.
        """
        if client is None:
            return None
        note_text = note_template.format(workflow_key=workflow.key, **note_vars)
        note = ClientNote(
            client_id=client.id,
            user_id=assigned_user.id,
            note=note_text,
        )
        self.db.add(note)
        self.db.flush()
        return note

    def _send_client_email(
        self,
        client: Optional[Client],
        workflow: WorkflowDefinition,
        subject_template: str,
        body_template: str,
        template_vars: Dict[str, Any],
    ) -> bool:
        """Send a per-trigger client email via the configured EmailService.

        Returns ``True`` if the provider accepted the message, ``False`` when
        the action is silently skipped (missing client, missing recipient
        address, missing tenant email-provider config, or malformed config).
        Any exception raised by the provider client itself bubbles up so the
        per-event execution log captures the failure.

        Imports for ``EmailService`` are deferred to call-time so the heavy
        provider SDKs (boto3, azure-communication-email, jinja2) aren't
        pulled in for tenants that never enable this action.
        """
        if client is None:
            return False
        recipient = getattr(client, "email", None)
        if not recipient:
            logger.warning(
                "Workflow %s send_client_email skipped: client %s has no email address",
                workflow.key,
                client.id,
            )
            return False

        from core.models.models_per_tenant import Settings as _Settings

        settings_row = (
            self.db.query(_Settings).filter(_Settings.key == "email_provider_config").first()
        )
        if not settings_row or not settings_row.value:
            logger.warning(
                "Workflow %s send_client_email skipped: email_provider_config not set",
                workflow.key,
            )
            return False

        cfg = settings_row.value
        try:
            from core.services.email_service import (
                EmailMessage,
                EmailProvider,
                EmailProviderConfig,
                EmailService,
            )
        except ImportError as exc:
            logger.warning(
                "Workflow %s send_client_email skipped: EmailService unavailable (%s)",
                workflow.key,
                exc,
            )
            return False

        try:
            provider_config = EmailProviderConfig(
                provider=EmailProvider(cfg["provider"]),
                from_email=cfg.get("from_email"),
                from_name=cfg.get("from_name"),
                aws_access_key_id=cfg.get("aws_access_key_id"),
                aws_secret_access_key=cfg.get("aws_secret_access_key"),
                aws_region=cfg.get("aws_region"),
                azure_connection_string=cfg.get("azure_connection_string"),
                mailgun_api_key=cfg.get("mailgun_api_key"),
                mailgun_domain=cfg.get("mailgun_domain"),
            )
        except (KeyError, ValueError) as exc:
            logger.warning(
                "Workflow %s send_client_email skipped: invalid email_provider_config (%s)",
                workflow.key,
                exc,
            )
            return False

        format_vars: Dict[str, Any] = {
            "workflow_key": workflow.key,
            "client_name": client.name or "",
        }
        format_vars.update(template_vars)

        try:
            subject = subject_template.format(**format_vars)
            body = body_template.format(**format_vars)
        except KeyError as exc:
            logger.warning(
                "Workflow %s send_client_email template missing variable %s; skipped",
                workflow.key,
                exc,
            )
            return False

        message = EmailMessage(
            to_email=recipient,
            to_name=client.name or "",
            subject=subject,
            html_body=body,
            text_body=body,
            from_email=cfg.get("from_email") or "noreply@invoiceapp.com",
            from_name=cfg.get("from_name") or workflow.key,
        )
        return EmailService(provider_config).send_email(message)

    def _send_slack_notification(
        self,
        workflow: WorkflowDefinition,
        message_template: str,
        template_vars: Dict[str, Any],
    ) -> bool:
        """POST a per-trigger plain-text message to the tenant's Slack webhook.

        Returns ``True`` on a 2xx response, ``False`` when the action is
        silently skipped (missing ``slack_webhook_config`` Settings row,
        missing ``webhook_url``, missing template variable, or any network
        error). The non-2xx case is treated as a failure and logged but does
        not raise — the per-event execution log records the boolean so an
        operator can surface failures in the existing executions UI.

        Imports for ``requests`` and the tenant ``Settings`` model are
        deferred to call-time to avoid widening top-level imports for an
        action that not every tenant enables.
        """
        from core.models.models_per_tenant import Settings as _Settings

        settings_row = (
            self.db.query(_Settings).filter(_Settings.key == "slack_webhook_config").first()
        )
        if not settings_row or not settings_row.value:
            logger.warning(
                "Workflow %s send_slack_notification skipped: slack_webhook_config not set",
                workflow.key,
            )
            return False

        cfg = settings_row.value
        webhook_url = cfg.get("webhook_url") or cfg.get("default_webhook_url")
        if not webhook_url:
            logger.warning(
                "Workflow %s send_slack_notification skipped: webhook_url missing in slack_webhook_config",
                workflow.key,
            )
            return False

        format_vars: Dict[str, Any] = {"workflow_key": workflow.key}
        format_vars.update(template_vars)

        try:
            text = message_template.format(**format_vars)
        except KeyError as exc:
            logger.warning(
                "Workflow %s send_slack_notification template missing variable %s; skipped",
                workflow.key,
                exc,
            )
            return False

        try:
            import requests as _requests
        except ImportError as exc:
            logger.warning(
                "Workflow %s send_slack_notification skipped: requests unavailable (%s)",
                workflow.key,
                exc,
            )
            return False

        try:
            response = _requests.post(webhook_url, json={"text": text}, timeout=10)
        except Exception as exc:
            logger.warning(
                "Workflow %s send_slack_notification network error: %s",
                workflow.key,
                exc,
            )
            return False

        if 200 <= response.status_code < 300:
            return True

        logger.warning(
            "Workflow %s send_slack_notification got non-2xx response %s",
            workflow.key,
            response.status_code,
        )
        return False

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

    def duplicate_workflow(self, workflow_id: int) -> WorkflowDefinition:
        """Clone an existing workflow as a fresh user-owned, enabled copy.

        System workflows are intentionally clonable — that's the primary use
        case (start from the built-in overdue follow-up template and edit
        the clone). The new row drops ``is_system`` / ``is_default`` and is
        always created enabled regardless of the source. Execution log rows
        are not copied; the clone starts with no run history.
        """
        source = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == workflow_id
        ).first()
        if not source:
            raise ValueError("Workflow not found")

        new_name = f"{source.name} (copy)"
        clone = WorkflowDefinition(
            name=new_name,
            key=self._build_workflow_key(new_name),
            description=source.description,
            trigger_type=source.trigger_type,
            conditions=dict(source.conditions) if source.conditions else {},
            actions=dict(source.actions) if source.actions else {},
            is_enabled=True,
            is_system=False,
            is_default=False,
        )
        self.db.add(clone)
        self.db.commit()
        self.db.refresh(clone)
        return clone

    def update_workflow(
        self,
        workflow_id: int,
        *,
        name: str,
        description: Optional[str],
        action_ids: list[str],
        assigned_user_id: Optional[int] = None,
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

        if "assign_to_specific_user" in normalized_actions and not assigned_user_id:
            raise ValueError(
                "assign_to_specific_user requires assigned_user_id to be set"
            )

        actions = {
            "send_internal_notification": "send_internal_notification" in normalized_actions,
            "create_internal_task": "create_internal_task" in normalized_actions,
            "add_client_note": "add_client_note" in normalized_actions,
            "assign_to_specific_user": "assign_to_specific_user" in normalized_actions,
            "send_client_email": "send_client_email" in normalized_actions,
            "send_slack_notification": "send_slack_notification" in normalized_actions,
            "assigned_user_id": assigned_user_id,
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

