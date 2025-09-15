"""
Comprehensive end-to-end tests for the inventory management system
Demonstrates the complete workflow from setup to reporting
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from models.models_per_tenant import (
    InventoryItem, InventoryCategory, StockMovement,
    Invoice, InvoiceItem, Expense, User, Client
)
from services.inventory_service import InventoryService
from services.stock_movement_service import StockMovementService
from services.inventory_integration_service import InventoryIntegrationService
from schemas.inventory import (
    InventoryItemCreate, InventoryCategoryCreate,
    StockMovementCreate
)


class TestInventoryComprehensiveWorkflow:
    """End-to-end workflow tests for the complete inventory system"""

    def test_complete_inventory_lifecycle(self, db_session):
        """Test the complete inventory management lifecycle"""
        # Initialize services
        inventory_service = InventoryService(db_session)
        stock_service = StockMovementService(db_session)
        integration_service = InventoryIntegrationService(db_session)

        # === PHASE 1: Setup Categories and Items ===

        # Create categories
        electronics_cat = inventory_service.create_category(
            InventoryCategoryCreate(
                name="Electronics",
                description="Electronic devices and accessories",
                color="#4A90E2"
            )
        )

        office_cat = inventory_service.create_category(
            InventoryCategoryCreate(
                name="Office Supplies",
                description="Office and stationery items",
                color="#50E3C2"
            )
        )

        assert electronics_cat.id is not None
        assert office_cat.id is not None

        # Create inventory items
        laptop = inventory_service.create_item(
            InventoryItemCreate(
                name="Business Laptop",
                description="High-performance business laptop",
                sku="LT-001",
                category_id=electronics_cat.id,
                unit_price=1299.99,
                cost_price=900.00,
                currency="USD",
                track_stock=True,
                current_stock=25,
                minimum_stock=5,
                unit_of_measure="each",
                item_type="product"
            ),
            user_id=1
        )

        monitor = inventory_service.create_item(
            InventoryItemCreate(
                name="27-inch Monitor",
                description="4K Ultra HD Monitor",
                sku="MN-001",
                category_id=electronics_cat.id,
                unit_price=399.99,
                cost_price=280.00,
                currency="USD",
                track_stock=True,
                current_stock=15,
                minimum_stock=3,
                unit_of_measure="each",
                item_type="product"
            ),
            user_id=1
        )

        notebook = inventory_service.create_item(
            InventoryItemCreate(
                name="Legal Pad Notebook",
                description="College-ruled notebook",
                sku="NB-001",
                category_id=office_cat.id,
                unit_price=4.99,
                cost_price=2.50,
                currency="USD",
                track_stock=True,
                current_stock=100,
                minimum_stock=20,
                unit_of_measure="each",
                item_type="product"
            ),
            user_id=1
        )

        assert laptop.id is not None
        assert monitor.id is not None
        assert notebook.id is not None

        # === PHASE 2: Stock Management ===

        # Manual stock adjustments
        stock_service.record_manual_adjustment(
            laptop.id, 10, "Received new shipment", 1
        )

        stock_service.record_manual_adjustment(
            monitor.id, -2, "Damaged in transit", 1
        )

        # Verify stock levels
        updated_laptop = inventory_service.get_item(laptop.id)
        updated_monitor = inventory_service.get_item(monitor.id)

        assert updated_laptop.current_stock == 35  # 25 + 10
        assert updated_monitor.current_stock == 13  # 15 - 2

        # === PHASE 3: Invoice Integration ===

        # Create client
        client = Client(
            name="ABC Corporation",
            email="billing@abc.com",
            balance=0.0
        )
        db_session.add(client)
        db_session.commit()

        # Create invoice with inventory items
        invoice = Invoice(
            number="INV-2024-001",
            amount=0.0,  # Will be calculated
            currency="USD",
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            status="draft",
            client_id=client.id
        )
        db_session.add(invoice)
        db_session.flush()

        # Add invoice items using integration service
        laptop_item_data = integration_service.populate_invoice_item_from_inventory(
            laptop.id, 2
        )
        monitor_item_data = integration_service.populate_invoice_item_from_inventory(
            monitor.id, 1
        )

        # Create invoice items
        laptop_invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            inventory_item_id=laptop.id,
            description=laptop_item_data["description"],
            quantity=2,
            price=laptop_item_data["price"],
            amount=laptop_item_data["amount"],
            unit_of_measure=laptop_item_data["unit_of_measure"]
        )
        db_session.add(laptop_invoice_item)

        monitor_invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            inventory_item_id=monitor.id,
            description=monitor_item_data["description"],
            quantity=1,
            price=monitor_item_data["price"],
            amount=monitor_item_data["amount"],
            unit_of_measure=monitor_item_data["unit_of_measure"]
        )
        db_session.add(monitor_invoice_item)

        # Calculate invoice total
        total_amount = laptop_item_data["amount"] + monitor_item_data["amount"]
        invoice.amount = total_amount
        db_session.commit()

        assert invoice.amount == 1999.98  # (2 * 1299.99) + (1 * 399.99)

        # === PHASE 4: Invoice Completion and Stock Reduction ===

        # Complete the invoice (simulate payment)
        invoice.status = "paid"
        db_session.commit()

        # Process stock movements for the completed invoice
        movements = integration_service.process_invoice_stock_movements(invoice, 1)

        assert len(movements) == 2

        # Verify stock reductions
        final_laptop = inventory_service.get_item(laptop.id)
        final_monitor = inventory_service.get_item(monitor.id)

        assert final_laptop.current_stock == 33  # 35 - 2
        assert final_monitor.current_stock == 12  # 13 - 1

        # === PHASE 5: Expense Integration (Inventory Purchase) ===

        # Create user
        user = User(
            email="procurement@company.com",
            hashed_password="hashed_password",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()

        # Create inventory purchase expense
        purchase_expense = Expense(
            amount=500.00,  # 5 notebooks * $4.99 + tax/shipping
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="Office Supplies",
            vendor="Office Depot",
            is_inventory_purchase=True,
            inventory_items=[
                {
                    "item_id": notebook.id,
                    "quantity": 50,
                    "unit_cost": 4.99
                }
            ],
            status="recorded",
            user_id=user.id
        )
        db_session.add(purchase_expense)
        db_session.commit()

        # Process stock movements for the purchase
        purchase_movements = integration_service.process_expense_inventory_purchase(
            purchase_expense, user.id
        )

        assert len(purchase_movements) == 1

        # Verify stock increase
        final_notebook = inventory_service.get_item(notebook.id)
        assert final_notebook.current_stock == 150  # 100 + 50

        # === PHASE 6: Analytics and Reporting ===

        # Test inventory analytics
        analytics = inventory_service.get_inventory_analytics()
        assert analytics.total_items == 3
        assert analytics.active_items == 3
        assert analytics.total_value > 0

        # Test profitability analysis
        profitability = inventory_service.get_profitability_analysis()
        assert "summary" in profitability
        assert "items" in profitability
        assert profitability["summary"]["total_revenue"] == 1999.98
        assert profitability["summary"]["total_profit"] > 0

        # Test low stock alerts
        alerts = inventory_service.get_low_stock_alerts(threshold_days=60)
        assert "alerts" in alerts
        assert "summary" in alerts

        # Test category performance
        category_report = inventory_service.get_category_performance_report()
        assert len(category_report["categories"]) == 2
        assert category_report["summary"]["total_categories"] == 2

        # === PHASE 7: Stock Movement Audit Trail ===

        # Get stock movement history
        laptop_movements = stock_service.get_movement_history(laptop.id)
        assert len(laptop_movements) >= 3  # Initial + manual adjustment + sale

        # Get movements by reference
        invoice_movements = stock_service.get_movements_by_reference("invoice", invoice.id)
        assert len(invoice_movements) == 2

        # Verify audit trail completeness
        audit_trail = stock_service.get_audit_trail(laptop.id)
        assert len(audit_trail) >= 3

        # Verify stock consistency
        final_audit_stock = audit_trail[-1]["current_stock"] if audit_trail else 0
        assert final_audit_stock == final_laptop.current_stock

        # === PHASE 8: Invoice Cancellation and Stock Reversal ===

        # Cancel the invoice
        invoice.status = "cancelled"
        db_session.commit()

        # Reverse stock movements
        reversal_movements = integration_service.reverse_invoice_stock_movements(invoice, 1)
        assert len(reversal_movements) == 2

        # Verify stock restoration
        restored_laptop = inventory_service.get_item(laptop.id)
        restored_monitor = inventory_service.get_item(monitor.id)

        assert restored_laptop.current_stock == 35  # Back to pre-sale level
        assert restored_monitor.current_stock == 13  # Back to pre-sale level

        print("🎉 Complete inventory lifecycle test passed!")
        print(f"📊 Final stock levels:")
        print(f"   • Laptop: {restored_laptop.current_stock} units")
        print(f"   • Monitor: {restored_monitor.current_stock} units")
        print(f"   • Notebook: {final_notebook.current_stock} units")
        print(f"💰 Total revenue processed: ${profitability['summary']['total_revenue']}")
        print(f"📈 Total profit: ${profitability['summary']['total_profit']}")

    def test_inventory_edge_cases_and_error_handling(self, db_session):
        """Test edge cases and error handling scenarios"""
        inventory_service = InventoryService(db_session)
        stock_service = StockMovementService(db_session)
        integration_service = InventoryIntegrationService(db_session)

        # === Test: Duplicate SKU Handling ===
        category = inventory_service.create_category(
            InventoryCategoryCreate(name="Test Category")
        )

        # Create first item
        item1 = inventory_service.create_item(
            InventoryItemCreate(
                name="Test Item 1",
                sku="DUPLICATE-SKU",
                unit_price=10.00,
                track_stock=False,
                current_stock=0,
                unit_of_measure="each"
            ),
            user_id=1
        )

        # Try to create item with duplicate SKU
        with pytest.raises(ValueError):
            inventory_service.create_item(
                InventoryItemCreate(
                    name="Test Item 2",
                    sku="DUPLICATE-SKU",
                    unit_price=20.00,
                    track_stock=False,
                    current_stock=0,
                    unit_of_measure="each"
                ),
                user_id=1
            )

        # === Test: Insufficient Stock Prevention ===
        stock_item = inventory_service.create_item(
            InventoryItemCreate(
                name="Limited Stock Item",
                sku="LIMITED-001",
                unit_price=50.00,
                track_stock=True,
                current_stock=5,
                unit_of_measure="each"
            ),
            user_id=1
        )

        # Try to sell more than available stock
        with pytest.raises(ValueError):
            stock_service.record_movement(StockMovementCreate(
                item_id=stock_item.id,
                movement_type="sale",
                quantity=-10,  # More than available
                user_id=1
            ))

        # === Test: Non-stock Item Operations ===
        non_stock_item = inventory_service.create_item(
            InventoryItemCreate(
                name="Service Item",
                sku="SERVICE-001",
                unit_price=100.00,
                track_stock=False,
                current_stock=0,
                unit_of_measure="hours",
                item_type="service"
            ),
            user_id=1
        )

        # Should be able to "sell" service items without stock tracking
        movement = stock_service.record_movement(StockMovementCreate(
            item_id=non_stock_item.id,
            movement_type="sale",
            quantity=-5,
            user_id=1
        ))

        assert movement.quantity == -5
        # Stock should remain 0 for non-tracked items
        updated_item = inventory_service.get_item(non_stock_item.id)
        assert updated_item.current_stock == 0

        # === Test: Category Deletion with Items ===
        category_with_items = inventory_service.create_category(
            InventoryCategoryCreate(name="Category With Items")
        )

        inventory_service.create_item(
            InventoryItemCreate(
                name="Item in Category",
                sku="CAT-001",
                category_id=category_with_items.id,
                unit_price=25.00,
                track_stock=False,
                current_stock=0,
                unit_of_measure="each"
            ),
            user_id=1
        )

        # Should not be able to delete category with items
        with pytest.raises(ValueError):
            inventory_service.delete_category(category_with_items.id)

        # === Test: Item Deletion with References ===
        referenced_item = inventory_service.create_item(
            InventoryItemCreate(
                name="Referenced Item",
                sku="REF-001",
                unit_price=30.00,
                track_stock=False,
                current_stock=0,
                unit_of_measure="each"
            ),
            user_id=1
        )

        # Create an invoice item referencing this item
        client = Client(name="Test Client", email="test@example.com")
        db_session.add(client)

        invoice = Invoice(
            number="TEST-INV-001",
            amount=30.00,
            currency="USD",
            due_date=datetime.now(timezone.utc),
            status="draft"
        )
        db_session.add(invoice)
        db_session.flush()

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            inventory_item_id=referenced_item.id,
            description="Referenced Item",
            quantity=1,
            price=30.00,
            amount=30.00
        )
        db_session.add(invoice_item)
        db_session.commit()

        # Should not be able to delete item with references
        with pytest.raises(ValueError):
            inventory_service.delete_item(referenced_item.id, user_id=1)

        print("✅ All edge cases and error handling tests passed!")

    def test_inventory_performance_and_scalability(self, db_session):
        """Test inventory system performance with larger datasets"""
        inventory_service = InventoryService(db_session)

        # Create multiple categories and items for performance testing
        categories = []
        for i in range(5):
            category = inventory_service.create_category(
                InventoryCategoryCreate(
                    name=f"Performance Category {i+1}",
                    description=f"Category for performance testing {i+1}"
                )
            )
            categories.append(category)

        # Create multiple items across categories
        items = []
        for i in range(50):
            category_id = categories[i % len(categories)].id
            item = inventory_service.create_item(
                InventoryItemCreate(
                    name=f"Performance Item {i+1:03d}",
                    sku=f"PERF-{i+1:03d}",
                    category_id=category_id,
                    unit_price=10.00 + i,
                    cost_price=7.00 + i * 0.7,
                    currency="USD",
                    track_stock=True,
                    current_stock=100 + i * 2,
                    minimum_stock=10 + i // 5,
                    unit_of_measure="each"
                ),
                user_id=1
            )
            items.append(item)

        # Test bulk operations performance
        start_time = datetime.now(timezone.utc)

        # Get all items
        all_items = inventory_service.get_items()
        assert len(all_items) >= 50

        # Test search performance
        search_results = inventory_service.search_items("Performance")
        assert len(search_results) >= 50

        # Test analytics performance
        analytics = inventory_service.get_inventory_analytics()
        assert analytics.total_items >= 50

        # Test low stock alerts performance
        alerts = inventory_service.get_low_stock_alerts()
        assert len(alerts["alerts"]) >= 0

        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()

        print(f"⏱️  Performance test completed in {execution_time:.2f} seconds")
        print(f"📊 Processed {len(items)} items across {len(categories)} categories")
        print(f"🔍 Search returned {len(search_results)} results")
        print(f"📈 Analytics processed {analytics.total_items} total items")

        # Performance assertions (adjust based on environment)
        assert execution_time < 30.0, f"Performance test took too long: {execution_time}s"
        assert len(all_items) >= 50, "Not all items were created/retrieved"

        print("✅ Performance and scalability tests passed!")
