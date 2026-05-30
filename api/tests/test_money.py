"""Unit tests for Decimal-based money helpers.

Regression coverage for float accumulation error in rollup/expense totals: summing many
amounts with binary floats drifts (0.1 + 0.2 -> 0.30000000000000004), and that total is
persisted to Expense.amount. sum_money/round_money accumulate in Decimal and round to cents.

Pure-function tests: no DB / heavy imports.
"""

import pytest

from core.utils.money import round_money, sum_money


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
