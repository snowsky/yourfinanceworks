from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone
import csv

from core.models.database import get_db
from core.models.models_per_tenant import InventoryItem, InventoryCategory, StockMovement, Invoice, InvoiceItem
from core.models.models import MasterUser
from core.schemas.inventory import (
    InventoryItem as InventoryItemSchema,
    InventoryItemCreate, InventoryItemUpdate,
    InventoryCategory as InventoryCategorySchema,
    InventoryCategoryCreate, InventoryCategoryUpdate,
    StockMovement as StockMovementSchema,
    StockMovementCreate, StockMovementUpdate,
    InventorySearchFilters, InventoryAnalytics,
    InventoryListResponse, InventoryValueReport,
    StockMovementSummary
)
from core.services.inventory_service import InventoryService
from core.services.stock_movement_service import StockMovementService
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.utils.audit import log_audit_event
from core.utils.inventory_error_handler import handle_inventory_exception
from core.exceptions.inventory_exceptions import InventoryException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"]
)


# Dependency to get inventory service
def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    return InventoryService(db)


# Dependency to get stock movement service
def get_stock_service(db: Session = Depends(get_db)) -> StockMovementService:
    return StockMovementService(db)


# === Category Endpoints ===

@router.post("/categories", response_model=InventoryCategorySchema)
async def create_category(
    category: InventoryCategoryCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Create a new inventory category"""
    try:
        created_category = inventory_service.create_category(category)
        log_audit_event(db, current_user.id, current_user.email, "CREATE", "inventory_category", str(created_category.id), created_category.name, None, None, None, "success", None
        )
        return created_category
    except Exception as e:
        handle_inventory_exception(e)


@router.get("/categories", response_model=List[InventoryCategorySchema])
async def get_categories(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get all inventory categories"""
    try:
        return inventory_service.get_categories(active_only)
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch categories")


@router.get("/categories/{category_id}", response_model=InventoryCategorySchema)
async def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get a specific category by ID"""
    try:
        category = inventory_service.get_category(category_id)
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return category
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch category")


@router.put("/categories/{category_id}", response_model=InventoryCategorySchema)
async def update_category(
    category_id: int,
    category_update: InventoryCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Update an inventory category"""
    try:
        updated_category = inventory_service.update_category(category_id, category_update)
        log_audit_event(db, current_user.id, current_user.email, "UPDATE", "inventory_category", str(category_id), updated_category.name, None, None, None, "success", None
        )
        return updated_category
    except Exception as e:
        handle_inventory_exception(e)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Delete an inventory category"""
    try:
        inventory_service.delete_category(category_id)
        log_audit_event(db, current_user.id, current_user.email, "DELETE", "inventory_category", str(category_id), "Deleted category", None, None, None, "success", None
        )
        return {"message": "Category deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete category")


# === Bulk Operations ===

@router.post("/categories/bulk", response_model=List[InventoryCategorySchema])
async def create_categories_bulk(
    categories: List[InventoryCategoryCreate],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Create multiple inventory categories at once"""
    try:
        created_categories = []
        for category_data in categories:
            created_category = inventory_service.create_category(category_data)
            created_categories.append(created_category)

        log_audit_event(db, current_user.id, current_user.email, "BULK_CREATE", "inventory_categories", None, f"Created {len(created_categories)} categories", None, None, None, "success", None
        )
        return created_categories
    except Exception as e:
        handle_inventory_exception(e)


@router.post("/items/bulk", response_model=List[InventoryItemSchema])
async def create_items_bulk(
    items: List[InventoryItemCreate],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Create multiple inventory items at once"""
    try:
        created_items = []
        for item_data in items:
            created_item = inventory_service.create_item(item_data, current_user.id)
            created_items.append(created_item)

        log_audit_event(db, current_user.id, current_user.email, "BULK_CREATE", "inventory_items", None, f"Created {len(created_items)} items", None, None, None, "success", None
        )
        return created_items
    except Exception as e:
        handle_inventory_exception(e)


# === Item Endpoints ===

@router.post("/items", response_model=InventoryItemSchema)
async def create_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Create a new inventory item"""
    try:
        created_item = inventory_service.create_item(item, current_user.id)
        log_audit_event(db, current_user.id, current_user.email, "CREATE", "inventory_item", str(created_item.id), created_item.name, None, None, None, "success", None
        )
        return created_item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create item")


@router.get("/items", response_model=InventoryListResponse)
async def get_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    item_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    track_stock: Optional[bool] = None,
    low_stock_only: Optional[bool] = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get inventory items with optional filtering"""
    try:
        filters = InventorySearchFilters(
            query=query,
            category_id=category_id,
            item_type=item_type,
            is_active=is_active,
            track_stock=track_stock,
            low_stock_only=low_stock_only,
            min_price=min_price,
            max_price=max_price
        )

        items = inventory_service.get_items(filters, skip, limit)
        total = len(items)  # TODO: Implement proper count query

        return InventoryListResponse(
            items=items,
            total=total,
            page=skip // limit + 1,
            page_size=limit,
            has_more=len(items) == limit
        )
    except Exception as e:
        logger.error(f"Error fetching items: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch items")


@router.get("/items/search")
async def search_items(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Search inventory items"""
    try:
        items = inventory_service.search_items(q, limit)
        return {"results": items, "total": len(items)}
    except Exception as e:
        logger.error(f"Error searching items: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search items")


@router.get("/items/{item_id}", response_model=InventoryItemSchema)
async def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get a specific inventory item"""
    try:
        item = inventory_service.get_item(item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch item")


@router.put("/items/{item_id}", response_model=InventoryItemSchema)
async def update_item(
    item_id: int,
    item_update: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Update an inventory item"""
    try:
        updated_item = inventory_service.update_item(item_id, item_update, current_user.id)
        log_audit_event(db, current_user.id, current_user.email, "UPDATE", "inventory_item", str(item_id), updated_item.name, None, None, None, "success", None
        )
        return updated_item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update item")


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Delete an inventory item"""
    try:
        await inventory_service.delete_item(item_id, current_user.id, current_user.tenant_id)
        log_audit_event(db, current_user.id, current_user.email, "DELETE", "inventory_item", str(item_id), "Deleted item", None, None, None, "success", None
        )
        return {"message": "Item deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete item")


# === Stock Management Endpoints ===

@router.post("/items/{item_id}/stock/adjust")
async def adjust_stock(
    item_id: int,
    quantity: float,
    reason: str = "Manual adjustment",
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Manually adjust stock levels"""
    try:
        movement = stock_service.record_manual_adjustment(item_id, quantity, reason, current_user.id)
        log_audit_event(db, current_user.id, current_user.email, "UPDATE", "inventory_item", str(item_id), f"Stock adjustment: {quantity} ({reason})", None, None, None, "success", None
        )
        return {"message": "Stock adjusted successfully", "movement": movement}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adjusting stock for item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to adjust stock")


@router.post("/stock-movements/bulk", response_model=List[StockMovementSchema])
async def create_stock_movements_bulk(
    movements: List[StockMovementCreate],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Create multiple stock movements at once"""
    try:
        created_movements = []
        for movement_data in movements:
            movement = stock_service.record_movement(
                item_id=movement_data.item_id,
                movement_type=movement_data.movement_type,
                quantity=movement_data.quantity,
                user_id=current_user.id,
                unit_cost=movement_data.unit_cost,
                reference_type=movement_data.reference_type,
                reference_id=movement_data.reference_id,
                notes=movement_data.notes
            )
            created_movements.append(movement)

        log_audit_event(db, current_user.id, current_user.email, "BULK_CREATE", "stock_movements", None, f"Created {len(created_movements)} stock movements", None, None, None, "success", None
        )
        return created_movements
    except Exception as e:
        handle_inventory_exception(e)


@router.get("/items/{item_id}/stock/movements", response_model=List[StockMovementSchema])
async def get_stock_movements(
    item_id: int,
    limit: int = Query(50, ge=1, le=500),
    movement_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Get stock movement history for an item"""
    try:
        return stock_service.get_movement_history(item_id, limit, movement_type)
    except Exception as e:
        logger.error(f"Error fetching stock movements for item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch stock movements")


@router.get("/movements/by-reference/{reference_type}/{reference_id}", response_model=List[StockMovementSchema])
async def get_stock_movements_by_reference(
    reference_type: str,
    reference_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Get stock movements by reference (invoice, expense, etc.)"""
    try:
        return stock_service.get_movements_by_reference(reference_type, reference_id)
    except Exception as e:
        logger.error(f"Error fetching stock movements for reference {reference_type}:{reference_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch stock movements by reference")


@router.get("/stock/low-stock", response_model=List[InventoryItemSchema])
async def get_low_stock_items(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get items with low stock levels"""
    try:
        return inventory_service.get_low_stock_items()
    except Exception as e:
        logger.error(f"Error fetching low stock items: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch low stock items")


@router.get("/items/{item_id}/availability")
async def check_stock_availability(
    item_id: int,
    requested_quantity: float = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Check if requested quantity is available for an item"""
    try:
        available = inventory_service.validate_stock_availability(item_id, requested_quantity)
        return {
            "item_id": item_id,
            "requested_quantity": requested_quantity,
            "available": available
        }
    except Exception as e:
        logger.error(f"Error checking stock availability for item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to check stock availability")


# === Invoice Integration Endpoints ===

@router.post("/invoice-items/populate")
async def populate_invoice_item_from_inventory(
    inventory_item_id: int = Query(..., description="ID of inventory item"),
    quantity: float = Query(1.0, gt=0, description="Quantity to populate"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Populate invoice item data from inventory item"""
    try:
        from core.services.inventory_integration_service import InventoryIntegrationService
        integration_service = InventoryIntegrationService(db)

        item_data = integration_service.populate_invoice_item_from_inventory(
            inventory_item_id, quantity
        )
        return item_data
    except Exception as e:
        handle_inventory_exception(e)


@router.post("/invoice-items/validate-stock")
async def validate_invoice_stock_availability(
    invoice_items: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Validate stock availability for invoice items"""
    try:
        from core.services.inventory_integration_service import InventoryIntegrationService
        integration_service = InventoryIntegrationService(db)

        validation_results = integration_service.validate_invoice_stock_availability(invoice_items)
        return {"validation_results": validation_results}
    except Exception as e:
        handle_inventory_exception(e)


@router.get("/invoice/{invoice_id}/inventory-summary")
async def get_invoice_inventory_summary(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get inventory summary for an invoice"""
    try:
        from core.services.inventory_integration_service import InventoryIntegrationService
        integration_service = InventoryIntegrationService(db)

        summary = integration_service.get_invoice_inventory_summary(invoice_id)
        return summary
    except Exception as e:
        handle_inventory_exception(e)


# === Expense Integration Endpoints ===

@router.post("/expenses/purchase")
async def create_inventory_purchase_expense(
    purchase_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create an expense for inventory purchase with automatic stock updates"""
    try:
        from core.schemas.expense import InventoryPurchaseCreate
        from core.services.inventory_integration_service import InventoryIntegrationService

        # Validate purchase data
        purchase = InventoryPurchaseCreate(**purchase_data)

        # Calculate total amount
        total_amount = 0.0
        for item in purchase.items:
            inventory_service = InventoryService(db)
            inventory_item = inventory_service.get_item(item.item_id)
            if not inventory_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Inventory item {item.item_id} not found"
                )
            total_amount += item.quantity * item.unit_cost

        # Create expense data
        expense_data = {
            "amount": total_amount,
            "currency": purchase.currency,
            "expense_date": purchase.purchase_date,
            "category": "Inventory Purchase",
            "vendor": purchase.vendor,
            "reference_number": purchase.reference_number,
            "payment_method": purchase.payment_method,
            "tax_rate": purchase.tax_rate,
            "notes": purchase.notes or f"Inventory purchase from {purchase.vendor}",
            "is_inventory_purchase": True,
            "inventory_items": [
                {
                    "item_id": item.item_id,
                    "quantity": item.quantity,
                    "unit_cost": item.unit_cost
                }
                for item in purchase.items
            ]
        }

        # Import and call expense creation
        from core.schemas.expense import ExpenseCreate
        from core.routers.expenses import create_expense

        expense_create = ExpenseCreate(**expense_data)
        result = await create_expense(expense_create, db, current_user)

        return {
            "message": "Inventory purchase expense created successfully",
            "expense": result,
            "stock_movements_processed": len(purchase.items)
        }

    except Exception as e:
        handle_inventory_exception(e)


@router.get("/expenses/purchase-summary")
async def get_inventory_purchase_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vendor: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get summary of inventory purchases"""
    try:
        from datetime import datetime

        query = db.query(Expense).filter(
            Expense.is_inventory_purchase == True
        )

        if start_date:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Expense.expense_date >= start)

        if end_date:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Expense.expense_date <= end)

        if vendor:
            query = query.filter(Expense.vendor.ilike(f"%{vendor}%"))

        expenses = query.order_by(Expense.expense_date.desc()).all()

        total_expenses = len(expenses)
        total_value = 0.0
        total_items = 0

        purchases = []
        for expense in expenses:
            expense_value = 0.0
            item_count = 0

            if expense.inventory_items:
                for item_data in expense.inventory_items:
                    quantity = item_data.get('quantity', 0)
                    unit_cost = item_data.get('unit_cost', 0)
                    expense_value += quantity * unit_cost
                    item_count += 1

                total_value += expense_value
                total_items += item_count

            purchases.append({
                "expense_id": expense.id,
                "date": expense.expense_date.isoformat(),
                "vendor": expense.vendor,
                "reference_number": expense.reference_number,
                "total_value": expense_value,
                "item_count": item_count,
                "currency": expense.currency
            })

        return {
            "total_expenses": total_expenses,
            "total_purchase_value": total_value,
            "total_items_purchased": total_items,
            "currency": "USD",  # TODO: Get from tenant settings
            "purchases": purchases
        }

    except Exception as e:
        handle_inventory_exception(e)


@router.get("/expense/{expense_id}/inventory-summary")
async def get_expense_inventory_summary(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get inventory summary for an expense"""
    try:
        # For expenses, we need to get inventory purchase summary
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

        if not expense.is_inventory_purchase or not expense.inventory_items:
            return {
                "expense_id": expense_id,
                "is_inventory_purchase": False,
                "inventory_items": [],
                "total_items": 0,
                "total_value": 0.0
            }

        # Get inventory item details
        inventory_service = InventoryService(db)
        items_detail = []
        total_value = 0.0

        for item_data in expense.inventory_items:
            item_id = item_data.get('item_id')
            quantity = item_data.get('quantity', 0)
            unit_cost = item_data.get('unit_cost', 0)

            if item_id:
                inventory_item = inventory_service.get_item(item_id)
                if inventory_item:
                    item_value = quantity * unit_cost
                    total_value += item_value

                    items_detail.append({
                        "item_id": item_id,
                        "item_name": inventory_item.name,
                        "sku": inventory_item.sku,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "line_total": item_value,
                        "current_stock": inventory_item.current_stock if inventory_item.track_stock else None
                    })

        return {
            "expense_id": expense_id,
            "is_inventory_purchase": True,
            "inventory_items": items_detail,
            "total_items": len(items_detail),
            "total_value": total_value
        }

    except HTTPException:
        raise
    except Exception as e:
        handle_inventory_exception(e)


# === Advanced Analytics and Reporting Endpoints ===

@router.get("/analytics", response_model=InventoryAnalytics)
async def get_inventory_analytics(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get basic inventory analytics"""
    try:
        return inventory_service.get_inventory_analytics()
    except Exception as e:
        logger.error(f"Error fetching inventory analytics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch analytics")


@router.get("/analytics/advanced")
async def get_advanced_inventory_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get advanced inventory analytics with trends and insights"""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

        return inventory_service.get_advanced_inventory_analytics(start, end)
    except Exception as e:
        logger.error(f"Error fetching advanced analytics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch advanced analytics")


@router.get("/analytics/sales-velocity")
async def get_sales_velocity_analysis(
    days: int = Query(30, ge=7, le=365, description="Analysis period in days"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get sales velocity analysis for inventory forecasting"""
    try:
        # Use the service method that handles database queries internally
        return inventory_service.get_sales_velocity_analysis(days)
    except Exception as e:
        logger.error(f"Error generating sales velocity analysis: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate sales velocity analysis")


@router.get("/analytics/forecasting")
async def get_inventory_forecasting(
    forecast_days: int = Query(90, ge=30, le=365, description="Forecast period in days"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get inventory forecasting based on historical data"""
    try:
        # Use the service method that handles database queries internally
        return inventory_service.get_inventory_forecasting(forecast_days)
    except Exception as e:
        logger.error(f"Error generating inventory forecast: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate inventory forecast")


@router.get("/reports/value")
async def get_inventory_value_report(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get detailed inventory value report"""
    try:
        return inventory_service.get_inventory_value_report()
    except Exception as e:
        logger.error(f"Error generating inventory value report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate value report")


@router.get("/reports/profitability")
async def get_profitability_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get detailed profitability analysis for inventory items"""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

        return inventory_service.get_profitability_analysis(start, end)
    except Exception as e:
        logger.error(f"Error generating profitability analysis: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate profitability analysis")


@router.get("/reports/turnover")
async def get_inventory_turnover_analysis(
    months: int = Query(12, ge=1, le=24, description="Analysis period in months"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get inventory turnover analysis"""
    try:
        return inventory_service.get_inventory_turnover_analysis(months)
    except Exception as e:
        logger.error(f"Error generating turnover analysis: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate turnover analysis")


@router.get("/reports/categories")
async def get_category_performance_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get performance report by inventory categories"""
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

        return inventory_service.get_category_performance_report(start, end)
    except Exception as e:
        logger.error(f"Error generating category performance report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate category report")


@router.get("/alerts/low-stock")
async def get_low_stock_alerts(
    threshold_days: int = Query(30, ge=1, le=365, description="Days threshold for alerts"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get low stock alerts based on sales velocity"""
    try:
        return inventory_service.get_low_stock_alerts(threshold_days)
    except Exception as e:
        logger.error(f"Error generating low stock alerts: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate low stock alerts")


@router.get("/reports/sales-velocity")
async def get_sales_velocity_report(
    days: int = Query(30, ge=7, le=365, description="Analysis period in days"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get sales velocity report for inventory items"""
    try:
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Get sales data with velocity calculations
        velocity_data = db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            InventoryItem.current_stock,
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.count(func.distinct(Invoice.id)).label('invoice_count'),
            func.avg(InvoiceItem.quantity).label('avg_order_quantity'),
            func.max(Invoice.created_at).label('last_sale_date')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku, InventoryItem.current_stock)

        results = []
        for row in velocity_data.all():
            item_id, name, sku, current_stock, total_sold, invoice_count, avg_order_qty, last_sale = row

            # Calculate velocity metrics
            days_since_last_sale = (end_date - last_sale).days if last_sale else None
            daily_sales_rate = total_sold / days if total_sold > 0 else 0
            weekly_sales_rate = daily_sales_rate * 7
            monthly_sales_rate = daily_sales_rate * 30

            # Stock coverage calculations
            days_stock_remaining = current_stock / daily_sales_rate if daily_sales_rate > 0 else None
            weeks_stock_remaining = current_stock / weekly_sales_rate if weekly_sales_rate > 0 else None

            results.append({
                'item_id': item_id,
                'item_name': name,
                'sku': sku,
                'current_stock': current_stock,
                'total_sold_period': total_sold,
                'invoice_count': invoice_count,
                'avg_order_quantity': avg_order_qty or 0,
                'daily_sales_rate': daily_sales_rate,
                'weekly_sales_rate': weekly_sales_rate,
                'monthly_sales_rate': monthly_sales_rate,
                'days_since_last_sale': days_since_last_sale,
                'days_stock_remaining': days_stock_remaining,
                'weeks_stock_remaining': weeks_stock_remaining,
                'last_sale_date': last_sale.isoformat() if last_sale else None
            })

        # Sort by sales velocity (descending)
        results.sort(key=lambda x: x['daily_sales_rate'], reverse=True)

        return {
            'analysis_period_days': days,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'items': results,
            'summary': {
                'total_items': len(results),
                'high_velocity_items': len([r for r in results if r['daily_sales_rate'] > 1]),
                'low_velocity_items': len([r for r in results if r['daily_sales_rate'] < 0.1]),
                'out_of_stock_risk': len([r for r in results if r['days_stock_remaining'] and r['days_stock_remaining'] < 7])
            }
        }

    except Exception as e:
        logger.error(f"Error generating sales velocity report: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate sales velocity report")


@router.get("/reports/dashboard")
async def get_inventory_dashboard_data(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get comprehensive dashboard data for inventory overview"""
    try:
        # Get basic analytics
        analytics = inventory_service.get_inventory_analytics()

        # Get low stock alerts
        alerts = inventory_service.get_low_stock_alerts(30)

        # Get recent sales velocity (last 7 days)
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        recent_sales = db.query(
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_revenue'),
            func.count(func.distinct(Invoice.id)).label('invoice_count')
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).first()

        # Get top selling items (last 30 days)
        top_items_period = end_date - timedelta(days=30)
        top_selling = db.query(
            InventoryItem.name.label('item_name'),
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_revenue')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(top_items_period, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name
        ).order_by(func.sum(InvoiceItem.quantity).desc()
        ).limit(5).all()

        return {
            'analytics': analytics,
            'alerts': alerts['summary'],
            'recent_activity': {
                'period_days': 7,
                'total_sold': recent_sales.total_sold or 0,
                'total_revenue': recent_sales.total_revenue or 0,
                'invoice_count': recent_sales.invoice_count or 0
            },
            'top_selling_items': [
                {
                    'item_name': item.item_name,
                    'total_sold': item.total_sold,
                    'total_revenue': item.total_revenue
                }
                for item in top_selling
            ],
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating inventory dashboard data: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate dashboard data")


@router.get("/reports/stock-movements")
async def get_stock_movement_summary(
    item_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get stock movement summary report"""
    try:
        return inventory_service.get_stock_movement_summary(item_id, days)
    except Exception as e:
        logger.error(f"Error generating stock movement summary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate stock movement summary")


@router.get("/movements/recent", response_model=List[StockMovementSchema])
async def get_recent_movements(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Get recent stock movements across all items"""
    try:
        return stock_service.get_recent_movements(days, limit)
    except Exception as e:
        logger.error(f"Error fetching recent movements: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch recent movements")


# === Import/Export Endpoints ===

@router.post("/import/csv")
async def import_inventory_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Import inventory items from CSV file"""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")

        content = await file.read()
        csv_text = content.decode('utf-8')

        # Parse CSV and create items
        lines = csv_text.strip().split('\n')
        if len(lines) < 2:
            raise HTTPException(status_code=400, detail="CSV file must have at least a header row and one data row")

        header = lines[0].split(',')
        imported_items = []

        for line_num, line in enumerate(lines[1:], 2):
            if not line.strip():
                continue

            values = line.split(',')
            if len(values) != len(header):
                raise HTTPException(status_code=400, detail=f"Line {line_num}: Expected {len(header)} columns, got {len(values)}")

            # Parse CSV row into item data
            item_data = {}
            for i, col in enumerate(header):
                col = col.strip().lower()
                value = values[i].strip()

                if col == 'name':
                    item_data['name'] = value
                elif col == 'sku':
                    item_data['sku'] = value if value else None
                elif col == 'description':
                    item_data['description'] = value if value else None
                elif col == 'category':
                    # Find or create category
                    if value:
                        category = inventory_service.get_category_by_name(value)
                        if not category:
                            category = inventory_service.create_category({"name": value, "is_active": True})
                        item_data['category_id'] = category.id
                elif col == 'unit_price':
                    item_data['unit_price'] = float(value) if value else 0
                elif col == 'cost_price':
                    item_data['cost_price'] = float(value) if value else None
                elif col == 'currency':
                    item_data['currency'] = value.upper() if value else 'USD'
                elif col == 'track_stock':
                    item_data['track_stock'] = value.lower() in ('true', '1', 'yes')
                elif col == 'current_stock':
                    item_data['current_stock'] = float(value) if value else 0
                elif col == 'minimum_stock':
                    item_data['minimum_stock'] = float(value) if value else 0
                elif col == 'unit_of_measure':
                    item_data['unit_of_measure'] = value if value else 'each'
                elif col == 'item_type':
                    item_data['item_type'] = value if value else 'product'

            # Set defaults for required fields
            item_data.setdefault('unit_price', 0)
            item_data.setdefault('currency', 'USD')
            item_data.setdefault('track_stock', False)
            item_data.setdefault('current_stock', 0)
            item_data.setdefault('minimum_stock', 0)
            item_data.setdefault('unit_of_measure', 'each')
            item_data.setdefault('item_type', 'product')
            item_data.setdefault('is_active', True)

            try:
                created_item = inventory_service.create_item(item_data, current_user.id)
                imported_items.append(created_item)
            except Exception as e:
                logger.error(f"Error importing item on line {line_num}: {e}")
                continue

        log_audit_event(db, current_user.id, current_user.email, "IMPORT", "inventory_items", None, f"Imported {len(imported_items)} items from CSV", None, None, None, "success", None
        )

        return {
            "message": f"Successfully imported {len(imported_items)} items",
            "imported_items": imported_items,
            "total_lines": len(lines) - 1,
            "successful_imports": len(imported_items)
        }
    except Exception as e:
        logger.error(f"Error importing CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import CSV: {str(e)}")


@router.get("/export/csv")
async def export_inventory_csv(
    include_inactive: bool = False,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Export inventory items to CSV format"""
    try:
        # Get items based on filters
        filters = {}
        if not include_inactive:
            filters['is_active'] = True
        if category_id:
            filters['category_id'] = category_id

        items = inventory_service.get_items_with_filters(filters)

        # Create CSV content
        csv_lines = []
        csv_lines.append("name,sku,description,category,unit_price,cost_price,currency,track_stock,current_stock,minimum_stock,unit_of_measure,item_type")

        for item in items:
            category_name = item.category.name if item.category else ""
            line = [
                item.name,
                item.sku or "",
                item.description or "",
                category_name,
                str(item.unit_price),
                str(item.cost_price) if item.cost_price else "",
                item.currency,
                str(item.track_stock).lower(),
                str(item.current_stock),
                str(item.minimum_stock),
                item.unit_of_measure,
                item.item_type
            ]
            csv_lines.append(','.join('"' + str(x).replace('"', '""') + '"' for x in line))

        csv_content = '\n'.join(csv_lines)

        log_audit_event(db, current_user.id, current_user.email, "EXPORT", "inventory_items", None, f"Exported {len(items)} items to CSV", None, None, None, "success", None)

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory_export.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export CSV: {str(e)}")


# === Barcode Management Endpoints ===

@router.get("/items/barcode/{barcode}")
async def get_item_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Get inventory item by barcode"""
    try:
        item = inventory_service.get_item_by_barcode(barcode)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found for barcode")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching item by barcode {barcode}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch item by barcode")


@router.post("/items/{item_id}/barcode")
async def update_item_barcode(
    item_id: int,
    barcode_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Update barcode for an inventory item"""
    try:
        barcode = barcode_data.get('barcode')
        barcode_type = barcode_data.get('barcode_type')
        barcode_format = barcode_data.get('barcode_format')

        if not barcode:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Barcode is required")

        updated_item = inventory_service.update_item_barcode(
            item_id, barcode, barcode_type, barcode_format
        )

        log_audit_event(db, current_user.id, current_user.email, "UPDATE", "inventory_item",
                       str(item_id), f"Updated barcode: {barcode}", None, None, None, "success", None)

        return {"message": "Barcode updated successfully", "item": updated_item}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating barcode for item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update barcode")


@router.post("/barcode/validate")
async def validate_barcode(
    barcode_data: Dict[str, str],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Validate a barcode and detect its type"""
    try:
        barcode = barcode_data.get('barcode')
        if not barcode:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Barcode is required")

        validation_result = inventory_service.validate_barcode(barcode)
        return validation_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating barcode: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate barcode")


@router.get("/barcode/suggestions")
async def get_barcode_suggestions(
    item_name: str = Query(..., description="Item name for generating suggestions"),
    sku: Optional[str] = Query(None, description="SKU for generating suggestions"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Generate barcode suggestions based on item information"""
    try:
        suggestions = inventory_service.generate_barcode_suggestions(item_name, sku)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error generating barcode suggestions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate barcode suggestions")


@router.post("/barcode/bulk-update")
async def bulk_update_barcodes(
    barcode_updates: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """Bulk update barcodes for multiple items"""
    try:
        result = inventory_service.bulk_update_barcodes(barcode_updates)

        log_audit_event(db, current_user.id, current_user.email, "BULK_UPDATE", "inventory_barcodes",
                       None, f"Bulk updated {result['success_count']} barcodes", None, None, None, "success", None)

        return result
    except Exception as e:
        logger.error(f"Error bulk updating barcodes: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to bulk update barcodes")


# Invoice-Inventory Linking Endpoints

@router.get("/items/{item_id}/linked-invoices", response_model=List[Dict[str, Any]])
async def get_invoices_linked_to_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Get all invoices that contain this inventory item"""
    try:
        from core.models.models_per_tenant import Invoice, InvoiceItem

        # Get all invoices that contain this inventory item
        invoice_items = db.query(InvoiceItem.invoice_id).filter(
            InvoiceItem.inventory_item_id == item_id
        ).distinct().all()

        if not invoice_items:
            return []

        # Get unique invoice IDs from invoice items
        invoice_ids = [item.invoice_id for item in invoice_items]

        # Get all stock movements for this item (for additional info)
        stock_movements = stock_service.get_movement_history(item_id, limit=1000)
        invoice_stock_movements = [m for m in stock_movements if m.reference_type == "invoice"]

        # Fetch invoice details with items
        invoices = db.query(
            Invoice.id,
            Invoice.number,
            Invoice.amount,
            Invoice.currency,
            Invoice.status,
            Invoice.due_date,
            Invoice.created_at,
            Invoice.client_id
        ).filter(
            Invoice.id.in_(invoice_ids),
            Invoice.is_deleted == False
        ).all()

        # Get invoice items for this inventory item
        invoice_items = db.query(
            InvoiceItem.invoice_id,
            InvoiceItem.quantity,
            InvoiceItem.price,
            InvoiceItem.amount
        ).filter(
            InvoiceItem.inventory_item_id == item_id,
            InvoiceItem.invoice_id.in_(invoice_ids)
        ).all()

        # Group invoice items by invoice_id
        items_by_invoice = {}
        for item in invoice_items:
            if item.invoice_id not in items_by_invoice:
                items_by_invoice[item.invoice_id] = []
            items_by_invoice[item.invoice_id].append({
                "quantity": float(item.quantity),
                "price": float(item.price),
                "amount": float(item.amount)
            })

        # Get stock movements by invoice
        movements_by_invoice = {}
        for movement in invoice_stock_movements:
            if movement.reference_id not in movements_by_invoice:
                movements_by_invoice[movement.reference_id] = []
            movements_by_invoice[movement.reference_id].append({
                "id": movement.id,
                "quantity": float(movement.quantity),
                "movement_type": movement.movement_type,
                "movement_date": movement.movement_date.isoformat(),
                "notes": movement.notes
            })

        # Build response
        result = []
        for invoice_data in invoices:
            invoice_dict = {
                "id": invoice_data.id,
                "number": invoice_data.number,
                "amount": float(invoice_data.amount),
                "currency": invoice_data.currency,
                "status": invoice_data.status,
                "due_date": invoice_data.due_date.isoformat() if invoice_data.due_date else None,
                "created_at": invoice_data.created_at.isoformat(),
                "client_id": invoice_data.client_id,
                "invoice_items": items_by_invoice.get(invoice_data.id, []),
                "stock_movements": movements_by_invoice.get(invoice_data.id, [])
            }
            result.append(invoice_dict)

        return result
    except Exception as e:
        logger.error(f"Error fetching linked invoices for inventory item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch linked invoices")


@router.get("/items/{item_id}/stock-movement-summary", response_model=Dict[str, Any])
async def get_inventory_item_stock_summary(
    item_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
    stock_service: StockMovementService = Depends(get_stock_service)
):
    """Get stock movement summary for an inventory item, grouped by reference type"""
    try:
        from core.models.models_per_tenant import Invoice, InvoiceItem, Expense

        # Get movement summary by type
        movement_summary = stock_service.get_movement_summary_by_type(item_id, days)

        # Get detailed movements for recent period
        recent_movements = stock_service.get_movement_history(item_id, limit=50)

        # Get linked references (invoices and expenses)
        linked_references = {
            "invoices": [],
            "expenses": []
        }

        # Get invoice references
        invoice_movements = [m for m in recent_movements if m.reference_type == "invoice"]
        if invoice_movements:
            invoice_ids = list(set(m.reference_id for m in invoice_movements))
            invoices = db.query(
                Invoice.id,
                Invoice.number,
                Invoice.amount,
                Invoice.currency,
                Invoice.status,
                Invoice.client_id
            ).filter(Invoice.id.in_(invoice_ids)).all()

            linked_references["invoices"] = [
                {
                    "id": inv.id,
                    "number": inv.number,
                    "amount": float(inv.amount),
                    "currency": inv.currency,
                    "status": inv.status,
                    "client_id": inv.client_id
                }
                for inv in invoices
            ]

        # Get expense references
        expense_movements = [m for m in recent_movements if m.reference_type == "expense"]
        if expense_movements:
            expense_ids = list(set(m.reference_id for m in expense_movements))
            expenses = db.query(
                Expense.id,
                Expense.amount,
                Expense.currency,
                Expense.category,
                Expense.vendor
            ).filter(Expense.id.in_(expense_ids)).all()

            linked_references["expenses"] = [
                {
                    "id": exp.id,
                    "amount": float(exp.amount),
                    "currency": exp.currency,
                    "category": exp.category,
                    "vendor": exp.vendor
                }
                for exp in expenses
            ]

        return {
            "item_id": item_id,
            "movement_summary": movement_summary,
            "recent_movements": [
                {
                    "id": m.id,
                    "movement_type": m.movement_type,
                    "quantity": float(m.quantity),
                    "reference_type": m.reference_type,
                    "reference_id": m.reference_id,
                    "movement_date": m.movement_date.isoformat(),
                    "notes": m.notes
                }
                for m in recent_movements[:20]  # Limit to 20 most recent
            ],
            "linked_references": linked_references,
            "period_days": days
        }

    except Exception as e:
        logger.error(f"Error fetching stock movement summary for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stock movement summary")
