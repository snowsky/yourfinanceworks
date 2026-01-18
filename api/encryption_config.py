"""
Encryption Configuration for tenant database encryption.

This module provides configuration management for encryption settings,
including PostgreSQL-specific optimizations and key vault integrations.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class KeyVaultProvider(Enum):
    """Supported key vault providers."""
    LOCAL = "local"
    AWS_KMS = "aws_kms"
    AZURE_KEYVAULT = "azure_keyvault"
    HASHICORP_VAULT = "hashicorp_vault"


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "AES-256-GCM"


@dataclass
class EncryptionConfig:
    """
    Configuration class for encryption settings.

    Supports environment variable configuration and validation
    for PostgreSQL-specific encryption requirements.
    """

    # Core encryption settings
    ENCRYPTION_ENABLED: bool = field(default_factory=lambda:
        os.getenv("ENCRYPTION_ENABLED", "true").lower() == "true")

    ENCRYPTION_ALGORITHM: str = field(default_factory=lambda:
        os.getenv("ENCRYPTION_ALGORITHM", EncryptionAlgorithm.AES_256_GCM.value))

    # Key management settings
    KEY_VAULT_PROVIDER: str = field(default_factory=lambda:
        os.getenv("KEY_VAULT_PROVIDER", KeyVaultProvider.LOCAL.value))

    MASTER_KEY_ID: str = field(default_factory=lambda:
        os.getenv("MASTER_KEY_ID", "default_master_key"))

    MASTER_KEY_PATH: str = field(default_factory=lambda:
        os.getenv("MASTER_KEY_PATH", "/app/keys/master.key"))

    # Key derivation settings
    KEY_DERIVATION_ITERATIONS: int = field(default_factory=lambda:
        int(os.getenv("KEY_DERIVATION_ITERATIONS", "100000")))

    KEY_DERIVATION_ITERATIONS_FALLBACK: List[int] = field(default_factory=lambda:
        [int(x) for x in os.getenv("KEY_DERIVATION_ITERATIONS_FALLBACK", "10000").split(",") if x])

    KEY_DERIVATION_SALT: str = field(default_factory=lambda:
        os.getenv("KEY_DERIVATION_SALT", "tenant_encryption_salt_2024"))

    # Key rotation settings
    KEY_ROTATION_INTERVAL_DAYS: int = field(default_factory=lambda:
        int(os.getenv("KEY_ROTATION_INTERVAL_DAYS", "90")))

    KEY_ROTATION_ENABLED: bool = field(default_factory=lambda:
        os.getenv("KEY_ROTATION_ENABLED", "true").lower() == "true")

    # Performance settings
    KEY_CACHE_TTL_SECONDS: int = field(default_factory=lambda:
        int(os.getenv("KEY_CACHE_TTL_SECONDS", "3600")))  # 1 hour

    KEY_CACHE_MAX_SIZE: int = field(default_factory=lambda:
        int(os.getenv("KEY_CACHE_MAX_SIZE", "1000")))

    # PostgreSQL-specific settings
    DATABASE_TYPE: str = field(default_factory=lambda:
        os.getenv("DATABASE_TYPE", "postgresql"))

    POSTGRES_JSONB_ENCRYPTION: bool = field(default_factory=lambda:
        os.getenv("POSTGRES_JSONB_ENCRYPTION", "true").lower() == "true")

    POSTGRES_INDEX_COMPATIBILITY: bool = field(default_factory=lambda:
        os.getenv("POSTGRES_INDEX_COMPATIBILITY", "false").lower() == "true")

    # Backup and recovery settings
    KEY_BACKUP_PATH: str = field(default_factory=lambda:
        os.getenv("KEY_BACKUP_PATH", "/app/backups/keys"))

    KEY_BACKUP_ENABLED: bool = field(default_factory=lambda:
        os.getenv("KEY_BACKUP_ENABLED", "true").lower() == "true")

    KEY_BACKUP_RETENTION_DAYS: int = field(default_factory=lambda:
        int(os.getenv("KEY_BACKUP_RETENTION_DAYS", "365")))

    # AWS KMS settings
    AWS_KMS_MASTER_KEY_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_KMS_MASTER_KEY_ID"))

    AWS_REGION: str = field(default_factory=lambda:
        os.getenv("AWS_REGION", "us-east-1"))

    AWS_ACCESS_KEY_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_ACCESS_KEY_ID"))

    AWS_SECRET_ACCESS_KEY: Optional[str] = field(default_factory=lambda:
        os.getenv("AWS_SECRET_ACCESS_KEY"))

    # Azure Key Vault settings
    AZURE_KEYVAULT_URL: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_KEYVAULT_URL"))

    AZURE_CLIENT_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_CLIENT_ID"))

    AZURE_CLIENT_SECRET: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_CLIENT_SECRET"))

    AZURE_TENANT_ID: Optional[str] = field(default_factory=lambda:
        os.getenv("AZURE_TENANT_ID"))

    # HashiCorp Vault settings
    HASHICORP_VAULT_URL: Optional[str] = field(default_factory=lambda:
        os.getenv("HASHICORP_VAULT_URL"))

    HASHICORP_VAULT_TOKEN: Optional[str] = field(default_factory=lambda:
        os.getenv("HASHICORP_VAULT_TOKEN"))

    HASHICORP_VAULT_NAMESPACE: Optional[str] = field(default_factory=lambda:
        os.getenv("HASHICORP_VAULT_NAMESPACE"))

    HASHICORP_VAULT_MOUNT_POINT: str = field(default_factory=lambda:
        os.getenv("HASHICORP_VAULT_MOUNT_POINT", "secret"))

    HASHICORP_VAULT_TRANSIT_MOUNT: str = field(default_factory=lambda:
        os.getenv("HASHICORP_VAULT_TRANSIT_MOUNT", "transit"))

    # Monitoring and alerting settings
    ENCRYPTION_MONITORING_ENABLED: bool = field(default_factory=lambda:
        os.getenv("ENCRYPTION_MONITORING_ENABLED", "true").lower() == "true")

    ENCRYPTION_METRICS_INTERVAL_SECONDS: int = field(default_factory=lambda:
        int(os.getenv("ENCRYPTION_METRICS_INTERVAL_SECONDS", "60")))

    ENCRYPTION_ALERT_FAILURE_THRESHOLD: int = field(default_factory=lambda:
        int(os.getenv("ENCRYPTION_ALERT_FAILURE_THRESHOLD", "10")))

    # Security settings
    SECURE_MEMORY_ENABLED: bool = field(default_factory=lambda:
        os.getenv("SECURE_MEMORY_ENABLED", "false").lower() == "true")

    MEMORY_PROTECTION_ENABLED: bool = field(default_factory=lambda:
        os.getenv("MEMORY_PROTECTION_ENABLED", "true").lower() == "true")

    AUDIT_LOGGING_ENABLED: bool = field(default_factory=lambda:
        os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true")

    # Compliance settings
    FIPS_MODE_ENABLED: bool = field(default_factory=lambda:
        os.getenv("FIPS_MODE_ENABLED", "false").lower() == "true")

    GDPR_COMPLIANCE_ENABLED: bool = field(default_factory=lambda:
        os.getenv("GDPR_COMPLIANCE_ENABLED", "true").lower() == "true")

    SOX_COMPLIANCE_ENABLED: bool = field(default_factory=lambda:
        os.getenv("SOX_COMPLIANCE_ENABLED", "false").lower() == "true")

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """
        Validate encryption configuration settings.

        Raises:
            ValueError: If configuration is invalid
        """
        errors = []

        # Validate encryption algorithm
        try:
            EncryptionAlgorithm(self.ENCRYPTION_ALGORITHM)
        except ValueError:
            errors.append(f"Invalid encryption algorithm: {self.ENCRYPTION_ALGORITHM}")

        # Validate key vault provider
        try:
            provider = KeyVaultProvider(self.KEY_VAULT_PROVIDER)
        except ValueError:
            errors.append(f"Invalid key vault provider: {self.KEY_VAULT_PROVIDER}")
        else:
            # Validate provider-specific settings
            if provider == KeyVaultProvider.AWS_KMS:
                if not self.AWS_KMS_MASTER_KEY_ID:
                    errors.append("AWS_KMS_MASTER_KEY_ID is required for AWS KMS provider")
            elif provider == KeyVaultProvider.AZURE_KEYVAULT:
                if not self.AZURE_KEYVAULT_URL:
                    errors.append("AZURE_KEYVAULT_URL is required for Azure Key Vault provider")
            elif provider == KeyVaultProvider.HASHICORP_VAULT:
                if not self.HASHICORP_VAULT_URL:
                    errors.append("HASHICORP_VAULT_URL is required for HashiCorp Vault provider")
                if not self.HASHICORP_VAULT_TOKEN:
                    errors.append("HASHICORP_VAULT_TOKEN is required for HashiCorp Vault provider")

        # Validate database type
        if self.DATABASE_TYPE.lower() != "postgresql":
            errors.append(f"Unsupported database type: {self.DATABASE_TYPE}. Only PostgreSQL is supported.")

        # Validate numeric settings
        if self.KEY_DERIVATION_ITERATIONS < 10000:
            errors.append("KEY_DERIVATION_ITERATIONS must be at least 10,000 for security")

        if self.KEY_CACHE_TTL_SECONDS < 60:
            errors.append("KEY_CACHE_TTL_SECONDS must be at least 60 seconds")

        if self.KEY_ROTATION_INTERVAL_DAYS < 1:
            errors.append("KEY_ROTATION_INTERVAL_DAYS must be at least 1 day")

        # Validate paths
        if self.KEY_VAULT_PROVIDER == KeyVaultProvider.LOCAL.value:
            master_key_dir = os.path.dirname(self.MASTER_KEY_PATH)
            if not os.path.exists(master_key_dir):
                try:
                    os.makedirs(master_key_dir, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create master key directory {master_key_dir}: {str(e)}")

        if errors:
            error_message = "Encryption configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            logger.error(error_message)
            raise ValueError(error_message)

        # logger.info("Encryption configuration validated successfully")

    def get_key_vault_config(self) -> Dict[str, Any]:
        """
        Get key vault provider-specific configuration.

        Returns:
            Dictionary with provider-specific settings
        """
        provider = KeyVaultProvider(self.KEY_VAULT_PROVIDER)

        if provider == KeyVaultProvider.AWS_KMS:
            return {
                "provider": "aws_kms",
                "master_key_id": self.AWS_KMS_MASTER_KEY_ID,
                "region": self.AWS_REGION,
                "access_key_id": self.AWS_ACCESS_KEY_ID,
                "secret_access_key": self.AWS_SECRET_ACCESS_KEY
            }
        elif provider == KeyVaultProvider.AZURE_KEYVAULT:
            return {
                "provider": "azure_keyvault",
                "vault_url": self.AZURE_KEYVAULT_URL,
                "client_id": self.AZURE_CLIENT_ID,
                "client_secret": self.AZURE_CLIENT_SECRET,
                "tenant_id": self.AZURE_TENANT_ID
            }
        elif provider == KeyVaultProvider.HASHICORP_VAULT:
            return {
                "provider": "hashicorp_vault",
                "url": self.HASHICORP_VAULT_URL,
                "token": self.HASHICORP_VAULT_TOKEN,
                "namespace": self.HASHICORP_VAULT_NAMESPACE,
                "mount_point": self.HASHICORP_VAULT_MOUNT_POINT,
                "transit_mount": self.HASHICORP_VAULT_TRANSIT_MOUNT
            }
        else:  # LOCAL
            return {
                "provider": "local",
                "master_key_path": self.MASTER_KEY_PATH,
                "backup_path": self.KEY_BACKUP_PATH
            }

    def get_postgresql_config(self) -> Dict[str, Any]:
        """
        Get PostgreSQL-specific encryption configuration.

        Returns:
            Dictionary with PostgreSQL settings
        """
        return {
            "jsonb_encryption": self.POSTGRES_JSONB_ENCRYPTION,
            "index_compatibility": self.POSTGRES_INDEX_COMPATIBILITY,
            "database_type": self.DATABASE_TYPE
        }
    
    def get_performance_config(self) -> Dict[str, Any]:
        """
        Get performance-related configuration.
        
        Returns:
            Dictionary with performance settings
        """
        return {
            "key_cache_ttl": self.KEY_CACHE_TTL_SECONDS,
            "key_cache_max_size": self.KEY_CACHE_MAX_SIZE,
            "key_derivation_iterations": self.KEY_DERIVATION_ITERATIONS
        }

    def get_compliance_config(self) -> Dict[str, Any]:
        """
        Get compliance-related configuration.

        Returns:
            Dictionary with compliance settings
        """
        return {
            "fips_mode": self.FIPS_MODE_ENABLED,
            "gdpr_compliance": self.GDPR_COMPLIANCE_ENABLED,
            "sox_compliance": self.SOX_COMPLIANCE_ENABLED,
            "audit_logging": self.AUDIT_LOGGING_ENABLED
        }

    def is_encryption_enabled(self) -> bool:
        """
        Check if encryption is enabled.

        Returns:
            True if encryption is enabled
        """
        return self.ENCRYPTION_ENABLED

    def is_key_rotation_enabled(self) -> bool:
        """
        Check if automatic key rotation is enabled.

        Returns:
            True if key rotation is enabled
        """
        return self.KEY_ROTATION_ENABLED

    def get_supported_algorithms(self) -> List[str]:
        """
        Get list of supported encryption algorithms.

        Returns:
            List of algorithm names
        """
        return [algo.value for algo in EncryptionAlgorithm]

    def get_supported_providers(self) -> List[str]:
        """
        Get list of supported key vault providers.

        Returns:
            List of provider names
        """
        return [provider.value for provider in KeyVaultProvider]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        config_dict = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            # Don't include sensitive values in dict representation
            if "secret" in field_name.lower() or "token" in field_name.lower() or "key" in field_name.lower():
                config_dict[field_name] = "***REDACTED***" if value else None
            else:
                config_dict[field_name] = value
        return config_dict

    @classmethod
    def from_env(cls) -> 'EncryptionConfig':
        """
        Create configuration from environment variables.

        Returns:
            EncryptionConfig instance
        """
        return cls()

    @classmethod
    def create_test_config(cls) -> 'EncryptionConfig':
        """
        Create configuration for testing purposes.

        Returns:
            EncryptionConfig instance with test settings
        """
        return cls(
            ENCRYPTION_ENABLED=True,
            KEY_VAULT_PROVIDER=KeyVaultProvider.LOCAL.value,
            MASTER_KEY_PATH="/tmp/test_master.key",
            KEY_BACKUP_PATH="/tmp/test_backups",
            KEY_CACHE_TTL_SECONDS=60,
            KEY_DERIVATION_ITERATIONS=10000,
            ENCRYPTION_MONITORING_ENABLED=False,
            AUDIT_LOGGING_ENABLED=True
        )


# Global configuration instance
_encryption_config: Optional[EncryptionConfig] = None

def get_encryption_config() -> EncryptionConfig:
    """
    Get global encryption configuration instance.

    Returns:
        EncryptionConfig instance
    """
    global _encryption_config
    if _encryption_config is None:
        _encryption_config = EncryptionConfig.from_env()
    return _encryption_config


def reload_encryption_config() -> EncryptionConfig:
    """
    Reload encryption configuration from environment.

    Returns:
        New EncryptionConfig instance
    """
    global _encryption_config
    _encryption_config = EncryptionConfig.from_env()
    return _encryption_config