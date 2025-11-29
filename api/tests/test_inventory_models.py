"""
Comprehensive tests for inventory management models
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from core.models.models_per_tenant import (
    InventoryItem, InventoryCategory, StockMovement,
    InvoiceItem, Expense, Invoice, User, Client
)
from core.schemas.inventory import (
    InventoryItemCreate, InventoryItemUpdate,
    InventoryCategoryCreate, InventoryCategoryUpdate,
    StockMovementCreate
)


class TestInventoryModels:
    """Test inventory model operations"""

    def test_inventory_category_creation(self, db_session):
        """Test creating an inventory category"""
        category_data = InventoryCategoryCreate(
            name="Test Category",
            description="Test category description",
            color="#FF5733"
        )

        category = InventoryCategory(**category_data.model_dump())
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        assert category.id is not None
        assert category.name == "Test Category"
        assert category.description == "Test category description"
        assert category.color == "#FF5733"
        assert category.is_active == True
        assert category.created_at is not None
        assert category.updated_at is not None

    def test_inventory_category_unique_name_constraint(self, db_session):
        """Test unique name constraint for categories"""
        # Create first category
        category1 = InventoryCategory(name="Unique Category", is_active=True)
        db_session.add(category1)
        db_session.commit()

        # Try to create duplicate category
        category2 = InventoryCategory(name="Unique Category", is_active=True)
        db_session.add(category2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_inventory_item_creation(self, db_session):
        """Test creating an inventory item"""
        # Create category first
        category = InventoryCategory(name="Test Category", is_active=True)
        db_session.add(category)
        db_session.commit()

        item_data = InventoryItemCreate(
            name="Test Item",
            description="Test item description",
            sku="TEST-001",
            category_id=category.id,
            unit_price=29.99,
            cost_price=15.50,
            currency="USD",
            track_stock=True,
            current_stock=100,
            minimum_stock=10,
            unit_of_measure="each",
            item_type="product"
        )

        item = InventoryItem(**item_data.model_dump())
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.id is not None
        assert item.name == "Test Item"
        assert item.sku == "TEST-001"
        assert item.category_id == category.id
        assert item.unit_price == 29.99
        assert item.cost_price == 15.50
        assert item.track_stock == True
        assert item.current_stock == 100
        assert item.minimum_stock == 10
        assert item.item_type == "product"
        assert item.is_active == True

    def test_inventory_item_unique_sku_constraint(self, db_session):
        """Test unique SKU constraint for items"""
        # Create first item
        item1 = InventoryItem(
            name="Item 1",
            sku="UNIQUE-SKU",
            unit_price=10.00,
            track_stock=False,
            current_stock=0,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item1)
        db_session.commit()

        # Try to create item with duplicate SKU
        item2 = InventoryItem(
            name="Item 2",
            sku="UNIQUE-SKU",
            unit_price=20.00,
            track_stock=False,
            current_stock=0,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_inventory_item_without_stock_tracking(self, db_session):
        """Test creating item without stock tracking"""
        item = InventoryItem(
            name="Service Item",
            unit_price=50.00,
            track_stock=False,
            current_stock=0,  # Should be allowed even if > 0
            minimum_stock=0,   # Should be allowed even if > 0
            unit_of_measure="hours",
            item_type="service",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.track_stock == False
        assert item.current_stock == 0
        assert item.minimum_stock == 0
        assert item.item_type == "service"

    def test_stock_movement_creation(self, db_session):
        """Test creating a stock movement"""
        # Create user and item first
        user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)

        category = InventoryCategory(name="Test Category", is_active=True)
        db_session.add(category)

        item = InventoryItem(
            name="Test Item",
            unit_price=10.00,
            track_stock=True,
            current_stock=100,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        movement_data = StockMovementCreate(
            item_id=item.id,
            movement_type="adjustment",
            quantity=-5,
            reference_type="manual",
            notes="Test adjustment",
            user_id=user.id
        )

        movement = StockMovement(**movement_data.model_dump())
        db_session.add(movement)
        db_session.commit()
        db_session.refresh(movement)

        assert movement.id is not None
        assert movement.item_id == item.id
        assert movement.movement_type == "adjustment"
        assert movement.quantity == -5
        assert movement.reference_type == "manual"
        assert movement.user_id == user.id
        assert movement.notes == "Test adjustment"
        assert movement.movement_date is not None

    def test_inventory_item_relationships(self, db_session):
        """Test inventory item relationships"""
        # Create category and item
        category = InventoryCategory(name="Electronics", is_active=True)
        db_session.add(category)

        item = InventoryItem(
            name="Laptop",
            category_id=category.id,
            unit_price=999.99,
            track_stock=True,
            current_stock=50,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        # Test category relationship
        assert item.category is not None
        assert item.category.name == "Electronics"
        assert category.items[0].name == "Laptop"

    def test_stock_movement_relationships(self, db_session):
        """Test stock movement relationships"""
        # Create user and item
        user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)

        item = InventoryItem(
            name="Test Item",
            unit_price=10.00,
            track_stock=True,
            current_stock=100,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        # Create movement
        movement = StockMovement(
            item_id=item.id,
            movement_type="purchase",
            quantity=50,
            user_id=user.id
        )
        db_session.add(movement)
        db_session.commit()

        # Test relationships
        assert movement.item is not None
        assert movement.item.name == "Test Item"
        assert movement.user is not None
        assert movement.user.email == "test@example.com"
        assert len(item.stock_movements) == 1
        assert item.stock_movements[0].movement_type == "purchase"

    def test_invoice_item_inventory_relationship(self, db_session):
        """Test invoice item to inventory relationship"""
        # Create necessary entities
        user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)

        client = Client(
            name="Test Client",
            email="client@example.com"
        )
        db_session.add(client)

        invoice = Invoice(
            number="INV-001",
            amount=100.00,
            currency="USD",
            due_date=datetime.now(timezone.utc),
            status="draft"
        )
        invoice.client_id = client.id
        db_session.add(invoice)

        # Create inventory item
        inventory_item = InventoryItem(
            name="Test Product",
            unit_price=25.00,
            track_stock=True,
            current_stock=100,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(inventory_item)
        db_session.commit()

        # Create invoice item linked to inventory
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            inventory_item_id=inventory_item.id,
            description="Test Product",
            quantity=4,
            price=25.00,
            amount=100.00,
            unit_of_measure="each"
        )
        db_session.add(invoice_item)
        db_session.commit()

        # Test relationships
        assert invoice_item.inventory_item is not None
        assert invoice_item.inventory_item.name == "Test Product"
        assert len(inventory_item.invoice_items) == 1
        assert inventory_item.invoice_items[0].description == "Test Product"

    def test_expense_inventory_purchase_relationship(self, db_session):
        """Test expense inventory purchase relationship"""
        # Create user
        user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)

        # Create inventory item
        inventory_item = InventoryItem(
            name="Office Supplies",
            unit_price=50.00,
            track_stock=True,
            current_stock=0,
            unit_of_measure="box",
            is_active=True
        )
        db_session.add(inventory_item)
        db_session.commit()

        # Create expense with inventory purchase
        expense = Expense(
            amount=150.00,
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="Office Supplies",
            vendor="Office Depot",
            is_inventory_purchase=True,
            inventory_items=[
                {
                    "item_id": inventory_item.id,
                    "quantity": 3,
                    "unit_cost": 50.00
                }
            ],
            user_id=user.id
        )
        db_session.add(expense)
        db_session.commit()

        # Test expense properties
        assert expense.is_inventory_purchase == True
        assert len(expense.inventory_items) == 1
        assert expense.inventory_items[0]["item_id"] == inventory_item.id
        assert expense.inventory_items[0]["quantity"] == 3
        assert expense.inventory_items[0]["unit_cost"] == 50.00

    def test_soft_delete_inventory_item(self, db_session):
        """Test soft delete functionality for inventory items"""
        item = InventoryItem(
            name="Test Item",
            unit_price=10.00,
            track_stock=False,
            current_stock=0,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        # Soft delete by setting is_active to False
        item.is_active = False
        db_session.commit()

        # Item should still exist but be inactive
        assert item.is_active == False
        assert db_session.query(InventoryItem).filter(InventoryItem.id == item.id).first() is not None

        # Active queries should exclude this item
        active_items = db_session.query(InventoryItem).filter(InventoryItem.is_active == True).all()
        assert len([i for i in active_items if i.id == item.id]) == 0

    def test_cascade_delete_stock_movements(self, db_session):
        """Test cascade delete of stock movements when item is deleted"""
        # Create user and item
        user = User(
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)

        item = InventoryItem(
            name="Test Item",
            unit_price=10.00,
            track_stock=True,
            current_stock=100,
            unit_of_measure="each",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        # Create movement
        movement = StockMovement(
            item_id=item.id,
            movement_type="purchase",
            quantity=50,
            user_id=user.id
        )
        db_session.add(movement)
        db_session.commit()

        movement_id = movement.id
        item_id = item.id

        # Delete item (this should cascade delete movements due to ondelete="CASCADE")
        db_session.delete(item)
        db_session.commit()

        # Movement should be deleted
        deleted_movement = db_session.query(StockMovement).filter(StockMovement.id == movement_id).first()
        assert deleted_movement is None

    def test_inventory_item_validation_constraints(self, db_session):
        """Test inventory item validation constraints"""
        # Test positive unit price requirement
        with pytest.raises(ValueError):
            InventoryItemCreate(
                name="Invalid Item",
                unit_price=-10.00,  # Invalid: negative price
                track_stock=False,
                current_stock=0,
                unit_of_measure="each"
            )

        # Test positive current stock when tracking
        with pytest.raises(ValueError):
            InventoryItemCreate(
                name="Invalid Item",
                unit_price=10.00,
                track_stock=True,
                current_stock=-5,  # Invalid: negative stock when tracking
                unit_of_measure="each"
            )

        # Test valid item creation
        valid_item = InventoryItemCreate(
            name="Valid Item",
            unit_price=10.00,
            track_stock=False,
            current_stock=100,  # Allowed when not tracking
            minimum_stock=50,   # Allowed when not tracking
            unit_of_measure="each"
        )
        assert valid_item.name == "Valid Item"
        assert valid_item.unit_price == 10.00
