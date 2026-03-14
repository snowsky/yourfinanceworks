"""
Configuration settings for the Invoice Application
"""
import os
from typing import Optional


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable '{name}' is not set")
    return value

# Application constants
APP_NAME = "YourFinanceWORKS"


class Config:
    """Main configuration for the invoice application"""

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./invoice_app.db")

    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # UI settings
    UI_BASE_URL: str = os.getenv("UI_BASE_URL", "http://localhost:8080")

    # Tax Service Integration settings
    TAX_SERVICE_ENABLED: bool = os.getenv("TAX_SERVICE_ENABLED", "false").lower() == "true"
    TAX_SERVICE_BASE_URL: str = os.getenv("TAX_SERVICE_BASE_URL", "http://localhost:8000")
    TAX_SERVICE_API_KEY: str = os.getenv("TAX_SERVICE_API_KEY", "")
    TAX_SERVICE_TIMEOUT: int = int(os.getenv("TAX_SERVICE_TIMEOUT", "30"))
    TAX_SERVICE_RETRY_ATTEMPTS: int = int(os.getenv("TAX_SERVICE_RETRY_ATTEMPTS", "3"))

    # Email settings (for notifications)
    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER")
    SMTP_PORT: Optional[int] = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM", "noreply@invoiceapp.com")
    EMAIL_FROM_NAME: Optional[str] = os.getenv("EMAIL_FROM_NAME", APP_NAME)

    # File upload settings
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default
    UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", "./attachments")

    # Security settings
    SECRET_KEY: str = _require_env("SECRET_KEY")
    JWT_SECRET_KEY: str = _require_env("JWT_SECRET_KEY")

    # Tenant settings
    MULTI_TENANT: bool = os.getenv("MULTI_TENANT", "true").lower() == "true"

    # Cache settings
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
    CACHE_MAX_MEMORY_SIZE: int = int(os.getenv("CACHE_MAX_MEMORY_SIZE", "100"))

    # Performance settings
    QUERY_OPTIMIZATION_ENABLED: bool = os.getenv("QUERY_OPTIMIZATION_ENABLED", "true").lower() == "true"
    SLOW_QUERY_THRESHOLD: float = float(os.getenv("SLOW_QUERY_THRESHOLD", "5.0"))
    MAX_RESULT_SIZE: int = int(os.getenv("MAX_RESULT_SIZE", "50000"))
    PROGRESS_TRACKING_ENABLED: bool = os.getenv("PROGRESS_TRACKING_ENABLED", "true").lower() == "true"

    @property
    def tax_service_config(self):
        """Get tax service configuration as dict"""
        from commercial.integrations.tax.service import TaxServiceConfig
        return TaxServiceConfig(
            base_url=self.TAX_SERVICE_BASE_URL,
            api_key=self.TAX_SERVICE_API_KEY,
            timeout=self.TAX_SERVICE_TIMEOUT,
            retry_attempts=self.TAX_SERVICE_RETRY_ATTEMPTS,
            enabled=self.TAX_SERVICE_ENABLED
        )


# Global config instance
config = Config()

def get_settings() -> Config:
    """Get the global configuration instance"""
    return config
