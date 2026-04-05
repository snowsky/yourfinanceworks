# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import httpx
import logging
import os

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.models.models_per_tenant import AIConfig, ClientNote
from core.utils.feature_gate import require_feature
from commercial.ai.services.ai_config_service import AIConfigService

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

router = APIRouter()


@router.post("/summarize-client-notes/{client_id}")
@require_feature("ai_chat")
async def summarize_client_notes(
    client_id: int,
    language: str = "English",
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Summarize client notes using AI
    """
    try:
        # Get client notes
        notes = db.query(ClientNote).filter(ClientNote.client_id == client_id).all()

        if not notes:
            logger.info(f"Summarize Client Notes: No notes found for client {client_id}")
            return {
                "success": False,
                "message": "No notes found to summarize."
            }

        # Combine notes into a single text
        notes_text = "\n".join([f"- {note.note} (Date: {note.created_at.strftime('%Y-%m-%d')})" for note in notes])
        logger.info(f"Summarize Client Notes: Found {len(notes)} notes for client {client_id}")
        logger.info(f"Summarize Client Notes: Notes text: {notes_text}")

        # Get AI config
        ai_config = db.query(AIConfig).filter(
            AIConfig.is_default == True,
            AIConfig.is_active == True
        ).first()

        if not ai_config:
            # Fallback to single active config
            active_configs = db.query(AIConfig).filter(AIConfig.is_active == True).all()
            if len(active_configs) == 1:
                config = active_configs[0]
                config.is_default = True
                db.commit()
                ai_config = config

        if not ai_config:
            # Fallback to environment variables
            from commercial.ai.services.ai_config_service import AIConfigService
            env_config = AIConfigService.get_ai_config(db, component="chat", require_ocr=False)

            if not env_config:
                 return {
                    "success": False,
                    "error": "No AI configuration found."
                }

            class EnvAIConfig:
                def __init__(self, config_dict):
                    self.provider_name = config_dict["provider_name"]
                    self.model_name = config_dict["model_name"]
                    self.api_key = config_dict.get("api_key")
                    self.provider_url = config_dict.get("provider_url")
                    self.is_active = True
                    self.is_default = True
                    self.max_tokens = 1000
                    self.temperature = 0.5

            ai_config = EnvAIConfig(env_config)

        # Construct prompt
        prompt = f"""You are a helpful assistant. Please summarize the following client notes for me in {language}. Even if the notes are brief, provide a summary or restatement of the content in {language}.

Client Notes:
{notes_text}

Summary ({language}):"""

        logger.info(f"Summarize Client Notes: Using provider: {ai_config.provider_name}, model: {ai_config.model_name}, language: {language}")
        logger.info(f"Summarize Client Notes: Generated prompt: {prompt}")

        # Call AI provider (Reuse logic from chat or use litellm if available/preferred, here copying structure for consistency)
        ai_response = ""

        if ai_config.provider_name == "ollama":
            payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "num_predict": ai_config.max_tokens or 4096,
                    "temperature": ai_config.temperature or 0.1
                }
            }
            if ai_config.provider_url:
                url = f"{ai_config.provider_url}/api/chat"
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=60.0)
                    response.raise_for_status()
                    ai_response = response.json()["message"]["content"]

        elif ai_config.provider_name == "openai":
            headers = {
                "Authorization": f"Bearer {ai_config.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": ai_config.max_tokens or 4096,
                "temperature": ai_config.temperature or 0.1
            }
            url = "https://api.openai.com/v1/chat/completions"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                ai_response = response.json()["choices"][0]["message"]["content"]

        elif ai_config.provider_name == "anthropic":
             headers = {
                "x-api-key": ai_config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
             payload = {
                "model": ai_config.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": ai_config.max_tokens or 4096,
                "temperature": ai_config.temperature or 0.1
            }
             url = "https://api.anthropic.com/v1/messages"
             async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                ai_response = response.json()["content"][0]["text"]

        else:
             # Basic fallback if provider not explicitly matched but exists (could use litellm generic)
             return {
                "success": False,
                "error": f"Unsupported provider for summarization: {ai_config.provider_name}"
            }

        return {
            "success": True,
            "data": {
                "summary": ai_response,
                "provider": ai_config.provider_name,
                "model": ai_config.model_name
            }
        }

    except Exception as e:
        logger.error(f"Summarize Client Notes error: {repr(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
