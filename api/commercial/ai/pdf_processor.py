from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import tempfile
import os
import json
from typing import Dict, Any, Optional
from types import SimpleNamespace
import logging

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import AIConfig as AIConfigModel, Client
from core.routers.auth import get_current_user
from commercial.ai.services.ocr_service import track_ai_usage
from commercial.prompt_management.services.prompt_service import get_prompt_service
from core.utils.feature_gate import require_feature

router = APIRouter(prefix="/invoices", tags=["pdf-processing"])
logger = logging.getLogger(__name__)

@router.get("/ai-status")
async def get_ai_status(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Check if AI is configured (authenticated users only)"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Use the same priority logic as PDF processing, prioritizing default
    ai_config = db.query(AIConfigModel).filter(
        AIConfigModel.is_active == True,
        AIConfigModel.tested == True
    ).order_by(AIConfigModel.is_default.desc()).first()
    
    if ai_config:
        config_source = "ai_config"
    else:
        # Check environment variables
        env_model = os.getenv("LLM_MODEL_INVOICES") or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL")
        env_api_base = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
        env_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if env_model or env_api_base or env_api_key:
            config_source = "env_vars"
        else:
            config_source = "manual"
    
    return {
        "configured": True,  # Always true since we have fallback
        "config_source": config_source,
        "message": {
            "ai_config": "AI configuration from database",
            "env_vars": "AI configuration from environment variables", 
            "manual": "Manual fallback configuration (may require setup)"
        }.get(config_source, "Unknown configuration source")
    }


@router.get("/process-status/{task_id}")
async def get_process_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get the status of an invoice PDF processing task"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from core.models.models_per_tenant import InvoiceProcessingTask
        
        # Query the processing task
        task = db.query(InvoiceProcessingTask).filter(
            InvoiceProcessingTask.task_id == task_id
        ).first()
        
        if not task:
            # Task might still be in queue, not yet picked up by worker
            return {
                'task_id': task_id,
                'status': 'queued',
                'message': 'Task is queued for processing'
            }
        
        response = {
            'task_id': task.task_id,
            'status': task.status,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'updated_at': task.updated_at.isoformat() if task.updated_at else None
        }
        
        if task.status == 'completed' and task.result_data:
            response['data'] = task.result_data
            response['message'] = 'Invoice data extracted successfully'
        elif task.status == 'failed' and task.error_message:
            response['error'] = task.error_message
            response['message'] = 'Invoice processing failed'
        elif task.status == 'processing':
            response['message'] = 'Invoice is being processed'
        else:
            response['message'] = 'Task is queued for processing'
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

async def process_pdf_with_ai(pdf_path: str, ai_config, db: Optional[Session] = None) -> Dict[str, Any]:
    """Process PDF using AI configuration and return extracted data"""
    try:
        # Import litellm for AI processing
        try:
            from litellm import completion
        except ImportError:
            raise Exception("LiteLLM not installed. Please install it with: pip install litellm")

        # Extract text from PDF
        from pypdf import PdfReader
        from core.utils.file_validation import validate_file_path
        validated_path = validate_file_path(pdf_path)
        with open(validated_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += page_text
                logger.info(f"Page {page_num + 1} extracted {len(page_text)} characters")

        logger.info(f"Total extracted text length: {len(text)} characters")
        logger.info(f"First 500 characters: {text[:500]}")

        if not text.strip():
            raise Exception("Could not extract text from PDF - extracted text is empty")

        # Truncate text if too long to avoid token limits
        max_text_length = 8000  # Conservative limit for most models
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
            logger.info(f"Truncated text to {max_text_length} characters")

        # Prepare prompt for invoice data extraction
        # Use a template string that works with both Jinja2 and simple formatting
        # We avoid f-strings here to keep the JSON braces literal for the next formatting step
        fallback_pdf_prompt = """Extract invoice information from this text and return ONLY valid JSON:

{
  "date": "YYYY-MM-DD",
  "bills_to": "Client name and email",
  "items": [
    {
      "description": "Item description", 
      "quantity": 1,
      "price": 0.00,
      "amount": 0.00,
      "discount": 0.0
    }
  ],
  "total_amount": 0.00,
  "total_discount": 0.0
}

Invoice text:
{{text}}

Respond with JSON only:"""

        try:
            # Get database session for prompt service if not provided
            if db is None:
                db_gen = get_db()
                try:
                    db_session = next(db_gen)
                    prompt_service = get_prompt_service(db_session)
                    prompt = prompt_service.get_prompt(
                        name="pdf_invoice_extraction",
                        variables={"text": text},
                        provider_name=ai_config.provider_name,
                        fallback_prompt=fallback_pdf_prompt
                    )
                finally:
                    db_gen.close()
            else:
                prompt_service = get_prompt_service(db)
                prompt = prompt_service.get_prompt(
                    name="pdf_invoice_extraction",
                    variables={"text": text},
                    provider_name=ai_config.provider_name,
                    fallback_prompt=fallback_pdf_prompt
                )
        except Exception as e:
            logger.warning(f"Failed to get PDF invoice prompt from service: {e}")
            # Manual fallback formatting if prompt service fails
            prompt = fallback_pdf_prompt.replace("{{text}}", text)

        # Format model name for LiteLLM
        model_name = ai_config.model_name
        if ai_config.provider_name == "ollama":
            model_name = f"ollama/{ai_config.model_name}"
        elif ai_config.provider_name == "openrouter":
            model_name = f"openrouter/{ai_config.model_name}"
        elif ai_config.provider_name == "anthropic":
            model_name = f"anthropic/{ai_config.model_name}"

        # Prepare completion arguments
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,  # Increased for better responses
            "temperature": 0.1
        }

        # Add provider-specific configuration
        logger.info(f"AI Config: provider={ai_config.provider_name}, model={ai_config.model_name}, has_api_key={bool(ai_config.api_key)}, provider_url={ai_config.provider_url}")

        if ai_config.provider_name == "openai" and ai_config.api_key:
            kwargs["api_key"] = ai_config.api_key
        elif ai_config.provider_name == "openrouter":
            if ai_config.api_key:
                kwargs["api_key"] = ai_config.api_key
            kwargs["api_base"] = ai_config.provider_url or "https://openrouter.ai/api/v1"
        elif ai_config.provider_name == "ollama" and ai_config.provider_url:
            kwargs["api_base"] = ai_config.provider_url
        elif ai_config.provider_name == "anthropic" and ai_config.api_key:
            kwargs["api_key"] = ai_config.api_key

        # Enhanced fallback logic for manual configuration
        if not kwargs.get("api_key") and ai_config.provider_name != "ollama":
            # Check if we can fallback to environment Ollama
            ollama_base = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
            if ollama_base:
                kwargs["api_base"] = ollama_base
                if not str(kwargs.get("model", "")).startswith("ollama/"):
                    kwargs["model"] = f"ollama/{ai_config.model_name}"
                logger.info("Falling back to Ollama provider via environment variables")
            elif not hasattr(ai_config, 'tested') or not ai_config.tested:
                # This is likely a manual fallback config
                logger.warning("Using untested manual configuration - this may fail")

        logger.info(f"Final kwargs for AI request: {kwargs}")

        # Log the request for debugging
        logger.info(f"Making AI request with model: {model_name}")
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.info(f"Text length: {len(text)} characters")

        # Make AI request
        try:
            response = completion(**kwargs)
            logger.info(f"AI response received: {response}")
        except Exception as e:
            logger.error(f"AI completion failed: {str(e)}")

            # Provide specific error messages based on the likely cause
            error_msg = str(e).lower()
            if "connection" in error_msg or "timeout" in error_msg:
                if ai_config.provider_name == "ollama":
                    raise Exception(f"Cannot connect to Ollama server at {ai_config.provider_url or 'default URL'}. Please ensure Ollama is running and accessible.")
                else:
                    raise Exception(f"Cannot connect to {ai_config.provider_name} API. Please check your network connection and API endpoint.")
            elif "api_key" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
                raise Exception(f"Authentication failed for {ai_config.provider_name}. Please check your API key in AI configuration settings.")
            elif "model" in error_msg or "not found" in error_msg:
                raise Exception(f"Model '{ai_config.model_name}' not found or not available. Please check your model name in AI configuration.")
            else:
                raise Exception(f"AI processing failed: {str(e)}")

        # Parse response
        logger.info(f"Checking AI response structure...")
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Has choices: {hasattr(response, 'choices')}")

        if response and hasattr(response, 'choices') and response.choices:
            logger.info(f"Number of choices: {len(response.choices)}")
            choice = response.choices[0]
            logger.info(f"Choice type: {type(choice)}")
            logger.info(f"Choice has message: {hasattr(choice, 'message')}")

            if hasattr(choice, 'message') and choice.message:
                message = choice.message
                logger.info(f"Message type: {type(message)}")
                logger.info(f"Message has content: {hasattr(message, 'content')}")

                if hasattr(message, 'content') and message.content:
                    response_text = message.content.strip()
                    logger.info(f"AI response text length: {len(response_text)}")
                    logger.info(f"Raw AI response: {response_text}")

                    # Try to extract JSON from response
                    try:
                        # Remove any markdown code block formatting
                        if response_text.startswith("```json"):
                            response_text = response_text[7:]
                        if response_text.endswith("```"):
                            response_text = response_text[:-3]
                        response_text = response_text.strip()

                        extracted_data = json.loads(response_text)
                        logger.info(f"Successfully parsed JSON: {extracted_data}")
                        return extracted_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse AI response as JSON: {response_text}")
                        raise Exception(f"AI returned invalid JSON format. The model may not be suitable for structured data extraction. Response: {response_text[:200]}...")
                else:
                    logger.error(f"Message content is empty or None: {message.content}")
                    raise Exception(f"AI returned empty response. This may indicate an issue with the {ai_config.provider_name} model or prompt.")
            else:
                logger.error(f"Choice has no message or message is None: {choice}")
                raise Exception(f"Invalid response format from {ai_config.provider_name}. The model may not be compatible with this request format.")
        else:
            logger.error(f"AI response structure invalid: {response}")
            logger.error(f"Response: {response}")
            logger.error(f"Has choices: {hasattr(response, 'choices') if response else 'Response is None'}")
            logger.error(f"Choices: {response.choices if response and hasattr(response, 'choices') else 'No choices'}")
            raise Exception(f"AI returned invalid response structure. This may indicate an issue with the {ai_config.provider_name} configuration or model compatibility.")

    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise

@router.post("/process-pdf")
async def process_pdf(
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Queue invoice PDF for async OCR processing"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Check if ai_invoice feature is enabled
    from core.utils.feature_gate import check_feature
    check_feature("ai_invoice", db)

    if not pdf_file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        from core.models.database import get_tenant_context
        from commercial.ai.services.ocr_service import publish_invoice_task
        from pathlib import Path
        import uuid
        from core.utils.file_validation import validate_file_path

        # Get tenant context
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context not available")

        # Save uploaded file to persistent storage
        tenant_folder = f"tenant_{tenant_id}"
        temp_dir = Path("attachments") / tenant_folder / "invoices" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        task_id = str(uuid.uuid4())
        file_extension = Path(pdf_file.filename).suffix
        stored_filename = f"{task_id}{file_extension}"
        file_path = temp_dir / stored_filename

        # Read file content first
        content = await pdf_file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file provided")

        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is 10MB")

        # Save file (validate path structure but don't require existence)
        validated_path = validate_file_path(str(file_path), must_exist=False)
        with open(validated_path, "wb") as f:
            f.write(content)

        # Queue the OCR task
        message = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "file_path": str(file_path),
            "filename": pdf_file.filename,
            "user_id": current_user.id,
            "attempt": 0
        }

        success = publish_invoice_task(message)

        if not success:
            # Clean up file if queueing failed
            if os.path.exists(str(file_path)):
                os.unlink(str(file_path))
            raise HTTPException(
                status_code=500, 
                detail="Failed to queue invoice for processing. Please check Kafka configuration."
            )

        logger.info(f"Invoice PDF queued for processing: task_id={task_id}, tenant_id={tenant_id}")

        return {
            'success': True,
            'task_id': task_id,
            'status': 'queued',
            'message': 'Invoice PDF queued for processing. You will be notified when extraction is complete.'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue invoice PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue invoice: {str(e)}")


# Note: Bank statement extraction moved to services/statement_service.py
