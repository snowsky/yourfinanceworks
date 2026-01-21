# OCR Unification Proposal

## Current State Analysis

### Bank Statements OCR
- **Primary Tool**: `unstructured` library
- **Fallback**: Tesseract OCR via unstructured
- **Processing**: Synchronous with timeout handling
- **Focus**: Text extraction from PDFs with table structure preservation
- **Error Handling**: Comprehensive OCR-specific exceptions

### Expenses OCR  
- **Primary Tool**: LiteLLM with vision models (GPT-4V, Claude Vision, etc.)
- **Fallback**: Ollama OCR library
- **Processing**: Async via Kafka queues
- **Focus**: Structured data extraction (JSON) from receipts/invoices
- **Error Handling**: General AI provider error handling

## Unified OCR Architecture Proposal

### 1. Create Unified OCR Service

```python
# api/services/unified_ocr_service.py
class UnifiedOCRService:
    """
    Unified OCR service supporting multiple extraction strategies:
    - Text extraction (bank statements, documents)
    - Structured data extraction (expenses, invoices)
    """
    
    def __init__(self, ai_config: Dict[str, Any]):
        self.ai_config = ai_config
        self.text_extractor = TextExtractionEngine(ai_config)
        self.structured_extractor = StructuredDataEngine(ai_config)
    
    def extract_text(self, file_path: str, **kwargs) -> TextExtractionResult:
        """Extract plain text from documents"""
        return self.text_extractor.extract(file_path, **kwargs)
    
    def extract_structured_data(self, file_path: str, schema: Dict, **kwargs) -> StructuredExtractionResult:
        """Extract structured data using AI vision models"""
        return self.structured_extractor.extract(file_path, schema, **kwargs)
```

### 2. Extraction Engines

#### Text Extraction Engine
- Uses `unstructured` library as primary method
- Falls back to Tesseract OCR when needed
- Optimized for bank statements and document text extraction

#### Structured Data Engine  
- Uses AI vision models (GPT-4V, Claude Vision, etc.) as primary method
- Falls back to text extraction + AI parsing
- Optimized for receipts, invoices, and structured data

### 3. Benefits of Unification

#### Consistency
- Single configuration system for all OCR operations
- Unified error handling and retry logic
- Consistent logging and monitoring

#### Efficiency
- Shared dependency management
- Reduced code duplication
- Single point of maintenance

#### Flexibility
- Easy to add new extraction methods
- Configurable fallback strategies
- Support for different document types

### 4. Migration Strategy

#### Phase 1: Create Unified Service
1. Create `UnifiedOCRService` class
2. Implement `TextExtractionEngine` (migrate bank statement logic)
3. Implement `StructuredDataEngine` (migrate expense logic)

#### Phase 2: Update Bank Statements
1. Replace `BankStatementOCRProcessor` with `UnifiedOCRService.extract_text()`
2. Update `EnhancedPDFTextExtractor` to use unified service
3. Maintain existing API compatibility

#### Phase 3: Update Expenses
1. Replace expense OCR logic with `UnifiedOCRService.extract_structured_data()`
2. Update `queue_or_process_attachment` to use unified service
3. Maintain Kafka integration

#### Phase 4: Optimization
1. Consolidate configuration management
2. Unify monitoring and analytics
3. Optimize shared resources

### 5. Implementation Details

#### Shared Configuration
```python
@dataclass
class UnifiedOCRConfig:
    # Text extraction settings
    unstructured_enabled: bool = True
    unstructured_api_key: Optional[str] = None
    tesseract_enabled: bool = True
    
    # Structured extraction settings  
    ai_vision_enabled: bool = True
    ai_providers: List[str] = field(default_factory=lambda: ["openai", "anthropic"])
    
    # Common settings
    timeout_seconds: int = 300
    retry_attempts: int = 3
    fallback_enabled: bool = True
```

#### Error Handling
```python
class OCRExtractionError(Exception):
    """Base class for all OCR extraction errors"""
    pass

class TextExtractionError(OCRExtractionError):
    """Text extraction specific errors"""
    pass

class StructuredExtractionError(OCRExtractionError):
    """Structured data extraction specific errors"""
    pass
```

### 6. Recommended Approach

**For Bank Statements**: Keep using `unstructured` as it's optimized for document text extraction and table preservation.

**For Expenses**: Keep using AI vision models as they're better at understanding receipt layouts and extracting structured data.

**Unified Layer**: Create a service layer that routes requests to the appropriate engine based on document type and extraction requirements.

### 7. Code Reuse Opportunities

#### Shared Components
- File validation and path handling
- Timeout and retry logic  
- Error handling and logging
- Configuration management
- Usage tracking and analytics

#### Document Type Detection
```python
def detect_document_type(file_path: str) -> DocumentType:
    """Automatically detect document type to choose optimal extraction method"""
    # Analyze file content, name patterns, etc.
    pass
```

This unified approach would provide better maintainability while preserving the strengths of each current implementation.