from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class AIConfigBase(BaseModel):
    provider_name: str
    provider_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str
    is_active: bool = True
    is_default: bool = False
    tested: bool = False

    # OCR specific settings
    ocr_enabled: bool = False
    max_tokens: int = 4096
    temperature: float = 0.1

class AIConfigCreate(AIConfigBase):
    pass

class AIConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    provider_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    tested: Optional[bool] = None
    ocr_enabled: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class AIConfig(AIConfigBase):
    id: int
    tenant_id: Optional[int] = None
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AIConfigTestRequest(BaseModel):
    """AI configuration test request schema."""
    custom_prompt: Optional[str] = None
    test_text: Optional[str] = None

class AIConfigTestResponse(BaseModel):
    """AI configuration test response schema."""
    success: bool
    message: str
    response_time_ms: Optional[float] = None
    response: Optional[str] = None
    error: Optional[str] = None

class AIConfigUsage(BaseModel):
    """AI configuration usage statistics."""
    config_id: int
    usage_count: int
    last_used_at: Optional[datetime] = None
    total_tokens_used: Optional[int] = None
    total_cost: Optional[float] = None

class AIProviderInfo(BaseModel):
    """Information about supported AI providers."""
    name: str
    display_name: str
    description: str
    website: Optional[str] = None
    models: List[str]
    supports_ocr: bool = False
    requires_api_key: bool = True
    default_model: str
    default_max_tokens: int = 4096

# Predefined provider information
SUPPORTED_PROVIDERS = {
    "openai": AIProviderInfo(
        name="openai",
        display_name="OpenAI",
        description="Industry-leading AI models with excellent OCR capabilities",
        website="https://openai.com",
        models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
        supports_ocr=True,
        requires_api_key=True,
        default_model="gpt-4",
        default_max_tokens=4096
    ),
    "openrouter": AIProviderInfo(
        name="openrouter",
        display_name="OpenRouter",
        description="Access 100+ AI models through a single API with competitive pricing",
        website="https://openrouter.ai",
        models=["openai/gpt-4", "openai/gpt-4-turbo", "anthropic/claude-3-sonnet", "anthropic/claude-3-opus", "meta-llama/llama-3.1-8b-instruct"],
        supports_ocr=True,
        requires_api_key=True,
        default_model="openai/gpt-4",
        default_max_tokens=4096
    ),
    "anthropic": AIProviderInfo(
        name="anthropic",
        display_name="Anthropic",
        description="Claude AI models with strong reasoning and OCR capabilities",
        website="https://anthropic.com",
        models=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
        supports_ocr=True,
        requires_api_key=True,
        default_model="claude-3-sonnet-20240229",
        default_max_tokens=4096
    ),
    "ollama": AIProviderInfo(
        name="ollama",
        display_name="Ollama (Local)",
        description="Run AI models locally with Ollama for privacy and offline use",
        website="https://ollama.ai",
        models=["llama3.2-vision:11b", "llama3.2:3b", "mistral:7b", "codellama:7b"],
        supports_ocr=True,
        requires_api_key=False,
        default_model="llama3.2-vision:11b",
        default_max_tokens=4096
    ),
    "google": AIProviderInfo(
        name="google",
        display_name="Google AI",
        description="Google's AI models including Gemini with OCR capabilities",
        website="https://ai.google",
        models=["gemini-pro", "gemini-pro-vision"],
        supports_ocr=True,
        requires_api_key=True,
        default_model="gemini-pro",
        default_max_tokens=4096
    ),
    "custom": AIProviderInfo(
        name="custom",
        display_name="Custom Provider",
        description="Connect to any compatible AI API endpoint",
        models=["custom-model"],
        supports_ocr=True,
        requires_api_key=True,
        default_model="custom-model",
        default_max_tokens=4096
    )
}