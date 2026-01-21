"""
Tests for key vault integrations.

This module tests the external key vault provider integrations
for AWS KMS, Azure Key Vault, and HashiCorp Vault.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from encryption_config import EncryptionConfig
from commercial.integrations.key_vault_factory import KeyVaultFactory, KeyVaultProvider
from commercial.integrations.aws_kms_provider import AWSKMSProvider
from commercial.integrations.azure_keyvault_provider import AzureKeyVaultProvider
from commercial.integrations.hashicorp_vault_provider import HashiCorpVaultProvider
from core.exceptions.encryption_exceptions import EncryptionError, KeyNotFoundError


class TestKeyVaultFactory:
    """Test the key vault factory."""
    
    def test_get_supported_providers(self):
        """Test getting supported providers."""
        providers = KeyVaultFactory.get_supported_providers()
        
        assert isinstance(providers, dict)
        assert KeyVaultProvider.AWS_KMS.value in providers
        assert KeyVaultProvider.AZURE_KEYVAULT.value in providers
        assert KeyVaultProvider.HASHICORP_VAULT.value in providers
    
    def test_validate_provider_config_aws_kms(self):
        """Test AWS KMS configuration validation."""
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="aws_kms",
            AWS_REGION="us-east-1",
            AWS_KMS_MASTER_KEY_ID="test-key-id"
        )
        
        result = KeyVaultFactory.validate_provider_config(config)
        
        assert result['valid'] is True
        assert result['provider'] == 'aws_kms'
        assert len(result['errors']) == 0
    
    def test_validate_provider_config_azure_keyvault(self):
        """Test Azure Key Vault configuration validation."""
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="azure_keyvault",
            AZURE_KEYVAULT_URL="https://test-vault.vault.azure.net/"
        )
        
        result = KeyVaultFactory.validate_provider_config(config)
        
        assert result['valid'] is True
        assert result['provider'] == 'azure_keyvault'
        assert len(result['errors']) == 0
    
    def test_validate_provider_config_hashicorp_vault(self):
        """Test HashiCorp Vault configuration validation."""
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="hashicorp_vault",
            HASHICORP_VAULT_URL="https://vault.example.com",
            HASHICORP_VAULT_TOKEN="test-token"
        )
        
        result = KeyVaultFactory.validate_provider_config(config)
        
        assert result['valid'] is True
        assert result['provider'] == 'hashicorp_vault'
        assert len(result['errors']) == 0
    
    def test_validate_provider_config_invalid(self):
        """Test validation with invalid provider."""
        config = EncryptionConfig(KEY_VAULT_PROVIDER="invalid_provider")
        
        result = KeyVaultFactory.validate_provider_config(config)
        
        assert result['valid'] is False
        assert len(result['errors']) > 0


class TestAWSKMSProvider:
    """Test AWS KMS provider."""
    
    @patch('api.integrations.aws_kms_provider.boto3')
    def test_initialization(self, mock_boto3):
        """Test AWS KMS provider initialization."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="aws_kms",
            AWS_REGION="us-east-1",
            AWS_KMS_MASTER_KEY_ID="test-key-id"
        )
        
        provider = AWSKMSProvider(config)
        
        assert provider.region == "us-east-1"
        assert provider.master_key_id == "test-key-id"
        mock_boto3.client.assert_called_once()
    
    @patch('api.integrations.aws_kms_provider.boto3')
    def test_generate_data_key(self, mock_boto3):
        """Test data key generation."""
        mock_client = Mock()
        mock_client.generate_data_key.return_value = {
            'Plaintext': b'test-plaintext-key',
            'CiphertextBlob': b'test-encrypted-key',
            'KeyId': 'test-key-id'
        }
        mock_boto3.client.return_value = mock_client
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="aws_kms",
            AWS_REGION="us-east-1",
            AWS_KMS_MASTER_KEY_ID="test-key-id"
        )
        
        provider = AWSKMSProvider(config)
        result = provider.generate_data_key(tenant_id=1)
        
        assert 'plaintext_key' in result
        assert 'encrypted_key' in result
        assert 'key_id' in result
        mock_client.generate_data_key.assert_called_once()
    
    @patch('api.integrations.aws_kms_provider.boto3')
    def test_health_check(self, mock_boto3):
        """Test health check."""
        mock_client = Mock()
        mock_client.describe_key.return_value = {
            'KeyMetadata': {'KeyState': 'Enabled'}
        }
        mock_boto3.client.return_value = mock_client
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="aws_kms",
            AWS_REGION="us-east-1",
            AWS_KMS_MASTER_KEY_ID="test-key-id"
        )
        
        provider = AWSKMSProvider(config)
        health = provider.health_check()
        
        assert health['provider'] == 'aws_kms'
        assert health['status'] == 'healthy'
        assert health['key_state'] == 'Enabled'


class TestAzureKeyVaultProvider:
    """Test Azure Key Vault provider."""
    
    @patch('api.integrations.azure_keyvault_provider.KeyClient')
    @patch('api.integrations.azure_keyvault_provider.SecretClient')
    @patch('api.integrations.azure_keyvault_provider.DefaultAzureCredential')
    def test_initialization(self, mock_credential, mock_secret_client, mock_key_client):
        """Test Azure Key Vault provider initialization."""
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="azure_keyvault",
            AZURE_KEYVAULT_URL="https://test-vault.vault.azure.net/"
        )
        
        provider = AzureKeyVaultProvider(config)
        
        assert provider.vault_url == "https://test-vault.vault.azure.net/"
        mock_credential.assert_called_once()
        mock_key_client.assert_called_once()
        mock_secret_client.assert_called_once()
    
    @patch('api.integrations.azure_keyvault_provider.KeyClient')
    @patch('api.integrations.azure_keyvault_provider.SecretClient')
    @patch('api.integrations.azure_keyvault_provider.DefaultAzureCredential')
    def test_generate_data_key(self, mock_credential, mock_secret_client, mock_key_client):
        """Test data key generation."""
        mock_secret = Mock()
        mock_secret.id = "https://test-vault.vault.azure.net/secrets/tenant-1-data-key/version"
        mock_secret.name = "tenant-1-data-key"
        mock_secret.properties.version = "version1"
        
        mock_secret_client_instance = Mock()
        mock_secret_client_instance.set_secret.return_value = mock_secret
        mock_secret_client.return_value = mock_secret_client_instance
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="azure_keyvault",
            AZURE_KEYVAULT_URL="https://test-vault.vault.azure.net/"
        )
        
        provider = AzureKeyVaultProvider(config)
        result = provider.generate_data_key(tenant_id=1)
        
        assert 'plaintext_key' in result
        assert 'encrypted_key' in result
        assert 'key_id' in result
        assert 'version' in result
        mock_secret_client_instance.set_secret.assert_called_once()


class TestHashiCorpVaultProvider:
    """Test HashiCorp Vault provider."""
    
    @patch('api.integrations.hashicorp_vault_provider.hvac')
    def test_initialization(self, mock_hvac):
        """Test HashiCorp Vault provider initialization."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="hashicorp_vault",
            HASHICORP_VAULT_URL="https://vault.example.com",
            HASHICORP_VAULT_TOKEN="test-token"
        )
        
        provider = HashiCorpVaultProvider(config)
        
        assert provider.vault_url == "https://vault.example.com"
        assert provider.vault_token == "test-token"
        mock_hvac.Client.assert_called_once()
        mock_client.is_authenticated.assert_called_once()
    
    @patch('api.integrations.hashicorp_vault_provider.hvac')
    def test_health_check(self, mock_hvac):
        """Test health check."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.sys.read_seal_status.return_value = {
            'sealed': False,
            'version': '1.15.0'
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            'data': {
                'secret/': {},
                'transit/': {}
            }
        }
        mock_hvac.Client.return_value = mock_client
        
        config = EncryptionConfig(
            KEY_VAULT_PROVIDER="hashicorp_vault",
            HASHICORP_VAULT_URL="https://vault.example.com",
            HASHICORP_VAULT_TOKEN="test-token"
        )
        
        provider = HashiCorpVaultProvider(config)
        health = provider.health_check()
        
        assert health['provider'] == 'hashicorp_vault'
        assert health['status'] == 'healthy'
        assert health['sealed'] is False
        assert health['engines']['kv_available'] is True
        assert health['engines']['transit_available'] is True


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return EncryptionConfig(
        KEY_VAULT_PROVIDER="local",
        ENCRYPTION_ENABLED=True
    )


def test_key_vault_factory_unsupported_provider():
    """Test factory with unsupported provider."""
    config = EncryptionConfig(KEY_VAULT_PROVIDER="unsupported")
    
    with pytest.raises(EncryptionError, match="Unsupported key vault provider"):
        KeyVaultFactory.create_provider(config)


def test_key_vault_factory_local_provider():
    """Test factory with local provider."""
    config = EncryptionConfig(KEY_VAULT_PROVIDER="local")
    
    with pytest.raises(EncryptionError, match="Local provider should be handled"):
        KeyVaultFactory.create_provider(config)