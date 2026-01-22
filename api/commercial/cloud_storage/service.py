"""
Cloud Storage Service - Main orchestration service for cloud file storage.

This service provides a unified interface for file storage operations across
multiple cloud providers with automatic fallback, health checking, and
comprehensive logging capabilities.
"""

import logging
import time
import mimetypes
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from core.interfaces.storage_provider import (
    CloudStorageProvider, 
    StorageResult, 
    StorageConfig, 
    StorageProvider
)
from commercial.cloud_storage.providers.factory import StorageProviderFactory
from commercial.cloud_storage.providers.circuit_breaker import (
    CloudStorageCircuitBreaker, 
    StorageCircuitBreakerManager,
    storage_circuit_breaker_manager
)
from commercial.cloud_storage.providers.logging_service import StorageLoggingService
from commercial.cloud_storage.providers.disaster_recovery_service import (
    DisasterRecoveryService, 
    ReplicationConfig,
    ReplicationStatus
)
from commercial.cloud_storage.config import CloudStorageConfig
from core.models.models_per_tenant import StorageOperationLog
from commercial.integrations.circuit_breaker import CircuitBreakerOpenException

logger = logging.getLogger(__name__)


class CloudStorageService:
    """
    Main service for cloud storage operations with provider abstraction
    and automatic fallback capabilities.
    
    This service orchestrates multiple storage providers, handles automatic
    failover, and provides comprehensive logging and monitoring.
    """
    
    def __init__(self, db: Session, config: Optional[CloudStorageConfig] = None):
        """
        Initialize the cloud storage service.
        
        Args:
            db: Database session for logging operations
            config: Cloud storage configuration (uses default if None)
        """
        self.db = db
        self.config = config or CloudStorageConfig()
        
        # Initialize provider factory
        self.provider_factory = StorageProviderFactory(self.config)
        
        # Initialize circuit breaker manager
        self.circuit_breaker_manager = storage_circuit_breaker_manager
        
        # Initialize logging service
        self.logging_service = StorageLoggingService(db)
        
        # Initialize disaster recovery service
        dr_config = ReplicationConfig(
            enabled=config.disaster_recovery_enabled if hasattr(config, 'disaster_recovery_enabled') else False,
            primary_region=config.primary_region if hasattr(config, 'primary_region') else "us-east-1",
            backup_regions=config.backup_regions if hasattr(config, 'backup_regions') else [],
            critical_file_patterns=config.critical_file_patterns if hasattr(config, 'critical_file_patterns') else ["invoices/", "contracts/"],
            auto_failover_enabled=config.auto_failover_enabled if hasattr(config, 'auto_failover_enabled') else True
        )
        self.disaster_recovery = DisasterRecoveryService(db, self.provider_factory, dr_config)
        
        # Cache for provider instances
        self._provider_cache: Dict[StorageProvider, CloudStorageProvider] = {}
        
        logger.info("Cloud storage service initialized with disaster recovery")
    
    def _generate_file_key(
        self,
        tenant_id: str,
        item_id: int,
        attachment_type: str,
        original_filename: str
    ) -> str:
        """
        Generate a unique file key for cloud storage.
        
        Args:
            tenant_id: Tenant identifier
            item_id: Item identifier (invoice, expense, etc.)
            attachment_type: Type of attachment (images, documents, etc.)
            original_filename: Original filename
            
        Returns:
            Unique file key for storage
        """
        # Create tenant-scoped path similar to local storage
        safe_filename = Path(original_filename).name  # Remove any path components
        timestamp = int(time.time())
        
        return f"tenant_{tenant_id}/{attachment_type}/{item_id}_{timestamp}_{safe_filename}"
    
    def _get_primary_provider(self) -> Optional[CloudStorageProvider]:
        """
        Get the primary storage provider.
        
        Returns:
            Primary provider instance or None if not available
        """
        try:
            return self.provider_factory.get_primary_provider()
        except Exception as e:
            logger.warning(f"Failed to get primary provider: {e}")
            return None
    
    def _get_fallback_providers(self) -> List[CloudStorageProvider]:
        """
        Get fallback providers in order of preference.
        
        Returns:
            List of fallback provider instances
        """
        try:
            return self.provider_factory.get_fallback_providers()
        except Exception as e:
            logger.warning(f"Failed to get fallback providers: {e}")
            return []
    
    def _is_provider_healthy(self, provider_type: StorageProvider) -> bool:
        """
        Check if a provider is currently healthy.
        
        Args:
            provider_type: The provider type to check
            
        Returns:
            True if provider is healthy
        """
        try:
            # Check both factory health and circuit breaker status
            factory_healthy = self.provider_factory.is_provider_healthy(provider_type)
            
            # Get circuit breaker for this provider
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider_type.value)
            circuit_healthy = not circuit_breaker.should_skip_provider()
            
            return factory_healthy and circuit_healthy
        except Exception as e:
            logger.warning(f"Health check failed for {provider_type.value}: {e}")
            return False
    
    async def _store_with_provider(
        self,
        provider: CloudStorageProvider,
        file_content: bytes,
        file_key: str,
        original_filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Store file with a specific provider.
        
        Args:
            provider: Storage provider instance
            file_content: File content as bytes
            file_key: Unique file key
            original_filename: Original filename
            metadata: Optional metadata
            
        Returns:
            StorageResult with operation details
        """
        # Determine content type
        content_type, _ = mimetypes.guess_type(original_filename)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Add metadata
        file_metadata = metadata or {}
        file_metadata.update({
            'original_filename': original_filename,
            'upload_timestamp': datetime.now().isoformat(),
            'file_size': len(file_content)
        })
        
        # Upload file using circuit breaker
        start_time = time.time()
        try:
            # Get circuit breaker for this provider
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider.provider_type.value)
            
            # Execute upload through circuit breaker
            result = await circuit_breaker.call_with_fallback_detection(
                provider.upload_file,
                "upload",
                file_content=file_content,
                file_key=file_key,
                content_type=content_type,
                metadata=file_metadata
            )
            
            # Add timing information
            duration_ms = int((time.time() - start_time) * 1000)
            result.operation_duration_ms = duration_ms
            result.provider = provider.provider_type.value
            
            return result
            
        except CircuitBreakerOpenException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Circuit breaker open for provider {provider.provider_type.value}: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Provider unavailable (circuit breaker open): {str(e)}",
                provider=provider.provider_type.value,
                operation_duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Upload failed with provider {provider.provider_type.value}: {e}")
            
            return StorageResult(
                success=False,
                error_message=f"Upload failed: {str(e)}",
                provider=provider.provider_type.value,
                operation_duration_ms=duration_ms
            )
    
    async def store_file(
        self,
        file_content: bytes,
        tenant_id: str,
        item_id: int,
        attachment_type: str,
        original_filename: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
        file_key: Optional[str] = None
    ) -> StorageResult:
        """
        Store file using configured provider with automatic fallback.
        
        Args:
            file_content: File content as bytes
            tenant_id: Tenant identifier
            item_id: Item identifier
            attachment_type: Attachment type (images, documents, etc.)
            original_filename: Original filename
            user_id: User performing the operation
            metadata: Optional metadata
            file_key: Optional custom file key (if None, one is generated)
            
        Returns:
            StorageResult with operation details
        """
        if file_key is None:
            file_key = self._generate_file_key(tenant_id, item_id, attachment_type, original_filename)
        
        logger.info(f"Storing file {original_filename} for tenant {tenant_id}, item {item_id}")
        
        # Try primary provider first
        primary_provider = self._get_primary_provider()
        if primary_provider and self._is_provider_healthy(primary_provider.provider_type):
            try:
                result = await self._store_with_provider(
                    primary_provider, file_content, file_key, original_filename, metadata
                )
                
                if result.success:
                    await self.logging_service.log_operation(
                        operation_type="upload",
                        file_key=file_key,
                        provider=result.provider,
                        success=True,
                        file_size=len(file_content),
                        duration_ms=result.operation_duration_ms,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        additional_metadata={'primary_provider': True}
                    )
                    
                    # Trigger disaster recovery replication for critical files
                    if self.disaster_recovery.config.enabled:
                        try:
                            replication_record = await self.disaster_recovery.replicate_file(
                                file_key=file_key,
                                file_content=file_content,
                                primary_provider=primary_provider,
                                metadata=metadata
                            )
                            logger.info(f"Disaster recovery replication status for {file_key}: {replication_record.status.value}")
                        except Exception as e:
                            logger.error(f"Disaster recovery replication failed for {file_key}: {e}")
                            # Don't fail the main upload if replication fails
                    
                    logger.info(f"Successfully stored file {file_key} with primary provider {primary_provider.provider_type.value}")
                    return result
                else:
                    logger.warning(f"Primary provider {primary_provider.provider_type.value} failed: {result.error_message}")
                    
            except CircuitBreakerOpenException as e:
                logger.warning(f"Primary provider circuit breaker is open: {e}")
            except Exception as e:
                logger.warning(f"Primary provider {primary_provider.provider_type.value} failed: {e}")
        
        # Try fallback providers
        fallback_providers = self._get_fallback_providers()
        for provider in fallback_providers:
            if not self._is_provider_healthy(provider.provider_type):
                continue
                
            try:
                result = await self._store_with_provider(
                    provider, file_content, file_key, original_filename, metadata
                )
                
                if result.success:
                    await self.logging_service.log_operation(
                        operation_type="upload",
                        file_key=file_key,
                        provider=result.provider,
                        success=True,
                        file_size=len(file_content),
                        duration_ms=result.operation_duration_ms,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        additional_metadata={'fallback_provider': True, 'reason': 'primary_failure'}
                    )
                    logger.info(f"Successfully stored file {file_key} with fallback provider {provider.provider_type.value}")
                    return result
                else:
                    logger.warning(f"Fallback provider {provider.provider_type.value} failed: {result.error_message}")
                    
            except CircuitBreakerOpenException as e:
                logger.warning(f"Fallback provider circuit breaker is open: {e}")
            except Exception as e:
                logger.warning(f"Fallback provider {provider.provider_type.value} failed: {e}")
        
        # All providers failed
        error_message = "All storage providers failed"
        await self.logging_service.log_operation(
            operation_type="upload",
            file_key=file_key,
            provider="none",
            success=False,
            file_size=len(file_content),
            tenant_id=tenant_id,
            user_id=user_id,
            error_message=error_message
        )
        
        return StorageResult(
            success=False,
            error_message=error_message
        )
    
    async def retrieve_file(
        self,
        file_key: str,
        tenant_id: str,
        user_id: int,
        generate_url: bool = True,
        expiry_seconds: int = 3600
    ) -> StorageResult:
        """
        Retrieve file from any available provider.
        
        Args:
            file_key: Unique file key
            tenant_id: Tenant identifier for logging
            user_id: User performing the operation
            generate_url: Whether to generate a temporary URL or download content
            expiry_seconds: URL expiration time in seconds
            
        Returns:
            StorageResult with file URL or content
        """
        logger.info(f"Retrieving file {file_key} for tenant {tenant_id}")
        
        # Try to find file in cloud providers first (excluding local)
        cloud_providers = [StorageProvider.AWS_S3, StorageProvider.AZURE_BLOB, StorageProvider.GCP_STORAGE]
        
        for provider_type in cloud_providers:
            provider = self.provider_factory.get_provider(provider_type)
            if not provider or not self._is_provider_healthy(provider_type):
                continue
            
            try:
                start_time = time.time()
                
                # Get circuit breaker for this provider
                circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider_type.value)
                
                if generate_url:
                    url = await circuit_breaker.call_with_fallback_detection(
                        provider.get_file_url,
                        "download",
                        file_key,
                        expiry_seconds
                    )
                    if url:
                        duration_ms = int((time.time() - start_time) * 1000)
                        
                        await self.logging_service.log_operation(
                            operation_type="download",
                            file_key=file_key,
                            provider=provider_type.value,
                            success=True,
                            duration_ms=duration_ms,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            additional_metadata={'url_generated': True}
                        )
                        
                        return StorageResult(
                            success=True,
                            file_url=url,
                            file_key=file_key,
                            provider=provider_type.value,
                            operation_duration_ms=duration_ms
                        )
                else:
                    result = await circuit_breaker.call_with_fallback_detection(
                        provider.download_file,
                        "download",
                        file_key
                    )
                    if result.success:
                        duration_ms = int((time.time() - start_time) * 1000)
                        result.operation_duration_ms = duration_ms
                        result.provider = provider_type.value
                        
                        await self.logging_service.log_operation(
                            operation_type="download",
                            file_key=file_key,
                            provider=provider_type.value,
                            success=True,
                            file_size=result.file_size,
                            duration_ms=duration_ms,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            additional_metadata={'content_downloaded': True}
                        )
                        
                        return result
                        
            except CircuitBreakerOpenException as e:
                logger.warning(f"Provider {provider_type.value} circuit breaker is open: {e}")
            except Exception as e:
                logger.warning(f"Provider {provider_type.value} failed to retrieve {file_key}: {e}")
        
        # Try local storage as final fallback
        local_provider = self.provider_factory.get_provider(StorageProvider.LOCAL)
        if local_provider:
            try:
                start_time = time.time()
                result = await local_provider.download_file(file_key)
                
                if result.success:
                    duration_ms = int((time.time() - start_time) * 1000)
                    result.operation_duration_ms = duration_ms
                    result.provider = StorageProvider.LOCAL.value
                    
                    await self.logging_service.log_operation(
                        operation_type="download",
                        file_key=file_key,
                        provider=StorageProvider.LOCAL.value,
                        success=True,
                        file_size=result.file_size,
                        duration_ms=duration_ms,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        additional_metadata={'local_fallback': True}
                    )
                    
                    logger.info(f"Retrieved file {file_key} from local storage")
                    return result
                    
            except Exception as e:
                logger.error(f"Local storage failed to retrieve {file_key}: {e}")
        
        # File not found in any provider
        error_message = f"File not found: {file_key}"
        await self.logging_service.log_operation(
            operation_type="download",
            file_key=file_key,
            provider="none",
            success=False,
            tenant_id=tenant_id,
            user_id=user_id,
            error_message=error_message
        )
        
        return StorageResult(
            success=False,
            error_message=error_message
        )
    
    async def delete_file(
        self,
        file_key: str,
        tenant_id: str,
        user_id: int,
        files_providers: Optional[List[StorageProvider]] = None
    ) -> bool:
        """
        Delete file from all storage providers.
        
        Args:
            file_key: Unique file key
            tenant_id: Tenant identifier for logging
            user_id: User performing the operation
            files_providers: Optional list of providers to delete from (default: all)
            
        Returns:
            True if file was deleted from at least one provider
        """
        logger.info(f"Deleting file {file_key} for tenant {tenant_id}")
        
        deletion_success = False
        
        # Determine target providers
        target_providers = files_providers if files_providers else list(StorageProvider)

        # Try to delete from target providers
        for provider_type in target_providers:
            provider = self.provider_factory.get_provider(provider_type)
            if not provider:
                continue
            
            try:
                start_time = time.time()
                
                # Get circuit breaker for this provider
                circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider_type.value)
                
                success = await circuit_breaker.call_with_fallback_detection(
                    provider.delete_file,
                    "delete",
                    file_key
                )
                duration_ms = int((time.time() - start_time) * 1000)
                
                if success:
                    deletion_success = True
                    logger.info(f"Deleted file {file_key} from {provider_type.value}")
                
                await self.logging_service.log_operation(
                    operation_type="delete",
                    file_key=file_key,
                    provider=provider_type.value,
                    success=success,
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                
            except CircuitBreakerOpenException as e:
                logger.warning(f"Circuit breaker open for provider {provider_type.value}: {e}")
                
                await self.logging_service.log_operation(
                    operation_type="delete",
                    file_key=file_key,
                    provider=provider_type.value,
                    success=False,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error_message=f"Circuit breaker open: {str(e)}"
                )
                
            except Exception as e:
                logger.warning(f"Failed to delete {file_key} from {provider_type.value}: {e}")
                
                await self.logging_service.log_operation(
                    operation_type="delete",
                    file_key=file_key,
                    provider=provider_type.value,
                    success=False,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error_message=str(e)
                )
        
        return deletion_success
    
    async def delete_folder(
        self,
        folder_prefix: str,
        tenant_id: str,
        bucket_name: str = None,
        aws_credentials: dict = None
    ) -> bool:
        """
        Delete all files in a folder (prefix) from all cloud storage providers.
        
        Args:
            folder_prefix: Folder prefix (e.g., "exported/job-id/")
            tenant_id: Tenant identifier for logging
            bucket_name: Optional bucket/container name (uses env var if not provided)
            aws_credentials: Optional dict with access_key, secret_key, region (AWS only)
            
        Returns:
            True if folder was deleted successfully from at least one provider
        """
        logger.info(f"Deleting folder {folder_prefix} for tenant {tenant_id}")
        
        deletion_success = False
        
        # Try to delete from all cloud providers (excluding local storage)
        cloud_providers = [StorageProvider.AWS_S3, StorageProvider.AZURE_BLOB, StorageProvider.GCP_STORAGE]
        
        for provider_type in cloud_providers:
            try:
                provider = self.provider_factory.get_provider(provider_type)
                if not provider:
                    continue
                
                # Check if provider has delete_folder method
                if hasattr(provider, 'delete_folder'):
                    # Use provider's delete_folder method
                    success = await provider.delete_folder(folder_prefix)
                    if success:
                        deletion_success = True
                        logger.info(f"Successfully deleted folder {folder_prefix} from {provider_type.value}")
                    else:
                        logger.warning(f"Failed to delete folder {folder_prefix} from {provider_type.value}")
                
                elif provider_type == StorageProvider.AWS_S3 and hasattr(provider, 's3_client'):
                    # Fallback for AWS S3 using direct S3 client access
                    s3_client = provider.s3_client
                    target_bucket = bucket_name or provider.bucket_name
                    
                    logger.info(f"Using S3 client for folder deletion, bucket: {target_bucket}")
                    
                    # List all objects with the prefix
                    paginator = s3_client.get_paginator('list_objects_v2')
                    pages = paginator.paginate(Bucket=target_bucket, Prefix=folder_prefix)
                    
                    deleted_count = 0
                    for page in pages:
                        if 'Contents' not in page:
                            continue
                        
                        # Delete objects in batches
                        objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                        if objects_to_delete:
                            s3_client.delete_objects(
                                Bucket=target_bucket,
                                Delete={'Objects': objects_to_delete}
                            )
                            deleted_count += len(objects_to_delete)
                            logger.info(f"Deleted batch of {len(objects_to_delete)} files from {folder_prefix}")
                    
                    if deleted_count > 0:
                        deletion_success = True
                        logger.info(f"Successfully deleted {deleted_count} total files from folder {folder_prefix} in S3")
                
            except Exception as e:
                logger.error(f"Failed to delete folder {folder_prefix} from {provider_type.value}: {e}", exc_info=True)
        
        if not deletion_success:
            logger.warning(f"No cloud provider successfully deleted folder {folder_prefix}")
        
        return deletion_success
    
    async def file_exists(
        self,
        file_key: str,
        tenant_id: str,
        user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if file exists in any storage provider.
        
        Args:
            file_key: Unique file key
            tenant_id: Tenant identifier for logging
            user_id: User performing the operation
            
        Returns:
            Tuple of (exists, provider_name)
        """
        # Check cloud providers first
        cloud_providers = [StorageProvider.AWS_S3, StorageProvider.AZURE_BLOB, StorageProvider.GCP_STORAGE]
        
        for provider_type in cloud_providers:
            provider = self.provider_factory.get_provider(provider_type)
            if not provider or not self._is_provider_healthy(provider_type):
                continue
            
            try:
                exists = await provider.file_exists(file_key)
                if exists:
                    return True, provider_type.value
            except Exception as e:
                logger.warning(f"Error checking file existence in {provider_type.value}: {e}")
        
        # Check local storage
        local_provider = self.provider_factory.get_provider(StorageProvider.LOCAL)
        if local_provider:
            try:
                exists = await local_provider.file_exists(file_key)
                if exists:
                    return True, StorageProvider.LOCAL.value
            except Exception as e:
                logger.warning(f"Error checking file existence in local storage: {e}")
        
        return False, None
    
    async def get_provider_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all storage providers.
        
        Returns:
            Dictionary with provider status information
        """
        return self.provider_factory.get_provider_status()
    
    async def health_check_all_providers(self, force_check: bool = False) -> Dict[StorageProvider, Any]:
        """
        Perform health check on all configured providers.
        
        Args:
            force_check: Force check even if recently checked
            
        Returns:
            Dictionary mapping provider types to health results
        """
        return await self.provider_factory.health_check_all_providers(force_check)
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """
        Get comprehensive circuit breaker status for all providers.
        
        Returns:
            Dictionary with circuit breaker status and metrics
        """
        return self.circuit_breaker_manager.get_all_status()
    
    def reset_circuit_breaker(self, provider_name: str) -> bool:
        """
        Reset circuit breaker for a specific provider.
        
        Args:
            provider_name: Name of the provider to reset
            
        Returns:
            True if circuit breaker was found and reset
        """
        return self.circuit_breaker_manager.reset_provider_circuit_breaker(provider_name)
    
    def reset_all_circuit_breakers(self) -> None:
        """Reset all circuit breakers."""
        self.circuit_breaker_manager.reset_all_circuit_breakers()
    
    def get_healthy_providers(self) -> List[str]:
        """
        Get list of healthy provider names.
        
        Returns:
            List of provider names that are currently healthy
        """
        return self.circuit_breaker_manager.get_healthy_providers()
    
    def get_degraded_providers(self) -> List[str]:
        """
        Get list of degraded provider names.
        
        Returns:
            List of provider names that are degraded but not completely failed
        """
        return self.circuit_breaker_manager.get_degraded_providers()
    
    def should_prefer_fallback(self, provider_type: StorageProvider) -> bool:
        """
        Determine if fallback providers should be preferred over the given provider.
        
        Args:
            provider_type: The provider type to check
            
        Returns:
            True if fallback should be preferred
        """
        circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(provider_type.value)
        return circuit_breaker.should_prefer_fallback()
    
    def get_operation_metrics(
        self,
        tenant_id: Optional[str] = None,
        provider: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Get comprehensive operation metrics.
        
        Args:
            tenant_id: Filter by tenant ID
            provider: Filter by provider
            operation_type: Filter by operation type
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records to analyze
            
        Returns:
            Dictionary with operation metrics and statistics
        """
        return self.logging_service.get_operation_metrics(
            tenant_id=tenant_id,
            provider=provider,
            operation_type=operation_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def get_provider_performance_comparison(
        self,
        tenant_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Compare performance across different storage providers.
        
        Args:
            tenant_id: Filter by tenant ID
            days: Number of days to analyze
            
        Returns:
            Dictionary with provider performance comparison
        """
        return self.logging_service.get_provider_performance_comparison(
            tenant_id=tenant_id,
            days=days
        )
    
    def get_audit_trail(
        self,
        tenant_id: str,
        file_key: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for storage operations.
        
        Args:
            tenant_id: Tenant identifier
            file_key: Filter by specific file key
            user_id: Filter by user ID
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records to return
            
        Returns:
            List of audit trail entries
        """
        return self.logging_service.get_audit_trail(
            tenant_id=tenant_id,
            file_key=file_key,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        Clean up old log entries to manage database size.
        
        Args:
            days_to_keep: Number of days of logs to retain
            
        Returns:
            Number of log entries deleted
        """
        return self.logging_service.cleanup_old_logs(days_to_keep)
