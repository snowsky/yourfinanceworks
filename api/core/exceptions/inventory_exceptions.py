"""
Custom exceptions for inventory management system
"""
from typing import Optional, Dict, Any


class InventoryException(Exception):
    """Base exception for inventory-related errors"""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ItemNotFoundException(InventoryException):
    """Raised when an inventory item is not found"""

    def __init__(self, item_id: int):
        super().__init__(
            f"Inventory item with ID {item_id} not found",
            "ITEM_NOT_FOUND",
            {"item_id": item_id}
        )


class CategoryNotFoundException(InventoryException):
    """Raised when an inventory category is not found"""

    def __init__(self, category_id: int):
        super().__init__(
            f"Inventory category with ID {category_id} not found",
            "CATEGORY_NOT_FOUND",
            {"category_id": category_id}
        )


class InsufficientStockException(InventoryException):
    """Raised when there is insufficient stock for an operation"""

    def __init__(self, item_id: int, requested: float, available: float):
        super().__init__(
            f"Insufficient stock for item {item_id}. Requested: {requested}, Available: {available}",
            "INSUFFICIENT_STOCK",
            {
                "item_id": item_id,
                "requested": requested,
                "available": available
            }
        )


class DuplicateSKUException(InventoryException):
    """Raised when attempting to create an item with a duplicate SKU"""

    def __init__(self, sku: str):
        super().__init__(
            f"SKU '{sku}' already exists",
            "DUPLICATE_SKU",
            {"sku": sku}
        )


class DuplicateCategoryException(InventoryException):
    """Raised when attempting to create a category with a duplicate name"""

    def __init__(self, name: str):
        super().__init__(
            f"Category name '{name}' already exists",
            "DUPLICATE_CATEGORY",
            {"category_name": name}
        )


class ItemInUseException(InventoryException):
    """Raised when attempting to delete an item that is referenced in invoices or expenses"""

    def __init__(self, item_id: int, references: Dict[str, int]):
        message = f"Cannot delete item {item_id} as it is referenced in:"
        for ref_type, count in references.items():
            message += f" {count} {ref_type}"
        super().__init__(
            message,
            "ITEM_IN_USE",
            {
                "item_id": item_id,
                "references": references
            }
        )


class CategoryInUseException(InventoryException):
    """Raised when attempting to delete a category that has associated items"""

    def __init__(self, category_id: int, item_count: int):
        super().__init__(
            f"Cannot delete category {category_id} as it has {item_count} associated items",
            "CATEGORY_IN_USE",
            {
                "category_id": category_id,
                "item_count": item_count
            }
        )


class InvalidMovementTypeException(InventoryException):
    """Raised when an invalid movement type is provided"""

    def __init__(self, movement_type: str):
        super().__init__(
            f"Invalid movement type: {movement_type}",
            "INVALID_MOVEMENT_TYPE",
            {"movement_type": movement_type}
        )


class InvalidItemTypeException(InventoryException):
    """Raised when an invalid item type is provided"""

    def __init__(self, item_type: str):
        super().__init__(
            f"Invalid item type: {item_type}",
            "INVALID_ITEM_TYPE",
            {"item_type": item_type}
        )


class StockNotTrackedException(InventoryException):
    """Raised when attempting to perform stock operations on an item that doesn't track stock"""

    def __init__(self, item_id: int):
        super().__init__(
            f"Item {item_id} does not track stock levels",
            "STOCK_NOT_TRACKED",
            {"item_id": item_id}
        )


class MovementValidationException(InventoryException):
    """Raised when stock movement validation fails"""

    def __init__(self, item_id: int, reason: str):
        super().__init__(
            f"Movement validation failed for item {item_id}: {reason}",
            "MOVEMENT_VALIDATION_FAILED",
            {
                "item_id": item_id,
                "reason": reason
            }
        )


class InventoryValidationException(InventoryException):
    """Raised when inventory data validation fails"""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for field '{field}' with value '{value}': {reason}",
            "VALIDATION_FAILED",
            {
                "field": field,
                "value": value,
                "reason": reason
            }
        )


class BulkOperationException(InventoryException):
    """Raised when a bulk operation partially fails"""

    def __init__(self, operation: str, success_count: int, failure_count: int, errors: list):
        message = f"Bulk {operation} completed with {success_count} successes and {failure_count} failures"
        super().__init__(
            message,
            "BULK_OPERATION_PARTIAL_FAILURE",
            {
                "operation": operation,
                "success_count": success_count,
                "failure_count": failure_count,
                "errors": errors
            }
        )


class InventoryServiceException(InventoryException):
    """Raised when an internal service error occurs"""

    def __init__(self, operation: str, details: str):
        super().__init__(
            f"Inventory service error during {operation}: {details}",
            "SERVICE_ERROR",
            {
                "operation": operation,
                "details": details
            }
        )


class DatabaseIntegrityException(InventoryException):
    """Raised when database integrity constraints are violated"""

    def __init__(self, constraint: str, details: str):
        super().__init__(
            f"Database integrity violation: {constraint} - {details}",
            "DATABASE_INTEGRITY_ERROR",
            {
                "constraint": constraint,
                "details": details
            }
        )
