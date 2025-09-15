"""
Comprehensive tests for inventory API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from models.models_per_tenant import InventoryItem, InventoryCategory, StockMovement, User
from schemas.inventory import (
    InventoryItemCreate, InventoryCategoryCreate,
    InventorySearchFilters, StockMovementCreate
)


class TestInventoryAPI:
    """Test inventory API endpoints"""

    def setup_method(self):
        """Setup test client and fixtures"""
        from main import app
        self.client = TestClient(app)
        self.test_user = {
            "email": "test@example.com",
            "id": 1,
            "is_active": True
        }

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_create_category_success(self, mock_get_service, mock_get_user):
        """Test successful category creation via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_category = Mock()
        mock_category.id = 1
        mock_category.name = "Test Category"
        mock_category.description = "Test description"
        mock_category.color = "#FF5733"
        mock_category.is_active = True
        mock_category.created_at = "2024-01-01T00:00:00Z"
        mock_category.updated_at = "2024-01-01T00:00:00Z"

        mock_service.create_category.return_value = mock_category
        mock_get_service.return_value = mock_service

        category_data = {
            "name": "Test Category",
            "description": "Test description",
            "color": "#FF5733"
        }

        response = self.client.post("/api/inventory/categories", json=category_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Category"
        assert data["description"] == "Test description"
        assert data["is_active"] == True

        mock_service.create_category.assert_called_once()

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_create_category_validation_error(self, mock_get_service, mock_get_user):
        """Test category creation with validation error"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_service.create_category.side_effect = ValueError("Category name already exists")
        mock_get_service.return_value = mock_service

        category_data = {
            "name": "Duplicate Category"
        }

        response = self.client.post("/api/inventory/categories", json=category_data)

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Category name already exists" in data["error"]

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_categories_success(self, mock_get_service, mock_get_user):
        """Test getting categories via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_categories = [
            Mock(id=1, name="Category 1", description="Desc 1", is_active=True),
            Mock(id=2, name="Category 2", description="Desc 2", is_active=True)
        ]
        mock_service.get_categories.return_value = mock_categories
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/categories")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Category 1"
        assert data[1]["name"] == "Category 2"

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_create_item_success(self, mock_get_service, mock_get_user):
        """Test successful item creation via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"
        mock_item.sku = "TEST-001"
        mock_item.unit_price = 29.99
        mock_item.track_stock = True
        mock_item.current_stock = 100
        mock_item.is_active = True

        mock_service.create_item.return_value = mock_item
        mock_get_service.return_value = mock_service

        item_data = {
            "name": "Test Item",
            "sku": "TEST-001",
            "unit_price": 29.99,
            "track_stock": True,
            "current_stock": 100,
            "unit_of_measure": "each"
        }

        response = self.client.post("/api/inventory/items", json=item_data)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Item"
        assert data["sku"] == "TEST-001"
        assert data["unit_price"] == 29.99

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_items_with_filters(self, mock_get_service, mock_get_user):
        """Test getting items with filters via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_items = [
            Mock(id=1, name="Item 1", sku="SKU-001", unit_price=10.99, is_active=True),
            Mock(id=2, name="Item 2", sku="SKU-002", unit_price=20.99, is_active=True)
        ]
        mock_service.get_items.return_value = mock_items
        mock_get_service.return_value = mock_service

        params = {
            "query": "test",
            "category_id": 1,
            "limit": 50,
            "skip": 0
        }

        response = self.client.get("/api/inventory/items", params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 50

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_search_items(self, mock_get_service, mock_get_user):
        """Test item search via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_items = [
            Mock(id=1, name="Search Result 1", sku="SR-001"),
            Mock(id=2, name="Search Result 2", sku="SR-002")
        ]
        mock_service.search_items.return_value = mock_items
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/items/search?q=laptop&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_item_not_found(self, mock_get_service, mock_get_user):
        """Test getting non-existent item via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_service.get_item.return_value = None
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/items/999")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_update_item_success(self, mock_get_service, mock_get_user):
        """Test successful item update via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Updated Item"
        mock_item.unit_price = 39.99

        mock_service.update_item.return_value = mock_item
        mock_get_service.return_value = mock_service

        update_data = {
            "name": "Updated Item",
            "unit_price": 39.99
        }

        response = self.client.put("/api/inventory/items/1", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Item"
        assert data["unit_price"] == 39.99

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_delete_item_success(self, mock_get_service, mock_get_user):
        """Test successful item deletion via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_service.delete_item.return_value = True
        mock_get_service.return_value = mock_service

        response = self.client.delete("/api/inventory/items/1")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "deleted" in data["message"].lower()

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_stock_service')
    def test_adjust_stock_success(self, mock_get_service, mock_get_user):
        """Test successful stock adjustment via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_movement = Mock()
        mock_movement.id = 1
        mock_movement.movement_type = "adjustment"
        mock_movement.quantity = 25

        mock_service.record_manual_adjustment.return_value = mock_movement
        mock_get_service.return_value = mock_service

        adjustment_data = {
            "quantity": 25,
            "reason": "Inventory count adjustment"
        }

        response = self.client.post("/api/inventory/items/1/stock/adjust", json=adjustment_data)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "adjusted" in data["message"].lower()

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_stock_service')
    def test_get_stock_movements(self, mock_get_service, mock_get_user):
        """Test getting stock movements via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_movements = [
            Mock(id=1, movement_type="purchase", quantity=50, movement_date="2024-01-01T00:00:00Z"),
            Mock(id=2, movement_type="sale", quantity=-10, movement_date="2024-01-02T00:00:00Z")
        ]
        mock_service.get_movement_history.return_value = mock_movements
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/items/1/stock/movements?limit=20")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["movement_type"] == "purchase"
        assert data[1]["movement_type"] == "sale"

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_low_stock_alerts(self, mock_get_service, mock_get_user):
        """Test getting low stock alerts via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_alerts = {
            'generated_at': '2024-01-01T00:00:00Z',
            'threshold_days': 30,
            'alerts': [
                {
                    'item_id': 1,
                    'item_name': 'Low Stock Item',
                    'alert_level': 'warning',
                    'days_until_empty': 15
                }
            ],
            'summary': {
                'total_items': 1,
                'critical_alerts': 0,
                'warning_alerts': 1,
                'normal_items': 0
            }
        }
        mock_service.get_low_stock_alerts.return_value = mock_alerts
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/alerts/low-stock?threshold_days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["threshold_days"] == 30
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["alert_level"] == "warning"
        assert data["summary"]["warning_alerts"] == 1

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_inventory_analytics(self, mock_get_service, mock_get_user):
        """Test getting inventory analytics via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_analytics = Mock()
        mock_analytics.total_items = 100
        mock_analytics.active_items = 95
        mock_analytics.low_stock_items = 5
        mock_analytics.total_value = 50000.00
        mock_analytics.currency = "USD"

        mock_service.get_inventory_analytics.return_value = mock_analytics
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 100
        assert data["active_items"] == 95
        assert data["low_stock_items"] == 5
        assert data["total_value"] == 50000.00

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_profitability_analysis(self, mock_get_service, mock_get_user):
        """Test getting profitability analysis via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_analysis = {
            'period': {
                'start_date': '2024-01-01T00:00:00Z',
                'end_date': '2024-01-31T23:59:59Z'
            },
            'summary': {
                'total_revenue': 10000.00,
                'total_cost': 6000.00,
                'total_profit': 4000.00,
                'overall_margin_percent': 40.0
            },
            'items': [
                {
                    'item_id': 1,
                    'item_name': 'Profitable Item',
                    'gross_profit': 2000.00,
                    'gross_margin_percent': 50.0
                }
            ]
        }
        mock_service.get_profitability_analysis.return_value = mock_analysis
        mock_get_service.return_value = mock_service

        params = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z"
        }

        response = self.client.get("/api/inventory/reports/profitability", params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_profit"] == 4000.00
        assert data["summary"]["overall_margin_percent"] == 40.0
        assert len(data["items"]) == 1

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_turnover_analysis(self, mock_get_service, mock_get_user):
        """Test getting inventory turnover analysis via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()
        mock_turnover = {
            'analysis_period_months': 12,
            'summary': {
                'total_inventory_value': 50000.00,
                'total_cogs': 30000.00,
                'overall_turnover_ratio': 0.6,
                'items_analyzed': 10
            },
            'turnover_categories': {
                'excellent': 2,
                'good': 3,
                'fair': 3,
                'slow': 1,
                'very_slow': 1
            },
            'items': [
                {
                    'item_id': 1,
                    'item_name': 'Fast Mover',
                    'turnover_ratio': 8.5,
                    'turnover_category': 'good'
                }
            ]
        }
        mock_service.get_inventory_turnover_analysis.return_value = mock_turnover
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/inventory/reports/turnover?months=12")

        assert response.status_code == 200
        data = response.json()
        assert data["analysis_period_months"] == 12
        assert data["summary"]["overall_turnover_ratio"] == 0.6
        assert data["turnover_categories"]["good"] == 3

    @patch('routers.inventory.get_current_user')
    @patch('routers.inventory.get_inventory_service')
    def test_get_dashboard_data(self, mock_get_service, mock_get_user):
        """Test getting inventory dashboard data via API"""
        mock_get_user.return_value = self.test_user

        mock_service = Mock()

        # Mock analytics
        mock_analytics = Mock()
        mock_analytics.total_items = 100
        mock_analytics.active_items = 95
        mock_analytics.low_stock_items = 5
        mock_analytics.total_value = 50000.00

        # Mock alerts
        mock_alerts = {
            'summary': {
                'critical_alerts': 1,
                'warning_alerts': 2,
                'normal_items': 92
            }
        }

        # Mock recent sales
        mock_recent_sales = Mock()
        mock_recent_sales.total_sold = 150
        mock_recent_sales.total_revenue = 7500.00
        mock_recent_sales.invoice_count = 12

        # Mock top selling items
        mock_top_items = [
            Mock(item_name="Best Seller", total_sold=50, total_revenue=2500.00),
            Mock(item_name="Second Best", total_sold=30, total_revenue=1500.00)
        ]

        mock_service.get_inventory_analytics.return_value = mock_analytics
        mock_service.get_low_stock_alerts.return_value = mock_alerts

        # Mock the dashboard query for recent sales
        with patch('routers.inventory.db') as mock_db:
            mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = mock_recent_sales

            # Mock top selling query
            mock_top_query = Mock()
            mock_top_query.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_top_items
            mock_db.query.return_value = mock_top_query

            response = self.client.get("/api/inventory/reports/dashboard")

            assert response.status_code == 200
            data = response.json()
            assert data["analytics"]["total_items"] == 100
            assert data["alerts"]["critical_alerts"] == 1
            assert data["recent_activity"]["total_sold"] == 150
            assert len(data["top_selling_items"]) == 2
