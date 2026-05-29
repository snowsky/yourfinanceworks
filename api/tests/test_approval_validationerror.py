"""Tests for the dual-form ApprovalException ValidationError.

approval_service raises ValidationError with a single message string, while
approval_validation_service raises it with structured (field, value, reason)
arguments. Both call styles must work; the single-message form previously
raised TypeError (missing positional args), turning validation failures into
500s.
"""

import pytest

from core.exceptions.approval_exceptions import ValidationError


@pytest.mark.unit
def test_validation_error_single_message_form():
    err = ValidationError("You cannot submit an expense for approval to yourself")
    assert err.user_message == "You cannot submit an expense for approval to yourself"
    assert err.message == "You cannot submit an expense for approval to yourself"
    assert err.error_code == "APPROVAL_VALIDATION_ERROR"
    assert err.details == {}


@pytest.mark.unit
def test_validation_error_structured_form():
    err = ValidationError("amount", 0, "must be greater than 0")
    assert err.details["field"] == "amount"
    assert err.details["value"] == 0
    assert err.details["reason"] == "must be greater than 0"
    assert err.user_message == "Invalid amount: must be greater than 0"
    assert "amount" in err.message and "must be greater than 0" in err.message


@pytest.mark.unit
def test_validation_error_structured_form_with_extra_details():
    err = ValidationError("approver_id", 7, "not found", details={"tenant": 3})
    assert err.details["tenant"] == 3
    assert err.details["field"] == "approver_id"


@pytest.mark.unit
def test_validation_error_is_raisable_and_catchable_single_arg():
    with pytest.raises(ValidationError, match="Rejection reason is required"):
        raise ValidationError("Rejection reason is required")
