from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models.database import get_master_db, get_db, set_tenant_context
from routers.auth import get_current_user
from models.models import MasterUser
from models.models_per_tenant import AIConfig as AIConfigModel
from schemas.ai_config import AIConfigCreate, AIConfigUpdate, AIConfig as AIConfigSchema
from services.tenant_database_manager import tenant_db_manager
from utils.rbac import require_admin

router = APIRouter(
    prefix="/ai-config",
    tags=["AI Configuration"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[AIConfigSchema])
async def get_ai_configs(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get all AI configurations for the current tenant"""
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        configs = db.query(AIConfigModel).all()
        return configs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch AI configurations: {str(e)}"
        )

@router.post("/", response_model=AIConfigSchema)
async def create_ai_config(
    config: AIConfigCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new AI configuration"""
    # Only tenant admins can create AI configs
    require_admin(current_user, "create AI configurations")
    
    # Manually set tenant context and get tenant database
    try:
        # If this is set as default, unset other defaults
        if config.is_default:
            # No tenant_id filtering needed since we're in the tenant's database
            db.query(AIConfigModel).filter(
                AIConfigModel.is_default == True
            ).update({"is_default": False})
        
        # No tenant_id needed since each tenant has its own database
        db_config = AIConfigModel(**config.model_dump())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create AI configuration: {str(e)}"
        )
    
@router.put("/{config_id}", response_model=AIConfigSchema)
async def update_ai_config(
    config_id: int,
    config: AIConfigUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Update an AI configuration"""
    # Only tenant admins can update AI configs
    require_admin(current_user, "update AI configurations")
    
    # Manually set tenant context and get tenant database
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()
        
        if not db_config:
            raise HTTPException(status_code=404, detail="AI configuration not found")
        
        # If this is set as default, unset other defaults
        if config.is_default:
            # No tenant_id filtering needed since we're in the tenant's database
            db.query(AIConfigModel).filter(
                AIConfigModel.is_default == True,
                AIConfigModel.id != config_id
            ).update({"is_default": False})
        
        # Update only provided fields
        update_data = config.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_config, field, value)
        
        db.commit()
        db.refresh(db_config)
        return db_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update AI configuration: {str(e)}"
        )

@router.delete("/{config_id}")
async def delete_ai_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Delete an AI configuration"""
    # Only tenant admins can delete AI configs
    require_admin(current_user, "delete AI configurations")
    
    # Manually set tenant context and get tenant database
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()
        
        if not db_config:
            raise HTTPException(status_code=404, detail="AI configuration not found")
        
        db.delete(db_config)
        db.commit()
        return {"message": "AI configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete AI configuration: {str(e)}"
        )

@router.get("/test/{config_id}")
async def test_ai_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Test an AI configuration"""
    # Manually set tenant context and get tenant database
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()
        
        if not db_config:
            raise HTTPException(status_code=404, detail="AI configuration not found")
        
        try:
            # Import litellm here to avoid circular imports
            try:
                from litellm import completion
            except ImportError:
                return {
                    "success": False,
                    "message": "LiteLLM not installed. Please install it with: pip install litellm"
                }
            
            # Prepare the test message
            test_message = "Hello! This is a test message to verify the AI configuration is working."
            
            # Prepare the completion call with proper model formatting
            model_name = db_config.model_name
            
            # Format model name based on provider for LiteLLM
            if db_config.provider_name == "ollama":
                # For Ollama, prefix with ollama/
                model_name = f"ollama/{db_config.model_name}"
            elif db_config.provider_name == "openai":
                # For OpenAI, use as-is (LiteLLM recognizes OpenAI models)
                model_name = db_config.model_name
            elif db_config.provider_name == "openrouter":
                # For OpenRouter, prefix with openrouter/
                model_name = f"openrouter/{db_config.model_name}"
            elif db_config.provider_name == "anthropic":
                # For Anthropic, use as-is (LiteLLM recognizes Anthropic models)
                model_name = db_config.model_name
            elif db_config.provider_name == "google":
                # For Google, use as-is (LiteLLM recognizes Google models)
                model_name = db_config.model_name
            elif db_config.provider_name == "custom":
                # For custom providers, use the model name as-is
                model_name = db_config.model_name
            
            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": test_message}],
                "max_tokens": 50
            }
            
            # Add provider-specific configuration
            if db_config.provider_name == "openai":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
                if db_config.provider_url:
                    kwargs["api_base"] = db_config.provider_url
            elif db_config.provider_name == "openrouter":
                import os
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
                elif os.getenv("OPENROUTER_API_KEY"):
                    kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")
            elif db_config.provider_name == "ollama":
                if db_config.provider_url:
                    kwargs["api_base"] = db_config.provider_url
            elif db_config.provider_name == "anthropic":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
            elif db_config.provider_name == "google":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
            elif db_config.provider_name == "custom":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
                if db_config.provider_url:
                    kwargs["api_base"] = db_config.provider_url
            
            # Make the test call
            response = completion(**kwargs)
            
            # Mark as tested if successful
            db_config.tested = True
            db.flush()  # Make the change visible to queries
            
            # Check if this is the only tested config and set as default if so
            tested_count = db.query(AIConfigModel).filter(AIConfigModel.tested == True).count()
            if tested_count == 1:
                # Unset any existing defaults first
                db.query(AIConfigModel).filter(
                    AIConfigModel.is_default == True
                ).update({"is_default": False})
                # Set this as default
                db_config.is_default = True
            
            db.commit()
            
            return {
                "success": True,
                "message": "Configuration test successful" + (" and set as default" if db_config.is_default else ""),
                "response": response.choices[0].message.content if response.choices else "No response"
            }
            
        except Exception as e:
            print(f"AI Config Test Error: {str(e)}")
            print(f"AI Config Test Error Type: {type(e)}")
            import traceback
            print(f"AI Config Test Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"Configuration test failed: {str(e)}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test AI configuration: {str(e)}"
        )

@router.post("/mark-tested/{config_id}")
async def mark_config_as_tested(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Manually mark an AI configuration as tested"""
    # Only tenant admins can mark configs as tested
    require_admin(current_user, "mark AI configurations as tested")
    
    # Manually set tenant context and get tenant database
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()
        
        if not db_config:
            raise HTTPException(status_code=404, detail="AI configuration not found")
        
        db_config.tested = True
        db.flush()  # Make the change visible to queries
        
        # Check if this is the only tested config and set as default if so
        tested_count = db.query(AIConfigModel).filter(AIConfigModel.tested == True).count()
        if tested_count == 1:
            # Unset any existing defaults first
            db.query(AIConfigModel).filter(
                AIConfigModel.is_default == True
            ).update({"is_default": False})
            # Set this as default
            db_config.is_default = True
        
        db.commit()
        
        return {"message": "AI configuration marked as tested successfully" + (" and set as default" if db_config.is_default else "")}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark AI configuration as tested: {str(e)}"
        )