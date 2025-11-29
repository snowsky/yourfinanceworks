"""
Cloud storage services package.

This package provides a unified interface for cloud storage operations
across multiple providers (AWS S3, Azure Blob Storage, Google Cloud Storage)
with automatic fallback to local storage.
"""

from core.interfaces.storage_provider import (
    CloudStorageProvider,
    StorageProvider,
    StorageResult,
    StorageConfig,
    FileMetadata,
    HealthCheckResult
)
from .factory import StorageProviderFactory

__all__ = [
    'CloudStorageProvider',
    'StorageResult', 
    'StorageConfig',
    'StorageProvider',
    'FileMetadata',
    'HealthCheckResult',
    'StorageProviderFactory'
]