"""Onboarding sample-data seeding.

Seeds a small, status-diverse set of demo clients/invoices/expenses (marked
``is_sample``) so a brand-new tenant's first session shows populated dashboards.
Everything is removable in one call; real data is never touched.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Client, Expense, Invoice, Payment

logger = logging.getLogger(__name__)


class SampleDataError(Exception):
    """Raised when sample data cannot be seeded (tenant not clean)."""


class SampleDataService:
    def __init__(self, db: Session):
        self.db = db

    # --- queries -----------------------------------------------------------

    def _has_real_data(self) -> bool:
        if self.db.query(Client).filter(Client.is_sample == False).count():  # noqa: E712
            return True
        return bool(
            self.db.query(Invoice)
            .filter(Invoice.is_sample == False, Invoice.is_deleted == False)  # noqa: E712
            .count()
        )

    def _has_sample_data(self) -> bool:
        return bool(
            self.db.query(Client).filter(Client.is_sample == True).count()  # noqa: E712
            or self.db.query(Invoice)
            .filter(Invoice.is_sample == True, Invoice.is_deleted == False)  # noqa: E712
            .count()
            or self.db.query(Expense)
            .filter(Expense.is_sample == True, Expense.is_deleted == False)  # noqa: E712
            .count()
        )

    def sample_data_status(self) -> Dict[str, bool]:
        has_any = bool(
            self.db.query(Client).count()
            or self.db.query(Invoice).filter(Invoice.is_deleted == False).count()  # noqa: E712
        )
        return {"has_sample_data": self._has_sample_data(), "has_any_data": has_any}

    # --- seed --------------------------------------------------------------

    def seed(self, user_id: Optional[int]) -> Dict[str, int]:
        if self._has_real_data():
            raise SampleDataError("Sample data can only be loaded into an empty workspace.")
        if self._has_sample_data():
            raise SampleDataError("Sample data already loaded.")

        now = datetime.now(timezone.utc)

        clients = [
            Client(name="Northwind Traders", email="ap@northwind.example", is_sample=True),
            Client(name="Acme Studio", email="billing@acmestudio.example", is_sample=True),
            Client(name="Riverside Cafe", email="owner@riverside.example", is_sample=True),
        ]
        self.db.add_all(clients)
        self.db.flush()

        # (status, due_offset_days, amount, paid_amount)
        specs = [
            ("draft", 14, 1200.0, 0.0),
            ("sent", 10, 850.0, 0.0),
            ("sent", 3, 450.0, 0.0),
            ("overdue", -20, 2000.0, 0.0),
            ("partially_paid", 7, 1500.0, 600.0),
            ("paid", -5, 700.0, 700.0),
        ]
        invoices = []
        for i, (status, due_off, amount, _paid) in enumerate(specs, start=1):
            inv = Invoice(
                number=f"SAMPLE-{i:04d}",
                amount=amount,
                subtotal=amount,
                currency="USD",
                due_date=now + timedelta(days=due_off),
                status=status,
                client_id=clients[i % len(clients)].id,
                created_by_user_id=user_id,
                is_sample=True,
            )
            invoices.append(inv)
        self.db.add_all(invoices)
        self.db.flush()

        payments = []
        for inv, (status, _d, amount, paid) in zip(invoices, specs):
            if paid > 0:
                payments.append(Payment(
                    invoice_id=inv.id, amount=paid, currency="USD",
                    payment_date=now - timedelta(days=2), payment_method="card",
                    user_id=user_id,
                ))
        self.db.add_all(payments)

        expenses = [
            Expense(category="Office Supplies", currency="USD", amount=120.0,
                    expense_date=now - timedelta(days=4), status="recorded",
                    vendor="Staples", user_id=user_id, is_sample=True),
            Expense(category="Software", currency="USD", amount=49.0,
                    expense_date=now - timedelta(days=9), status="recorded",
                    vendor="Figma", user_id=user_id, is_sample=True),
            Expense(category="Travel", currency="USD", amount=320.0,
                    expense_date=now - timedelta(days=15), status="recorded",
                    vendor="Delta", user_id=user_id, is_sample=True),
            Expense(category="Meals", currency="USD", amount=64.0,
                    expense_date=now - timedelta(days=2), status="recorded",
                    vendor="Bistro", user_id=user_id, is_sample=True),
        ]
        self.db.add_all(expenses)
        self.db.commit()

        return {"clients": len(clients), "invoices": len(invoices),
                "expenses": len(expenses), "payments": len(payments)}

    # --- clear -------------------------------------------------------------

    def clear(self) -> Dict[str, int]:
        sample_invoice_ids = [
            row[0] for row in
            self.db.query(Invoice.id).filter(Invoice.is_sample == True).all()  # noqa: E712
        ]
        payments = 0
        if sample_invoice_ids:
            payments = (
                self.db.query(Payment)
                .filter(Payment.invoice_id.in_(sample_invoice_ids))
                .delete(synchronize_session=False)
            )
        invoices = (
            self.db.query(Invoice).filter(Invoice.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        expenses = (
            self.db.query(Expense).filter(Expense.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        clients = (
            self.db.query(Client).filter(Client.is_sample == True)  # noqa: E712
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return {"clients": clients, "invoices": invoices,
                "expenses": expenses, "payments": payments}
