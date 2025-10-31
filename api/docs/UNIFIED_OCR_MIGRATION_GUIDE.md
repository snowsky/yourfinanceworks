# Unified OCR Service Migration Guide

This guide helps you migrate from the existing separate OCR implementations to the new Unified OCR Service.

## Overview

The Unified OCR Service consolidates:
- **Bank Statement OCR** (unstructured + Tesseract)
- **Expense OCR** (AI vision models)
- **Invoice OCR** (AI vision models)

Into a single, consistent interface while preserving the strengths of each approach.

## Benefits of Migration

✅ **Consistent Interface** - Single API for all OCR operations  
✅ **Intelligent Routing** - Automatically chooses the best method for each document type  
✅ **Shared Configuration** - Unified settings and error handling  
✅ **Better Monitoring** - Centralized logging and analytics  
✅ **Easier Testing** - Single service to test and maintain  

## Migration Steps

### 1. Bank Statement Processing

**Before (Old Code):**
```python
from services.statement_service import process_bank_pdf_with_llm
from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor

# Old way - multiple services
extractor = EnhancedPDFTextExtractor(ai_config)
result = extractor.extract_text(pdf_path)
text = result.text

# Or
transactions = process_bank_pdf_with_llm(pdf_path, ai_config)
```

**After (New Code):**
```python
from services.unified_ocr_service import UnifiedOCRService, DocumentType

# New way - unified service
service = UnifiedOCRService()
result = service.extract_text(pdf_path, DocumentType.BANK_STATEMENT)

if result.success:
    text = result.text
    processing_time = result.processing_time
    method_used = result.method
```

### 2. Expense Receipt Processing

**Before (Old Code):**
```python
from services.ocr_service import _run_ocr

# Old way - direct OCR function
result = await _run_ocr(file_path, custom_prompt, ai_config)
```

**After (New Code):**
```python
from services.unified_ocr_service import UnifiedOCRService, DocumentType

# New way - unified service
service = UnifiedOCRService()
result = await service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT)

if result.success:
    expense_data = result.structured_data
    confidence = result.confidence_score
```

### 3. Invoice Processing

**Before (Old Code):**
```python
# Custom OCR implementation for invoices
# (varies by implementation)
```

**After (New Code):**
```python
from services.unified_ocr_service import UnifiedOCRService, DocumentType

service = UnifiedOCRService()
result = await service.extract_structured_data(file_path, DocumentType.INVOICE)

if result.success:
    invoice_data = result.structured_data
```

## Configuration Migration

### Old Configuration (Multiple Places)
```python
# Bank statement config
ocr_config = get_ocr_config()

# Expense config
ai_config = {
    "provider_name": "openai",
    "model_name": "gpt-4-vision",
    "api_key": "...",
}

# Different timeout settings
timeout_seconds = 300
```

### New Configuration (Unified)
```python
from services.unified_ocr_service import OCRConfig

config = OCRConfig(
    # AI configuration for structured extraction
    ai_config={
        "provider_name": "openai",
        "model_name": "gpt-4-vision-preview",
        "api_key": "your-api-key",
    },
    
    # Text extraction settings
    enable_unstructured=True,
    enable_tesseract_fallback=True,
    
    # Structured extraction settings
    enable_ai_vision=True,
    enable_fallback_parsing=True,
    
    # Performance settings
    timeout_seconds=300,
    max_retries=3,
    
    # Quality settings
    min_text_threshold=50,
    min_confidence_threshold=0.7
)

service = UnifiedOCRService(config)
```

## Error Handling Migration

### Old Error Handling (Inconsistent)
```python
try:
    # Bank statement processing
    result = extractor.extract_text(pdf_path)
except OCRTimeoutError:
    # Handle timeout
except OCRProcessingError:
    # Handle processing error

try:
    # Expense processing
    result = await _run_ocr(file_path)
except Exception as e:
    # Generic error handling
```

### New Error Handling (Consistent)
```python
from services.unified_ocr_service import UnifiedOCRService, DocumentType

service = UnifiedOCRService()

# Text extraction
result = service.extract_text(file_path, DocumentType.BANK_STATEMENT)
if not result.success:
    logger.error(f"Text extraction failed: {result.error_message}")
    # Handle error based on result.method and result.processing_time

# Structured extraction
result = await service.extract_structured_data(file_path, DocumentType.EXPENSE_RECEIPT)
if not result.success:
    logger.error(f"Structured extraction failed: {result.error_message}")
    # Consistent error handling across all document types
```

## Backward Compatibility

The service provides backward compatibility functions:

```python
# These functions still work for existing code
from services.unified_ocr_service import extract_expense_data, extract_bank_statement_text

# Expense processing (backward compatible)
expense_data = await extract_expense_data(file_path, ai_config)

# Bank statement processing (backward compatible)
statement_text = extract_bank_statement_text(file_path, ai_config)
```

## Step-by-Step Migration Process

### Phase 1: Install and Test
1. Ensure the unified OCR service is available
2. Run the test script: `python scripts/test_unified_ocr_service.py`
3. Verify all engines are available

### Phase 2: Update Bank Statement Processing
1. Replace `EnhancedPDFTextExtractor` usage with `UnifiedOCRService.extract_text()`
2. Update error handling to use `ExtractionResult`
3. Test with existing bank statement files

### Phase 3: Update Expense Processing
1. Replace direct `_run_ocr` calls with `UnifiedOCRService.extract_structured_data()`
2. Update data access patterns to use `result.structured_data`
3. Test with existing expense receipts

### Phase 4: Update Invoice Processing
1. Implement invoice processing using `DocumentType.INVOICE`
2. Test with invoice files
3. Update any custom invoice OCR code

### Phase 5: Configuration Consolidation
1. Create unified `OCRConfig` instances
2. Remove duplicate configuration code
3. Update environment variable handling

### Phase 6: Monitoring and Analytics
1. Update logging to use unified service metrics
2. Implement monitoring for `ExtractionResult` data
3. Set up alerts for processing failures

## Testing Your Migration

### Unit Tests
```python
import pytest
from services.unified_ocr_service import UnifiedOCRService, DocumentType

@pytest.mark.asyncio
async def test_expense_extraction():
    service = UnifiedOCRService()
    result = await service.extract_structured_data(
        "test_receipt.jpg", 
        DocumentType.EXPENSE_RECEIPT
    )
    assert result.success
    assert result.structured_data is not None

def test_bank_statement_extraction():
    service = UnifiedOCRService()
    result = service.extract_text(
        "test_statement.pdf", 
        DocumentType.BANK_STATEMENT
    )
    assert result.success
    assert result.text is not None
```

### Integration Tests
```python
def test_service_status():
    service = UnifiedOCRService()
    status = service.get_service_status()
    assert status['status'] == 'active'
    assert 'engines' in status
```

## Performance Considerations

### Before Migration
- Multiple service initializations
- Inconsistent caching
- Duplicate dependency checks

### After Migration
- Single service initialization
- Shared component caching
- Unified dependency management
- Better resource utilization

## Rollback Plan

If you need to rollback:

1. **Keep old code** during migration period
2. **Use feature flags** to switch between old and new implementations
3. **Monitor metrics** to compare performance
4. **Gradual rollout** by document type

```python
# Feature flag example
USE_UNIFIED_OCR = os.getenv("USE_UNIFIED_OCR", "false").lower() == "true"

if USE_UNIFIED_OCR:
    # New unified service
    service = UnifiedOCRService()
    result = service.extract_text(file_path, DocumentType.BANK_STATEMENT)
else:
    # Old implementation
    extractor = EnhancedPDFTextExtractor(ai_config)
    result = extractor.extract_text(file_path)
```

## Support and Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Configuration Issues**: Check `OCRConfig` settings
3. **Performance Issues**: Adjust timeout and retry settings
4. **Quality Issues**: Tune confidence thresholds

### Getting Help

1. Check the service status: `service.get_service_status()`
2. Review logs for detailed error messages
3. Test with the provided example scripts
4. Use the troubleshooting guide: `api/docs/LANGCHAIN_TROUBLESHOOTING.md`

## Next Steps

After migration:

1. **Monitor Performance** - Track processing times and success rates
2. **Optimize Configuration** - Tune settings based on your document types
3. **Implement Analytics** - Use `ExtractionResult` data for insights
4. **Plan Enhancements** - Consider additional document types or methods

The Unified OCR Service provides a solid foundation for future OCR enhancements while maintaining compatibility with existing functionality.