"""
AI configuration-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListAIConfigsArgs(BaseModel):
    pass  # No arguments needed for listing AI configs


class CreateAIConfigArgs(BaseModel):
    provider_name: str = Field(description="AI provider name (openai, anthropic, ollama, google, custom)")
    provider_url: Optional[str] = Field(default=None, description="Provider URL (for custom providers)")
    api_key: Optional[str] = Field(default=None, description="API key for the provider")
    model_name: str = Field(description="Model name to use")
    is_active: bool = Field(default=True, description="Whether the config is active")
    is_default: bool = Field(default=False, description="Whether this is the default config")
    ocr_enabled: bool = Field(default=False, description="Whether OCR is enabled for this config")
    max_tokens: int = Field(default=4096, description="Maximum tokens for requests")
    temperature: float = Field(default=0.1, description="Temperature for AI responses")


class UpdateAIConfigArgs(BaseModel):
    config_id: int = Field(description="ID of the AI config to update")
    provider_name: Optional[str] = Field(default=None, description="AI provider name")
    provider_url: Optional[str] = Field(default=None, description="Provider URL")
    api_key: Optional[str] = Field(default=None, description="API key")
    model_name: Optional[str] = Field(default=None, description="Model name")
    is_active: Optional[bool] = Field(default=None, description="Whether active")
    is_default: Optional[bool] = Field(default=None, description="Whether default")
    ocr_enabled: Optional[bool] = Field(default=None, description="OCR enabled")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")
    temperature: Optional[float] = Field(default=None, description="Temperature")


class TestAIConfigArgs(BaseModel):
    config_id: int = Field(description="ID of the AI config to test")
    custom_prompt: Optional[str] = Field(default=None, description="Custom test prompt")
    test_text: Optional[str] = Field(default=None, description="Test text for processing")


class GetAIStatusArgs(BaseModel):
    pass  # No arguments needed


class ProcessPDFUploadArgs(BaseModel):
    file_path: str = Field(description="Path to the PDF file to upload")
    filename: Optional[str] = Field(default=None, description="Override filename")


class AIToolsMixin:
    # AI Configuration Tools
    async def list_ai_configs(self) -> Dict[str, Any]:
        """List all AI configurations"""
        try:
            response = await self.api_client.list_ai_configs()

            # Extract items from paginated response
            configs = self._extract_items_from_response(response, ["items", "data", "configs"])

            return {
                "success": True,
                "data": configs,
                "count": len(configs),
                "message": f"Found {len(configs)} AI configurations"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list AI configs: {e}"}

    async def create_ai_config(
        self,
        provider_name: str,
        model_name: str,
        provider_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = False,
        ocr_enabled: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Create a new AI configuration"""
        try:
            config_data = {
                "provider_name": provider_name,
                "model_name": model_name,
                "is_active": is_active,
                "is_default": is_default,
                "ocr_enabled": ocr_enabled,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            if provider_url:
                config_data["provider_url"] = provider_url
            if api_key:
                config_data["api_key"] = api_key

            config = await self.api_client.create_ai_config(config_data)
            return {
                "success": True,
                "data": config,
                "message": "AI configuration created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create AI config: {e}"}

    async def update_ai_config(
        self,
        config_id: int,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        ocr_enabled: Optional[bool] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update an AI configuration"""
        try:
            update_data = {}
            if provider_name is not None:
                update_data["provider_name"] = provider_name
            if model_name is not None:
                update_data["model_name"] = model_name
            if provider_url is not None:
                update_data["provider_url"] = provider_url
            if api_key is not None:
                update_data["api_key"] = api_key
            if is_active is not None:
                update_data["is_active"] = is_active
            if is_default is not None:
                update_data["is_default"] = is_default
            if ocr_enabled is not None:
                update_data["ocr_enabled"] = ocr_enabled
            if max_tokens is not None:
                update_data["max_tokens"] = max_tokens
            if temperature is not None:
                update_data["temperature"] = temperature

            config = await self.api_client.update_ai_config(config_id, update_data)
            return {
                "success": True,
                "data": config,
                "message": "AI configuration updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update AI config: {e}"}

    async def test_ai_config(self, config_id: int, custom_prompt: Optional[str] = None, test_text: Optional[str] = None) -> Dict[str, Any]:
        """Test an AI configuration"""
        try:
            test_data = {}
            if custom_prompt:
                test_data["custom_prompt"] = custom_prompt
            if test_text:
                test_data["test_text"] = test_text

            result = await self.api_client.test_ai_config(config_id, test_data)
            return {
                "success": True,
                "data": result,
                "message": "AI configuration test completed"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to test AI config: {e}"}

    # PDF Processing Tools
    async def get_ai_status(self) -> Dict[str, Any]:
        """Get AI status for PDF processing"""
        try:
            status = await self.api_client.get_ai_status()
            return {
                "success": True,
                "data": status,
                "message": "AI status retrieved"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get AI status: {e}"}

    async def process_pdf_upload(self, file_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """Upload and process a PDF file"""
        try:
            result = await self.api_client.process_pdf_upload(file_path=file_path, filename=filename)
            return {
                "success": True,
                "data": result,
                "message": "PDF uploaded and processing started"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to process PDF upload: {e}"}
