"""
Document type classification for batch processing.

Uses filename heuristics first, then falls back to LangChain + LLM
classification when the filename is ambiguous.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class BatchClassificationMixin:
    """Mixin providing document type detection and LLM-based classification."""

    DOCUMENT_TYPE_TOPICS = {
        'invoice': 'invoices_ocr',
        'expense': 'expense_ocr',
        'statement': 'bank_statements_ocr'
    }

    async def determine_document_type(
        self, filename: str, content: Optional[bytes] = None
    ) -> str:
        filename_lower = filename.lower()

        invoice_keywords = ['invoice', 'inv', 'bill']
        expense_keywords = ['expense', 'receipt', 'exp']
        statement_keywords = ['statement', 'bank', 'stmt']

        if any(keyword in filename_lower for keyword in invoice_keywords):
            doc_type = 'invoice'
        elif any(keyword in filename_lower for keyword in expense_keywords):
            doc_type = 'expense'
        elif any(keyword in filename_lower for keyword in statement_keywords):
            doc_type = 'statement'
        else:
            if content:
                try:
                    doc_type = await self._classify_with_langchain(filename, content)
                    logger.info(f"LangChain classified '{filename}' as '{doc_type}'")
                except Exception as e:
                    logger.warning(
                        f"LangChain classification failed for '{filename}': {e}. "
                        f"Defaulting to 'expense'"
                    )
                    doc_type = 'expense'
            else:
                logger.debug(
                    f"Filename '{filename}' is uncertain and no content available. "
                    f"Defaulting to 'expense'"
                )
                doc_type = 'expense'

        logger.debug(f"Determined document type '{doc_type}' for file: {filename}")
        return doc_type

    async def _classify_with_langchain(self, filename: str, content: bytes) -> str:
        import tempfile
        import os
        from pathlib import Path
        from commercial.ai.services.ai_config_service import AIConfigService

        ai_config = AIConfigService.get_ai_config(self.db, component="ocr", require_ocr=False)

        if not ai_config:
            logger.warning(
                "No AI configuration available for LangChain classification "
                "(neither from core.settings nor environment variables)"
            )
            raise Exception("No AI configuration available")

        file_ext = Path(filename).suffix.lower()
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(content)
                temp_file = tmp.name

            documents = self._load_document_with_langchain(temp_file)
            if not documents:
                raise Exception("Failed to extract text from document")

            text_content = "\n\n".join([doc.page_content for doc in documents[:3]])[:2000]
            doc_type = await self._classify_text_with_llm(text_content, ai_config)
            return doc_type

        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def _load_document_with_langchain(self, file_path: str) -> List:
        try:
            from langchain_community.document_loaders import (
                PyPDFLoader,
                PyMuPDFLoader,
                CSVLoader,
            )
        except ImportError:
            logger.warning("LangChain not available for document loading")
            raise Exception("LangChain not available")

        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == '.pdf':
                try:
                    loader = PyMuPDFLoader(file_path)
                except Exception:
                    loader = PyPDFLoader(file_path)
                documents = loader.load()
            elif file_ext == '.csv':
                loader = CSVLoader(file_path)
                documents = loader.load()
            else:
                logger.warning(f"Unsupported file type for text extraction: {file_ext}")
                return []

            return documents

        except Exception as e:
            logger.error(f"Failed to load document with LangChain: {e}")
            raise

    async def _classify_text_with_llm(
        self, text: str, ai_config: Dict[str, Any]
    ) -> str:
        try:
            from litellm import completion
        except ImportError:
            logger.warning("LiteLLM not available for classification")
            raise Exception("LiteLLM not available")

        provider_name = ai_config.get("provider_name", "ollama")
        model_name = ai_config.get("model_name", "llama3.2-vision:11b")
        base_url = ai_config.get("provider_url")
        api_key = ai_config.get("api_key")

        classification_prompt = f"""Analyze the following document text and classify it as one of these types:
- invoice: A document requesting payment for goods/services provided (bills, invoices, bills of sale)
- expense: A receipt or expense record showing a purchase or payment made (receipts, purchase records)
- statement: A bank or financial statement showing account transactions (bank statements, account summaries)

Document text (first 2000 characters):
{text[:2000]}

Respond with ONLY one word: invoice, expense, or statement. Do not include any explanation or additional text."""

        if provider_name == "ollama":
            model = model_name
        elif provider_name == "openai":
            model = model_name
        elif provider_name == "anthropic":
            model = f"anthropic/{model_name}"
        elif provider_name == "openrouter":
            model = f"openrouter/{model_name}"
        else:
            model = f"{provider_name}/{model_name}"

        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": classification_prompt}],
            "max_tokens": 10,
            "temperature": 0.1,
        }

        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url

        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: completion(**kwargs))

        if hasattr(response, 'choices') and len(response.choices) > 0:
            classification = response.choices[0].message.content.strip().lower()
        else:
            classification = str(response).strip().lower()

        if 'invoice' in classification:
            return 'invoice'
        elif 'expense' in classification or 'receipt' in classification:
            return 'expense'
        elif 'statement' in classification:
            return 'statement'
        else:
            logger.warning(
                f"Unclear LLM classification: '{classification}'. Defaulting to 'expense'"
            )
            return 'expense'
