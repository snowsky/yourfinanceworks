from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import tempfile
import os
import json
from typing import Dict, Any
from types import SimpleNamespace
import logging

from models.database import get_db
from models.models import MasterUser
from models.models_per_tenant import AIConfig as AIConfigModel, Client
from routers.auth import get_current_user
from services.ocr_service import track_ai_usage

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

async def process_pdf_with_ai(pdf_path: str, ai_config) -> Dict[str, Any]:
    """Process PDF using AI configuration and return extracted data"""
    try:
        # Import litellm for AI processing
        try:
            from litellm import completion
        except ImportError:
            raise Exception("LiteLLM not installed. Please install it with: pip install litellm")

        # Extract text from PDF
        from pypdf import PdfReader
        with open(pdf_path, 'rb') as file:
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
        prompt = f"""Extract invoice information from this text and return ONLY valid JSON:

{{
  "date": "YYYY-MM-DD",
  "bills_to": "Client name and email",
  "items": [
    {{
      "description": "Item description", 
      "quantity": 1,
      "price": 0.00,
      "amount": 0.00,
      "discount": 0.0
    }}
  ],
  "total_amount": 0.00,
  "total_discount": 0.0
}}

Invoice text:
{text}

Respond with JSON only:"""

        # Format model name for LiteLLM
        model_name = ai_config.model_name
        if ai_config.provider_name == "ollama":
            model_name = f"ollama/{ai_config.model_name}"
        elif ai_config.provider_name == "openai":
            model_name = ai_config.model_name
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
        if ai_config.provider_name == "ollama" and ai_config.provider_url:
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
    """Check if AI is configured (authenticated users only)"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    """Process PDF invoice and extract data using the main.py script"""

    if not pdf_file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await pdf_file.read()
            temp_file.write(content)
            temp_pdf_path = temp_file.name

        # Priority system: AI config → env vars → manual fallback
        active_config = None
        config_source = "manual"
        
        # 1. Check if AI config is set up and tested, prioritizing default
        ai_config = db.query(AIConfigModel).filter(
            AIConfigModel.is_active == True,
            AIConfigModel.tested == True
        ).order_by(AIConfigModel.is_default.desc()).first()
        
        if ai_config:
            active_config = ai_config
            config_source = "ai_config"
            logger.info("Using AI configuration from database")
        else:
            # 2. Check if env vars are set up
            env_model = os.getenv("LLM_MODEL_INVOICES") or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL")
            env_api_base = os.getenv("LLM_API_BASE") or os.getenv("OLLAMA_API_BASE")
            env_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            
            # Debug logging
            logger.info(f"Environment variables check:")
            logger.info(f"  LLM_MODEL_INVOICES: {os.getenv('LLM_MODEL_INVOICES')}")
            logger.info(f"  LLM_MODEL: {os.getenv('LLM_MODEL')}")
            logger.info(f"  OLLAMA_MODEL: {os.getenv('OLLAMA_MODEL')}")
            logger.info(f"  LLM_API_BASE: {os.getenv('LLM_API_BASE')}")
            logger.info(f"  OLLAMA_API_BASE: {os.getenv('OLLAMA_API_BASE')}")
            logger.info(f"  LLM_API_KEY: {'***' if os.getenv('LLM_API_KEY') else None}")
            logger.info(f"  OPENAI_API_KEY: {'***' if os.getenv('OPENAI_API_KEY') else None}")
            logger.info(f"  Final values - model: {env_model}, api_base: {env_api_base}, api_key: {'***' if env_api_key else None}")
            
            if env_model or env_api_base or env_api_key:
                # Determine provider from env vars
                if env_api_base or os.getenv("OLLAMA_MODEL"):
                    provider_name = "ollama"
                elif env_api_key:
                    provider_name = "openai"
                else:
                    provider_name = "ollama"  # Default fallback
                
                active_config = SimpleNamespace(
                    provider_name=provider_name,
                    provider_url=env_api_base,
                    api_key=env_api_key,
                    model_name=env_model or "gpt-oss:latest",
                    is_active=True,
                    tested=True,
                )
                config_source = "env_vars"
                logger.info(f"Using AI configuration from environment variables: provider={provider_name}, model={env_model or 'gpt-oss:latest'}, api_base={env_api_base}")
            else:
                # 3. Manual fallback - use basic defaults
                active_config = SimpleNamespace(
                    provider_name="ollama",
                    provider_url="http://localhost:11434",
                    api_key=None,
                    model_name="gpt-oss:latest",
                    is_active=True,
                    tested=False,  # Mark as untested for manual config
                )
                config_source = "manual"
                logger.info("No environment variables found, using manual fallback AI configuration")

        try:
            # Process PDF with AI
            extracted_data = await process_pdf_with_ai(temp_pdf_path, active_config)
            logger.info(f"PDF processed successfully with AI (config source: {config_source})")

            # Track AI usage if we used a database AI config
            if config_source == "ai_config" and hasattr(active_config, 'provider_name'):
                ai_config_dict = {
                    'provider_name': active_config.provider_name,
                    'model_name': active_config.model_name,
                    'provider_url': getattr(active_config, 'provider_url', None),
                    'api_key': getattr(active_config, 'api_key', None)
                }
                track_ai_usage(db, ai_config_dict)

        except Exception as e:
            logger.error(f"PDF processing failed with {config_source} config: {str(e)}")
            
            # Provide helpful error message based on config source
            if config_source == "manual":
                error_msg = f"PDF processing failed with manual configuration. Please set up AI configuration in Settings or configure environment variables. Error: {str(e)}"
            elif config_source == "env_vars":
                error_msg = f"PDF processing failed with environment variables. Please check your LLM environment configuration or set up AI config in Settings. Error: {str(e)}"
            else:
                error_msg = f"PDF processing failed with AI configuration. Please verify your AI settings are correct. Error: {str(e)}"
            
            raise HTTPException(status_code=500, detail=error_msg)

        # Check if client exists or needs to be created
        client_info = extracted_data.get('bills_to', '')
        existing_client = None

        if client_info:
            # Try to find existing client by email (regex matching)
            import re
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', client_info)
            if email_match:
                client_email = email_match.group()
                existing_client = db.query(Client).filter(
                    Client.email.ilike(client_email)
                ).first()

        # Format response
        client_email = None
        if client_info:
            import re
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', client_info)
            if email_match:
                client_email = email_match.group()

        response_data = {
            'invoice_data': extracted_data,
            'client_exists': existing_client is not None,
            'existing_client': {
                'id': existing_client.id,
                'name': existing_client.name,
                'email': existing_client.email
            } if existing_client else None,
            'suggested_client': {
                'name': client_info.split('\n')[0].strip() if client_info else '',
                'email': client_email or '',
                'address': client_info
            } if client_info else None,
            'config_source': config_source  # Include config source in response
        }

        return {
            'success': True,
            'data': response_data,
            'message': f'PDF processed successfully using {config_source} configuration'
        }

    finally:
        # Clean up temporary file
        if os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)


# Note: Bank statement extraction moved to services/statement_service.py
