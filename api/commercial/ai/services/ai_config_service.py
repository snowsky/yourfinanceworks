"""
Unified AI Configuration Service

This service provides a centralized way to manage AI configurations across all components
with intelligent fallback to environment variables when database configurations are unavailable.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from core.models.models_per_tenant import AIConfig as AIConfigModel, Settings

logger = logging.getLogger(__name__)


class AIConfigService:
    """
    Centralized service for managing AI configurations across all application components.

    Provides intelligent fallback from database configurations to environment variables
    with support for multiple AI providers and use cases.
    """

    @staticmethod
    def get_model_parameters(model_name: str, **custom_params) -> Dict[str, Any]:
        """
        Get standardized model parameters based on the model name.
        Handles max_completion_tokens vs max_tokens and temperature restrictions.
        """
        params = custom_params.copy()
        model_lower = model_name.lower()

        # 1. Handle max tokens parameter name
        max_tokens = params.pop("max_tokens", None)
        max_completion_tokens = params.pop("max_completion_tokens", None)

        # Use whatever was provided or default to 4000
        tokens = max_completion_tokens or max_tokens or 4000

        # Newer OpenAI models prefer max_completion_tokens
        if "gpt-4o" in model_lower or "gpt-5" in model_lower or model_lower.startswith("o1") or model_lower.startswith("o3"):
            params["max_completion_tokens"] = tokens
        else:
            params["max_tokens"] = tokens

        # 2. Handle temperature restrictions
        # Reasoning models often restrict temperature to 1.0 or don't support it
        if model_lower.startswith("o1") or model_lower.startswith("o3") or "gpt-5" in model_lower:
            # Reasoning models usually handle their own temperature/sampling
            if "temperature" in params:
                del params["temperature"]
        elif "temperature" not in params:
            # Default temperature for non-reasoning models
            params["temperature"] = 0.7

        return params

    # Environment variable mappings for different components
    ENV_VAR_MAPPINGS = {
        # OCR/Expense processing
        "ocr": {
            "api_base": ["LLM_API_BASE", "OLLAMA_API_BASE"],
            "api_key": ["LLM_API_KEY"],
            "model": ["LLM_MODEL_EXPENSES", "OLLAMA_MODEL"],
        },
        # AI Chat
        "chat": {
            "provider": ["AI_PROVIDER"],
            "model": ["AI_MODEL"],
            "api_key": ["AI_API_KEY"],
            "api_url": ["AI_API_URL"],
        },
        # Bank statement processing
        "bank_statement": {
            "api_base": ["LLM_API_BASE_BANK", "LLM_API_BASE", "OLLAMA_API_BASE"],
            "api_key": ["LLM_API_KEY_BANK", "LLM_API_KEY"],
            "model": ["LLM_MODEL_BANK_STATEMENTS", "LLM_MODEL_EXPENSES", "OLLAMA_MODEL"],
        },
        # Invoice processing
        "invoice": {
            "api_base": ["LLM_API_BASE_INVOICE", "LLM_API_BASE", "OLLAMA_API_BASE"],
            "api_key": ["LLM_API_KEY_INVOICE", "LLM_API_KEY"],
            "model": ["LLM_MODEL_INVOICES", "LLM_MODEL_EXPENSES", "OLLAMA_MODEL"],
        },
        # Reviewer processing
        "reviewer": {
            "api_base": ["LLM_API_BASE_REVIEWER", "LLM_API_BASE", "OLLAMA_API_BASE"],
            "api_key": ["LLM_API_KEY_REVIEWER", "LLM_API_KEY"],
            "model": ["LLM_MODEL_REVIEWER", "LLM_MODEL_EXPENSES", "OLLAMA_MODEL"],
        },
    }

    # Default models for each provider
    DEFAULT_MODELS = {
        "ollama": "llama3.2-vision:11b",
        "openai": "gpt-4-vision-preview",
        "anthropic": "claude-3-haiku",
        "google": "gemini-pro-vision",
        "openrouter": "openai/gpt-4-vision-preview",
    }

    # Default API bases for each provider
    DEFAULT_API_BASES = {
        "ollama": os.environ.get("OLLAMA_API_BASE") or os.environ.get("LLM_API_BASE") or "http://localhost:11434",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "openrouter": "https://openrouter.ai/api/v1",
    }

    @classmethod
    def get_ai_config(
        cls, 
        db: Session, 
        component: str = "ocr", 
        require_ocr: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get AI configuration with intelligent fallback from database to environment variables.

        Args:
            db: Database session
            component: Component requesting config ("ocr", "chat", "bank_statement", "invoice")
            require_ocr: Whether OCR capability is required

        Returns:
            AI configuration dictionary or None if no configuration available
        """
        # First, try to get configuration from database
        db_config = None
        try:
            db_config = cls._get_database_config(db, require_ocr, component)
            if db_config:
                # 1. Apply provider-specific default URLs if missing from DB
                provider_name = db_config.get("provider_name")
                db_url = db_config.get("provider_url")

                if provider_name and (not db_url or "localhost" in db_url or "127.0.0.1" in db_url):
                    default_url = cls.DEFAULT_API_BASES.get(provider_name.lower())
                    if default_url:
                        db_config["provider_url"] = default_url
                        logger.debug(f"Applied default URL for {provider_name}: {default_url}")

                # 2. Only fallback missing fields to environment variables IF the provider names match
                # This prevents Ollama env URLs from leaking into OpenAI DB configs
                env_config = cls._get_env_config(component)
                if env_config:
                    env_provider = env_config.get("provider_name")

                    if env_provider and provider_name and env_provider.lower() == provider_name.lower():
                        # Priority: Provider URL / API Base
                        # If DB URL is still local or empty after default check, use environment if it matches
                        db_url = db_config.get("provider_url")
                        env_url = env_config.get("provider_url")
                        if env_url and (not db_url or "localhost" in db_url or "127.0.0.1" in db_url):
                            db_config["provider_url"] = env_url

                        # Other missing fields
                        for key in ["model_name", "api_key"]:
                            if not db_config.get(key) and env_config.get(key):
                                db_config[key] = env_config[key]
                    else:
                        logger.debug(f"Skipping environment fallback as providers do not match: DB={provider_name}, ENV={env_provider}")

                logger.info(f"Using AI config from database for {component}: {db_config['provider_name']}/{db_config['model_name']} at {db_config.get('provider_url')}")
                return db_config
        except Exception as e:
            logger.debug(f"Database AI config fetch failed for {component}: {e}")
            # Continue to env fallback

        # Fallback to environment variables
        try:
            env_config = cls._get_env_config(component)
            if env_config:
                logger.info(f"Using AI config from environment variables for {component}: {env_config['provider_name']}/{env_config['model_name']}")
                return env_config
        except Exception as e:
            logger.error(f"Failed to get AI config from environment variables for {component}: {e}")

        logger.warning(f"No AI configuration available for {component} from database or environment variables")
        return None

    @classmethod
    def _get_database_config(cls, db: Session, require_ocr: bool = False, component: str = "ocr") -> Optional[Dict[str, Any]]:
        """Get AI configuration from database."""
        try:
            # Special handling for reviewer component
            if component == "reviewer":
                setting = db.query(Settings).filter(Settings.key == "reviewer_ai_config").first()
                if setting and setting.value:
                    config_data = setting.value
                    # If specific config is enabled, return it
                    if config_data.get("use_custom_config") and config_data.get("config"):
                        custom_config = config_data.get("config")
                        # Ensure basic fields exist
                        if custom_config.get("provider_name") and custom_config.get("model_name"):
                             custom_config["source"] = "database_reviewer_custom"
                             custom_config["use_for_extraction"] = config_data.get("use_for_extraction", False)
                             # Ensure ocr_enabled is true for reviewer component to allow LLM calls
                             if "ocr_enabled" not in custom_config:
                                 custom_config["ocr_enabled"] = True
                             return custom_config

            # Fallback to default active config for other components or if reviewer uses default
            query = db.query(AIConfigModel).filter(
                AIConfigModel.is_active == True,
                AIConfigModel.tested == True
            )

            if require_ocr:
                query = query.filter(AIConfigModel.ocr_enabled == True)

            ai_row = query.order_by(AIConfigModel.is_default.desc()).first()

            if ai_row:
                return {
                    "provider_name": ai_row.provider_name,
                    "provider_url": ai_row.provider_url,
                    "api_key": ai_row.api_key,
                    "model_name": ai_row.model_name,
                    "ocr_enabled": getattr(ai_row, 'ocr_enabled', False),
                    "source": "database"
                }

            return None

        except Exception as e:
            logger.error(f"Database AI config fetch failed: {e}")
            return None

    @classmethod
    def _get_env_config(cls, component: str) -> Optional[Dict[str, Any]]:
        """Get AI configuration from environment variables for specific component."""
        try:
            mapping = cls.ENV_VAR_MAPPINGS.get(component, cls.ENV_VAR_MAPPINGS["ocr"])
            logger.debug(f"[DEBUG] _get_env_config for component '{component}', mapping keys: {mapping.keys()}")

            # Get environment variables with fallback priority
            env_api_base = cls._get_first_env_var(mapping.get("api_base", []))
            env_api_key = cls._get_first_env_var(mapping.get("api_key", []))
            env_model = cls._get_first_env_var(mapping.get("model", []))
            env_provider = cls._get_first_env_var(mapping.get("provider", []))
            env_api_url = cls._get_first_env_var(mapping.get("api_url", []))

            logger.debug(f"[DEBUG] Environment variables for {component}: api_base={env_api_base}, api_key={bool(env_api_key)}, model={env_model}, provider={env_provider}, api_url={env_api_url}")

            # Use api_url as fallback for api_base
            if not env_api_base and env_api_url:
                env_api_base = env_api_url

            # If no environment variables are set, return None
            if not any([env_api_base, env_api_key, env_model, env_provider]):
                logger.debug(f"No environment variables found for {component}: api_base={env_api_base}, api_key={bool(env_api_key)}, model={env_model}, provider={env_provider}")
                return None

            # Detect provider from environment variables
            provider_name = cls._detect_provider(env_provider, env_api_base, env_api_key, env_model)

            # Set default model if not specified
            if not env_model:
                env_model = cls.DEFAULT_MODELS.get(provider_name, "llama3.2-vision:11b")

            # Set default API base if not specified
            if not env_api_base:
                env_api_base = cls.DEFAULT_API_BASES.get(provider_name)

            logger.debug(f"Created AI config from environment for {component}: provider={provider_name}, model={env_model}, api_base={env_api_base}")

            return {
                "provider_name": provider_name,
                "provider_url": env_api_base,
                "api_key": env_api_key,
                "model_name": env_model,
                "ocr_enabled": True,  # Assume OCR is enabled for env fallback
                "source": "environment"
            }

        except Exception as e:
            logger.error(f"Failed to create AI config from environment variables for {component}: {e}", exc_info=True)
            return None

    @classmethod
    def _get_first_env_var(cls, var_names: List[str]) -> Optional[str]:
        """Get the first available environment variable from a list."""
        for var_name in var_names:
            value = os.getenv(var_name)
            if value:
                return value
        return None

    @classmethod
    def _detect_provider(
        cls, 
        env_provider: Optional[str], 
        env_api_base: Optional[str], 
        env_api_key: Optional[str], 
        env_model: Optional[str]
    ) -> str:
        """Detect AI provider from environment variables."""
        # Explicit provider setting takes precedence
        if env_provider:
            return env_provider.lower()

        # Detect from API base URL
        if env_api_base:
            api_base_lower = env_api_base.lower()
            if "openrouter.ai" in api_base_lower or "openrouter" in api_base_lower:
                return "openrouter"
            elif "api.openai.com" in api_base_lower or "openai" in api_base_lower:
                return "openai"
            elif "anthropic" in api_base_lower:
                return "anthropic"
            elif "google" in api_base_lower or "generativelanguage" in api_base_lower:
                return "google"
            elif "localhost" in api_base_lower or "11434" in api_base_lower:
                return "ollama"

        # Detect from model name patterns
        if env_model:
            model_lower = env_model.lower()
            if "gpt" in model_lower:
                return "openai"
            elif "claude" in model_lower:
                return "anthropic"
            elif "gemini" in model_lower:
                return "google"
            elif "llama" in model_lower or "mistral" in model_lower:
                return "ollama"

        # Default based on available credentials
        if env_api_key:
            return "openai"  # Default to OpenAI if API key present
        else:
            return "ollama"  # Final fallback

    @classmethod
    def get_supported_components(cls) -> List[str]:
        """Get list of supported components."""
        return list(cls.ENV_VAR_MAPPINGS.keys())

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate AI configuration and return validation results.

        Args:
            config: AI configuration dictionary

        Returns:
            Dictionary with validation results
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Check required fields
        required_fields = ["provider_name", "model_name"]
        for field in required_fields:
            if not config.get(field):
                validation["valid"] = False
                validation["errors"].append(f"Missing required field: {field}")

        # Provider-specific validation
        provider = config.get("provider_name", "").lower()

        if provider in ["openai", "anthropic", "google", "openrouter"]:
            if not config.get("api_key"):
                validation["valid"] = False
                validation["errors"].append(f"API key required for {provider}")

        if provider == "ollama":
            if not config.get("provider_url"):
                default_url = os.environ.get("OLLAMA_API_BASE") or os.environ.get("LLM_API_BASE") or "http://localhost:11434"
                validation["warnings"].append(f"No API URL specified for Ollama, using default {default_url}")

        # Model validation
        model_name = config.get("model_name", "")
        if provider == "openrouter" and not ("/" in model_name or "gpt" in model_name.lower()):
            validation["warnings"].append("OpenRouter models typically use format 'provider/model' (e.g., 'openai/gpt-4-vision-preview')")

        return validation

    @classmethod
    def is_review_worker_enabled(cls, db: Session) -> bool:
        """Check if the review worker is enabled for the current tenant."""
        try:
            setting = db.query(Settings).filter(Settings.key == "review_worker_enabled").first()
            return setting.value if setting else False
        except Exception as e:
            logger.error(f"Error checking review_worker_enabled: {e}")
            return False


# Convenience functions for backward compatibility
def get_ai_config_from_env() -> Optional[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return AIConfigService._get_env_config("ocr")


def get_ai_config_for_component(
    db: Session, 
    component: str, 
    require_ocr: bool = False
) -> Optional[Dict[str, Any]]:
    """Get AI configuration for a specific component."""
    return AIConfigService.get_ai_config(db, component, require_ocr)
