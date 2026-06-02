"""Unit tests for Decimal-based money helpers.

Regression coverage for float accumulation error in rollup/expense totals: summing many
amounts with binary floats drifts (0.1 + 0.2 -> 0.30000000000000004), and that total is
persisted to Expense.amount. sum_money/round_money accumulate in Decimal and round to cents.

Pure-function tests: no DB / heavy imports.
"""

import pytest

from core.utils.money import (
    round_money,
    sum_money,
    line_amount,
    subtotal_from_items,
    compute_discount,
    invoice_total,
)


@pytest.mark.unit
class TestRoundMoney:
    def test_none_is_zero(self):
        assert round_money(None) == 0.0

    def test_rounds_to_two_dp_half_up(self):
        assert round_money(1.005) == 1.01
        assert round_money(1.004) == 1.0

    def test_accepts_string(self):
        assert round_money("45.67") == 45.67


@pytest.mark.unit
class TestSumMoney:
    def test_classic_float_drift_is_eliminated(self):
        assert sum_money([0.1, 0.2]) == 0.30
        assert sum_money([0.99, 0.99, 0.99]) == 2.97

    def test_empty_is_zero(self):
        assert sum_money([]) == 0.0

    def test_skips_none(self):
        assert sum_money([1.50, None, 2.50]) == 4.0

    def test_many_small_amounts(self):
        # 100 x 0.01 must be exactly 1.00, not 0.9999999999999999
        assert sum_money([0.01] * 100) == 1.0

    def test_result_is_float(self):
        assert isinstance(sum_money([1.0, 2.0]), float)


@pytest.mark.unit
class TestInvoiceTotals:
    def test_line_amount(self):
        assert line_amount(3, 19.99) == 59.97
        assert line_amount(2.5, 4) == 10.0

    def test_subtotal_sums_rounded_lines(self):
        assert subtotal_from_items([(3, 19.99), (1, 0.01)]) == 59.98

    def test_subtotal_no_float_drift(self):
        assert subtotal_from_items([(1, 0.1), (1, 0.2)]) == 0.30

    def test_percentage_discount(self):
        assert compute_discount(100.0, "percentage", 10) == 10.0
        assert compute_discount(59.97, "percentage", 12.5) == 7.50

    def test_fixed_discount(self):
        assert compute_discount(100.0, "fixed", 15) == 15.0

    def test_discount_capped_at_subtotal(self):
        assert compute_discount(20.0, "fixed", 50) == 20.0

    def test_zero_or_negative_discount(self):
        assert compute_discount(100.0, "percentage", 0) == 0.0
        assert compute_discount(100.0, "fixed", -5) == 0.0

    def test_invoice_total(self):
        assert invoice_total(100.0, "percentage", 10) == 90.0
        assert invoice_total(100.0, "fixed", 25) == 75.0

    def test_invoice_total_floored_at_zero(self):
        assert invoice_total(10.0, "fixed", 50) == 0.0

    def test_result_is_float(self):
        assert isinstance(invoice_total(100.0, "percentage", 10), float)
        assert isinstance(line_amount(1, 2), float)
