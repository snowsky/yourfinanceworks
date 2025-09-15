"""
Integration tests for inventory system components
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from models.models_per_tenant import (
    InventoryItem, InventoryCategory, StockMovement,
    Invoice, InvoiceItem, Expense, User, Client
)
from services.inventory_integration_service import InventoryIntegrationService
from services.inventory_service import InventoryService
from services.stock_movement_service import StockMovementService
from schemas.inventory import InventoryItemCreate


class TestInventoryIntegration:
    """Test integration between inventory and other systems"""

    def setup_method(self):
        """Setup test fixtures"""
        self.db = Mock()
        self.inventory_service = InventoryService(self.db)
        self.stock_service = StockMovementService(self.db)
        self.integration_service = InventoryIntegrationService(self.db)

    def test_invoice_item_population_from_inventory(self):
        """Test populating invoice item data from inventory"""
        # Mock inventory item
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Product"
        mock_item.unit_price = 29.99
        mock_item.unit_of_measure = "each"
        mock_item.track_stock = True
        mock_item.current_stock = 100

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        result = self.integration_service.populate_invoice_item_from_inventory(1, 5)

        assert result["inventory_item_id"] == 1
        assert result["description"] == "Test Product"
        assert result["quantity"] == 5
        assert result["price"] == 29.99
        assert result["amount"] == 149.95  # 5 * 29.99
        assert result["unit_of_measure"] == "each"
        assert result["inventory_item"] == mock_item

    def test_invoice_item_population_insufficient_stock(self):
        """Test invoice item population with insufficient stock"""
        # Mock inventory item with low stock
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Low Stock Item"
        mock_item.track_stock = True
        mock_item.current_stock = 5

        self.db.query.return_value.filter.return_value.first.return_value = mock_item

        with pytest.raises(Exception):  # Should raise InsufficientStockException
            self.integration_service.populate_invoice_item_from_inventory(1, 10)

    def test_stock_movement_processing_for_invoice(self):
        """Test stock movement processing when invoice is completed"""
        # Mock invoice
        mock_invoice = Mock()
        mock_invoice.id = 123
        mock_invoice.number = "INV-001"
        mock_invoice.status = "paid"

        # Mock invoice items with inventory
        mock_invoice_item1 = Mock()
        mock_invoice_item1.inventory_item_id = 1
        mock_invoice_item1.quantity = 5

        mock_invoice_item2 = Mock()
        mock_invoice_item2.inventory_item_id = 2
        mock_invoice_item2.quantity = 3

        # Mock inventory items
        mock_inv_item1 = Mock()
        mock_inv_item1.id = 1
        mock_inv_item1.track_stock = True
        mock_inv_item1.current_stock = 100

        mock_inv_item2 = Mock()
        mock_inv_item2.id = 2
        mock_inv_item2.track_stock = True
        mock_inv_item2.current_stock = 50

        # Setup mock queries
        mock_items_query = Mock()
        mock_items_query.options.return_value = mock_items_query
        mock_items_query.filter.return_value = mock_items_query
        mock_items_query.all.return_value = [mock_invoice_item1, mock_invoice_item2]

        self.db.query.return_value = mock_items_query

        # Mock inventory item queries
        def mock_item_query(item_id):
            if item_id == 1:
                return mock_inv_item1
            elif item_id == 2:
                return mock_inv_item2
            return None

        self.inventory_service.get_item = mock_item_query

        # Mock stock movement creation
        mock_movement1 = Mock()
        mock_movement2 = Mock()

        with patch.object(self.stock_service, 'record_movement') as mock_record:
            mock_record.side_effect = [mock_movement1, mock_movement2]

            movements = self.integration_service.process_invoice_stock_movements(mock_invoice, user_id=1)

            assert len(movements) == 2
            assert mock_record.call_count == 2

            # Verify stock was reduced correctly
            assert mock_inv_item1.current_stock == 95  # 100 - 5
            assert mock_inv_item2.current_stock == 47  # 50 - 3

    def test_stock_movement_reversal_for_cancelled_invoice(self):
        """Test stock movement reversal when invoice is cancelled"""
        # Mock invoice
        mock_invoice = Mock()
        mock_invoice.id = 123
        mock_invoice.number = "INV-001"

        # Mock existing stock movements for this invoice
        mock_movement1 = Mock()
        mock_movement1.id = 1
        mock_movement1.item_id = 1
        mock_movement1.quantity = -5  # Sale movement (negative)

        mock_movement2 = Mock()
        mock_movement2.id = 2
        mock_movement2.item_id = 2
        mock_movement2.quantity = -3  # Sale movement (negative)

        # Setup mock query for movements
        mock_movements_query = Mock()
        mock_movements_query.filter.return_value = mock_movements_query
        mock_movements_query.all.return_value = [mock_movement1, mock_movement2]

        # Mock the query chain
        self.db.query.side_effect = lambda *args: mock_movements_query

        # Mock inventory items
        mock_inv_item1 = Mock()
        mock_inv_item1.track_stock = True
        mock_inv_item1.current_stock = 95

        mock_inv_item2 = Mock()
        mock_inv_item2.track_stock = True
        mock_inv_item2.current_stock = 47

        def mock_item_query(item_id):
            if item_id == 1:
                return mock_inv_item1
            elif item_id == 2:
                return mock_inv_item2
            return None

        self.inventory_service.get_item = mock_item_query

        # Mock stock movement creation for reversals
        mock_reverse_movement1 = Mock()
        mock_reverse_movement2 = Mock()

        with patch.object(self.stock_service, 'record_movement') as mock_record:
            mock_record.side_effect = [mock_reverse_movement1, mock_reverse_movement2]

            movements = self.integration_service.reverse_invoice_stock_movements(mock_invoice, user_id=1)

            assert len(movements) == 2
            assert mock_record.call_count == 2

            # Verify stock was restored correctly
            assert mock_inv_item1.current_stock == 100  # 95 + 5
            assert mock_inv_item2.current_stock == 50   # 47 + 3

    def test_expense_inventory_purchase_processing(self):
        """Test stock increase processing for inventory purchase expenses"""
        # Mock expense
        mock_expense = Mock()
        mock_expense.id = 456
        mock_expense.is_inventory_purchase = True
        mock_expense.inventory_items = [
            {"item_id": 1, "quantity": 25, "unit_cost": 15.00},
            {"item_id": 2, "quantity": 10, "unit_cost": 20.00}
        ]

        # Mock inventory items
        mock_inv_item1 = Mock()
        mock_inv_item1.id = 1
        mock_inv_item1.track_stock = True
        mock_inv_item1.current_stock = 50

        mock_inv_item2 = Mock()
        mock_inv_item2.id = 2
        mock_inv_item2.track_stock = True
        mock_inv_item2.current_stock = 30

        def mock_item_query(item_id):
            if item_id == 1:
                return mock_inv_item1
            elif item_id == 2:
                return mock_inv_item2
            return None

        self.inventory_service.get_item = mock_item_query

        # Mock stock movement creation
        mock_movement1 = Mock()
        mock_movement2 = Mock()

        with patch.object(self.stock_service, 'record_movement') as mock_record:
            mock_record.side_effect = [mock_movement1, mock_movement2]

            movements = self.integration_service.process_expense_inventory_purchase(mock_expense, user_id=1)

            assert len(movements) == 2
            assert mock_record.call_count == 2

            # Verify stock was increased correctly
            assert mock_inv_item1.current_stock == 75  # 50 + 25
            assert mock_inv_item2.current_stock == 40  # 30 + 10

    def test_inventory_purchase_expense_reversal(self):
        """Test stock decrease when inventory purchase expense is cancelled"""
        # Mock expense
        mock_expense = Mock()
        mock_expense.id = 456
        mock_expense.is_inventory_purchase = True
        mock_expense.inventory_items = [
            {"item_id": 1, "quantity": 25, "unit_cost": 15.00}
        ]

        # Mock existing stock movements for this expense
        mock_movement = Mock()
        mock_movement.id = 1
        mock_movement.item_id = 1
        mock_movement.quantity = 25  # Purchase movement (positive)

        # Setup mock query for movements
        mock_movements_query = Mock()
        mock_movements_query.filter.return_value = mock_movements_query
        mock_movements_query.all.return_value = [mock_movement]

        # Mock the query chain
        self.db.query.side_effect = lambda *args: mock_movements_query

        # Mock inventory item
        mock_inv_item = Mock()
        mock_inv_item.track_stock = True
        mock_inv_item.current_stock = 75

        def mock_item_query(item_id):
            return mock_inv_item if item_id == 1 else None

        self.inventory_service.get_item = mock_item_query

        # Mock stock movement creation for reversal
        mock_reverse_movement = Mock()

        with patch.object(self.stock_service, 'record_movement') as mock_record:
            mock_record.return_value = mock_reverse_movement

            movements = self.integration_service.reverse_expense_stock_impact(mock_expense, user_id=1)

            assert len(movements) == 1
            assert mock_record.call_count == 1

            # Verify stock was decreased correctly
            assert mock_inv_item.current_stock == 50  # 75 - 25

    def test_invoice_inventory_summary_generation(self):
        """Test generating inventory summary for an invoice"""
        # Mock invoice items with inventory
        mock_invoice_item1 = Mock()
        mock_invoice_item1.id = 1
        mock_invoice_item1.inventory_item_id = 1
        mock_invoice_item1.quantity = 2
        mock_invoice_item1.price = 25.00
        mock_invoice_item1.amount = 50.00

        mock_invoice_item2 = Mock()
        mock_invoice_item2.id = 2
        mock_invoice_item2.inventory_item_id = 2
        mock_invoice_item2.quantity = 1
        mock_invoice_item2.price = 100.00
        mock_invoice_item2.amount = 100.00

        # Mock inventory items
        mock_inv_item1 = Mock()
        mock_inv_item1.id = 1
        mock_inv_item1.name = "Product A"
        mock_inv_item1.sku = "PROD-A"
        mock_inv_item1.track_stock = True
        mock_inv_item1.current_stock = 48

        mock_inv_item2 = Mock()
        mock_inv_item2.id = 2
        mock_inv_item2.name = "Product B"
        mock_inv_item2.sku = "PROD-B"
        mock_inv_item2.track_stock = False
        mock_inv_item2.current_stock = 0

        # Setup mock queries
        mock_items_query = Mock()
        mock_items_query.options.return_value = mock_items_query
        mock_items_query.filter.return_value = mock_items_query
        mock_items_query.all.return_value = [mock_invoice_item1, mock_invoice_item2]

        self.db.query.return_value = mock_items_query

        # Mock inventory item queries
        def mock_item_query(item_id):
            if item_id == 1:
                return mock_inv_item1
            elif item_id == 2:
                return mock_inv_item2
            return None

        self.inventory_service.get_item = mock_item_query

        result = self.integration_service.get_invoice_inventory_summary(123)

        assert result["invoice_id"] == 123
        assert result["total_inventory_items"] == 2
        assert result["total_inventory_value"] == 150.00  # 50 + 100
        assert len(result["inventory_items"]) == 2

        # Check first item
        item1 = result["inventory_items"][0]
        assert item1["item_id"] == 1
        assert item1["item_name"] == "Product A"
        assert item1["quantity"] == 2
        assert item1["line_total"] == 50.00
        assert item1["current_stock"] == 48

        # Check second item
        item2 = result["inventory_items"][1]
        assert item2["item_id"] == 2
        assert item2["item_name"] == "Product B"
        assert item2["quantity"] == 1
        assert item2["line_total"] == 100.00
        assert item2["current_stock"] is None  # Not tracking stock

    def test_expense_inventory_summary_generation(self):
        """Test generating inventory summary for an expense"""
        # Mock expense
        mock_expense = Mock()
        mock_expense.id = 456
        mock_expense.is_inventory_purchase = True
        mock_expense.inventory_items = [
            {"item_id": 1, "quantity": 10, "unit_cost": 15.00},
            {"item_id": 2, "quantity": 5, "unit_cost": 25.00}
        ]

        self.db.query.return_value.filter.return_value.first.return_value = mock_expense

        # Mock inventory items
        mock_inv_item1 = Mock()
        mock_inv_item1.id = 1
        mock_inv_item1.name = "Purchase Item A"
        mock_inv_item1.sku = "PUR-A"
        mock_inv_item1.track_stock = True
        mock_inv_item1.current_stock = 60

        mock_inv_item2 = Mock()
        mock_inv_item2.id = 2
        mock_inv_item2.name = "Purchase Item B"
        mock_inv_item2.sku = "PUR-B"
        mock_inv_item2.track_stock = True
        mock_inv_item2.current_stock = 25

        def mock_item_query(item_id):
            if item_id == 1:
                return mock_inv_item1
            elif item_id == 2:
                return mock_inv_item2
            return None

        self.inventory_service.get_item = mock_item_query

        result = self.integration_service.get_expense_inventory_summary(456)

        assert result["expense_id"] == 456
        assert result["is_inventory_purchase"] == True
        assert result["total_items"] == 2
        assert result["total_value"] == 275.00  # (10*15) + (5*25)
        assert len(result["inventory_items"]) == 2

        # Check items
        item1 = result["inventory_items"][0]
        assert item1["item_name"] == "Purchase Item A"
        assert item1["quantity"] == 10
        assert item1["unit_cost"] == 15.00
        assert item1["line_total"] == 150.00

        item2 = result["inventory_items"][1]
        assert item2["item_name"] == "Purchase Item B"
        assert item2["quantity"] == 5
        assert item2["unit_cost"] == 25.00
        assert item2["line_total"] == 125.00

    def test_validate_stock_availability_for_invoice(self):
        """Test stock validation for multiple invoice items"""
        # Mock invoice items
        invoice_items = [
            {"inventory_item_id": 1, "quantity": 5},
            {"inventory_item_id": 2, "quantity": 10},
            {"inventory_item_id": None, "quantity": 1}  # Non-inventory item
        ]

        # Mock inventory items
        mock_item1 = Mock()
        mock_item1.id = 1
        mock_item1.name = "Item 1"
        mock_item1.track_stock = True
        mock_item1.current_stock = 20

        mock_item2 = Mock()
        mock_item2.id = 2
        mock_item2.name = "Item 2"
        mock_item2.track_stock = True
        mock_item2.current_stock = 5  # Insufficient stock

        def mock_item_query(item_id):
            if item_id == 1:
                return mock_item1
            elif item_id == 2:
                return mock_item2
            return None

        self.inventory_service.get_item = mock_item_query

        result = self.integration_service.validate_invoice_stock_availability(invoice_items)

        assert len(result) == 3

        # Item 1 - sufficient stock
        assert result[0]["item_id"] == 1
        assert result[0]["sufficient"] == True
        assert result[0]["available"] == 20

        # Item 2 - insufficient stock
        assert result[1]["item_id"] == 2
        assert result[1]["sufficient"] == False
        assert result[1]["available"] == 5

        # Non-inventory item
        assert result[2]["item_id"] is None
        assert result[2]["sufficient"] == True
        assert result[2]["available"] == True

    def test_update_invoice_item_inventory_reference(self):
        """Test updating inventory reference for invoice item"""
        # Mock invoice item
        mock_invoice_item = Mock()
        mock_invoice_item.id = 1
        mock_invoice_item.inventory_item_id = None

        self.db.query.return_value.filter.return_value.first.return_value = mock_invoice_item

        # Mock inventory item
        mock_inventory_item = Mock()
        mock_inventory_item.id = 10
        mock_inventory_item.name = "Test Product"
        mock_inventory_item.unit_price = 29.99
        mock_inventory_item.unit_of_measure = "each"

        def mock_item_query(item_id):
            return mock_inventory_item if item_id == 10 else None

        self.inventory_service.get_item = mock_item_query

        result = self.integration_service.update_invoice_item_inventory_reference(1, 10, 1)

        assert result == True
        assert mock_invoice_item.inventory_item_id == 10
        assert mock_invoice_item.description == "Test Product"
        assert mock_invoice_item.price == 29.99
        assert mock_invoice_item.unit_of_measure == "each"

        self.db.commit.assert_called_once()
