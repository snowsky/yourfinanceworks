"""statement_service package — bank statement extraction and processing.

Re-exports all public symbols so existing imports continue to work:
    from core.services.statement_service import process_bank_pdf_with_llm, ...
"""
from ._shared import (
    BankLLMUnavailableError,
    Document,
    LANGCHAIN_AVAILABLE,
    OllamaCallbackHandler,
    PromptTemplate,
    RecursiveCharacterTextSplitter,
    Transaction,
    TransactionListModel,
    TransactionModel,
    _clean_and_deduplicate_transactions,
    _normalize_date,
    _normalize_column_name,
    pd,
)
from .csv_processing import (
    _enhanced_regex_extraction,
    _parse_csv_file_basic,
    _preprocess_bank_text,
    build_bank_transactions_prompt,
)
from .extraction import (
    BankTransactionExtractor,
    UniversalBankTransactionExtractor,
)
from .processing import (
    BankStatementExtractor,
    StatementService,
    extract_transactions_from_pdf_paths,
    is_bank_llm_reachable,
    process_bank_pdf_with_llm,
)

__all__ = [
    # Errors
    "BankLLMUnavailableError",
    # Models / types
    "Transaction",
    "TransactionModel",
    "TransactionListModel",
    # LangChain compatibility shims
    "Document",
    "LANGCHAIN_AVAILABLE",
    "OllamaCallbackHandler",
    "PromptTemplate",
    "RecursiveCharacterTextSplitter",
    "pd",
    # Extraction classes
    "UniversalBankTransactionExtractor",
    "BankTransactionExtractor",
    # Legacy / entry-point
    "BankStatementExtractor",
    "StatementService",
    # Functions
    "process_bank_pdf_with_llm",
    "extract_transactions_from_pdf_paths",
    "is_bank_llm_reachable",
    "build_bank_transactions_prompt",
    "_enhanced_regex_extraction",
    "_preprocess_bank_text",
    "_parse_csv_file_basic",
    "_clean_and_deduplicate_transactions",
    "_normalize_date",
    "_normalize_column_name",
]
