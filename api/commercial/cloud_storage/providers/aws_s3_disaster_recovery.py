"""
AWS S3 Disaster Recovery Extensions.

This module extends the AWS S3 provider with disaster recovery capabilities
including cross-region replication, versioning, and backup management.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .aws_s3_provider import AWSS3Provider
from core.interfaces.storage_provider import StorageResult, StorageConfig

logger = logging.getLogger(__name__)


class AWSS3DisasterRecoveryProvider(AWSS3Provider):
    """
    Enhanced AWS S3 provider with disaster recovery capabilities.
    
    Features:
    - Cross-region replication configuration
    - S3 versioning and lifecycle policies
    - Cross-region backup and restoration
    - Automated failover support
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize AWS S3 provider with disaster recovery features.
        
        Args:
            config: StorageConfig with S3 and DR-specific settings
        """
        super().__init__(config)
        
        # Extract disaster recovery configuration
        dr_config = config.config.get('disaster_recovery', {})
        self.replication_enabled = dr_config.get('replication_enabled', False)
        self.versioning_enabled = dr_config.get('versioning_enabled', True)
        self.backup_regions = dr_config.get('backup_regions', [])
        self.replication_role_arn = dr_config.get('replication_role_arn')
        self.lifecycle_policies = dr_config.get('lifecycle_policies', {})
        
        # Initialize regional clients
        self._regional_clients: Dict[str, Any] = {}
        
        if self.replication_enabled:
            self._init_disaster_recovery()
    
    def _init_disaster_recovery(self) -> None:
        """Initialize disaster recovery features."""
        try:
            # Enable versioning on primary bucket
            if self.versioning_enabled:
                asyncio.create_task(self._enable_bucket_versioning())
            
            # Configure cross-region replication
            if self.backup_regions and self.replication_role_arn:
                asyncio.create_task(self._configure_cross_region_replication())
            
            # Set up lifecycle policies
            if self.lifecycle_policies:
                asyncio.create_task(self._configure_lifecycle_policies())
                
            logger.info(f"Disaster recovery initialized for bucket {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize disaster recovery: {e}")
    
    def _get_regional_client(self, region: str) -> Any:
        """
        Get or create S3 client for a specific region.
        
        Args:
            region: Target region
            
        Returns:
            S3 client for the region
        """
        if region not in self._regional_clients:
            boto_config = Config(
                region_name=region,
                max_pool_connections=20,
                retries={
                    'max_attempts': self.config.max_retry_attempts,
                    'mode': 'adaptive'
                }
            )
            
            if self.access_key_id and self.secret_access_key:
                session = boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=region
                )
                self._regional_clients[region] = session.client('s3', config=boto_config)
            else:
                self._regional_clients[region] = boto3.client('s3', config=boto_config)
        
        return self._regional_clients[region]
    
    async def _enable_bucket_versioning(self) -> bool:
        """
        Enable versioning on the S3 bucket.
        
        Returns:
            True if versioning was enabled successfully
        """
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_bucket_versioning(
                    Bucket=self.bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
            )
            
            logger.info(f"Enabled versioning for bucket {self.bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to enable versioning for bucket {self.bucket_name}: {e}")
            return False
    
    async def _configure_cross_region_replication(self) -> bool:
        """
        Configure cross-region replication for the S3 bucket.
        
        Returns:
            True if replication was configured successfully
        """
        try:
            # Create replication configuration
            replication_config = {
                'Role': self.replication_role_arn,
                'Rules': []
            }
            
            for i, region in enumerate(self.backup_regions):
                # Create destination bucket name
                dest_bucket = f"{self.bucket_name}-{region}"
                
                # Ensure destination bucket exists
                await self._ensure_destination_bucket(region, dest_bucket)
                
                # Add replication rule
                rule = {
                    'ID': f'ReplicateToRegion{i+1}',
                    'Status': 'Enabled',
                    'Priority': i + 1,
                    'Filter': {'Prefix': ''},
                    'Destination': {
                        'Bucket': f'arn:aws:s3:::{dest_bucket}',
                        'StorageClass': 'STANDARD_IA'  # Use cheaper storage class for backups
                    },
                    'DeleteMarkerReplication': {'Status': 'Enabled'}
                }
                
                replication_config['Rules'].append(rule)
            
            # Apply replication configuration
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_bucket_replication(
                    Bucket=self.bucket_name,
                    ReplicationConfiguration=replication_config
                )
            )
            
            logger.info(f"Configured cross-region replication for bucket {self.bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to configure cross-region replication: {e}")
            return False
    
    async def _ensure_destination_bucket(self, region: str, bucket_name: str) -> bool:
        """
        Ensure destination bucket exists in the target region.
        
        Args:
            region: Target region
            bucket_name: Destination bucket name
            
        Returns:
            True if bucket exists or was created
        """
        try:
            regional_client = self._get_regional_client(region)
            
            # Check if bucket exists
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: regional_client.head_bucket(Bucket=bucket_name)
                )
                logger.debug(f"Destination bucket {bucket_name} already exists in {region}")
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Bucket doesn't exist, create it
                    create_config = {}
                    if region != 'us-east-1':  # us-east-1 doesn't need LocationConstraint
                        create_config['CreateBucketConfiguration'] = {'LocationConstraint': region}
                    
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: regional_client.create_bucket(
                            Bucket=bucket_name,
                            **create_config
                        )
                    )
                    
                    # Enable versioning on destination bucket
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: regional_client.put_bucket_versioning(
                            Bucket=bucket_name,
                            VersioningConfiguration={'Status': 'Enabled'}
                        )
                    )
                    
                    logger.info(f"Created destination bucket {bucket_name} in {region}")
                    return True
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Failed to ensure destination bucket {bucket_name} in {region}: {e}")
            return False
    
    async def _configure_lifecycle_policies(self) -> bool:
        """
        Configure lifecycle policies for cost optimization and data management.
        
        Returns:
            True if lifecycle policies were configured successfully
        """
        try:
            lifecycle_rules = []
            
            # Standard lifecycle transitions
            if self.lifecycle_policies.get('transition_to_ia_days'):
                lifecycle_rules.append({
                    'ID': 'TransitionToIA',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': ''},
                    'Transitions': [{
                        'Days': self.lifecycle_policies['transition_to_ia_days'],
                        'StorageClass': 'STANDARD_IA'
                    }]
                })
            
            if self.lifecycle_policies.get('transition_to_glacier_days'):
                lifecycle_rules.append({
                    'ID': 'TransitionToGlacier',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': ''},
                    'Transitions': [{
                        'Days': self.lifecycle_policies['transition_to_glacier_days'],
                        'StorageClass': 'GLACIER'
                    }]
                })
            
            if self.lifecycle_policies.get('transition_to_deep_archive_days'):
                lifecycle_rules.append({
                    'ID': 'TransitionToDeepArchive',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': ''},
                    'Transitions': [{
                        'Days': self.lifecycle_policies['transition_to_deep_archive_days'],
                        'StorageClass': 'DEEP_ARCHIVE'
                    }]
                })
            
            # Backup-specific lifecycle rules
            if self.lifecycle_policies.get('backup_retention_days'):
                lifecycle_rules.append({
                    'ID': 'BackupRetention',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'backups/'},
                    'Expiration': {
                        'Days': self.lifecycle_policies['backup_retention_days']
                    }
                })
            
            # Version management
            if self.lifecycle_policies.get('noncurrent_version_expiration_days'):
                lifecycle_rules.append({
                    'ID': 'VersionManagement',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': ''},
                    'NoncurrentVersionExpiration': {
                        'NoncurrentDays': self.lifecycle_policies['noncurrent_version_expiration_days']
                    }
                })
            
            if lifecycle_rules:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.put_bucket_lifecycle_configuration(
                        Bucket=self.bucket_name,
                        LifecycleConfiguration={'Rules': lifecycle_rules}
                    )
                )
                
                logger.info(f"Configured lifecycle policies for bucket {self.bucket_name}")
            
            return True
            
        except ClientError as e:
            logger.error(f"Failed to configure lifecycle policies: {e}")
            return False
    
    async def upload_file_with_replication(
        self,
        file_content: bytes,
        file_key: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        replicate_immediately: bool = False
    ) -> StorageResult:
        """
        Upload file with optional immediate replication to backup regions.
        
        Args:
            file_content: File content as bytes
            file_key: Unique file key
            content_type: MIME type
            metadata: Optional metadata
            replicate_immediately: Whether to replicate immediately (bypassing S3 replication)
            
        Returns:
            StorageResult with upload and replication details
        """
        # First upload to primary region
        result = await self.upload_file(file_content, file_key, content_type, metadata)
        
        if not result.success:
            return result
        
        # If immediate replication is requested and S3 replication is not configured
        if replicate_immediately and (not self.replication_enabled or not self.backup_regions):
            replication_results = []
            
            for region in self.backup_regions:
                try:
                    regional_client = self._get_regional_client(region)
                    dest_bucket = f"{self.bucket_name}-{region}"
                    
                    # Upload to backup region
                    extra_args = self._get_upload_args(content_type, metadata)
                    
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: regional_client.put_object(
                            Bucket=dest_bucket,
                            Key=file_key,
                            Body=file_content,
                            **extra_args
                        )
                    )
                    
                    replication_results.append(f"Replicated to {region}")
                    logger.info(f"Immediately replicated {file_key} to region {region}")
                    
                except Exception as e:
                    replication_results.append(f"Failed to replicate to {region}: {str(e)}")
                    logger.error(f"Immediate replication failed for region {region}: {e}")
            
            # Add replication info to result metadata
            if result.metadata is None:
                result.metadata = {}
            result.metadata['replication_results'] = replication_results
        
        return result
    
    async def restore_from_region(
        self,
        file_key: str,
        source_region: str,
        target_region: Optional[str] = None
    ) -> StorageResult:
        """
        Restore a file from a backup region.
        
        Args:
            file_key: File key to restore
            source_region: Region to restore from
            target_region: Target region (defaults to primary)
            
        Returns:
            StorageResult with restoration details
        """
        try:
            target_region = target_region or self.region
            
            # Get clients for source and target regions
            source_client = self._get_regional_client(source_region)
            target_client = self._get_regional_client(target_region)
            
            source_bucket = f"{self.bucket_name}-{source_region}" if source_region != self.region else self.bucket_name
            target_bucket = f"{self.bucket_name}-{target_region}" if target_region != self.region else self.bucket_name
            
            # Download from source region
            source_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: source_client.get_object(Bucket=source_bucket, Key=file_key)
            )
            
            file_content = source_response['Body'].read()
            content_type = source_response.get('ContentType', 'application/octet-stream')
            
            # Upload to target region
            extra_args = {
                'ContentType': content_type,
                'ServerSideEncryption': self.server_side_encryption,
                'Metadata': {
                    'restored_from_region': source_region,
                    'restoration_timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: target_client.put_object(
                    Bucket=target_bucket,
                    Key=file_key,
                    Body=file_content,
                    **extra_args
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
            
        except ClientError as e:
            error_message = f"Failed to restore from region {source_region}: {str(e)}"
            logger.error(error_message)
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value
            )
    
    async def list_object_versions(
        self,
        file_key: str,
        max_versions: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List all versions of an object.
        
        Args:
            file_key: File key to list versions for
            max_versions: Maximum number of versions to return
            
        Returns:
            List of version information
        """
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.list_object_versions(
                    Bucket=self.bucket_name,
                    Prefix=file_key,
                    MaxKeys=max_versions
                )
            )
            
            versions = []
            for version in response.get('Versions', []):
                if version['Key'] == file_key:
                    versions.append({
                        'version_id': version['VersionId'],
                        'last_modified': version['LastModified'].isoformat(),
                        'size': version['Size'],
                        'etag': version['ETag'].strip('"'),
                        'is_latest': version.get('IsLatest', False)
                    })
            
            return sorted(versions, key=lambda x: x['last_modified'], reverse=True)
            
        except ClientError as e:
            logger.error(f"Failed to list versions for {file_key}: {e}")
            return []
    
    async def restore_object_version(
        self,
        file_key: str,
        version_id: str
    ) -> StorageResult:
        """
        Restore a specific version of an object.
        
        Args:
            file_key: File key to restore
            version_id: Version ID to restore
            
        Returns:
            StorageResult with restoration details
        """
        try:
            # Download the specific version
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    VersionId=version_id
                )
            )
            
            file_content = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')
            
            # Upload as new current version
            extra_args = {
                'ContentType': content_type,
                'ServerSideEncryption': self.server_side_encryption,
                'Metadata': {
                    'restored_from_version': version_id,
                    'restoration_timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    Body=file_content,
                    **extra_args
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
            
        except ClientError as e:
            error_message = f"Failed to restore version {version_id}: {str(e)}"
            logger.error(error_message)
            
            return StorageResult(
                success=False,
                error_message=error_message,
                provider=self.provider_type.value
            )
    
    async def get_replication_status(self, file_key: str) -> Dict[str, Any]:
        """
        Get replication status for a file across regions.
        
        Args:
            file_key: File key to check
            
        Returns:
            Dictionary with replication status information
        """
        status = {
            'file_key': file_key,
            'primary_region': self.region,
            'backup_regions': {},
            'replication_enabled': self.replication_enabled
        }
        
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
        for region in self.backup_regions:
            try:
                regional_client = self._get_regional_client(region)
                dest_bucket = f"{self.bucket_name}-{region}"
                
                # Check if file exists in backup region
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: regional_client.head_object(Bucket=dest_bucket, Key=file_key)
                )
                
                # Get object metadata for checksum
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: regional_client.head_object(Bucket=dest_bucket, Key=file_key)
                )
                
                status['backup_regions'][region] = {
                    'exists': True,
                    'checksum': response.get('ETag', '').strip('"'),
                    'last_modified': response.get('LastModified', '').isoformat() if response.get('LastModified') else None
                }
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    status['backup_regions'][region] = {'exists': False}
                else:
                    status['backup_regions'][region] = {'error': str(e)}
            except Exception as e:
                status['backup_regions'][region] = {'error': str(e)}
        
        return status