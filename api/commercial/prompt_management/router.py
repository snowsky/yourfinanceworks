"""
Prompt Management API Routes

REST API for managing AI prompt templates with admin interface support.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

from core.models.database import get_db, get_tenant_context
from core.models.prompt_templates import PromptTemplate
from core.services.prompt_service import PromptService, get_prompt_service
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.tenant_database_manager import tenant_db_manager

router = APIRouter(prefix="/prompts", tags=["prompt-management"])


def get_tenant_db(current_user: MasterUser = Depends(get_current_user)):
    """Get tenant database session for prompt operations."""
    session = tenant_db_manager.get_tenant_session(current_user.tenant_id)()
    try:
        yield session
    finally:
        session.close()


# Pydantic models for API
class PromptTemplateCreate(BaseModel):
    name: str = Field(..., description="Unique template name")
    category: str = Field(..., description="Template category")
    template_content: str = Field(..., description="Template content with variable placeholders")
    description: Optional[str] = Field(None, description="Optional description")
    template_variables: Optional[List[str]] = Field(None, description="List of variable names")
    output_format: str = Field("json", description="Expected output format")
    default_values: Optional[Dict[str, Any]] = Field(None, description="Default variable values")
    provider_overrides: Optional[Dict[str, str]] = Field(None, description="Provider-specific overrides")


class PromptTemplateUpdate(BaseModel):
    template_content: Optional[str] = Field(None, description="Template content")
    description: Optional[str] = Field(None, description="Template description")
    template_variables: Optional[List[str]] = Field(None, description="Template variables")
    output_format: Optional[str] = Field(None, description="Output format")
    default_values: Optional[Dict[str, Any]] = Field(None, description="Default values")
    provider_overrides: Optional[Dict[str, str]] = Field(None, description="Provider overrides")
    is_active: Optional[bool] = Field(None, description="Active status")


class PromptTemplateResponse(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str] = None
    template_content: str
    template_variables: Optional[List[str]] = None
    output_format: str
    default_values: Optional[Dict[str, Any]] = None
    provider_overrides: Optional[Dict[str, str]] = None
    version: int
    is_active: bool
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

    @field_validator('template_variables', 'default_values', 'provider_overrides', mode='before')
    @classmethod
    def parse_json_fields(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


class PromptTestRequest(BaseModel):
    variables: Dict[str, Any] = Field(..., description="Variables for template rendering")
    provider_name: Optional[str] = Field(None, description="Provider for override testing")


class PromptUsageStats(BaseModel):
    total_usage: int
    successful_usage: int
    success_rate: float
    avg_processing_time_ms: float
    total_tokens: int
    provider_stats: Dict[str, Any]
    days_analyzed: int


@router.get("/", response_model=List[PromptTemplateResponse])
async def list_prompts(
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active templates"),
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all prompt templates."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    templates = prompt_service.list_prompts(category=category, active_only=active_only)

    return [
        PromptTemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category,
            description=t.description,
            template_content=t.template_content,
            template_variables=t.template_variables,
            output_format=t.output_format,
            default_values=t.default_values,
            provider_overrides=t.provider_overrides,
            version=t.version,
            is_active=t.is_active,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else None,
            created_by=t.created_by,
            updated_by=t.updated_by
        )
        for t in templates
    ]


@router.post("/", response_model=PromptTemplateResponse)
async def create_prompt_template(
    prompt_data: PromptTemplateCreate,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new prompt template."""
    # Check feature gate for prompt management
    require_feature("prompt_management", db)

    prompt_service = get_prompt_service(db)
    template = prompt_service.create_prompt(
        name=prompt_data.name,
        category=prompt_data.category,
        template_content=prompt_data.template_content,
        description=prompt_data.description,
        template_variables=prompt_data.template_variables,
        output_format=prompt_data.output_format,
        default_values=prompt_data.default_values,
        provider_overrides=prompt_data.provider_overrides,
        created_by=current_user.id
    )

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        template_content=template.template_content,
        template_variables=template.template_variables,
        output_format=template.output_format,
        default_values=template.default_values,
        provider_overrides=template.provider_overrides,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        updated_by=template.updated_by
    )


@router.put("/{name}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    name: str,
    prompt_data: PromptTemplateUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update an existing prompt template."""
    # Check feature gate for prompt management
    require_feature("prompt_management", db)

    prompt_service = get_prompt_service(db)

    # Convert to dict, excluding None values
    updates = {k: v for k, v in prompt_data.dict().items() if v is not None}

    template = prompt_service.update_prompt(
        name=name,
        updates=updates,
        updated_by=current_user.id
    )

    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found")

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        template_content=template.template_content,
        template_variables=template.template_variables,
        output_format=template.output_format,
        default_values=template.default_values,
        provider_overrides=template.provider_overrides,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        updated_by=template.updated_by
    )


@router.post("/{name}/test")
async def test_prompt_template(
    name: str,
    test_request: PromptTestRequest,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Test a prompt template with provided variables."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)

    try:
        rendered_prompt = prompt_service.get_prompt(
            name=name,
            variables=test_request.variables,
            provider_name=test_request.provider_name
        )

        return {
            "success": True,
            "rendered_prompt": rendered_prompt,
            "variables_used": list(test_request.variables.keys()),
            "provider_override": test_request.provider_name
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "rendered_prompt": None
        }


@router.get("/usage-stats", response_model=PromptUsageStats)
async def get_usage_stats(
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get usage statistics for all prompts."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    stats = prompt_service.get_usage_stats(days=days)

    return PromptUsageStats(**stats)


@router.get("/{name}/usage-stats", response_model=PromptUsageStats)
async def get_prompt_usage_stats(
    name: str,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get usage statistics for a specific prompt template."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    stats = prompt_service.get_usage_stats(template_name=name, days=days)

    return PromptUsageStats(**stats)


@router.get("/categories/list")
async def list_prompt_categories(
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all available prompt categories."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    try:
        categories = db.query(PromptTemplate.category).distinct().all()
        return {"categories": [cat[0] for cat in categories if cat[0]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list categories: {str(e)}")


@router.get("/usage-stats/global", response_model=PromptUsageStats)
async def get_global_usage_stats(
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get global usage statistics for all prompts."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    stats = prompt_service.get_usage_stats(days=days)

    return PromptUsageStats(**stats)


@router.get("/defaults/list", response_model=List[PromptTemplateResponse])
async def list_default_prompts(
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all default prompt templates."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)
    
    prompt_service = get_prompt_service(db)
    templates = prompt_service.list_default_prompts()

    return [
        PromptTemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category,
            description=t.description,
            template_content=t.template_content,
            template_variables=t.template_variables,
            output_format=t.output_format,
            default_values=t.default_values,
            provider_overrides=t.provider_overrides,
            version=t.version,
            is_active=t.is_active,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else None
        )
        for t in templates
    ]


@router.delete("/{name}")
async def delete_prompt_template(
    name: str,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Delete a prompt template."""
    # Check feature gate for prompt management
    require_feature("prompt_management", db)

    prompt_service = get_prompt_service(db)
    success = prompt_service.delete_prompt(name, updated_by=current_user.id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found")

    return {"message": f"Prompt template '{name}' deleted successfully"}


@router.post("/{name}/reset")
async def reset_prompt_to_default(
    name: str,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Reset a prompt template to its default version."""
    # Check feature gate for prompt management
    require_feature("prompt_management", db)

    prompt_service = get_prompt_service(db)
    template = prompt_service.reset_prompt_to_default(name, updated_by=current_user.id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found or no default available")

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        template_content=template.template_content,
        template_variables=template.template_variables,
        output_format=template.output_format,
        default_values=template.default_values,
        provider_overrides=template.provider_overrides,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        updated_by=template.updated_by
    )


@router.get("/{name}/versions", response_model=List[PromptTemplateResponse])
async def list_prompt_versions(
    name: str,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """List all versions of a specific prompt template."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    templates = prompt_service.list_prompt_versions(name)

    return [
        PromptTemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category,
            description=t.description,
            template_content=t.template_content,
            template_variables=t.template_variables,
            output_format=t.output_format,
            default_values=t.default_values,
            provider_overrides=t.provider_overrides,
            version=t.version,
            is_active=t.is_active,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else None
        )
        for t in templates
    ]


@router.post("/{name}/versions/{version}/restore")
async def restore_prompt_version(
    name: str,
    version: int,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Restore a specific version of a prompt template."""
    # Check feature gate for prompt management
    require_feature("prompt_management", db)

    prompt_service = get_prompt_service(db)
    template = prompt_service.restore_prompt_version(name, version, updated_by=current_user.id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' version {version} not found")

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        template_content=template.template_content,
        template_variables=template.template_variables,
        output_format=template.output_format,
        default_values=template.default_values,
        provider_overrides=template.provider_overrides,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        updated_by=template.updated_by
    )


@router.get("/{name}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    name: str,
    db: Session = Depends(get_tenant_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get a specific prompt template by name."""
    # Check feature gate for prompt management (read access)
    from core.utils.feature_gate import check_feature_read_only
    check_feature_read_only("prompt_management", db)

    prompt_service = get_prompt_service(db)
    template = prompt_service._get_template(name)

    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt template '{name}' not found")

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        template_content=template.template_content,
        template_variables=template.template_variables,
        output_format=template.output_format,
        default_values=template.default_values,
        provider_overrides=template.provider_overrides,
        version=template.version,
        is_active=template.is_active,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
        created_by=template.created_by,
        updated_by=template.updated_by
    )
