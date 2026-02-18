"""
Unit tests for LLMExtractionService

Tests the LLM-powered holdings extraction from PDF and CSV files.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from decimal import Decimal

from plugins.investments.services.llm_extraction_service import LLMExtractionService


class TestLLMExtractionService:
    """Test cases for LLMExtractionService"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return Mock()

    @pytest.fixture
    def mock_ai_config(self):
        """Create mock AI configuration"""
        return {
            "provider_name": "openai",
            "provider_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "model_name": "gpt-4",
            "ocr_enabled": True
        }

    @pytest.fixture
    def mock_prompt_service(self):
        """Create mock prompt service"""
        service = Mock()
        service.get_prompt.return_value = "Extract holdings from: {document_content}"
        return service

    @pytest.fixture
    def mock_ocr_service(self):
        """Create mock OCR service"""
        service = Mock()
        result = Mock()
        result.success = True
        result.text = "AAPL 100 shares at $150 per share"
        result.error_message = None
        service.extract_text.return_value = result
        return service

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM"""
        llm = Mock()
        response = Mock()
        response.content = json.dumps({
            "holdings": [
                {
                    "security_symbol": "AAPL",
                    "security_name": "Apple Inc.",
                    "quantity": 100,
                    "cost_basis": 15000,
                    "purchase_date": "2024-01-15",
                    "security_type": "STOCK",
                    "asset_class": "STOCKS"
                }
            ],
            "extraction_confidence": 0.95,
            "notes": "Successfully extracted holdings"
        })
        llm.invoke.return_value = response
        return llm

    @pytest.fixture
    def extraction_service(self, mock_db, mock_ai_config, mock_prompt_service, mock_ocr_service, mock_llm):
        """Create LLMExtractionService with mocked dependencies"""
        with patch('plugins.investments.services.llm_extraction_service.AIConfigService') as mock_ai_service:
            mock_ai_service.get_ai_config.return_value = mock_ai_config

            with patch('plugins.investments.services.llm_extraction_service.get_prompt_service') as mock_prompt_getter:
                mock_prompt_getter.return_value = mock_prompt_service

                with patch('plugins.investments.services.llm_extraction_service.UnifiedOCRService') as mock_ocr_class:
                    mock_ocr_class.return_value = mock_ocr_service

                    service = LLMExtractionService(mock_db)
                    service.llm = mock_llm
                    return service

    @pytest.mark.asyncio
    async def test_extract_holdings_from_pdf_success(self, extraction_service, mock_ocr_service, mock_llm):
        """Test successful PDF holdings extraction"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            holdings = await extraction_service.extract_holdings_from_pdf(pdf_path)

            assert len(holdings) == 1
            assert holdings[0]["security_symbol"] == "AAPL"
            assert holdings[0]["quantity"] == 100
            assert holdings[0]["cost_basis"] == 15000

            mock_ocr_service.extract_text.assert_called_once()
            mock_llm.invoke.assert_called_once()
        finally:
            Path(pdf_path).unlink()

    @pytest.mark.asyncio
    async def test_extract_holdings_from_pdf_no_ocr_service(self, mock_db):
        """Test PDF extraction fails when OCR service unavailable"""
        with patch('plugins.investments.services.llm_extraction_service.AIConfigService') as mock_ai_service:
            mock_ai_service.get_ai_config.return_value = None

            with patch('plugins.investments.services.llm_extraction_service.get_prompt_service'):
                service = LLMExtractionService(mock_db)

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    pdf_path = f.name

                try:
                    with pytest.raises(ValueError, match="OCR service not available"):
                        await service.extract_holdings_from_pdf(pdf_path)
                finally:
                    Path(pdf_path).unlink()

    @pytest.mark.asyncio
    async def test_extract_holdings_from_csv_success(self, extraction_service, mock_llm):
        """Test successful CSV holdings extraction"""
        csv_content = """Symbol,Name,Quantity,CostBasis
AAPL,Apple Inc.,100,15000
MSFT,Microsoft Corp.,50,12000"""

        with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            holdings = await extraction_service.extract_holdings_from_csv(csv_path)

            assert len(holdings) == 1
            assert holdings[0]["security_symbol"] == "AAPL"

            mock_llm.invoke.assert_called_once()
        finally:
            Path(csv_path).unlink()

    @pytest.mark.asyncio
    async def test_extract_holdings_from_csv_file_not_found(self, extraction_service):
        """Test CSV extraction fails when file not found"""
        with pytest.raises(ValueError, match="Failed to extract portfolio data from CSV"):
            await extraction_service.extract_holdings_from_csv("/nonexistent/file.csv")

    def test_parse_extracted_holdings_valid_json(self, extraction_service):
        """Test parsing valid JSON response"""
        response = json.dumps({
            "holdings": [
                {
                    "security_symbol": "AAPL",
                    "security_name": "Apple Inc.",
                    "quantity": 100,
                    "cost_basis": 15000,
                    "purchase_date": "2024-01-15",
                    "security_type": "STOCK",
                    "asset_class": "STOCKS"
                },
                {
                    "security_symbol": "MSFT",
                    "security_name": "Microsoft Corp.",
                    "quantity": 50,
                    "cost_basis": 12000,
                    "purchase_date": "2024-02-01",
                    "security_type": "STOCK",
                    "asset_class": "STOCKS"
                }
            ],
            "extraction_confidence": 0.95
        })

        holdings = extraction_service.parse_extracted_holdings(response)

        assert len(holdings) == 2
        assert holdings[0]["security_symbol"] == "AAPL"
        assert holdings[1]["security_symbol"] == "MSFT"

    def test_parse_extracted_holdings_json_array(self, extraction_service):
        """Test parsing JSON array response"""
        response = json.dumps([
            {
                "security_symbol": "AAPL",
                "security_name": "Apple Inc.",
                "quantity": 100,
                "cost_basis": 15000
            }
        ])

        holdings = extraction_service.parse_extracted_holdings(response)

        assert len(holdings) == 1
        assert holdings[0]["security_symbol"] == "AAPL"

    def test_parse_extracted_holdings_with_markdown(self, extraction_service):
        """Test parsing JSON response with markdown code blocks"""
        response = """```json
{
  "holdings": [
    {
      "security_symbol": "AAPL",
      "security_name": "Apple Inc.",
      "quantity": 100,
      "cost_basis": 15000
    }
  ]
}
```"""

        holdings = extraction_service.parse_extracted_holdings(response)

        assert len(holdings) == 1
        assert holdings[0]["security_symbol"] == "AAPL"

    def test_parse_extracted_holdings_error_response(self, extraction_service):
        """Test parsing error response from LLM"""
        response = json.dumps({
            "error": "Could not extract holdings from document",
            "extraction_confidence": 0
        })

        with pytest.raises(ValueError, match="LLM returned error"):
            extraction_service.parse_extracted_holdings(response)

    def test_parse_extracted_holdings_invalid_json(self, extraction_service):
        """Test parsing invalid JSON response"""
        response = "This is not valid JSON {invalid}"

        with pytest.raises(ValueError, match="Invalid JSON in LLM response"):
            extraction_service.parse_extracted_holdings(response)

    def test_parse_extracted_holdings_missing_holdings_array(self, extraction_service):
        """Test parsing response without holdings array"""
        response = json.dumps({
            "data": "some data",
            "extraction_confidence": 0.95
        })

        with pytest.raises(ValueError, match="Response does not contain holdings array"):
            extraction_service.parse_extracted_holdings(response)

    def test_parse_extracted_holdings_holdings_not_list(self, extraction_service):
        """Test parsing response where holdings is not a list"""
        response = json.dumps({
            "holdings": "not a list",
            "extraction_confidence": 0.95
        })

        with pytest.raises(ValueError, match="Holdings data is not a list"):
            extraction_service.parse_extracted_holdings(response)

    @pytest.mark.asyncio
    async def test_extract_with_llm_no_llm_available(self, mock_db):
        """Test extraction fails when LLM not available"""
        with patch('plugins.investments.services.llm_extraction_service.AIConfigService') as mock_ai_service:
            mock_ai_service.get_ai_config.return_value = None

            with patch('plugins.investments.services.llm_extraction_service.get_prompt_service'):
                service = LLMExtractionService(mock_db)

                with pytest.raises(ValueError, match="LLM not available"):
                    await service._extract_with_llm("test content", "pdf")

    @pytest.mark.asyncio
    async def test_extract_with_llm_invalid_response(self, extraction_service, mock_llm):
        """Test extraction with invalid LLM response"""
        mock_llm.invoke.return_value = Mock(content="invalid json")

        with pytest.raises(ValueError, match="Invalid JSON in LLM response"):
            await extraction_service._extract_with_llm("test content", "pdf")

    def test_get_default_extraction_prompt(self, extraction_service):
        """Test default extraction prompt generation"""
        prompt = extraction_service._get_default_extraction_prompt()

        assert "financial data extraction specialist" in prompt.lower()
        assert "security_symbol" in prompt
        assert "quantity" in prompt
        assert "cost_basis" in prompt
        assert "market_price" in prompt
        assert "{{ document_content }}" in prompt
        assert "{{ document_type }}" in prompt

    @pytest.mark.asyncio
    async def test_extract_holdings_from_pdf_ocr_failure(self, extraction_service, mock_ocr_service):
        """Test PDF extraction when OCR fails"""
        mock_ocr_service.extract_text.return_value = Mock(
            success=False,
            error_message="OCR processing failed",
            text=None
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            with pytest.raises(ValueError, match="PDF text extraction failed"):
                await extraction_service.extract_holdings_from_pdf(pdf_path)
        finally:
            Path(pdf_path).unlink()

    @pytest.mark.asyncio
    async def test_extract_holdings_multiple_holdings(self, extraction_service, mock_llm):
        """Test extraction of multiple holdings"""
        mock_llm.invoke.return_value = Mock(content=json.dumps({
            "holdings": [
                {
                    "security_symbol": "AAPL",
                    "security_name": "Apple Inc.",
                    "quantity": 100,
                    "cost_basis": 15000,
                    "security_type": "STOCK",
                    "asset_class": "STOCKS"
                },
                {
                    "security_symbol": "MSFT",
                    "security_name": "Microsoft Corp.",
                    "quantity": 50,
                    "cost_basis": 12000,
                    "security_type": "STOCK",
                    "asset_class": "STOCKS"
                },
                {
                    "security_symbol": "VTSAX",
                    "security_name": "Vanguard Total Stock Market ETF",
                    "quantity": 200,
                    "cost_basis": 20000,
                    "security_type": "ETF",
                    "asset_class": "STOCKS"
                }
            ]
        }))

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            holdings = await extraction_service.extract_holdings_from_pdf(pdf_path)

            assert len(holdings) == 3
            assert holdings[0]["security_symbol"] == "AAPL"
            assert holdings[1]["security_symbol"] == "MSFT"
            assert holdings[2]["security_symbol"] == "VTSAX"
        finally:
            Path(pdf_path).unlink()
