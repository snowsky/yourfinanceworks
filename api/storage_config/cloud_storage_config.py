"""
Cloud Storage Configuration for multi-provider file storage.

This module provides configuration management for cloud storage providers,
including AWS S3, Azure Blob Storage, and Google Cloud Storage with
credential encryption and validation capabilities.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class StorageProvider(Enum):
    """Supported cloud storage providers."""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    AZURE_BLOB = "azure_blob"
    GCP_STORAGE = "gcp_storage"


class StorageClass(Enum):
    """Storage classes for cost optimization."""
    STANDARD = "standard"
    INFREQUENT_ACCESS = "infrequent_access"
    ARCHIVE = "archive"
    DEEP_ARCHIVE = "deep_archive"


@dataclass
class CloudStorageConfig:
    """
    Configuration class for cloud storage settings.

    Supports environment variable configuration and validation
    for all supported cloud storage providers.
    """

    # Provider selection
    PRIMARY_PROVIDER: str = field(default_factory=lambda: 
        os.getenv("CLOUD_STORAGE_PRIMARY_PROVIDER", StorageProvider.LOCAL.value))
    
    FALLBACK_ENABLED: bool = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_FALLBACK_ENABLED", "true").lower() == "true")
    
    FALLBACK_PROVIDER: str = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_FALLBACK_PROVIDER", StorageProvider.LOCAL.value))

    # General settings
    MAX_FILE_SIZE: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_MAX_FILE_SIZE", "104857600")))  # 100MB default
    
    ALLOWED_EXTENSIONS: List[str] = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_ALLOWED_EXTENSIONS", 
                 "pdf,jpg,jpeg,png,gif,doc,docx,xls,xlsx,txt,csv").split(","))
    
    URL_EXPIRY_SECONDS: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_URL_EXPIRY_SECONDS", "3600")))  # 1 hour default

    # AWS S3 Configuration
    AWS_S3_ENABLED: bool = field(default_factory=lambda:
        os.getenv("AWS_S3_ENABLED", "false").lower() == "true")
    
    AWS_S3_BUCKET_NAME: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_S3_BUCKET_NAME"))
    
    AWS_S3_REGION: str = field(default_factory=lambda:
        os.getenv("AWS_S3_REGION", "us-east-1"))
    
    AWS_S3_ACCESS_KEY_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_S3_ACCESS_KEY_ID"))
    
    AWS_S3_SECRET_ACCESS_KEY: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_S3_SECRET_ACCESS_KEY"))
    
    AWS_S3_ENDPOINT_URL: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_S3_ENDPOINT_URL"))  # For S3-compatible services
    
    AWS_S3_USE_SSL: bool = field(default_factory=lambda:
        os.getenv("AWS_S3_USE_SSL", "true").lower() == "true")
    
    AWS_S3_STORAGE_CLASS: str = field(default_factory=lambda:
        os.getenv("AWS_S3_STORAGE_CLASS", StorageClass.STANDARD.value))

    # Azure Blob Storage Configuration
    AZURE_BLOB_ENABLED: bool = field(default_factory=lambda:
        os.getenv("AZURE_BLOB_ENABLED", "false").lower() == "true")
    
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_STORAGE_ACCOUNT_NAME"))
    
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_STORAGE_ACCOUNT_KEY"))
    
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
    
    AZURE_CONTAINER_NAME: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_CONTAINER_NAME"))
    
    AZURE_BLOB_ENDPOINT: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_BLOB_ENDPOINT"))
    
    AZURE_BLOB_TIER: str = field(default_factory=lambda:
        os.getenv("AZURE_BLOB_TIER", "Hot"))

    # Google Cloud Storage Configuration
    GCP_STORAGE_ENABLED: bool = field(default_factory=lambda:
        os.getenv("GCP_STORAGE_ENABLED", "false").lower() == "true")
    
    GCP_BUCKET_NAME: Optional[str] = field(default_factory=lambda:
        os.getenv("GCP_BUCKET_NAME"))
    
    GCP_PROJECT_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("GCP_PROJECT_ID"))
    
    GCP_CREDENTIALS_PATH: Optional[str] = field(default_factory=lambda:
        os.getenv("GCP_CREDENTIALS_PATH"))
    
    GCP_CREDENTIALS_JSON: Optional[str] = field(default_factory=lambda:
        os.getenv("GCP_CREDENTIALS_JSON"))  # Base64 encoded JSON
    
    GCP_STORAGE_CLASS: str = field(default_factory=lambda:
        os.getenv("GCP_STORAGE_CLASS", "STANDARD"))

    # Local Storage Configuration (fallback)
    LOCAL_STORAGE_PATH: str = field(default_factory=lambda:
        os.getenv("LOCAL_STORAGE_PATH", "./attachments"))
    
    LOCAL_STORAGE_MAX_SIZE: int = field(default_factory=lambda:
        int(os.getenv("LOCAL_STORAGE_MAX_SIZE", "1073741824")))  # 1GB default

    # Security and Encryption
    ENCRYPT_CREDENTIALS: bool = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_ENCRYPT_CREDENTIALS", "true").lower() == "true")
    
    ENCRYPTION_KEY_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_ENCRYPTION_KEY_ID"))

    # Performance settings
    CONNECTION_TIMEOUT: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_CONNECTION_TIMEOUT", "30")))
    
    READ_TIMEOUT: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_READ_TIMEOUT", "60")))
    
    MAX_RETRIES: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_MAX_RETRIES", "3")))
    
    RETRY_BACKOFF_FACTOR: float = field(default_factory=lambda:
        float(os.getenv("CLOUD_STORAGE_RETRY_BACKOFF_FACTOR", "2.0")))

    # Circuit breaker settings
    CIRCUIT_BREAKER_ENABLED: bool = field(default_factory=lambda:
        os.getenv("CLOUD_STORAGE_CIRCUIT_BREAKER_ENABLED", "true").lower() == "true")
    
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")))
    
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = field(default_factory=lambda:
        int(os.getenv("CLOUD_STORAGE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")))

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """
        Validate cloud storage configuration settings.

        Raises:
            ValueError: If configuration is invalid
        """
        errors = []

        # Validate primary provider
        try:
            StorageProvider(self.PRIMARY_PROVIDER)
        except ValueError:
            errors.append(f"Invalid primary provider: {self.PRIMARY_PROVIDER}")

        # Validate fallback provider
        if self.FALLBACK_ENABLED:
            try:
                StorageProvider(self.FALLBACK_PROVIDER)
            except ValueError:
                errors.append(f"Invalid fallback provider: {self.FALLBACK_PROVIDER}")

        # Validate provider-specific settings
        if self.AWS_S3_ENABLED:
            aws_errors = self._validate_aws_s3_config()
            errors.extend(aws_errors)

        if self.AZURE_BLOB_ENABLED:
            azure_errors = self._validate_azure_blob_config()
            errors.extend(azure_errors)

        if self.GCP_STORAGE_ENABLED:
            gcp_errors = self._validate_gcp_storage_config()
            errors.extend(gcp_errors)

        # Validate general settings
        if self.MAX_FILE_SIZE <= 0:
            errors.append("MAX_FILE_SIZE must be greater than 0")

        if self.URL_EXPIRY_SECONDS <= 0:
            errors.append("URL_EXPIRY_SECONDS must be greater than 0")

        if self.CONNECTION_TIMEOUT <= 0:
            errors.append("CONNECTION_TIMEOUT must be greater than 0")

        if self.READ_TIMEOUT <= 0:
            errors.append("READ_TIMEOUT must be greater than 0")

        if self.MAX_RETRIES < 0:
            errors.append("MAX_RETRIES must be non-negative")

        if self.RETRY_BACKOFF_FACTOR <= 0:
            errors.append("RETRY_BACKOFF_FACTOR must be greater than 0")

        # Validate that at least one provider is enabled
        enabled_providers = []
        if self.AWS_S3_ENABLED:
            enabled_providers.append("AWS S3")
        if self.AZURE_BLOB_ENABLED:
            enabled_providers.append("Azure Blob")
        if self.GCP_STORAGE_ENABLED:
            enabled_providers.append("GCP Storage")
        
        # Local storage is always available as fallback
        enabled_providers.append("Local Storage")

        if not enabled_providers:
            errors.append("At least one storage provider must be enabled")

        if errors:
            error_message = "Cloud storage configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            logger.error(error_message)
            raise ValueError(error_message)

        logger.info(f"Cloud storage configuration validated successfully. Enabled providers: {', '.join(enabled_providers)}")

    def _validate_aws_s3_config(self) -> List[str]:
        """Validate AWS S3 configuration."""
        errors = []
        
        if not self.AWS_S3_BUCKET_NAME:
            errors.append("AWS_S3_BUCKET_NAME is required when AWS S3 is enabled")
        
        if not self.AWS_S3_ACCESS_KEY_ID:
            errors.append("AWS_S3_ACCESS_KEY_ID is required when AWS S3 is enabled")
        
        if not self.AWS_S3_SECRET_ACCESS_KEY:
            errors.append("AWS_S3_SECRET_ACCESS_KEY is required when AWS S3 is enabled")
        
        # Validate storage class
        valid_s3_classes = ["STANDARD", "REDUCED_REDUNDANCY", "STANDARD_IA", 
                           "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER", 
                           "DEEP_ARCHIVE", "GLACIER_IR"]
        if self.AWS_S3_STORAGE_CLASS.upper() not in valid_s3_classes:
            errors.append(f"Invalid AWS S3 storage class: {self.AWS_S3_STORAGE_CLASS}")
        
        return errors

    def _validate_azure_blob_config(self) -> List[str]:
        """Validate Azure Blob Storage configuration."""
        errors = []
        
        if not self.AZURE_CONTAINER_NAME:
            errors.append("AZURE_CONTAINER_NAME is required when Azure Blob is enabled")
        
        # Either connection string or account name/key is required
        if not self.AZURE_STORAGE_CONNECTION_STRING:
            if not self.AZURE_STORAGE_ACCOUNT_NAME:
                errors.append("AZURE_STORAGE_ACCOUNT_NAME is required when Azure Blob is enabled and connection string is not provided")
            if not self.AZURE_STORAGE_ACCOUNT_KEY:
                errors.append("AZURE_STORAGE_ACCOUNT_KEY is required when Azure Blob is enabled and connection string is not provided")
        
        # Validate blob tier
        valid_blob_tiers = ["Hot", "Cool", "Archive"]
        if self.AZURE_BLOB_TIER not in valid_blob_tiers:
            errors.append(f"Invalid Azure Blob tier: {self.AZURE_BLOB_TIER}")
        
        return errors

    def _validate_gcp_storage_config(self) -> List[str]:
        """Validate Google Cloud Storage configuration."""
        errors = []
        
        if not self.GCP_BUCKET_NAME:
            errors.append("GCP_BUCKET_NAME is required when GCP Storage is enabled")
        
        if not self.GCP_PROJECT_ID:
            errors.append("GCP_PROJECT_ID is required when GCP Storage is enabled")
        
        # Either credentials path or JSON is required
        if not self.GCP_CREDENTIALS_PATH and not self.GCP_CREDENTIALS_JSON:
            errors.append("Either GCP_CREDENTIALS_PATH or GCP_CREDENTIALS_JSON is required when GCP Storage is enabled")
        
        # Validate storage class
        valid_gcp_classes = ["STANDARD", "NEARLINE", "COLDLINE", "ARCHIVE"]
        if self.GCP_STORAGE_CLASS.upper() not in valid_gcp_classes:
            errors.append(f"Invalid GCP storage class: {self.GCP_STORAGE_CLASS}")
        
        return errors

    def get_provider_config(self, provider: StorageProvider) -> Dict[str, Any]:
        """
        Get configuration for a specific provider.

        Args:
            provider: Storage provider enum

        Returns:
            Dictionary with provider-specific configuration
        """
        if provider == StorageProvider.AWS_S3:
            return self._get_aws_s3_config()
        elif provider == StorageProvider.AZURE_BLOB:
            return self._get_azure_blob_config()
        elif provider == StorageProvider.GCP_STORAGE:
            return self._get_gcp_storage_config()
        elif provider == StorageProvider.LOCAL:
            return self._get_local_storage_config()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _get_aws_s3_config(self) -> Dict[str, Any]:
        """Get AWS S3 configuration."""
        config = {
            "bucket_name": self.AWS_S3_BUCKET_NAME,
            "region": self.AWS_S3_REGION,
            "access_key_id": self.AWS_S3_ACCESS_KEY_ID,
            "secret_access_key": self.AWS_S3_SECRET_ACCESS_KEY,
            "use_ssl": self.AWS_S3_USE_SSL,
            "storage_class": self.AWS_S3_STORAGE_CLASS.upper(),
            "connection_timeout": self.CONNECTION_TIMEOUT,
            "read_timeout": self.READ_TIMEOUT,
            "max_retries": self.MAX_RETRIES,
            "retry_backoff_factor": self.RETRY_BACKOFF_FACTOR
        }
        
        if self.AWS_S3_ENDPOINT_URL:
            config["endpoint_url"] = self.AWS_S3_ENDPOINT_URL
        
        return config

    def _get_azure_blob_config(self) -> Dict[str, Any]:
        """Get Azure Blob Storage configuration."""
        config = {
            "container_name": self.AZURE_CONTAINER_NAME,
            "blob_tier": self.AZURE_BLOB_TIER,
            "connection_timeout": self.CONNECTION_TIMEOUT,
            "read_timeout": self.READ_TIMEOUT,
            "max_retries": self.MAX_RETRIES,
            "retry_backoff_factor": self.RETRY_BACKOFF_FACTOR
        }
        
        if self.AZURE_STORAGE_CONNECTION_STRING:
            config["connection_string"] = self.AZURE_STORAGE_CONNECTION_STRING
        else:
            config["account_name"] = self.AZURE_STORAGE_ACCOUNT_NAME
            config["account_key"] = self.AZURE_STORAGE_ACCOUNT_KEY
        
        if self.AZURE_BLOB_ENDPOINT:
            config["blob_endpoint"] = self.AZURE_BLOB_ENDPOINT
        
        return config

    def _get_gcp_storage_config(self) -> Dict[str, Any]:
        """Get Google Cloud Storage configuration."""
        config = {
            "bucket_name": self.GCP_BUCKET_NAME,
            "project_id": self.GCP_PROJECT_ID,
            "storage_class": self.GCP_STORAGE_CLASS.upper(),
            "connection_timeout": self.CONNECTION_TIMEOUT,
            "read_timeout": self.READ_TIMEOUT,
            "max_retries": self.MAX_RETRIES,
            "retry_backoff_factor": self.RETRY_BACKOFF_FACTOR
        }
        
        if self.GCP_CREDENTIALS_PATH:
            config["credentials_path"] = self.GCP_CREDENTIALS_PATH
        elif self.GCP_CREDENTIALS_JSON:
            config["credentials_json"] = self.GCP_CREDENTIALS_JSON
        
        return config

    def _get_local_storage_config(self) -> Dict[str, Any]:
        """Get local storage configuration."""
        return {
            "storage_path": self.LOCAL_STORAGE_PATH,
            "max_size": self.LOCAL_STORAGE_MAX_SIZE,
            "max_file_size": self.MAX_FILE_SIZE,
            "allowed_extensions": self.ALLOWED_EXTENSIONS
        }

    def get_enabled_providers(self) -> List[StorageProvider]:
        """
        Get list of enabled storage providers.

        Returns:
            List of enabled provider enums
        """
        providers = []
        
        if self.AWS_S3_ENABLED:
            providers.append(StorageProvider.AWS_S3)
        
        if self.AZURE_BLOB_ENABLED:
            providers.append(StorageProvider.AZURE_BLOB)
        
        if self.GCP_STORAGE_ENABLED:
            providers.append(StorageProvider.GCP_STORAGE)
        
        # Local storage is always available
        providers.append(StorageProvider.LOCAL)
        
        return providers

    def get_primary_provider(self) -> StorageProvider:
        """Get the primary storage provider."""
        return StorageProvider(self.PRIMARY_PROVIDER)

    def get_fallback_provider(self) -> Optional[StorageProvider]:
        """Get the fallback storage provider."""
        if self.FALLBACK_ENABLED:
            return StorageProvider(self.FALLBACK_PROVIDER)
        return None

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """
        Encrypt sensitive credentials using the existing encryption system.

        Args:
            credentials: Dictionary containing sensitive data

        Returns:
            Base64 encoded encrypted credentials
        """
        if not self.ENCRYPT_CREDENTIALS:
            return json.dumps(credentials)

        try:
            # Import encryption service
            from services.key_management_service import get_key_management_service
            
            key_service = get_key_management_service()
            
            # Convert credentials to JSON string
            credentials_json = json.dumps(credentials)
            credentials_bytes = credentials_json.encode('utf-8')
            
            # Encrypt using master key (similar to tenant key encryption)
            encrypted_data = key_service._encrypt_with_master_key(credentials_bytes)
            
            logger.debug("Successfully encrypted cloud storage credentials")
            return encrypted_data
            
        except Exception as e:
            logger.error(f"Failed to encrypt credentials: {str(e)}")
            # Fall back to unencrypted storage with warning
            logger.warning("Storing credentials unencrypted due to encryption failure")
            return json.dumps(credentials)

    def decrypt_credentials(self, encrypted_credentials: str) -> Dict[str, Any]:
        """
        Decrypt sensitive credentials using the existing encryption system.

        Args:
            encrypted_credentials: Base64 encoded encrypted credentials

        Returns:
            Dictionary containing decrypted credentials
        """
        if not self.ENCRYPT_CREDENTIALS:
            return json.loads(encrypted_credentials)

        try:
            # Import encryption service
            from services.key_management_service import get_key_management_service
            
            key_service = get_key_management_service()
            
            # Decrypt using master key
            decrypted_bytes = key_service._decrypt_with_master_key(encrypted_credentials)
            credentials_json = decrypted_bytes.decode('utf-8')
            
            logger.debug("Successfully decrypted cloud storage credentials")
            return json.loads(credentials_json)
            
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {str(e)}")
            # Try to parse as unencrypted JSON
            try:
                return json.loads(encrypted_credentials)
            except json.JSONDecodeError:
                logger.error("Failed to parse credentials as JSON")
                raise ValueError("Invalid encrypted credentials format")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary, redacting sensitive values.

        Returns:
            Dictionary representation of configuration
        """
        config_dict = {}
        sensitive_fields = [
            "AWS_S3_SECRET_ACCESS_KEY", "AZURE_STORAGE_ACCOUNT_KEY", 
            "AZURE_STORAGE_CONNECTION_STRING", "GCP_CREDENTIALS_JSON",
            "ENCRYPTION_KEY_ID"
        ]
        
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name in sensitive_fields and value:
                config_dict[field_name] = "***REDACTED***"
            else:
                config_dict[field_name] = value
        
        return config_dict

    @classmethod
    def from_env(cls) -> 'CloudStorageConfig':
        """
        Create configuration from environment variables.

        Returns:
            CloudStorageConfig instance
        """
        return cls()

    @classmethod
    def create_test_config(cls) -> 'CloudStorageConfig':
        """
        Create configuration for testing purposes.

        Returns:
            CloudStorageConfig instance with test settings
        """
        return cls(
            PRIMARY_PROVIDER=StorageProvider.LOCAL.value,
            FALLBACK_ENABLED=True,
            FALLBACK_PROVIDER=StorageProvider.LOCAL.value,
            AWS_S3_ENABLED=False,
            AZURE_BLOB_ENABLED=False,
            GCP_STORAGE_ENABLED=False,
            LOCAL_STORAGE_PATH="./test_attachments",
            MAX_FILE_SIZE=10485760,  # 10MB
            URL_EXPIRY_SECONDS=3600,
            ENCRYPT_CREDENTIALS=False,  # Disable for testing
            CONNECTION_TIMEOUT=10,
            READ_TIMEOUT=30,
            MAX_RETRIES=2,
            CIRCUIT_BREAKER_ENABLED=False
        )


# Global configuration instance
_cloud_storage_config: Optional[CloudStorageConfig] = None


def get_cloud_storage_config() -> CloudStorageConfig:
    """
    Get global cloud storage configuration instance.

    Returns:
        CloudStorageConfig instance
    """
    global _cloud_storage_config
    if _cloud_storage_config is None:
        _cloud_storage_config = CloudStorageConfig.from_env()
    return _cloud_storage_config


def reload_cloud_storage_config() -> CloudStorageConfig:
    """
    Reload cloud storage configuration from environment.

    Returns:
        New CloudStorageConfig instance
    """
    global _cloud_storage_config
    _cloud_storage_config = CloudStorageConfig.from_env()
    return _cloud_storage_config


class CloudStorageConfigurationManager:
    """
    Manager for cloud storage provider configurations with database persistence.
    """
    
    def __init__(self):
        self.config = get_cloud_storage_config()
    
    def validate_provider_config(self, provider: StorageProvider, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration for a specific provider.
        
        Args:
            provider: Storage provider to validate
            config: Configuration dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if provider == StorageProvider.AWS_S3:
            required_fields = ["bucket_name", "access_key_id", "secret_access_key"]
            for field in required_fields:
                if not config.get(field):
                    errors.append(f"AWS S3 requires {field}")
        
        elif provider == StorageProvider.AZURE_BLOB:
            if not config.get("container_name"):
                errors.append("Azure Blob requires container_name")
            
            # Either connection string or account credentials
            if not config.get("connection_string"):
                if not config.get("account_name") or not config.get("account_key"):
                    errors.append("Azure Blob requires either connection_string or account_name/account_key")
        
        elif provider == StorageProvider.GCP_STORAGE:
            required_fields = ["bucket_name", "project_id"]
            for field in required_fields:
                if not config.get(field):
                    errors.append(f"GCP Storage requires {field}")
            
            if not config.get("credentials_path") and not config.get("credentials_json"):
                errors.append("GCP Storage requires either credentials_path or credentials_json")
        
        elif provider == StorageProvider.LOCAL:
            if not config.get("storage_path"):
                errors.append("Local storage requires storage_path")
        
        return errors
    
    def test_provider_connection(self, provider: StorageProvider, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test connection to a storage provider.
        
        Args:
            provider: Storage provider to test
            config: Provider configuration
            
        Returns:
            Dictionary with test results
        """
        try:
            if provider == StorageProvider.AWS_S3:
                return self._test_aws_s3_connection(config)
            elif provider == StorageProvider.AZURE_BLOB:
                return self._test_azure_blob_connection(config)
            elif provider == StorageProvider.GCP_STORAGE:
                return self._test_gcp_storage_connection(config)
            elif provider == StorageProvider.LOCAL:
                return self._test_local_storage_connection(config)
            else:
                return {"success": False, "error": f"Unsupported provider: {provider}"}
        
        except Exception as e:
            logger.error(f"Connection test failed for {provider}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _test_aws_s3_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test AWS S3 connection."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=config.get('access_key_id'),
                aws_secret_access_key=config.get('secret_access_key'),
                region_name=config.get('region', 'us-east-1'),
                endpoint_url=config.get('endpoint_url')
            )
            
            # Test bucket access
            bucket_name = config.get('bucket_name')
            s3_client.head_bucket(Bucket=bucket_name)
            
            return {
                "success": True,
                "message": f"Successfully connected to S3 bucket: {bucket_name}",
                "provider": "aws_s3"
            }
            
        except NoCredentialsError:
            return {"success": False, "error": "Invalid AWS credentials"}
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return {"success": False, "error": f"Bucket not found: {bucket_name}"}
            elif error_code == '403':
                return {"success": False, "error": "Access denied to bucket"}
            else:
                return {"success": False, "error": f"AWS S3 error: {str(e)}"}
        except ImportError:
            return {"success": False, "error": "boto3 library not installed"}
        except Exception as e:
            return {"success": False, "error": f"Connection test failed: {str(e)}"}
    
    def _test_azure_blob_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Azure Blob Storage connection."""
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError
            
            # Create blob service client
            if config.get('connection_string'):
                blob_service_client = BlobServiceClient.from_connection_string(
                    config['connection_string']
                )
            else:
                account_url = f"https://{config['account_name']}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=config['account_key']
                )
            
            # Test container access
            container_name = config.get('container_name')
            container_client = blob_service_client.get_container_client(container_name)
            container_client.get_container_properties()
            
            return {
                "success": True,
                "message": f"Successfully connected to Azure container: {container_name}",
                "provider": "azure_blob"
            }
            
        except ClientAuthenticationError:
            return {"success": False, "error": "Invalid Azure credentials"}
        except ResourceNotFoundError:
            return {"success": False, "error": f"Container not found: {container_name}"}
        except ImportError:
            return {"success": False, "error": "azure-storage-blob library not installed"}
        except Exception as e:
            return {"success": False, "error": f"Connection test failed: {str(e)}"}
    
    def _test_gcp_storage_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Google Cloud Storage connection."""
        try:
            from google.cloud import storage
            from google.auth.exceptions import DefaultCredentialsError
            import json
            import tempfile
            import os
            
            # Set up credentials
            if config.get('credentials_json'):
                # Use JSON credentials
                credentials_dict = json.loads(config['credentials_json'])
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(credentials_dict, f)
                    credentials_path = f.name
                
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            elif config.get('credentials_path'):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = config['credentials_path']
            
            # Create storage client
            client = storage.Client(project=config.get('project_id'))
            
            # Test bucket access
            bucket_name = config.get('bucket_name')
            bucket = client.bucket(bucket_name)
            bucket.reload()  # This will raise an exception if bucket doesn't exist or no access
            
            # Clean up temporary credentials file
            if config.get('credentials_json') and 'credentials_path' in locals():
                try:
                    os.unlink(credentials_path)
                except:
                    pass
            
            return {
                "success": True,
                "message": f"Successfully connected to GCS bucket: {bucket_name}",
                "provider": "gcp_storage"
            }
            
        except DefaultCredentialsError:
            return {"success": False, "error": "Invalid GCP credentials"}
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return {"success": False, "error": f"Bucket not found: {bucket_name}"}
            elif "403" in error_msg:
                return {"success": False, "error": "Access denied to bucket"}
            else:
                return {"success": False, "error": f"Connection test failed: {error_msg}"}
    
    def _test_local_storage_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test local storage connection."""
        try:
            import os
            
            storage_path = config.get('storage_path')
            
            # Check if path exists or can be created
            if not os.path.exists(storage_path):
                os.makedirs(storage_path, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(storage_path, '.test_write_access')
            with open(test_file, 'w') as f:
                f.write('test')
            
            # Clean up test file
            os.unlink(test_file)
            
            return {
                "success": True,
                "message": f"Successfully connected to local storage: {storage_path}",
                "provider": "local"
            }
            
        except PermissionError:
            return {"success": False, "error": f"No write permission to: {storage_path}"}
        except Exception as e:
            return {"success": False, "error": f"Local storage test failed: {str(e)}"}