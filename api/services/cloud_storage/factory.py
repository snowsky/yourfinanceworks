"""
Storage Provider Factory for instantiating and managing cloud storage providers.

This module provides a factory pattern implementation for creating storage providers
with automatic health checking, circuit breaker integration, and provider discovery.
"""

import logging
from typing import Dict, Optional, Type, List, Any
from datetime import datetime, timedelta

from .provider import CloudStorageProvider, StorageProvider, StorageConfig, HealthCheckResult
from integrations.circuit_breaker import CloudProviderCircuitBreaker
from settings.cloud_storage_config import CloudStorageConfig

logger = logging.getLogger(__name__)


class ProviderRegistrationError(Exception):
    """Exception raised when provider registration fails."""
    pass


class ProviderInstantiationError(Exception):
    """Exception raised when provider instantiation fails."""
    pass


class StorageProviderFactory:
    """
    Factory for creating and managing cloud storage providers.
    
    Handles provider registration, instantiation, health checking,
    and circuit breaker integration for resilient storage operations.
    """
    
    def __init__(self, config: CloudStorageConfig):
        """
        Initialize the storage provider factory.
        
        Args:
            config: Cloud storage configuration
        """
        self.config = config
        self._providers: Dict[StorageProvider, CloudStorageProvider] = {}
        self._provider_classes: Dict[StorageProvider, Type[CloudStorageProvider]] = {}
        self._circuit_breakers: Dict[StorageProvider, CloudProviderCircuitBreaker] = {}
        self._health_check_cache: Dict[StorageProvider, HealthCheckResult] = {}
        self._last_health_check: Dict[StorageProvider, datetime] = {}
        
        # Initialize circuit breakers for each provider type
        self._init_circuit_breakers()
        
        # Register built-in providers
        self._register_builtin_providers()
    
    def _init_circuit_breakers(self) -> None:
        """Initialize circuit breakers for all provider types."""
        for provider_type in StorageProvider:
            self._circuit_breakers[provider_type] = CloudProviderCircuitBreaker(
                provider_name=provider_type.value,
                operation_name="storage_operations",
                failure_threshold=3,  # Open after 3 failures
                recovery_timeout=30.0,  # Wait 30 seconds before retry
                success_threshold=2  # Need 2 successes to close
            )
            logger.debug(f"Initialized circuit breaker for {provider_type.value}")
    
    def _register_builtin_providers(self) -> None:
        """Register built-in storage provider classes."""
        # Import providers dynamically to avoid circular imports
        try:
            from .local_storage_provider import LocalStorageProvider
            self.register_provider(StorageProvider.LOCAL, LocalStorageProvider)
        except ImportError as e:
            logger.warning(f"Failed to register local storage provider: {e}")
        
        try:
            from .aws_s3_provider import AWSS3Provider
            self.register_provider(StorageProvider.AWS_S3, AWSS3Provider)
        except ImportError as e:
            logger.debug(f"AWS S3 provider not available: {e}")
        
        try:
            from .azure_blob_provider import AzureBlobProvider
            self.register_provider(StorageProvider.AZURE_BLOB, AzureBlobProvider)
        except ImportError as e:
            logger.debug(f"Azure Blob provider not available: {e}")
        
        try:
            from .gcp_storage_provider import GCPStorageProvider
            self.register_provider(StorageProvider.GCP_STORAGE, GCPStorageProvider)
        except ImportError as e:
            logger.debug(f"GCP Storage provider not available: {e}")
    
    def register_provider(
        self, 
        provider_type: StorageProvider, 
        provider_class: Type[CloudStorageProvider]
    ) -> None:
        """
        Register a storage provider class.
        
        Args:
            provider_type: The provider type enum
            provider_class: The provider class to register
            
        Raises:
            ProviderRegistrationError: If registration fails
        """
        if not issubclass(provider_class, CloudStorageProvider):
            raise ProviderRegistrationError(
                f"Provider class must inherit from CloudStorageProvider"
            )
        
        self._provider_classes[provider_type] = provider_class
        logger.info(f"Registered provider class for {provider_type.value}")
    
    def get_provider(self, provider_type: StorageProvider) -> Optional[CloudStorageProvider]:
        """
        Get or create a storage provider instance.
        
        Args:
            provider_type: The type of provider to get
            
        Returns:
            Provider instance or None if not available/configured
        """
        # Check if provider_type is valid
        if provider_type is None:
            logger.warning("Provider type is None")
            return None
            
        # Return cached instance if available
        if provider_type in self._providers:
            return self._providers[provider_type]
        
        # Check if provider class is registered
        if provider_type not in self._provider_classes:
            provider_name = provider_type.value if provider_type else "None"
            logger.warning(f"No provider class registered for {provider_name}")
            return None
        
        # Get provider configuration
        provider_config = self._get_provider_config(provider_type)
        if not provider_config or not provider_config.enabled:
            logger.debug(f"Provider {provider_type.value} not configured or disabled")
            return None
        
        # Create provider instance
        try:
            provider_class = self._provider_classes[provider_type]
            provider = provider_class(provider_config)
            self._providers[provider_type] = provider
            logger.info(f"Created provider instance for {provider_type.value}")
            return provider
        except Exception as e:
            logger.error(f"Failed to create provider {provider_type.value}: {e}")
            raise ProviderInstantiationError(f"Failed to create {provider_type.value} provider: {e}")
    
    def _get_provider_config(self, provider_type: StorageProvider) -> Optional[StorageConfig]:
        """
        Get configuration for a specific provider.
        
        Args:
            provider_type: The provider type
            
        Returns:
            StorageConfig or None if not configured
        """
        # Convert our StorageProvider enum to the config's StorageProvider enum
        from settings.cloud_storage_config import StorageProvider as ConfigStorageProvider
        
        try:
            config_provider_type = ConfigStorageProvider(provider_type.value)
            config_dict = self.config.get_provider_config(config_provider_type)
            
            # Check if provider is enabled
            enabled = True
            if provider_type == StorageProvider.AWS_S3:
                enabled = self.config.AWS_S3_ENABLED
            elif provider_type == StorageProvider.AZURE_BLOB:
                enabled = self.config.AZURE_BLOB_ENABLED
            elif provider_type == StorageProvider.GCP_STORAGE:
                enabled = self.config.GCP_STORAGE_ENABLED
            elif provider_type == StorageProvider.LOCAL:
                enabled = True  # Local storage is always enabled
            
            if not enabled:
                return None
            
            # Check if this is the primary provider
            is_primary = (self.config.get_primary_provider().value == provider_type.value)
            
            return StorageConfig(
                provider=provider_type,
                enabled=enabled,
                is_primary=is_primary,
                config=config_dict
            )
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get config for provider {provider_type.value}: {e}")
            return None
    
    def get_primary_provider(self) -> Optional[CloudStorageProvider]:
        """
        Get the primary storage provider.
        
        Returns:
            Primary provider instance or None if not configured
        """
        # Get primary provider from configuration
        try:
            primary_provider = self.config.get_primary_provider()
            provider_type = StorageProvider(primary_provider.value)
            return self.get_provider(provider_type)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get primary provider: {e}")
            return None
    
    def get_available_providers(self) -> List[CloudStorageProvider]:
        """
        Get all available and healthy storage providers.
        
        Returns:
            List of available provider instances
        """
        available_providers = []
        
        for provider_type in StorageProvider:
            provider = self.get_provider(provider_type)
            if provider and self.is_provider_healthy(provider_type):
                available_providers.append(provider)
        
        return available_providers
    
    def get_fallback_providers(self) -> List[CloudStorageProvider]:
        """
        Get fallback providers in order of preference.
        
        Returns:
            List of fallback provider instances
        """
        fallback_providers = []
        
        # Always include local storage as ultimate fallback
        local_provider = self.get_provider(StorageProvider.LOCAL)
        if local_provider:
            fallback_providers.append(local_provider)
        
        # Add other healthy providers
        for provider_type in [StorageProvider.AWS_S3, StorageProvider.AZURE_BLOB, StorageProvider.GCP_STORAGE]:
            provider = self.get_provider(provider_type)
            if provider and self.is_provider_healthy(provider_type):
                fallback_providers.append(provider)
        
        return fallback_providers
    
    async def health_check_provider(
        self, 
        provider_type: StorageProvider,
        force_check: bool = False
    ) -> Optional[HealthCheckResult]:
        """
        Perform health check on a specific provider.
        
        Args:
            provider_type: The provider to check
            force_check: Force check even if recently checked
            
        Returns:
            HealthCheckResult or None if provider not available
        """
        # Check if we need to perform health check
        if not force_check and self._should_skip_health_check(provider_type):
            return self._health_check_cache.get(provider_type)
        
        provider = self.get_provider(provider_type)
        if not provider:
            return None
        
        try:
            # Use circuit breaker for health check
            circuit_breaker = self._circuit_breakers[provider_type]
            health_result = await circuit_breaker.call(provider.health_check)
            
            # Cache the result
            self._health_check_cache[provider_type] = health_result
            self._last_health_check[provider_type] = datetime.now()
            
            logger.debug(f"Health check for {provider_type.value}: {health_result.healthy}")
            return health_result
            
        except Exception as e:
            logger.warning(f"Health check failed for {provider_type.value}: {e}")
            # Create failed health check result
            failed_result = HealthCheckResult(
                provider=provider_type,
                healthy=False,
                error_message=str(e),
                last_check=datetime.now()
            )
            self._health_check_cache[provider_type] = failed_result
            self._last_health_check[provider_type] = datetime.now()
            return failed_result
    
    def _should_skip_health_check(self, provider_type: StorageProvider) -> bool:
        """
        Check if health check should be skipped based on cache.
        
        Args:
            provider_type: The provider type
            
        Returns:
            True if health check should be skipped
        """
        if provider_type not in self._last_health_check:
            return False
        
        last_check = self._last_health_check[provider_type]
        check_interval = timedelta(seconds=300)  # 5 minutes default
        
        return datetime.now() - last_check < check_interval
    
    def is_provider_healthy(self, provider_type: StorageProvider) -> bool:
        """
        Check if a provider is currently healthy.
        
        Args:
            provider_type: The provider type
            
        Returns:
            True if provider is healthy
        """
        # Check circuit breaker state
        circuit_breaker = self._circuit_breakers[provider_type]
        circuit_status = circuit_breaker.get_health_status()
        
        if circuit_status['state'] == 'OPEN':
            return False
        
        # Check cached health result
        if provider_type in self._health_check_cache:
            health_result = self._health_check_cache[provider_type]
            return health_result.healthy
        
        return True  # Assume healthy if no information available
    
    def get_circuit_breaker(self, provider_type: StorageProvider) -> CloudProviderCircuitBreaker:
        """
        Get circuit breaker for a provider.
        
        Args:
            provider_type: The provider type
            
        Returns:
            Circuit breaker instance
        """
        return self._circuit_breakers[provider_type]
    
    def reset_circuit_breaker(self, provider_type: StorageProvider) -> None:
        """
        Manually reset circuit breaker for a provider.
        
        Args:
            provider_type: The provider type
        """
        circuit_breaker = self._circuit_breakers[provider_type]
        circuit_breaker.reset()
        logger.info(f"Reset circuit breaker for {provider_type.value}")
    
    async def health_check_all_providers(self, force_check: bool = False) -> Dict[StorageProvider, HealthCheckResult]:
        """
        Perform health check on all configured providers.
        
        Args:
            force_check: Force check even if recently checked
            
        Returns:
            Dictionary mapping provider types to health results
        """
        health_results = {}
        
        for provider_type in StorageProvider:
            result = await self.health_check_provider(provider_type, force_check)
            if result:
                health_results[provider_type] = result
        
        return health_results
    
    def get_provider_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all providers.
        
        Returns:
            Dictionary with provider status information
        """
        status = {
            'providers': {},
            'circuit_breakers': {},
            'primary_provider': None,
            'available_providers': [],
            'last_updated': datetime.now().isoformat()
        }
        
        # Get primary provider info
        primary_provider = self.get_primary_provider()
        if primary_provider:
            status['primary_provider'] = primary_provider.provider_type.value
        
        # Get provider and circuit breaker status
        for provider_type in StorageProvider:
            provider_name = provider_type.value
            
            # Provider status
            provider = self.get_provider(provider_type)
            if provider:
                status['providers'][provider_name] = provider.get_provider_info()
                if self.is_provider_healthy(provider_type):
                    status['available_providers'].append(provider_name)
            
            # Circuit breaker status
            circuit_breaker = self._circuit_breakers[provider_type]
            status['circuit_breakers'][provider_name] = circuit_breaker.get_health_status()
        
        return status
    
    def cleanup(self) -> None:
        """Clean up resources and close provider connections."""
        logger.info("Cleaning up storage provider factory")
        
        # Clear provider instances (they should handle their own cleanup)
        self._providers.clear()
        self._health_check_cache.clear()
        self._last_health_check.clear()
        
        logger.info("Storage provider factory cleanup completed")