from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    """Result of a single anomaly detection rule."""

    risk_score: float  # 0.0 to 100.0
    risk_level: str  # low, medium, high, critical
    reason: str
    rule_id: str
    details: Optional[Dict[str, Any]] = None


class BaseAnomalyRule(ABC):
    """
    Abstract base class for all anomaly detection rules.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for the rule."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the rule."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of what the rule detects."""
        pass

    @abstractmethod
    async def analyze(
        self,
        db: Session,
        entity: Any,
        entity_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[AnomalyResult]:
        """
        Analyze an entity for anomalies.
        """
        pass

    async def _run_ai_audit(
        self,
        db: Session,
        prompt_name: str,
        variables: Dict[str, Any],
        ai_config: Optional[Dict[str, Any]] = None,
        attachment_paths: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Helper to run AI forensic analysis using the prompt service and LiteLLM."""
        if not ai_config:
            return None

        from commercial.prompt_management.services.prompt_service import PromptService
        from litellm import acompletion as completion
        import json
        import logging
        import base64
        import os

        logger = logging.getLogger(__name__)

        try:
            # 1. Get the formatted prompt
            prompt_service = PromptService(db)
            prompt = prompt_service.get_prompt(prompt_name, variables)

            # 2. Prepare LiteLLM configuration
            provider = ai_config.get("provider_name", "ollama")
            model = ai_config.get("model_name", "llama3.2-vision:11b")
            api_key = ai_config.get("api_key")
            api_base = ai_config.get("provider_url")

            logger.info(
                f"AI Audit using provider={provider}, model={model}, api_base={api_base}"
            )

            # Format model for LiteLLM
            litellm_model = f"{provider}/{model}" if "/" not in model else model

            # 3. Construct messages (multimodal if attachments present)
            content = [{"type": "text", "text": prompt}]

            if attachment_paths:
                for path in attachment_paths:
                    if not os.path.exists(path):
                        continue

                    with open(path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode(
                            "utf-8"
                        )
                        mime_type = "image/jpeg"  # Default
                        if path.lower().endswith(".png"):
                            mime_type = "image/png"
                        elif path.lower().endswith(".webp"):
                            mime_type = "image/webp"

                        content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{encoded_string}"
                                },
                            }
                        )

            kwargs = {
                "model": litellm_model,
                "messages": [
                    {"role": "user", "content": content if attachment_paths else prompt}
                ],
                "response_format": {"type": "json_object"},
            }
            if api_key:
                kwargs["api_key"] = api_key
            if api_base and provider != "openai":
                kwargs["api_base"] = api_base

            # 4. Call LLM
            response = await completion(**kwargs)
            content_resp = response.choices[0].message.content

            # 5. Parse result
            if isinstance(content_resp, str):
                try:
                    return json.loads(content_resp)
                except json.JSONDecodeError:
                    # Attempt heal if string has markdown
                    import re

                    match = re.search(r"\{.*\}", content_resp, re.DOTALL)
                    if match:
                        return json.loads(match.group())
            return None

        except Exception as e:
            logger.error(f"AI Audit failed for {prompt_name}: {e}")
            return None
