import logging
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from commercial.ai.services.ai_config_service import AIConfigService
from commercial.prompt_management.services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)

class EmailClassificationService:
    """Service for AI-powered email classification to detect receipts/expenses."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def classify_email(
        self, 
        subject: str, 
        body: str, 
        sender: str,
        has_attachments: bool = False
    ) -> Dict[str, Any]:
        """
        Classify if email contains a receipt, invoice, or expense.
        
        Args:
            subject: Email subject line
            body: Email body text (will be truncated for API efficiency)
            sender: Email sender address
            has_attachments: Whether email has attachments
            
        Returns:
            {
                "is_expense": bool,
                "confidence": float (0.0-1.0),
                "reasoning": str
            }
        """
        try:
            logger.info(f"[DEBUG] classify_email called: subject='{subject}', sender='{sender}', has_attachments={has_attachments}")
            
            # Get AI configuration
            ai_config = AIConfigService.get_ai_config(self.db, "ocr")
            logger.info(f"[DEBUG] AI config result: {ai_config}")
            
            if not ai_config:
                logger.warning("No AI config available for email classification")
                return {
                    "is_expense": False,
                    "confidence": 0.0,
                    "reasoning": "AI configuration not available"
                }
            
            # Truncate body for efficiency (first 1000 chars usually enough)
            body_preview = body[:1000] if body else ""
            
            # Build classification prompt
            prompt = self._build_classification_prompt(subject, body_preview, sender, has_attachments, ai_config)
            
            # Call LLM
            result = await self._call_llm_for_classification(prompt, ai_config)
            
            return result
            
        except Exception as e:
            logger.error(f"Email classification failed: {e}", exc_info=True)
            return {
                "is_expense": False,
                "confidence": 0.0,
                "reasoning": f"Classification error: {str(e)}"
            }
    
    def _build_classification_prompt(
        self, 
        subject: str, 
        body: str, 
        sender: str,
        has_attachments: bool,
        ai_config: Dict[str, Any]
    ) -> str:
        """Build the classification prompt for the LLM."""
        try:
            prompt_service = get_prompt_service(self.db)
            prompt = prompt_service.get_prompt(
                name="email_expense_classification",
                variables={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "has_attachments": has_attachments
                },
                provider_name=ai_config.get("provider_name"),
                fallback_prompt="""Analyze this email and determine if it contains a receipt, invoice, expense, or purchase confirmation.

Subject: {{subject}}
From: {{sender}}
Has Attachments: {{has_attachments}}

Email Body Preview:
{{body}}

Common expense email patterns:
- Receipt from stores/restaurants (e.g., "Your receipt from...", "Thank you for your purchase")
- Invoice notifications (e.g., "Invoice #...", "Payment confirmation")
- Subscription/service charges (e.g., "Your monthly bill", "Payment processed")
- Delivery/ride receipts (e.g., Uber, DoorDash, Amazon)
- Utility bills, insurance payments, etc.

NOT expense emails:
- Marketing/promotional emails
- Newsletters
- Account notifications (password reset, security alerts)
- Social media notifications
- General correspondence

Respond with ONLY valid JSON in this exact format:
{
  "is_expense": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation (max 100 chars)"
}"""
            )
            return prompt
        except Exception as e:
            logger.warning(f"Failed to get email classification prompt from service: {e}")
            # Fallback to hardcoded template
            return f"""Analyze this email and determine if it contains a receipt, invoice, expense, or purchase confirmation.

Subject: {subject}
From: {sender}
Has Attachments: {has_attachments}

Email Body Preview:
{body}

Common expense email patterns:
- Receipt from stores/restaurants (e.g., "Your receipt from...", "Thank you for your purchase")
- Invoice notifications (e.g., "Invoice #...", "Payment confirmation")
- Subscription/service charges (e.g., "Your monthly bill", "Payment processed")
- Delivery/ride receipts (e.g., Uber, DoorDash, Amazon)
- Utility bills, insurance payments, etc.

NOT expense emails:
- Marketing/promotional emails
- Newsletters
- Account notifications (password reset, security alerts)
- Social media notifications
- General correspondence

Respond with ONLY valid JSON in this exact format:
{{
  "is_expense": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation (max 100 chars)"
}}"""
    
    async def _call_llm_for_classification(
        self, 
        prompt: str, 
        ai_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call LLM API for classification."""
        try:
            import asyncio
            from litellm import completion
            
            # Prepare LLM request
            provider_name = ai_config.get("provider_name", "ollama")
            model_name = ai_config.get("model_name")
            
            # Build model string for litellm
            if provider_name == "ollama":
                model = f"ollama/{model_name}"
                api_base = ai_config.get("provider_url", "http://localhost:11434")
            elif provider_name == "openai":
                model = model_name
                api_base = ai_config.get("provider_url", "https://api.openai.com/v1")
            else:
                model = f"{provider_name}/{model_name}"
                api_base = ai_config.get("provider_url")
            
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Low temperature for consistent classification
                "max_tokens": 200,   # Short response expected
            }
            
            if api_base:
                kwargs["api_base"] = api_base
            
            if ai_config.get("api_key"):
                kwargs["api_key"] = ai_config["api_key"]
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: completion(**kwargs))
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            result = self._extract_json_from_response(content)
            
            # Validate result
            if not isinstance(result, dict):
                raise ValueError("LLM response is not a valid JSON object")
            
            # Ensure required fields
            result.setdefault("is_expense", False)
            result.setdefault("confidence", 0.0)
            result.setdefault("reasoning", "Unknown")
            
            # Clamp confidence to 0-1 range
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            
            logger.info(
                f"Email classified: is_expense={result['is_expense']}, "
                f"confidence={result['confidence']:.2f}, reason={result['reasoning']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"LLM classification call failed: {e}", exc_info=True)
            return {
                "is_expense": False,
                "confidence": 0.0,
                "reasoning": f"LLM error: {str(e)[:50]}"
            }
    
    def _extract_json_from_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        import re
        
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Try direct JSON parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON object in text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except:
                pass
        
        return None
