"""
Comprehensive tests for inventory service layer
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from core.models.models_per_tenant import (
    InventoryItem, InventoryCategory, StockMovement,
    User, Invoice, InvoiceItem, Expense
)
from core.services.inventory_service import InventoryService
from core.services.stock_movement_service import StockMovementService
from core.schemas.inventory import (
    InventoryItemCreate, InventoryItemUpdate,
    InventoryCategoryCreate, InventoryCategoryUpdate,
    InventorySearchFilters, StockMovementCreate
)
from core.exceptions.inventory_exceptions import (
    ItemNotFoundException, CategoryNotFoundException,
    DuplicateSKUException, InsufficientStockException,
    StockNotTrackedException
)


class TestInventoryService:
    """Test inventory service operations"""

    def setup_method(self):
        """Setup test fixtures"""
        self.db = Mock()
        self.service = InventoryService(self.db)

    def test_create_category_success(self):
        """Test successful category creation"""
        category_data = InventoryCategoryCreate(
            name="Test Category",
            description="Test description"
        )

        mock_category = Mock()
        mock_category.id = 1
        mock_category.name = "Test Category"

        with patch.object(self.service, '_get_category_model', return_value=Mock()) as mock_model:
            mock_model.return_value = mock_category
            self.db.add = Mock()
            self.db.commit = Mock()
            self.db.refresh = Mock()

            result = self.service.create_category(category_data)

            self.db.add.assert_called_once()
            self.db.commit.assert_called_once()
            self.db.refresh.assert_called_once()
            assert result == mock_category

    def test_create_category_duplicate_name(self):
        """Test category creation with duplicate name"""
        category_data = InventoryCategoryCreate(name="Duplicate Category")

        with patch.object(self.service, '_get_category_model') as mock_model:
            mock_model.side_effect = Exception("Unique constraint violation")

            with pytest.raises(ValueError):
                self.service.create_category(category_data)

    def test_create_item_success(self):
        """Test successful item creation"""
        item_data = InventoryItemCreate(
            name="Test Item",
            unit_price=29.99,
            track_stock=True,
            current_stock=100,
            unit_of_measure="each"
        )

        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"

        with patch.object(self.service, '_get_item_model', return_value=Mock()) as mock_model:
            mock_model.return_value = mock_item
            self.db.add = Mock()
            self.db.commit = Mock()
            self.db.refresh = Mock()

            result = self.service.create_item(item_data, user_id=1)

            self.db.add.assert_called_once()
            self.db.commit.assert_called_once()
            self.db.refresh.assert_called_once()
            assert result == mock_item

    def test_create_item_duplicate_sku(self):
        """Test item creation with duplicate SKU"""
        item_data = InventoryItemCreate(
            name="Test Item",
            sku="DUPLICATE-SKU",
            unit_price=29.99,
            track_stock=False,
            current_stock=0,
            unit_of_measure="each"
        )

        with patch.object(self.service, '_get_item_model') as mock_model:
            mock_model.side_effect = Exception("Unique constraint violation")

            with pytest.raises(ValueError):
                self.service.create_item(item_data, user_id=1)

    def test_get_item_not_found(self):
        """Test getting non-existent item"""
        self.db.query.return_value.options.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ItemNotFoundException):
            self.service.get_item(999)

    def test_update_item_success(self):
        """Test successful item update"""
        item_data = InventoryItemUpdate(name="Updated Name")

        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Original Name"

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.service.update_item(1, item_data, user_id=1)

        assert result == mock_item
        assert mock_item.name == "Updated Name"
        self.db.commit.assert_called_once()

    def test_update_item_not_found(self):
        """Test updating non-existent item"""
        item_data = InventoryItemUpdate(name="Updated Name")

        self.db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ItemNotFoundException):
            self.service.update_item(999, item_data, user_id=1)

    def test_delete_item_success(self):
        """Test successful item deletion"""
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"

        # Mock no invoice/expense references
        self.db.query.return_value.filter.return_value.scalar.return_value = 0
        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.service.delete_item(1, user_id=1)

        assert result == True
        self.db.delete.assert_called_once_with(mock_item)
        self.db.commit.assert_called_once()

    def test_delete_item_in_use(self):
        """Test deleting item that is referenced in invoices"""
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"

        # Mock invoice references exist
        self.db.query.return_value.filter.return_value.scalar.return_value = 2
        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        with pytest.raises(ValueError):
            self.service.delete_item(1, user_id=1)

    def test_search_items_with_filters(self):
        """Test item search with filters"""
        filters = InventorySearchFilters(
            query="test",
            category_id=1,
            item_type="product",
            is_active=True
        )

        mock_items = [Mock(), Mock()]

        # Mock the query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_items

        self.db.query.return_value = mock_query

        result = self.service.get_items(filters, skip=0, limit=100)

        assert result == mock_items
        assert len(result) == 2

    def test_validate_stock_availability_tracked_item(self):
        """Test stock validation for tracked items"""
        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 50

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        # Test sufficient stock
        result = self.service.validate_stock_availability(1, 25)
        assert result == True

        # Test insufficient stock
        result = self.service.validate_stock_availability(1, 75)
        assert result == False

    def test_validate_stock_availability_untracked_item(self):
        """Test stock validation for untracked items"""
        mock_item = Mock()
        mock_item.track_stock = False

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        # Untracked items should always be available
        result = self.service.validate_stock_availability(1, 1000)
        assert result == True

    def test_get_low_stock_items(self):
        """Test getting low stock items"""
        mock_items = [Mock(), Mock(), Mock()]

        # Mock the query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_items

        self.db.query.return_value = mock_query

        result = self.service.get_low_stock_items()

        assert result == mock_items
        assert len(result) == 3

    def test_get_inventory_analytics(self):
        """Test getting inventory analytics"""
        # Mock count queries
        self.db.query.return_value.scalar.side_effect = [100, 95, 5, 5000.00]

        result = self.service.get_inventory_analytics()

        assert result.total_items == 100
        assert result.active_items == 95
        assert result.low_stock_items == 5
        assert result.total_value == 5000.00


class TestStockMovementService:
    """Test stock movement service operations"""

    def setup_method(self):
        """Setup test fixtures"""
        self.db = Mock()
        self.service = StockMovementService(self.db)

    def test_record_movement_success(self):
        """Test successful stock movement recording"""
        movement_data = StockMovementCreate(
            item_id=1,
            movement_type="sale",
            quantity=-5,
            reference_type="invoice",
            reference_id=123,
            user_id=1
        )

        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 100

        mock_movement = Mock()
        mock_movement.id = 1

        self.db.query.return_value.filter.return_value.first.return_value = mock_item
        self.db.add = Mock()
        self.db.commit = Mock()
        self.db.refresh = Mock()

        result = self.service.record_movement(movement_data)

        # Verify stock was updated correctly
        assert mock_item.current_stock == 95  # 100 - 5
        self.db.add.assert_called_once()
        self.db.commit.assert_called_once()

    def test_record_movement_insufficient_stock(self):
        """Test stock movement with insufficient stock"""
        movement_data = StockMovementCreate(
            item_id=1,
            movement_type="sale",
            quantity=-50,
            user_id=1
        )

        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 25

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        with pytest.raises(ValueError):
            self.service.record_movement(movement_data)

    def test_record_movement_untracked_item(self):
        """Test stock movement on untracked item"""
        movement_data = StockMovementCreate(
            item_id=1,
            movement_type="adjustment",
            quantity=10,
            user_id=1
        )

        mock_item = Mock()
        mock_item.track_stock = False

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        with pytest.raises(ValueError):
            self.service.record_movement(movement_data)

    def test_record_manual_adjustment(self):
        """Test manual stock adjustment"""
        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 50

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        with patch.object(self.service, 'record_movement') as mock_record:
            mock_record.return_value = Mock()

            result = self.service.record_manual_adjustment(1, 25, "Test adjustment", 1)

            mock_record.assert_called_once()
            call_args = mock_record.call_args[0][0]

            assert call_args.item_id == 1
            assert call_args.movement_type == "adjustment"
            assert call_args.quantity == 25
            assert call_args.reference_type == "manual"
            assert call_args.notes == "Test adjustment"
            assert call_args.user_id == 1

    def test_get_movement_history(self):
        """Test getting movement history"""
        mock_movements = [Mock(), Mock(), Mock()]

        # Mock the query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_movements

        self.db.query.return_value = mock_query

        result = self.service.get_movement_history(1, limit=50)

        assert result == mock_movements
        assert len(result) == 3

    def test_get_movements_by_reference(self):
        """Test getting movements by reference"""
        mock_movements = [Mock(), Mock()]

        # Mock the query chain
        mock_query = Mock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_movements

        self.db.query.return_value = mock_query

        result = self.service.get_movements_by_reference("invoice", 123)

        assert result == mock_movements
        assert len(result) == 2

    def test_validate_stock_operation_sufficient_stock(self):
        """Test stock operation validation with sufficient stock"""
        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 100

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.service.validate_stock_operation(1, 25, "sale")

        assert result["valid"] == True
        assert result["current_stock"] == 100
        assert result["available"] == 100

    def test_validate_stock_operation_insufficient_stock(self):
        """Test stock operation validation with insufficient stock"""
        mock_item = Mock()
        mock_item.track_stock = True
        mock_item.current_stock = 20

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.service.validate_stock_operation(1, 50, "sale")

        assert result["valid"] == False
        assert result["current_stock"] == 20
        assert result["available"] == 20
        assert "Insufficient stock" in result["reason"]

    def test_validate_stock_operation_untracked_item(self):
        """Test stock operation validation for untracked item"""
        mock_item = Mock()
        mock_item.track_stock = False
        mock_item.current_stock = 0

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.service.validate_stock_operation(1, 100, "sale")

        assert result["valid"] == True
        assert result["available"] == float('inf')

    def test_get_audit_trail(self):
        """Test getting audit trail for an item"""
        mock_movements = [
            Mock(
                id=1,
                movement_type="purchase",
                quantity=50,
                current_stock_after_movement=50,
                movement_date=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ),
            Mock(
                id=2,
                movement_type="sale",
                quantity=-10,
                current_stock_after_movement=40,
                movement_date=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            )
        ]

        # Mock the query chain
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_movements

        self.db.query.return_value = mock_query

        result = self.service.get_audit_trail(1)

        assert len(result) == 2
        assert result[0]["movement_type"] == "purchase"
        assert result[0]["quantity"] == 50
        assert result[0]["running_total"] == 50
        assert result[1]["running_total"] == 40

    def test_get_stock_summary(self):
        """Test getting stock summary"""
        mock_summary_data = [
            (1, "Item 1", "SKU-001", 100, 45, 3, datetime.now(timezone.utc), datetime.now(timezone.utc)),
            (2, "Item 2", "SKU-002", 75, 30, 2, datetime.now(timezone.utc), datetime.now(timezone.utc))
        ]

        # Mock the query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_summary_data

        self.db.query.return_value = mock_query

        result = self.service.get_stock_summary()

        assert len(result) == 2
        assert result[0]["item_id"] == 1
        assert result[0]["item_name"] == "Item 1"
        assert result[0]["total_movement"] == 45
        assert result[0]["movement_count"] == 3
