"""
Invoice AI Processing Service

This service provides AI-powered invoice processing capabilities with
intelligent fallback to environment variables when database configurations
are unavailable.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from core.services.ai_config_service import AIConfigService
from core.services.ocr_service import _run_ocr, track_ai_usage

logger = logging.getLogger(__name__)


class InvoiceAIService:
    """
    Service for AI-powered invoice processing with unified configuration management.
    
    Provides OCR extraction, data parsing, and intelligent field extraction
    for invoice documents using multiple AI providers.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the invoice AI service.
        
        Args:
            db_session: Database session for configuration and usage tracking
        """
        self.db_session = db_session
        logger.info("InvoiceAIService initialized")
    
    def get_ai_config(self, require_ocr: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get AI configuration for invoice processing.
        
        Args:
            require_ocr: Whether OCR capability is required
            
        Returns:
            AI configuration dictionary or None
        """
        return AIConfigService.get_ai_config(
            self.db_session, 
            component="invoice", 
            require_ocr=require_ocr
        )
    
    async def extract_invoice_data(
        self, 
        file_path: str, 
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from invoice using AI.
        
        Args:
            file_path: Path to the invoice file
            custom_prompt: Optional custom prompt for extraction
            
        Returns:
            Dictionary with extracted invoice data
        """
        try:
            # Get AI configuration with fallback
            ai_config = self.get_ai_config(require_ocr=True)
            
            if not ai_config:
                logger.warning("No AI configuration available for invoice processing")
                return {
                    "error": "No AI configuration available for invoice processing",
                    "success": False
                }
            
            # Use invoice-specific prompt if not provided
            if not custom_prompt:
                custom_prompt = (
                    "You are an invoice data extraction AI. Extract key invoice fields and respond ONLY with compact JSON. "
                    "Required keys: invoice_number, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD), "
                    "vendor_name, vendor_address, client_name, client_address, "
                    "subtotal, tax_amount, tax_rate, total_amount, currency, "
                    "line_items (array with description, quantity, unit_price, total), "
                    "payment_terms, notes. "
                    "If a field is unknown, set it to null. Do not include any prose."
                )
            
            logger.info(f"Extracting invoice data from {file_path} using {ai_config['provider_name']}")
            
            # Extract data using OCR service
            result = await _run_ocr(file_path, custom_prompt=custom_prompt, ai_config=ai_config)
            
            if isinstance(result, dict) and "error" not in result:
                # Track successful AI usage
                self._track_usage(ai_config, "invoice_extraction", result)
                
                # Add extraction metadata
                result["extraction_metadata"] = {
                    "provider": ai_config["provider_name"],
                    "model": ai_config["model_name"],
                    "component": "invoice",
                    "success": True
                }
                
                logger.info(f"Successfully extracted invoice data: {len(result)} fields")
                return {"success": True, "data": result}
            else:
                logger.error(f"Invoice extraction failed: {result.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": result.get("error", "Invoice extraction failed"),
                    "extraction_metadata": {
                        "provider": ai_config["provider_name"],
                        "model": ai_config["model_name"],
                        "component": "invoice",
                        "success": False
                    }
                }
                
        except Exception as e:
            logger.error(f"Invoice AI processing failed: {e}")
            return {
                "success": False,
                "error": f"Invoice AI processing failed: {str(e)}"
            }
    
    async def classify_invoice_type(self, file_path: str) -> Dict[str, Any]:
        """
        Classify the type of invoice document.
        
        Args:
            file_path: Path to the invoice file
            
        Returns:
            Dictionary with classification results
        """
        try:
            ai_config = self.get_ai_config(require_ocr=True)
            
            if not ai_config:
                return {
                    "success": False,
                    "error": "No AI configuration available for invoice classification"
                }
            
            classification_prompt = (
                "Analyze this invoice document and classify it. Respond ONLY with JSON. "
                "Required keys: document_type (invoice/receipt/bill/statement), "
                "invoice_type (service/product/mixed), complexity (simple/standard/complex), "
                "language, currency_detected, has_line_items (boolean), "
                "estimated_processing_difficulty (low/medium/high). "
                "Do not include any prose."
            )
            
            result = await _run_ocr(file_path, custom_prompt=classification_prompt, ai_config=ai_config)
            
            if isinstance(result, dict) and "error" not in result:
                self._track_usage(ai_config, "invoice_classification", result)
                return {"success": True, "classification": result}
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Classification failed")
                }
                
        except Exception as e:
            logger.error(f"Invoice classification failed: {e}")
            return {
                "success": False,
                "error": f"Invoice classification failed: {str(e)}"
            }
    
    async def validate_invoice_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted invoice data for completeness and accuracy.
        
        Args:
            extracted_data: Previously extracted invoice data
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "completeness_score": 0.0
        }
        
        # Required fields for a complete invoice
        required_fields = [
            "invoice_number", "invoice_date", "vendor_name", 
            "total_amount", "currency"
        ]
        
        # Optional but important fields
        important_fields = [
            "due_date", "client_name", "subtotal", "tax_amount", "line_items"
        ]
        
        # Check required fields
        missing_required = []
        for field in required_fields:
            if not extracted_data.get(field):
                missing_required.append(field)
                validation_results["valid"] = False
        
        if missing_required:
            validation_results["errors"].append(f"Missing required fields: {', '.join(missing_required)}")
        
        # Check important fields
        missing_important = []
        for field in important_fields:
            if not extracted_data.get(field):
                missing_important.append(field)
        
        if missing_important:
            validation_results["warnings"].append(f"Missing important fields: {', '.join(missing_important)}")
        
        # Calculate completeness score
        total_fields = len(required_fields) + len(important_fields)
        present_fields = sum(1 for field in required_fields + important_fields if extracted_data.get(field))
        validation_results["completeness_score"] = (present_fields / total_fields) * 100
        
        # Validate data types and formats
        self._validate_field_formats(extracted_data, validation_results)
        
        return validation_results
    
    def _validate_field_formats(self, data: Dict[str, Any], validation: Dict[str, Any]) -> None:
        """Validate field formats and data types."""
        # Date format validation
        date_fields = ["invoice_date", "due_date"]
        for field in date_fields:
            if data.get(field):
                try:
                    from dateutil import parser as dateparser
                    dateparser.parse(str(data[field]))
                except Exception:
                    validation["errors"].append(f"Invalid date format in {field}: {data[field]}")
                    validation["valid"] = False
        
        # Numeric field validation
        numeric_fields = ["subtotal", "tax_amount", "tax_rate", "total_amount"]
        for field in numeric_fields:
            if data.get(field) is not None:
                try:
                    float(str(data[field]).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    validation["warnings"].append(f"Non-numeric value in {field}: {data[field]}")
        
        # Currency validation
        if data.get("currency"):
            currency = str(data["currency"]).upper()
            valid_currencies = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY", "INR", "BRL"]
            if currency not in valid_currencies:
                validation["warnings"].append(f"Unrecognized currency: {currency}")
    
    def _track_usage(self, ai_config: Dict[str, Any], operation_type: str, result: Dict[str, Any]) -> None:
        """Track AI usage for invoice processing."""
        try:
            # Calculate result metadata
            text_length = 0
            if isinstance(result, dict):
                text_length = sum(len(str(v)) for v in result.values() if isinstance(v, str))
            
            # Track usage with metadata
            track_ai_usage(
                db=self.db_session,
                ai_config=ai_config,
                operation_type=operation_type,
                metadata={
                    "component": "invoice",
                    "operation": operation_type,
                    "result_size": text_length,
                    "fields_extracted": len(result) if isinstance(result, dict) else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to track invoice AI usage: {e}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get invoice processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            ai_config = self.get_ai_config(require_ocr=False)
            
            return {
                "service": "InvoiceAIService",
                "ai_config_available": ai_config is not None,
                "provider": ai_config.get("provider_name") if ai_config else None,
                "model": ai_config.get("model_name") if ai_config else None,
                "ocr_enabled": ai_config.get("ocr_enabled", False) if ai_config else False,
                "config_source": ai_config.get("source") if ai_config else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get invoice processing stats: {e}")
            return {"error": str(e)}


# Convenience functions
async def extract_invoice_data_with_fallback(
    db: Session, 
    file_path: str, 
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to extract invoice data with AI fallback.
    
    Args:
        db: Database session
        file_path: Path to invoice file
        custom_prompt: Optional custom extraction prompt
        
    Returns:
        Dictionary with extraction results
    """
    service = InvoiceAIService(db)
    return await service.extract_invoice_data(file_path, custom_prompt)


def get_invoice_ai_config(db: Session) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get invoice AI configuration.
    
    Args:
        db: Database session
        
    Returns:
        AI configuration dictionary or None
    """
    return AIConfigService.get_ai_config(db, component="invoice", require_ocr=True)