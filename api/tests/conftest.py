"""
Pytest configuration and fixtures for inventory testing
"""
import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from models.models_per_tenant import Base


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing"""
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_db():
    """Create a mock database session for unit testing"""
    return Mock(spec=Session)


@pytest.fixture
def sample_inventory_category():
    """Create a sample inventory category for testing"""
    from models.models_per_tenant import InventoryCategory
    from datetime import datetime, timezone

    return InventoryCategory(
        id=1,
        name="Test Category",
        description="Test category description",
        color="#FF5733",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_inventory_item():
    """Create a sample inventory item for testing"""
    from models.models_per_tenant import InventoryItem
    from datetime import datetime, timezone

    return InventoryItem(
        id=1,
        name="Test Item",
        description="Test item description",
        sku="TEST-001",
        category_id=1,
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


@pytest.fixture
def sample_stock_movement():
    """Create a sample stock movement for testing"""
    from models.models_per_tenant import StockMovement
    from schemas.inventory import StockMovementCreate
    from datetime import datetime, timezone

    return StockMovementCreate(
        item_id=1,
        movement_type="sale",
        quantity=-5,
        reference_type="invoice",
        reference_id=123,
        notes="Test sale",
        user_id=1,
        movement_date=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_user():
    """Create a sample user for testing"""
    from models.models_per_tenant import User

    return User(
        id=1,
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        role="admin"
    )


@pytest.fixture
def sample_client():
    """Create a sample client for testing"""
    from models.models_per_tenant import Client
    from datetime import datetime, timezone

    return Client(
        id=1,
        name="Test Client",
        email="client@example.com",
        balance=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_invoice():
    """Create a sample invoice for testing"""
    from models.models_per_tenant import Invoice
    from datetime import datetime, timezone

    return Invoice(
        id=1,
        number="INV-001",
        amount=100.00,
        currency="USD",
        due_date=datetime.now(timezone.utc),
        status="draft",
        notes="Test invoice",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_expense():
    """Create a sample expense for testing"""
    from models.models_per_tenant import Expense
    from datetime import datetime, timezone

    return Expense(
        id=1,
        amount=50.00,
        currency="USD",
        expense_date=datetime.now(timezone.utc),
        category="Office Supplies",
        vendor="Test Vendor",
        is_inventory_purchase=False,
        status="recorded",
        notes="Test expense",
        user_id=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def inventory_service(db_session):
    """Create an inventory service instance"""
    from services.inventory_service import InventoryService
    return InventoryService(db_session)


@pytest.fixture
def stock_movement_service(db_session):
    """Create a stock movement service instance"""
    from services.stock_movement_service import StockMovementService
    return StockMovementService(db_session)


@pytest.fixture
def inventory_integration_service(db_session):
    """Create an inventory integration service instance"""
    from services.inventory_integration_service import InventoryIntegrationService
    return InventoryIntegrationService(db_session)


# Test data factories
def create_test_category(db_session, **kwargs):
    """Factory for creating test inventory categories"""
    from models.models_per_tenant import InventoryCategory
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
    from models.models_per_tenant import InventoryItem
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


def create_test_user(db_session, **kwargs):
    """Factory for creating test users"""
    from models.models_per_tenant import User

    defaults = {
        "email": "test@example.com",
        "hashed_password": "hashed_password",
        "is_active": True,
        "role": "admin",
        "first_name": "Test",
        "last_name": "User"
    }
    defaults.update(kwargs)

    user = User(**defaults)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


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
        from models.models_per_tenant import Invoice, InvoiceItem, Client

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
        from models.models_per_tenant import Expense, User

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