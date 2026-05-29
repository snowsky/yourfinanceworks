"""Tests for mobile-app per-user expense scoping helpers."""

from types import SimpleNamespace

import pytest

from core.routers.expenses._shared import (
    MOBILE_EXPENSE_APP_HEADER,
    is_mobile_expense_request,
    user_owns_expense,
)


@pytest.mark.unit
def test_is_mobile_expense_request_true_when_header_present():
    request = SimpleNamespace(headers={MOBILE_EXPENSE_APP_HEADER: "app-123"})
    assert is_mobile_expense_request(request) is True


@pytest.mark.unit
def test_is_mobile_expense_request_false_without_header():
    request = SimpleNamespace(headers={})
    assert is_mobile_expense_request(request) is False


@pytest.mark.unit
def test_is_mobile_expense_request_false_when_request_none():
    assert is_mobile_expense_request(None) is False


@pytest.mark.unit
def test_user_owns_expense_by_creator():
    expense = SimpleNamespace(created_by_user_id=7, user_id=99)
    assert user_owns_expense(expense, 7) is True
    assert user_owns_expense(expense, 8) is False


@pytest.mark.unit
def test_user_owns_expense_legacy_fallback_to_user_id():
    # Legacy expenses without created_by_user_id fall back to user_id ownership.
    expense = SimpleNamespace(created_by_user_id=None, user_id=42)
    assert user_owns_expense(expense, 42) is True
    assert user_owns_expense(expense, 7) is False


@pytest.mark.unit
def test_user_owns_expense_creator_takes_precedence_over_user_id():
    # When created_by_user_id is set, user_id is not consulted.
    expense = SimpleNamespace(created_by_user_id=7, user_id=42)
    assert user_owns_expense(expense, 42) is False
