from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.models.models import MasterUser
from core.models.database import get_master_db
from core.models.models_per_tenant import (
    Client,
    ClientNote,
    Invoice,
    Payment,
    Reminder,
    ReminderPriority,
    ReminderStatus,
    User,
)
from core.schemas.client_record import ClientTaskCreateRequest
from core.schemas.client import Client as ClientSchema
from core.schemas.client_record import (
    ClientActivityItem,
    ClientRecordResponse,
    ClientRecordSummary,
    ClientTaskItem,
)


class ClientRecordService:
    def __init__(self, db: Session):
        self.db = db

    def get_client_record(self, client_id: int) -> Optional[ClientRecordResponse]:
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            return None

        invoices = self.db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.is_deleted == False,
        ).order_by(Invoice.created_at.desc()).all()

        payments = self.db.query(Payment).join(Invoice, Payment.invoice_id == Invoice.id).filter(
            Invoice.client_id == client_id,
            Invoice.is_deleted == False,
        ).order_by(Payment.payment_date.desc()).all()

        reminders = self.db.query(Reminder).filter(
            Reminder.is_deleted == False
        ).order_by(Reminder.due_date.asc()).all()
        client_reminders = [reminder for reminder in reminders if self._matches_client(reminder.extra_metadata, client_id)]

        notes = self.db.query(ClientNote).options(
            joinedload(ClientNote.user)
        ).filter(
            ClientNote.client_id == client_id
        ).order_by(ClientNote.created_at.desc()).all()

        total_outstanding = sum(
            float(invoice.amount or 0)
            for invoice in invoices
            if invoice.status in ['pending', 'overdue', 'partially_paid']
        )
        overdue_invoices_count = sum(1 for invoice in invoices if invoice.status == 'overdue')
        open_invoices_count = sum(1 for invoice in invoices if invoice.status in ['pending', 'overdue', 'partially_paid'])
        total_paid = sum(float(payment.amount or 0) for payment in payments)
        open_tasks = [reminder for reminder in client_reminders if getattr(reminder.status, "value", reminder.status) != "completed"]
        completed_tasks = [reminder for reminder in client_reminders if getattr(reminder.status, "value", reminder.status) == "completed"]

        summary = ClientRecordSummary(
            open_invoices_count=open_invoices_count,
            overdue_invoices_count=overdue_invoices_count,
            total_outstanding=total_outstanding,
            total_paid=total_paid,
            open_tasks_count=len(open_tasks),
            completed_tasks_count=len(completed_tasks),
            last_payment_at=payments[0].payment_date if payments else None,
            last_invoice_at=invoices[0].created_at if invoices else None,
        )

        recent_activity = self._build_recent_activity(notes=notes, invoices=invoices, payments=payments, reminders=client_reminders)
        open_task_items = [self._to_task_item(reminder) for reminder in open_tasks[:10]]

        client_payload = ClientSchema.model_validate({
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "phone": client.phone,
            "address": client.address,
            "company": client.company,
            "balance": client.balance,
            "paid_amount": total_paid,
            "outstanding_balance": total_outstanding,
            "preferred_currency": client.preferred_currency,
            "labels": client.labels,
            "owner_user_id": client.owner_user_id,
            "stage": client.stage,
            "relationship_status": client.relationship_status,
            "source": client.source,
            "last_contact_at": client.last_contact_at,
            "next_follow_up_at": client.next_follow_up_at,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        })

        return ClientRecordResponse(
            client=client_payload,
            summary=summary,
            recent_activity=recent_activity,
            open_tasks=open_task_items,
        )

    def update_client_record(self, client_id: int, payload: dict[str, Any]) -> Optional[Client]:
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            return None

        if "owner_user_id" in payload and payload["owner_user_id"] is not None:
            owner = self.db.query(User).filter(
                User.id == payload["owner_user_id"],
                User.is_active == True,
            ).first()
            if owner is None:
                raise ValueError("Owner user not found")

        for field, value in payload.items():
            setattr(client, field, value)

        client.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(client)
        return client

    def get_client_tasks(self, client_id: int) -> list[ClientTaskItem]:
        reminders = self.db.query(Reminder).filter(
            Reminder.is_deleted == False
        ).order_by(Reminder.due_date.asc()).all()
        client_reminders = [reminder for reminder in reminders if self._matches_client(reminder.extra_metadata, client_id)]
        return [self._to_task_item(reminder) for reminder in client_reminders]

    def create_client_task(
        self,
        *,
        client_id: int,
        task_data: ClientTaskCreateRequest,
        current_user: MasterUser,
    ) -> ClientTaskItem:
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            raise ValueError("Client not found")

        self._ensure_tenant_user(task_data.assigned_to_id)

        max_pos = self.db.query(func.max(Reminder.position)).filter(
            Reminder.assigned_to_id == task_data.assigned_to_id,
            Reminder.is_deleted == False
        ).scalar() or 0

        priority = self._parse_priority(task_data.priority)

        reminder = Reminder(
            title=task_data.title,
            description=task_data.description,
            due_date=task_data.due_date,
            status=ReminderStatus.PENDING,
            priority=priority,
            created_by_id=current_user.id,
            assigned_to_id=task_data.assigned_to_id,
            position=max_pos + 1,
            is_pinned=False,
            tags=["client-task"],
            extra_metadata={
                "client_id": client_id,
                "task_kind": "follow_up",
                "task_origin": "manual",
            },
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return self._to_task_item(reminder)

    def _build_recent_activity(
        self,
        *,
        notes: list[ClientNote],
        invoices: list[Invoice],
        payments: list[Payment],
        reminders: list[Reminder],
    ) -> list[ClientActivityItem]:
        items: list[ClientActivityItem] = []

        for note in notes[:10]:
            actor_name = None
            if note.user:
                actor_name = self._display_name(note.user)
            items.append(
                ClientActivityItem(
                    type="note_created",
                    timestamp=note.created_at,
                    title="Note added",
                    description=note.note,
                    actor_name=actor_name,
                    entity_type="note",
                    entity_id=str(note.id),
                    metadata={"client_id": note.client_id},
                )
            )

        for invoice in invoices[:10]:
            items.append(
                ClientActivityItem(
                    type="invoice_created",
                    timestamp=invoice.created_at,
                    title=f"Invoice #{invoice.number} created",
                    description=f"Status: {invoice.status}",
                    actor_name=self._display_name(invoice.created_by) if invoice.created_by else None,
                    entity_type="invoice",
                    entity_id=str(invoice.id),
                    metadata={
                        "amount": invoice.amount,
                        "currency": invoice.currency,
                        "status": invoice.status,
                    },
                )
            )

            if invoice.status == "overdue":
                overdue_timestamp = self._coerce_datetime(invoice.updated_at or invoice.created_at)
                items.append(
                    ClientActivityItem(
                        type="invoice_overdue",
                        timestamp=overdue_timestamp,
                        title=f"Invoice #{invoice.number} is overdue",
                        description=f"Amount due: {invoice.amount} {invoice.currency}",
                        actor_name=None,
                        entity_type="invoice",
                        entity_id=str(invoice.id),
                        metadata={"status": invoice.status},
                    )
                )

        for payment in payments[:10]:
            items.append(
                ClientActivityItem(
                    type="payment_received",
                    timestamp=payment.payment_date,
                    title="Payment received",
                    description=f"{payment.amount} {payment.currency}",
                    actor_name=self._display_name(payment.user) if payment.user else None,
                    entity_type="payment",
                    entity_id=str(payment.id),
                    metadata={
                        "invoice_id": payment.invoice_id,
                        "payment_method": payment.payment_method,
                    },
                )
            )

        for reminder in reminders[:10]:
            reminder_status = getattr(reminder.status, "value", reminder.status)
            activity_type = "task_completed" if reminder_status == "completed" else "task_created"
            items.append(
                ClientActivityItem(
                    type=activity_type,
                    timestamp=reminder.completed_at or reminder.created_at,
                    title=reminder.title,
                    description=reminder.description,
                    actor_name=self._display_name(reminder.assigned_to) if reminder.assigned_to else None,
                    entity_type="task",
                    entity_id=str(reminder.id),
                    metadata=reminder.extra_metadata,
                )
            )

        items.sort(key=lambda item: item.timestamp, reverse=True)
        return items[:20]

    def _to_task_item(self, reminder: Reminder) -> ClientTaskItem:
        metadata = reminder.extra_metadata or {}
        status = getattr(reminder.status, "value", reminder.status)
        priority = getattr(reminder.priority, "value", reminder.priority)
        return ClientTaskItem(
            id=reminder.id,
            title=reminder.title,
            description=reminder.description,
            due_date=reminder.due_date,
            status=status,
            priority=priority,
            assigned_to_id=reminder.assigned_to_id,
            task_origin=metadata.get("task_origin"),
            workflow_id=metadata.get("workflow_id"),
        )

    def _ensure_tenant_user(self, user_id: int) -> User:
        tenant_user = self.db.query(User).filter(User.id == user_id).first()
        if tenant_user:
            return tenant_user

        master_db = next(get_master_db())
        try:
            master_user = master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
            if master_user is None:
                raise ValueError("Assigned user not found")

            tenant_user = User(
                id=master_user.id,
                email=master_user.email,
                first_name=master_user.first_name,
                last_name=master_user.last_name,
                hashed_password=master_user.hashed_password,
                role=master_user.role,
                is_active=True,
            )
            self.db.add(tenant_user)
            self.db.flush()
            return tenant_user
        finally:
            master_db.close()

    def _matches_client(self, metadata: Any, client_id: int) -> bool:
        if not isinstance(metadata, dict):
            return False
        try:
            return int(metadata.get("client_id")) == client_id
        except (TypeError, ValueError):
            return False

    def _display_name(self, user: User) -> str:
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.first_name or user.last_name or user.email

    def _coerce_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _parse_priority(self, value: str) -> ReminderPriority:
        normalized = (value or "medium").lower()
        mapping = {
            "low": ReminderPriority.LOW,
            "medium": ReminderPriority.MEDIUM,
            "high": ReminderPriority.HIGH,
            "urgent": ReminderPriority.URGENT,
        }
        if normalized not in mapping:
            raise ValueError("Invalid task priority")
        return mapping[normalized]
