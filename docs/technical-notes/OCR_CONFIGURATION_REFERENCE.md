# OCR Configuration Reference

This document provides a comprehensive reference for all OCR fallback configuration options, behavior changes, and examples.

## Configuration Overview

The OCR fallback system introduces new configuration options while maintaining backward compatibility with existing bank statement processing. All OCR features are optional and can be disabled without affecting existing functionality.

## Environment Variables

### Core OCR Settings

#### `BANK_OCR_ENABLED`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Master switch to enable/disable OCR fallback functionality
- **Example**: `BANK_OCR_ENABLED=true`
- **Notes**: When disabled, system falls back to existing PDF-only processing

#### `BANK_OCR_TIMEOUT`
- **Type**: Integer (seconds)
- **Default**: `300` (5 minutes)
- **Range**: `30-3600` (30 seconds to 1 hour)
- **Description**: Maximum time allowed for OCR processing per document
- **Example**: `BANK_OCR_TIMEOUT=600`
- **Notes**: Longer timeouts allow processing of complex documents but may impact user experience

#### `BANK_OCR_MIN_TEXT_THRESHOLD`
- **Type**: Integer (characters)
- **Default**: `50`
- **Range**: `10-500`
- **Description**: Minimum characters required from PDF extraction to skip OCR
- **Example**: `BANK_OCR_MIN_TEXT_THRESHOLD=100`
- **Notes**: Higher values make OCR fallback more likely; lower values prefer PDF extraction

#### `BANK_OCR_MIN_WORD_THRESHOLD`
- **Type**: Integer (words)
- **Default**: `10`
- **Range**: `3-100`
- **Description**: Minimum words required from PDF extraction to skip OCR
- **Example**: `BANK_OCR_MIN_WORD_THRESHOLD=15`
- **Notes**: Used in conjunction with character threshold for text quality assessment

### Tesseract Configuration

#### `TESSERACT_CMD`
- **Type**: String (file path)
- **Default**: `/usr/bin/tesseract`
- **Description**: Full path to Tesseract OCR executable
- **Example**: `TESSERACT_CMD=/usr/local/bin/tesseract`
- **Platform-specific defaults**:
  - Linux: `/usr/bin/tesseract`
  - macOS: `/usr/local/bin/tesseract` or `/opt/homebrew/bin/tesseract`
  - Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`

#### `TESSERACT_CONFIG`
- **Type**: String (command-line options)
- **Default**: `--oem 3 --psm 6`
- **Description**: Tesseract command-line options for OCR processing
- **Example**: `TESSERACT_CONFIG="--oem 3 --psm 1 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,-$"`

**Common Tesseract Options**:
- `--oem 3`: Use LSTM OCR Engine Mode (recommended)
- `--oem 1`: Use Legacy OCR Engine Mode
- `--psm 6`: Uniform block of text (good for bank statements)
- `--psm 1`: Automatic page segmentation with OSD
- `--psm 4`: Single column of text
- `-c tessedit_char_whitelist=...`: Limit recognized characters

### UnstructuredLoader Configuration

#### `UNSTRUCTURED_STRATEGY`
- **Type**: String (enum)
- **Default**: `hi_res`
- **Options**: `hi_res`, `fast`, `ocr_only`, `auto`
- **Description**: Processing strategy for UnstructuredLoader
- **Example**: `UNSTRUCTURED_STRATEGY=fast`

**Strategy Details**:
- `hi_res`: High-resolution processing for maximum accuracy (slower)
- `fast`: Fast processing with reduced accuracy (faster)
- `ocr_only`: Force OCR processing without PDF text extraction
- `auto`: Automatically select strategy based on document characteristics

#### `UNSTRUCTURED_MODE`
- **Type**: String (enum)
- **Default**: `single`
- **Options**: `single`, `elements`, `paged`
- **Description**: Output mode for processed documents
- **Example**: `UNSTRUCTURED_MODE=elements`

#### `UNSTRUCTURED_USE_API`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Use Unstructured.io cloud API instead of local processing
- **Example**: `UNSTRUCTURED_USE_API=true`
- **Notes**: Requires `UNSTRUCTURED_API_KEY` when enabled

#### `UNSTRUCTURED_API_KEY`
- **Type**: String (API key)
- **Default**: None
- **Description**: API key for Unstructured.io cloud service
- **Example**: `UNSTRUCTURED_API_KEY=your-api-key-here`
- **Notes**: Required when `UNSTRUCTURED_USE_API=true`

#### `UNSTRUCTURED_API_URL`
- **Type**: String (URL)
- **Default**: `https://api.unstructured.io`
- **Description**: Base URL for Unstructured.io API
- **Example**: `UNSTRUCTURED_API_URL=https://api.unstructured.io`

### Performance Settings

#### `OCR_MAX_CONCURRENT_JOBS`
- **Type**: Integer
- **Default**: `2`
- **Range**: `1-10`
- **Description**: Maximum number of concurrent OCR operations
- **Example**: `OCR_MAX_CONCURRENT_JOBS=4`
- **Notes**: Higher values increase throughput but consume more system resources

#### `OCR_TEMP_DIR`
- **Type**: String (directory path)
- **Default**: `/tmp/ocr_processing`
- **Description**: Directory for temporary OCR processing files
- **Example**: `OCR_TEMP_DIR=/var/tmp/ocr_processing`
- **Notes**: Ensure directory has sufficient space and proper permissions

#### `OCR_CLEANUP_INTERVAL`
- **Type**: Integer (seconds)
- **Default**: `3600` (1 hour)
- **Description**: Interval for cleaning up temporary OCR files
- **Example**: `OCR_CLEANUP_INTERVAL=1800`

### Logging and Monitoring

#### `OCR_LOG_LEVEL`
- **Type**: String (enum)
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- **Description**: Logging level for OCR operations
- **Example**: `OCR_LOG_LEVEL=DEBUG`

#### `OCR_METRICS_ENABLED`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Enable collection of OCR performance metrics
- **Example**: `OCR_METRICS_ENABLED=false`

## Configuration Examples

### Development Environment

```bash
# Development OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=120
BANK_OCR_MIN_TEXT_THRESHOLD=30
BANK_OCR_MIN_WORD_THRESHOLD=5

# Fast processing for development
UNSTRUCTURED_STRATEGY=fast
OCR_MAX_CONCURRENT_JOBS=1

# Debug logging
OCR_LOG_LEVEL=DEBUG

# Local Tesseract
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG="--oem 3 --psm 6"
```

### Production Environment

```bash
# Production OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
BANK_OCR_MIN_TEXT_THRESHOLD=50
BANK_OCR_MIN_WORD_THRESHOLD=10

# High-quality processing
UNSTRUCTURED_STRATEGY=hi_res
OCR_MAX_CONCURRENT_JOBS=4

# Production logging
OCR_LOG_LEVEL=WARNING

# Optimized Tesseract settings
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0"

# Performance optimization
OCR_TEMP_DIR=/var/tmp/ocr_processing
OCR_CLEANUP_INTERVAL=1800
```

### High-Volume Environment

```bash
# High-volume OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=180
BANK_OCR_MIN_TEXT_THRESHOLD=75
BANK_OCR_MIN_WORD_THRESHOLD=15

# Fast processing for throughput
UNSTRUCTURED_STRATEGY=fast
OCR_MAX_CONCURRENT_JOBS=8

# Minimal logging
OCR_LOG_LEVEL=ERROR

# Optimized for speed
TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0 -c tessedit_pageseg_mode=6"

# SSD storage for temp files
OCR_TEMP_DIR=/mnt/ssd/ocr_temp
OCR_CLEANUP_INTERVAL=900
```

### Cloud API Configuration

```bash
# Cloud-based OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300

# Use Unstructured.io API
UNSTRUCTURED_USE_API=true
UNSTRUCTURED_API_KEY=your-api-key-here
UNSTRUCTURED_API_URL=https://api.unstructured.io

# Reduced local processing
OCR_MAX_CONCURRENT_JOBS=2
TESSERACT_CMD=/usr/bin/tesseract  # Still needed as fallback
```

## Behavior Changes

### Processing Flow Changes

#### Before OCR Implementation
```
PDF Upload → PDF Text Extraction → LLM Processing → Results
                ↓ (if fails)
            Error Response
```

#### After OCR Implementation
```
PDF Upload → PDF Text Extraction → Text Quality Check
                ↓ (sufficient)         ↓ (insufficient)
            LLM Processing         OCR Processing
                ↓                      ↓
            Results ←─────────────── LLM Processing
                                       ↓
                                   Results
```

### API Response Changes

#### New Fields in Statement Objects

```json
{
  "id": 123,
  "original_filename": "statement.pdf",
  "status": "completed",
  // New OCR-related fields
  "processing_metadata": {
    "extraction_method": "ocr",           // "pdf_loader" or "ocr"
    "processing_time": 23.5,              // Total processing time
    "text_length": 2847,                  // Characters extracted
    "ocr_confidence": 0.92,               // OCR confidence (0.0-1.0)
    "fallback_reason": "insufficient_pdf_text",  // Why OCR was used
    "pdf_text_length": 12,                // PDF extraction result
    "ocr_strategy": "hi_res"              // OCR strategy used
  }
}
```

#### New Status Values

- `processing`: Document is being processed (may include OCR)
- `ocr_processing`: Document is specifically undergoing OCR processing
- `ocr_timeout`: OCR processing timed out
- `ocr_failed`: OCR processing failed

### Error Handling Changes

#### New Error Codes

```json
{
  "detail": "OCR processing timed out after 300 seconds",
  "error_code": "OCR_TIMEOUT",
  "context": {
    "statement_id": 123,
    "processing_time": 300.0,
    "extraction_method": "ocr",
    "fallback_triggered": true
  }
}
```

#### Enhanced Error Context

All OCR-related errors now include:
- Processing method attempted
- Time spent processing
- Fallback status
- Suggested resolutions

## Configuration Validation

### Startup Validation

The system validates OCR configuration on startup:

```python
# Configuration validation results
{
  "ocr_config_valid": true,
  "validation_results": {
    "tesseract_available": true,
    "tesseract_version": "4.1.1",
    "python_packages": {
      "pytesseract": "0.3.10",
      "unstructured": "0.10.30",

    },
    "directories": {
      "temp_dir_writable": true,
      "temp_dir_space": "15.2 GB"
    },
    "api_connectivity": {
      "unstructured_api": "not_configured"
    }
  },
  "warnings": [
    "OCR_MAX_CONCURRENT_JOBS set to 8, may consume significant memory"
  ],
  "errors": []
}
```

### Runtime Validation

Configuration is also validated at runtime:

```python
# Runtime validation endpoint
GET /api/v1/ocr/validate-config

{
  "config_valid": true,
  "current_settings": {
    "ocr_enabled": true,
    "timeout": 300,
    "strategy": "hi_res",
    "concurrent_jobs": 2
  },
  "system_status": {
    "tesseract_responsive": true,
    "temp_dir_available": true,
    "memory_available": "4.2 GB",
    "cpu_load": 0.45
  }
}
```

## Performance Tuning

### Memory Optimization

```bash
# For systems with limited memory
OCR_MAX_CONCURRENT_JOBS=1
UNSTRUCTURED_STRATEGY=fast
BANK_OCR_TIMEOUT=120

# Tesseract memory optimization
TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0"
```

### CPU Optimization

```bash
# For CPU-intensive environments
OCR_MAX_CONCURRENT_JOBS=4  # Match CPU cores
UNSTRUCTURED_STRATEGY=hi_res  # Utilize available CPU

# Tesseract CPU optimization
TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_parallelize=1"
```

### Storage Optimization

```bash
# Use SSD for temporary files
OCR_TEMP_DIR=/mnt/ssd/ocr_temp

# Aggressive cleanup
OCR_CLEANUP_INTERVAL=600  # 10 minutes

# Limit temp file size
OCR_MAX_TEMP_SIZE=1073741824  # 1GB
```

## Monitoring Configuration

### Metrics Collection

```bash
# Enable comprehensive metrics
OCR_METRICS_ENABLED=true
OCR_METRICS_INTERVAL=60  # seconds
OCR_METRICS_RETENTION=86400  # 24 hours

# Detailed logging
OCR_LOG_LEVEL=INFO
OCR_LOG_PERFORMANCE=true
OCR_LOG_ERRORS=true
```

### Health Check Configuration

```bash
# Health check settings
OCR_HEALTH_CHECK_ENABLED=true
OCR_HEALTH_CHECK_INTERVAL=300  # 5 minutes
OCR_HEALTH_CHECK_TIMEOUT=30    # 30 seconds
```

## Security Configuration

### File Security

```bash
# Secure temporary directory
OCR_TEMP_DIR=/var/secure/ocr_temp
OCR_TEMP_PERMISSIONS=700

# File cleanup security
OCR_SECURE_DELETE=true
OCR_CLEANUP_VERIFICATION=true
```

### API Security

```bash
# Unstructured API security
UNSTRUCTURED_API_KEY=your-secure-key
UNSTRUCTURED_API_TIMEOUT=60
UNSTRUCTURED_API_RETRY_LIMIT=3

# Network security
OCR_ALLOWED_HOSTS=api.unstructured.io
OCR_USE_TLS=true
```

## Troubleshooting Configuration

### Debug Configuration

```bash
# Maximum debugging
OCR_LOG_LEVEL=DEBUG
OCR_DEBUG_SAVE_TEMP_FILES=true
OCR_DEBUG_TIMING=true
OCR_DEBUG_MEMORY=true

# Extended timeouts for debugging
BANK_OCR_TIMEOUT=1800  # 30 minutes
OCR_HEALTH_CHECK_TIMEOUT=120
```

### Test Configuration

```bash
# Configuration for testing
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=60
OCR_MAX_CONCURRENT_JOBS=1
UNSTRUCTURED_STRATEGY=fast

# Test-specific settings
OCR_TEST_MODE=true
OCR_MOCK_FAILURES=false
OCR_DETERMINISTIC_RESULTS=true
```

## Migration Configuration

### Gradual Rollout

```bash
# Phase 1: OCR available but not default
BANK_OCR_ENABLED=true
BANK_OCR_MIN_TEXT_THRESHOLD=10  # Very low threshold
BANK_OCR_TIMEOUT=60             # Short timeout

# Phase 2: Increase OCR usage
BANK_OCR_MIN_TEXT_THRESHOLD=50  # Normal threshold
BANK_OCR_TIMEOUT=300            # Normal timeout

# Phase 3: Full deployment
OCR_MAX_CONCURRENT_JOBS=4       # Full capacity
UNSTRUCTURED_STRATEGY=hi_res    # Best quality
```

### A/B Testing Configuration

```bash
# A/B testing setup
OCR_AB_TEST_ENABLED=true
OCR_AB_TEST_PERCENTAGE=50       # 50% of users get OCR
OCR_AB_TEST_SEED=12345          # Consistent user assignment
```

## Best Practices

### Configuration Management

1. **Environment-Specific Configs**: Use different configurations for dev/staging/production
2. **Version Control**: Store configuration templates in version control
3. **Validation**: Always validate configuration before deployment
4. **Monitoring**: Monitor configuration effectiveness with metrics
5. **Documentation**: Document any custom configuration changes

### Performance Optimization

1. **Resource Monitoring**: Monitor CPU, memory, and disk usage
2. **Timeout Tuning**: Adjust timeouts based on document complexity
3. **Concurrent Jobs**: Balance throughput with resource consumption
4. **Strategy Selection**: Choose appropriate OCR strategy for use case

### Security Considerations

1. **API Keys**: Store API keys securely, never in code
2. **File Permissions**: Secure temporary directories and files
3. **Network Security**: Use TLS for API communications
4. **Audit Logging**: Log all configuration changes

This configuration reference provides comprehensive guidance for optimizing OCR fallback functionality based on specific requirements and constraints.