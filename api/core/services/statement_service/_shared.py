"""Shared types, models, constants, and utility functions for statement_service."""
import contextlib
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List as TypingList

logger = logging.getLogger(__name__)


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
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    # LLMChain is deprecated in LangChain v1.0+, we'll use direct LLM calls instead
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_ollama import OllamaLLM
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not available - falling back to basic functionality")

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

        def format(self, **kwargs):
            # Safer formatting that doesn't trigger on other braces (like JSON)
            result = self.template
            for k, v in kwargs.items():
                result = result.replace(f"{{{k}}}", str(v))
                # Also handle double braces if they exist
                result = result.replace(f"{{{{{k}}}}}", str(v))
            return result

    # LLMChain is deprecated in LangChain v1.0+, no fallback needed

    class RecursiveCharacterTextSplitter:
        def __init__(self, **kwargs):
            self.chunk_size = kwargs.get('chunk_size', 6000)
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
    card_type: str = Field(default="debit", description="debit|credit")

    @model_validator(mode='before')
    @classmethod
    def fix_transaction_type_by_amount(cls, data: Any) -> Any:
        if isinstance(data, dict):
            amount = data.get('amount')
            card_type = data.get('card_type', 'debit')
            if amount is not None:
                try:
                    amt = float(amount)
                    if card_type == 'credit':
                        data['transaction_type'] = 'credit' if amt < 0 else 'debit'
                    else:
                        data['transaction_type'] = 'debit' if amt < 0 else 'credit'
                except (ValueError, TypeError):
                    pass
        return data

    @field_validator('transaction_type', mode='before')
    @classmethod
    def validate_transaction_type(cls, v):
        try:
            vv = (v or '').lower()
            if vv not in ['debit', 'credit']:
                return 'debit' if vv == '' else ('credit' if vv.startswith('c') or vv == '-' else 'debit')
            return vv
        except Exception:
            return 'debit'

    @field_validator('date', mode='before')
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


def _normalize_column_name(name: str) -> str:
    """Normalize CSV column names by removing spaces, punctuation, and lowercasing.
    Example: 'Date Posted' -> 'dateposted', 'Transaction Amount' -> 'transactionamount'
    """
    try:
        return re.sub(r"[^a-z0-9]", "", (name or "").strip().lower())
    except Exception:
        return (name or "").strip().lower()


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

    try:
        unique_transactions.sort(key=lambda x: x.get("date", ""))
    except Exception:
        pass

    return unique_transactions
