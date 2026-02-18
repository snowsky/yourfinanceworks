"""
LLM Extraction Service for Portfolio Holdings Import

Provides AI-powered extraction of holdings data from PDF and CSV files.
Integrates with the prompt management system and LLM providers.
"""

import json
import logging
import csv
import io
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session

from commercial.ai.services.ai_config_service import AIConfigService
from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig
from commercial.prompt_management.services.prompt_service import get_prompt_service
from core.constants.default_prompts import DEFAULT_PROMPT_TEMPLATES

logger = logging.getLogger(__name__)


class LLMExtractionService:
    """
    Service for extracting holdings data from PDF and CSV files using LLM.

    Handles:
    - PDF text extraction via OCR
    - CSV parsing and validation
    - LLM-based holdings extraction
    - Response parsing and validation
    """

    def __init__(self, db: Session):
        """
        Initialize the LLM extraction service.

        Args:
            db: Database session for accessing AI config and prompts
        """
        self.db = db
        self.ai_config = AIConfigService.get_ai_config(db, component="ocr", require_ocr=True)
        self.prompt_service = get_prompt_service(db)
        self.ocr_service = None
        self.llm = None

        # Initialize OCR service if AI config is available
        if self.ai_config:
            try:
                ocr_config = OCRConfig(ai_config=self.ai_config)
                self.ocr_service = UnifiedOCRService(ocr_config)
                logger.info("✓ OCR service initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OCR service: {e}")

        # Initialize LLM if available
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM for extraction."""
        if not self.ai_config:
            logger.warning("No AI config available for LLM initialization")
            return

        try:
            provider = self.ai_config.get("provider_name", "").lower()

            if provider == "openai":
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(
                    api_key=self.ai_config.get("api_key"),
                    model=self.ai_config.get("model_name"),
                    temperature=0.0,  # Lower temperature for more stable JSON
                    max_tokens=4000,
                    model_kwargs={"response_format": {"type": "json_object"}}
                )
                logger.info(f"✓ OpenAI LLM initialized: {self.ai_config.get('model_name')}")

            elif provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self.llm = ChatAnthropic(
                    api_key=self.ai_config.get("api_key"),
                    model=self.ai_config.get("model_name"),
                    temperature=0.1,
                    max_tokens=4000
                )
                logger.info(f"✓ Anthropic LLM initialized: {self.ai_config.get('model_name')}")

            elif provider == "ollama":
                from langchain_ollama import OllamaLLM
                self.llm = OllamaLLM(
                    base_url=self.ai_config.get("provider_url", "http://localhost:11434"),
                    model=self.ai_config.get("model_name"),
                    temperature=0.1,
                    num_predict=4000
                )
                logger.info(f"✓ Ollama LLM initialized: {self.ai_config.get('model_name')}")

            else:
                logger.warning(f"Unsupported LLM provider: {provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None

    async def extract_holdings_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract holdings data from a PDF file.

        Uses OCR to extract text, then sends to LLM for structured extraction.

        Args:
            file_path: Path to the PDF file

        Returns:
            List of extracted holdings dictionaries

        Raises:
            ValueError: If extraction fails or file is invalid
        """
        result = await self.extract_portfolio_data_from_pdf(file_path, use_ai_extraction=False)
        return result["holdings"]

    async def extract_portfolio_data_from_pdf(
        self, file_path: str, use_ai_extraction: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract portfolio data (holdings and optionally transactions) from a PDF file.

        Uses OCR to extract text, then sends to LLM for structured extraction.

        Args:
            file_path: Path to the PDF file
            use_ai_extraction: If True, use AI to extract both holdings and transaction history

        Returns:
            Dictionary with "holdings" and "transactions" keys

        Raises:
            ValueError: If extraction fails or file is invalid
        """
        logger.info(f"Extracting portfolio data from PDF: {file_path} (AI extraction={use_ai_extraction})")

        if not self.ocr_service:
            raise ValueError("OCR service not available for PDF extraction")

        try:
            # Extract text from PDF
            result = self.ocr_service.extract_text(file_path, DocumentType.GENERIC_DOCUMENT)

            if not result.success:
                raise ValueError(f"PDF text extraction failed: {result.error_message}")

            extracted_text = result.text
            logger.info(f"✓ Extracted {len(extracted_text)} characters from PDF")

            # Send to LLM for extraction
            data = await self._extract_with_llm(extracted_text, "pdf", use_ai_extraction)

            return data

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ValueError(f"Failed to extract portfolio data from PDF: {str(e)}")


    async def extract_holdings_from_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract holdings data from a CSV file.

        Parses CSV and sends to LLM for validation and enrichment.

        Args:
            file_path: Path to the CSV file

        Returns:
            List of extracted holdings dictionaries

        Raises:
            ValueError: If extraction fails or file is invalid
        """
        result = await self.extract_portfolio_data_from_csv(file_path, use_ai_extraction=False)
        return result["holdings"]

    async def extract_portfolio_data_from_csv(
        self, file_path: str, use_ai_extraction: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract portfolio data (holdings and optionally transactions) from a CSV file.

        Parses CSV and sends to LLM for validation and enrichment.

        Args:
            file_path: Path to the CSV file
            use_ai_extraction: If True, use AI to extract both holdings and transaction history

        Returns:
            Dictionary with "holdings" and "transactions" keys

        Raises:
            ValueError: If extraction fails or file is invalid
        """
        logger.info(f"Extracting portfolio data from CSV: {file_path} (AI extraction={use_ai_extraction})")

        try:
            # Read CSV file
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()

            logger.info(f"✓ Read CSV file: {len(csv_content)} characters")

            # Send to LLM for extraction
            data = await self._extract_with_llm(csv_content, "csv", use_ai_extraction)

            return data

        except Exception as e:
            logger.error(f"CSV extraction failed: {e}")
            raise ValueError(f"Failed to extract portfolio data from CSV: {str(e)}")


    async def _extract_with_llm(
        self, content: str, file_type: str, use_ai_extraction: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Send content to LLM for portfolio data extraction.

        Args:
            content: File content (text or CSV)
            file_type: Type of file ("pdf" or "csv")
            use_ai_extraction: If True, use AI to extract both holdings and transaction history

        Returns:
            Dictionary with "holdings" and "transactions" keys

        Raises:
            ValueError: If LLM extraction fails
        """
        if not self.llm:
            raise ValueError("LLM not available for extraction")

        try:
            # Get extraction prompt from prompt management system
            # Always extract both holdings and transactions when using AI
            prompt_text = self.prompt_service.get_prompt(
                name="portfolio_data_extraction",
                variables={
                    "document_content": content,
                    "document_type": file_type
                },
                fallback_prompt=self._get_default_extraction_prompt()
            )



            logger.info(f"Sending {len(content)} characters to LLM for extraction (AI extraction={use_ai_extraction})")

            # Call LLM
            response = self.llm.invoke(prompt_text)

            # Parse response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            logger.info(f"✓ LLM response received: {len(response_text)} characters")

            # Parse extracted data
            data = self.parse_extracted_portfolio_data(response_text, use_ai_extraction)

            logger.info(
                f"✓ Extracted {len(data['holdings'])} holdings and "
                f"{len(data.get('transactions', []))} transactions from LLM response"
            )

            return data

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise ValueError(f"Failed to extract portfolio data with LLM: {str(e)}")


    def parse_extracted_holdings(self, raw_response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response to extract structured holdings data.

        Validates JSON response and extracts holdings array.

        Args:
            raw_response: Raw LLM response text

        Returns:
            List of validated holdings dictionaries

        Raises:
            ValueError: If response cannot be parsed
        """
        logger.info("Parsing LLM response for holdings data")

        try:
            # Parse JSON
            response = raw_response.strip()
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback: if LLM still returned markdown code blocks despite instructions,
                # attempt one-time cleanup. But we prefer LLM to follow instructions.
                if "```json" in response:
                    response = response.split("```json")[-1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[-1].split("```")[0].strip()
                data = json.loads(response)

            # Check for error in response
            if isinstance(data, dict) and "error" in data:
                raise ValueError(f"LLM returned error: {data['error']}")

            # Extract holdings array
            if isinstance(data, dict) and "holdings" in data:
                holdings = data["holdings"]
            elif isinstance(data, list):
                holdings = data
            else:
                raise ValueError("Response does not contain holdings array")

            if not isinstance(holdings, list):
                raise ValueError("Holdings data is not a list")

            logger.info(f"✓ Parsed {len(holdings)} holdings from response")

            return holdings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response content: {raw_response[:500]}")
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to parse holdings: {e}")
            raise ValueError(f"Failed to parse extracted holdings: {str(e)}")

            raise ValueError(f"Failed to parse extracted holdings: {str(e)}")

    def parse_extracted_portfolio_data(
        self, raw_response: str, use_ai_extraction: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse LLM response to extract structured portfolio data.

        Validates JSON response and extracts holdings and optionally transactions.

        Args:
            raw_response: Raw LLM response text
            use_ai_extraction: If True, expect both holdings and transactions in response

        Returns:
            Dictionary with "holdings" and "transactions" keys

        Raises:
            ValueError: If response cannot be parsed
        """
        logger.info(f"Parsing LLM response for portfolio data (AI extraction={use_ai_extraction})")

        try:
            # Parse JSON
            response = raw_response.strip()
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback: if LLM still returned markdown code blocks despite instructions,
                # attempt one-time cleanup. But we prefer LLM to follow instructions.
                if "```json" in response:
                    response = response.split("```json")[-1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[-1].split("```")[0].strip()
                data = json.loads(response)

            # Check for error in response
            if isinstance(data, dict) and "error" in data:
                raise ValueError(f"LLM returned error: {data['error']}")

            # Extract holdings array
            if isinstance(data, dict) and "holdings" in data:
                holdings = data["holdings"]
            elif isinstance(data, list):
                # Backward compatibility: if just a list, treat as holdings
                holdings = data
            else:
                raise ValueError("Response does not contain holdings array")

            if not isinstance(holdings, list):
                raise ValueError("Holdings data is not a list")

            # Extract transactions if requested
            transactions = []
            if use_ai_extraction:
                if isinstance(data, dict) and "transactions" in data:
                    transactions = data["transactions"]
                    if not isinstance(transactions, list):
                        raise ValueError("Transactions data is not a list")
                else:
                    logger.warning("Transactions requested but not found in response")

            logger.info(f"✓ Parsed {len(holdings)} holdings and {len(transactions)} transactions from response")

            return {
                "holdings": holdings,
                "transactions": transactions
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response content: {raw_response[:500]}")
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to parse portfolio data: {e}")
            raise ValueError(f"Failed to parse extracted portfolio data: {str(e)}")

    def _get_default_extraction_prompt(self) -> str:
        """Fallback prompt if prompt management system is unavailable. Always extracts both holdings and transactions."""
        return """You are a financial data extraction specialist. Extract investment holdings and transaction history from the provided document.

IMPORTANT: Your response MUST be ONLY a valid raw JSON object.
DO NOT include any markdown formatting (like ```json).
DO NOT include any explanations, introduction, or concluding prose.
ONLY return the JSON.

=== FIELD DEFINITIONS (read carefully before extracting) ===

For each holding, extract these fields:

1. security_symbol: The ticker symbol (e.g., AAPL, AMD, COIN)
2. security_name: Full name of the security
3. security_type: STOCK, BOND, ETF, MUTUAL_FUND, CASH
4. asset_class: STOCKS, BONDS, CASH, REAL_ESTATE, COMMODITIES

5. quantity: Number of shares or units held
   - Column names: "Quantity", "Shares", "Units", "Position", "Qty"

6. cost_basis: The TOTAL book cost for ALL shares combined (not per-share price)
   - Column names: "Book Cost", "Total Cost", "Cost Basis", "Adjusted Cost Base", "ACB", "Book Value"
   - Example: 40 shares with book cost of $128.84 total -> cost_basis = 128.84
   - WARNING: Do NOT put the market price or current price here

7. market_price: The CURRENT market price PER SHARE as of the statement date
   - Column names: "Market Price", "Current Price", "Last Price", "Price", "Mkt Price", "Unit Price"
   - Example: AMD trading at $214.16/share -> market_price = 214.16
   - Sanity check: market_price x quantity should approximately equal the "Market Value" column
   - WARNING: Do NOT put the book cost or total cost here

8. purchase_date: Date of purchase (YYYY-MM-DD, or null if not shown)
9. asset_class: STOCKS, BONDS, CASH, REAL_ESTATE, COMMODITIES

=== COLUMN DISAMBIGUATION TABLE ===

| PDF Column Label                              | Maps to JSON field |
|-----------------------------------------------|--------------------|
| Book Cost / Book Value / ACB / Adjusted Cost  | cost_basis         |
| Market Price / Current Price / Last Price     | market_price       |
| Market Value / Current Value / Mkt Value      | (do not store)     |
| Quantity / Shares / Position / Units          | quantity           |

For each transaction found, extract:
- transaction_date: Date of the transaction
- transaction_type: BUY, SELL, DIVIDEND, SPLIT, TRANSFER
- security_symbol: The ticker symbol
- security_name: The full name
- quantity: Number of shares (positive for buy, negative for sell)
- price: Price per share
- amount: Total transaction amount
- fees: Transaction fees (if any)

The JSON structure must be:
{
  "holdings": [
    {
      "security_symbol": "AMD",
      "security_name": "Advanced Micro Devices Inc.",
      "quantity": 40,
      "cost_basis": 128.84,
      "market_price": 214.16,
      "purchase_date": null,
      "security_type": "STOCK",
      "asset_class": "STOCKS"
    }
  ],
  "transactions": [
    {
      "transaction_date": "...",
      "transaction_type": "...",
      "security_symbol": "...",
      "security_name": "...",
      "quantity": 0,
      "price": 0,
      "amount": 0,
      "fees": 0
    }
  ]
}

Document content:
{{ document_content }}

Document type: {{ document_type }}

JSON ONLY:"""
