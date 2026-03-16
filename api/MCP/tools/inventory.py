"""
Inventory management-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# === Inventory Management Argument Schemas ===

class ListInventoryCategoriesArgs(BaseModel):
    active_only: bool = Field(default=True, description="Return only active categories")

class CreateInventoryCategoryArgs(BaseModel):
    name: str = Field(description="Category name")
    description: Optional[str] = Field(default=None, description="Category description")
    is_active: bool = Field(default=True, description="Whether category is active")

class UpdateInventoryCategoryArgs(BaseModel):
    category_id: int = Field(description="ID of category to update")
    name: Optional[str] = Field(default=None, description="New category name")
    description: Optional[str] = Field(default=None, description="New category description")
    is_active: Optional[bool] = Field(default=None, description="Whether category is active")

class ListInventoryItemsArgs(BaseModel):
    skip: int = Field(default=0, description="Number of items to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of items to return")
    query: Optional[str] = Field(default=None, description="Search query for items")
    category_id: Optional[int] = Field(default=None, description="Filter by category ID")
    item_type: Optional[str] = Field(default=None, description="Filter by item type")
    low_stock_only: bool = Field(default=False, description="Return only low stock items")
    track_stock: Optional[bool] = Field(default=None, description="Filter by stock tracking")

class CreateInventoryItemArgs(BaseModel):
    name: str = Field(description="Item name")
    sku: Optional[str] = Field(default=None, description="Stock Keeping Unit")
    description: Optional[str] = Field(default=None, description="Item description")
    category_id: Optional[int] = Field(default=None, description="Category ID")
    unit_price: float = Field(description="Unit selling price")
    cost_price: Optional[float] = Field(default=None, description="Unit cost price")
    currency: str = Field(default="USD", description="Currency code")
    track_stock: bool = Field(default=True, description="Whether to track stock levels")
    current_stock: float = Field(default=0, description="Current stock quantity")
    minimum_stock: float = Field(default=0, description="Minimum stock level")
    unit_of_measure: str = Field(default="each", description="Unit of measure")
    item_type: str = Field(default="product", description="Type of item")
    is_active: bool = Field(default=True, description="Whether item is active")

class UpdateInventoryItemArgs(BaseModel):
    item_id: int = Field(description="ID of item to update")
    name: Optional[str] = Field(default=None, description="New item name")
    sku: Optional[str] = Field(default=None, description="New SKU")
    description: Optional[str] = Field(default=None, description="New description")
    category_id: Optional[int] = Field(default=None, description="New category ID")
    unit_price: Optional[float] = Field(default=None, description="New unit price")
    cost_price: Optional[float] = Field(default=None, description="New cost price")
    currency: Optional[str] = Field(default=None, description="New currency")
    track_stock: Optional[bool] = Field(default=None, description="New stock tracking setting")
    current_stock: Optional[float] = Field(default=None, description="New current stock")
    minimum_stock: Optional[float] = Field(default=None, description="New minimum stock")
    unit_of_measure: Optional[str] = Field(default=None, description="New unit of measure")
    item_type: Optional[str] = Field(default=None, description="New item type")
    is_active: Optional[bool] = Field(default=None, description="New active status")

class AdjustStockArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    quantity: float = Field(description="Quantity to adjust (positive for increase, negative for decrease)")
    reason: str = Field(default="Manual adjustment", description="Reason for adjustment")

class GetInventoryAnalyticsArgs(BaseModel):
    pass  # No arguments needed for analytics

class GetLowStockItemsArgs(BaseModel):
    pass  # No arguments needed for low stock list


# === Advanced Analytics & Reporting Schemas ===

class GetAdvancedInventoryAnalyticsArgs(BaseModel):
    start_date: Optional[str] = Field(default=None, description="Start date for analysis (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date for analysis (YYYY-MM-DD)")


class GetSalesVelocityAnalysisArgs(BaseModel):
    days: int = Field(default=30, ge=7, le=365, description="Analysis period in days")


class GetInventoryForecastingArgs(BaseModel):
    forecast_days: int = Field(default=90, ge=30, le=365, description="Forecast period in days")


class GetInventoryValueReportArgs(BaseModel):
    pass  # No arguments needed


class GetProfitabilityAnalysisArgs(BaseModel):
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")


class GetInventoryTurnoverAnalysisArgs(BaseModel):
    months: int = Field(default=12, ge=1, le=24, description="Analysis period in months")


class GetCategoryPerformanceReportArgs(BaseModel):
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")


class GetLowStockAlertsArgs(BaseModel):
    threshold_days: int = Field(default=30, ge=1, le=365, description="Days threshold for alerts")


class GetInventoryDashboardDataArgs(BaseModel):
    pass  # No arguments needed


class GetStockMovementSummaryArgs(BaseModel):
    item_id: Optional[int] = Field(default=None, description="Item ID to filter by")
    days: int = Field(default=30, ge=1, le=365, description="Analysis period in days")


# === Import/Export Schemas ===

class ImportInventoryCSVArgs(BaseModel):
    file_path: str = Field(description="Path to CSV file to import")


class ExportInventoryCSVArgs(BaseModel):
    include_inactive: bool = Field(default=False, description="Include inactive items")
    category_id: Optional[int] = Field(default=None, description="Filter by category ID")


# === Barcode Management Schemas ===

class GetItemByBarcodeArgs(BaseModel):
    barcode: str = Field(description="Barcode to search for")


class UpdateItemBarcodeArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    barcode: str = Field(description="Barcode value")
    barcode_type: Optional[str] = Field(default=None, description="Barcode type (UPC, EAN, etc.)")
    barcode_format: Optional[str] = Field(default=None, description="Barcode format (1D, 2D)")


class ValidateBarcodeArgs(BaseModel):
    barcode: str = Field(description="Barcode to validate")


class GenerateBarcodeSuggestionsArgs(BaseModel):
    item_name: str = Field(description="Item name for generating suggestions")
    sku: Optional[str] = Field(default=None, description="SKU for generating suggestions")


class BulkUpdateBarcodesArgs(BaseModel):
    barcode_updates: List[Dict[str, Any]] = Field(description="List of barcode updates")


# === Integration Schemas ===

class PopulateInvoiceItemFromInventoryArgs(BaseModel):
    inventory_item_id: int = Field(description="ID of inventory item")
    quantity: float = Field(default=1.0, gt=0, description="Quantity to populate")


class ValidateInvoiceStockAvailabilityArgs(BaseModel):
    invoice_items: List[Dict[str, Any]] = Field(description="List of invoice items to validate")


class GetInvoiceInventorySummaryArgs(BaseModel):
    invoice_id: int = Field(description="ID of invoice")


class CreateInventoryPurchaseExpenseArgs(BaseModel):
    purchase_data: Dict[str, Any] = Field(description="Purchase data including items and vendor info")


class GetInventoryPurchaseSummaryArgs(BaseModel):
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    vendor: Optional[str] = Field(default=None, description="Filter by vendor")


class GetExpenseInventorySummaryArgs(BaseModel):
    expense_id: int = Field(description="ID of expense")


class GetLinkedInvoicesForInventoryItemArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")


class GetInventoryItemStockSummaryArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    days: int = Field(default=30, ge=1, le=365, description="Analysis period in days")


# === Additional Stock Management Schemas ===

class GetRecentMovementsArgs(BaseModel):
    days: int = Field(default=7, ge=1, le=365, description="Days to look back")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum movements to return")


class CheckStockAvailabilityArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    requested_quantity: float = Field(..., gt=0, description="Quantity to check availability for")


# === Inventory Attachments Schemas ===

class UploadAttachmentArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    file_path: str = Field(description="Path to file to upload")
    attachment_type: Optional[str] = Field(None, description="Attachment type: 'image' or 'document'")
    document_type: Optional[str] = Field(None, description="Document type (for documents)")
    description: Optional[str] = Field(None, description="Optional description")


class GetAttachmentsArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_type: Optional[str] = Field(None, description="Filter by attachment type")


class GetAttachmentArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of attachment")


class UpdateAttachmentArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of attachment")
    description: Optional[str] = Field(None, description="New description")
    document_type: Optional[str] = Field(None, description="New document type")
    alt_text: Optional[str] = Field(None, description="New alt text for images")
    display_order: Optional[int] = Field(None, description="New display order")


class DeleteAttachmentArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of attachment")


class SetPrimaryImageArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of image attachment to set as primary")


class ReorderAttachmentsArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_orders: List[Dict[str, Any]] = Field(description="List of attachment orders with attachment_id and order")


class GetThumbnailArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of attachment")
    size: str = Field(description="Thumbnail size (e.g., '150x150')")


class DownloadAttachmentArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")
    attachment_id: int = Field(description="ID of attachment")


class GetStorageUsageArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item (for tenant context)")


class GetPrimaryImageArgs(BaseModel):
    item_id: int = Field(description="ID of inventory item")


class InventoryToolsMixin:
    # === Inventory Management Tools ===

    async def list_inventory_categories(self, active_only: bool = True) -> Dict[str, Any]:
        """List all inventory categories"""
        try:
            # Call inventory API endpoint
            response = await self.api_client._make_request("GET", "/inventory/categories", params={"active_only": active_only})
            return {
                "success": True,
                "data": response.get("data", []),
                "count": len(response.get("data", [])),
                "active_only": active_only
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list inventory categories: {e}"}

    async def create_inventory_category(self, name: str, description: Optional[str] = None, is_active: bool = True) -> Dict[str, Any]:
        """Create a new inventory category"""
        try:
            category_data = {"name": name, "is_active": is_active}
            if description:
                category_data["description"] = description

            response = await self.api_client._make_request("POST", "/inventory/categories", json=category_data)
            return {
                "success": True,
                "data": response.get("data", {}),
                "message": "Inventory category created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create inventory category: {e}"}

    async def update_inventory_category(self, category_id: int, name: Optional[str] = None, description: Optional[str] = None, is_active: Optional[bool] = None) -> Dict[str, Any]:
        """Update an inventory category"""
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if is_active is not None:
                update_data["is_active"] = is_active

            response = await self.api_client._make_request("PUT", f"/inventory/categories/{category_id}", json=update_data)
            return {
                "success": True,
                "data": response.get("data", {}),
                "message": "Inventory category updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update inventory category: {e}"}

    async def list_inventory_items(
        self,
        skip: int = 0,
        limit: int = 100,
        query: Optional[str] = None,
        category_id: Optional[int] = None,
        item_type: Optional[str] = None,
        low_stock_only: bool = False,
        track_stock: Optional[bool] = None
    ) -> Dict[str, Any]:
        """List inventory items with optional filtering"""
        try:
            params = {
                "skip": skip,
                "limit": limit,
                "low_stock_only": low_stock_only
            }
            if query:
                params["query"] = query
            if category_id:
                params["category_id"] = category_id
            if item_type:
                params["item_type"] = item_type
            if track_stock is not None:
                params["track_stock"] = track_stock

            response = await self.api_client._make_request("GET", "/inventory/items", params=params)
            return {
                "success": True,
                "data": response.get("items", []),
                "total": response.get("total", 0),
                "count": len(response.get("items", [])),
                "pagination": {
                    "skip": skip,
                    "limit": limit,
                    "has_more": len(response.get("items", [])) == limit
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list inventory items: {e}"}

    async def create_inventory_item(
        self,
        name: str,
        unit_price: float,
        sku: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        cost_price: Optional[float] = None,
        currency: str = "USD",
        track_stock: bool = True,
        current_stock: float = 0,
        minimum_stock: float = 0,
        unit_of_measure: str = "each",
        item_type: str = "product",
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Create a new inventory item"""
        try:
            item_data = {
                "name": name,
                "unit_price": unit_price,
                "currency": currency,
                "track_stock": track_stock,
                "current_stock": current_stock,
                "minimum_stock": minimum_stock,
                "unit_of_measure": unit_of_measure,
                "item_type": item_type,
                "is_active": is_active
            }
            if sku:
                item_data["sku"] = sku
            if description:
                item_data["description"] = description
            if category_id:
                item_data["category_id"] = category_id
            if cost_price:
                item_data["cost_price"] = cost_price

            response = await self.api_client._make_request("POST", "/inventory/items", json=item_data)
            return {
                "success": True,
                "data": response.get("data", {}),
                "message": "Inventory item created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create inventory item: {e}"}

    async def update_inventory_item(
        self,
        item_id: int,
        name: Optional[str] = None,
        sku: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        unit_price: Optional[float] = None,
        cost_price: Optional[float] = None,
        currency: Optional[str] = None,
        track_stock: Optional[bool] = None,
        current_stock: Optional[float] = None,
        minimum_stock: Optional[float] = None,
        unit_of_measure: Optional[str] = None,
        item_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an inventory item"""
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if sku is not None:
                update_data["sku"] = sku
            if description is not None:
                update_data["description"] = description
            if category_id is not None:
                update_data["category_id"] = category_id
            if unit_price is not None:
                update_data["unit_price"] = unit_price
            if cost_price is not None:
                update_data["cost_price"] = cost_price
            if currency is not None:
                update_data["currency"] = currency
            if track_stock is not None:
                update_data["track_stock"] = track_stock
            if current_stock is not None:
                update_data["current_stock"] = current_stock
            if minimum_stock is not None:
                update_data["minimum_stock"] = minimum_stock
            if unit_of_measure is not None:
                update_data["unit_of_measure"] = unit_of_measure
            if item_type is not None:
                update_data["item_type"] = item_type
            if is_active is not None:
                update_data["is_active"] = is_active

            response = await self.api_client._make_request("PUT", f"/inventory/items/{item_id}", json=update_data)
            return {
                "success": True,
                "data": response.get("data", {}),
                "message": "Inventory item updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update inventory item: {e}"}

    async def adjust_stock(self, item_id: int, quantity: float, reason: str = "Manual adjustment") -> Dict[str, Any]:
        """Adjust stock levels for an inventory item"""
        try:
            response = await self.api_client._make_request(
                "POST",
                f"/inventory/items/{item_id}/stock/adjust",
                json={"quantity": quantity, "reason": reason}
            )
            return {
                "success": True,
                "data": response,
                "message": "Stock adjusted successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to adjust stock: {e}"}

    async def get_inventory_analytics(self) -> Dict[str, Any]:
        """Get inventory analytics and statistics"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/analytics")
            return {
                "success": True,
                "data": response.get("data", {}),
                "message": "Inventory analytics retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory analytics: {e}"}

    async def get_low_stock_items(self) -> Dict[str, Any]:
        """Get items with low stock levels"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/stock/low-stock")
            return {
                "success": True,
                "data": response,
                "count": len(response),
                "message": f"Found {len(response)} low stock items"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get low stock items: {e}"}

    # === Advanced Analytics & Reporting Tools ===

    async def get_advanced_inventory_analytics(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get advanced inventory analytics with trends and insights"""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await self.api_client._make_request("GET", "/inventory/analytics/advanced", params=params)
            return {
                "success": True,
                "data": response,
                "message": "Advanced inventory analytics retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get advanced inventory analytics: {e}"}

    async def get_sales_velocity_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Get sales velocity analysis for inventory forecasting"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/analytics/sales-velocity", params={"days": days})
            return {
                "success": True,
                "data": response,
                "analysis_period_days": days,
                "message": f"Sales velocity analysis for the past {days} days"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get sales velocity analysis: {e}"}

    async def get_inventory_forecasting(self, forecast_days: int = 90) -> Dict[str, Any]:
        """Get inventory forecasting based on historical data"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/analytics/forecasting", params={"forecast_days": forecast_days})
            return {
                "success": True,
                "data": response,
                "forecast_period_days": forecast_days,
                "message": f"Inventory forecast for the next {forecast_days} days"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory forecasting: {e}"}

    async def get_inventory_value_report(self) -> Dict[str, Any]:
        """Get detailed inventory value report"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/reports/value")
            return {
                "success": True,
                "data": response,
                "message": "Inventory value report retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory value report: {e}"}

    async def get_profitability_analysis(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed profitability analysis for inventory items"""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await self.api_client._make_request("GET", "/inventory/reports/profitability", params=params)
            return {
                "success": True,
                "data": response,
                "message": "Profitability analysis retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get profitability analysis: {e}"}

    async def get_inventory_turnover_analysis(self, months: int = 12) -> Dict[str, Any]:
        """Get inventory turnover analysis"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/reports/turnover", params={"months": months})
            return {
                "success": True,
                "data": response,
                "analysis_period_months": months,
                "message": f"Inventory turnover analysis for the past {months} months"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory turnover analysis: {e}"}

    async def get_category_performance_report(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get performance report by inventory categories"""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await self.api_client._make_request("GET", "/inventory/reports/categories", params=params)
            return {
                "success": True,
                "data": response,
                "message": "Category performance report retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get category performance report: {e}"}

    async def get_low_stock_alerts(self, threshold_days: int = 30) -> Dict[str, Any]:
        """Get low stock alerts based on sales velocity"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/alerts/low-stock", params={"threshold_days": threshold_days})
            return {
                "success": True,
                "data": response,
                "threshold_days": threshold_days,
                "message": f"Low stock alerts for {threshold_days} days threshold"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get low stock alerts: {e}"}

    async def get_inventory_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data for inventory overview"""
        try:
            response = await self.api_client._make_request("GET", "/inventory/reports/dashboard")
            return {
                "success": True,
                "data": response,
                "message": "Inventory dashboard data retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory dashboard data: {e}"}

    async def get_stock_movement_summary(self, item_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """Get stock movement summary report"""
        try:
            params = {"days": days}
            if item_id:
                params["item_id"] = item_id

            response = await self.api_client._make_request("GET", "/inventory/reports/stock-movements", params=params)
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "analysis_period_days": days,
                "message": f"Stock movement summary for the past {days} days"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get stock movement summary: {e}"}

    # === Import/Export Tools ===

    async def import_inventory_csv(self, file_path: str) -> Dict[str, Any]:
        """Import inventory items from CSV file"""
        try:
            # Validate file path before reading
            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(file_path)

            # Read the file content
            with open(validated_path, 'rb') as f:
                file_content = f.read()

            # Create multipart form data
            files = {"file": (file_path.split('/')[-1], file_content, "text/csv")}

            response = await self.api_client._make_request("POST", "/inventory/import/csv", files=files)
            return {
                "success": True,
                "data": response,
                "message": "CSV import completed successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to import inventory CSV: {e}"}

    async def export_inventory_csv(self, include_inactive: bool = False, category_id: Optional[int] = None) -> Dict[str, Any]:
        """Export inventory items to CSV format"""
        try:
            params = {"include_inactive": include_inactive}
            if category_id:
                params["category_id"] = category_id

            response = await self.api_client._make_request("GET", "/inventory/export/csv", params=params)
            return {
                "success": True,
                "data": response.decode('utf-8') if isinstance(response, bytes) else response,
                "include_inactive": include_inactive,
                "category_id": category_id,
                "message": "Inventory CSV export completed successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to export inventory CSV: {e}"}

    # === Barcode Management Tools ===

    async def get_item_by_barcode(self, barcode: str) -> Dict[str, Any]:
        """Get inventory item by barcode"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/items/barcode/{barcode}")
            return {
                "success": True,
                "data": response,
                "barcode": barcode,
                "message": "Item retrieved by barcode successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get item by barcode: {e}"}

    async def update_item_barcode(self, item_id: int, barcode: str, barcode_type: Optional[str] = None, barcode_format: Optional[str] = None) -> Dict[str, Any]:
        """Update barcode for an inventory item"""
        try:
            update_data = {"barcode": barcode}
            if barcode_type:
                update_data["barcode_type"] = barcode_type
            if barcode_format:
                update_data["barcode_format"] = barcode_format

            response = await self.api_client._make_request("POST", f"/inventory/items/{item_id}/barcode", json=update_data)
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "barcode": barcode,
                "message": "Item barcode updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update item barcode: {e}"}

    async def validate_barcode(self, barcode: str) -> Dict[str, Any]:
        """Validate a barcode and detect its type"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/barcode/validate", json={"barcode": barcode})
            return {
                "success": True,
                "data": response,
                "barcode": barcode,
                "message": "Barcode validation completed"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to validate barcode: {e}"}

    async def generate_barcode_suggestions(self, item_name: str, sku: Optional[str] = None) -> Dict[str, Any]:
        """Generate barcode suggestions based on item information"""
        try:
            params = {"item_name": item_name}
            if sku:
                params["sku"] = sku

            response = await self.api_client._make_request("GET", "/inventory/barcode/suggestions", params=params)
            return {
                "success": True,
                "data": response,
                "item_name": item_name,
                "sku": sku,
                "message": "Barcode suggestions generated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to generate barcode suggestions: {e}"}

    async def bulk_update_barcodes(self, barcode_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk update barcodes for multiple items"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/barcode/bulk-update", json={"barcode_updates": barcode_updates})
            return {
                "success": True,
                "data": response,
                "update_count": len(barcode_updates),
                "message": "Bulk barcode update completed"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to bulk update barcodes: {e}"}

    # === Integration Tools ===

    async def populate_invoice_item_from_inventory(self, inventory_item_id: int, quantity: float = 1.0) -> Dict[str, Any]:
        """Populate invoice item data from inventory item"""
        try:
            params = {"inventory_item_id": inventory_item_id, "quantity": quantity}
            response = await self.api_client._make_request("POST", "/inventory/invoice-items/populate", params=params)
            return {
                "success": True,
                "data": response,
                "inventory_item_id": inventory_item_id,
                "quantity": quantity,
                "message": "Invoice item populated from inventory successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to populate invoice item from inventory: {e}"}

    async def validate_invoice_stock_availability(self, invoice_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate stock availability for invoice items"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/invoice-items/validate-stock", json={"invoice_items": invoice_items})
            return {
                "success": True,
                "data": response,
                "item_count": len(invoice_items),
                "message": "Invoice stock validation completed"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to validate invoice stock availability: {e}"}

    async def get_invoice_inventory_summary(self, invoice_id: int) -> Dict[str, Any]:
        """Get inventory summary for an invoice"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/invoice/{invoice_id}/inventory-summary")
            return {
                "success": True,
                "data": response,
                "invoice_id": invoice_id,
                "message": "Invoice inventory summary retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get invoice inventory summary: {e}"}

    async def create_inventory_purchase_expense(self, purchase_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an expense for inventory purchase with automatic stock updates"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/expenses/purchase", json=purchase_data)
            return {
                "success": True,
                "data": response,
                "message": "Inventory purchase expense created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create inventory purchase expense: {e}"}

    async def get_inventory_purchase_summary(self, start_date: Optional[str] = None, end_date: Optional[str] = None, vendor: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of inventory purchases"""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if vendor:
                params["vendor"] = vendor

            response = await self.api_client._make_request("GET", "/inventory/expenses/purchase-summary", params=params)
            return {
                "success": True,
                "data": response,
                "start_date": start_date,
                "end_date": end_date,
                "vendor": vendor,
                "message": "Inventory purchase summary retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory purchase summary: {e}"}

    async def get_expense_inventory_summary(self, expense_id: int) -> Dict[str, Any]:
        """Get inventory summary for an expense"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/expense/{expense_id}/inventory-summary")
            return {
                "success": True,
                "data": response,
                "expense_id": expense_id,
                "message": "Expense inventory summary retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get expense inventory summary: {e}"}

    async def get_linked_invoices_for_inventory_item(self, item_id: int) -> Dict[str, Any]:
        """Get all invoices that contain this inventory item"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/items/{item_id}/linked-invoices")
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "invoice_count": len(response),
                "message": f"Found {len(response)} linked invoices for inventory item"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get linked invoices for inventory item: {e}"}

    async def get_inventory_item_stock_summary(self, item_id: int, days: int = 30) -> Dict[str, Any]:
        """Get stock movement summary for an inventory item, grouped by reference type"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/items/{item_id}/stock-movement-summary", params={"days": days})
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "analysis_period_days": days,
                "message": "Inventory item stock summary retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory item stock summary: {e}"}

    # === Additional Stock Management Tools ===

    async def get_recent_movements(self, days: int = 7, limit: int = 50) -> Dict[str, Any]:
        """Get recent stock movements across all items"""
        try:
            params = {"days": days, "limit": limit}
            response = await self.api_client._make_request("GET", "/inventory/movements/recent", params=params)
            return {
                "success": True,
                "data": response,
                "movement_count": len(response),
                "period_days": days,
                "limit": limit,
                "message": f"Found {len(response)} recent stock movements"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get recent movements: {e}"}

    async def check_stock_availability(self, item_id: int, requested_quantity: float) -> Dict[str, Any]:
        """Check if requested quantity is available for an item"""
        try:
            params = {"requested_quantity": requested_quantity}
            response = await self.api_client._make_request("GET", f"/inventory/items/{item_id}/availability", params=params)
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "requested_quantity": requested_quantity,
                "message": "Stock availability check completed"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to check stock availability: {e}"}

    # === Bulk Operations Tools ===

    async def create_inventory_categories_bulk(self, categories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple inventory categories at once"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/categories/bulk", json={"categories": categories})
            return {
                "success": True,
                "data": response,
                "count": len(categories),
                "message": f"Successfully created {len(categories)} inventory categories"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create inventory categories bulk: {e}"}

    async def create_inventory_items_bulk(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple inventory items at once"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/items/bulk", json={"items": items})
            return {
                "success": True,
                "data": response,
                "count": len(items),
                "message": f"Successfully created {len(items)} inventory items"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create inventory items bulk: {e}"}

    async def create_stock_movements_bulk(self, movements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple stock movements at once"""
        try:
            response = await self.api_client._make_request("POST", "/inventory/stock-movements/bulk", json={"movements": movements})
            return {
                "success": True,
                "data": response,
                "count": len(movements),
                "message": f"Successfully created {len(movements)} stock movements"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create stock movements bulk: {e}"}

    # === Search and Filtering Tools ===

    async def search_inventory_items(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """Search inventory items"""
        try:
            params = {"q": query, "limit": limit}
            response = await self.api_client._make_request("GET", "/inventory/items/search", params=params)

            # Extract results from response
            results = self._extract_items_from_response(response, ["results", "items", "data"])

            return {
                "success": True,
                "data": results,
                "query": query,
                "limit": limit,
                "result_count": len(results),
                "message": f"Found {len(results)} items matching '{query}'"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to search inventory items: {e}"}

    async def get_inventory_item_movements(self, item_id: int, limit: int = 50, movement_type: Optional[str] = None) -> Dict[str, Any]:
        """Get stock movement history for an item"""
        try:
            params = {"limit": limit}
            if movement_type:
                params["movement_type"] = movement_type

            response = await self.api_client._make_request("GET", f"/inventory/items/{item_id}/stock/movements", params=params)
            return {
                "success": True,
                "data": response,
                "item_id": item_id,
                "movement_count": len(response),
                "movement_type": movement_type,
                "limit": limit,
                "message": f"Found {len(response)} stock movements for item {item_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get inventory item movements: {e}"}

    async def get_stock_movements_by_reference(self, reference_type: str, reference_id: int) -> Dict[str, Any]:
        """Get stock movements by reference (invoice, expense, etc.)"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/movements/by-reference/{reference_type}/{reference_id}")
            return {
                "success": True,
                "data": response,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "movement_count": len(response),
                "message": f"Found {len(response)} stock movements for {reference_type} {reference_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get stock movements by reference: {e}"}

    # === Inventory Attachments Tools ===

    async def upload_attachment(self, item_id: int, file_path: str, attachment_type: Optional[str] = None, document_type: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """Upload an attachment for an inventory item"""
        try:
            # Validate file path before reading
            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(file_path)

            # Read file content
            with open(validated_path, 'rb') as f:
                file_content = f.read()

            if not file_content:
                return {"success": False, "error": "Empty file provided"}

            # Prepare request data
            data = {"item_id": item_id}
            if attachment_type:
                data["attachment_type"] = attachment_type
            if document_type:
                data["document_type"] = document_type
            if description:
                data["description"] = description

            # Create multipart form data
            files = {"file": (file_path.split('/')[-1], file_content)}

            response = await self.api_client._make_request(
                "POST",
                f"/inventory/{item_id}/attachments",
                data=data,
                files=files
            )
            return {
                "success": True,
                "data": response,
                "message": "Attachment uploaded successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to upload attachment: {e}"}

    async def get_attachments(self, item_id: int, attachment_type: Optional[str] = None) -> Dict[str, Any]:
        """Get all attachments for an inventory item"""
        try:
            params = {}
            if attachment_type:
                params["attachment_type"] = attachment_type

            response = await self.api_client._make_request("GET", f"/inventory/{item_id}/attachments", params=params)
            return {
                "success": True,
                "data": response,
                "count": len(response),
                "message": f"Found {len(response)} attachments"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get attachments: {e}"}

    async def get_attachment(self, item_id: int, attachment_id: int) -> Dict[str, Any]:
        """Get a specific attachment by ID"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/{item_id}/attachments/{attachment_id}")
            return {
                "success": True,
                "data": response,
                "message": "Attachment retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get attachment: {e}"}

    async def update_attachment(self, item_id: int, attachment_id: int, description: Optional[str] = None, document_type: Optional[str] = None, alt_text: Optional[str] = None, display_order: Optional[int] = None) -> Dict[str, Any]:
        """Update attachment metadata"""
        try:
            update_data = {}
            if description is not None:
                update_data["description"] = description
            if document_type is not None:
                update_data["document_type"] = document_type
            if alt_text is not None:
                update_data["alt_text"] = alt_text
            if display_order is not None:
                update_data["display_order"] = display_order

            response = await self.api_client._make_request("PUT", f"/inventory/{item_id}/attachments/{attachment_id}", json=update_data)
            return {
                "success": True,
                "data": response,
                "message": "Attachment updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update attachment: {e}"}

    async def delete_attachment(self, item_id: int, attachment_id: int) -> Dict[str, Any]:
        """Delete an attachment"""
        try:
            await self.api_client._make_request("DELETE", f"/inventory/{item_id}/attachments/{attachment_id}")
            return {
                "success": True,
                "message": "Attachment deleted successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to delete attachment: {e}"}

    async def set_primary_image(self, item_id: int, attachment_id: int) -> Dict[str, Any]:
        """Set an image attachment as the primary image for an inventory item"""
        try:
            response = await self.api_client._make_request("POST", f"/inventory/{item_id}/attachments/{attachment_id}/set-primary")
            return {
                "success": True,
                "data": response,
                "message": "Primary image set successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to set primary image: {e}"}

    async def reorder_attachments(self, item_id: int, attachment_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reorder attachments for display"""
        try:
            response = await self.api_client._make_request("POST", f"/inventory/{item_id}/attachments/reorder", json={"orders": attachment_orders})
            return {
                "success": True,
                "data": response,
                "message": "Attachments reordered successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to reorder attachments: {e}"}

    async def get_thumbnail(self, item_id: int, attachment_id: int, size: str) -> Dict[str, Any]:
        """Get a thumbnail image"""
        try:
            # Make direct HTTP request since this returns binary content, not JSON
            headers = await self.api_client.auth_client.get_auth_headers()
            response = await self.api_client._client.get(
                url=f"{self.api_client.base_url}/inventory/{item_id}/attachments/{attachment_id}/thumbnail/{size}",
                headers=headers
            )
            response.raise_for_status()

            return {
                "success": True,
                "content_type": response.headers.get('content-type', 'image/jpeg'),
                "content_length": len(response.content),
                "data": response.content,  # Binary image content
                "size": size,
                "message": f"Thumbnail retrieved successfully (size: {size})"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get thumbnail: {e}"}

    async def download_attachment(self, item_id: int, attachment_id: int) -> Dict[str, Any]:
        """Download an attachment file"""
        try:
            # Make direct HTTP request since this returns binary content, not JSON
            headers = await self.api_client.auth_client.get_auth_headers()
            response = await self.api_client._client.get(
                url=f"{self.api_client.base_url}/inventory/{item_id}/attachments/{attachment_id}/download",
                headers=headers
            )
            response.raise_for_status()

            # Get filename from Content-Disposition header
            content_disposition = response.headers.get('content-disposition', '')
            filename = f"attachment_{attachment_id}"
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[-1].strip('"')

            # Return file information and content
            return {
                "success": True,
                "filename": filename,
                "content_type": response.headers.get('content-type', 'application/octet-stream'),
                "content_length": len(response.content),
                "data": response.content,  # Binary content
                "message": f"Attachment '{filename}' downloaded successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to download attachment: {e}"}

    async def get_storage_usage(self, item_id: int) -> Dict[str, Any]:
        """Get storage usage statistics"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/{item_id}/attachments/storage/usage")
            return {
                "success": True,
                "data": response,
                "message": "Storage usage retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get storage usage: {e}"}

    async def get_primary_image(self, item_id: int) -> Dict[str, Any]:
        """Get the primary image for an inventory item"""
        try:
            response = await self.api_client._make_request("GET", f"/inventory/{item_id}/attachments/primary-image")
            return {
                "success": True,
                "data": response,
                "message": "Primary image retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get primary image: {e}"}
