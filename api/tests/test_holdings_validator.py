"""
Unit tests for HoldingsValidator

This module tests the holdings validator service including validation logic,
duplicate detection, and duplicate handling strategies.
"""

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from plugins.investments.services.holdings_validator import (
    HoldingsValidator, DuplicateHandlingMode
)
from plugins.investments.repositories.holdings_repository import HoldingsRepository
from plugins.investments.models import (
    InvestmentPortfolio, InvestmentHolding,
    PortfolioType, SecurityType, AssetClass
)


class TestHoldingsValidator:
    """Test cases for HoldingsValidator"""

    @pytest.fixture
    def holdings_repo(self, db_session):
        """Create a HoldingsRepository instance"""
        return HoldingsRepository(db_session)

    @pytest.fixture
    def validator(self, holdings_repo):
        """Create a HoldingsValidator instance"""
        return HoldingsValidator(holdings_repo, DuplicateHandlingMode.MERGE)

    @pytest.fixture
    def sample_portfolio(self, db_session):
        """Create a sample portfolio for testing"""
        portfolio = InvestmentPortfolio(
            tenant_id=1,
            name="Test Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(portfolio)
        db_session.commit()
        return portfolio

    @pytest.fixture
    def sample_holding(self, db_session, sample_portfolio):
        """Create a sample holding for testing"""
        holding = InvestmentHolding(
            portfolio_id=sample_portfolio.id,
            security_symbol="AAPL",
            security_name="Apple Inc.",
            security_type=SecurityType.STOCK,
            asset_class=AssetClass.STOCKS,
            quantity=Decimal("100"),
            cost_basis=Decimal("15000"),
            purchase_date=date(2023, 1, 15),
            is_closed=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(holding)
        db_session.commit()
        return holding

    # Tests for validate_holding

    def test_validate_holding_valid_data(self, validator):
        """Test validation of valid holding data"""
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks",
            "purchase_date": date(2023, 1, 15)
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is True
        assert error_msg is None

    def test_validate_holding_missing_required_field(self, validator):
        """Test validation fails when required field is missing"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            # Missing cost_basis
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "Missing required fields" in error_msg
        assert "cost_basis" in error_msg

    def test_validate_holding_empty_symbol(self, validator):
        """Test validation fails with empty security symbol"""
        holding_data = {
            "security_symbol": "",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "empty" in error_msg.lower()

    def test_validate_holding_symbol_too_long(self, validator):
        """Test validation fails when symbol exceeds max length"""
        holding_data = {
            "security_symbol": "A" * 21,  # 21 characters, max is 20
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "20 characters" in error_msg

    def test_validate_holding_negative_quantity(self, validator):
        """Test validation fails with negative quantity"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("-100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_validate_holding_zero_quantity(self, validator):
        """Test validation fails with zero quantity"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("0"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_validate_holding_negative_cost_basis(self, validator):
        """Test validation fails with negative cost basis"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("-15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_validate_holding_invalid_quantity_type(self, validator):
        """Test validation fails with invalid quantity type"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": "not_a_number",
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "valid number" in error_msg.lower()

    def test_validate_holding_invalid_security_type(self, validator):
        """Test validation fails with invalid security type"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "invalid_type",
            "asset_class": "stocks"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "Invalid security type" in error_msg

    def test_validate_holding_invalid_asset_class(self, validator):
        """Test validation fails with invalid asset class"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "invalid_class"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "Invalid asset class" in error_msg

    def test_validate_holding_future_purchase_date(self, validator):
        """Test validation fails with future purchase date"""
        future_date = date.today()
        future_date = future_date.replace(year=future_date.year + 1)

        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks",
            "purchase_date": future_date
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is False
        assert "future" in error_msg.lower()

    def test_validate_holding_valid_purchase_date_string(self, validator):
        """Test validation accepts purchase date as ISO string"""
        holding_data = {
            "security_symbol": "AAPL",
            "quantity": Decimal("100"),
            "cost_basis": Decimal("15000"),
            "security_type": "stock",
            "asset_class": "stocks",
            "purchase_date": "2023-01-15"
        }

        is_valid, error_msg = validator.validate_holding(holding_data)

        assert is_valid is True
        assert error_msg is None

    # Tests for detect_duplicate

    def test_detect_duplicate_found(self, validator, sample_portfolio, sample_holding):
        """Test duplicate detection when holding exists"""
        duplicate = validator.detect_duplicate(sample_portfolio.id, "AAPL")

        assert duplicate is not None
        assert duplicate.id == sample_holding.id
        assert duplicate.security_symbol == "AAPL"

    def test_detect_duplicate_not_found(self, validator, sample_portfolio):
        """Test duplicate detection when no holding exists"""
        duplicate = validator.detect_duplicate(sample_portfolio.id, "GOOGL")

        assert duplicate is None

    def test_detect_duplicate_closed_holding_ignored(self, validator, db_session, sample_portfolio, sample_holding):
        """Test duplicate detection ignores closed holdings"""
        # Close the holding
        sample_holding.is_closed = True
        db_session.commit()

        duplicate = validator.detect_duplicate(sample_portfolio.id, "AAPL")

        assert duplicate is None

    # Tests for merge_holdings

    def test_merge_holdings_combines_quantities(self, validator, sample_holding):
        """Test merge combines quantities correctly"""
        new_quantity = Decimal("50")
        new_cost_basis = Decimal("7500")

        result = validator.merge_holdings(sample_holding, new_quantity, new_cost_basis)

        assert result["quantity"] == Decimal("150")  # 100 + 50
        assert result["cost_basis"] == Decimal("22500")  # 15000 + 7500

    def test_merge_holdings_recalculates_average_cost(self, validator, sample_holding):
        """Test merge recalculates average cost per share"""
        new_quantity = Decimal("50")
        new_cost_basis = Decimal("7500")

        result = validator.merge_holdings(sample_holding, new_quantity, new_cost_basis)

        # Average cost = 22500 / 150 = 150
        assert result["average_cost_per_share"] == Decimal("150")

    def test_merge_holdings_with_different_prices(self, validator, sample_holding):
        """Test merge with different purchase prices"""
        # Existing: 100 shares at $150/share = $15000
        # New: 100 shares at $200/share = $20000
        # Merged: 200 shares at $175/share = $35000

        new_quantity = Decimal("100")
        new_cost_basis = Decimal("20000")

        result = validator.merge_holdings(sample_holding, new_quantity, new_cost_basis)

        assert result["quantity"] == Decimal("200")
        assert result["cost_basis"] == Decimal("35000")
        assert result["average_cost_per_share"] == Decimal("175")

    def test_merge_holdings_zero_quantity_result(self, validator, sample_holding):
        """Test merge with zero resulting quantity"""
        # This shouldn't happen in practice, but test edge case
        new_quantity = Decimal("-100")
        new_cost_basis = Decimal("-15000")

        result = validator.merge_holdings(sample_holding, new_quantity, new_cost_basis)

        assert result["quantity"] == Decimal("0")
        assert result["cost_basis"] == Decimal("0")
        assert result["average_cost_per_share"] == Decimal("0")

    # Tests for create_separate_holding

    def test_create_separate_holding_returns_new_data(self, validator, sample_holding):
        """Test create_separate returns new holding data"""
        new_quantity = Decimal("50")
        new_cost_basis = Decimal("7500")

        result = validator.create_separate_holding(sample_holding, new_quantity, new_cost_basis)

        assert result["quantity"] == Decimal("50")
        assert result["cost_basis"] == Decimal("7500")

    def test_create_separate_holding_calculates_average_cost(self, validator, sample_holding):
        """Test create_separate calculates average cost correctly"""
        new_quantity = Decimal("50")
        new_cost_basis = Decimal("7500")

        result = validator.create_separate_holding(sample_holding, new_quantity, new_cost_basis)

        # Average cost = 7500 / 50 = 150
        assert result["average_cost_per_share"] == Decimal("150")

    def test_create_separate_holding_does_not_modify_existing(self, validator, sample_holding):
        """Test create_separate doesn't modify existing holding"""
        original_quantity = sample_holding.quantity
        original_cost = sample_holding.cost_basis

        new_quantity = Decimal("50")
        new_cost_basis = Decimal("7500")

        validator.create_separate_holding(sample_holding, new_quantity, new_cost_basis)

        # Existing holding should be unchanged
        assert sample_holding.quantity == original_quantity
        assert sample_holding.cost_basis == original_cost

    # Tests for handle_duplicate

    def test_handle_duplicate_merge_mode(self, validator, sample_portfolio, sample_holding):
        """Test handle_duplicate with merge mode"""
        validator.set_duplicate_mode(DuplicateHandlingMode.MERGE)

        is_duplicate, action_data = validator.handle_duplicate(
            sample_portfolio.id,
            "AAPL",
            Decimal("50"),
            Decimal("7500")
        )

        assert is_duplicate is True
        assert action_data["quantity"] == Decimal("150")
        assert action_data["cost_basis"] == Decimal("22500")

    def test_handle_duplicate_create_separate_mode(self, validator, sample_portfolio, sample_holding):
        """Test handle_duplicate with create_separate mode"""
        validator.set_duplicate_mode(DuplicateHandlingMode.CREATE_SEPARATE)

        is_duplicate, action_data = validator.handle_duplicate(
            sample_portfolio.id,
            "AAPL",
            Decimal("50"),
            Decimal("7500")
        )

        assert is_duplicate is True
        assert action_data["quantity"] == Decimal("50")
        assert action_data["cost_basis"] == Decimal("7500")

    def test_handle_duplicate_no_duplicate(self, validator, sample_portfolio):
        """Test handle_duplicate when no duplicate exists"""
        is_duplicate, action_data = validator.handle_duplicate(
            sample_portfolio.id,
            "GOOGL",
            Decimal("50"),
            Decimal("7500")
        )

        assert is_duplicate is False
        assert action_data == {}

    # Tests for set_duplicate_mode

    def test_set_duplicate_mode_merge(self, validator):
        """Test setting duplicate mode to merge"""
        validator.set_duplicate_mode(DuplicateHandlingMode.MERGE)
        assert validator.duplicate_mode == DuplicateHandlingMode.MERGE

    def test_set_duplicate_mode_create_separate(self, validator):
        """Test setting duplicate mode to create_separate"""
        validator.set_duplicate_mode(DuplicateHandlingMode.CREATE_SEPARATE)
        assert validator.duplicate_mode == DuplicateHandlingMode.CREATE_SEPARATE

    def test_set_duplicate_mode_invalid(self, validator):
        """Test setting invalid duplicate mode raises error"""
        with pytest.raises(ValueError):
            validator.set_duplicate_mode("invalid_mode")

    # Integration tests

    def test_validate_and_handle_duplicate_workflow(self, validator, sample_portfolio, sample_holding):
        """Test complete workflow: validate then handle duplicate"""
        holding_data = {
            "security_symbol": "AAPL",
            "security_name": "Apple Inc.",
            "quantity": Decimal("50"),
            "cost_basis": Decimal("7500"),
            "security_type": "stock",
            "asset_class": "stocks",
            "purchase_date": date(2023, 6, 15)
        }

        # Validate
        is_valid, error_msg = validator.validate_holding(holding_data)
        assert is_valid is True

        # Handle duplicate
        validator.set_duplicate_mode(DuplicateHandlingMode.MERGE)
        is_duplicate, action_data = validator.handle_duplicate(
            sample_portfolio.id,
            holding_data["security_symbol"],
            holding_data["quantity"],
            holding_data["cost_basis"]
        )

        assert is_duplicate is True
        assert action_data["quantity"] == Decimal("150")

    def test_validate_multiple_holdings(self, validator):
        """Test validating multiple holdings"""
        holdings_data = [
            {
                "security_symbol": "AAPL",
                "quantity": Decimal("100"),
                "cost_basis": Decimal("15000"),
                "security_type": "stock",
                "asset_class": "stocks"
            },
            {
                "security_symbol": "GOOGL",
                "quantity": Decimal("50"),
                "cost_basis": Decimal("7500"),
                "security_type": "stock",
                "asset_class": "stocks"
            },
            {
                "security_symbol": "MSFT",
                "quantity": Decimal("75"),
                "cost_basis": Decimal("22500"),
                "security_type": "stock",
                "asset_class": "stocks"
            }
        ]

        for holding_data in holdings_data:
            is_valid, error_msg = validator.validate_holding(holding_data)
            assert is_valid is True, f"Validation failed for {holding_data['security_symbol']}: {error_msg}"
