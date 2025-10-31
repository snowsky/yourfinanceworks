# Bank Statement OCR Fallback API Documentation

This document provides comprehensive API documentation for the bank statement processing system with OCR fallback functionality.

## Overview

The Bank Statement OCR API provides endpoints for uploading, processing, and managing bank statements with automatic OCR fallback when PDF text extraction fails. The system intelligently detects when documents require OCR processing and seamlessly falls back to optical character recognition for scanned or image-based PDFs.

## Base URL

```
https://your-api-domain.com/api/v1
```

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## API Endpoints

### Upload Bank Statements

Upload bank statement files for processing with automatic OCR fallback.

**Endpoint:** `POST /statements/upload`

**Description:** Upload up to 12 PDF or CSV bank statement files. The system automatically detects document type and applies appropriate processing method (PDF text extraction or OCR fallback).

**Request:**
```http
POST /statements/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>

files: [file1.pdf, file2.pdf, ...]
```

**Parameters:**
- `files` (required): Array of files (max 12)
  - Supported formats: PDF, CSV
  - Max file size: 10MB per file
  - Supported content types: `application/pdf`, `text/csv`, `application/vnd.ms-excel`

**Response:**
```json
{
  "message": "Successfully uploaded 2 statements",
  "statements": [
    {
      "id": 123,
      "original_filename": "statement_jan_2024.pdf",
      "status": "processing",
      "created_at": "2024-01-15T10:30:00Z",
      "tenant_id": 1,
      "processing_method": "queued",
      "ocr_enabled": true
    },
    {
      "id": 124,
      "original_filename": "statement_feb_2024.pdf", 
      "status": "processing",
      "created_at": "2024-01-15T10:30:00Z",
      "tenant_id": 1,
      "processing_method": "queued",
      "ocr_enabled": true
    }
  ]
}
```

**OCR-Specific Behavior:**
- Documents are initially processed using PDF text extraction
- If text extraction yields insufficient content (< 50 characters or < 10 words), OCR fallback is automatically triggered
- OCR processing may take longer (up to 5 minutes by default)
- Processing status can be monitored via the list statements endpoint

**Error Responses:**
```json
// File validation error
{
  "detail": "File type not supported. Only PDF and CSV files are allowed.",
  "error_code": "INVALID_FILE_TYPE"
}

// OCR unavailable
{
  "detail": "OCR processing is currently unavailable. Please try again later.",
  "error_code": "OCR_UNAVAILABLE"
}

// Processing timeout
{
  "detail": "Document processing timed out. Please try with a smaller or clearer document.",
  "error_code": "OCR_TIMEOUT"
}
```

### List Bank Statements

Retrieve a list of uploaded bank statements with processing status.

**Endpoint:** `GET /statements`

**Request:**
```http
GET /statements?skip=0&limit=50
Authorization: Bearer <token>
```

**Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 50, max: 100)

**Response:**
```json
{
  "statements": [
    {
      "id": 123,
      "original_filename": "statement_jan_2024.pdf",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z",
      "tenant_id": 1,
      "notes": "January bank statement",
      "label": "business-checking",
      "transaction_count": 45,
      "processing_metadata": {
        "extraction_method": "ocr",
        "processing_time": 23.5,
        "text_length": 2847,
        "ocr_confidence": 0.92
      }
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 50
}
```

**Processing Status Values:**
- `processing`: Document is being processed (PDF extraction or OCR)
- `completed`: Processing completed successfully
- `failed`: Processing failed (see error details)
- `timeout`: Processing timed out

**Processing Metadata Fields:**
- `extraction_method`: `"pdf_loader"` or `"ocr"`
- `processing_time`: Time in seconds
- `text_length`: Number of characters extracted
- `ocr_confidence`: OCR confidence score (0.0-1.0, only for OCR method)

### Get Bank Statement Details

Retrieve detailed information about a specific bank statement.

**Endpoint:** `GET /statements/{statement_id}`

**Request:**
```http
GET /statements/123
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 123,
  "original_filename": "statement_jan_2024.pdf",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  "tenant_id": 1,
  "notes": "January bank statement",
  "label": "business-checking",
  "processing_metadata": {
    "extraction_method": "ocr",
    "processing_time": 23.5,
    "text_length": 2847,
    "ocr_confidence": 0.92,
    "fallback_reason": "insufficient_pdf_text",
    "pdf_text_length": 12,
    "ocr_strategy": "hi_res"
  },
  "transactions": [
    {
      "id": 456,
      "date": "2024-01-15",
      "description": "DEPOSIT - PAYROLL",
      "amount": 2500.00,
      "balance": 5847.32,
      "type": "credit"
    }
  ]
}
```

**OCR-Specific Metadata:**
- `fallback_reason`: Why OCR was triggered (`"insufficient_pdf_text"`, `"pdf_extraction_failed"`)
- `pdf_text_length`: Characters extracted from PDF before OCR fallback
- `ocr_strategy`: OCR processing strategy used (`"hi_res"`, `"fast"`)

### Reprocess Bank Statement

Requeue a bank statement for processing, useful when initial processing failed or OCR improvements are available.

**Endpoint:** `POST /statements/{statement_id}/reprocess`

**Request:**
```http
POST /statements/123/reprocess
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Statement requeued for processing",
  "statement_id": 123,
  "status": "processing",
  "processing_method": "ocr_fallback_enabled"
}
```

**OCR Behavior:**
- Reprocessing will attempt PDF extraction first, then OCR if needed
- Previous processing results are preserved until new processing completes
- OCR configuration changes (timeouts, strategies) will be applied

### Update Statement Metadata

Update notes and labels for a bank statement.

**Endpoint:** `PUT /statements/{statement_id}/metadata`

**Request:**
```http
PUT /statements/123/metadata
Content-Type: application/json
Authorization: Bearer <token>

{
  "notes": "Updated notes for January statement",
  "label": "business-checking-updated"
}
```

**Response:**
```json
{
  "message": "Statement metadata updated successfully",
  "statement": {
    "id": 123,
    "notes": "Updated notes for January statement",
    "label": "business-checking-updated",
    "updated_at": "2024-01-15T11:00:00Z"
  }
}
```

### Download Statement File

Download the original uploaded bank statement file.

**Endpoint:** `GET /statements/{statement_id}/download`

**Request:**
```http
GET /statements/123/download?inline=false
Authorization: Bearer <token>
```

**Parameters:**
- `inline` (optional): If `true`, display in browser; if `false`, download as attachment (default: false)

**Response:**
- Content-Type: `application/pdf` or `text/csv`
- Content-Disposition: `attachment; filename="statement_jan_2024.pdf"` or `inline`

### Get OCR Configuration Status

Check the current OCR configuration and availability.

**Endpoint:** `GET /statements/ocr/status`

**Request:**
```http
GET /statements/ocr/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "ocr_available": true,
  "ocr_enabled": true,
  "configuration": {
    "timeout_seconds": 300,
    "min_text_threshold": 50,
    "min_word_threshold": 10,
    "strategy": "hi_res",
    "max_concurrent_jobs": 2,
    "use_api": false
  },
  "dependencies": {
    "tesseract_available": true,
    "tesseract_version": "4.1.1",
    "unstructured_available": true,
    "python_packages_ok": true
  },
  "statistics": {
    "total_processed": 1247,
    "pdf_extraction_used": 892,
    "ocr_fallback_used": 355,
    "success_rate": 0.987,
    "average_processing_time": {
      "pdf_extraction": 1.2,
      "ocr_fallback": 18.7
    }
  }
}
```

## Configuration Options

### Environment Variables

The following environment variables control OCR fallback behavior:

```bash
# Core OCR Settings
BANK_OCR_ENABLED=true                    # Enable/disable OCR fallback
BANK_OCR_TIMEOUT=300                     # OCR processing timeout (seconds)
BANK_OCR_MIN_TEXT_THRESHOLD=50           # Minimum characters to skip OCR
BANK_OCR_MIN_WORD_THRESHOLD=10           # Minimum words to skip OCR

# Tesseract Configuration
TESSERACT_CMD=/usr/bin/tesseract         # Path to Tesseract binary
TESSERACT_CONFIG="--oem 3 --psm 6"       # Tesseract OCR options

# UnstructuredLoader Settings
UNSTRUCTURED_STRATEGY=hi_res             # Processing strategy (hi_res, fast)
UNSTRUCTURED_MODE=single                 # Processing mode
UNSTRUCTURED_USE_API=false               # Use Unstructured API vs local

# Performance Settings
OCR_MAX_CONCURRENT_JOBS=2                # Max parallel OCR operations
OCR_TEMP_DIR=/tmp/ocr_processing         # Temporary file directory
OCR_CLEANUP_INTERVAL=3600                # Cleanup interval (seconds)

# API Settings (if using Unstructured API)
UNSTRUCTURED_API_KEY=your-api-key        # API key for Unstructured.io
UNSTRUCTURED_API_URL=https://api.unstructured.io  # API endpoint
```

### Configuration Validation

The system validates configuration on startup and provides detailed error messages:

```json
{
  "error": "OCR configuration invalid",
  "details": {
    "tesseract_available": false,
    "error_message": "Tesseract not found at /usr/bin/tesseract",
    "suggestions": [
      "Install Tesseract: sudo apt-get install tesseract-ocr",
      "Set correct path: export TESSERACT_CMD=/usr/local/bin/tesseract"
    ]
  }
}
```

## Error Codes and Handling

### OCR-Specific Error Codes

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| `OCR_UNAVAILABLE` | 503 | OCR system is not available | Check OCR dependencies, retry later |
| `OCR_TIMEOUT` | 408 | OCR processing timed out | Increase timeout or use faster strategy |
| `OCR_PROCESSING_ERROR` | 500 | OCR processing failed | Check document quality, retry |
| `TESSERACT_NOT_FOUND` | 503 | Tesseract OCR engine not installed | Install Tesseract system dependency |
| `INSUFFICIENT_TEXT_QUALITY` | 422 | Neither PDF nor OCR yielded usable text | Check document quality and format |
| `OCR_DEPENDENCY_MISSING` | 503 | Required Python packages missing | Install missing dependencies |
| `OCR_CONFIG_INVALID` | 500 | OCR configuration is invalid | Check environment variables |

### Error Response Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "context": {
    "statement_id": 123,
    "extraction_method": "ocr",
    "processing_time": 45.2,
    "additional_info": "Specific details about the error"
  },
  "suggestions": [
    "Try uploading a clearer scan of the document",
    "Ensure the document contains readable text"
  ]
}
```

### Retry Logic

The system implements intelligent retry logic for OCR operations:

1. **Automatic Retries**: Failed OCR operations are automatically retried up to 3 times
2. **Exponential Backoff**: Retry delays increase exponentially (1s, 2s, 4s)
3. **Fallback Strategies**: If high-resolution OCR fails, system tries fast strategy
4. **Manual Retry**: Users can manually trigger reprocessing via API

## OCR Fallback Scenarios

### Scenario 1: Successful PDF Extraction

```json
{
  "processing_flow": [
    {
      "step": "pdf_extraction",
      "status": "success",
      "text_length": 2847,
      "processing_time": 1.2
    }
  ],
  "final_method": "pdf_loader",
  "total_time": 1.2
}
```

### Scenario 2: OCR Fallback Triggered

```json
{
  "processing_flow": [
    {
      "step": "pdf_extraction", 
      "status": "insufficient_text",
      "text_length": 12,
      "processing_time": 0.8
    },
    {
      "step": "ocr_fallback",
      "status": "success", 
      "text_length": 2847,
      "processing_time": 23.5,
      "confidence": 0.92
    }
  ],
  "final_method": "ocr",
  "total_time": 24.3
}
```

### Scenario 3: Complete Processing Failure

```json
{
  "processing_flow": [
    {
      "step": "pdf_extraction",
      "status": "failed",
      "error": "PDF parsing error",
      "processing_time": 0.5
    },
    {
      "step": "ocr_fallback",
      "status": "failed",
      "error": "OCR timeout after 300 seconds",
      "processing_time": 300.0
    }
  ],
  "final_method": "none",
  "total_time": 300.5,
  "error_code": "OCR_TIMEOUT"
}
```

## Performance Considerations

### Processing Times

Typical processing times vary by document type and method:

| Document Type | PDF Extraction | OCR Fallback | Total Time |
|---------------|----------------|--------------|------------|
| Digital PDF (text-based) | 0.5-2s | N/A | 0.5-2s |
| Scanned PDF (clear) | 0.5s + 15-30s | 15-30s | 15-30s |
| Scanned PDF (poor quality) | 0.5s + 30-60s | 30-60s | 30-60s |
| Large documents (>10 pages) | 1-3s + 60-180s | 60-180s | 60-180s |

### Optimization Strategies

1. **Strategy Selection**:
   - Use `hi_res` for accuracy (slower)
   - Use `fast` for speed (less accurate)

2. **Concurrent Processing**:
   - Adjust `OCR_MAX_CONCURRENT_JOBS` based on system resources
   - Monitor memory usage during OCR operations

3. **Timeout Configuration**:
   - Set appropriate timeouts based on document complexity
   - Consider user experience vs processing completeness

## Monitoring and Analytics

### Processing Metrics

Monitor these key metrics for OCR performance:

```json
{
  "metrics": {
    "total_documents_processed": 1247,
    "pdf_extraction_success_rate": 0.715,
    "ocr_fallback_usage_rate": 0.285,
    "overall_success_rate": 0.987,
    "average_processing_times": {
      "pdf_only": 1.2,
      "with_ocr_fallback": 18.7
    },
    "error_rates": {
      "ocr_timeout": 0.008,
      "ocr_processing_error": 0.003,
      "insufficient_text_quality": 0.002
    }
  }
}
```

### Health Check Endpoint

Monitor OCR system health:

**Endpoint:** `GET /health/ocr`

**Response:**
```json
{
  "status": "healthy",
  "ocr_available": true,
  "dependencies": {
    "tesseract": "ok",
    "python_packages": "ok",
    "disk_space": "ok",
    "memory": "ok"
  },
  "performance": {
    "avg_processing_time": 18.7,
    "success_rate_24h": 0.987,
    "queue_length": 3
  },
  "timestamp": "2024-01-15T12:00:00Z"
}
```

## Best Practices

### For API Consumers

1. **Handle Async Processing**: Bank statement processing is asynchronous. Poll the status endpoint or implement webhooks.

2. **Implement Retry Logic**: Handle temporary OCR unavailability with exponential backoff.

3. **Monitor Processing Times**: OCR operations take longer than PDF extraction. Set appropriate timeouts.

4. **Validate File Quality**: Higher quality scans produce better OCR results.

### For System Administrators

1. **Resource Planning**: OCR operations are CPU and memory intensive. Plan system resources accordingly.

2. **Monitoring**: Monitor OCR success rates, processing times, and error patterns.

3. **Configuration Tuning**: Adjust OCR settings based on document types and performance requirements.

4. **Dependency Management**: Keep Tesseract and Python packages updated for best performance.

## Migration Guide

### Upgrading from Non-OCR Version

When upgrading from a version without OCR support:

1. **Install Dependencies**: Install Tesseract and required Python packages
2. **Update Configuration**: Add OCR environment variables
3. **Test Functionality**: Verify OCR works with sample documents
4. **Monitor Performance**: Watch for performance impact during rollout

### Configuration Changes

No API breaking changes are introduced. OCR functionality is automatically enabled when dependencies are available and configuration is valid.

## Support and Troubleshooting

### Common Issues

1. **OCR Not Working**: Check Tesseract installation and configuration
2. **Slow Processing**: Adjust OCR strategy or increase system resources  
3. **Poor Accuracy**: Improve document quality or adjust OCR parameters
4. **Timeouts**: Increase timeout values or optimize system performance

### Debug Information

Enable debug logging for detailed OCR troubleshooting:

```bash
export OCR_LOG_LEVEL=DEBUG
```

This provides detailed information about:
- PDF extraction attempts and results
- OCR fallback triggers and processing
- Performance metrics and timing
- Error details and stack traces

### Getting Help

For additional support:
1. Check system logs for detailed error messages
2. Use the OCR status endpoint to verify configuration
3. Test with sample documents to isolate issues
4. Review the troubleshooting guide for common solutions