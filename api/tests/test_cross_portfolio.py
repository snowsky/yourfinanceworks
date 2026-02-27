"""
Cross-Portfolio Analysis Tests

Tests for the cross-portfolio analyzer calculator and service layer.
Uses the existing conftest fixtures (db_session, investment_portfolio_service, etc.)
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

from plugins.investments.services.cross_portfolio_service import CrossPortfolioService
from plugins.investments.calculators.cross_portfolio_analyzer import CrossPortfolioAnalyzer
from plugins.investments.models import (
    AssetClass, SecurityType, PortfolioType, TransactionType
)
from plugins.investments.schemas import (
    PortfolioCreate, HoldingCreate
)

TENANT_ID = 1


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def cross_portfolio_service(db_session):
    return CrossPortfolioService(db_session)


@pytest.fixture
def analyzer():
    return CrossPortfolioAnalyzer()


def _create_portfolio(svc, name, ptype=PortfolioType.TAXABLE):
    return svc.create_portfolio(
        tenant_id=TENANT_ID,
        portfolio_data=PortfolioCreate(name=name, portfolio_type=ptype)
    )


def _create_holding(svc, portfolio_id, symbol, quantity, cost_basis, current_price=None):
    holding = svc.create_holding(
        tenant_id=TENANT_ID,
        portfolio_id=portfolio_id,
        holding_data=HoldingCreate(
            security_symbol=symbol,
            security_name=f"{symbol} Inc.",
            security_type=SecurityType.STOCK,
            asset_class=AssetClass.STOCKS,
            quantity=Decimal(str(quantity)),
            cost_basis=Decimal(str(cost_basis)),
            purchase_date=date.today() - timedelta(days=90),
        )
    )
    if current_price is not None:
        svc.update_price(TENANT_ID, holding.id, Decimal(str(current_price)))
    return holding


# =====================================================================
# Consolidated Holdings Tests
# =====================================================================

def test_consolidated_holdings_combines_same_stock(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """AAPL in two portfolios should be consolidated into one entry."""
    p1 = _create_portfolio(investment_portfolio_service, "Growth")
    p2 = _create_portfolio(investment_portfolio_service, "Retirement")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p2.id, "AAPL", 5, 900, 200)

    result = cross_portfolio_service.get_consolidated_holdings(TENANT_ID)

    assert result["portfolio_count"] == 2
    assert result["total_unique_securities"] == 1

    aapl = result["consolidated_holdings"][0]
    assert aapl["security_symbol"] == "AAPL"
    assert aapl["total_quantity"] == 15.0
    assert aapl["total_cost_basis"] == 2400.0
    assert aapl["total_current_value"] == 3000.0  # 15 * 200
    assert len(aapl["portfolios"]) == 2


def test_consolidated_holdings_multiple_stocks(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Multiple different stocks across portfolios."""
    p1 = _create_portfolio(investment_portfolio_service, "P1")
    p2 = _create_portfolio(investment_portfolio_service, "P2")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p1.id, "MSFT", 5, 1500, 350)
    _create_holding(investment_holdings_service, p2.id, "AAPL", 8, 1200, 200)

    result = cross_portfolio_service.get_consolidated_holdings(TENANT_ID)

    assert result["total_unique_securities"] == 2
    symbols = {h["security_symbol"] for h in result["consolidated_holdings"]}
    assert symbols == {"AAPL", "MSFT"}

    # AAPL should be consolidated from both portfolios
    aapl = next(h for h in result["consolidated_holdings"] if h["security_symbol"] == "AAPL")
    assert aapl["total_quantity"] == 18.0
    assert aapl["portfolio_count"] == 2

    # MSFT only in one portfolio
    msft = next(h for h in result["consolidated_holdings"] if h["security_symbol"] == "MSFT")
    assert msft["portfolio_count"] == 1


# =====================================================================
# Overlap Analysis Tests
# =====================================================================

def test_overlap_detection_finds_shared_stocks(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """AAPL in P1 and P2, MSFT in P2 and P3: two overlapping securities."""
    p1 = _create_portfolio(investment_portfolio_service, "Portfolio A")
    p2 = _create_portfolio(investment_portfolio_service, "Portfolio B")
    p3 = _create_portfolio(investment_portfolio_service, "Portfolio C")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p2.id, "AAPL", 5, 750, 200)
    _create_holding(investment_holdings_service, p2.id, "MSFT", 8, 2400, 350)
    _create_holding(investment_holdings_service, p3.id, "MSFT", 3, 900, 350)
    _create_holding(investment_holdings_service, p3.id, "GOOG", 2, 280, 170)

    result = cross_portfolio_service.get_overlap_analysis(TENANT_ID)

    assert result["total_unique_securities"] == 3
    assert result["overlapping_securities_count"] == 2
    assert result["portfolio_count"] == 3

    overlap_symbols = {d["security_symbol"] for d in result["overlap_details"]}
    assert overlap_symbols == {"AAPL", "MSFT"}


def test_no_overlap_when_all_different(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """No overlap when every portfolio has different stocks."""
    p1 = _create_portfolio(investment_portfolio_service, "P1")
    p2 = _create_portfolio(investment_portfolio_service, "P2")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p2.id, "MSFT", 5, 1500, 350)

    result = cross_portfolio_service.get_overlap_analysis(TENANT_ID)

    assert result["total_unique_securities"] == 2
    assert result["overlapping_securities_count"] == 0
    assert len(result["overlap_details"]) == 0


# =====================================================================
# Stock Comparison Tests
# =====================================================================

def test_compare_stock_across_portfolios(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Compare AAPL bought at different costs in different portfolios."""
    p1 = _create_portfolio(investment_portfolio_service, "Growth")
    p2 = _create_portfolio(investment_portfolio_service, "Value")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)  # cost $150/sh
    _create_holding(investment_holdings_service, p2.id, "AAPL", 20, 3600, 200)  # cost $180/sh

    result = cross_portfolio_service.compare_stock(TENANT_ID, "AAPL")

    assert result["security_symbol"] == "AAPL"
    assert result["found_in_portfolios"] == 2
    assert result["total_quantity"] == 30.0
    assert result["total_cost_basis"] == 5100.0
    assert result["total_current_value"] == 6000.0  # 30 * 200

    # The Growth portfolio should have better gain/loss % than Value
    portfolios = result["portfolios"]
    growth = next(p for p in portfolios if p["portfolio_name"] == "Growth")
    value = next(p for p in portfolios if p["portfolio_name"] == "Value")
    assert growth["gain_loss_pct"] > value["gain_loss_pct"]


def test_compare_stock_not_found(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Stock not held in any portfolio should return zero results."""
    _create_portfolio(investment_portfolio_service, "Empty")

    result = cross_portfolio_service.compare_stock(TENANT_ID, "TSLA")
    assert result["found_in_portfolios"] == 0
    assert result["total_quantity"] == 0


# =====================================================================
# Exposure / Concentration Report Tests
# =====================================================================

def test_exposure_report_percentages_sum_to_100(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Exposure percentages should sum to 100% when there are holdings."""
    p1 = _create_portfolio(investment_portfolio_service, "P1")
    p2 = _create_portfolio(investment_portfolio_service, "P2")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p1.id, "MSFT", 5, 1500, 300)
    _create_holding(investment_holdings_service, p2.id, "GOOG", 3, 450, 170)

    result = cross_portfolio_service.get_exposure_report(TENANT_ID)

    total_pct = sum(e["pct_of_total"] for e in result["exposures"])
    assert abs(total_pct - 100.0) < 0.01  # Allow floating point tolerance

    assert result["securities_count"] == 3
    assert result["total_combined_value"] > 0


def test_exposure_report_warns_on_concentration(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """A stock with >20% exposure should trigger a concentration warning."""
    p1 = _create_portfolio(investment_portfolio_service, "P1")

    # AAPL = $4000, MSFT = $500 => AAPL = 88.9% concentration
    _create_holding(investment_holdings_service, p1.id, "AAPL", 20, 3000, 200)
    _create_holding(investment_holdings_service, p1.id, "MSFT", 1, 300, 500)

    result = cross_portfolio_service.get_exposure_report(TENANT_ID)

    assert result["concentration_warnings_count"] >= 1
    warning_symbols = {w["security_symbol"] for w in result["concentration_warnings"]}
    assert "AAPL" in warning_symbols


# =====================================================================
# Portfolio ID Filtering Tests
# =====================================================================

def test_portfolio_id_filtering(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Filtering by specific portfolio IDs should only include those portfolios."""
    p1 = _create_portfolio(investment_portfolio_service, "P1")
    p2 = _create_portfolio(investment_portfolio_service, "P2")
    p3 = _create_portfolio(investment_portfolio_service, "P3")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p2.id, "MSFT", 5, 1500, 350)
    _create_holding(investment_holdings_service, p3.id, "GOOG", 3, 450, 170)

    # Only include P1 and P2
    result = cross_portfolio_service.get_consolidated_holdings(
        TENANT_ID, portfolio_ids=[p1.id, p2.id]
    )

    assert result["portfolio_count"] == 2
    symbols = {h["security_symbol"] for h in result["consolidated_holdings"]}
    assert "GOOG" not in symbols
    assert "AAPL" in symbols
    assert "MSFT" in symbols


# =====================================================================
# Empty Portfolio Tests
# =====================================================================

def test_empty_portfolios_return_zero_results(
    cross_portfolio_service,
    investment_portfolio_service,
):
    """No portfolios should produce empty results without errors."""
    result = cross_portfolio_service.get_consolidated_holdings(TENANT_ID)
    assert result["portfolio_count"] == 0
    assert result["total_unique_securities"] == 0

    result = cross_portfolio_service.get_overlap_analysis(TENANT_ID)
    assert result["overlapping_securities_count"] == 0


def test_empty_portfolios_no_holdings(
    cross_portfolio_service,
    investment_portfolio_service,
):
    """Portfolios with no holdings should produce empty results."""
    _create_portfolio(investment_portfolio_service, "Empty1")
    _create_portfolio(investment_portfolio_service, "Empty2")

    result = cross_portfolio_service.get_consolidated_holdings(TENANT_ID)
    assert result["portfolio_count"] == 2
    assert result["total_unique_securities"] == 0


# =====================================================================
# Single Portfolio Tests
# =====================================================================

def test_single_portfolio_consolidated(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Single portfolio should still work, just no overlap."""
    p1 = _create_portfolio(investment_portfolio_service, "Solo")
    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)

    result = cross_portfolio_service.get_consolidated_holdings(TENANT_ID)
    assert result["portfolio_count"] == 1
    assert result["total_unique_securities"] == 1

    overlap = cross_portfolio_service.get_overlap_analysis(TENANT_ID)
    assert overlap["overlapping_securities_count"] == 0


# =====================================================================
# Cross-Portfolio Summary Tests
# =====================================================================

def test_cross_portfolio_summary(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Summary endpoint combines consolidation, overlap, and exposure data."""
    p1 = _create_portfolio(investment_portfolio_service, "Alpha")
    p2 = _create_portfolio(investment_portfolio_service, "Beta")

    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)
    _create_holding(investment_holdings_service, p1.id, "MSFT", 5, 1500, 350)
    _create_holding(investment_holdings_service, p2.id, "AAPL", 8, 1200, 200)

    result = cross_portfolio_service.get_cross_portfolio_summary(TENANT_ID)

    assert result["portfolio_count"] == 2
    assert result["total_unique_securities"] == 2
    assert result["total_combined_value"] > 0
    assert result["overlapping_securities_count"] == 1
    assert len(result["top_holdings"]) <= 5


def test_cross_portfolio_summary_empty(
    cross_portfolio_service,
):
    """Summary with no portfolios returns zeroed-out structure."""
    result = cross_portfolio_service.get_cross_portfolio_summary(TENANT_ID)
    assert result["portfolio_count"] == 0
    assert result["total_combined_value"] == 0.0


# =====================================================================
# Monthly Comparison Tests
# =====================================================================

def test_monthly_comparison_basic(
    cross_portfolio_service,
    investment_portfolio_service,
    investment_holdings_service,
):
    """Monthly comparison should return structure with portfolio data and month keys."""
    p1 = _create_portfolio(investment_portfolio_service, "Monthly Test")
    _create_holding(investment_holdings_service, p1.id, "AAPL", 10, 1500, 200)

    result = cross_portfolio_service.get_monthly_comparison(TENANT_ID, months=3)

    assert result["months_analyzed"] == 3
    assert result["portfolio_count"] == 1
    assert len(result["month_keys"]) == 3
    assert len(result["portfolios"]) == 1
    assert result["portfolios"][0]["portfolio_name"] == "Monthly Test"
    assert len(result["aggregate_months"]) == 3
