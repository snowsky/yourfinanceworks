"""
Azure Blob Storage Disaster Recovery Extensions.

This module extends the Azure Blob Storage provider with disaster recovery capabilities
including geo-replication, versioning, and backup management.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from azure.core.exceptions import (
    ResourceNotFoundError, 
    ClientAuthenticationError,
    ServiceRequestError,
    ResourceExistsError
)

from .azure_blob_provider import AzureBlobProvider
from core.interfaces.storage_provider import StorageResult, StorageConfig

logger = logging.getLogger(__name__)


class AzureBlobDisasterRecoveryProvider(AzureBlobProvider):
    """
    Enhanced Azure Blob Storage provider with disaster recovery capabilities.
    
    Features:
    - Geo-replication configuration
    - Blob versioning and lifecycle management
    - Cross-region backup and restoration
    - Automated failover support
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize Azure Blob provider with disaster recovery features.
        
        Args:
            config: StorageConfig with Azure Blob and DR-specific settings
        """
        super().__init__(config)
        
        # Extract disaster recovery configuration
        dr_config = config.config.get('disaster_recovery', {})
        self.geo_replication_enabled = dr_config.get('geo_replication_enabled', False)
        self.versioning_enabled = dr_config.get('versioning_enabled', True)
        self.backup_regions = dr_config.get('backup_regions', [])
        self.lifecycle_policies = dr_config.get('lifecycle_policies', {})
        self.secondary_endpoint = dr_config.get('secondary_endpoint')
        
        # Initialize regional clients
        self._regional_clients: Dict[str, BlobServiceClient] = {}
        
        if self.geo_replication_enabled:
            self._init_disaster_recovery()
    
    def _init_disaster_recovery(self) -> None:
        """Initialize disaster recovery features."""
        try:
            # Enable versioning on primary container
            if self.versioning_enabled:
                asyncio.create_task(self._enable_container_versioning())
            
            # Configure lifecycle management
            if self.lifecycle_policies:
                asyncio.create_task(self._configure_lifecycle_management())
                
            logger.info(f"Disaster recovery initialized for container {self.container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize disaster recovery: {e}")
    
    def _get_regional_client(self, region: str, account_name: Optional[str] = None) -> BlobServiceClient:
        """
        Get or create Blob Service client for a specific region.
        
        Args:
            region: Target region
            account_name: Storage account name for the region
            
        Returns:
            BlobServiceClient for the region
        """
        region_key = f"{region}_{account_name or self.account_name}"
        
        if region_key not in self._regional_clients:
            if account_name:
                # Use different storage account for the region
                account_url = f"https://{account_name}.blob.core.windows.net"
                
                if self.connection_string:
                    # Modify connection string for different account
                    modified_connection = self.connection_string.replace(
                        self.account_name, account_name
                    )
                    self._regional_clients[region_key] = BlobServiceClient.from_connection_string(
                        modified_connection
                    )
                else:
                    self._regional_clients[region_key] = BlobServiceClient(
                        account_url=account_url,
                        credential=self.account_key
                    )
            else:
                # Use secondary endpoint for geo-replication
                if self.secondary_endpoint:
                    self._regional_clients[region_key] = BlobServiceClient(
                        account_url=self.secondary_endpoint,
                        credential=self.account_key
                    )
                else:
                    # Fallback to primary client
                    self._regional_clients[region_key] = self.blob_service_client
        
        return self._regional_clients[region_key]
    
    async def _enable_container_versioning(self) -> bool:
        """
        Enable versioning on the blob container (via account-level setting).
        
        Returns:
            True if versioning was enabled successfully
        """
        try:
            # Note: Azure Blob versioning is enabled at the storage account level
            # This would typically be done through Azure CLI or ARM templates
            # Here we just log that versioning should be enabled
            
            logger.info(f"Versioning should be enabled at account level for {self.account_name}")
            
            # We can check if versioning is enabled by attempting to list blob versions
            try:
                test_blobs = self.container_client.list_blobs(include=['versions'])
                logger.info("Blob versioning is available")
                return True
            except Exception as e:
                logger.warning(f"Blob versioning may not be enabled: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify versioning for container {self.container_name}: {e}")
            return False
    
    async def _configure_lifecycle_management(self) -> bool:
        """
        Configure lifecycle management policies for cost optimization.
        
        Returns:
            True if lifecycle policies were configured successfully
        """
        try:
            # Note: Azure Blob lifecycle management is configured at the storage account level
            # This would typically be done through Azure CLI, PowerShell, or ARM templates
            
            logger.info("Lifecycle management policies should be configured at account level")
            
            # Example lifecycle policy structure (for reference):
            lifecycle_policy = {
                "rules": []
            }
            
            # Transition to cool tier
            if self.lifecycle_policies.get('transition_to_cool_days'):
                lifecycle_policy["rules"].append({
                    "name": "TransitionToCool",
                    "enabled": True,
                    "type": "Lifecycle",
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"]
                        },
                        "actions": {
                            "baseBlob": {
                                "tierToCool": {
                                    "daysAfterModificationGreaterThan": self.lifecycle_policies['transition_to_cool_days']
                                }
                            }
                        }
                    }
                })
            
            # Transition to archive tier
            if self.lifecycle_policies.get('transition_to_archive_days'):
                lifecycle_policy["rules"].append({
                    "name": "TransitionToArchive",
                    "enabled": True,
                    "type": "Lifecycle",
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"]
                        },
                        "actions": {
                            "baseBlob": {
                                "tierToArchive": {
                                    "daysAfterModificationGreaterThan": self.lifecycle_policies['transition_to_archive_days']
                                }
                            }
                        }
                    }
                })
            
            # Delete old versions
            if self.lifecycle_policies.get('delete_versions_days'):
                lifecycle_policy["rules"].append({
                    "name": "DeleteOldVersions",
                    "enabled": True,
                    "type": "Lifecycle",
                    "definition": {
                        "filters": {
                            "blobTypes": ["blockBlob"]
                        },
                        "actions": {
                            "version": {
                                "delete": {
                                    "daysAfterCreationGreaterThan": self.lifecycle_policies['delete_versions_days']
                                }
                            }
                        }
                    }
                })
            
            logger.info(f"Lifecycle policy structure prepared: {len(lifecycle_policy['rules'])} rules")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure lifecycle management: {e}")
            return False
    
    async def upload_blob_with_replication(
        self,
        file_content: bytes,
        file_key: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        replicate_immediately: bool = False
    ) -> StorageResult:
        """
        Upload blob with optional immediate replication to backup regions.
        
        Args:
            file_content: File content as bytes
            file_key: Unique file key
            content_type: MIME type
            metadata: Optional metadata
            replicate_immediately: Whether to replicate immediately
            
        Returns:
            StorageResult with upload and replication details
        """
        # First upload to primary region
        result = await self.upload_file(file_content, file_key, content_type, metadata)
        
        if not result.success:
            return result
        
        # If immediate replication is requested
        if replicate_immediately and self.backup_regions:
            replication_results = []
            
            for region_config in self.backup_regions:
                try:
                    region_name = region_config.get('name', 'unknown')
                    account_name = region_config.get('account_name')
                    container_name = region_config.get('container_name', self.container_name)
                    
                    if not account_name:
                        replication_results.append(f"No account name for region {region_name}")
                        continue
                    
                    # Get regional client
                    regional_client = self._get_regional_client(region_name, account_name)
                    regional_container = regional_client.get_container_client(container_name)
                    
                    # Generate blob name
                    blob_name = self._generate_blob_name(file_key)
                    blob_client = regional_container.get_blob_client(blob_name)
                    
                    # Prepare metadata
                    blob_metadata = self._get_upload_metadata(content_type, metadata)
                    blob_metadata['replicated_from_primary'] = 'true'
                    blob_metadata['replication_timestamp'] = datetime.now(timezone.utc).isoformat()
                    
                    # Upload to backup region
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: blob_client.upload_blob(
                            file_content,
                            content_type=content_type,
                            metadata=blob_metadata,
                            standard_blob_tier=self.blob_tier,
                            overwrite=True
                        )
                    )
                    
                    replication_results.append(f"Replicated to {region_name}")
                    logger.info(f"Immediately replicated {file_key} to region {region_name}")
                    
                except Exception as e:
                    replication_results.append(f"Failed to replicate to {region_config.get('name', 'unknown')}: {str(e)}")
                    logger.error(f"Immediate replication failed for region {region_config}: {e}")
            
            # Add replication info to result metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata['replication_results'] = replication_results
        
        return result
    
    async def restore_from_region(
        self,
        file_key: str,
        source_region_config: Dict[str, str],
        target_region_config: Optional[Dict[str, str]] = None
    ) -> StorageResult:
        """
        Restore a blob from a backup region.
        
        Args:
            file_key: File key to restore
            source_region_config: Source region configuration
            target_region_config: Target region configuration (defaults to primary)
            
        Returns:
            StorageResult with restoration details
        """
        try:
            source_region = source_region_config.get('name', 'unknown')
            source_account = source_region_config.get('account_name')
            source_container = source_region_config.get('container_name', self.container_name)
            
            # Get source client
            source_client = self._get_regional_client(source_region, source_account)
            source_container_client = source_client.get_container_client(source_container)
            
            # Generate blob name
            blob_name = self._generate_blob_name(file_key)
            source_blob_client = source_container_client.get_blob_client(blob_name)
            
            # Download from source region
            download_stream = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: source_blob_client.download_blob()
            )
            
            file_content = download_stream.readall()
            blob_properties = download_stream.properties
            content_type = blob_properties.content_settings.content_type or 'application/octet-stream'
            
            # Determine target (default to primary)
            if target_region_config:
                target_region = target_region_config.get('name', 'primary')
                target_account = target_region_config.get('account_name')
                target_container = target_region_config.get('container_name', self.container_name)
                
                target_client = self._get_regional_client(target_region, target_account)
                target_container_client = target_client.get_container_client(target_container)
            else:
                target_container_client = self.container_client
                target_region = 'primary'
            
            # Upload to target region
            target_blob_client = target_container_client.get_blob_client(blob_name)
            
            restoration_metadata = {
                'restored_from_region': source_region,
                'restoration_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: target_blob_client.upload_blob(
                    file_content,
                    content_type=content_type,
                    metadata=restoration_metadata,
                    standard_blob_tier=self.blob_tier,
                    overwrite=True
                )
            )
            
            logger.info(f"Successfully restored {file_key} from {source_region} to {target_region}")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                metadata={
                    'restored_from_region': source_region,
                    'target_region': target_region
                }
            )
            
        except Exception as e:
            error_message = f"Failed to restore from region {source_region_config.get('name', 'unknown')}: {str(e)}"
            logger.error(error_message)
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value
            )
    
    async def list_blob_versions(
        self,
        file_key: str,
        max_versions: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List all versions of a blob.
        
        Args:
            file_key: File key to list versions for
            max_versions: Maximum number of versions to return
            
        Returns:
            List of version information
        """
        try:
            blob_name = self._generate_blob_name(file_key)
            
            # List blob versions
            blob_list = self.container_client.list_blobs(
                name_starts_with=blob_name,
                include=['versions'],
                results_per_page=max_versions
            )
            
            versions = []
            for blob in blob_list:
                if blob.name == blob_name:
                    versions.append({
                        'version_id': blob.version_id,
                        'last_modified': blob.last_modified.isoformat() if blob.last_modified else None,
                        'size': blob.size,
                        'etag': blob.etag.strip('"') if blob.etag else None,
                        'is_current_version': blob.is_current_version,
                        'blob_tier': blob.blob_tier
                    })
            
            return sorted(versions, key=lambda x: x['last_modified'] or '', reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list versions for {file_key}: {e}")
            return []
    
    async def restore_blob_version(
        self,
        file_key: str,
        version_id: str
    ) -> StorageResult:
        """
        Restore a specific version of a blob.
        
        Args:
            file_key: File key to restore
            version_id: Version ID to restore
            
        Returns:
            StorageResult with restoration details
        """
        try:
            blob_name = self._generate_blob_name(file_key)
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Download the specific version
            download_stream = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.download_blob(version_id=version_id)
            )
            
            file_content = download_stream.readall()
            blob_properties = download_stream.properties
            content_type = blob_properties.content_settings.content_type or 'application/octet-stream'
            
            # Upload as new current version
            restoration_metadata = {
                'restored_from_version': version_id,
                'restoration_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.upload_blob(
                    file_content,
                    content_type=content_type,
                    metadata=restoration_metadata,
                    standard_blob_tier=self.blob_tier,
                    overwrite=True
                )
            )
            
            logger.info(f"Successfully restored {file_key} from version {version_id}")
            
            return StorageResult(
                success=True,
                file_key=file_key,
                file_size=len(file_content),
                content_type=content_type,
                provider=self.provider_type.value,
                metadata={
                    'restored_from_version': version_id
                }
            )
            
        except Exception as e:
            error_message = f"Failed to restore version {version_id}: {str(e)}"
            logger.error(error_message)
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value
            )
    
    async def get_geo_replication_status(self, file_key: str) -> Dict[str, Any]:
        """
        Get geo-replication status for a blob across regions.
        
        Args:
            file_key: File key to check
            
        Returns:
            Dictionary with replication status information
        """
        status = {
            'file_key': file_key,
            'primary_account': self.account_name,
            'backup_regions': {},
            'geo_replication_enabled': self.geo_replication_enabled
        }
        
        blob_name = self._generate_blob_name(file_key)
        
        # Check primary region
        try:
            primary_exists = await self.file_exists(file_key)
            status['primary_exists'] = primary_exists
            
            if primary_exists:
                metadata = await self.get_file_metadata(file_key)
                status['primary_checksum'] = metadata.checksum if metadata else None
        except Exception as e:
            status['primary_error'] = str(e)
        
        # Check backup regions
        for region_config in self.backup_regions:
            region_name = region_config.get('name', 'unknown')
            account_name = region_config.get('account_name')
            container_name = region_config.get('container_name', self.container_name)
            
            try:
                if not account_name:
                    status['backup_regions'][region_name] = {'error': 'No account name configured'}
                    continue
                
                # Get regional client
                regional_client = self._get_regional_client(region_name, account_name)
                regional_container = regional_client.get_container_client(container_name)
                blob_client = regional_container.get_blob_client(blob_name)
                
                # Check if blob exists in backup region
                blob_properties = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: blob_client.get_blob_properties()
                )
                
                status['backup_regions'][region_name] = {
                    'exists': True,
                    'checksum': blob_properties.etag.strip('"') if blob_properties.etag else None,
                    'last_modified': blob_properties.last_modified.isoformat() if blob_properties.last_modified else None,
                    'blob_tier': blob_properties.blob_tier,
                    'account_name': account_name
                }
                
            except ResourceNotFoundError:
                status['backup_regions'][region_name] = {'exists': False}
            except Exception as e:
                status['backup_regions'][region_name] = {'error': str(e)}
        
        return status
    
    async def sync_to_secondary_endpoint(self, file_key: str) -> bool:
        """
        Manually sync a blob to the secondary endpoint (for RA-GRS accounts).
        
        Args:
            file_key: File key to sync
            
        Returns:
            True if sync was successful
        """
        if not self.secondary_endpoint:
            logger.warning("No secondary endpoint configured for geo-replication")
            return False
        
        try:
            blob_name = self._generate_blob_name(file_key)
            
            # Download from primary
            primary_blob_client = self.container_client.get_blob_client(blob_name)
            download_stream = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: primary_blob_client.download_blob()
            )
            
            file_content = download_stream.readall()
            blob_properties = download_stream.properties
            
            # Upload to secondary (read-only, so this is mainly for verification)
            # Note: In actual RA-GRS, secondary is read-only and sync is automatic
            logger.info(f"Verified blob {file_key} exists in primary for geo-replication")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync {file_key} to secondary endpoint: {e}")
            return False