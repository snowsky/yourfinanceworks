import os
import re
import json
import time
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from services.ocr_service import track_ai_usage

logger = logging.getLogger(__name__)
# Custom error to signal LLM unavailability to callers that want to retry
class BankLLMUnavailableError(Exception):
    pass

# Optional imports with fallbacks
try:
    import pandas as pd
except ImportError:
    pd = None

# LangChain imports - optional (updated to langchain_community to avoid deprecation warnings)
try:
    from langchain_community.document_loaders import (
        PyPDFLoader, 
        PyMuPDFLoader, 
        PDFMinerLoader,
        PyPDFium2Loader,
        PDFPlumberLoader,
        UnstructuredPDFLoader,
        CSVLoader,
    )
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
    from langchain.prompts import PromptTemplate, ChatPromptTemplate
    from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
    from langchain.chains import LLMChain
    from langchain.callbacks.base import BaseCallbackHandler
    from langchain_community.llms import Ollama
    from langchain_community.chat_models import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not available - falling back to basic functionality")
    # Create dummy classes for type hints
    class Document:
        def __init__(self, page_content="", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}
    
    class BaseCallbackHandler:
        pass
    
    class PromptTemplate:
        def __init__(self, template="", input_variables=None):
            self.template = template
            self.input_variables = input_variables or []
    
    class LLMChain:
        def __init__(self, llm=None, prompt=None):
            pass
        
        def run(self, **kwargs):
            raise NotImplementedError("LangChain not available")
    
    class RecursiveCharacterTextSplitter:
        def __init__(self, **kwargs):
            self.chunk_size = kwargs.get('chunk_size', 3000)
            self.chunk_overlap = kwargs.get('chunk_overlap', 150)
        
        def split_text(self, text):
            # Simple text splitting fallback
            chunks = []
            i = 0
            while i < len(text):
                chunk = text[i:i + self.chunk_size]
                if not chunk.strip():
                    break
                chunks.append(chunk)
                i += self.chunk_size - self.chunk_overlap
            return chunks
    
    LANGCHAIN_AVAILABLE = False

# Pydantic models for structured output - optional (migrate to field_validator)
try:
    from pydantic import BaseModel, Field
    try:
        # Pydantic v2
        from pydantic import field_validator
        _HAS_FIELD_VALIDATOR = True
    except ImportError:
        # Pydantic v1 fallback
        from pydantic import validator  # type: ignore
        field_validator = None  # type: ignore
        _HAS_FIELD_VALIDATOR = False
    from typing import List as TypingList
    PYDANTIC_AVAILABLE = True
except ImportError:
    logger.warning("Pydantic not available - using basic validation")
    # Create dummy classes
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    def Field(**kwargs):
        return None
    
    def validator(field_name):
        def decorator(func):
            return func
        return decorator
    field_validator = validator  # type: ignore
    
    TypingList = List
    PYDANTIC_AVAILABLE = False


@dataclass
class Transaction:
    date: str
    description: str
    amount: float
    transaction_type: str  # 'debit' | 'credit'
    balance: Optional[float] = None
    category: Optional[str] = None


class TransactionModel(BaseModel):
    """Pydantic model for individual transactions"""
    date: str = Field(description="Transaction date in YYYY-MM-DD format")
    description: str = Field(description="Transaction description or merchant name")
    amount: float = Field(description="Transaction amount (negative for debits, positive for credits)")
    transaction_type: str = Field(description="Type of transaction: 'debit' or 'credit'")
    balance: Optional[float] = Field(default=None, description="Account balance after transaction")
    category: Optional[str] = Field(default=None, description="Transaction category")

    # Use pydantic v2 field_validator if available, else v1 validator
    if 'field_validator' in globals() and field_validator:  # type: ignore
        @field_validator('transaction_type', mode='before')  # type: ignore
        @classmethod
        def validate_transaction_type(cls, v):
            try:
                vv = (v or '').lower()
                if vv not in ['debit', 'credit']:
                    return 'debit' if vv == '' else ('credit' if vv.startswith('c') or vv == '+' else 'debit')
                return vv
            except Exception:
                return 'debit'

        @field_validator('date', mode='before')  # type: ignore
        @classmethod
        def validate_date(cls, v):
            try:
                from datetime import datetime
                s = str(v)
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%Y/%m/%d']:
                    try:
                        dt = datetime.strptime(s, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                return s
            except Exception:
                return v
    else:
        @validator('transaction_type')  # type: ignore
        def validate_transaction_type_v1(cls, v):  # type: ignore
            if (v or '').lower() not in ['debit', 'credit']:
                return 'debit' if v else 'credit'
            return (v or '').lower()

        @validator('date')  # type: ignore
        def validate_date_v1(cls, v):  # type: ignore
            try:
                from datetime import datetime
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%Y/%m/%d']:
                    try:
                        dt = datetime.strptime(v, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                return v
            except Exception:
                return v


class TransactionListModel(BaseModel):
    """Pydantic model for list of transactions"""
    transactions: TypingList[TransactionModel] = Field(description="List of extracted bank transactions")


class OllamaCallbackHandler(BaseCallbackHandler):
    """Custom callback handler to track Ollama usage"""
    
    def __init__(self):
        self.total_tokens = 0
        self.total_time = 0
        self.request_count = 0
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        self.start_time = time.time()
        self.request_count += 1
    
    def on_llm_end(self, response, **kwargs):
        self.total_time += time.time() - self.start_time
        if hasattr(response, 'llm_output') and response.llm_output:
            self.total_tokens += response.llm_output.get('token_usage', {}).get('total_tokens', 0)


class UniversalBankTransactionExtractor:
    """
    Universal bank transaction extractor that supports multiple LLM providers via LiteLLM.
    Supports: OpenAI, OpenRouter, Anthropic, Google, Ollama, and other LiteLLM-compatible providers.
    """
    
    def __init__(self, 
                 ai_config: Dict[str, Any],
                 temperature: float = 0.1,
                 chunk_size: int = 3000,
                 chunk_overlap: int = 150,
                 request_timeout: int = 120):
        """
        Initialize the extractor with AI configuration
        
        Args:
            ai_config: AI configuration dict with provider_name, model_name, api_key, provider_url
            temperature: Temperature for LLM responses
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            request_timeout: Timeout for requests
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required for UniversalBankTransactionExtractor. Please install langchain package.")
        
        self.ai_config = ai_config
        self.provider_name = ai_config.get("provider_name", "openai")
        self.model_name = ai_config.get("model_name", "gpt-4")
        self.api_key = ai_config.get("api_key")
        self.provider_url = ai_config.get("provider_url")
        self.temperature = temperature
        self.request_timeout = request_timeout
        
        logger.info(f"🚀 Initializing UniversalBankTransactionExtractor: {self.provider_name} / {self.model_name}")
        
        # Test provider connection
        self._test_provider_connection()
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            keep_separator=False
        )
        
        # Available PDF loaders (same as original)
        self.pdf_loaders = {}
        if LANGCHAIN_AVAILABLE:
            try:
                self.pdf_loaders['pypdf'] = {
                    'class': PyPDFLoader,
                    'description': 'Fast, basic PDF text extraction',
                    'best_for': 'Simple text-based PDFs'
                }
            except: pass
            
            try:
                self.pdf_loaders['pymupdf'] = {
                    'class': PyMuPDFLoader,
                    'description': 'High-quality text extraction with metadata',
                    'best_for': 'Most PDF types, good balance of speed and quality'
                }
            except: pass
            
            try:
                self.pdf_loaders['pdfplumber'] = {
                    'class': PDFPlumberLoader,
                    'description': 'Excellent for tables and structured data',
                    'best_for': 'Bank statements with tables'
                }
            except: pass
        
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
        if self.provider_name == "ollama" and not self.provider_url:
            kwargs["api_base"] = "http://localhost:11434"
        
        return kwargs
    
    def _create_extraction_prompt(self) -> PromptTemplate:
        """Create extraction prompt optimized for universal providers"""
        
        template = """You are a financial data extraction expert. Extract bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts
2. Amounts with "-" or in parentheses are debits (money out)
3. Positive amounts are credits (money in)
4. Convert dates to YYYY-MM-DD format
5. Extract merchant names clearly
6. Only extract actual transactions, not headers or summaries

TEXT:
{text}

Return ONLY a JSON array like this example:
[
  {{"date": "2024-01-15", "description": "GROCERY STORE", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56}},
  {{"date": "2024-01-16", "description": "SALARY DEPOSIT", "amount": 2500.00, "transaction_type": "credit", "balance": 3689.89}}
]

JSON:"""
        
        return PromptTemplate(
            template=template,
            input_variables=["text"]
        )
    
    def extract_transactions_with_litellm(self, text: str) -> List[Dict]:
        """Extract transactions using LiteLLM"""
        try:
            from litellm import completion
            
            model_name = self._format_model_name()
            kwargs = self._prepare_litellm_kwargs()
            
            kwargs.update({
                "model": model_name,
                "messages": [{"role": "user", "content": self.extraction_prompt.format(text=text)}],
                "max_tokens": 2000,
                "temperature": self.temperature
            })
            
            logger.info(f"🔄 Processing text chunk with {self.provider_name} ({len(text)} chars)")
            
            response = completion(**kwargs)
            
            if response and response.choices:
                result_text = response.choices[0].message.content
                return self._parse_response(result_text)
            else:
                logger.warning("No response received from LLM")
                return []
                
        except Exception as e:
            logger.error(f"Error in LiteLLM extraction: {e}")
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
                            return data
                        elif isinstance(data, dict):
                            return [data]
                            
                    except json.JSONDecodeError:
                        continue
            
            # If no JSON found, try to extract transaction-like patterns
            return self._extract_with_regex(response)
            
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
                except:
                    continue
        
        return transactions
    
    # Include the same PDF loading and processing methods as the original class
    def load_pdf_with_langchain(self, pdf_path: str, loader_names: List[str] = None) -> List[Document]:
        """Load PDF using LangChain loaders with automatic fallback"""
        pdf_path = Path(pdf_path)
        
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
            content = re.sub(r'Statement Period:.*?\n', '', content)
            content = re.sub(r'Account Summary.*?\n', '', content)
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
        return processed_docs
    
    def extract_transactions_from_documents(self, documents: List[Document]) -> List[Dict]:
        """Extract transactions using LiteLLM"""
        
        all_transactions = []
        
        logger.info(f"Extracting transactions from {len(documents)} chunks using {self.provider_name}")
        
        for i, doc in enumerate(documents):
            logger.info(f"Processing chunk {i+1}/{len(documents)} (size: {len(doc.page_content)} chars)")
            
            try:
                start_time = time.time()
                
                # Use LiteLLM for extraction
                chunk_transactions = self.extract_transactions_with_litellm(doc.page_content)
                
                processing_time = time.time() - start_time
                logger.info(f"   Processed in {processing_time:.2f}s")
                
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
    
    def process_pdf(self, 
                   pdf_path: str,
                   loader_names: List[str] = None,
                   categorize: bool = False,  # Simplified for now
                   save_debug: bool = False) -> Union[pd.DataFrame, List[Dict]]:
        """Main method to process PDF using LiteLLM"""
        
        logger.info(f"Processing bank statement with {self.provider_name}: {pdf_path}")
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
                with open("universal_debug_chunks.txt", "w", encoding="utf-8") as f:
                    f.write(debug_text)
                logger.info("Debug chunks saved to universal_debug_chunks.txt")
            
            # Extract transactions
            transactions = self.extract_transactions_from_documents(processed_docs)
            
            if not transactions:
                logger.error("No transactions found")
                return pd.DataFrame() if pd else []
            
            # Basic validation and cleaning
            result = self.validate_and_clean_data(transactions)
            
            logger.info(f"Successfully processed {len(result) if hasattr(result, '__len__') else 'unknown'} transactions")
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return pd.DataFrame() if pd else []
    
    def validate_and_clean_data(self, transactions: List[Dict]) -> Union[pd.DataFrame, List[Dict]]:
        """Basic validation and cleaning of extracted transaction data"""
        
        if not transactions:
            return pd.DataFrame() if pd else []
        
        logger.info("Validating and cleaning data...")
        
        if not pd:
            # Fallback to basic validation without pandas
            return self._basic_validate_and_clean(transactions)
        
        df = pd.DataFrame(transactions)
        initial_count = len(df)
        logger.info(f"DataFrame created with {initial_count} transactions")
        
        # Ensure required columns
        required_cols = ['date', 'description', 'amount', 'transaction_type']
        for col in required_cols:
            if col not in df.columns:
                if col == 'transaction_type':
                    df[col] = df.get('amount', 0).apply(
                        lambda x: 'credit' if x > 0 else 'debit'
                    )
                else:
                    df[col] = None
        
        # Data type conversions
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
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
        seen = set()
        
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
            except:
                continue
            
            # Validate amount
            try:
                txn['amount'] = float(txn['amount'])
            except:
                continue
            
            # Deduplicate
            key = (txn['date'], txn['description'], round(txn['amount'], 2))
            if key not in seen:
                seen.add(key)
                cleaned.append(txn)
        
        # Sort by date
        try:
            cleaned.sort(key=lambda x: x['date'])
        except:
            pass
        
        return cleaned


class BankTransactionExtractor:
    # TODO: Currently tested with Ollama only - need to refactor to support other LLM vendors
    # Support needed for: OpenAI, Anthropic, Google PaLM, Azure OpenAI, AWS Bedrock, etc.
    # Consider implementing LLM provider abstraction layer for vendor-agnostic interface
    
    def __init__(self, 
                 model_name: str = "gpt-oss:latest",
                 ollama_base_url: str = "http://localhost:11434",
                 temperature: float = 0.1,
                 chunk_size: int = 3000,  # Smaller chunks for local models
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
            raise ImportError("LangChain is required for BankTransactionExtractor. Please install langchain package.")
        
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url
        self.temperature = temperature
        self.request_timeout = request_timeout
        
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
        self.simple_llm = Ollama(
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
        
        # Available PDF loaders (only add if available)
        self.pdf_loaders = {}
        if LANGCHAIN_AVAILABLE:
            try:
                self.pdf_loaders['pypdf'] = {
                    'class': PyPDFLoader,
                    'description': 'Fast, basic PDF text extraction',
                    'best_for': 'Simple text-based PDFs'
                }
            except: pass
            
            # CSV loader
            try:
                # Note: CSVLoader loads rows as Documents with page_content as a string
                self.csv_loader_available = True
            except:  # pragma: no cover - defensive
                self.csv_loader_available = False
        else:
            self.csv_loader_available = False

            try:
                self.pdf_loaders['pymupdf'] = {
                    'class': PyMuPDFLoader,
                    'description': 'High-quality text extraction with metadata',
                    'best_for': 'Most PDF types, good balance of speed and quality'
                }
            except: pass
            
            try:
                self.pdf_loaders['pdfminer'] = {
                    'class': PDFMinerLoader,
                    'description': 'Detailed text extraction with layout info',
                    'best_for': 'Complex layouts, precise text positioning'
                }
            except: pass
            
            try:
                self.pdf_loaders['pdfium2'] = {
                    'class': PyPDFium2Loader,
                    'description': 'Google\'s PDF library, fast and reliable',
                    'best_for': 'Modern PDFs, good performance'
                }
            except: pass
            
            try:
                self.pdf_loaders['pdfplumber'] = {
                    'class': PDFPlumberLoader,
                    'description': 'Excellent for tables and structured data',
                    'best_for': 'Bank statements with tables'
                }
            except: pass
            
            try:
                self.pdf_loaders['unstructured'] = {
                    'class': UnstructuredPDFLoader,
                    'description': 'Advanced preprocessing and cleaning',
                    'best_for': 'Messy or poorly formatted PDFs'
                }
            except: pass
        
        # Setup prompts (optimized for local models)
        self.extraction_prompt = self._create_extraction_prompt()
        self.categorization_prompt = self._create_categorization_prompt()
        
        # Create chains
        self.extraction_chain = LLMChain(llm=self.simple_llm, prompt=self.extraction_prompt)
        self.categorization_chain = LLMChain(llm=self.simple_llm, prompt=self.categorization_prompt)
    
    def _test_ollama_connection(self):
        """Test connection to Ollama server"""
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
        
        template = """You are a financial data extraction expert. Extract bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts
2. Amounts with "-" or in parentheses are debits (money out)
3. Positive amounts are credits (money in)
4. Convert dates to YYYY-MM-DD format
5. Extract merchant names clearly
6. Only extract actual transactions, not headers or summaries

TEXT:
{text}

Return ONLY a JSON array like this example:
[
  {{"date": "2024-01-15", "description": "GROCERY STORE", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56}},
  {{"date": "2024-01-16", "description": "SALARY DEPOSIT", "amount": 2500.00, "transaction_type": "credit", "balance": 3689.89}}
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
        except:
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
        pdf_path = Path(pdf_path)
        
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
        csv_path = Path(csv_path)
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
                    header = None
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
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
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
            content = re.sub(r'Statement Period:.*?\n', '', content)
            content = re.sub(r'Account Summary.*?\n', '', content)
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
                
                # Use the extraction chain
                result = self.extraction_chain.run(text=doc.page_content)
                
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
            
            # If no JSON found, try to extract transaction-like patterns
            return self._extract_with_regex(response)
            
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
                except:
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
            
            result = self.categorization_chain.run(
                descriptions=json.dumps(descriptions)
            )
            
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
    
    def validate_and_clean_data(self, transactions: List[Dict]) -> Union[pd.DataFrame, List[Dict]]:
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
                        lambda x: 'credit' if x > 0 else 'debit'
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
        seen = set()
        
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
            except:
                continue
            
            # Validate amount
            try:
                txn['amount'] = float(txn['amount'])
            except:
                continue
            
            # Deduplicate
            key = (txn['date'], txn['description'], round(txn['amount'], 2))
            if key not in seen:
                seen.add(key)
                cleaned.append(txn)
        
        # Sort by date
        try:
            cleaned.sort(key=lambda x: x['date'])
        except:
            pass
        
        return cleaned
    
    def process_pdf(self, 
                   pdf_path: str,
                   loader_names: List[str] = None,
                   categorize: bool = True,
                   save_debug: bool = False) -> Union[pd.DataFrame, List[Dict]]:
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
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return pd.DataFrame() if pd else []

    def process_csv(self,
                    csv_path: str,
                    categorize: bool = True,
                    save_debug: bool = False) -> Union[pd.DataFrame, List[Dict]]:
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


def _normalize_date(value: str) -> str:
    """Normalize date using exact patterns from test-main.py"""
    value = value.strip()
    
    # Standard date formats from test-main.py validator
    fmts = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y%m%d']
    for fmt in fmts:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If all else fails, return the original value
    logger.warning(f"Could not normalize date: {value}")
    return value


# Legacy functions for backward compatibility - these now use the new BankTransactionExtractor

def build_bank_transactions_prompt(text: str) -> str:
    """Legacy function - use BankTransactionExtractor._create_extraction_prompt instead"""
    # Use the same prompt template as the new class
    return f"""You are a financial data extraction expert. Extract bank transactions from the text below.

RULES:
1. Look for dates, descriptions, and amounts
2. Amounts with "-" or in parentheses are debits (money out)
3. Positive amounts are credits (money in)
4. Convert dates to YYYY-MM-DD format
5. Extract merchant names clearly
6. Only extract actual transactions, not headers or summaries

TEXT:
{text}

Return ONLY a JSON array like this example:
[
  {{"date": "2024-01-15", "description": "GROCERY STORE", "amount": -45.67, "transaction_type": "debit", "balance": 1234.56}},
  {{"date": "2024-01-16", "description": "SALARY DEPOSIT", "amount": 2500.00, "transaction_type": "credit", "balance": 3689.89}}
]

JSON:"""


def _enhanced_regex_extraction(text: str) -> List[Dict[str, Any]]:
    """Legacy function - use BankTransactionExtractor._extract_with_regex instead"""
    transactions = []
    
    # Look for transaction-like patterns - exact from test-main.py
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
            except:
                continue
    
    return transactions


def _preprocess_bank_text(raw_text: str) -> str:
    """Legacy function - use BankTransactionExtractor.preprocess_documents instead"""
    text = raw_text
    
    # Clean PDF artifacts - exact from test-main.py
    text = re.sub(r'Page \d+ of \d+', '', text)
    text = re.sub(r'Statement Period:.*?\n', '', text)
    text = re.sub(r'Account Summary.*?\n', '', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def _normalize_column_name(name: str) -> str:
    """Normalize CSV column names by removing spaces, punctuation, and lowercasing.
    Example: 'Date Posted' -> 'dateposted', 'Transaction Amount' -> 'transactionamount'
    """
    try:
        import re as _re
        return _re.sub(r"[^a-z0-9]", "", (name or "").strip().lower())
    except Exception:
        return (name or "").strip().lower()


def _parse_csv_file_basic(csv_path: str) -> List[Dict[str, Any]]:
    """Robust CSV fallback parser for bank exports with possible preambles.

    - Skips preamble lines before the real header
    - Handles common header variants: Date Posted, Transaction Amount, Transaction Type, Description
    - Converts YYYYMMDD to YYYY-MM-DD
    - Parses amounts, handling '$' and comma separators
    - Infers transaction_type from amount sign if missing
    - Skips obviously invalid/empty rows
    """
    import csv as _csv
    rows: List[Dict[str, Any]] = []
    try:
        # Read all lines first to locate the header row
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            lines = [ln.rstrip("\n\r") for ln in f]

        # Find header index: line with at least 3 commas and includes expected keywords
        header_idx = -1
        for i, ln in enumerate(lines):
            if not ln or ln.strip() == "":
                continue
            comma_count = ln.count(",")
            if comma_count < 2:
                continue
            probe = [c.strip().lower() for c in ln.split(",")]
            joined = ",".join(probe)
            if ("date" in joined or "posted" in joined) and ("amount" in joined or "description" in joined):
                header_idx = i
                break

        if header_idx == -1:
            return []

        header = lines[header_idx]
        data_lines = lines[header_idx:]
        reader = _csv.DictReader(data_lines)

        # Build a map from normalized header to actual keys
        norm_to_key: Dict[str, str] = {}
        for key in reader.fieldnames or []:
            norm_to_key[_normalize_column_name(key)] = key

        # Helper to get column by synonyms
        def key_for(*candidates: str) -> Optional[str]:
            for cand in candidates:
                if cand in norm_to_key:
                    return norm_to_key[cand]
            return None

        date_key = key_for("date", "dateposted", "transactiondate", "transdate")
        desc_key = key_for("description", "details", "memo", "payee", "narration")
        amt_key = key_for("amount", "transactionamount", "value", "amt")
        type_key = key_for("transactiontype", "type", "creditdebit", "debitcredit")
        bal_key = key_for("balance", "runningbalance")

        import re as _re
        for r in reader:
            try:
                raw_date = (r.get(date_key) if date_key else "") or ""
                raw_desc = (r.get(desc_key) if desc_key else "") or ""
                raw_amt = (r.get(amt_key) if amt_key else "")
                raw_type = (r.get(type_key) if type_key else "")
                raw_bal = (r.get(bal_key) if bal_key else "")

                # Skip empty lines
                if not raw_date and not raw_desc and not raw_amt and not raw_type:
                    continue

                # Normalize date (support YYYYMMDD too)
                dt = _normalize_date(str(raw_date).strip())
                # Require strict YYYY-MM-DD to avoid counting stray lines
                if not dt or not _re.match(r"^\d{4}-\d{2}-\d{2}$", dt):
                    # If date cannot be normalized, skip
                    continue

                # Parse amount (required)
                if raw_amt in (None, ""):
                    # Require an amount field to avoid counting stray lines
                    continue
                try:
                    amt_val = float(str(raw_amt).replace(",", "").replace("$", "").strip())
                except Exception:
                    # If amount cannot be parsed, skip this row
                    logger.warning(f"Could not parse amount: {raw_amt}")
                    continue

                # If amount is zero but type suggests direction, keep but still validate description
                desc_text = str(raw_desc).strip()
                if not desc_text:
                    # Require a description to reduce false positives
                    logger.warning(f"No description found for amount: {raw_amt}")
                    continue

                # Balance (optional)
                bal_val = None
                if raw_bal not in (None, ""):
                    try:
                        bal_val = float(str(raw_bal).replace(",", "").replace("$", "").strip())
                    except Exception:
                        logger.warning(f"Could not parse balance: {raw_bal}")
                        bal_val = None

                # Transaction type
                tx_type = str(raw_type or "").strip().lower()
                if tx_type not in ("debit", "credit"):
                    tx_type = "debit" if amt_val < 0 else "credit"

                rows.append({
                    "date": dt,
                    "description": desc_text,
                    "amount": amt_val,
                    "transaction_type": tx_type,
                    "balance": bal_val,
                })
            except Exception:
                continue

        # Deduplicate and sort
        if rows:
            rows = _clean_and_deduplicate_transactions(rows)
        return rows
    except Exception as e:
        logger.error(f"CSV basic parse failed: {e}")
        return []

def _clean_and_deduplicate_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Legacy function - use BankTransactionExtractor.validate_and_clean_data instead"""
    if not transactions:
        return []
    
    # Remove duplicates
    seen = set()
    unique_transactions = []
    
    for txn in transactions:
        # Create a key for deduplication
        key = (txn.get("date", ""), txn.get("description", ""), round(float(txn.get("amount", 0)), 2))
        
        if key not in seen:
            seen.add(key)
            unique_transactions.append(txn)
    
    # Sort by date
    try:
        unique_transactions.sort(key=lambda x: x.get("date", ""))
    except:
        pass
    
    return unique_transactions


def process_bank_pdf_with_llm(pdf_path: str, ai_config: Optional[Dict[str, Any]] = None, db: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Enhanced LLM-based extraction using BankTransactionExtractor from test-main.py

    Raises BankLLMUnavailableError if LLM is unavailable and fallback extraction yields no transactions,
    so callers can implement retries/backoff.
    """
    logger.info(f"Processing bank PDF: {pdf_path}")
    
    try:
        # Configure model based on ai_config or environment
        model_name = "gpt-oss:latest"
        base_url = "http://localhost:11434"
        
        if ai_config:
            provider_name = ai_config.get("provider_name", "ollama")
            model_name = ai_config.get("model_name", "gpt-oss:latest")
            logger.info(f"🔧 Using AI config from database: {provider_name} model={model_name}")
            
            # Use the new UniversalBankTransactionExtractor for all providers
            try:
                extractor = UniversalBankTransactionExtractor(
                    ai_config=ai_config,
                    temperature=0.1,
                    chunk_size=3000,
                    chunk_overlap=150,
                    request_timeout=120
                )
            except Exception as e:
                logger.warning(f"Failed to initialize UniversalBankTransactionExtractor: {e}")
                logger.info("Falling back to regex extraction")
                # Fallback to regex extraction
                try:
                    from pathlib import Path as _P
                    ext = _P(pdf_path).suffix.lower()
                    if ext == ".csv":
                        txns = _parse_csv_file_basic(pdf_path)
                    else:
                        try:
                            from pypdf import PdfReader
                        except ImportError:
                            logger.error("pypdf not available for fallback extraction")
                            return []
                        texts = []
                        with open(pdf_path, "rb") as f:
                            reader = PdfReader(f)
                            for page in reader.pages:
                                texts.append(page.extract_text() or "")
                        raw_text = "\n\n".join(texts)
                        text = _preprocess_bank_text(raw_text)
                        txns = _enhanced_regex_extraction(text)
                    return txns
                except Exception as fallback_e:
                    logger.error(f"Fallback extraction failed: {fallback_e}")
                    return []
        else:
            # Fallback to environment variables - create ai_config from env vars
            model_name = os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
            base_url = os.getenv("LLM_API_BASE", "http://localhost:11434")
            logger.info(f"⚠️ Using environment variables: model={model_name} base_url={base_url}")
            
            # Create ai_config from environment variables
            ai_config = {
                "provider_name": "ollama",
                "model_name": model_name,
                "provider_url": base_url,
                "api_key": None
            }
            
            try:
                extractor = UniversalBankTransactionExtractor(
                    ai_config=ai_config,
                    temperature=0.1,
                    chunk_size=3000,
                    chunk_overlap=150,
                    request_timeout=120
                )
            except Exception as e:
                logger.warning(f"Failed to initialize BankTransactionExtractor: {e}")
                logger.info("Falling back to legacy regex extraction")
                # Fallback to simple PDF loading and regex extraction
                try:
                    from pathlib import Path as _P
                    ext = _P(pdf_path).suffix.lower()
                    if ext == ".csv":
                        # Robust CSV fallback parser that skips preamble lines
                        txns = _parse_csv_file_basic(pdf_path)
                    else:
                        # Simple fallback PDF loader
                        try:
                            from pypdf import PdfReader
                        except ImportError:
                            logger.error("pypdf not available for fallback extraction")
                            raise BankLLMUnavailableError("LLM not reachable and fallback unavailable")
                        texts = []
                        with open(pdf_path, "rb") as f:
                            reader = PdfReader(f)
                            for page in reader.pages:
                                texts.append(page.extract_text() or "")
                        raw_text = "\n\n".join(texts)
                        text = _preprocess_bank_text(raw_text)
                        txns = _enhanced_regex_extraction(text)
                    if not txns:
                        # Signal to caller to retry later
                        raise BankLLMUnavailableError("LLM not reachable; no transactions via fallback")
                    return txns
                except BankLLMUnavailableError:
                    raise
                except Exception as fallback_e:
                    logger.error(f"Fallback extraction also failed: {fallback_e}")
                    raise BankLLMUnavailableError("LLM not reachable and fallback failed")
        
        # Dispatch based on file extension (supports PDF and CSV)
        from pathlib import Path as _P
        _ext = _P(pdf_path).suffix.lower()
        if _ext == ".csv":
            df = extractor.process_csv(pdf_path, categorize=True, save_debug=False)
        else:
            df = extractor.process_pdf(
                pdf_path,
                loader_names=['pymupdf', 'pdfplumber', 'pdfium2', 'pypdf'],
                categorize=True,
                save_debug=False
            )
        
        # Convert pandas DataFrame back to list of dicts for compatibility
        if not df.empty:
            transactions = df.to_dict('records')
            # Convert datetime objects to strings for JSON serialization
            for txn in transactions:
                if 'date' in txn and hasattr(txn['date'], 'strftime'):
                    txn['date'] = txn['date'].strftime('%Y-%m-%d')

            # Track AI usage if ai_config was used and we have a db session
            if ai_config and db:
                track_ai_usage(db, ai_config)

            return transactions
        else:
            return []
            
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        # Final fallback to regex extraction
        try:
            from pathlib import Path as _P
            _ext = _P(pdf_path).suffix.lower()
            if _ext == ".csv":
                # Robust CSV fallback
                return _parse_csv_file_basic(pdf_path)
            else:
                try:
                    from pypdf import PdfReader
                except ImportError:
                    logger.error("pypdf not available for final fallback extraction")
                    return []
                texts = []
                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        texts.append(page.extract_text() or "")
                raw_text = "\n\n".join(texts)
                text = _preprocess_bank_text(raw_text)
                return _enhanced_regex_extraction(text)
        except Exception as final_e:
            logger.error(f"Final fallback extraction failed: {final_e}")
            return []


def extract_transactions_from_pdf_paths(pdf_paths: List[str]) -> List[Dict[str, Any]]:
    """Extract transactions from PDF paths using BankTransactionExtractor"""
    all_transactions = []
    
    # Try to use the new BankTransactionExtractor first
    try:
        model_name = os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        extractor = BankTransactionExtractor(
            model_name=model_name,
            ollama_base_url=base_url,
            temperature=0.1,
            chunk_size=3000,
            chunk_overlap=150,
            request_timeout=120
        )
        
        for pdf_path in pdf_paths:
            try:
                logger.info(f"Processing {pdf_path} with BankTransactionExtractor")
                df = extractor.process_pdf(pdf_path, categorize=False, save_debug=False)
                
                if not df.empty:
                    transactions = df.to_dict('records')
                    # Convert datetime objects to strings
                    for txn in transactions:
                        if 'date' in txn and hasattr(txn['date'], 'strftime'):
                            txn['date'] = txn['date'].strftime('%Y-%m-%d')
                    all_transactions.extend(transactions)
                    
            except Exception as e:
                logger.error(f"Failed to process {pdf_path} with BankTransactionExtractor: {e}")
                # Fallback to regex extraction for this file
                try:
                    try:
                        from pypdf import PdfReader
                    except ImportError:
                        logger.error(f"pypdf not available for {pdf_path}")
                        continue
                        
                    texts = []
                    with open(pdf_path, "rb") as f:
                        reader = PdfReader(f)
                        for page in reader.pages:
                            texts.append(page.extract_text() or "")
                    raw_text = "\n\n".join(texts)
                    text = _preprocess_bank_text(raw_text)
                    transactions = _enhanced_regex_extraction(text)
                    all_transactions.extend(transactions)
                except Exception as regex_e:
                    logger.error(f"Regex fallback also failed for {pdf_path}: {regex_e}")
                    continue
        
    except Exception as e:
        logger.error(f"Failed to initialize BankTransactionExtractor: {e}")
        # Fallback to simple regex extraction for all files
        for pdf_path in pdf_paths:
            try:
                try:
                    from pypdf import PdfReader
                except ImportError:
                    logger.error(f"pypdf not available for {pdf_path}")
                    continue
                    
                texts = []
                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        texts.append(page.extract_text() or "")
                raw_text = "\n\n".join(texts)
                text = _preprocess_bank_text(raw_text)
                transactions = _enhanced_regex_extraction(text)
                all_transactions.extend(transactions)
            except Exception as file_e:
                logger.error(f"Failed to process {pdf_path}: {file_e}")
                continue
    
    return _clean_and_deduplicate_transactions(all_transactions)


class BankStatementExtractor:
    """Legacy extractor wrapper - uses new BankTransactionExtractor internally"""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "gpt-oss:latest")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_available = self._check_ollama()
        
        # Initialize the new extractor if possible
        try:
            self._extractor = BankTransactionExtractor(
                model_name=self.model_name,
                ollama_base_url=self.base_url,
                temperature=0.1,
                chunk_size=3000,
                chunk_overlap=150,
                request_timeout=120
            )
        except Exception as e:
            logger.warning(f"Could not initialize BankTransactionExtractor: {e}")
            self._extractor = None

    def _check_ollama(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            models = [m.get("name") for m in (resp.json().get("models") or [])]
            return self.model_name in models
        except Exception:
            return False

    def extract_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        return process_bank_pdf_with_llm(pdf_path)

    def extract_from_files(self, files: List[str]) -> List[Dict[str, Any]]:
        return extract_transactions_from_pdf_paths(files)


def is_bank_llm_reachable(ai_config: Optional[Dict[str, Any]] = None) -> bool:
    """Lightweight reachability check for the bank LLM endpoint/model.

    Returns True if the configured provider is reachable. Supports all LiteLLM-compatible providers.
    """
    try:
        if not ai_config:
            # Fallback to environment variables (assume Ollama)
            ai_config = {
                "provider_name": "ollama",
                "model_name": os.getenv("OLLAMA_MODEL", "gpt-oss:latest"),
                "provider_url": os.getenv("LLM_API_BASE", "http://localhost:11434"),
                "api_key": None
            }
        
        provider_name = ai_config.get("provider_name", "ollama")
        logger.info(f"🔍 Testing reachability for provider: {provider_name}")
        
        # For Ollama, test the /api/tags endpoint
        if provider_name == "ollama":
            model_name = ai_config.get("model_name", "gpt-oss:latest")
            provider_url = ai_config.get("provider_url", "http://localhost:11434")
            
            if provider_url:
                # Clean up the URL and extract base URL
                url = provider_url.strip().rstrip('/')
                m = re.match(r"^(https?://[^/]+)(/api.*)?$", url)
                base_url = m.group(1) if m else url
            else:
                base_url = "http://localhost:11434"

            resp = requests.get(f"{base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            data = resp.json() or {}
            models = [m.get("name") for m in (data.get("models") or [])]
            return model_name in models
        
        else:
            # For other providers, use LiteLLM to test connection
            try:
                from litellm import completion
                
                # Create a temporary extractor to test connection
                temp_extractor = UniversalBankTransactionExtractor(
                    ai_config=ai_config,
                    temperature=0.1
                )
                # If initialization succeeds, the connection test passed
                return True
                
            except Exception as e:
                logger.warning(f"LiteLLM connection test failed for {provider_name}: {e}")
                return False
        
    except Exception as e:
        logger.warning(f"Reachability check failed: {e}")
        return False