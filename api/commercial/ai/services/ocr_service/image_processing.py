"""AI vision OCR execution: PDF conversion, LLM-based extraction, and retry logic."""

import asyncio
import base64
import os
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ._shared import _get_ai_config_from_env, logger
from .text_parsers import _extract_json_from_text, _heuristic_parse_text


def _pdf_pages_to_png_bytes(file_path: str, max_pages: int = 5) -> List[bytes]:
    """Convert PDF pages to PNG bytes using PyMuPDF. Returns up to max_pages pages."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        pages_bytes = []
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pages_bytes.append(pix.tobytes("png"))
        doc.close()
        return pages_bytes
    except Exception as e:
        logger.warning(f"Failed to convert PDF to images with PyMuPDF: {e}")
        return []


async def _convert_raw_ocr_to_json(
    raw_content: str,
    model_name: str,
    provider_name: str,
    kwargs: Dict[str, Any],
    db_session: Session,
    custom_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Use LLM to convert raw OCR output (markdown, text, etc.) to structured JSON.
    This is a second-pass conversion when the first OCR attempt returns non-JSON format.
    """
    try:
        logger.info(f"Converting raw OCR output to JSON using {provider_name}/{model_name}")

        if custom_prompt:
            conversion_prompt = custom_prompt.replace("{{raw_content}}", raw_content)
        else:
            fallback_ocr_prompt = (
                "You are a data extraction expert. The following is OCR output from a receipt or invoice "
                "in various formats (markdown, text, etc.). "
                "Convert it to a compact JSON object with these keys: amount, currency, expense_date (YYYY-MM-DD), "
                "category, vendor, tax_rate, tax_amount, total_amount, payment_method, reference_number, notes, "
                "receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). "
                "For receipt_timestamp, use the exact time from the receipt if visible. "
                "If a field is unknown or not present, set it to null. "
                "Return ONLY the JSON object, no markdown, no explanations.\n\n"
                "OCR Output:\n{{raw_content}}"
            )

            try:
                from commercial.prompt_management.services.prompt_service import get_prompt_service

                prompt_service = get_prompt_service(db_session)
                conversion_prompt = prompt_service.get_prompt(
                    name="ocr_data_conversion",
                    variables={"raw_content": raw_content},
                    provider_name=provider_name,
                    fallback_prompt=fallback_ocr_prompt,
                )
            except Exception as e:
                logger.warning(f"Failed to get OCR conversion prompt from service: {e}")
                conversion_prompt = fallback_ocr_prompt.replace("{{raw_content}}", raw_content)

        messages = [{"role": "user", "content": conversion_prompt}]

        if provider_name.lower() == "ollama":
            try:
                import ollama

                base_url = (
                    kwargs.get("base_url") or os.environ.get("OLLAMA_API_BASE") or "http://localhost:11434"
                )
                client = ollama.Client(host=base_url)
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.chat(model=model_name, messages=messages, stream=False),
                    ),
                    timeout=90.0,
                )
                content = response.get("message", {}).get("content", "")
            except Exception as e:
                logger.warning(f"Ollama conversion failed: {type(e).__name__}: {e!r} - {str(e)}")
                return None
        else:
            try:
                from litellm import completion

                if "model" in kwargs:
                    del kwargs["model"]
                kwargs["request_timeout"] = 90.0
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: completion(
                        model=f"{provider_name}/{model_name}", messages=messages, **kwargs
                    ),
                )
                content = response.choices[0].message.content if response.choices else ""
            except Exception as e:
                logger.warning(f"LiteLLM conversion failed: {e}")
                return None

        if not content:
            logger.warning("Conversion LLM returned empty content")
            return None

        parsed = _extract_json_from_text(content)
        if parsed:
            logger.info("Successfully extracted JSON from conversion response")
            return parsed

        logger.warning(f"Conversion response did not contain valid JSON: {content[:100]}")
        return None

    except Exception as e:
        logger.error(f"Failed to convert raw OCR to JSON: {e}")
        return None


async def _retry_ocr_with_ai(
    file_path: Optional[str],
    ai_config: Optional[Dict[str, Any]],
    db_session: Session,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """Retry OCR extraction using AI LLM when initial extraction is poor.
    Returns the parsed result dict or None.
    """
    if not file_path:
        return None

    retry_ai_config = ai_config or _get_ai_config_from_env()
    if not retry_ai_config:
        logger.info("AI LLM retry not available (no config)")
        return None

    try:
        logger.info(f"🔄 Retrying with AI LLM due to {reason}...")
        ai_result = await _run_ocr(file_path, ai_config=retry_ai_config, db_session=db_session)
        if ai_result and isinstance(ai_result, dict) and len(ai_result) > 1:
            return ai_result
        return None
    except Exception as retry_error:
        logger.error(f"AI LLM retry failed: {retry_error}")
        return None


async def _run_ocr(
    file_path: str,
    custom_prompt: Optional[str] = None,
    ai_config: Optional[Dict[str, Any]] = None,
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Run OCR using the configured AI provider. Supports multiple providers via LiteLLM."""
    OCR_VERSION = "2024.01.24.03"

    prompt_service = None
    if db_session:
        try:
            from commercial.prompt_management.services.prompt_service import get_prompt_service

            prompt_service = get_prompt_service(db_session)
        except Exception as e:
            logger.warning(f"Failed to initialize prompt service: {e}")

    try:
        provider_name = None
        model_name = None
        base_url = None
        api_key = None
        ocr_enabled = True

        if ai_config:
            provider_name = ai_config.get("provider", ai_config.get("provider_name"))
            model_name = ai_config.get("model", ai_config.get("model_name"))
            base_url = ai_config.get("api_base", ai_config.get("provider_url"))
            api_key = ai_config.get("api_key")
            ocr_enabled = ai_config.get("ocr_enabled", False)

            if provider_name:
                provider_name = provider_name.lower()

        env_api_base = os.getenv("LLM_API_BASE")
        env_ollama_base = os.getenv("OLLAMA_API_BASE")
        env_api_key = os.getenv("LLM_API_KEY")

        if not provider_name:
            if env_api_base and ("openrouter" in env_api_base or "openrouter.ai" in env_api_base):
                provider_name = "openrouter"
            elif env_api_base and ("api.openai.com" in env_api_base or "openai" in env_api_base):
                provider_name = "openai"
            elif env_api_base and ("anthropic" in env_api_base or "claude" in env_api_base):
                provider_name = "anthropic"
            elif env_api_base and ("google" in env_api_base or "gemini" in env_api_base):
                provider_name = "google"
            elif env_ollama_base or os.getenv("OLLAMA_MODEL"):
                provider_name = "ollama"
            elif env_api_key:
                provider_name = "openai"
            else:
                provider_name = "ollama"

        if not model_name:
            model_name = os.getenv("LLM_MODEL_EXPENSES", os.getenv("OLLAMA_MODEL", "gemma4"))

        if not base_url:
            if provider_name == "ollama":
                base_url = env_ollama_base or env_api_base or "http://localhost:11434"
            elif provider_name in ["anthropic", "google", "bedrock", "vertex_ai"]:
                base_url = None
            else:
                base_url = env_api_base

        if not api_key:
            api_key = env_api_key

        if ai_config:
            logger.info(
                f"[OCR {OCR_VERSION}] Using explicit config with env fallbacks: "
                f"{provider_name}/{model_name} at {base_url}"
            )
        else:
            logger.info(
                f"[OCR {OCR_VERSION}] Using environment fallback: {provider_name}/{model_name} at {base_url}"
            )

        if not ocr_enabled:
            logger.warning(
                f"⚠️ OCR not enabled for provider '{provider_name}'. "
                "Please enable OCR in AI configuration settings."
            )
            return {
                "error": f"OCR not enabled for provider '{provider_name}'.",
                "ocr_not_enabled": True,
            }

        template_name = "expense_receipt_vision_extraction"
        prompt_text = custom_prompt

        fallback_prompt = (
            "You are an OCR parser. Extract key expense fields and respond ONLY with compact JSON. "
            "Required keys: amount, currency, expense_date (YYYY-MM-DD), category, vendor, tax_rate, "
            "tax_amount, total_amount, payment_method, reference_number, notes, "
            "receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). "
            "For receipt_timestamp, extract the exact time from the receipt if visible "
            "(not just the date). Look for timestamps like '14:32', '2:45 PM', etc. "
            "If a field is unknown, set it to null. "
            "IMPORTANT: Return ONLY the JSON object, no markdown formatting, no explanations, "
            "no headers like '**Receipt Data Extraction**'."
        )

        if not prompt_text and prompt_service:
            try:
                prompt_text = prompt_service.get_prompt(
                    name=template_name,
                    provider_name=provider_name,
                    fallback_prompt=fallback_prompt,
                )
            except Exception as e:
                logger.warning(f"Failed to get managed prompt, using fallback: {e}")
                prompt_text = fallback_prompt
        elif not prompt_text:
            prompt_text = fallback_prompt

        if provider_name == "ollama":
            import ollama

            try:
                client = ollama.Client(host=base_url)

                is_pdf = file_path.lower().endswith(".pdf")
                if is_pdf:
                    pdf_pages = _pdf_pages_to_png_bytes(file_path)
                    if not pdf_pages:
                        logger.error(f"Failed to convert PDF to images for Ollama OCR: {file_path}")
                        return {"error": "Failed to convert PDF to images for OCR"}
                    images_bytes = pdf_pages
                    logger.info(f"Converted PDF to {len(images_bytes)} page image(s) for Ollama OCR")
                else:
                    with open(file_path, "rb") as f:
                        images_bytes = [f.read()]

                messages = [
                    {
                        "role": "user",
                        "content": prompt_text,
                        "images": images_bytes,
                    }
                ]

                options = {"temperature": 0.1}
                t0 = time.time()
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.chat(
                            model=model_name,
                            messages=messages,
                            format="json" if custom_prompt is None else None,
                            options=options,
                            stream=False,
                        ),
                    ),
                    timeout=90.0,
                )

                result = response.get("message", {}).get("content", "")
                dt = (time.time() - t0) * 1000
                processing_time_ms = int(dt)
                logger.info(f"Ollama OCR raw result length={len(result)} duration_ms={dt:.0f}")

                if prompt_service and not custom_prompt:
                    prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=bool(result),
                        processing_time_ms=processing_time_ms,
                        token_count=len(result) // 4,
                        error_message=None if result else "Empty result",
                    )

                if result:
                    parsed = _extract_json_from_text(result)
                    if parsed is not None:
                        return parsed
                    return {"raw": result}
                return {}

            except Exception as e:
                logger.error(f"Ollama direct OCR processing failed: {type(e).__name__}: {e!r} - {str(e)}")

                if prompt_service and not custom_prompt:
                    prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=False,
                        processing_time_ms=0,
                        token_count=0,
                        error_message=f"{type(e).__name__}: {str(e) or repr(e)}",
                    )

                return {"error": f"{type(e).__name__}: {str(e)}"}

        # Use LiteLLM for other providers (OpenAI, Anthropic, Google, etc.)
        t0 = time.time()
        try:
            from litellm import completion
            import litellm

            litellm.suppress_debug_info = True

            if provider_name == "openai":
                litellm_model = model_name
            elif provider_name == "anthropic":
                litellm_model = f"anthropic/{model_name}"
            elif provider_name == "google":
                litellm_model = f"google/{model_name}"
            elif provider_name == "openrouter":
                if "gpt-oss-20b" in model_name or "free" in model_name:
                    logger.warning(
                        f"Model {model_name} may not support vision. "
                        "Consider using a vision-capable model like 'openai/gpt-4-vision-preview' "
                        "or 'anthropic/claude-3-haiku'"
                    )
                    return {
                        "error": (
                            f"Model '{model_name}' does not support vision capabilities. "
                            "Please configure a vision-capable model like 'openai/gpt-4-vision-preview', "
                            "'anthropic/claude-3-haiku', or 'google/gemini-pro-vision'."
                        )
                    }
                litellm_model = f"openrouter/{model_name}"
            else:
                litellm_model = f"{provider_name}/{model_name}"

            kwargs: Dict[str, Any] = {"model": litellm_model}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url and provider_name != "openai":
                kwargs["api_base"] = base_url

            from core.utils.file_validation import validate_file_path

            try:
                safe_path = validate_file_path(file_path)
            except ValueError as e:
                logger.error(str(e))
                return {"error": f"Invalid file path: {e}"}

            is_pdf = file_path.lower().endswith(".pdf")

            if file_path.lower().endswith(".png"):
                image_format = "png"
            elif file_path.lower().endswith(".jpg") or file_path.lower().endswith(".jpeg"):
                image_format = "jpeg"
            elif file_path.lower().endswith(".webp"):
                image_format = "webp"
            else:
                image_format = "png"

            prompt = prompt_text

            if is_pdf and provider_name == "anthropic":
                with open(safe_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode("utf-8")
                file_content_blocks = [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": image_data,
                        },
                    }
                ]
            elif is_pdf:
                pdf_pages = _pdf_pages_to_png_bytes(safe_path)
                if not pdf_pages:
                    logger.error(f"Failed to convert PDF to images for OCR: {safe_path}")
                    return {"error": "Failed to convert PDF to images for OCR"}
                logger.info(f"Converted PDF to {len(pdf_pages)} page image(s) for {provider_name} OCR")
                file_content_blocks = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64.b64encode(page_bytes).decode('utf-8')}"
                        },
                    }
                    for page_bytes in pdf_pages
                ]
            else:
                with open(safe_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode("utf-8")
                file_content_blocks = [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_format};base64,{image_data}"},
                    }
                ]

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *file_content_blocks,
                    ],
                }
            ]

            t0 = time.time()
            kwargs["request_timeout"] = 90.0
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: completion(messages=messages, **kwargs),
            )
            dt = (time.time() - t0) * 1000
            processing_time_ms = int(dt)
            logger.info(f"OCR via LiteLLM result duration_ms={dt:.0f}")

            total_tokens = 0
            if response and hasattr(response, "usage") and response.usage:
                total_tokens = getattr(response.usage, "total_tokens", 0)

            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content

                if prompt_service and not custom_prompt:
                    try:
                        prompt_service.log_usage(
                            template_name=template_name,
                            provider_name=provider_name,
                            model_name=model_name,
                            success=True,
                            processing_time_ms=processing_time_ms,
                            token_count=total_tokens,
                            error_message=None,
                        )
                        logger.info("Successfully logged usage for OCR success")
                    except Exception as log_error:
                        logger.error(f"Failed to log usage: {log_error}")

                if isinstance(content, str):
                    parsed = _extract_json_from_text(content)
                    if parsed is not None:
                        return parsed

                    logger.info("First-pass OCR returned non-JSON format, attempting second-pass conversion...")
                    json_conversion_result = await _convert_raw_ocr_to_json(
                        content, model_name, provider_name, kwargs, db_session
                    )
                    if json_conversion_result and "error" not in json_conversion_result:
                        logger.info("Successfully converted raw OCR output to JSON via second-pass LLM")
                        return json_conversion_result

                    logger.info("Second-pass LLM conversion failed, attempting heuristic parsing...")
                    heuristic_result = _heuristic_parse_text(content)
                    if heuristic_result:
                        logger.info(f"Heuristic parsing extracted {len(heuristic_result)} fields")
                        return heuristic_result

                    logger.warning("All parsing methods failed, returning raw content")
                    return {"raw": content}
                else:
                    return {"raw": str(content)}
            else:
                if prompt_service and not custom_prompt:
                    try:
                        prompt_service.log_usage(
                            template_name=template_name,
                            provider_name=provider_name,
                            model_name=model_name,
                            success=False,
                            processing_time_ms=processing_time_ms,
                            token_count=total_tokens,
                            error_message="No response from AI provider",
                        )
                    except Exception:
                        logger.warning("Failed to log OCR usage metrics", exc_info=True)
                return {"error": "No response from AI provider"}

        except ImportError:
            return {"error": "LiteLLM not available for non-Ollama providers"}
        except Exception as e:
            logger.error(f"LiteLLM exception caught: {e}")
            if prompt_service and not custom_prompt:
                try:
                    prompt_service.log_usage(
                        template_name=template_name,
                        provider_name=provider_name,
                        model_name=model_name,
                        success=False,
                        processing_time_ms=int((time.time() - t0) * 1000),
                        token_count=0,
                        error_message=str(e),
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log failure usage: {log_error}")

            logger.error(f"LiteLLM OCR processing failed: {e}")
            error_msg = str(e)
            if "No endpoints found that support image input" in error_msg:
                logger.warning(
                    f"Vision model '{litellm_model}' does not support image input. "
                    "Consider switching to a vision-capable model."
                )
                return {
                    "error": (
                        f"Vision model '{model_name}' does not support image input. "
                        "Please configure a vision-capable model like 'gpt-4-vision-preview' or 'claude-3-haiku'."
                    )
                }
            return {"error": f"LiteLLM OCR failed: {error_msg}"}

    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return {"error": str(e)}

    return {"error": "Unknown error (execution fell through)"}
