"""
Sandbox validation decorators for external API endpoints.
Provides reusable decorators to check sandbox mode and prevent unauthorized operations.
"""

from functools import wraps
from typing import Callable, Any
from fastapi import HTTPException, status
from core.models.api_models import APIClient


def require_production_api_key(error_message: str = None):
    """
    Decorator to check if API client is not in sandbox mode.

    Args:
        error_message: Custom error message (optional)

    Returns:
        Decorator function that raises HTTPException if client is in sandbox mode

    Usage:
        @require_production_api_key("Sandbox API keys cannot perform this operation.")
        async def my_endpoint(api_client: APIClient, ...):
            # Endpoint logic - api_client is guaranteed to be production
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Find api_client in args or kwargs
            api_client = None

            # Check positional arguments
            for arg in args:
                if isinstance(arg, APIClient):
                    api_client = arg
                    break

            # Check keyword arguments  
            if api_client is None:
                for key, value in kwargs.items():
                    if isinstance(value, APIClient):
                        api_client = value
                        break

            if api_client and api_client.is_sandbox:
                message = error_message or "Sandbox API keys cannot perform this operation. Use a production API key."
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_production_auth_context(error_message: str = None):
    """
    Decorator to check if auth context is not in sandbox mode.

    Args:
        error_message: Custom error message (optional)

    Returns:
        Decorator function that raises HTTPException if auth context is in sandbox mode

    Usage:
        @require_production_auth_context("Sandbox API keys cannot perform this operation.")
        async def my_endpoint(auth_context: AuthContext, ...):
            # Endpoint logic - auth_context is guaranteed to be production
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Find auth_context in args or kwargs
            auth_context = None

            # Check positional arguments
            for arg in args:
                if hasattr(arg, 'is_sandbox'):
                    auth_context = arg
                    break

            # Check keyword arguments  
            if auth_context is None:
                for key, value in kwargs.items():
                    if hasattr(value, 'is_sandbox'):
                        auth_context = value
                        break

            if auth_context and auth_context.is_sandbox:
                message = error_message or "Sandbox API keys cannot perform this operation. Use a production API key."
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
