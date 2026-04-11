"""Settings, Discount Rules, CRM, Email, Tenant, and AI Configuration tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


# Settings Tools

@mcp.tool()
async def get_settings() -> dict:
    """
    Get tenant settings including company information and invoice settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_settings()


# Discount Rules Tools

@mcp.tool()
async def list_discount_rules() -> dict:
    """
    List all discount rules for the current tenant.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_discount_rules()


@mcp.tool()
async def create_discount_rule(
    name: str,
    discount_type: str,
    discount_value: float,
    min_amount: Optional[float] = None,
    max_discount: Optional[float] = None,
    priority: int = 1,
    is_active: bool = True,
    currency: Optional[str] = None,
) -> dict:
    """
    Create a new discount rule for the tenant.

    Args:
        name: Name of the discount rule
        discount_type: Type of discount (percentage, fixed)
        discount_value: Discount value
        min_amount: Minimum amount for discount to apply (optional)
        max_discount: Maximum discount amount (optional)
        priority: Priority of the rule, higher number = higher priority (default: 1)
        is_active: Whether the rule is active (default: True)
        currency: Currency code for the rule (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    if discount_type not in ["percentage", "fixed"]:
        return {"success": False, "error": "discount_type must be either 'percentage' or 'fixed'"}

    return await server_context.tools.create_discount_rule(
        name=name,
        discount_type=discount_type,
        discount_value=discount_value,
        min_amount=min_amount,
        max_discount=max_discount,
        priority=priority,
        is_active=is_active,
        currency=currency,
    )


# CRM Tools

@mcp.tool()
async def create_client_note(
    client_id: int, title: str, content: str, note_type: str = "general"
) -> dict:
    """
    Create a note for a client.

    Args:
        client_id: ID of the client
        title: Note title
        content: Note content
        note_type: Type of note (general, call, meeting, etc.) (default: "general")
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_client_note(
        client_id=client_id, title=title, content=content, note_type=note_type
    )


# Email Tools

@mcp.tool()
async def send_invoice_email(
    invoice_id: int,
    to_email: Optional[str] = None,
    to_name: Optional[str] = None,
    subject: Optional[str] = None,
    message: Optional[str] = None,
) -> dict:
    """
    Send an invoice via email.

    Args:
        invoice_id: ID of the invoice to send
        to_email: Recipient email address (optional, uses client email if not provided)
        to_name: Recipient name (optional, uses client name if not provided)
        subject: Email subject (optional)
        message: Custom message (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.send_invoice_email(
        invoice_id=invoice_id, to_email=to_email, to_name=to_name, subject=subject, message=message
    )


@mcp.tool()
async def test_email_configuration(test_email: str) -> dict:
    """
    Test email configuration by sending a test email.

    Args:
        test_email: Email address to send test email to
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.test_email_configuration(test_email=test_email)


# Tenant Tools

@mcp.tool()
async def get_tenant_info() -> dict:
    """
    Get current tenant information including company details and settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_tenant_info()


# AI Configuration Tools

@mcp.tool()
async def list_ai_configs() -> dict:
    """
    List all AI configurations for the current tenant. Returns configuration details including providers, models, and settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_ai_configs()


@mcp.tool()
async def create_ai_config(
    provider_name: str,
    model_name: str,
    provider_url: Optional[str] = None,
    api_key: Optional[str] = None,
    is_active: bool = True,
    is_default: bool = False,
    ocr_enabled: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> dict:
    """
    Create a new AI configuration for the tenant.

    Args:
        provider_name: AI provider name (openai, anthropic, ollama, google, custom)
        model_name: Model name to use
        provider_url: Provider URL (for custom providers)
        api_key: API key for the provider
        is_active: Whether the config is active (default: True)
        is_default: Whether this is the default config (default: False)
        ocr_enabled: Whether OCR is enabled for this config (default: False)
        max_tokens: Maximum tokens for requests (default: 4096)
        temperature: Temperature for AI responses (default: 0.1)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_ai_config(
        provider_name=provider_name,
        model_name=model_name,
        provider_url=provider_url,
        api_key=api_key,
        is_active=is_active,
        is_default=is_default,
        ocr_enabled=ocr_enabled,
        max_tokens=max_tokens,
        temperature=temperature,
    )


@mcp.tool()
async def update_ai_config(
    config_id: int,
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    provider_url: Optional[str] = None,
    api_key: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_default: Optional[bool] = None,
    ocr_enabled: Optional[bool] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> dict:
    """
    Update an existing AI configuration.

    Args:
        config_id: ID of the AI config to update
        provider_name: AI provider name (optional)
        model_name: Model name to use (optional)
        provider_url: Provider URL (optional)
        api_key: API key for the provider (optional)
        is_active: Whether the config is active (optional)
        is_default: Whether this is the default config (optional)
        ocr_enabled: Whether OCR is enabled for this config (optional)
        max_tokens: Maximum tokens for requests (optional)
        temperature: Temperature for AI responses (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_ai_config(
        config_id=config_id,
        provider_name=provider_name,
        model_name=model_name,
        provider_url=provider_url,
        api_key=api_key,
        is_active=is_active,
        is_default=is_default,
        ocr_enabled=ocr_enabled,
        max_tokens=max_tokens,
        temperature=temperature,
    )


@mcp.tool()
async def test_ai_config(
    config_id: int,
    custom_prompt: Optional[str] = None,
    test_text: Optional[str] = None,
) -> dict:
    """
    Test an AI configuration to ensure it's working properly.

    Args:
        config_id: ID of the AI config to test
        custom_prompt: Custom test prompt (optional)
        test_text: Test text for processing (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.test_ai_config(
        config_id=config_id, custom_prompt=custom_prompt, test_text=test_text
    )
