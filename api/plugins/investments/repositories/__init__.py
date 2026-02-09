"""
Investment Repositories Package

This package contains the data access layer for the investment management plugin.
All repositories follow the repository pattern and enforce tenant isolation.
"""

from .portfolio_repository import PortfolioRepository
from .file_attachment_repository import FileAttachmentRepository

__all__ = [
    'PortfolioRepository',
    'FileAttachmentRepository',
]