from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import logging
from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.models.models_per_tenant import AIConfig as AIConfigModel
from commercial.ai.schemas.ai_config import (
    AIConfigCreate,
    AIConfigUpdate,
    AIConfig as AIConfigSchema,
    AIConfigTestRequest,
    AIConfigTestWithOverrides,
    AIConfigTestResponse,
    SUPPORTED_PROVIDERS
)
from core.utils.rbac import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-config",
    tags=["AI Configuration"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

def _extract_meaningful_error(error_str: str) -> str:
    """Extract meaningful error message from technical error strings."""
    import re

    # Common patterns to extract meaningful errors
    patterns = [
        # Ollama model not found: {"error":"model 'llama2' not found"}
        r'"error":"([^"]+)"',
        # OpenAI/OpenRouter API errors: "message": "..."
        r'"message":\s*"([^"]+)"',
        # General API connection errors
        r'APIConnectionError:\s*(.+?)(?:\n|$)',
        r'AuthenticationError:\s*(.+?)(?:\n|$)',
        r'RateLimitError:\s*(.+?)(?:\n|$)',
        # LiteLLM specific errors
        r'litellm\.\w+Error:\s*(.+?)(?:\n|$)',
        # Connection refused or timeout
        r'Connection refused|timeout|timed out',
        # Model not found patterns
        r"model '[^']+' not found",
        r"Model '[^']+' not found",
    ]

    # Try each pattern
    for pattern in patterns:
        match = re.search(pattern, error_str, re.IGNORECASE)
        if match:
            if match.groups():
                extracted = match.group(1).strip()
            else:
                extracted = match.group(0).strip()

            # Add helpful suggestions for common errors
            if "not found" in extracted.lower() and "model" in extracted.lower():
                extracted += ". Please check if the model is available in your Ollama installation."
            elif "connection refused" in extracted.lower():
                extracted += ". Please check if the service is running and accessible."
            elif "incorrect api key" in extracted.lower():
                extracted += ". Please verify your API key is correct."

            return extracted

    # If no pattern matches, try to extract the last meaningful line
    lines = error_str.split('\n')
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('Traceback') and not line.startswith('File '):
            # Remove common prefixes
            for prefix in ['litellm.', 'openai.', 'anthropic.', 'Exception: ', 'Error: ']:
                if line.startswith(prefix):
                    line = line[len(prefix):]
            return line

    # Fallback to original error if nothing else works
    return error_str[:200] + "..." if len(error_str) > 200 else error_str



@router.get("/", response_model=List[AIConfigSchema])
async def get_ai_configs(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get all AI configurations for the current tenant"""
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        configs = db.query(AIConfigModel).order_by(AIConfigModel.provider_name, AIConfigModel.model_name).all()
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

        # Log audit event to tenant database
        try:
            from core.utils.audit import log_audit_event
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="CREATE_AI_CONFIG",
                resource_type="ai_config",
                resource_id=str(db_config.id),
                resource_name=f"{db_config.provider_name}/{db_config.model_name}",
                details={
                    "config_name": f"{db_config.provider_name}/{db_config.model_name}",
                    "config_provider": db_config.provider_name,
                    "config_id": db_config.id,
                    "is_default": db_config.is_default
                },
                status="success"
            )
        except Exception as e:
            logger.error(f"Failed to log AI config creation: {e}")
            pass  # Continue even if audit logging fails

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

        # Log audit event to tenant database
        try:
            from core.utils.audit import log_audit_event
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="UPDATE_AI_CONFIG",
                resource_type="ai_config",
                resource_id=str(config_id),
                resource_name=f"{db_config.provider_name}/{db_config.model_name}",
                details={
                    "config_name": f"{db_config.provider_name}/{db_config.model_name}",
                    "config_provider": db_config.provider_name,
                    "config_id": config_id,
                    "updated_fields": list(update_data.keys()),
                    "is_default": db_config.is_default
                },
                status="success"
            )
        except Exception as e:
            logger.error(f"Failed to log AI config update: {e}")
            pass  # Continue even if audit logging fails

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

        # Log audit event to tenant database
        try:
            from core.utils.audit import log_audit_event
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="DELETE_AI_CONFIG",
                resource_type="ai_config",
                resource_id=str(config_id),
                resource_name=f"{db_config.provider_name}/{db_config.model_name}",
                details={
                    "config_name": f"{db_config.provider_name}/{db_config.model_name}",
                    "config_provider": db_config.provider_name,
                    "config_id": config_id
                },
                status="success"
            )
        except Exception as e:
            logger.error(f"Failed to log AI config deletion: {e}")
            pass  # Continue even if audit logging fails

        return {"message": "AI configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete AI configuration: {str(e)}"
        )

@router.post("/test-with-overrides", response_model=AIConfigTestResponse)
async def test_ai_config_with_overrides(
    test_request: AIConfigTestWithOverrides,
    current_user: MasterUser = Depends(get_current_user)
):
    """Test an AI configuration with override parameters for unsaved changes."""
    try:
        start_time = datetime.now(timezone.utc)
        test_text = test_request.test_text or \
                   "Hello! This is a test message to verify the AI configuration is working."

        # Validate required override fields
        if not test_request.provider_name:
            raise HTTPException(status_code=400, detail="provider_name is required")
        if not test_request.model_name:
            raise HTTPException(status_code=400, detail="model_name is required")

        try:
            # Import litellm here to avoid circular imports
            try:
                from litellm import completion
            except ImportError:
                return AIConfigTestResponse(
                    success=False,
                    message="LiteLLM not installed. Please install it with: pip install litellm"
                )

            # Prepare the completion call with proper model formatting using override values
            model_name = test_request.model_name
            provider_name = test_request.provider_name

            # Format model name based on provider for LiteLLM
            if provider_name == "ollama":
                model_name = f"ollama/{model_name}"
            elif provider_name == "openrouter":
                model_name = f"openrouter/{model_name}"

            # Use override values with defaults
            max_tokens = min(test_request.max_tokens or 4096, 100)  # Limit for testing
            temperature = test_request.temperature if test_request.temperature is not None else 0.1

            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": test_text}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            # Add provider-specific configuration using override values
            if provider_name == "openai" and test_request.api_key:
                kwargs["api_key"] = test_request.api_key
            elif provider_name == "openrouter":
                if test_request.api_key:
                    kwargs["api_key"] = test_request.api_key
                # Set the OpenRouter API base URL
                kwargs["api_base"] = test_request.provider_url or "https://openrouter.ai/api/v1"
            elif provider_name == "anthropic" and test_request.api_key:
                kwargs["api_key"] = test_request.api_key
            elif provider_name == "google" and test_request.api_key:
                kwargs["api_key"] = test_request.api_key
            elif provider_name == "ollama" and test_request.provider_url:
                kwargs["api_base"] = test_request.provider_url
            elif provider_name == "custom":
                if test_request.api_key:
                    kwargs["api_key"] = test_request.api_key
                if test_request.provider_url:
                    kwargs["api_base"] = test_request.provider_url

            # Enable debug logging for LiteLLM
            import litellm
            litellm._turn_on_debug()

            # Make the test call
            response = completion(**kwargs)

            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds() * 1000

            return AIConfigTestResponse(
                success=True,
                message="Configuration test successful",
                response_time_ms=response_time,
                response=response.choices[0].message.content if response.choices else "No response"
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds() * 1000

            # Extract meaningful error message
            error_message = _extract_meaningful_error(str(e))

            return AIConfigTestResponse(
                success=False,
                message=f"Configuration test failed: {error_message}",
                response_time_ms=response_time,
                error=error_message
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test AI configuration: {str(e)}"
        )

@router.post("/{config_id}/test", response_model=AIConfigTestResponse)
async def test_ai_config(
    config_id: int,
    test_request: AIConfigTestRequest = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Test an AI configuration with enhanced response tracking"""
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()

        if not db_config:
            raise HTTPException(status_code=404, detail="AI configuration not found")

        start_time = datetime.now(timezone.utc)
        test_text = (test_request.test_text if test_request else None) or \
                   "Hello! This is a test message to verify the AI configuration is working."

        try:
            # Import litellm here to avoid circular imports
            try:
                from litellm import completion
            except ImportError:
                return AIConfigTestResponse(
                    success=False,
                    message="LiteLLM not installed. Please install it with: pip install litellm"
                )

            # Prepare the completion call with proper model formatting
            model_name = db_config.model_name

            # Format model name based on provider for LiteLLM
            if db_config.provider_name == "ollama":
                model_name = f"ollama/{model_name}"
            elif db_config.provider_name == "openrouter":
                model_name = f"openrouter/{model_name}"  # OpenRouter requires "openrouter/" prefix for proper routing

            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": test_text}],
                "max_tokens": min(db_config.max_tokens, 100),  # Limit for testing
                "temperature": db_config.temperature
            }

            # Add provider-specific configuration
            if db_config.provider_name == "openai" and db_config.api_key:
                kwargs["api_key"] = db_config.api_key
            elif db_config.provider_name == "openrouter":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
                # Set the OpenRouter API base URL
                kwargs["api_base"] = db_config.provider_url or "https://openrouter.ai/api/v1"
            elif db_config.provider_name == "anthropic" and db_config.api_key:
                kwargs["api_key"] = db_config.api_key
            elif db_config.provider_name == "google" and db_config.api_key:
                kwargs["api_key"] = db_config.api_key
            elif db_config.provider_name == "ollama" and db_config.provider_url:
                kwargs["api_base"] = db_config.provider_url
            elif db_config.provider_name == "custom":
                if db_config.api_key:
                    kwargs["api_key"] = db_config.api_key
                if db_config.provider_url:
                    kwargs["api_base"] = db_config.provider_url

            # Enable debug logging for LiteLLM
            import litellm
            litellm._turn_on_debug()

            # Make the test call
            response = completion(**kwargs)

            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds() * 1000

            # Mark as tested if successful and update usage tracking
            db_config.tested = True
            db_config.usage_count += 1
            db_config.last_used_at = end_time
            db.commit()

            return AIConfigTestResponse(
                success=True,
                message="Configuration test successful",
                response_time_ms=response_time,
                response=response.choices[0].message.content if response.choices else "No response"
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds() * 1000

            # Extract meaningful error message
            error_message = _extract_meaningful_error(str(e))

            # Mark as not tested if the test failed
            db_config.tested = False
            db.commit()

            return AIConfigTestResponse(
                success=False,
                message=f"Configuration test failed: {error_message}",
                response_time_ms=response_time,
                error=error_message
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test AI configuration: {str(e)}"
        )


# Add provider information endpoint (public - no authentication required)
@router.get("/providers")
async def get_supported_providers():
    """Get information about supported AI providers."""
    return {
        "providers": SUPPORTED_PROVIDERS,
        "count": len(SUPPORTED_PROVIDERS)
    }


@router.get("/{config_id}/usage")
async def get_config_usage(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get usage statistics for an AI configuration."""
    try:
        # No tenant_id filtering needed since we're in the tenant's database
        db_config = db.query(AIConfigModel).filter(AIConfigModel.id == config_id).first()

        if not db_config:
            raise HTTPException(
                status_code=404,
                detail="AI configuration not found"
            )

        return {
            "config_id": config_id,
            "usage_count": db_config.usage_count,
            "last_used_at": db_config.last_used_at,
            "created_at": db_config.created_at,
            "updated_at": db_config.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get usage statistics: {str(e)}"
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

@router.post("/trigger-full-review")
async def trigger_full_system_review(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Reset review status for all documents (Invoices, Expenses, Statements) to trigger a full re-review"""
    require_admin(current_user, "trigger full system review")

    try:
        from core.models.models_per_tenant import Invoice, Expense, BankStatement
        from commercial.ai.services.ai_config_service import AIConfigService
        
        # Check if review worker is enabled
        if not AIConfigService.is_review_worker_enabled(db):
            raise HTTPException(
                status_code=400,
                detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
            )

        logger.info(f"Triggering full system review for tenant context")
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        logger.info(f"Full review trigger: active tenant_id = {tenant_id}")

        # Reset Invoices
        invoice_count = db.query(Invoice).filter(Invoice.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        # Reset Expenses
        expense_count = db.query(Expense).filter(Expense.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        # Reset Bank Statements
        statement_count = db.query(BankStatement).filter(BankStatement.is_deleted == False).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        db.commit()

        # Publish Kafka event to trigger immediate processing
        try:
            from core.services.review_event_service import get_review_event_service

            if tenant_id:
                logger.info(f"Publishing full review trigger event for tenant {tenant_id}")
                event_service = get_review_event_service()
                event_service.publish_full_review_trigger(tenant_id)
            else:
                logger.warning("Could not publish review trigger event: No tenant_id in context")
        except Exception as e:
            logger.warning(f"Failed to publish review trigger event: {e}")

        return {
            "success": True,
            "message": f"Full system review triggered. {invoice_count} invoices, {expense_count} expenses, and {statement_count} statements queued for review.",
            "counts": {
                "invoices": invoice_count,
                "expenses": expense_count,
                "statements": statement_count
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-progress")
async def get_review_progress(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get the current review progress for all document types"""
    require_admin(current_user, "view review progress")

    try:
        from core.models.models_per_tenant import Invoice, Expense, BankStatement

        # Get counts for each status
        invoice_stats = {
            "not_started": db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.review_status == "not_started"
            ).count(),
            "pending": db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.review_status == "pending"
            ).count(),
            "reviewed": db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.review_status == "reviewed"
            ).count(),
            "diff_found": db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.review_status == "diff_found"
            ).count(),
            "failed": db.query(Invoice).filter(
                Invoice.is_deleted == False,
                Invoice.review_status == "failed"
            ).count(),
        }

        expense_stats = {
            "not_started": db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.review_status == "not_started"
            ).count(),
            "pending": db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.review_status == "pending"
            ).count(),
            "reviewed": db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.review_status == "reviewed"
            ).count(),
            "diff_found": db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.review_status == "diff_found"
            ).count(),
            "failed": db.query(Expense).filter(
                Expense.is_deleted == False,
                Expense.review_status == "failed"
            ).count(),
        }

        statement_stats = {
            "not_started": db.query(BankStatement).filter(
                BankStatement.is_deleted == False,
                BankStatement.review_status == "not_started"
            ).count(),
            "pending": db.query(BankStatement).filter(
                BankStatement.is_deleted == False,
                BankStatement.review_status == "pending"
            ).count(),
            "reviewed": db.query(BankStatement).filter(
                BankStatement.is_deleted == False,
                BankStatement.review_status == "reviewed"
            ).count(),
            "diff_found": db.query(BankStatement).filter(
                BankStatement.is_deleted == False,
                BankStatement.review_status == "diff_found"
            ).count(),
            "failed": db.query(BankStatement).filter(
                BankStatement.is_deleted == False,
                BankStatement.review_status == "failed"
            ).count(),
        }

        # Calculate totals and progress
        invoice_total = sum(invoice_stats.values())
        invoice_completed = invoice_stats["reviewed"] + invoice_stats["diff_found"] + invoice_stats["failed"]
        invoice_progress = (invoice_completed / invoice_total * 100) if invoice_total > 0 else 0

        expense_total = sum(expense_stats.values())
        expense_completed = expense_stats["reviewed"] + expense_stats["diff_found"] + expense_stats["failed"]
        expense_progress = (expense_completed / expense_total * 100) if expense_total > 0 else 0

        statement_total = sum(statement_stats.values())
        statement_completed = statement_stats["reviewed"] + statement_stats["diff_found"] + statement_stats["failed"]
        statement_progress = (statement_completed / statement_total * 100) if statement_total > 0 else 0

        return {
            "invoices": {
                "stats": invoice_stats,
                "total": invoice_total,
                "completed": invoice_completed,
                "progress_percent": round(invoice_progress, 1)
            },
            "expenses": {
                "stats": expense_stats,
                "total": expense_total,
                "completed": expense_completed,
                "progress_percent": round(expense_progress, 1)
            },
            "statements": {
                "stats": statement_stats,
                "total": statement_total,
                "completed": statement_completed,
                "progress_percent": round(statement_progress, 1)
            },
            "overall_progress_percent": round(
                ((invoice_completed + expense_completed + statement_completed) / 
                 (invoice_total + expense_total + statement_total) * 100) 
                if (invoice_total + expense_total + statement_total) > 0 else 0,
                1
            )
        }
    except Exception as e:
        logger.error(f"Failed to get review progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-full-review")
async def cancel_full_system_review(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Cancel the full system review by resetting all pending reviews back to not_started"""
    require_admin(current_user, "cancel full system review")

    try:
        logger.info(f"Cancelling full system review for tenant context")
        from core.models.models_per_tenant import Invoice, Expense, BankStatement
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        logger.info(f"Cancel review: active tenant_id = {tenant_id}")

        # Reset pending Invoices back to not_started
        invoice_count = db.query(Invoice).filter(
            Invoice.is_deleted == False,
            Invoice.review_status == "pending"
        ).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        # Reset pending Expenses back to not_started
        expense_count = db.query(Expense).filter(
            Expense.is_deleted == False,
            Expense.review_status == "pending"
        ).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        # Reset pending Bank Statements back to not_started
        statement_count = db.query(BankStatement).filter(
            BankStatement.is_deleted == False,
            BankStatement.review_status == "pending"
        ).update({
            "review_status": "not_started",
            "review_result": None,
            "reviewed_at": None
        }, synchronize_session=False)

        db.commit()

        logger.info(f"Cancelled full system review. Reset {invoice_count} invoices, {expense_count} expenses, and {statement_count} statements")

        return {
            "success": True,
            "message": f"Full system review cancelled. Reset {invoice_count} invoices, {expense_count} expenses, and {statement_count} statements back to not_started."
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cancel full system review: {e}")
        raise HTTPException(status_code=500, detail=str(e))
