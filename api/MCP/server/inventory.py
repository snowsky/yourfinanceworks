"""Inventory Management tool registrations.

Covers: categories, items, stock management, advanced analytics, import/export,
barcode management, invoice/expense integration, bulk operations, search, and attachments.
"""
from typing import Any, Dict, List, Optional

from ._shared import mcp, server_context


# Inventory Management Tools

@mcp.tool()
async def list_inventory_categories(active_only: bool = True) -> dict:
    """
    List all inventory categories with optional filtering for active categories only.

    Args:
        active_only: Return only active categories (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_inventory_categories(active_only=active_only)


@mcp.tool()
async def create_inventory_category(
    name: str, description: Optional[str] = None, is_active: bool = True
) -> dict:
    """
    Create a new inventory category for organizing inventory items.

    Args:
        name: Category name
        description: Category description (optional)
        is_active: Whether category is active (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_inventory_category(
        name=name, description=description, is_active=is_active
    )


@mcp.tool()
async def update_inventory_category(
    category_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> dict:
    """
    Update an existing inventory category.

    Args:
        category_id: ID of category to update
        name: New category name (optional)
        description: New category description (optional)
        is_active: New active status (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_inventory_category(
        category_id=category_id, name=name, description=description, is_active=is_active
    )


@mcp.tool()
async def list_inventory_items(
    skip: int = 0,
    limit: int = 100,
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    item_type: Optional[str] = None,
    low_stock_only: bool = False,
    track_stock: Optional[bool] = None,
) -> dict:
    """
    List inventory items with optional filtering and pagination.

    Args:
        skip: Number of items to skip for pagination (default: 0)
        limit: Maximum number of items to return (default: 100)
        query: Search query for items (optional)
        category_id: Filter by category ID (optional)
        item_type: Filter by item type (optional)
        low_stock_only: Return only low stock items (default: False)
        track_stock: Filter by stock tracking setting (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_inventory_items(
        skip=skip,
        limit=limit,
        query=query,
        category_id=category_id,
        item_type=item_type,
        low_stock_only=low_stock_only,
        track_stock=track_stock,
    )


@mcp.tool()
async def create_inventory_item(
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
    is_active: bool = True,
) -> dict:
    """
    Create a new inventory item with detailed specifications.

    Args:
        name: Item name
        unit_price: Unit selling price
        sku: Stock Keeping Unit (optional)
        description: Item description (optional)
        category_id: Category ID (optional)
        cost_price: Unit cost price (optional)
        currency: Currency code (default: USD)
        track_stock: Whether to track stock levels (default: True)
        current_stock: Current stock quantity (default: 0)
        minimum_stock: Minimum stock level (default: 0)
        unit_of_measure: Unit of measure (default: "each")
        item_type: Type of item (default: "product")
        is_active: Whether item is active (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_inventory_item(
        name=name,
        unit_price=unit_price,
        sku=sku,
        description=description,
        category_id=category_id,
        cost_price=cost_price,
        currency=currency,
        track_stock=track_stock,
        current_stock=current_stock,
        minimum_stock=minimum_stock,
        unit_of_measure=unit_of_measure,
        item_type=item_type,
        is_active=is_active,
    )


@mcp.tool()
async def update_inventory_item(
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
    is_active: Optional[bool] = None,
) -> dict:
    """
    Update an existing inventory item.

    Args:
        item_id: ID of item to update
        name: New item name (optional)
        sku: New SKU (optional)
        description: New description (optional)
        category_id: New category ID (optional)
        unit_price: New unit price (optional)
        cost_price: New cost price (optional)
        currency: New currency (optional)
        track_stock: New stock tracking setting (optional)
        current_stock: New current stock (optional)
        minimum_stock: New minimum stock (optional)
        unit_of_measure: New unit of measure (optional)
        item_type: New item type (optional)
        is_active: New active status (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_inventory_item(
        item_id=item_id,
        name=name,
        sku=sku,
        description=description,
        category_id=category_id,
        unit_price=unit_price,
        cost_price=cost_price,
        currency=currency,
        track_stock=track_stock,
        current_stock=current_stock,
        minimum_stock=minimum_stock,
        unit_of_measure=unit_of_measure,
        item_type=item_type,
        is_active=is_active,
    )


@mcp.tool()
async def adjust_stock(item_id: int, quantity: float, reason: str = "Manual adjustment") -> dict:
    """
    Adjust stock levels for an inventory item manually.

    Args:
        item_id: ID of inventory item
        quantity: Quantity to adjust (positive for increase, negative for decrease)
        reason: Reason for adjustment (default: "Manual adjustment")
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.adjust_stock(item_id=item_id, quantity=quantity, reason=reason)


@mcp.tool()
async def get_inventory_analytics() -> dict:
    """
    Get comprehensive inventory analytics and statistics including totals, low stock alerts, and category breakdowns.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_analytics()


@mcp.tool()
async def get_low_stock_items() -> dict:
    """
    Get items with stock levels below their minimum threshold.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_low_stock_items()


# === Advanced Analytics & Reporting Tools ===

@mcp.tool()
async def get_advanced_inventory_analytics(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict:
    """
    Get advanced inventory analytics with trends and insights.

    Args:
        start_date: Start date for analysis (YYYY-MM-DD) (optional)
        end_date: End date for analysis (YYYY-MM-DD) (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_advanced_inventory_analytics(
        start_date=start_date, end_date=end_date
    )


@mcp.tool()
async def get_sales_velocity_analysis(days: int = 30) -> dict:
    """
    Get sales velocity analysis for inventory forecasting.

    Args:
        days: Analysis period in days (default: 30)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_sales_velocity_analysis(days=days)


@mcp.tool()
async def get_inventory_forecasting(forecast_days: int = 90) -> dict:
    """
    Get inventory forecasting based on historical data.

    Args:
        forecast_days: Forecast period in days (default: 90)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_forecasting(forecast_days=forecast_days)


@mcp.tool()
async def get_inventory_value_report() -> dict:
    """
    Get detailed inventory value report including total values and item breakdowns.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_value_report()


@mcp.tool()
async def get_profitability_analysis(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict:
    """
    Get detailed profitability analysis for inventory items.

    Args:
        start_date: Start date (YYYY-MM-DD) (optional)
        end_date: End date (YYYY-MM-DD) (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_profitability_analysis(
        start_date=start_date, end_date=end_date
    )


@mcp.tool()
async def get_inventory_turnover_analysis(months: int = 12) -> dict:
    """
    Get inventory turnover analysis to understand how quickly inventory is sold.

    Args:
        months: Analysis period in months (default: 12)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_turnover_analysis(months=months)


@mcp.tool()
async def get_category_performance_report(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict:
    """
    Get performance report by inventory categories.

    Args:
        start_date: Start date (YYYY-MM-DD) (optional)
        end_date: End date (YYYY-MM-DD) (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_category_performance_report(
        start_date=start_date, end_date=end_date
    )


@mcp.tool()
async def get_low_stock_alerts(threshold_days: int = 30) -> dict:
    """
    Get low stock alerts based on sales velocity.

    Args:
        threshold_days: Days threshold for alerts (default: 30)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_low_stock_alerts(threshold_days=threshold_days)


@mcp.tool()
async def get_inventory_dashboard_data() -> dict:
    """
    Get comprehensive dashboard data for inventory overview including analytics, alerts, and recent activity.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_dashboard_data()


@mcp.tool()
async def get_stock_movement_summary(item_id: Optional[int] = None, days: int = 30) -> dict:
    """
    Get stock movement summary report.

    Args:
        item_id: Item ID to filter by (optional)
        days: Analysis period in days (default: 30)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_stock_movement_summary(item_id=item_id, days=days)


# === Import/Export Tools ===

@mcp.tool()
async def import_inventory_csv(file_path: str) -> dict:
    """
    Import inventory items from CSV file.

    Args:
        file_path: Path to CSV file to import
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.import_inventory_csv(file_path=file_path)


@mcp.tool()
async def export_inventory_csv(
    include_inactive: bool = False, category_id: Optional[int] = None
) -> dict:
    """
    Export inventory items to CSV format.

    Args:
        include_inactive: Include inactive items (default: False)
        category_id: Filter by category ID (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.export_inventory_csv(
        include_inactive=include_inactive, category_id=category_id
    )


# === Barcode Management Tools ===

@mcp.tool()
async def get_item_by_barcode(barcode: str) -> dict:
    """
    Get inventory item by barcode.

    Args:
        barcode: Barcode to search for
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_item_by_barcode(barcode=barcode)


@mcp.tool()
async def update_item_barcode(
    item_id: int,
    barcode: str,
    barcode_type: Optional[str] = None,
    barcode_format: Optional[str] = None,
) -> dict:
    """
    Update barcode for an inventory item.

    Args:
        item_id: ID of inventory item
        barcode: Barcode value
        barcode_type: Barcode type (UPC, EAN, etc.) (optional)
        barcode_format: Barcode format (1D, 2D) (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_item_barcode(
        item_id=item_id, barcode=barcode, barcode_type=barcode_type, barcode_format=barcode_format
    )


@mcp.tool()
async def validate_barcode(barcode: str) -> dict:
    """
    Validate a barcode and detect its type.

    Args:
        barcode: Barcode to validate
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.validate_barcode(barcode=barcode)


@mcp.tool()
async def generate_barcode_suggestions(item_name: str, sku: Optional[str] = None) -> dict:
    """
    Generate barcode suggestions based on item information.

    Args:
        item_name: Item name for generating suggestions
        sku: SKU for generating suggestions (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.generate_barcode_suggestions(item_name=item_name, sku=sku)


@mcp.tool()
async def bulk_update_barcodes(barcode_updates: List[Dict[str, Any]]) -> dict:
    """
    Bulk update barcodes for multiple items.

    Args:
        barcode_updates: List of barcode updates
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.bulk_update_barcodes(barcode_updates=barcode_updates)


# === Integration Tools ===

@mcp.tool()
async def populate_invoice_item_from_inventory(
    inventory_item_id: int, quantity: float = 1.0
) -> dict:
    """
    Populate invoice item data from inventory item.

    Args:
        inventory_item_id: ID of inventory item
        quantity: Quantity to populate (default: 1.0)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.populate_invoice_item_from_inventory(
        inventory_item_id=inventory_item_id, quantity=quantity
    )


@mcp.tool()
async def validate_invoice_stock_availability(invoice_items: List[Dict[str, Any]]) -> dict:
    """
    Validate stock availability for invoice items.

    Args:
        invoice_items: List of invoice items to validate
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.validate_invoice_stock_availability(invoice_items=invoice_items)


@mcp.tool()
async def get_invoice_inventory_summary(invoice_id: int) -> dict:
    """
    Get inventory summary for an invoice.

    Args:
        invoice_id: ID of invoice
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_invoice_inventory_summary(invoice_id=invoice_id)


@mcp.tool()
async def create_inventory_purchase_expense(purchase_data: Dict[str, Any]) -> dict:
    """
    Create an expense for inventory purchase with automatic stock updates.

    Args:
        purchase_data: Purchase data including items and vendor info
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_inventory_purchase_expense(purchase_data=purchase_data)


@mcp.tool()
async def get_inventory_purchase_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vendor: Optional[str] = None,
) -> dict:
    """
    Get summary of inventory purchases.

    Args:
        start_date: Start date (YYYY-MM-DD) (optional)
        end_date: End date (YYYY-MM-DD) (optional)
        vendor: Filter by vendor (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_purchase_summary(
        start_date=start_date, end_date=end_date, vendor=vendor
    )


@mcp.tool()
async def get_expense_inventory_summary(expense_id: int) -> dict:
    """
    Get inventory summary for an expense.

    Args:
        expense_id: ID of expense
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_expense_inventory_summary(expense_id=expense_id)


@mcp.tool()
async def get_linked_invoices_for_inventory_item(item_id: int) -> dict:
    """
    Get all invoices that contain this inventory item.

    Args:
        item_id: ID of inventory item
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_linked_invoices_for_inventory_item(item_id=item_id)


@mcp.tool()
async def get_inventory_item_stock_summary(item_id: int, days: int = 30) -> dict:
    """
    Get stock movement summary for an inventory item.

    Args:
        item_id: ID of inventory item
        days: Analysis period in days (default: 30)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_item_stock_summary(item_id=item_id, days=days)


# === Additional Stock Management Tools ===

@mcp.tool()
async def get_recent_movements(days: int = 7, limit: int = 50) -> dict:
    """
    Get recent stock movements across all items.

    Args:
        days: Days to look back (default: 7)
        limit: Maximum movements to return (default: 50)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_recent_movements(days=days, limit=limit)


@mcp.tool()
async def check_stock_availability(item_id: int, requested_quantity: float) -> dict:
    """
    Check if requested quantity is available for an item.

    Args:
        item_id: ID of inventory item
        requested_quantity: Quantity to check availability for
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.check_stock_availability(
        item_id=item_id, requested_quantity=requested_quantity
    )


# === Bulk Operations Tools ===

@mcp.tool()
async def create_inventory_categories_bulk(categories: List[Dict[str, Any]]) -> dict:
    """
    Create multiple inventory categories at once.

    Args:
        categories: List of category data to create
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_inventory_categories_bulk(categories=categories)


@mcp.tool()
async def create_inventory_items_bulk(items: List[Dict[str, Any]]) -> dict:
    """
    Create multiple inventory items at once.

    Args:
        items: List of item data to create
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_inventory_items_bulk(items=items)


@mcp.tool()
async def create_stock_movements_bulk(movements: List[Dict[str, Any]]) -> dict:
    """
    Create multiple stock movements at once.

    Args:
        movements: List of stock movement data to create
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_stock_movements_bulk(movements=movements)


# === Search and Filtering Tools ===

@mcp.tool()
async def search_inventory_items(query: str, limit: int = 50) -> dict:
    """
    Search inventory items by name, SKU, or description.

    Args:
        query: Search query
        limit: Maximum number of results to return (default: 50)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.search_inventory_items(query=query, limit=limit)


@mcp.tool()
async def get_inventory_item_movements(
    item_id: int, limit: int = 50, movement_type: Optional[str] = None
) -> dict:
    """
    Get stock movement history for an inventory item.

    Args:
        item_id: ID of inventory item
        limit: Maximum movements to return (default: 50)
        movement_type: Filter by movement type (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_inventory_item_movements(
        item_id=item_id, limit=limit, movement_type=movement_type
    )


@mcp.tool()
async def get_stock_movements_by_reference(reference_type: str, reference_id: int) -> dict:
    """
    Get stock movements by reference (invoice, expense, etc.).

    Args:
        reference_type: Type of reference (invoice, expense, etc.)
        reference_id: ID of the referenced item
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_stock_movements_by_reference(
        reference_type=reference_type, reference_id=reference_id
    )


# === Inventory Attachments Tools ===

@mcp.tool()
async def upload_attachment(
    item_id: int,
    file_path: str,
    attachment_type: Optional[str] = None,
    document_type: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Upload an attachment for an inventory item.

    Args:
        item_id: ID of inventory item
        file_path: Path to file to upload
        attachment_type: Attachment type ('image' or 'document') (optional)
        document_type: Document type (for documents) (optional)
        description: Optional description (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.upload_attachment(
        item_id=item_id,
        file_path=file_path,
        attachment_type=attachment_type,
        document_type=document_type,
        description=description,
    )


@mcp.tool()
async def get_attachments(item_id: int, attachment_type: Optional[str] = None) -> dict:
    """
    Get all attachments for an inventory item.

    Args:
        item_id: ID of inventory item
        attachment_type: Filter by attachment type ('image', 'document', or None) (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_attachments(item_id=item_id, attachment_type=attachment_type)


@mcp.tool()
async def get_attachment(item_id: int, attachment_id: int) -> dict:
    """
    Get a specific attachment by ID.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of attachment
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_attachment(item_id=item_id, attachment_id=attachment_id)


@mcp.tool()
async def update_attachment(
    item_id: int,
    attachment_id: int,
    description: Optional[str] = None,
    document_type: Optional[str] = None,
    alt_text: Optional[str] = None,
    display_order: Optional[int] = None,
) -> dict:
    """
    Update attachment metadata.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of attachment
        description: New description (optional)
        document_type: New document type (optional)
        alt_text: New alt text for images (optional)
        display_order: New display order (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_attachment(
        item_id=item_id,
        attachment_id=attachment_id,
        description=description,
        document_type=document_type,
        alt_text=alt_text,
        display_order=display_order,
    )


@mcp.tool()
async def delete_attachment(item_id: int, attachment_id: int) -> dict:
    """
    Delete an attachment.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of attachment
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_attachment(item_id=item_id, attachment_id=attachment_id)


@mcp.tool()
async def set_primary_image(item_id: int, attachment_id: int) -> dict:
    """
    Set an image attachment as the primary image for an inventory item.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of image attachment to set as primary
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.set_primary_image(item_id=item_id, attachment_id=attachment_id)


@mcp.tool()
async def reorder_attachments(item_id: int, attachment_orders: List[Dict[str, Any]]) -> dict:
    """
    Reorder attachments for display.

    Args:
        item_id: ID of inventory item
        attachment_orders: List of attachment orders with attachment_id and order
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.reorder_attachments(
        item_id=item_id, attachment_orders=attachment_orders
    )


@mcp.tool()
async def get_thumbnail(item_id: int, attachment_id: int, size: str) -> dict:
    """
    Get a thumbnail image.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of attachment
        size: Thumbnail size (e.g., '150x150')
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_thumbnail(
        item_id=item_id, attachment_id=attachment_id, size=size
    )


@mcp.tool()
async def download_attachment(item_id: int, attachment_id: int) -> dict:
    """
    Download an attachment file.

    Args:
        item_id: ID of inventory item
        attachment_id: ID of attachment
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.download_attachment(
        item_id=item_id, attachment_id=attachment_id
    )


@mcp.tool()
async def get_storage_usage(item_id: int) -> dict:
    """
    Get storage usage statistics for the current tenant.

    Args:
        item_id: ID of inventory item (used for tenant context)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_storage_usage(item_id=item_id)


@mcp.tool()
async def get_primary_image(item_id: int) -> dict:
    """
    Get the primary image for an inventory item.

    Args:
        item_id: ID of inventory item
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_primary_image(item_id=item_id)
