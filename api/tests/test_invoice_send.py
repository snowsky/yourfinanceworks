"""Tests for invoice send helpers (status transition + copy-to-sender BCC)."""

import pytest

from core.services.invoice_send import resolve_send_bcc, status_after_send


@pytest.mark.parametrize("current", ["draft", "approved"])
def test_status_advances_pre_send_to_sent(current):
    assert status_after_send(current) == "sent"


@pytest.mark.parametrize(
    "current",
    ["sent", "paid", "partially_paid", "overdue", "cancelled", "pending_approval", "rejected"],
)
def test_status_unchanged_for_non_pre_send(current):
    assert status_after_send(current) == current


def test_resolve_send_bcc_on_with_address():
    assert resolve_send_bcc(True, "owner@acme.com") == ["owner@acme.com"]


def test_resolve_send_bcc_off():
    assert resolve_send_bcc(False, "owner@acme.com") == []


@pytest.mark.parametrize("addr", [None, "", "   "])
def test_resolve_send_bcc_no_address(addr):
    assert resolve_send_bcc(True, addr) == []
