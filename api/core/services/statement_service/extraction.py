"""LLM-based bank transaction extraction classes."""
import contextlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from sqlalchemy.orm import Session
from commercial.ai.services.ocr_service import track_ai_usage, track_ocr_usage, parse_number
from commercial.prompt_management.services.prompt_service import get_prompt_service
from core.utils.file_validation import validate_file_path

from ._shared import (
    BankLLMUnavailableError,
    Document,
    LANGCHAIN_AVAILABLE,
    OllamaCallbackHandler,
    PromptTemplate,
    RecursiveCharacterTextSplitter,
    TransactionModel,
    _normalize_date,
    pd,
)

# Conditional imports that require LANGCHAIN_AVAILABLE
if LANGCHAIN_AVAILABLE:
    from langchain_community.document_loaders import (
        PyPDFLoader,
        PyMuPDFLoader,
        PDFMinerLoader,
        PyPDFium2Loader,
        PDFPlumberLoader,
        UnstructuredPDFLoader,
        CSVLoader,
    )
    from langchain_ollama import OllamaLLM, ChatOllama

logger = logging.getLogger(__name__)


class UniversalBankTransactionExtractor:
    """
    Universal bank transaction extractor that supports multiple LLM providers via LiteLLM.
    Supports: OpenAI, OpenRouter, Anthropic, Google, Ollama, and other LiteLLM-compatible providers.
    Enhanced with OCR fallback capability for scanned documents.
    """

    def __init__(self,
                 ai_config: Dict[str, Any],
                 db_session: Session,
                 temperature: float = 0.1,
                 chunk_size: int = 6000,
                 chunk_overlap: int = 150,
                 request_timeout: int = 120,
                 prompt_name: str = "bank_transaction_extraction",
                 card_type: str = "debit"):
        """
        Initialize the extractor with AI configuration

        Args:
            ai_config: AI configuration dict with provider_name, model_name, api_key, provider_url
            db_session: Database session for prompt management
            temperature: Temperature for LLM responses
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            request_timeout: Timeout for requests
        """
        if not LANGCHAIN_AVAILABLE:
            logger.error("LangChain is not available for UniversalBankTransactionExtractor. Bank statement processing will be limited.")
            # Don't raise an error, just log it and continue with limited functionality
            self.langchain_available = False
        else:
            self.langchain_available = True

        self.ai_config = ai_config
        self.provider_name = ai_config.get("provider_name", "openai")
        self.model_name = ai_config.get("model_name", "gpt-4")
        self.api_key = ai_config.get("api_key")
        self.provider_url = ai_config.get("provider_url")
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.db_session = db_session
        self.prompt_name = prompt_name
        self.prompt_service = get_prompt_service(db_session)
        self.card_type = card_type
        self.detected_card_type = card_type if card_type != "auto" else "debit"  # Default fallback
        self.statement_metadata = {}  # Store year, period, etc.

        logger.info(f"🚀 Initializing UniversalBankTransactionExtractor: {self.provider_name} / {self.model_name}, prompt_name={self.prompt_name}")

        # Test provider connection
        # self._test_provider_connection()

        # Initialize enhanced PDF text extractor with OCR fallback
        try:
            from commercial.ai.services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
            self.text_extractor = EnhancedPDFTextExtractor(ai_config)
            logger.info("✅ Enhanced PDF text extractor with OCR fallback initialized")
        except ImportError as e:
            logger.warning(f"Enhanced PDF extractor not available: {e}")
            self.text_extractor = None

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            keep_separator=False
        )

        # Available PDF loaders (fallback when enhanced extractor not available)
        self.pdf_loaders = {}
        if LANGCHAIN_AVAILABLE:
            try:
                self.pdf_loaders['pypdf'] = {
                    'class': PyPDFLoader,
                    'description': 'Fast, basic PDF text extraction',
                    'best_for': 'Simple text-based PDFs'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['pymupdf'] = {
                    'class': PyMuPDFLoader,
                    'description': 'High-quality text extraction with metadata',
                    'best_for': 'Most PDF types, good balance of speed and quality'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['pdfplumber'] = {
                    'class': PDFPlumberLoader,
                    'description': 'Excellent for tables and structured data',
                    'best_for': 'Bank statements with tables'
                }
            except Exception:
                pass

        # Setup prompts
        self.extraction_prompt = self._create_extraction_prompt()

    def _test_provider_connection(self):
        """Test connection to the configured provider"""
        try:
            from litellm import completion

            # Prepare model name and parameters for LiteLLM
            model_name = self._format_model_name()
            kwargs = self._prepare_litellm_kwargs()

            # Simple test call
            kwargs.update({
                "model": model_name,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
                "temperature": 0.1
            })

            logger.info(f"🔍 Testing connection to {self.provider_name} with model {model_name}")
            response = completion(**kwargs)

            if response and response.choices:
                logger.info(f"✅ Successfully connected to {self.provider_name}")
            else:
                raise Exception("No response received")

        except Exception as e:
            logger.error(f"❌ Failed to connect to {self.provider_name}: {e}")
            raise Exception(f"Provider connection failed: {e}")

    def _format_model_name(self) -> str:
        """Format model name for LiteLLM based on provider"""
        if self.provider_name == "ollama":
            return f"ollama/{self.model_name}"
        elif self.provider_name == "openrouter":
            return f"openrouter/{self.model_name}"  # OpenRouter requires "openrouter/" prefix for proper routing
        else:
            return self.model_name  # OpenAI, Anthropic, etc. use model names directly

    def _prepare_litellm_kwargs(self) -> Dict[str, Any]:
        """Prepare LiteLLM kwargs based on provider"""
        kwargs = {}

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.provider_url:
            kwargs["api_base"] = self.provider_url

        # Provider-specific configurations
        if self.provider_name == "ollama":
            # If provider_url is missing or localhost/127.0.0.1, check for environment override
            if not self.provider_url or "localhost" in self.provider_url or "127.0.0.1" in self.provider_url:
                env_api_base = os.environ.get("OLLAMA_API_BASE") or os.environ.get("LLM_API_BASE")
                if env_api_base:
                    kwargs["api_base"] = env_api_base
                elif not self.provider_url:
                    kwargs["api_base"] = "http://localhost:11434"

        return kwargs

    def _create_extraction_prompt(self) -> PromptTemplate:
        """Create extraction prompt optimized for universal providers"""

        # 0. Check for explicit prompt override in ai_config
        prompt_override = self.ai_config.get("prompt_override")
        if prompt_override:
            logger.info(f"Using prompt override for {self.prompt_name}")
            return PromptTemplate(
                template=prompt_override,
                input_variables=["text"]
            )

        # Try to get prompt from service
        try:
            from core.constants.default_prompts import BANK_TRANSACTION_EXTRACTION_PROMPT
            prompt_template = self.prompt_service.get_prompt(
                name=self.prompt_name,
                variables={
                    "text": "{{text}}",
                    "card_type": "{{card_type}}",
                    "statement_context": "{{statement_context}}"
                },  # Preserve placeholders for late binding
                provider_name=self.provider_name,
                fallback_prompt=BANK_TRANSACTION_EXTRACTION_PROMPT
            )

            # Create PromptTemplate object for compatibility
            return PromptTemplate(
                template=prompt_template,
                input_variables=["text", "card_type", "statement_context"]
            )

        except Exception as e:
            logger.warning(f"Failed to get bank transaction extraction prompt from service: {e}")
            from core.constants.default_prompts import BANK_TRANSACTION_EXTRACTION_PROMPT

            return PromptTemplate(
                template=BANK_TRANSACTION_EXTRACTION_PROMPT,
                input_variables=["text"]
            )

    def _detect_card_type_from_text(self, text: str) -> str:
        """Detect card type using keyword analysis on the raw statement text.
        Returns 'credit', 'debit', or '' if inconclusive."""
        text_lower = text.lower()
        credit_signals = [
            'credit card', 'available credit', 'credit limit', 'minimum payment',
            'minimum due', 'payment due', 'statement balance', 'revolving credit',
            'visa credit', 'mastercard credit', 'amex', 'american express',
        ]
        debit_signals = [
            'checking account', 'current account', 'savings account', 'chequing',
            'debit card', 'available balance', 'overdraft', 'chequing account',
        ]
        credit_score = sum(1 for s in credit_signals if s in text_lower)
        debit_score = sum(1 for s in debit_signals if s in text_lower)
        if credit_score > debit_score:
            return "credit"
        if debit_score > credit_score:
            return "debit"
        return ""

    def _detect_card_type(self, text: str) -> str:
        """Detect if statement is for a credit or debit card"""
        # First try fast text-based detection on the raw statement text
        text_result = self._detect_card_type_from_text(text)
        if text_result:
            logger.info(f"🔍 Text-based card type detection: {text_result}")
            return text_result

        # Fall back to LLM-based detection
        try:
            from core.constants.default_prompts import BANK_STATEMENT_CLASSIFICATION_PROMPT
            from litellm import completion

            model_name = self._format_model_name()
            kwargs = self._prepare_litellm_kwargs()

            prompt = BANK_STATEMENT_CLASSIFICATION_PROMPT.replace("{{text}}", text[:4000])

            kwargs.update({
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.0
            })

            logger.info(f"🔍 Detecting card type via LLM for {self.provider_name}")
            response = completion(**kwargs)

            if response and response.choices:
                result_text = response.choices[0].message.content
                # Simple parsing for 'credit' or 'debit'
                if '"card_type": "credit"' in result_text.lower() or "'card_type': 'credit'" in result_text.lower():
                    return "credit"
                elif '"card_type": "debit"' in result_text.lower() or "'card_type': 'debit'" in result_text.lower():
                    return "debit"

                # Fallback to keyword search in result
                if "credit" in result_text.lower():
                    return "credit"
                if "debit" in result_text.lower():
                    return "debit"

            return "debit"  # Fallback
        except Exception as e:
            logger.warning(f"Detection failed: {e}")
            return "debit"

    def _render_extraction_prompt(self, text: str) -> str:
        """Safely render extraction prompt with metadata context injection"""
        prompt_info = "Fallback"
        if hasattr(self.extraction_prompt, 'name') and self.extraction_prompt.name:
            prompt_info = f"DB Prompt '{self.extraction_prompt.name}'"
            if hasattr(self.extraction_prompt, 'version'):
                prompt_info += f" (v{self.extraction_prompt.version})"
        elif hasattr(self, 'prompt_name'):
            prompt_info = f"Prompt '{self.prompt_name}'"

        if hasattr(self.extraction_prompt, 'format') or hasattr(self.extraction_prompt, 'template'):
            # This handles both our dummy class and LangChain's if used safely
            try:
                # First try safe replacement
                template_str = getattr(self.extraction_prompt, 'template', "")
                if template_str:
                    placeholder = "{{statement_context}}"
                    has_placeholder = placeholder in template_str or "{statement_context}" in template_str

                    # Inject metadata context if available
                    context_str = ""
                    if self.statement_metadata:
                        year = self.statement_metadata.get('year')
                        period = self.statement_metadata.get('period')
                        if year or period:
                            context_str = f"STATEMENT CONTEXT:\n"
                            if year:
                                context_str += f"- Year: {year}\n"
                            if period:
                                context_str += f"- Statement Period: {period}\n"

                    logger.info(f"📄 Using {prompt_info} (Placeholder: {'FOUND' if has_placeholder else 'MISSING'})")

                    if context_str:
                        if has_placeholder:
                            logger.info(f"💉 Injecting context: {context_str.strip().replace(chr(10), ', ')}")
                        else:
                            logger.warning(f"⚠️ Placeholder {placeholder} missing in {prompt_info}! Prepending context as safety.")
                            # Safety measure: prepend context to ensure AI sees it even if placeholder is missing
                            template_str = f"{context_str}\n\n{template_str}"
                    else:
                        logger.warning("⚠️ No metadata context available for injection!")

                    rendered = template_str.replace("{{text}}", text).replace("{text}", text) \
                                       .replace("{{card_type}}", self.card_type).replace("{card_type}", self.card_type) \
                                       .replace("{{statement_context}}", context_str).replace("{statement_context}", context_str)
                    return rendered
                return self.extraction_prompt.format(text=text)
            except Exception:
                # Fallback to whatever the object provides
                return str(self.extraction_prompt).replace("{text}", text)
        return str(self.extraction_prompt).replace("{text}", text)

    def _extract_statement_metadata(self, text: str):
        """Perform a first-pass LLM call to extract statement metadata (year, period, card_type)"""
        try:
            logger.info("🧠 [AI SMARTS] Running first-pass metadata extraction...")
            from litellm import completion

            # Use only the first 4000 characters for metadata extraction to be efficient
            header_text = text[:4000]

            model_name = self._format_model_name()
            kwargs = self._prepare_litellm_kwargs()

            from core.constants.default_prompts import BANK_STATEMENT_METADATA_EXTRACTION_PROMPT

            # Try to get metadata prompt from service
            try:
                prompt_template = self.prompt_service.get_prompt(
                    name="bank_statement_metadata_extraction",
                    variables={"header_text": "{{header_text}}"},
                    provider_name=self.provider_name,
                    fallback_prompt=BANK_STATEMENT_METADATA_EXTRACTION_PROMPT
                )
                prompt = prompt_template.replace("{{header_text}}", header_text).replace("{header_text}", header_text)
            except Exception as e:
                logger.warning(f"Failed to get metadata extraction prompt from service: {e}")
                prompt = BANK_STATEMENT_METADATA_EXTRACTION_PROMPT.replace("{{header_text}}", header_text)

            kwargs.update({
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.0
            })

            logger.info(f"🔍 Extracting statement metadata using {self.provider_name}...")
            response = completion(**kwargs)

            if response and response.choices:
                result_text = response.choices[0].message.content
                logger.debug(f"📄 RAW METADATA RESPONSE from {self.provider_name}: {result_text}")
                
                # Basic JSON extraction from response - handles conversational filler
                match = re.search(r'(\{[\s\S]*\})', result_text)
                if match:
                    try:
                        json_str = match.group(0)
                        # Clean up common OCR/LLM hallucinations in JSON
                        json_str = json_str.replace('```json', '').replace('```', '')
                        self.statement_metadata = json.loads(json_str)
                        
                        logger.info(f"✨ [AI SMARTS] Successfully detected statement metadata:")
                        logger.info(f"   - Year: {self.statement_metadata.get('year')}")
                        logger.info(f"   - Period: {self.statement_metadata.get('period')}")
                        logger.info(f"   - Type: {self.statement_metadata.get('card_type')}")
                        logger.info(f"   - Bank: {self.statement_metadata.get('bank_name')}")

                        # Update card_type if it was auto and we detected it here
                        if self.card_type == "auto" and self.statement_metadata.get('card_type'):
                            self.detected_card_type = self.statement_metadata['card_type']
                            self.card_type = self.detected_card_type
                            logger.info(f"   - Card type set to: {self.card_type}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"🔍 [AI SMARTS] Found JSON-like block but it was invalid: {e}")
                        logger.info(f"📄 RAW RESPONSE THAT FAILED PARSING: {result_text}")
                else:
                    logger.warning("🔍 [AI SMARTS] Metadata extraction LLM responded, but no JSON was found.")
                    logger.info(f"📄 RAW METADATA RESPONSE: {result_text}")
            else:
                logger.warning("🔍 [AI SMARTS] No response received from metadata extraction LLM.")
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            # Non-critical failure, we continue with empty metadata

        # If card_type is still 'auto' after LLM extraction, try text-based detection
        if self.card_type == "auto":
            text_detected = self._detect_card_type_from_text(text)
            if text_detected:
                self.detected_card_type = text_detected
                self.card_type = text_detected
                logger.info(f"🔍 [AI SMARTS] Text-based card type fallback detected: {text_detected}")

    def extract_transactions_with_litellm(self, text: str, temperature: float = None) -> List[Dict]:
        """Extract transactions using LiteLLM"""
        try:
            from litellm import completion

            model_name = self._format_model_name()
            kwargs = self._prepare_litellm_kwargs()

            # Use provided temperature or default
            current_temp = temperature if temperature is not None else self.temperature

            kwargs.update({
                "model": model_name,
                "messages": [{"role": "user", "content": self._render_extraction_prompt(text)}],
                "max_tokens": 8000,
                "temperature": current_temp
            })

            logger.info(f"🔄 Processing text chunk with {self.provider_name} ({len(text)} chars)")
            response = completion(**kwargs)

            if response and response.choices:
                result_text = response.choices[0].message.content
                # Log raw response for debugging signs
                logger.debug(f"📄 RAW LLM RESPONSE: {result_text[:1000]}...")

                # If auto-detect, try to determine from first chunk or use result insight
                if self.card_type == "auto":
                    # For simplicity, we detect on first successful extraction call text
                    self.detected_card_type = self._detect_card_type(text)
                    self.card_type = self.detected_card_type  # Set it so downstream uses it
                    logger.info(f"🔍 AI detected card_type: {self.detected_card_type}")

                txns = self._parse_response(result_text)
                # Inject card_type and bank_name for TransactionModel validation
                bank_name = self.statement_metadata.get('bank_name')
                for t in txns:
                    t['card_type'] = self.card_type
                    if bank_name:
                        t['bank_name'] = bank_name
                return txns
            else:
                logger.warning("No response received from LLM")
                return []

        except KeyError as e:
            logger.error(f"Error in LiteLLM extraction - missing field: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in LiteLLM extraction: {e}")
            # Check for connection errors to raise BankLLMUnavailableError
            error_str = str(e).lower()
            if "connection" in error_str or "unreachable" in error_str or "timeout" in error_str:
                raise BankLLMUnavailableError(f"LLM connection failed: {e}")
            return []

    def _parse_response(self, response: str) -> List[Dict]:
        """Parse LLM response to extract transactions"""
        try:
            # Clean the response
            response = response.strip()

            # Remove any markdown formatting
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)

            # Find JSON content
            json_patterns = [
                r'\[[\s\S]*?\]',  # Standard JSON array
                r'\{[\s\S]*?\}',  # Single JSON object
            ]

            for pattern in json_patterns:
                matches = re.findall(pattern, response)
                for match in matches:
                    try:
                        data = json.loads(match)

                        if isinstance(data, list):
                            # Validate and filter transactions
                            valid_txns = []
                            for txn in data:
                                if isinstance(txn, dict) and txn.get('date'):
                                    valid_txns.append(txn)
                                else:
                                    logger.warning(f"Skipping invalid transaction (missing date): {txn}")
                            return valid_txns
                        elif isinstance(data, dict):
                            if data.get('date'):
                                return [data]
                            else:
                                logger.warning(f"Skipping invalid transaction (missing date): {data}")
                                return []

                    except json.JSONDecodeError:
                        continue

            # If no JSON found, log and return empty
            logger.warning("No valid JSON content found in LLM response")
            return []

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []

    def _extract_with_regex(self, text: str) -> List[Dict]:
        """Fallback extraction using regex patterns"""
        transactions = []

        # Look for transaction-like patterns
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
            r'(\d{4}-\d{2}-\d{2})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                try:
                    date, desc, amount = match
                    amount_float = float(amount.replace('$', '').replace(',', ''))

                    transactions.append({
                        'date': date,
                        'description': desc.strip(),
                        'amount': amount_float,
                        'transaction_type': 'debit' if amount_float < 0 else 'credit'
                    })
                except Exception:
                    continue

        return transactions

    def load_pdf_with_langchain(self, pdf_path: str, loader_names: List[str] = None) -> List[Document]:
        """Load PDF using LangChain loaders with automatic fallback"""
        # Validate pdf_path to prevent path traversal
        try:
            safe_path = validate_file_path(pdf_path)
        except ValueError as e:
            logger.error(str(e))
            raise FileNotFoundError(f"Invalid PDF path: {e}")
        pdf_path = Path(safe_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if loader_names is None:
            loader_names = ['pymupdf', 'pdfplumber', 'pypdf']

        last_error = None

        for loader_name in loader_names:
            if loader_name not in self.pdf_loaders:
                continue

            try:
                logger.info(f"Trying {loader_name} loader...")
                loader_class = self.pdf_loaders[loader_name]['class']
                loader = loader_class(str(pdf_path))

                documents = loader.load()

                if documents and any(doc.page_content.strip() for doc in documents):
                    logger.info(f"Successfully loaded with {loader_name}")
                    return documents

            except Exception as e:
                last_error = e
                logger.error(f"{loader_name} failed: {str(e)[:100]}...")
                continue

        raise Exception(f"All PDF loaders failed. Last error: {last_error}")

    def preprocess_documents(self, documents: List[Document]) -> List[Document]:
        """Preprocess documents with cleaning and chunking"""

        logger.info("Preprocessing documents...")

        # Combine all pages
        full_text = ""
        for doc in documents:
            content = doc.page_content

            # Clean PDF artifacts
            content = re.sub(r'Page \d+ of \d+', '', content)
            content = re.sub(r'\s+', ' ', content)

            full_text += content + "\n\n"

        # Split into chunks
        chunks = self.text_splitter.split_text(full_text)

        processed_docs = []
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                processed_docs.append(Document(
                    page_content=chunk,
                    metadata={
                        "chunk": i,
                        "source": documents[0].metadata.get("source", "unknown"),
                        "chunk_size": len(chunk)
                    }
                ))

        logger.info(f"Created {len(processed_docs)} chunks for processing")

        # Log chunk details for debugging
        for i, doc in enumerate(processed_docs):
            preview = doc.page_content[:200].replace('\n', ' ')
            logger.info(f"  Chunk {i+1}/{len(processed_docs)}: {len(doc.page_content)} chars, preview: {preview}...")

        return processed_docs

    def extract_transactions_from_documents(self, documents: List[Document]) -> List[Dict]:
        """Extract transactions using LiteLLM"""

        all_transactions = []

        logger.info(f"Extracting transactions from {len(documents)} chunks using {self.provider_name}")

        # FIRST PASS: Extract global metadata from the first chunk
        if documents:
            self._extract_statement_metadata(documents[0].page_content)

        for i, doc in enumerate(documents):
            logger.info(f"Processing chunk {i+1}/{len(documents)} (size: {len(doc.page_content)} chars)")

            try:
                start_time = time.time()

                # Use LiteLLM for extraction with retry logic
                # Set to 1 since we will introduce reviewer worker
                max_retries = 1
                best_transactions = []
                base_temp = 0.1

                for attempt in range(max_retries):
                    # Increase temperature for each retry to break "stuck" logic
                    # 0.1, 0.3, 0.5, 0.7, 0.9
                    current_temp = min(0.9, base_temp + (attempt * 0.2))

                    logger.info(f"   Attempt {attempt+1}/{max_retries} extracting transactions (temp={current_temp:.1f})...")
                    attempt_transactions = self.extract_transactions_with_litellm(doc.page_content, temperature=current_temp)

                    logger.info(f"     Found {len(attempt_transactions)} transactions in attempt {attempt+1}")

                    # Keep the result with the most transactions
                    if len(attempt_transactions) > len(best_transactions):
                        best_transactions = attempt_transactions

                    # Optimization: If we found a good number of transactions, we can stop early
                    if len(best_transactions) > 6:
                        logger.info(f"   Found sufficient transactions ({len(best_transactions)}), stopping retries early")
                        break

                    # If we have minimal transactions, force retry
                    if len(best_transactions) <= 2 and attempt < max_retries - 1:
                        logger.info(f"   Low transaction count ({len(best_transactions)}), retrying with higher temperature...")
                        continue

                chunk_transactions = best_transactions
                processing_time = time.time() - start_time
                logger.info(f"   Processed chunk {i+1} in {processing_time:.2f}s (best of {attempt+1} attempts)")

                if chunk_transactions:
                    logger.info(f"   Found {len(chunk_transactions)} transactions in chunk {i+1}")
                    # Log first transaction as sample
                    if chunk_transactions:
                        sample = chunk_transactions[0]
                        logger.info(f"   Sample transaction: date={sample.get('date')}, desc={sample.get('description', '')[:30]}, amt={sample.get('amount')}")
                    all_transactions.extend(chunk_transactions)
                else:
                    logger.info(f"   No transactions found in chunk {i+1}")

            except BankLLMUnavailableError:
                raise
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {e}")
                continue

        logger.info(f"📊 EXTRACTION SUMMARY: Total transactions before deduplication: {len(all_transactions)}")
        if all_transactions:
            logger.info(f"   Sample transaction: {all_transactions[0]}")
            # Log transaction distribution
            dates = [t.get('date') for t in all_transactions if t.get('date')]
            if dates:
                logger.info(f"   Date range: {min(dates)} to {max(dates)}")
        return all_transactions

    def process_pdf(self,
                    pdf_path: str,
                    loader_names: List[str] = None,
                    categorize: bool = False,  # Simplified for now
                    save_debug: bool = False) -> Union["pd.DataFrame", List[Dict]]:
        """Main method to process PDF using LiteLLM with OCR fallback support"""

        logger.info(f"Processing bank statement with {self.provider_name}: {pdf_path}")
        logger.info(f"Using model: {self.model_name}")

        extraction_method = "unknown"
        processing_time = 0.0

        try:
            # Use enhanced text extractor with OCR fallback if available
            if self.text_extractor:
                extraction_result = self.text_extractor.extract_text(pdf_path)
                text = extraction_result.text
                extraction_method = extraction_result.method
                processing_time = extraction_result.processing_time

                # Store extraction metadata for later AI usage tracking
                self.last_extraction_method = extraction_method
                self.last_processing_time = processing_time
                self.last_text_length = len(text)

                # Track extraction method for analytics
                self._track_extraction_method(extraction_method, pdf_path, processing_time)

                # Notify user about processing completion
                try:
                    from core.utils.ocr_notifications import notify_ocr_processing_completed
                    # We'll add transaction count after processing
                except ImportError:
                    pass

                # Create documents from extracted text
                documents = [Document(page_content=text, metadata={"source": pdf_path, "extraction_method": extraction_method})]
            else:
                # Fallback to original PDF loading method
                logger.warning("Enhanced text extractor not available, using fallback PDF loading")
                documents = self.load_pdf_with_langchain(pdf_path, loader_names)
                extraction_method = "pdf_loader_fallback"

            # Preprocess documents
            processed_docs = self.preprocess_documents(documents)

            if save_debug:
                debug_text = "\n\n--- CHUNK SEPARATOR ---\n\n".join([
                    f"CHUNK {i+1} (method: {extraction_method}):\n{doc.page_content}"
                    for i, doc in enumerate(processed_docs)
                ])
                with open("universal_debug_chunks.txt", "w", encoding="utf-8") as f:
                    f.write(debug_text)
                logger.info("Debug chunks saved to universal_debug_chunks.txt")

            # Extract transactions
            transactions = self.extract_transactions_from_documents(processed_docs)

            if not transactions:
                logger.error("No transactions found")
                return pd.DataFrame() if pd else []

            # Add extraction method metadata to transactions
            for transaction in transactions:
                transaction['_extraction_method'] = extraction_method
                transaction['_processing_time'] = processing_time

            # Basic validation and cleaning
            result = self.validate_and_clean_data(transactions)

            transaction_count = len(result) if hasattr(result, '__len__') else 0
            logger.info(f"Successfully processed {transaction_count} transactions using {extraction_method}")

            # Notify user about processing completion
            try:
                from core.utils.ocr_notifications import notify_ocr_processing_completed
                notify_ocr_processing_completed(
                    pdf_path,
                    transaction_count,
                    processing_time,
                    extraction_method
                )
            except ImportError:
                pass

            return result

        except Exception as e:
            logger.error(f"Error processing PDF with {extraction_method}: {e}")

            # Track failed extraction attempt
            try:
                from commercial.ai_bank_statement.analytics.bank_statement_analytics_service import track_bank_statement_extraction
                from core.models.database import get_db

                with contextlib.closing(next(get_db())) as db:
                    track_bank_statement_extraction(
                        db=db,
                        method=extraction_method,
                        pdf_path=pdf_path,
                        processing_time=processing_time,
                        text_length=getattr(self, 'last_text_length', 0),
                        word_count=getattr(self, 'last_text_length', 0) // 5,
                        success=False,
                        ai_config=self.ai_config,
                        error_details=str(e)
                    )
            except Exception as track_error:
                logger.warning(f"Failed to track failed extraction: {track_error}")

            # Import OCR exceptions for specific error handling
            try:
                from commercial.ai.exceptions.bank_ocr_exceptions import OCRUnavailableError, OCRTimeoutError, OCRProcessingError

                if isinstance(e, (OCRUnavailableError, OCRTimeoutError, OCRProcessingError)):
                    # Re-raise OCR-specific exceptions for upstream handling
                    raise
            except ImportError:
                pass

            return pd.DataFrame() if pd else []

    def validate_and_clean_data(self, transactions: List[Dict]) -> Union["pd.DataFrame", List[Dict]]:
        """Basic validation and cleaning of extracted transaction data"""

        if not transactions:
            return pd.DataFrame() if pd else []

        logger.info("Validating and cleaning data...")

        if not pd:
            # Fallback to basic validation without pandas
            return self._basic_validate_and_clean(transactions)

        # Log raw transaction list before cleaning
        logger.info(f"🔍 Validating {len(transactions)} raw transactions from LLM")
        if transactions:
            logger.debug(f"🔍 First raw transaction: {transactions[0]}")

        df = pd.DataFrame(transactions)
        initial_count = len(df)
        logger.info(f"DataFrame created with {initial_count} transactions")

        # Ensure required columns
        required_cols = ['date', 'description', 'amount', 'transaction_type']
        for col in required_cols:
            if col not in df.columns:
                if col == 'transaction_type':
                    if self.card_type == 'credit':
                        df[col] = df.get('amount', 0).apply(
                            lambda x: 'credit' if x < 0 else 'debit'
                        )
                    else:
                        df[col] = df.get('amount', 0).apply(
                            lambda x: 'debit' if x < 0 else 'credit'
                        )
                else:
                    df[col] = None

        # Data type conversions and sign synchronization
        if 'amount' in df.columns:
            # For each amount, check if it's already a float or needs parsing
            def parse_amt(x):
                if pd.isna(x):
                    return x
                if isinstance(x, (int, float)):
                    return float(x)

                orig_val = str(x)
                amt = parse_number(orig_val)

                # Detailed logging for potential negative numbers (contains -, (, or ))
                if any(char in orig_val for char in ('-', '(', ')')):
                    logger.info(f"🔢 Parsed signed amount: '{orig_val}' → {amt}")

                return amt

            df['amount'] = df['amount'].apply(parse_amt)

            # Synchronize signs with transaction_type
            if 'transaction_type' in df.columns:
                def sync_sign(row):
                    amt = row['amount']
                    ttype = str(row['transaction_type']).lower()
                    if pd.isna(amt):
                        return amt

                    if self.card_type == 'credit':
                        if ttype == 'debit' and amt < 0:
                            return abs(amt)
                        elif ttype == 'credit' and amt > 0:
                            return -amt
                    else:
                        # Debit card: negative is debit, positive is credit
                        if ttype == 'debit' and amt > 0:
                            return -amt
                        elif ttype == 'credit' and amt < 0:
                            return abs(amt)
                    return amt

                df['amount'] = df.apply(sync_sign, axis=1)

        if 'balance' in df.columns:
            df['balance'] = pd.to_numeric(df['balance'], errors='coerce')

        # Remove invalid rows
        before_dropna = len(df)
        df = df.dropna(subset=['date', 'amount'])

        # Filter out opening/closing balances
        if 'description' in df.columns:
            balance_keywords = ['opening balance', 'closing balance', 'previous balance', 'new balance', 'ending balance', 'beginning balance', 'statement balance']
            pattern = '|'.join(balance_keywords)
            df = df[~df['description'].str.lower().str.contains(pattern, na=False, regex=True)]

        after_dropna = len(df)
        if before_dropna != after_dropna:
            logger.info(f"Removed {before_dropna - after_dropna} transactions with missing date/amount")

        # Sort by date
        if not df.empty:
            df = df.sort_values('date').reset_index(drop=True)

        cleaned_count = len(df)
        if cleaned_count < initial_count:
            logger.info(f"Removed {initial_count - cleaned_count} invalid/duplicate transactions")

        return df

    def _basic_validate_and_clean(self, transactions: List[Dict]) -> List[Dict]:
        """Basic validation without pandas"""
        cleaned = []

        balance_keywords = ['opening balance', 'closing balance', 'previous balance', 'new balance', 'ending balance', 'beginning balance', 'statement balance']

        for txn in transactions:
            # Ensure required fields
            if not all(key in txn for key in ['date', 'description', 'amount']):
                continue

            # Filter out opening/closing balances
            desc = str(txn.get('description', '')).lower()
            if any(keyword in desc for keyword in balance_keywords):
                continue

            # Add transaction_type if missing
            if 'transaction_type' not in txn:
                if self.card_type == 'credit':
                    txn['transaction_type'] = 'credit' if float(txn.get('amount', 0)) < 0 else 'debit'
                else:
                    txn['transaction_type'] = 'debit' if float(txn.get('amount', 0)) < 0 else 'credit'

            # Normalize date
            try:
                txn['date'] = _normalize_date(str(txn['date']))
            except Exception:
                continue

            # Validate amount and synchronize sign
            try:
                orig_amt = str(txn['amount'])
                val = parse_number(orig_amt)

                # Detailed logging for signed amounts
                if any(char in orig_amt for char in ('-', '(', ')')):
                    logger.info(f"🔢 Parsed signed amount (basic): '{orig_amt}' → {val}")

                ttype = str(txn.get('transaction_type', '')).lower()

                if ttype == 'debit' and val > 0:
                    txn['amount'] = -val
                elif ttype == 'credit' and val < 0:
                    txn['amount'] = abs(val)
                else:
                    txn['amount'] = val
            except Exception as e:
                logger.warning(f"Failed to parse amount '{txn.get('amount')}': {e}")
                continue

            cleaned.append(txn)

        # Sort by date
        try:
            cleaned.sort(key=lambda x: x['date'])
        except Exception:
            pass

        return cleaned

    def _track_extraction_method(self, method: str, pdf_path: str, processing_time: float) -> None:
        """Track extraction method usage for analytics."""
        logger.info(
            f"📊 Extraction method tracking: method={method} "
            f"file={Path(pdf_path).name} time={processing_time:.2f}s"
        )

        # Track using the analytics service
        try:
            from commercial.ai_bank_statement.analytics.bank_statement_analytics_service import track_bank_statement_extraction
            from core.models.database import get_db

            # Calculate text metrics if available
            text_length = getattr(self, 'last_text_length', 0)
            word_count = text_length // 5 if text_length > 0 else 0  # Rough estimate

            with contextlib.closing(next(get_db())) as db:
                track_bank_statement_extraction(
                    db=db,
                    method=method,
                    pdf_path=pdf_path,
                    processing_time=processing_time,
                    text_length=text_length,
                    word_count=word_count,
                    success=True,  # Assume success if we're tracking
                    ai_config=self.ai_config
                )

        except Exception as e:
            logger.warning(f"Failed to track extraction method with analytics service: {e}")
            # Don't fail the main operation if tracking fails

    def create_processing_result(
        self,
        transactions: List[Dict],
        extraction_method: str,
        processing_time: float,
        pdf_path: str,
        text_length: int = 0,
        word_count: int = 0,
        success: bool = True,
        errors: Optional[List[str]] = None,
        statement_id: Optional[int] = None
    ) -> Any:
        """Create a comprehensive processing result with all metadata."""
        try:
            from core.models.bank_statement_processing import (
                create_processing_result,
                ExtractionMethod,
                ProcessingStatus
            )

            # Map extraction method string to enum
            method_mapping = {
                "pdf_loader": ExtractionMethod.PDF_LOADER,
                "ocr": ExtractionMethod.OCR,
                "pdf_loader_insufficient": ExtractionMethod.PDF_LOADER_INSUFFICIENT,
                "pdf_loader_fallback": ExtractionMethod.PDF_LOADER
            }

            method_enum = method_mapping.get(extraction_method, ExtractionMethod.PDF_LOADER)
            status = ProcessingStatus.SUCCESS if success else ProcessingStatus.FAILED

            # Create processing result with comprehensive metadata
            result = create_processing_result(
                transactions=transactions,
                extraction_method=method_enum,
                processing_time=processing_time,
                text_length=text_length,
                word_count=word_count,
                file_path=pdf_path,
                status=status,
                ai_config_used=self.ai_config,
                ocr_engine="tesseract" if extraction_method == "ocr" else None,
                pdf_loader_used=getattr(self, 'last_pdf_loader_used', None),
                contains_bank_keywords=True,  # Assume true for bank statements
                is_scanned=extraction_method == "ocr",
                statement_id=statement_id
            )

            # Add any errors
            if errors:
                for error in errors:
                    result.add_error(error)

            # Mark as completed
            result.mark_completed()

            # Release processing lock for bank statement
            try:
                from commercial.ai.services.ocr_service import release_processing_lock
                release_processing_lock("bank_statement", statement_id)
            except Exception as lock_error:
                logger.warning(f"Failed to release processing lock for bank statement {statement_id}: {lock_error}")

            return result

        except Exception as e:
            logger.error(f"Failed to create processing result: {e}")
            # Return a minimal result structure
            return {
                "transactions": transactions,
                "extraction_method": extraction_method,
                "processing_time": processing_time,
                "success": success,
                "error": str(e)
            }


class BankTransactionExtractor:
    # TODO: Currently tested with Ollama only - need to refactor to support other LLM vendors
    # Support needed for: OpenAI, Anthropic, Google PaLM, Azure OpenAI, AWS Bedrock, etc.
    # Consider implementing LLM provider abstraction layer for vendor-agnostic interface

    def __init__(self,
                 model_name: str = "gpt-oss:latest",
                 ollama_base_url: Optional[str] = None,
                 temperature: float = 0.1,
                 chunk_size: int = 6000,  # Smaller chunks for local models
                 chunk_overlap: int = 150,
                 request_timeout: int = 120):
        """
        Initialize the extractor with Ollama

        Args:
            model_name: Ollama model name (e.g., 'llama2:7b', 'mistral:7b', 'codellama:7b')
            ollama_base_url: Ollama server URL
            temperature: Temperature for LLM responses
            chunk_size: Size of text chunks (smaller for local models)
            chunk_overlap: Overlap between chunks
            request_timeout: Timeout for Ollama requests
        """
        if not LANGCHAIN_AVAILABLE:
            logger.error("LangChain is not available for BankTransactionExtractor. Bank statement processing will be limited.")
            # Don't raise an error, just log it and continue with limited functionality
            self.langchain_available = False
        else:
            self.langchain_available = True

        self.model_name = model_name

        # Determine Ollama base URL from args or environment
        if not ollama_base_url:
            ollama_base_url = os.environ.get("OLLAMA_API_BASE") or os.environ.get("LLM_API_BASE") or "http://localhost:11434"

        self.ollama_base_url = ollama_base_url
        self.temperature = temperature
        self.request_timeout = request_timeout

        if self.langchain_available:
            # Test Ollama connection
            self._test_ollama_connection()

            # Initialize callback handler
            self.callback_handler = OllamaCallbackHandler()

            # Initialize Ollama LLM with proper endpoint
            self.llm = ChatOllama(
                model=model_name,
                base_url=ollama_base_url,
                temperature=temperature,
                timeout=request_timeout,
                callbacks=[self.callback_handler]
            )

            # For simpler prompts, use the basic Ollama LLM
            self.simple_llm = OllamaLLM(
                model=model_name,
                base_url=ollama_base_url,
                temperature=temperature,
                timeout=request_timeout,
                callbacks=[self.callback_handler]
            )

            # Initialize text splitter (smaller chunks for local models)
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", " ", ""],
                keep_separator=False
            )
        else:
            # Initialize fallback components
            self.callback_handler = None
            self.llm = None
            self.simple_llm = None
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

        # Available PDF loaders (only add if available)
        self.pdf_loaders = {}
        if LANGCHAIN_AVAILABLE:
            try:
                self.pdf_loaders['pypdf'] = {
                    'class': PyPDFLoader,
                    'description': 'Fast, basic PDF text extraction',
                    'best_for': 'Simple text-based PDFs'
                }
            except Exception:
                pass

            # CSV loader
            try:
                # Note: CSVLoader loads rows as Documents with page_content as a string
                self.csv_loader_available = True
            except Exception:  # pragma: no cover - defensive
                self.csv_loader_available = False
        else:
            self.csv_loader_available = False

            try:
                self.pdf_loaders['pymupdf'] = {
                    'class': PyMuPDFLoader,
                    'description': 'High-quality text extraction with metadata',
                    'best_for': 'Most PDF types, good balance of speed and quality'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['pdfminer'] = {
                    'class': PDFMinerLoader,
                    'description': 'Detailed text extraction with layout info',
                    'best_for': 'Complex layouts, precise text positioning'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['pdfium2'] = {
                    'class': PyPDFium2Loader,
                    'description': 'Google\'s PDF library, fast and reliable',
                    'best_for': 'Modern PDFs, good performance'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['pdfplumber'] = {
                    'class': PDFPlumberLoader,
                    'description': 'Excellent for tables and structured data',
                    'best_for': 'Bank statements with tables'
                }
            except Exception:
                pass

            try:
                self.pdf_loaders['unstructured'] = {
                    'class': UnstructuredPDFLoader,
                    'description': 'Advanced preprocessing and cleaning',
                    'best_for': 'Messy or poorly formatted PDFs'
                }
            except Exception:
                pass

        # Setup prompts (optimized for local models)
        self.extraction_prompt = self._create_extraction_prompt()
        self.categorization_prompt = self._create_categorization_prompt()

        # Store prompts for direct LLM usage (LLMChain is deprecated in v1.0+)
        self.extraction_prompt_template = self.extraction_prompt
        self.categorization_prompt_template = self.categorization_prompt

    def _test_ollama_connection(self):
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                available_models = [model['name'] for model in response.json()['models']]
                logger.info(f"Connected to Ollama server")
                logger.info(f"Available models: {', '.join(available_models)}")

                if self.model_name not in available_models:
                    logger.warning(f"Model '{self.model_name}' not found!")
                    logger.warning(f"Run: ollama pull {self.model_name}")
                    raise Exception(f"Model {self.model_name} not available")
                else:
                    logger.info(f"Using model: {self.model_name}")
            else:
                raise Exception(f"Ollama server responded with status {response.status_code}")

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama server")
            logger.error("Make sure Ollama is running: ollama serve")
            logger.error("Or check the base_url parameter")
            raise Exception("Ollama connection failed")
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            raise

    def _create_extraction_prompt(self) -> PromptTemplate:
        """Create extraction prompt optimized for local models"""

        template = """You are a financial data extraction expert. Your task is to extract ALL bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts.
2. Identify the transaction type:
   - 'debit': Money leaving the account (Withdrawals, Payments, Transfers Out, etc.).
   - 'credit': Money entering the account (Deposits, Salary, Transfers In, Interest, etc.).
3. Use context such as column headers (Withdrawal/Debit vs Deposit/Credit) or keywords in the description to determine the type.
4. Normalize the 'amount':
   - For 'debit' transactions, the amount MUST BE NEGATIVE (e.g., -45.67).
   - For 'credit' transactions, the amount MUST BE POSITIVE (e.g., 2500.00).
   - Ignore existing signs or parentheses if they contradict the identified transaction type.
5. Convert dates to YYYY-MM-DD format.
6. Extract merchant names or transaction descriptions clearly.
7. Only extract actual transactions, not headers, sub-totals, or account summaries.

TEXT:
{{text}}

Return ONLY a JSON array like this:
[
  {"date": "2024-01-15", "description": "WALMART", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56},
  {"date": "2024-01-16", "description": "ABC CORP SALARY", "amount": 2500.00, "transaction_type": "credit", "balance": 3734.56}
]

JSON:"""

        return PromptTemplate(
            template=template,
            input_variables=["text"]
        )

    def _create_categorization_prompt(self) -> PromptTemplate:
        """Create categorization prompt optimized for local models"""

        template = """Categorize these transaction descriptions into spending categories.

CATEGORIES:
Income, Food, Transportation, Shopping, Bills, Healthcare, Entertainment, Financial, Travel, Other

DESCRIPTIONS:
{descriptions}

Return ONLY a JSON array with one category per description:
["Food", "Income", "Transportation", "Shopping"]

JSON:"""

        return PromptTemplate(
            template=template,
            input_variables=["descriptions"]
        )

    def get_ollama_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags")
            if response.status_code == 200:
                return [model['name'] for model in response.json()['models']]
            return []
        except Exception:
            return []

    def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry"""
        try:
            logger.info(f"Pulling model: {model_name}")
            response = requests.post(
                f"{self.ollama_base_url}/api/pull",
                json={"name": model_name},
                timeout=600  # 10 minutes timeout for model download
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False

    def load_pdf_with_langchain(self,
                                pdf_path: str,
                                loader_names: List[str] = None) -> List[Document]:
        """Load PDF using LangChain loaders with automatic fallback"""
        # Validate pdf_path to prevent path traversal
        try:
            safe_path = validate_file_path(pdf_path)
        except ValueError as e:
            logger.error(str(e))
            raise FileNotFoundError(f"Invalid PDF path: {e}")
        pdf_path = Path(safe_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if loader_names is None:
            loader_names = ['pymupdf', 'pdfplumber', 'pdfium2', 'pypdf']

        last_error = None

        for loader_name in loader_names:
            if loader_name not in self.pdf_loaders:
                continue

            try:
                logger.info(f"Trying {loader_name} loader...")
                loader_class = self.pdf_loaders[loader_name]['class']
                loader = loader_class(str(pdf_path))

                documents = loader.load()

                if documents and any(doc.page_content.strip() for doc in documents):
                    logger.info(f"Successfully loaded with {loader_name}")
                    return documents

            except Exception as e:
                last_error = e
                logger.error(f"{loader_name} failed: {str(e)[:100]}...")
                continue

        raise Exception(f"All PDF loaders failed. Last error: {last_error}")

    def load_csv_with_langchain(self, csv_path: str) -> List[Document]:
        """Load CSV using LangChain CSVLoader or graceful fallbacks.

        Returns a list of Documents where page_content contains CSV text suitable for prompting.
        """
        # Validate csv_path to prevent path traversal
        try:
            safe_path = validate_file_path(csv_path)
        except ValueError as e:
            logger.error(str(e))
            raise FileNotFoundError(f"Invalid CSV path: {e}")
        csv_path = Path(safe_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Prefer LangChain CSVLoader when available
        if LANGCHAIN_AVAILABLE:
            try:
                loader = CSVLoader(
                    file_path=str(csv_path),
                    csv_args={"delimiter": ",", "quotechar": '"'},
                    encoding="utf-8"
                )
                docs = loader.load()
                # If CSVLoader returns many row-docs, concatenate into chunk-friendly documents
                if docs:
                    # Join all rows into a single CSV text block to leverage the existing prompt
                    lines = []
                    for d in docs:
                        content = (d.page_content or "").strip()
                        if not content:
                            continue
                        # CSVLoader usually formats as "column: value" per field; keep as-is
                        lines.append(content)
                    combined = "\n".join(lines)
                    return [Document(page_content=combined, metadata={"source": str(csv_path)})]
            except Exception as e:
                logger.warning(f"CSVLoader failed, falling back: {e}")

        # Fallback 1: pandas to read and stringify
        try:
            if pd is not None:
                df = pd.read_csv(str(csv_path))
                combined = df.to_csv(index=False)
                return [Document(page_content=combined, metadata={"source": str(csv_path)})]
        except Exception as e:
            logger.warning(f"pandas CSV read failed, falling back: {e}")

        # Fallback 2: builtin csv module
        import csv
        try:
            # Validate csv_path to prevent path traversal
            try:
                safe_path = validate_file_path(str(csv_path))
            except ValueError as e:
                logger.error(str(e))
                return []
            with open(safe_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = [",".join(row) for row in reader]
                combined = "\n".join(rows)
                return [Document(page_content=combined, metadata={"source": str(csv_path)})]
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            return []

    def preprocess_documents(self, documents: List[Document]) -> List[Document]:
        """Preprocess documents with cleaning and chunking"""

        logger.info("Preprocessing documents...")

        # Combine all pages
        full_text = ""
        for doc in documents:
            content = doc.page_content

            # Clean PDF artifacts
            content = re.sub(r'Page \d+ of \d+', '', content)
            content = re.sub(r'\s+', ' ', content)

            full_text += content + "\n\n"

        # Split into smaller chunks for local models
        chunks = self.text_splitter.split_text(full_text)

        processed_docs = []
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                processed_docs.append(Document(
                    page_content=chunk,
                    metadata={
                        "chunk": i,
                        "source": documents[0].metadata.get("source", "unknown"),
                        "chunk_size": len(chunk)
                    }
                ))

        logger.info(f"Created {len(processed_docs)} chunks for processing")
        return processed_docs

    def extract_transactions_from_documents(self, documents: List[Document]) -> List[Dict]:
        """Extract transactions using Ollama"""

        all_transactions = []

        logger.info(f"Extracting transactions from {len(documents)} chunks using Ollama...")

        for i, doc in enumerate(documents):
            logger.info(f"Processing chunk {i+1}/{len(documents)} (size: {len(doc.page_content)} chars)")

            try:
                start_time = time.time()

                # Use direct LLM call (LLMChain is deprecated)
                if self.langchain_available and self.simple_llm:
                    # Safely format prompt
                    template_str = getattr(self.extraction_prompt_template, 'template', "")
                    if template_str:
                        formatted_prompt = template_str.replace("{text}", doc.page_content).replace("{{text}}", doc.page_content)
                    else:
                        formatted_prompt = self.extraction_prompt_template.format(text=doc.page_content)
                    result = self.simple_llm.invoke(formatted_prompt)
                else:
                    result = ""

                processing_time = time.time() - start_time
                logger.info(f"   Processed in {processing_time:.2f}s")

                # Parse the result
                chunk_transactions = self._parse_ollama_response(result)

                if chunk_transactions:
                    logger.info(f"   Found {len(chunk_transactions)} transactions")
                    all_transactions.extend(chunk_transactions)
                else:
                    logger.info(f"   No transactions found")

            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {e}")
                continue

        logger.info(f"Total transactions found: {len(all_transactions)}")
        if all_transactions:
            logger.info(f"Sample transaction: {all_transactions[0]}")
        return all_transactions

    def _parse_ollama_response(self, response: str) -> List[Dict]:
        """Parse Ollama response to extract transactions"""
        try:
            # Clean the response
            response = response.strip()

            # Remove any markdown formatting
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)

            # Find JSON content - be more flexible with local model responses
            json_patterns = [
                r'\[[\s\S]*?\]',  # Standard JSON array
                r'\{[\s\S]*?\}',  # Single JSON object
            ]

            for pattern in json_patterns:
                matches = re.findall(pattern, response)
                for match in matches:
                    try:
                        data = json.loads(match)

                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict):
                            return [data]

                    except json.JSONDecodeError:
                        continue

            # If no JSON found, log and return empty. Do NOT fall back to regex silently.
            logger.warning("No JSON content found in LLM response")
            return []

        except Exception as e:
            logger.error(f"Error parsing Ollama response: {e}")
            return []

    def _extract_with_regex(self, text: str) -> List[Dict]:
        """Fallback extraction using regex patterns"""
        transactions = []

        # Look for transaction-like patterns
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
            r'(\d{4}-\d{2}-\d{2})\s+([^$\d-]+?)\s+([-$]?\d+\.?\d*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                try:
                    date, desc, amount = match
                    amount_float = float(amount.replace('$', '').replace(',', ''))

                    transactions.append({
                        'date': date,
                        'description': desc.strip(),
                        'amount': amount_float,
                        'transaction_type': 'debit' if amount_float < 0 else 'credit'
                    })
                except Exception:
                    continue

        return transactions

    def categorize_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """Categorize transactions using Ollama"""

        if not transactions:
            return transactions

        logger.info("Categorizing transactions with Ollama...")

        descriptions = [t.get('description', 'Unknown') for t in transactions]

        try:
            start_time = time.time()

            # Use direct LLM call (LLMChain is deprecated)
            if self.langchain_available and self.simple_llm:
                formatted_prompt = self.categorization_prompt_template.format(
                    descriptions=json.dumps(descriptions)
                )
                result = self.simple_llm.invoke(formatted_prompt)
            else:
                result = ""

            processing_time = time.time() - start_time
            logger.info(f"Categorization completed in {processing_time:.2f}s")

            categories = self._parse_categories(result)

            # Assign categories
            for i, category in enumerate(categories):
                if i < len(transactions):
                    transactions[i]['category'] = category

        except Exception as e:
            logger.error(f"Error in categorization: {e}")
            # Assign default categories
            for transaction in transactions:
                transaction['category'] = 'Other'

        return transactions

    def _parse_categories(self, response: str) -> List[str]:
        """Parse category response from Ollama"""
        try:
            response = response.strip()

            # Remove markdown
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)

            # Find JSON array
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                categories = json.loads(json_match.group())
                return categories if isinstance(categories, list) else []

            return []

        except Exception as e:
            logger.error(f"Error parsing categories: {e}")
            return []

    def validate_and_clean_data(self, transactions: List[Dict]) -> Union["pd.DataFrame", List[Dict]]:
        """Validate and clean extracted transaction data"""

        if not transactions:
            return pd.DataFrame() if pd else []

        logger.info("Validating and cleaning data...")

        if not pd:
            # Fallback to basic validation without pandas
            logger.warning("Pandas not available - using basic validation")
            return self._basic_validate_and_clean(transactions)

        df = pd.DataFrame(transactions)
        initial_count = len(df)
        logger.info(f"DataFrame created with {initial_count} transactions")
        if initial_count > 0:
            logger.info(f"DataFrame columns: {list(df.columns)}")
            logger.info(f"First row: {df.iloc[0].to_dict()}")

        # Standardize columns
        column_mapping = {
            'trans_date': 'date',
            'transaction_date': 'date',
            'trans_amount': 'amount',
            'transaction_amount': 'amount',
            'trans_description': 'description',
            'transaction_description': 'description',
            'type': 'transaction_type'
        }
        df = df.rename(columns=column_mapping)

        # Ensure required columns
        required_cols = ['date', 'description', 'amount', 'transaction_type']
        for col in required_cols:
            if col not in df.columns:
                if col == 'transaction_type':
                    df[col] = df.get('amount', 0).apply(
                        lambda x: 'credit' if x < 0 else 'debit'
                    )
                else:
                    df[col] = None

        # Data type conversions
        if 'date' in df.columns:
            logger.info(f"Converting dates. Sample values: {df['date'].head().tolist()}")
            df['date'] = pd.to_datetime(df['date'], errors='coerce', infer_datetime_format=True)
            invalid_dates = df['date'].isna().sum()
            if invalid_dates > 0:
                logger.info(f"Found {invalid_dates} invalid dates that will be removed")

        if 'amount' in df.columns:
            logger.info(f"Converting amounts. Sample values: {df['amount'].head().tolist()}")
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            invalid_amounts = df['amount'].isna().sum()
            if invalid_amounts > 0:
                logger.info(f"Found {invalid_amounts} invalid amounts that will be removed")

        if 'balance' in df.columns:
            df['balance'] = pd.to_numeric(df['balance'], errors='coerce')

        # Remove invalid rows
        before_dropna = len(df)
        df = df.dropna(subset=['date', 'amount'])
        after_dropna = len(df)
        if before_dropna != after_dropna:
            logger.info(f"Removed {before_dropna - after_dropna} transactions with missing date/amount")

        # Remove duplicates
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['date', 'description', 'amount']).reset_index(drop=True)
        after_dedup = len(df)
        if before_dedup != after_dedup:
            logger.info(f"Removed {before_dedup - after_dedup} duplicate transactions")

        # Sort by date
        if not df.empty:
            df = df.sort_values('date').reset_index(drop=True)

        cleaned_count = len(df)
        if cleaned_count < initial_count:
            logger.info(f"Removed {initial_count - cleaned_count} invalid/duplicate transactions")

        return df

    def _basic_validate_and_clean(self, transactions: List[Dict]) -> List[Dict]:
        """Basic validation without pandas"""
        cleaned = []

        for txn in transactions:
            # Ensure required fields
            if not all(key in txn for key in ['date', 'description', 'amount']):
                continue

            # Add transaction_type if missing
            if 'transaction_type' not in txn:
                txn['transaction_type'] = 'credit' if float(txn.get('amount', 0)) > 0 else 'debit'

            # Normalize date
            try:
                txn['date'] = _normalize_date(str(txn['date']))
            except Exception:
                continue

            # Validate amount
            try:
                orig_amt = str(txn['amount'])
                txn['amount'] = parse_number(orig_amt)
            except Exception as e:
                logger.warning(f"Failed to parse amount in basic clean: {e}")
                continue

            cleaned.append(txn)

        # Sort by date
        try:
            cleaned.sort(key=lambda x: x['date'])
        except Exception:
            pass

        return cleaned

    def process_pdf(self,
                    pdf_path: str,
                    loader_names: List[str] = None,
                    categorize: bool = True,
                    save_debug: bool = False) -> Union["pd.DataFrame", List[Dict]]:
        """Main method to process PDF using Ollama"""

        logger.info(f"Processing bank statement with Ollama: {pdf_path}")
        logger.info(f"Using model: {self.model_name}")

        try:
            # Load PDF
            documents = self.load_pdf_with_langchain(pdf_path, loader_names)

            # Preprocess documents
            processed_docs = self.preprocess_documents(documents)

            if save_debug:
                debug_text = "\n\n--- CHUNK SEPARATOR ---\n\n".join([
                    f"CHUNK {i+1}:\n{doc.page_content}"
                    for i, doc in enumerate(processed_docs)
                ])
                with open("ollama_debug_chunks.txt", "w", encoding="utf-8") as f:
                    f.write(debug_text)
                logger.info("Debug chunks saved to ollama_debug_chunks.txt")

            # Extract transactions
            transactions = self.extract_transactions_from_documents(processed_docs)

            if not transactions:
                logger.error("No transactions found")
                return pd.DataFrame() if pd else []

            # Categorize transactions
            if categorize:
                transactions = self.categorize_transactions(transactions)

            # Validate and clean data
            logger.info(f"About to validate {len(transactions)} transactions")
            if transactions:
                logger.info(f"First transaction before validation: {transactions[0]}")
            result = self.validate_and_clean_data(transactions)

            # Print performance stats
            self._print_performance_stats()

            if pd and hasattr(result, '__len__'):
                logger.info(f"Successfully processed {len(result)} transactions")
            else:
                logger.info(f"Successfully processed {len(result) if isinstance(result, list) else 'unknown'} transactions")
            return result

        except BankLLMUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return pd.DataFrame() if pd else []

    def process_csv(self,
                    csv_path: str,
                    categorize: bool = True,
                    save_debug: bool = False) -> Union["pd.DataFrame", List[Dict]]:
        """Process a CSV bank export using the same extraction prompt flow."""
        logger.info(f"Processing bank CSV with Ollama: {csv_path}")
        logger.info(f"Using model: {self.model_name}")

        try:
            # Load CSV
            documents = self.load_csv_with_langchain(csv_path)
            if not documents:
                logger.error("CSV load produced no documents")
                return pd.DataFrame() if pd else []

            # For CSV, skip heavy PDF-specific cleaning; still chunk
            full_text = "\n\n".join([(d.page_content or "").strip() for d in documents if (d.page_content or "").strip()])
            chunks = self.text_splitter.split_text(full_text)
            processed_docs = [Document(page_content=c, metadata={"chunk": i, "source": str(csv_path)}) for i, c in enumerate(chunks) if c.strip()]

            if save_debug:
                debug_text = "\n\n--- CHUNK SEPARATOR ---\n\n".join([f"CHUNK {i+1}:\n{doc.page_content}" for i, doc in enumerate(processed_docs)])
                with open("ollama_debug_chunks.txt", "w", encoding="utf-8") as f:
                    f.write(debug_text)
                logger.info("Debug chunks saved to ollama_debug_chunks.txt")

            # Extract transactions
            transactions = self.extract_transactions_from_documents(processed_docs)

            if not transactions:
                logger.info("No transactions found from CSV text")
                return pd.DataFrame() if pd else []

            # Categorize
            if categorize:
                transactions = self.categorize_transactions(transactions)

            # Validate/clean
            result = self.validate_and_clean_data(transactions)
            self._print_performance_stats()

            if pd and hasattr(result, '__len__'):
                logger.info(f"Successfully processed {len(result)} CSV transactions")
            else:
                logger.info(f"Successfully processed {len(result) if isinstance(result, list) else 'unknown'} CSV transactions")
            return result
        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            return pd.DataFrame() if pd else []

    def _print_performance_stats(self):
        """Print Ollama performance statistics"""
        logger.info(f"Ollama Performance Stats:")
        logger.info(f"   Requests made: {self.callback_handler.request_count}")
        logger.info(f"   Total time: {self.callback_handler.total_time:.2f}s")
        if self.callback_handler.request_count > 0:
            avg_time = self.callback_handler.total_time / self.callback_handler.request_count
            logger.info(f"   Average time per request: {avg_time:.2f}s")
