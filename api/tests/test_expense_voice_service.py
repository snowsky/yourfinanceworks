from datetime import date

from core.services.expense_voice_service import parse_voice_expense_heuristic


def test_parse_voice_expense_heuristic_extracts_amount_vendor_and_category():
    result = parse_voice_expense_heuristic(
        "Spent 18.45 on lunch at Freshii yesterday",
        currency_hint="CAD",
        date_hint=date(2026, 3, 30),
    )

    assert result.amount == 18.45
    assert result.currency == "CAD"
    assert result.category == "Meals"
    assert result.vendor == "Freshii"
    assert result.expense_date == date(2026, 3, 29)
    assert result.parser_used == "heuristic"
    assert result.confidence > 0.5


def test_parse_voice_expense_heuristic_defaults_when_details_are_sparse():
    result = parse_voice_expense_heuristic(
        "Paid for software",
        date_hint=date(2026, 3, 30),
    )

    assert result.amount is None
    assert result.currency == "USD"
    assert result.category == "Software"
    assert result.expense_date == date(2026, 3, 30)
