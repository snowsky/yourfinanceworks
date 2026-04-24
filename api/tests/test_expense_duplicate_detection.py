from types import SimpleNamespace

from core.routers.expenses._shared import _is_expense_duplicate_detection_eligible


def test_attachment_ocr_failure_is_not_duplicate_eligible():
    expense = SimpleNamespace(
        amount=0,
        imported_from_attachment=True,
        analysis_status="failed",
    )

    assert _is_expense_duplicate_detection_eligible(expense) is False


def test_attachment_pending_ocr_is_not_duplicate_eligible_even_with_amount():
    expense = SimpleNamespace(
        amount=42.5,
        imported_from_attachment=True,
        analysis_status="processing",
    )

    assert _is_expense_duplicate_detection_eligible(expense) is False


def test_completed_ocr_expense_with_amount_is_duplicate_eligible():
    expense = SimpleNamespace(
        amount=42.5,
        imported_from_attachment=True,
        analysis_status="done",
    )

    assert _is_expense_duplicate_detection_eligible(expense) is True


def test_zero_amount_expense_is_not_duplicate_eligible():
    expense = SimpleNamespace(
        amount=0,
        imported_from_attachment=False,
        analysis_status="not_started",
    )

    assert _is_expense_duplicate_detection_eligible(expense) is False
