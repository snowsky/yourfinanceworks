"""Tests for the invoice approval-before-send policy helpers.

The policy lives in the ``invoice_settings`` blob and is inert unless the
commercial ``approvals`` feature is enabled. ``feature_enabled`` is the seam we
monkeypatch (mirroring test_invoice_dunning.py) so no real feature config is hit.
"""

from types import SimpleNamespace

import pytest

from core.models.models_per_tenant import Settings
from core.services import invoice_approval_policy as mod
from core.services.invoice_approval_policy import (
    invoice_requires_approval,
    send_blocked_by_approval,
    validate_approval_threshold,
)


@pytest.fixture
def approvals_on(monkeypatch):
    monkeypatch.setattr(mod, "feature_enabled", lambda fid, db: True)


def _policy(db, *, enabled=True, threshold=0):
    db.add(Settings(key="invoice_settings", value={
        "require_approval_before_send": enabled,
        "approval_threshold_amount": threshold,
    }))
    db.commit()


def _invoice(amount=100.0, status="draft"):
    return SimpleNamespace(amount=amount, status=status)


def test_inert_when_feature_disabled(db_session, monkeypatch):
    monkeypatch.setattr(mod, "feature_enabled", lambda fid, db: False)
    _policy(db_session, enabled=True, threshold=0)
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_false_when_policy_off(db_session, approvals_on):
    _policy(db_session, enabled=False)
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_false_when_no_settings_row(db_session, approvals_on):
    assert invoice_requires_approval(db_session, _invoice()) is False


def test_true_when_policy_on_threshold_zero(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=0)
    assert invoice_requires_approval(db_session, _invoice(amount=5.0)) is True


def test_threshold_boundary(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=100)
    assert invoice_requires_approval(db_session, _invoice(amount=99.99)) is False
    assert invoice_requires_approval(db_session, _invoice(amount=100.0)) is True
    assert invoice_requires_approval(db_session, _invoice(amount=250.0)) is True


def test_send_blocked_only_for_unapproved_statuses(db_session, approvals_on):
    _policy(db_session, enabled=True, threshold=0)
    for status in ("draft", "pending_approval", "rejected"):
        assert send_blocked_by_approval(db_session, _invoice(status=status)) is True
    for status in ("approved", "sent", "paid", "partially_paid", "overdue", "cancelled"):
        assert send_blocked_by_approval(db_session, _invoice(status=status)) is False


def test_send_not_blocked_when_policy_off(db_session, approvals_on):
    _policy(db_session, enabled=False)
    assert send_blocked_by_approval(db_session, _invoice(status="draft")) is False


def test_validate_approval_threshold_accepts_valid():
    validate_approval_threshold({})  # absent -> ok
    validate_approval_threshold({"approval_threshold_amount": 0})
    validate_approval_threshold({"approval_threshold_amount": 1500})
    validate_approval_threshold({"approval_threshold_amount": 12.5})


@pytest.mark.parametrize("bad", [-1, -0.01, "abc", None, True, False])
def test_validate_approval_threshold_rejects(bad):
    with pytest.raises(ValueError):
        validate_approval_threshold({"approval_threshold_amount": bad})


def test_corrupted_threshold_falls_back_to_all_invoices(db_session, approvals_on):
    db_session.add(Settings(key="invoice_settings", value={
        "require_approval_before_send": True,
        "approval_threshold_amount": "not-a-number",
    }))
    db_session.commit()
    assert invoice_requires_approval(db_session, _invoice(amount=1.0)) is True


def test_defaults_present_in_router_defaults():
    # The GET /settings default dict must carry the two new keys so the UI and
    # the policy helper see a defined shape for never-configured tenants.
    import inspect
    from core.routers import settings as settings_router

    src = inspect.getsource(settings_router)
    assert '"require_approval_before_send": False' in src
    assert '"approval_threshold_amount": 0' in src
