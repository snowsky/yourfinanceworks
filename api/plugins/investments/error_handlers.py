"""
Investment Management Error Handlers

This module provides centralized error handling for the investment management plugin.
It converts custom exceptions to appropriate HTTP responses with consistent formatting.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from .exceptions import (
    InvestmentError,
    ValidationError,
    TenantAccessError,
    ResourceNotFoundError,
    ConflictError,
    DuplicateTransactionError,
    InsufficientQuantityError,
    PortfolioHasHoldingsError,
    FutureDateError,
    NegativeValueError,
    InvalidEnumValueError,
    DatabaseError,
    CalculationError,
    FileUploadError,
    FileValidationError,
    FileStorageError,
    ExtractionError,
    CloudStorageError
)

# Set up logger
logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    error_message: str,
    details: Optional[List[Dict[str, Any]]] = None,
    error_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response format.

    Args:
        status_code: HTTP status code
        error_message: Main error message
        details: Optional list of error details
        error_code: Optional error code for client handling

    Returns:
        Dictionary containing error response data
    """
    response = {
        "detail": error_message,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": status_code
    }

    if details:
        response["details"] = details

    if error_code:
        response["error_code"] = error_code

    return response


def handle_investment_error(error: InvestmentError) -> JSONResponse:
    """
    Handle custom investment management errors.

    Args:
        error: The investment error to handle

    Returns:
        JSONResponse with appropriate status code and error details
    """
    # Map exception types to HTTP status codes
    status_code_map = {
        ValidationError: 400,
        InsufficientQuantityError: 400,
        FutureDateError: 400,
        NegativeValueError: 400,
        InvalidEnumValueError: 400,
        FileUploadError: 400,
        FileValidationError: 400,
        TenantAccessError: 403,
        ResourceNotFoundError: 404,
        ConflictError: 409,
        DuplicateTransactionError: 409,
        PortfolioHasHoldingsError: 409,
        DatabaseError: 500,
        CalculationError: 500,
        FileStorageError: 500,
        ExtractionError: 500,
        CloudStorageError: 500,
        InvestmentError: 500  # Default for base class
    }

    status_code = status_code_map.get(type(error), 500)

    # Log error details for server errors
    if status_code >= 500:
        logger.error(f"Investment error: {error.message}", exc_info=True)
    else:
        logger.warning(f"Investment validation/client error: {error.message}")

    # Create error response
    response_data = create_error_response(
        status_code=status_code,
        error_message=error.message,
        details=error.details,
        error_code=type(error).__name__
    )

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


def handle_pydantic_validation_error(error: PydanticValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Args:
        error: The Pydantic validation error

    Returns:
        JSONResponse with 400 status and validation details
    """
    logger.warning(f"Pydantic validation error: {error}")

    # Convert Pydantic errors to our format
    details = []
    for err in error.errors():
        field_path = ".".join(str(loc) for loc in err["loc"])
        details.append({
            "field": field_path,
            "message": err["msg"],
            "code": err["type"]
        })

    response_data = create_error_response(
        status_code=400,
        error_message="Validation failed",
        details=details,
        error_code="ValidationError"
    )

    return JSONResponse(
        status_code=400,
        content=response_data
    )


def handle_sqlalchemy_error(error: SQLAlchemyError) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.

    Args:
        error: The SQLAlchemy error

    Returns:
        JSONResponse with appropriate status code
    """
    logger.error(f"Database error: {error}", exc_info=True)

    # Handle specific database errors
    if isinstance(error, IntegrityError):
        # Check for common integrity constraint violations
        error_msg = str(error.orig) if hasattr(error, 'orig') else str(error)

        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            response_data = create_error_response(
                status_code=409,
                error_message="Resource already exists or violates uniqueness constraint",
                error_code="DuplicateResourceError"
            )
            return JSONResponse(status_code=409, content=response_data)

        elif "foreign key" in error_msg.lower():
            response_data = create_error_response(
                status_code=400,
                error_message="Invalid reference to related resource",
                error_code="InvalidReferenceError"
            )
            return JSONResponse(status_code=400, content=response_data)

        elif "check constraint" in error_msg.lower():
            response_data = create_error_response(
                status_code=400,
                error_message="Data violates business rules or constraints",
                error_code="ConstraintViolationError"
            )
            return JSONResponse(status_code=400, content=response_data)

    # Generic database error
    response_data = create_error_response(
        status_code=500,
        error_message="Database operation failed",
        error_code="DatabaseError"
    )

    return JSONResponse(status_code=500, content=response_data)


def handle_generic_exception(error: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        error: The unexpected exception

    Returns:
        JSONResponse with 500 status
    """
    logger.error(f"Unexpected error: {error}", exc_info=True)

    response_data = create_error_response(
        status_code=500,
        error_message="An unexpected error occurred",
        error_code="InternalServerError"
    )

    return JSONResponse(status_code=500, content=response_data)


def create_investment_exception_handler():
    """
    Create a comprehensive exception handler for investment endpoints.

    Returns:
        Function that can be used as FastAPI exception handler
    """
    async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all exceptions for investment endpoints.

        Args:
            request: The FastAPI request object
            exc: The exception that occurred

        Returns:
            JSONResponse with appropriate error details
        """
        # Handle custom investment errors
        if isinstance(exc, InvestmentError):
            return handle_investment_error(exc)

        # Handle Pydantic validation errors
        elif isinstance(exc, PydanticValidationError):
            return handle_pydantic_validation_error(exc)

        # Handle SQLAlchemy errors
        elif isinstance(exc, SQLAlchemyError):
            return handle_sqlalchemy_error(exc)

        # Handle FastAPI HTTP exceptions (pass through)
        elif isinstance(exc, HTTPException):
            response_data = create_error_response(
                status_code=exc.status_code,
                error_message=exc.detail,
                error_code="HTTPException"
            )
            return JSONResponse(status_code=exc.status_code, content=response_data)

        # Handle all other exceptions
        else:
            return handle_generic_exception(exc)

    return exception_handler


# Convenience functions for raising common errors
def raise_validation_error(message: str, field: Optional[str] = None) -> None:
    """Raise a validation error with optional field information."""
    details = [{"field": field, "message": message}] if field else None
    raise ValidationError(message, details)


def raise_not_found_error(resource_type: str, resource_id: Any) -> None:
    """Raise a not found error for a specific resource."""
    raise ResourceNotFoundError(f"{resource_type} with ID {resource_id} not found")


def raise_tenant_access_error(resource_type: str, resource_id: Any) -> None:
    """Raise a tenant access error for a specific resource."""
    raise TenantAccessError(f"Access denied to {resource_type} with ID {resource_id}")


def raise_conflict_error(message: str) -> None:
    """Raise a conflict error with a custom message."""
    raise ConflictError(message)


def raise_duplicate_transaction_error() -> None:
    """Raise a duplicate transaction error."""
    raise DuplicateTransactionError("Duplicate transaction detected within 60-second window")


def raise_file_validation_error(message: str) -> None:
    """Raise a file validation error."""
    raise FileValidationError(message)


def raise_file_upload_error(message: str) -> None:
    """Raise a file upload error."""
    raise FileUploadError(message)


def raise_file_storage_error(message: str) -> None:
    """Raise a file storage error."""
    raise FileStorageError(message)


def raise_extraction_error(message: str) -> None:
    """Raise an extraction error."""
    raise ExtractionError(message)


def raise_cloud_storage_error(message: str) -> None:
    """Raise a cloud storage error."""
    raise CloudStorageError(message)