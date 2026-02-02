"""
Abstract base class and data structures for cloud storage providers.

This module defines the common interface that all storage providers must implement,
along with supporting data classes for consistent responses and configuration.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime


class StorageProvider(Enum):
    """Enumeration of supported storage providers."""
    AWS_S3 = "aws_s3"
    AZURE_BLOB = "azure_blob"
    GCP_STORAGE = "gcp_storage"
    LOCAL = "local"


@dataclass
class StorageResult:
    """Result object for storage operations with consistent response format."""
    success: bool
    file_url: Optional[str] = None
    file_key: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    file_content: Optional[bytes] = None  # For downloads when generate_url=False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    operation_duration_ms: Optional[int] = None
    
    def __post_init__(self):
        """Validate result data after initialization."""
        if self.success and not self.file_key:
            raise ValueError("Successful storage result must include file_key")


@dataclass
class StorageConfig:
    """Configuration for a storage provider."""
    provider: StorageProvider
    enabled: bool = True
    is_primary: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    health_check_interval: int = 300  # seconds
    max_retry_attempts: int = 3
    timeout_seconds: int = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not isinstance(self.config, dict):
            raise ValueError("config must be a dictionary")


@dataclass
class FileMetadata:
    """Metadata for files stored in cloud storage."""
    file_key: str
    file_size: int
    content_type: str
    created_at: datetime
    modified_at: Optional[datetime] = None
    tenant_id: Optional[str] = None
    checksum: Optional[str] = None
    custom_metadata: Optional[Dict[str, str]] = None


@dataclass
class HealthCheckResult:
    """Result of a provider health check."""
    provider: StorageProvider
    healthy: bool
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    last_check: Optional[datetime] = None
    additional_info: Optional[Dict[str, Any]] = None


class CloudStorageProvider(ABC):
    """
    Abstract base class for cloud storage providers.
    
    All storage providers must implement this interface to ensure
    consistent behavior across different cloud storage backends.
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize the storage provider with configuration."""
        self.config = config
        self.provider_type = config.provider
        self._last_health_check: Optional[HealthCheckResult] = None
    
    @abstractmethod
    async def upload_file(
        self, 
        file_content: bytes, 
        file_key: str, 
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Upload file to storage provider.
        
        Args:
            file_content: The file content as bytes
            file_key: Unique key/path for the file in storage
            content_type: MIME type of the file
            metadata: Optional metadata to store with the file
            
        Returns:
            StorageResult with operation details
        """
        pass
    
    @abstractmethod
    async def download_file(self, file_key: str) -> StorageResult:
        """
        Download file from storage provider.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            StorageResult with file content or download URL
        """
        pass
    
    @abstractmethod
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete file from storage provider.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_file_url(
        self, 
        file_key: str, 
        expiry_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate temporary access URL for file.
        
        Args:
            file_key: Unique key/path for the file in storage
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            Temporary URL string or None if generation failed
        """
        pass
    
    @abstractmethod
    async def list_files(
        self, 
        prefix: str = "", 
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List files with given prefix.
        
        Args:
            prefix: Prefix to filter files
            limit: Maximum number of files to return
            continuation_token: Token for pagination
            
        Returns:
            Dictionary with files list and pagination info
        """
        pass
    
    @abstractmethod
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if file exists in storage.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a file.
        
        Args:
            file_key: Unique key/path for the file in storage
            
        Returns:
            FileMetadata object or None if file not found
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """
        Check provider health status.
        
        Returns:
            HealthCheckResult with provider status information
        """
        pass
    
    async def batch_upload(
        self,
        files: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[StorageResult]:
        """
        Upload multiple files concurrently.
        
        Args:
            files: List of file dictionaries with keys: content, key, content_type, metadata
            max_concurrent: Maximum number of concurrent uploads
            
        Returns:
            List of StorageResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def upload_single(file_info: Dict[str, Any]) -> StorageResult:
            async with semaphore:
                return await self.upload_file(
                    file_content=file_info['content'],
                    file_key=file_info['key'],
                    content_type=file_info['content_type'],
                    metadata=file_info.get('metadata')
                )
        
        tasks = [upload_single(file_info) for file_info in files]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def batch_delete(
        self,
        file_keys: List[str],
        max_concurrent: int = 10
    ) -> List[bool]:
        """
        Delete multiple files concurrently.
        
        Args:
            file_keys: List of file keys to delete
            max_concurrent: Maximum number of concurrent deletions
            
        Returns:
            List of boolean results for each deletion
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def delete_single(file_key: str) -> bool:
            async with semaphore:
                return await self.delete_file(file_key)
        
        tasks = [delete_single(key) for key in file_keys]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def get_last_health_check(self) -> Optional[HealthCheckResult]:
        """Get the last health check result."""
        return self._last_health_check
    
    def is_healthy(self) -> bool:
        """Check if provider is currently healthy based on last health check."""
        if not self._last_health_check:
            return False
        return self._last_health_check.healthy
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information and configuration summary."""
        return {
            'provider': self.provider_type.value,
            'enabled': self.config.enabled,
            'is_primary': self.config.is_primary,
            'healthy': self.is_healthy(),
            'last_health_check': self._last_health_check.last_check if self._last_health_check else None
        }