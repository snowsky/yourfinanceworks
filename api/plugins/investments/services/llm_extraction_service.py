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
                from langchain_community.llms import Ollama
                self.llm = Ollama(
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
        logger.info(f"Extracting holdings from PDF: {file_path}")

        if not self.ocr_service:
            raise ValueError("OCR service not available for PDF extraction")

        try:
            # Extract text from PDF
            result = self.ocr_service.extract_text(file_path, DocumentType.GENERIC_DOCUMENT)

            if not result.success:
                raise ValueError(f"PDF text extraction failed: {result.error_message}")

            extracted_text = result.text
            logger.info(f"✓ Extracted {len(extracted_text)} characters from PDF")

            # Send to LLM for holdings extraction
            holdings = await self._extract_with_llm(extracted_text, "pdf")

            return holdings

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ValueError(f"Failed to extract holdings from PDF: {str(e)}")

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
        logger.info(f"Extracting holdings from CSV: {file_path}")

        try:
            # Read CSV file
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()

            logger.info(f"✓ Read CSV file: {len(csv_content)} characters")

            # Send to LLM for holdings extraction
            holdings = await self._extract_with_llm(csv_content, "csv")

            return holdings

        except Exception as e:
            logger.error(f"CSV extraction failed: {e}")
            raise ValueError(f"Failed to extract holdings from CSV: {str(e)}")

    async def _extract_with_llm(self, content: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Send content to LLM for holdings extraction.

        Args:
            content: File content (text or CSV)
            file_type: Type of file ("pdf" or "csv")

        Returns:
            List of extracted holdings dictionaries

        Raises:
            ValueError: If LLM extraction fails
        """
        if not self.llm:
            raise ValueError("LLM not available for extraction")

        try:
            # Get extraction prompt from prompt management system
            prompt_text = self.prompt_service.get_prompt(
                name="holdings_extraction",
                variables={
                    "document_content": content,
                    "document_type": file_type
                },
                fallback_prompt=self._get_default_extraction_prompt()
            )

            logger.info(f"Sending {len(content)} characters to LLM for extraction")

            # Call LLM
            response = self.llm.invoke(prompt_text)

            # Parse response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            logger.info(f"✓ LLM response received: {len(response_text)} characters")

            # Parse extracted holdings
            holdings = self.parse_extracted_holdings(response_text)

            logger.info(f"✓ Extracted {len(holdings)} holdings from LLM response")

            return holdings

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise ValueError(f"Failed to extract holdings with LLM: {str(e)}")

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

    def _get_default_extraction_prompt(self) -> str:
        """Fallback prompt if prompt management system is unavailable."""
        return """You are a financial data extraction specialist. Extract investment holdings information from the provided document.

IMPORTANT: Your response MUST be ONLY a valid raw JSON object.
DO NOT include any markdown formatting (like ```json).
DO NOT include any explanations, introduction, or concluding prose.
ONLY return the JSON.

For each holding found, extract:
- security_symbol: The ticker symbol or identifier (e.g., AAPL)
- security_name: The full name
- quantity: Number of shares
- cost_basis: Total cost basis
- purchase_date: Date of purchase
- security_type: STOCK, BOND, ETF, MUTUAL_FUND, CASH
- asset_class: STOCKS, BONDS, CASH, REAL_ESTATE, COMMODITIES

The JSON structure must be:
{
  "holdings": [
    {
      "security_symbol": "...",
      "security_name": "...",
      "quantity": 0,
      "cost_basis": 0,
      "purchase_date": "...",
      "security_type": "...",
      "asset_class": "..."
    }
  ]
}

Document content:
{{ document_content }}

Document type: {{ document_type }}

JSON ONLY:"""
