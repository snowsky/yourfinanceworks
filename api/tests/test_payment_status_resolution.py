"""Unit tests for invoice payment-status resolution.

Targets the regression where deleting the last payment forced an invoice to
"pending", clobbering a prior sent/overdue/approved status. The logic under test
is pure (no DB), so these run without the full app environment.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils.payment_status import resolve_invoice_status


def test_full_payment_marks_paid_and_snapshots_prior_status():
    status, pre = resolve_invoice_status(
        current_status="sent", pre_payment_status=None, total_paid=100.0, amount=100.0
    )
    assert status == "paid"
    assert pre == "sent"


def test_partial_payment_marks_partially_paid_and_snapshots():
    status, pre = resolve_invoice_status(
        current_status="overdue", pre_payment_status=None, total_paid=40.0, amount=100.0
    )
    assert status == "partially_paid"
    assert pre == "overdue"


def test_removing_payments_restores_prior_status_not_pending():
    # The core regression: was reverting to "pending".
    status, pre = resolve_invoice_status(
        current_status="paid", pre_payment_status="sent", total_paid=0.0, amount=100.0
    )
    assert status == "sent"
    assert status != "pending"
    assert pre is None


def test_removing_payments_restores_overdue():
    status, pre = resolve_invoice_status(
        current_status="partially_paid", pre_payment_status="overdue", total_paid=0.0, amount=100.0
    )
    assert status == "overdue"
    assert pre is None


def test_removing_payments_falls_back_to_sent_when_no_snapshot():
    # Legacy invoice paid before the snapshot field existed.
    status, pre = resolve_invoice_status(
        current_status="paid", pre_payment_status=None, total_paid=0.0, amount=100.0
    )
    assert status == "sent"
    assert pre is None


def test_snapshot_not_overwritten_when_already_payment_driven():
    # Going partially_paid -> paid must keep the original snapshot, not capture
    # "partially_paid" as the pre-payment status.
    status, pre = resolve_invoice_status(
        current_status="partially_paid", pre_payment_status="sent", total_paid=100.0, amount=100.0
    )
    assert status == "paid"
    assert pre == "sent"


def test_unpaid_draft_is_left_untouched():
    status, pre = resolve_invoice_status(
        current_status="draft", pre_payment_status=None, total_paid=0.0, amount=100.0
    )
    assert status == "draft"
    assert pre is None


def test_unpaid_overdue_is_left_untouched():
    status, pre = resolve_invoice_status(
        current_status="overdue", pre_payment_status=None, total_paid=0.0, amount=100.0
    )
    assert status == "overdue"
    assert pre is None


def test_overpayment_marks_paid():
    status, pre = resolve_invoice_status(
        current_status="sent", pre_payment_status=None, total_paid=150.0, amount=100.0
    )
    assert status == "paid"
    assert pre == "sent"
