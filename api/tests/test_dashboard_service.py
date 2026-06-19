"""Unit tests for the server-side dashboard aggregation.

These pin each metric against the original client-side getStats() semantics.
Pure function (no DB), so they run with `--noconftest` locally.
"""

from datetime import datetime, timezone

from core.services.dashboard_service import _aggregate_stats, _js_round

NOW = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _inv(**kw):
    base = dict(
        amount=0.0, paid_amount=0.0, currency="USD", status="draft",
        payer="Client", created_at=NOW, updated_at=NOW, due_date=NOW, client_id=1,
    )
    base.update(kw)
    return base


def test_js_round_is_half_up_not_bankers():
    assert _js_round(2.5) == 3      # Python round(2.5) == 2
    assert _js_round(7.5) == 8
    assert _js_round(0.5) == 1      # Python round(0.5) == 0
    assert _js_round(-1.5) == -1    # toward +inf, like Math.round


def test_income_by_currency_respects_status_and_payer_filter():
    invoices = [
        _inv(status="paid", paid_amount=100, currency="USD", payer="Client"),
        _inv(status="partially_paid", paid_amount=50, currency="USD", payer=""),   # empty payer counts
        _inv(status="paid", paid_amount=70, currency="EUR", payer="client"),       # lowercased
        _inv(status="paid", paid_amount=999, currency="USD", payer="You"),         # payer 'you' excluded
        _inv(status="pending", paid_amount=10, currency="USD", payer="Client"),    # not paid -> excluded
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert out["totalIncome"] == {"USD": 150, "EUR": 70}


def test_pending_by_currency_outstanding_positive_only():
    invoices = [
        _inv(status="pending", amount=100, paid_amount=30, currency="USD"),         # 70
        _inv(status="overdue", amount=40, paid_amount=40, currency="USD"),          # 0 -> excluded
        _inv(status="partially_paid", amount=200, paid_amount=50, currency="EUR"),  # 150
        _inv(status="paid", amount=100, paid_amount=0, currency="USD"),             # paid not pending -> excluded
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert out["pendingInvoices"] == {"USD": 70, "EUR": 150}


def test_expenses_total_amount_or_amount_or_zero_quirk():
    expenses = [
        {"currency": "USD", "total_amount": 80, "amount": 999},    # uses total_amount
        {"currency": "USD", "total_amount": 0, "amount": 20},      # 0 falls through to amount
        {"currency": "USD", "total_amount": None, "amount": 5},    # None -> amount
        {"currency": "EUR", "total_amount": None, "amount": None}, # both falsy -> 0
    ]
    out = _aggregate_stats([], expenses, 0, NOW)
    assert out["totalExpenses"] == {"USD": 105, "EUR": 0}


def test_status_counts():
    invoices = [_inv(status="paid"), _inv(status="paid"), _inv(status="pending"), _inv(status="overdue")]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert (out["invoicesPaid"], out["invoicesPending"], out["invoicesOverdue"]) == (2, 1, 1)


def test_income_trend_current_vs_previous_month():
    may = datetime(2026, 5, 10, tzinfo=timezone.utc)
    jun = datetime(2026, 6, 10, tzinfo=timezone.utc)
    invoices = [
        _inv(status="paid", paid_amount=200, created_at=jun),  # current 200
        _inv(status="paid", paid_amount=100, created_at=may),  # previous 100
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert out["trends"]["income"] == {"value": 100.0, "isPositive": True}


def test_negative_trend_is_not_positive():
    may = datetime(2026, 5, 10, tzinfo=timezone.utc)
    jun = datetime(2026, 6, 10, tzinfo=timezone.utc)
    invoices = [
        _inv(status="paid", paid_amount=50, created_at=jun),
        _inv(status="paid", paid_amount=100, created_at=may),
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert out["trends"]["income"] == {"value": -50.0, "isPositive": False}


def test_previous_zero_guard_yields_100_when_current_positive():
    jun = datetime(2026, 6, 10, tzinfo=timezone.utc)
    out = _aggregate_stats([_inv(status="paid", paid_amount=50, created_at=jun)], [], 0, NOW)
    assert out["trends"]["income"] == {"value": 100.0, "isPositive": True}


def test_monthly_clients_are_distinct():
    jun = datetime(2026, 6, 10, tzinfo=timezone.utc)
    invoices = [
        _inv(created_at=jun, client_id=1),
        _inv(created_at=jun, client_id=1),  # duplicate client
        _inv(created_at=jun, client_id=2),
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    assert out["trends"]["clients"]["value"] == 100.0  # 2 distinct this month, 0 last -> +100


def test_payment_quality_metrics():
    d = lambda day: datetime(2026, 6, day, tzinfo=timezone.utc)
    invoices = [
        _inv(status="paid", created_at=d(1), updated_at=d(6), due_date=d(10)),   # 5 days, on-time
        _inv(status="paid", created_at=d(1), updated_at=d(11), due_date=d(8)),   # 10 days, late
        _inv(status="overdue", created_at=d(1)),
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)
    pt = out["paymentTrends"]
    assert pt["onTimePaymentRate"] == 50          # 1 of 2 paid on-time
    assert pt["averagePaymentTime"] == 8          # ceil(5)+ceil(10)=15, 15/2=7.5 -> _js_round -> 8
    assert pt["overdueRate"] == 33                # 1 of 3 -> 33.33 -> 33


def test_naive_due_date_does_not_crash_on_time_comparison():
    # Regression: DB returns due_date tz-naive (DateTime) but updated_at tz-aware
    # (DateTime(timezone=True)); comparing them raised TypeError for any tenant
    # with paid invoices. _as_utc must normalize both before comparison.
    naive_due = datetime(2026, 6, 20)  # tz-naive, like the column
    aware_paid = datetime(2026, 6, 10, tzinfo=timezone.utc)  # on time (<= due)
    invoices = [
        _inv(status="paid", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
             updated_at=aware_paid, due_date=naive_due),
    ]
    out = _aggregate_stats(invoices, [], 0, NOW)  # must not raise
    assert out["paymentTrends"]["onTimePaymentRate"] == 100


def test_empty_inputs_yield_zeroed_stats():
    out = _aggregate_stats([], [], 0, NOW)
    assert out["totalIncome"] == {} and out["pendingInvoices"] == {} and out["totalExpenses"] == {}
    assert (out["invoicesPaid"], out["invoicesPending"], out["invoicesOverdue"]) == (0, 0, 0)
    assert out["paymentTrends"] == {"onTimePaymentRate": 0, "averagePaymentTime": 0, "overdueRate": 0}
    assert out["trends"]["income"] == {"value": 0, "isPositive": True}
    assert out["totalClients"] == 0
