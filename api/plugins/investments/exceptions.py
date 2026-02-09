"""
Investment Management Custom Exceptions

This module defines custom exceptions for the investment management plugin
to provide clear error handling and appropriate HTTP status codes.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime


class InvestmentError(Exception):
    """Base exception for investment management errors"""

    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class ValidationError(InvestmentError):
    """Raised when input validation fails (HTTP 400)"""
    pass


class TenantAccessError(InvestmentError):
    """Raised when tenant tries to access resources they don't own (HTTP 403)"""
    pass


class ResourceNotFoundError(InvestmentError):
    """Raised when a requested resource doesn't exist (HTTP 404)"""
    pass


class ConflictError(InvestmentError):
    """Raised when an operation conflicts with current state (HTTP 409)"""
    pass


class DuplicateTransactionError(ConflictError):
    """Raised when a duplicate transaction is detected (HTTP 409)"""
    pass


class InsufficientQuantityError(ValidationError):
    """Raised when trying to sell more shares than owned"""
    pass


class PortfolioHasHoldingsError(ConflictError):
    """Raised when trying to delete a portfolio that has holdings"""
    pass


class FutureDateError(ValidationError):
    """Raised when a date is in the future when it shouldn't be"""
    pass


class NegativeValueError(ValidationError):
    """Raised when a value is negative when it should be positive"""
    pass


class InvalidEnumValueError(ValidationError):
    """Raised when an invalid enum value is provided"""
    pass


class DatabaseError(InvestmentError):
    """Raised when a database operation fails (HTTP 500)"""
    pass


class CalculationError(InvestmentError):
    """Raised when a financial calculation fails (HTTP 500)"""
    pass


class FileUploadError(ValidationError):
    """Raised when file upload fails (HTTP 400)"""
    pass


class FileValidationError(ValidationError):
    """Raised when file validation fails (HTTP 400)"""
    pass


class FileStorageError(InvestmentError):
    """Raised when file storage operation fails (HTTP 500)"""
    pass


class ExtractionError(InvestmentError):
    """Raised when LLM extraction fails (HTTP 500)"""
    pass


class CloudStorageError(InvestmentError):
    """Raised when cloud storage operation fails (HTTP 500)"""
    pass