"""
Export Destination Service for managing cloud storage export configurations.

Handles credential encryption, destination management, and connection testing
for various cloud storage providers (S3, Azure, GCS, Google Drive).
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models_per_tenant import ExportDestinationConfig
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.schemas.export_destination import (
    ExportDestinationCreate,
    ExportDestinationUpdate,
    ExportDestinationResponse,
    ExportDestinationTestResult
)
from core.exceptions.encryption_exceptions import EncryptionError, DecryptionError
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)


class ExportDestinationService:
    """
    Service for managing export destination configurations.
    
    Provides secure credential storage using tenant-specific encryption,
    destination management, and connection testing capabilities.
    """

    def __init__(self, db: Session, tenant_id: int):
        """
        Initialize the export destination service.
        
        Args:
            db: Database session
            tenant_id: Tenant identifier for encryption and data isolation
        """
        self.db = db
        self.tenant_id = tenant_id
        
        # Initialize encryption service
        key_management = KeyManagementService()
        self.encryption_service = EncryptionService(key_management)
        
        logger.info(f"ExportDestinationService initialized for tenant {tenant_id}")

    def create_destination(
        self,
        name: str,
        destination_type: str,
        credentials: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        is_default: bool = False
    ) -> ExportDestinationConfig:
        """
        Create a new export destination with encrypted credentials.
        
        Args:
            name: User-friendly name for the destination
            destination_type: Type of destination (s3, azure, gcs, google_drive)
            credentials: Destination-specific credentials
            config: Additional configuration
            user_id: User creating the destination
            is_default: Whether this should be the default destination
            
        Returns:
            Created ExportDestinationConfig instance
            
        Raises:
            EncryptionError: If credential encryption fails
            ValueError: If validation fails
        """
        try:
            # Validate destination type
            allowed_types = ['s3', 'azure', 'gcs', 'google_drive']
            if destination_type not in allowed_types:
                raise ValueError(f"Invalid destination type. Must be one of: {', '.join(allowed_types)}")
            
            # SECURITY: Encrypt credentials using tenant-specific encryption key
            # Credentials are stored encrypted in the database and only decrypted when needed
            credentials_json = json.dumps(credentials)
            encrypted_credentials = self.encryption_service.encrypt_data(
                credentials_json,
                self.tenant_id
            )
            
            logger.debug(f"Encrypted credentials for destination '{name}' (tenant {self.tenant_id})")
            
            # If setting as default, unset other defaults
            if is_default:
                self.db.query(ExportDestinationConfig).filter(
                    and_(
                        ExportDestinationConfig.tenant_id == self.tenant_id,
                        ExportDestinationConfig.is_default == True
                    )
                ).update({"is_default": False})
            
            # Create destination record
            destination = ExportDestinationConfig(
                tenant_id=self.tenant_id,
                name=name,
                destination_type=destination_type,
                encrypted_credentials=encrypted_credentials,
                config=config or {},
                is_active=True,
                is_default=is_default,
                created_by=user_id
            )
            
            self.db.add(destination)
            self.db.commit()
            self.db.refresh(destination)
            
            logger.info(f"Created export destination '{name}' (type: {destination_type}) for tenant {self.tenant_id}")
            
            # AUDIT: Log destination creation
            try:
                log_audit_event(
                    db=self.db,
                    user_id=user_id or 0,
                    user_email=f"user_{user_id}@tenant_{self.tenant_id}" if user_id else f"system@tenant_{self.tenant_id}",
                    action="CREATE",
                    resource_type="export_destination",
                    resource_id=str(destination.id),
                    resource_name=name,
                    details={
                        "destination_type": destination_type,
                        "is_default": is_default,
                        "has_credentials": bool(credentials)
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log audit event for destination creation: {e}")
            
            return destination
            
        except EncryptionError as e:
            logger.error(f"Failed to encrypt credentials for destination '{name}': {str(e)}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to create export destination '{name}': {str(e)}")
            self.db.rollback()
            raise

    def update_destination(
        self,
        destination_id: int,
        updates: Dict[str, Any]
    ) -> ExportDestinationConfig:
        """
        Update an existing export destination.
        
        Enforces tenant isolation by filtering on tenant_id.
        
        Args:
            destination_id: ID of the destination to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated ExportDestinationConfig instance
            
        Raises:
            ValueError: If destination not found or validation fails
            EncryptionError: If credential encryption fails
        """
        try:
            # Get destination with tenant isolation
            destination = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == destination_id,
                    ExportDestinationConfig.tenant_id == self.tenant_id  # Tenant isolation
                )
            ).first()
            
            if not destination:
                raise ValueError(f"Export destination {destination_id} not found")
            
            # SECURITY: Re-encrypt credentials if updated
            # Credentials are always stored encrypted using tenant-specific encryption key
            if 'credentials' in updates and updates['credentials']:
                credentials_json = json.dumps(updates['credentials'])
                encrypted_credentials = self.encryption_service.encrypt_data(
                    credentials_json,
                    self.tenant_id
                )
                destination.encrypted_credentials = encrypted_credentials
                
                logger.debug(f"Re-encrypted credentials for destination {destination_id} (tenant {self.tenant_id})")
            
            # Update other fields
            if 'name' in updates:
                destination.name = updates['name']
            if 'config' in updates:
                destination.config = updates['config']
            if 'is_active' in updates:
                destination.is_active = updates['is_active']
            if 'is_default' in updates and updates['is_default']:
                # Unset other defaults
                self.db.query(ExportDestinationConfig).filter(
                    and_(
                        ExportDestinationConfig.tenant_id == self.tenant_id,
                        ExportDestinationConfig.id != destination_id,
                        ExportDestinationConfig.is_default == True
                    )
                ).update({"is_default": False})
                destination.is_default = True
            
            destination.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(destination)
            
            logger.info(f"Updated export destination {destination_id} for tenant {self.tenant_id}")
            
            # AUDIT: Log destination update
            try:
                log_audit_event(
                    db=self.db,
                    user_id=0,  # User ID not available in service layer
                    user_email=f"system@tenant_{self.tenant_id}",
                    action="UPDATE",
                    resource_type="export_destination",
                    resource_id=str(destination_id),
                    resource_name=destination.name,
                    details={
                        "updated_fields": list(updates.keys()),
                        "credentials_updated": 'credentials' in updates
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log audit event for destination update: {e}")
            
            return destination
            
        except EncryptionError as e:
            logger.error(f"Failed to encrypt credentials for destination {destination_id}: {str(e)}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to update export destination {destination_id}: {str(e)}")
            self.db.rollback()
            raise

    def get_destination(self, destination_id: int) -> Optional[ExportDestinationConfig]:
        """
        Get a specific export destination.
        
        Enforces tenant isolation by filtering on tenant_id.
        
        Args:
            destination_id: ID of the destination
            
        Returns:
            ExportDestinationConfig instance or None if not found
        """
        return self.db.query(ExportDestinationConfig).filter(
            and_(
                ExportDestinationConfig.id == destination_id,
                ExportDestinationConfig.tenant_id == self.tenant_id  # Tenant isolation
            )
        ).first()

    def list_destinations(
        self,
        active_only: bool = False,
        destination_type: Optional[str] = None
    ) -> List[ExportDestinationConfig]:
        """
        List all export destinations for the tenant.
        
        Enforces tenant isolation by filtering on tenant_id.
        
        Args:
            active_only: If True, only return active destinations
            destination_type: Filter by destination type
            
        Returns:
            List of ExportDestinationConfig instances
        """
        query = self.db.query(ExportDestinationConfig).filter(
            ExportDestinationConfig.tenant_id == self.tenant_id  # Tenant isolation
        )
        
        if active_only:
            query = query.filter(ExportDestinationConfig.is_active == True)
        
        if destination_type:
            query = query.filter(ExportDestinationConfig.destination_type == destination_type)
        
        return query.order_by(ExportDestinationConfig.created_at.desc()).all()

    def delete_destination(self, destination_id: int) -> bool:
        """
        Soft delete an export destination (set is_active=False).
        
        Enforces tenant isolation by filtering on tenant_id.
        
        Args:
            destination_id: ID of the destination to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If destination not found or has active jobs
        """
        try:
            destination = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == destination_id,
                    ExportDestinationConfig.tenant_id == self.tenant_id  # Tenant isolation
                )
            ).first()
            
            if not destination:
                raise ValueError(f"Export destination {destination_id} not found")
            
            # Check for active batch jobs using this destination
            # This will be implemented when BatchProcessingJob is available
            # For now, just soft delete
            
            destination.is_active = False
            destination.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            
            logger.info(f"Deleted export destination {destination_id} for tenant {self.tenant_id}")
            
            # AUDIT: Log destination deletion
            try:
                log_audit_event(
                    db=self.db,
                    user_id=0,  # User ID not available in service layer
                    user_email=f"system@tenant_{self.tenant_id}",
                    action="DELETE",
                    resource_type="export_destination",
                    resource_id=str(destination_id),
                    resource_name=destination.name,
                    details={
                        "destination_type": destination.destination_type,
                        "soft_delete": True
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log audit event for destination deletion: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete export destination {destination_id}: {str(e)}")
            self.db.rollback()
            raise

    def get_decrypted_credentials(self, destination_id: int) -> Dict[str, Any]:
        """
        Retrieve and decrypt destination credentials.
        
        SECURITY: This method decrypts credentials using tenant-specific encryption keys.
        Decrypted credentials should ONLY be used for:
        - Connection testing
        - Export operations
        - Internal service operations
        
        NEVER return decrypted credentials in API responses. Use mask_credentials() instead.
        
        Enforces tenant isolation by filtering on tenant_id.
        
        Args:
            destination_id: ID of the destination
            
        Returns:
            Decrypted credentials dictionary
            
        Raises:
            ValueError: If destination not found
            DecryptionError: If decryption fails
        """
        try:
            destination = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == destination_id,
                    ExportDestinationConfig.tenant_id == self.tenant_id  # Tenant isolation
                )
            ).first()

            if not destination:
                raise ValueError(f"Export destination {destination_id} not found")

            if not destination.encrypted_credentials:
                # Check for environment variable fallback
                return self._get_fallback_credentials(destination.destination_type)

            # Decrypt credentials using tenant-specific encryption key
            decrypted_json = self.encryption_service.decrypt_data(
                destination.encrypted_credentials,
                self.tenant_id
            )

            credentials = json.loads(decrypted_json)

            logger.debug(f"Decrypted credentials for destination {destination_id} (tenant {self.tenant_id})")

            return credentials

        except DecryptionError as e:
            logger.error(f"Failed to decrypt credentials for destination {destination_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get credentials for destination {destination_id}: {str(e)}")
            raise

    def _get_fallback_credentials(self, destination_type: str) -> Dict[str, Any]:
        """
        Get credentials from environment variables as fallback.

        Checks for destination-specific environment variables when credentials
        are not configured in the database. Logs when fallback is used.

        Args:
            destination_type: Type of destination

        Returns:
            Credentials dictionary from environment variables

        Raises:
            ValueError: If required environment variables are not set
        """
        logger.warning(
            f"No credentials configured for {destination_type} destination. "
            f"Attempting to use environment variable fallback for tenant {self.tenant_id}"
        )

        if destination_type == 's3':
            # For S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_S3_BUCKET
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            region = os.getenv('AWS_REGION', 'us-east-1')
            bucket = os.getenv('AWS_S3_BUCKET')

            if not all([access_key, secret_key, bucket]):
                missing = []
                if not access_key:
                    missing.append('AWS_ACCESS_KEY_ID')
                if not secret_key:
                    missing.append('AWS_SECRET_ACCESS_KEY')
                if not bucket:
                    missing.append('AWS_S3_BUCKET')
                raise ValueError(
                    f"Missing required S3 environment variables: {', '.join(missing)}. "
                    "Please configure credentials in the export destination settings."
                )

            logger.info(
                f"Using S3 environment variable fallback: bucket={bucket}, region={region}"
            )

            return {
                'access_key_id': access_key,
                'secret_access_key': secret_key,
                'region': region,
                'bucket_name': bucket,
                'path_prefix': os.getenv('AWS_S3_PATH_PREFIX', '')
            }

        elif destination_type == 'azure':
            # For Azure: AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER
            connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            container = os.getenv('AZURE_STORAGE_CONTAINER')

            if not all([connection_string, container]):
                missing = []
                if not connection_string:
                    missing.append('AZURE_STORAGE_CONNECTION_STRING')
                if not container:
                    missing.append('AZURE_STORAGE_CONTAINER')
                raise ValueError(
                    f"Missing required Azure environment variables: {', '.join(missing)}. "
                    "Please configure credentials in the export destination settings."
                )

            logger.info(
                f"Using Azure environment variable fallback: container={container}"
            )

            return {
                'connection_string': connection_string,
                'container_name': container,
                'path_prefix': os.getenv('AZURE_STORAGE_PATH_PREFIX', '')
            }

        elif destination_type == 'gcs':
            # For GCS: GOOGLE_APPLICATION_CREDENTIALS, GCS_BUCKET_NAME
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            bucket = os.getenv('GCS_BUCKET_NAME')

            if not all([credentials_path, bucket]):
                missing = []
                if not credentials_path:
                    missing.append('GOOGLE_APPLICATION_CREDENTIALS')
                if not bucket:
                    missing.append('GCS_BUCKET_NAME')
                raise ValueError(
                    f"Missing required GCS environment variables: {', '.join(missing)}. "
                    "Please configure credentials in the export destination settings."
                )

            # Read service account JSON
            try:
                with open(credentials_path, 'r') as f:
                    service_account_json = f.read()
            except FileNotFoundError:
                raise ValueError(
                    f"GCS service account file not found at {credentials_path}. "
                    "Please ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid file."
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to read GCS service account file: {str(e)}"
                )

            logger.info(
                f"Using GCS environment variable fallback: bucket={bucket}"
            )

            return {
                'service_account_json': service_account_json,
                'bucket_name': bucket,
                'path_prefix': os.getenv('GCS_PATH_PREFIX', '')
            }

        elif destination_type == 'google_drive':
            logger.error(
                "Google Drive does not support environment variable fallback (OAuth2 required)"
            )
            raise ValueError(
                "Google Drive requires OAuth2 authentication and does not support "
                "environment variable fallback. Please configure credentials in the "
                "export destination settings."
            )

        else:
            raise ValueError(f"Unknown destination type: {destination_type}")

    def mask_credentials(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """
        Mask sensitive credential values for API responses.

        SECURITY: This method ensures sensitive credentials are never exposed in API responses.
        Sensitive fields (secrets, keys, passwords) show only the last 4 characters.
        Non-sensitive fields (regions, bucket names, etc.) show full values.

        Args:
            credentials: Credentials dictionary

        Returns:
            Dictionary with masked sensitive values (e.g., "****ABCD") and full non-sensitive values
        """
        # Define which fields should be masked (secrets, keys, passwords, tokens)
        # Use exact field name matching to avoid false positives
        sensitive_fields = {
            'secret_access_key', 'account_key', 'credentials', 'oauth_token',
            'refresh_token', 'connection_string', 'service_account_json',
            'private_key', 'api_key', 'password', 'token', 'secret', 'access_token'
        }

        masked = {}

        for key, value in credentials.items():
            # Check if this field should be masked (exact match or contains sensitive keyword)
            key_lower = key.lower()
            should_mask = (
                key_lower in sensitive_fields or
                key_lower.endswith('_secret') or
                key_lower.endswith('_key') or
                key_lower.endswith('_password') or
                key_lower.endswith('_token') or
                'secret' in key_lower and 'secret' != key_lower.replace('_', '') or
                'password' in key_lower or
                'token' in key_lower and key_lower != 'token_type'
            )

            # Explicitly exclude non-sensitive fields that might match patterns
            non_sensitive_fields = {
                'bucket_name', 'container_name', 'region', 'project_id',
                'folder_id', 'path_prefix', 'account_name', 'access_key_id'
            }
            if key_lower in non_sensitive_fields:
                should_mask = False

            if should_mask and isinstance(value, str):
                if len(value) > 4:
                    # Show only last 4 characters for identification
                    masked[key] = '****' + value[-4:]
                else:
                    # Value too short, mask completely
                    masked[key] = '****'
            else:
                # Non-sensitive fields or non-string values: show as-is
                masked[key] = str(value) if value is not None else ''

        logger.debug(f"Masked {len([k for k in credentials.keys() if any(s in k.lower() for s in sensitive_fields)])} sensitive fields out of {len(credentials)} total fields")

        return masked

    async def test_connection(self, destination_id: int) -> Tuple[bool, Optional[str]]:
        """
        Test connection to an export destination.

        Args:
            destination_id: ID of the destination to test

        Returns:
            Tuple of (success, error_message)
        """
        try:
            destination = self.get_destination(destination_id)

            if not destination:
                return False, f"Destination {destination_id} not found"

            # Get decrypted credentials
            credentials = self.get_decrypted_credentials(destination_id)

            # Test based on destination type
            if destination.destination_type == 's3':
                success, error = await self._test_s3_connection(credentials)
            elif destination.destination_type == 'azure':
                success, error = await self._test_azure_connection(credentials)
            elif destination.destination_type == 'gcs':
                success, error = await self._test_gcs_connection(credentials)
            elif destination.destination_type == 'google_drive':
                success, error = await self._test_google_drive_connection(credentials)
            else:
                return False, f"Unknown destination type: {destination.destination_type}"

            # Update test results
            destination.last_test_at = datetime.now(timezone.utc)
            destination.last_test_success = success
            destination.last_test_error = error if not success else None

            self.db.commit()

            return success, error

        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            logger.error(f"Failed to test destination {destination_id}: {error_msg}")

            # Update test results
            if destination:
                destination.last_test_at = datetime.now(timezone.utc)
                destination.last_test_success = False
                destination.last_test_error = error_msg
                self.db.commit()

            return False, error_msg

    async def _test_s3_connection(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Test AWS S3 connection by attempting to list bucket contents.

        Args:
            credentials: S3 credentials

        Returns:
            Tuple of (success, error_message)
        """
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            import os

            # Extract credentials with environment variable fallback
            access_key_id = credentials.get('access_key_id', '').strip() or os.getenv('AWS_S3_ACCESS_KEY_ID', '')
            secret_access_key = credentials.get('secret_access_key', '').strip() or os.getenv('AWS_S3_SECRET_ACCESS_KEY', '')
            region = credentials.get('region', '').strip() or os.getenv('AWS_S3_REGION', 'us-east-1')
            bucket_name = credentials.get('bucket_name', '').strip() or os.getenv('AWS_S3_BUCKET_NAME', '')
            path_prefix = credentials.get('path_prefix', '').strip()

            using_env_fallback = not credentials.get('access_key_id')
            if using_env_fallback:
                logger.info("Using environment variables for S3 credentials")

            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region
            )

            # Attempt to list bucket contents (limit to 1 object)

            s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=path_prefix,
                MaxKeys=1
            )

            logger.info(f"S3 connection test successful for bucket {bucket_name}")
            return True, None

        except NoCredentialsError:
            return False, "Invalid AWS credentials"
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return False, f"S3 error ({error_code}): {error_msg}"
        except Exception as e:
            return False, f"S3 connection failed: {str(e)}"

    async def _test_azure_connection(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Test Azure Blob Storage connection by attempting to list container.

        Args:
            credentials: Azure credentials

        Returns:
            Tuple of (success, error_message)
        """
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.core.exceptions import AzureError
        except ImportError:
            return False, "Azure SDK not installed. Install with: pip install azure-storage-blob"

        try:
            # Create blob service client
            if 'connection_string' in credentials:
                blob_service_client = BlobServiceClient.from_connection_string(
                    credentials['connection_string']
                )
            else:
                account_name = credentials.get('account_name')
                account_key = credentials.get('account_key')
                account_url = f"https://{account_name}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key
                )

            # Attempt to list container contents
            container_name = credentials.get('container_name')
            container_client = blob_service_client.get_container_client(container_name)

            # List blobs (limit to 1)
            blob_list = container_client.list_blobs(results_per_page=1)
            next(iter(blob_list), None)  # Force evaluation

            logger.info(f"Azure connection test successful for container {container_name}")
            return True, None

        except AzureError as e:
            return False, f"Azure error: {str(e)}"
        except Exception as e:
            return False, f"Azure connection failed: {str(e)}"

    async def _test_gcs_connection(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Test Google Cloud Storage connection by attempting to list bucket.

        Args:
            credentials: GCS credentials

        Returns:
            Tuple of (success, error_message)
        """
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
            from google.api_core.exceptions import GoogleAPIError
        except ImportError:
            return False, "Google Cloud SDK not installed. Install with: pip install google-cloud-storage"

        try:
            import json

            # Parse service account credentials
            if 'service_account_json' in credentials:
                service_account_info = json.loads(credentials['service_account_json'])
                credentials_obj = service_account.Credentials.from_service_account_info(
                    service_account_info
                )
            else:
                # Use project_id and credentials
                credentials_info = json.loads(credentials['credentials'])
                credentials_obj = service_account.Credentials.from_service_account_info(
                    credentials_info
                )

            # Create storage client
            storage_client = storage.Client(
                credentials=credentials_obj,
                project=credentials_obj.project_id
            )

            # Attempt to list bucket contents
            bucket_name = credentials.get('bucket_name')
            bucket = storage_client.bucket(bucket_name)

            # List blobs (limit to 1)
            blobs = list(bucket.list_blobs(max_results=1))

            logger.info(f"GCS connection test successful for bucket {bucket_name}")
            return True, None

        except GoogleAPIError as e:
            return False, f"GCS error: {str(e)}"
        except Exception as e:
            return False, f"GCS connection failed: {str(e)}"

    async def _test_google_drive_connection(self, credentials: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Test Google Drive connection by attempting to access folder.

        Args:
            credentials: Google Drive credentials

        Returns:
            Tuple of (success, error_message)
        """
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            from googleapiclient.errors import HttpError

            # Create credentials object
            creds = Credentials(
                token=credentials.get('oauth_token'),
                refresh_token=credentials.get('refresh_token')
            )

            # Build Drive API service
            service = build('drive', 'v3', credentials=creds)

            # Attempt to get folder metadata
            folder_id = credentials.get('folder_id')
            folder = service.files().get(
                fileId=folder_id,
                fields='id,name,mimeType'
            ).execute()

            # Verify it's a folder
            if folder.get('mimeType') != 'application/vnd.google-apps.folder':
                return False, "Specified ID is not a folder"

            logger.info(f"Google Drive connection test successful for folder {folder_id}")
            return True, None

        except HttpError as e:
            return False, f"Google Drive error: {str(e)}"
        except Exception as e:
            return False, f"Google Drive connection failed: {str(e)}"
