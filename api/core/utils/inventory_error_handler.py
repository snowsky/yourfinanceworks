"""
Utility functions for handling inventory exceptions in API responses
"""
from fastapi import HTTPException, status
from typing import Union
import logging

from core.exceptions.inventory_exceptions import InventoryException
from core.schemas.inventory import InventoryErrorResponse, InventoryValidationErrorResponse, ValidationErrorDetail

logger = logging.getLogger(__name__)


def handle_inventory_exception(e: Union[InventoryException, Exception]) -> None:
    """
    Handle inventory exceptions and convert them to appropriate HTTP responses
    """
    if isinstance(e, InventoryException):
        logger.warning(f"Inventory exception: {e.error_code} - {e.message}")

        # Map error codes to HTTP status codes
        status_mapping = {
            "ITEM_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "CATEGORY_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "INSUFFICIENT_STOCK": status.HTTP_400_BAD_REQUEST,
            "DUPLICATE_SKU": status.HTTP_400_BAD_REQUEST,
            "DUPLICATE_CATEGORY": status.HTTP_400_BAD_REQUEST,
            "ITEM_IN_USE": status.HTTP_400_BAD_REQUEST,
            "CATEGORY_IN_USE": status.HTTP_400_BAD_REQUEST,
            "INVALID_MOVEMENT_TYPE": status.HTTP_400_BAD_REQUEST,
            "INVALID_ITEM_TYPE": status.HTTP_400_BAD_REQUEST,
            "STOCK_NOT_TRACKED": status.HTTP_400_BAD_REQUEST,
            "MOVEMENT_VALIDATION_FAILED": status.HTTP_400_BAD_REQUEST,
            "VALIDATION_FAILED": status.HTTP_400_BAD_REQUEST,
            "BULK_OPERATION_PARTIAL_FAILURE": status.HTTP_207_MULTI_STATUS,
            "SERVICE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "DATABASE_INTEGRITY_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }

        http_status = status_mapping.get(e.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        raise HTTPException(
            status_code=http_status,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    else:
        # Handle unexpected exceptions
        logger.error(f"Unexpected error in inventory operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "An unexpected error occurred",
                "error_code": "INTERNAL_ERROR"
            }
        )


def create_validation_error_response(field_errors: list) -> InventoryValidationErrorResponse:
    """
    Create a standardized validation error response
    """
    validation_errors = []
    for field, message in field_errors:
        validation_errors.append(ValidationErrorDetail(
            field=field,
            message=message
        ))

    return InventoryValidationErrorResponse(
        error="Validation failed",
        error_code="VALIDATION_FAILED",
        validation_errors=validation_errors
    )


def handle_bulk_operation_errors(success_count: int, failure_count: int, errors: list) -> dict:
    """
    Handle responses for bulk operations with partial failures
    """
    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "total_processed": success_count + failure_count,
        "success_rate": success_count / (success_count + failure_count) if (success_count + failure_count) > 0 else 0,
        "errors": errors,
        "message": f"Processed {success_count + failure_count} items with {success_count} successes and {failure_count} failures"
    }


def validate_inventory_operation(operation: str, **kwargs) -> None:
    """
    Validate common inventory operation parameters
    """
    from core.exceptions.inventory_exceptions import InventoryValidationException

    if operation == "create_item":
        if kwargs.get('unit_price', 0) <= 0:
            raise InventoryValidationException("unit_price", kwargs.get('unit_price'), "Must be greater than 0")

        if kwargs.get('track_stock') and kwargs.get('current_stock', 0) < 0:
            raise InventoryValidationException("current_stock", kwargs.get('current_stock'), "Cannot be negative when tracking stock")

    elif operation == "stock_movement":
        if kwargs.get('quantity', 0) == 0:
            raise InventoryValidationException("quantity", kwargs.get('quantity'), "Cannot be zero")

        if not kwargs.get('item_id'):
            raise InventoryValidationException("item_id", kwargs.get('item_id'), "Required for stock movement")

    elif operation == "category_operation":
        if not kwargs.get('name', '').strip():
            raise InventoryValidationException("name", kwargs.get('name'), "Cannot be empty or whitespace")

    # Add more operation validations as needed


# Decorator for inventory endpoints
def inventory_endpoint(operation_name: str = None):
    """
    Decorator to handle inventory exceptions in API endpoints
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handle_inventory_exception(e)
        return wrapper
    return decorator


# Common error messages
INVENTORY_ERROR_MESSAGES = {
    "item_not_found": "The requested inventory item was not found",
    "category_not_found": "The requested inventory category was not found",
    "insufficient_stock": "Insufficient stock available for the requested operation",
    "duplicate_sku": "An item with this SKU already exists",
    "duplicate_category": "A category with this name already exists",
    "item_in_use": "This item cannot be deleted as it is referenced in existing transactions",
    "category_in_use": "This category cannot be deleted as it contains items",
    "invalid_movement": "The requested stock movement is not valid",
    "service_unavailable": "Inventory service is temporarily unavailable",
    "database_error": "A database error occurred while processing your request"
}


def get_error_message(error_code: str, default: str = None) -> str:
    """
    Get a user-friendly error message for an error code
    """
    return INVENTORY_ERROR_MESSAGES.get(error_code, default or "An error occurred")
