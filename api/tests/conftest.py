"""
Pytest configuration and fixtures for inventory and investment testing
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import Mock

from core.models.models_per_tenant import Base as TenantBase
from core.models.models import Base as MasterBase
from core.models.analytics import Base as AnalyticsBase
from core.models.gamification import Base as GamificationBase
from main import app

# Import all models to ensure they're registered with their respective Bases
try:
    import core.models.models
    import core.models.models_per_tenant
    import core.models.analytics
    import core.models.gamification
    from plugins.investments.models import (
        InvestmentPortfolio, InvestmentHolding, InvestmentTransaction,
        InvestmentAccount, FileAttachment,
        PortfolioType, SecurityType, AssetClass, TransactionType, DividendType
    )
    INVESTMENT_MODELS_AVAILABLE = True
except ImportError:
    INVESTMENT_MODELS_AVAILABLE = False

# Register commercial subscription model on TenantBase.metadata so
# create_all() picks up the detected_subscriptions table for tests.
try:
    import commercial.subscriptions.models  # noqa: F401
except ImportError:
    pass

# Postgres test configuration
POSTGRES_BASE_URL = "postgresql://postgres:password@postgres-master:5432/postgres"
TEST_DB_NAME = "invoice_test"
SQLALCHEMY_DATABASE_URL = f"postgresql://postgres:password@postgres-master:5432/{TEST_DB_NAME}"

# Create the test database if it doesn't exist
def setup_test_db():
    engine = create_engine(POSTGRES_BASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        # Terminate other connections if any (unlikely for test_db which we control)
        conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()"))
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    engine.dispose()

setup_test_db()

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Monkeypatch to ensure middleware uses testing DB
import core.models.database
core.models.database.SessionLocal = TestingSessionLocal
core.models.database.engine = engine

# Create all tables - TenantBase first to win on common table names (like 'users')
TenantBase.metadata.create_all(bind=engine)
MasterBase.metadata.create_all(bind=engine)
AnalyticsBase.metadata.create_all(bind=engine)
GamificationBase.metadata.create_all(bind=engine)

# Seed default tenant for tests
db = TestingSessionLocal()
from core.models.models import Tenant
if not db.query(Tenant).filter(Tenant.id == 1).first():
    tenant = Tenant(id=1, name="Default Tenant", is_active=True)
    db.add(tenant)
    db.commit()

# Seed supported currencies
from core.models.models_per_tenant import SupportedCurrency
if not db.query(SupportedCurrency).filter(SupportedCurrency.code == "USD").first():
    usd = SupportedCurrency(
        code="USD",
        name="US Dollar",
        symbol="$",
        decimal_places=2,
        is_active=True
    )
    db.add(usd)
    db.commit()
db.close()

# Mock TenantDatabaseManager to use the testing session
from core.services.tenant_database_manager import tenant_db_manager
tenant_db_manager.create_tenant_database = Mock(return_value=True)
tenant_db_manager.get_tenant_session = Mock(return_value=TestingSessionLocal)
tenant_db_manager.get_existing_tenant_ids = Mock(return_value=[1])

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def create_test_client():
    from core.models.database import get_db, get_master_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_master_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def client():
    """Create FastAPI test client"""
    return create_test_client()

@pytest.fixture
def create_test_user(db_session):
    """Factory for creating test users"""
    from core.models.models_per_tenant import User
    from datetime import datetime, timezone

    def _create_user(**kwargs):
        defaults = {
            "email": "test@example.com",
            "hashed_password": "hashed_password",
            "is_active": True,
            "role": "admin",
            "first_name": "Test",
            "last_name": "User",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        defaults.update(kwargs)
        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    return _create_user


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing"""
    # Use the shared engine/sessionmaker for compatibility
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Clean up data but keep tables
        for base in [MasterBase, TenantBase, AnalyticsBase, GamificationBase]:
            for table in reversed(base.metadata.sorted_tables):
                session.execute(table.delete())
        session.commit()

        # Re-seed tenant after cleanup
        db = TestingSessionLocal()
        from core.models.models import Tenant
        if not db.query(Tenant).filter(Tenant.id == 1).first():
            tenant = Tenant(id=1, name="Default Tenant", is_active=True)
            db.add(tenant)
            db.commit()

        from core.models.models_per_tenant import SupportedCurrency
        if not db.query(SupportedCurrency).filter(SupportedCurrency.code == "USD").first():
            usd = SupportedCurrency(
                code="USD",
                name="US Dollar",
                symbol="$",
                decimal_places=2,
                is_active=True
            )
            db.add(usd)
            db.commit()
        db.close()


@pytest.fixture
def mock_db():
    """Create a mock database session for unit testing"""
    return Mock(spec=Session)


@pytest.fixture
def sample_inventory_category(db_session):
    """Create a sample inventory category for testing"""
    from core.models.models_per_tenant import InventoryCategory
    from datetime import datetime, timezone

    category = InventoryCategory(
        name="Test Category",
        description="Test category description",
        color="#FF5733",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def sample_inventory_item(db_session, sample_inventory_category):
    """Create a sample inventory item for testing"""
    from core.models.models_per_tenant import InventoryItem
    from datetime import datetime, timezone

    item = InventoryItem(
        name="Test Item",
        description="Test item description",
        sku="TEST-001",
        category_id=sample_inventory_category.id,
        unit_price=29.99,
        cost_price=15.50,
        currency="USD",
        track_stock=True,
        current_stock=100,
        minimum_stock=10,
        unit_of_measure="each",
        item_type="product",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def sample_stock_movement(db_session, sample_inventory_item, sample_user):
    """Create a sample stock movement for testing"""
    from core.models.models_per_tenant import StockMovement
    from core.schemas.inventory import StockMovementCreate
    from datetime import datetime, timezone

    # We return the schema here to match previous behavior, but we might want the model
    return StockMovementCreate(
        item_id=sample_inventory_item.id,
        movement_type="sale",
        quantity=-5,
        reference_type="invoice",
        reference_id=123,
        notes="Test sale",
        user_id=sample_user.id,
        movement_date=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    from core.models.models_per_tenant import User

    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        role="admin",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_client(db_session):
    """Create a sample client for testing"""
    from core.models.models_per_tenant import Client
    from datetime import datetime, timezone

    client = Client(
        name="Test Client",
        email="client@example.com",
        balance=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


@pytest.fixture
def sample_invoice(db_session, sample_client):
    """Create a sample invoice for testing"""
    from core.models.models_per_tenant import Invoice
    from datetime import datetime, timezone

    invoice = Invoice(
        number="INV-001",
        amount=100.00,
        currency="USD",
        due_date=datetime.now(timezone.utc),
        status="draft",
        notes="Test invoice",
        client_id=sample_client.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


@pytest.fixture
def sample_expense(db_session, sample_user):
    """Create a sample expense for testing"""
    from core.models.models_per_tenant import Expense
    from datetime import datetime, timezone

    expense = Expense(
        amount=50.00,
        currency="USD",
        expense_date=datetime.now(timezone.utc),
        category="Office Supplies",
        vendor="Test Vendor",
        is_inventory_purchase=False,
        status="recorded",
        notes="Test expense",
        user_id=sample_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)
    return expense


@pytest.fixture
def inventory_service(db_session):
    """Create an inventory service instance"""
    from core.services.inventory_service import InventoryService
    return InventoryService(db_session)


@pytest.fixture
def stock_movement_service(db_session):
    """Create a stock movement service instance"""
    from core.services.stock_movement_service import StockMovementService
    return StockMovementService(db_session)


@pytest.fixture
def inventory_integration_service(db_session):
    """Create an inventory integration service instance"""
    from core.services.inventory_integration_service import InventoryIntegrationService
    return InventoryIntegrationService(db_session)


# Investment-specific fixtures (only available if investment models are imported)
if INVESTMENT_MODELS_AVAILABLE:
    @pytest.fixture
    def sample_investment_portfolio(db_session):
        """Create a sample investment portfolio for testing"""
        from plugins.investments.models import InvestmentPortfolio, PortfolioType
        from datetime import datetime, timezone

        portfolio = InvestmentPortfolio(
            tenant_id=1,  # Add tenant_id for proper tenant isolation
            name="Test Investment Portfolio",
            portfolio_type=PortfolioType.TAXABLE,
            is_archived=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(portfolio)
        db_session.commit()
        db_session.refresh(portfolio)
        return portfolio

    @pytest.fixture
    def sample_investment_holding(db_session, sample_investment_portfolio):
        """Create a sample investment holding for testing"""
        from plugins.investments.models import InvestmentHolding, SecurityType, AssetClass
        from datetime import datetime, timezone, date
        from decimal import Decimal

        holding = InvestmentHolding(
            portfolio_id=sample_investment_portfolio.id,
            security_symbol="AAPL",
            security_name="Apple Inc.",
            security_type=SecurityType.STOCK,
            asset_class=AssetClass.STOCKS,
            quantity=Decimal('100'),
            cost_basis=Decimal('10000'),  # $100 per share
            purchase_date=date(2024, 1, 1),
            current_price=Decimal('150'),
            is_closed=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(holding)
        db_session.commit()
        db_session.refresh(holding)
        return holding

    @pytest.fixture
    def investment_portfolio_service(db_session):
        """Create an investment portfolio service instance"""
        from plugins.investments.services.portfolio_service import PortfolioService
        return PortfolioService(db_session)

    @pytest.fixture
    def investment_holdings_service(db_session):
        """Create an investment holdings service instance"""
        from plugins.investments.services.holdings_service import HoldingsService
        return HoldingsService(db_session)

    @pytest.fixture
    def investment_transaction_service(db_session):
        """Create an investment transaction service instance"""
        from plugins.investments.services.transaction_service import TransactionService
        return TransactionService(db_session)

    @pytest.fixture
    def investment_analytics_service(db_session):
        """Create an investment analytics service instance"""
        from plugins.investments.services.analytics_service import AnalyticsService
        return AnalyticsService(db_session)

    @pytest.fixture
    def investment_portfolio_repo(db_session):
        """Create an investment portfolio repository instance"""
        from plugins.investments.repositories.portfolio_repository import PortfolioRepository
        return PortfolioRepository(db_session)

    @pytest.fixture
    def investment_holdings_repo(db_session):
        """Create an investment holdings repository instance"""
        from plugins.investments.repositories.holdings_repository import HoldingsRepository
        return HoldingsRepository(db_session)

    @pytest.fixture
    def investment_transaction_repo(db_session):
        """Create an investment transaction repository instance"""
        from plugins.investments.repositories.transaction_repository import TransactionRepository
        return TransactionRepository(db_session)


# Test data factories
def create_test_category(db_session, **kwargs):
    """Factory for creating test inventory categories"""
    from core.models.models_per_tenant import InventoryCategory
    from datetime import datetime, timezone

    defaults = {
        "name": "Test Category",
        "description": "Test category",
        "color": "#FF5733",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    defaults.update(kwargs)

    category = InventoryCategory(**defaults)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_test_item(db_session, **kwargs):
    """Factory for creating test inventory items"""
    from core.models.models_per_tenant import InventoryItem
    from datetime import datetime, timezone

    defaults = {
        "name": "Test Item",
        "description": "Test item",
        "sku": "TEST-001",
        "unit_price": 29.99,
        "cost_price": 15.50,
        "currency": "USD",
        "track_stock": True,
        "current_stock": 100,
        "minimum_stock": 10,
        "unit_of_measure": "each",
        "item_type": "product",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    defaults.update(kwargs)

    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


# Custom pytest markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "inventory: mark test as inventory-related")


# Test utilities
class InventoryTestHelper:
    """Helper class for inventory testing"""

    @staticmethod
    def create_category_with_items(db_session, category_name, item_count=3):
        """Create a category with multiple test items"""
        category = create_test_category(db_session, name=category_name)

        items = []
        for i in range(item_count):
            item = create_test_item(
                db_session,
                name=f"{category_name} Item {i+1}",
                sku=f"{category_name[:3].upper()}-{i+1:03d}",
                category_id=category.id,
                unit_price=10.00 * (i + 1),
                current_stock=50 * (i + 1)
            )
            items.append(item)

        return category, items

    @staticmethod
    def create_invoice_with_inventory_items(db_session, item_ids, quantities=None):
        """Create an invoice with inventory items"""
        from core.models.models_per_tenant import Invoice, InvoiceItem, Client

        if quantities is None:
            quantities = [1] * len(item_ids)

        # Create client and invoice
        client = Client(
            name="Test Client",
            email="client@example.com"
        )
        db_session.add(client)

        invoice = Invoice(
            number="INV-TEST-001",
            amount=0.0,  # Will be calculated
            currency="USD",
            due_date=datetime.now(timezone.utc),
            status="draft",
            client_id=client.id
        )
        db_session.add(invoice)
        db_session.flush()

        # Create invoice items
        total_amount = 0
        for i, item_id in enumerate(item_ids):
            item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            quantity = quantities[i] if i < len(quantities) else 1
            price = item.unit_price
            amount = quantity * price
            total_amount += amount

            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                inventory_item_id=item_id,
                description=item.name,
                quantity=quantity,
                price=price,
                amount=amount,
                unit_of_measure=item.unit_of_measure
            )
            db_session.add(invoice_item)

        # Update invoice total
        invoice.amount = total_amount
        db_session.commit()
        db_session.refresh(invoice)

        return invoice

    @staticmethod
    def create_expense_inventory_purchase(db_session, item_quantities):
        """Create an expense for inventory purchase"""
        from core.models.models_per_tenant import Expense, User

        # Create user if needed
        user = db_session.query(User).first()
        if not user:
            user = create_test_user(db_session)

        # Calculate total amount
        total_amount = 0
        inventory_items = []

        for item_id, quantity in item_quantities.items():
            item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            unit_cost = item.cost_price or item.unit_price * 0.6  # Estimate cost
            total_amount += quantity * unit_cost

            inventory_items.append({
                "item_id": item_id,
                "quantity": quantity,
                "unit_cost": unit_cost
            })

        expense = Expense(
            amount=total_amount,
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="Inventory Purchase",
            vendor="Test Supplier",
            is_inventory_purchase=True,
            inventory_items=inventory_items,
            status="recorded",
            user_id=user.id
        )

        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)

        return expense