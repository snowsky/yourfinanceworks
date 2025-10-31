# OCR Error Codes Documentation

This document provides comprehensive documentation for all OCR-related error codes, their meanings, common causes, and resolution strategies.

## Error Code Format

OCR error codes follow the format `OCR_XXX` where `XXX` is a three-digit number. Each error code is accompanied by:
- HTTP status code
- Human-readable error message
- Machine-readable error code
- Context information
- Suggested resolutions

## OCR Error Codes Reference

### OCR_001: OCR_UNAVAILABLE

**HTTP Status**: 503 Service Unavailable

**Description**: OCR system is not available or has been disabled.

**Common Causes**:
- OCR functionality disabled via configuration (`BANK_OCR_ENABLED=false`)
- Required dependencies not installed (Tesseract, Python packages)
- System resources exhausted
- OCR service temporarily down

**Example Response**:
```json
{
  "detail": "OCR processing is currently unavailable. Please try again later.",
  "error_code": "OCR_UNAVAILABLE",
  "context": {
    "ocr_enabled": false,
    "tesseract_available": false,
    "dependencies_missing": ["pytesseract", "unstructured"]
  },
  "suggestions": [
    "Check OCR configuration settings",
    "Verify Tesseract installation",
    "Install missing Python dependencies"
  ]
}
```

**Resolution Steps**:
1. Check `BANK_OCR_ENABLED` environment variable
2. Verify Tesseract installation: `tesseract --version`
3. Install missing dependencies: `pip install -r requirements.txt`
4. Check system resources (CPU, memory, disk space)

---

### OCR_002: OCR_TIMEOUT

**HTTP Status**: 408 Request Timeout

**Description**: OCR processing exceeded the configured timeout limit.

**Common Causes**:
- Document too complex or large
- System under heavy load
- Timeout setting too low
- Poor document quality requiring extensive processing

**Example Response**:
```json
{
  "detail": "OCR processing timed out after 300 seconds",
  "error_code": "OCR_TIMEOUT",
  "context": {
    "timeout_seconds": 300,
    "processing_time": 300.0,
    "document_size": "15.2 MB",
    "pages": 25
  },
  "suggestions": [
    "Try with a smaller or clearer document",
    "Increase OCR timeout setting",
    "Use fast processing strategy for large documents"
  ]
}
```

**Resolution Steps**:
1. Increase `BANK_OCR_TIMEOUT` value
2. Use `UNSTRUCTURED_STRATEGY=fast` for faster processing
3. Reduce document size or split large documents
4. Improve document quality (higher resolution, better contrast)

---

### OCR_003: OCR_PROCESSING_ERROR

**HTTP Status**: 500 Internal Server Error

**Description**: OCR processing failed due to an internal error.

**Common Causes**:
- Corrupted or invalid document format
- Tesseract processing error
- Memory allocation failure
- Unexpected exception during processing

**Example Response**:
```json
{
  "detail": "OCR processing failed: Unable to process document structure",
  "error_code": "OCR_PROCESSING_ERROR",
  "context": {
    "extraction_method": "ocr",
    "error_details": "TesseractError: (1, 'Error opening data file')",
    "document_type": "PDF",
    "processing_stage": "text_extraction"
  },
  "suggestions": [
    "Verify document is not corrupted",
    "Try with a different document format",
    "Check Tesseract language data installation"
  ]
}
```

**Resolution Steps**:
1. Verify document integrity
2. Check Tesseract language packs: `tesseract --list-langs`
3. Install language data: `sudo apt-get install tesseract-ocr-eng`
4. Try with a different document or format

---

### OCR_004: TESSERACT_NOT_FOUND

**HTTP Status**: 503 Service Unavailable

**Description**: Tesseract OCR engine is not installed or not found at the specified path.

**Common Causes**:
- Tesseract not installed on system
- Incorrect `TESSERACT_CMD` path
- Permission issues accessing Tesseract binary
- Tesseract installation corrupted

**Example Response**:
```json
{
  "detail": "Tesseract OCR engine not found at /usr/bin/tesseract",
  "error_code": "TESSERACT_NOT_FOUND",
  "context": {
    "tesseract_path": "/usr/bin/tesseract",
    "path_exists": false,
    "system_path": "/usr/local/bin:/usr/bin:/bin"
  },
  "suggestions": [
    "Install Tesseract: sudo apt-get install tesseract-ocr",
    "Set correct path: export TESSERACT_CMD=/usr/local/bin/tesseract",
    "Verify Tesseract permissions"
  ]
}
```

**Resolution Steps**:
1. Install Tesseract: `sudo apt-get install tesseract-ocr`
2. Find Tesseract location: `which tesseract`
3. Set correct path: `export TESSERACT_CMD=$(which tesseract)`
4. Verify permissions: `ls -la $(which tesseract)`

---

### OCR_005: INSUFFICIENT_TEXT_QUALITY

**HTTP Status**: 422 Unprocessable Entity

**Description**: Neither PDF extraction nor OCR produced sufficient readable text.

**Common Causes**:
- Very poor document quality
- Document contains mostly images or graphics
- Text too small or blurry to recognize
- Unsupported language or character set

**Example Response**:
```json
{
  "detail": "Unable to extract sufficient text from document using PDF or OCR methods",
  "error_code": "INSUFFICIENT_TEXT_QUALITY",
  "context": {
    "pdf_text_length": 5,
    "ocr_text_length": 12,
    "min_threshold": 50,
    "ocr_confidence": 0.23
  },
  "suggestions": [
    "Provide a clearer scan or higher resolution document",
    "Ensure document contains readable text",
    "Try with a different document format"
  ]
}
```

**Resolution Steps**:
1. Improve document quality (higher resolution, better contrast)
2. Ensure document contains actual text (not just images)
3. Try different scanning settings
4. Lower text quality thresholds if appropriate

---

### OCR_006: OCR_DEPENDENCY_MISSING

**HTTP Status**: 503 Service Unavailable

**Description**: Required Python packages for OCR processing are not installed.

**Common Causes**:
- Missing `pytesseract` package
- Missing `unstructured` package
- Missing `langchain-unstructured` package
- Incompatible package versions

**Example Response**:
```json
{
  "detail": "Required OCR dependencies are missing",
  "error_code": "OCR_DEPENDENCY_MISSING",
  "context": {
    "missing_packages": ["pytesseract", "unstructured[pdf]"],
    "python_version": "3.11.0",
    "pip_version": "23.0.1"
  },
  "suggestions": [
    "Install missing packages: pip install pytesseract unstructured[pdf]",
    "Update requirements: pip install -r requirements.txt",
    "Check package compatibility"
  ]
}
```

**Resolution Steps**:
1. Install missing packages: `pip install pytesseract unstructured[pdf] langchain-unstructured`
2. Update all requirements: `pip install -r requirements.txt`
3. Verify installations: `pip list | grep -E "(tesseract|unstructured)"`

---

### OCR_007: OCR_CONFIG_INVALID

**HTTP Status**: 500 Internal Server Error

**Description**: OCR configuration contains invalid or incompatible settings.

**Common Causes**:
- Invalid timeout values
- Incompatible Tesseract options
- Invalid directory paths
- Conflicting configuration settings

**Example Response**:
```json
{
  "detail": "OCR configuration is invalid",
  "error_code": "OCR_CONFIG_INVALID",
  "context": {
    "invalid_settings": {
      "BANK_OCR_TIMEOUT": "invalid_value",
      "OCR_TEMP_DIR": "/nonexistent/path"
    },
    "validation_errors": [
      "Timeout must be between 30 and 3600 seconds",
      "Temporary directory does not exist or is not writable"
    ]
  },
  "suggestions": [
    "Check environment variable values",
    "Ensure directories exist and are writable",
    "Validate timeout and threshold settings"
  ]
}
```

**Resolution Steps**:
1. Validate all OCR environment variables
2. Check directory permissions and existence
3. Ensure numeric values are within valid ranges
4. Test configuration with validation endpoint

---

### OCR_008: OCR_FILE_TOO_LARGE

**HTTP Status**: 413 Payload Too Large

**Description**: Document file is too large for OCR processing.

**Common Causes**:
- File exceeds maximum size limit
- Document has too many pages
- High-resolution images in document
- System memory limitations

**Example Response**:
```json
{
  "detail": "Document file is too large for OCR processing",
  "error_code": "OCR_FILE_TOO_LARGE",
  "context": {
    "file_size": "52.3 MB",
    "max_size": "50 MB",
    "pages": 150,
    "max_pages": 100
  },
  "suggestions": [
    "Split large documents into smaller files",
    "Reduce image resolution in PDF",
    "Use document compression tools"
  ]
}
```

**Resolution Steps**:
1. Split large documents into smaller files
2. Reduce PDF image quality/resolution
3. Increase system memory if possible
4. Configure larger file size limits if appropriate

---

### OCR_009: OCR_UNSUPPORTED_FORMAT

**HTTP Status**: 415 Unsupported Media Type

**Description**: Document format is not supported by OCR processing.

**Common Causes**:
- Encrypted or password-protected PDFs
- Corrupted file format
- Unsupported PDF version
- Non-standard document encoding

**Example Response**:
```json
{
  "detail": "Document format is not supported for OCR processing",
  "error_code": "OCR_UNSUPPORTED_FORMAT",
  "context": {
    "file_type": "application/pdf",
    "format_details": "encrypted PDF",
    "supported_formats": ["PDF (unencrypted)", "CSV", "TXT"]
  },
  "suggestions": [
    "Remove password protection from PDF",
    "Convert to supported format",
    "Verify file is not corrupted"
  ]
}
```

**Resolution Steps**:
1. Remove password protection from PDFs
2. Convert to standard PDF format
3. Verify file integrity
4. Try with a different document

---

### OCR_010: OCR_MEMORY_ERROR

**HTTP Status**: 507 Insufficient Storage

**Description**: OCR processing failed due to insufficient memory.

**Common Causes**:
- System running out of RAM
- Large document requiring extensive memory
- Memory leak in OCR processing
- Too many concurrent OCR operations

**Example Response**:
```json
{
  "detail": "OCR processing failed due to insufficient memory",
  "error_code": "OCR_MEMORY_ERROR",
  "context": {
    "available_memory": "512 MB",
    "required_memory": "2 GB",
    "concurrent_jobs": 4,
    "document_size": "25.7 MB"
  },
  "suggestions": [
    "Reduce concurrent OCR operations",
    "Process smaller documents",
    "Increase system memory",
    "Use fast processing strategy"
  ]
}
```

**Resolution Steps**:
1. Reduce `OCR_MAX_CONCURRENT_JOBS`
2. Use `UNSTRUCTURED_STRATEGY=fast`
3. Add system memory or swap space
4. Process documents in smaller batches

---

### OCR_011: OCR_PERMISSION_DENIED

**HTTP Status**: 403 Forbidden

**Description**: OCR processing failed due to insufficient file system permissions.

**Common Causes**:
- Cannot access temporary directory
- Cannot execute Tesseract binary
- Cannot read input document
- Cannot write output files

**Example Response**:
```json
{
  "detail": "OCR processing failed due to permission denied",
  "error_code": "OCR_PERMISSION_DENIED",
  "context": {
    "operation": "create_temp_file",
    "path": "/tmp/ocr_processing",
    "user": "www-data",
    "permissions": "755"
  },
  "suggestions": [
    "Check directory permissions",
    "Ensure user has write access to temp directory",
    "Verify Tesseract binary is executable"
  ]
}
```

**Resolution Steps**:
1. Check directory permissions: `ls -la /tmp/ocr_processing`
2. Fix permissions: `chmod 755 /tmp/ocr_processing`
3. Ensure correct ownership: `chown user:group /tmp/ocr_processing`
4. Verify Tesseract permissions: `ls -la $(which tesseract)`

---

### OCR_012: OCR_TEMP_DIR_UNAVAILABLE

**HTTP Status**: 503 Service Unavailable

**Description**: OCR temporary directory is not available or accessible.

**Common Causes**:
- Temporary directory does not exist
- Disk space exhausted
- Directory permissions incorrect
- Mount point unavailable

**Example Response**:
```json
{
  "detail": "OCR temporary directory is not available",
  "error_code": "OCR_TEMP_DIR_UNAVAILABLE",
  "context": {
    "temp_dir": "/tmp/ocr_processing",
    "exists": false,
    "disk_space": "0 MB",
    "mount_point": "/tmp"
  },
  "suggestions": [
    "Create temporary directory",
    "Free up disk space",
    "Check mount point availability"
  ]
}
```

**Resolution Steps**:
1. Create directory: `mkdir -p /tmp/ocr_processing`
2. Check disk space: `df -h /tmp`
3. Clean up old files: `find /tmp -name "*ocr*" -mtime +1 -delete`
4. Set proper permissions: `chmod 755 /tmp/ocr_processing`

---

### OCR_013: OCR_API_KEY_INVALID

**HTTP Status**: 401 Unauthorized

**Description**: Unstructured API key is invalid or expired.

**Common Causes**:
- API key not set or incorrect
- API key expired
- API key lacks required permissions
- API endpoint changed

**Example Response**:
```json
{
  "detail": "Unstructured API key is invalid or expired",
  "error_code": "OCR_API_KEY_INVALID",
  "context": {
    "api_endpoint": "https://api.unstructured.io",
    "key_length": 32,
    "last_successful_call": "2024-01-10T15:30:00Z"
  },
  "suggestions": [
    "Verify API key is correct",
    "Check API key expiration",
    "Regenerate API key if needed"
  ]
}
```

**Resolution Steps**:
1. Verify API key: `echo $UNSTRUCTURED_API_KEY`
2. Test API key: `curl -H "Authorization: Bearer $UNSTRUCTURED_API_KEY" https://api.unstructured.io`
3. Regenerate key if needed
4. Update environment variable

---

### OCR_014: OCR_API_QUOTA_EXCEEDED

**HTTP Status**: 429 Too Many Requests

**Description**: Unstructured API quota or rate limit exceeded.

**Common Causes**:
- Monthly API quota exhausted
- Rate limit exceeded
- Too many concurrent requests
- Account billing issues

**Example Response**:
```json
{
  "detail": "Unstructured API quota exceeded",
  "error_code": "OCR_API_QUOTA_EXCEEDED",
  "context": {
    "quota_used": 10000,
    "quota_limit": 10000,
    "reset_date": "2024-02-01T00:00:00Z",
    "rate_limit": "100/hour"
  },
  "suggestions": [
    "Wait for quota reset",
    "Upgrade API plan",
    "Use local OCR processing",
    "Reduce processing frequency"
  ]
}
```

**Resolution Steps**:
1. Check API usage dashboard
2. Wait for quota reset or upgrade plan
3. Switch to local processing: `UNSTRUCTURED_USE_API=false`
4. Implement request throttling

---

### OCR_015: OCR_API_CONNECTION_FAILED

**HTTP Status**: 502 Bad Gateway

**Description**: Failed to connect to Unstructured API service.

**Common Causes**:
- Network connectivity issues
- API service temporarily down
- Firewall blocking requests
- DNS resolution problems

**Example Response**:
```json
{
  "detail": "Failed to connect to Unstructured API",
  "error_code": "OCR_API_CONNECTION_FAILED",
  "context": {
    "api_endpoint": "https://api.unstructured.io",
    "connection_timeout": 30,
    "last_attempt": "2024-01-15T10:30:00Z",
    "retry_count": 3
  },
  "suggestions": [
    "Check network connectivity",
    "Verify API endpoint URL",
    "Try again later",
    "Use local OCR processing as fallback"
  ]
}
```

**Resolution Steps**:
1. Test connectivity: `ping api.unstructured.io`
2. Check firewall settings
3. Verify DNS resolution: `nslookup api.unstructured.io`
4. Fall back to local processing temporarily

## Error Handling Best Practices

### For API Consumers

1. **Implement Retry Logic**: Use exponential backoff for transient errors
2. **Handle Timeouts Gracefully**: OCR operations can take several minutes
3. **Provide User Feedback**: Inform users about processing delays
4. **Fallback Strategies**: Have alternatives when OCR fails

### Example Error Handling

```javascript
async function processDocument(file) {
  try {
    const response = await uploadDocument(file);
    return response;
  } catch (error) {
    switch (error.error_code) {
      case 'OCR_TIMEOUT':
        // Retry with longer timeout or different strategy
        return retryWithFastStrategy(file);
      
      case 'OCR_UNAVAILABLE':
        // Fall back to manual processing
        return scheduleManualProcessing(file);
      
      case 'INSUFFICIENT_TEXT_QUALITY':
        // Ask user to provide better quality document
        throw new UserError('Please provide a clearer document');
      
      default:
        // Generic error handling
        throw new ProcessingError('Document processing failed');
    }
  }
}
```

### For System Administrators

1. **Monitor Error Rates**: Track OCR error frequency and patterns
2. **Set Up Alerts**: Alert on high error rates or specific error types
3. **Log Analysis**: Analyze logs to identify common issues
4. **Capacity Planning**: Monitor resource usage during OCR operations

### Error Monitoring Query Examples

```bash
# Monitor OCR error rates
grep "OCR_" /var/log/app/app.log | grep -c "$(date +%Y-%m-%d)"

# Most common OCR errors
grep "OCR_" /var/log/app/app.log | awk '{print $NF}' | sort | uniq -c | sort -nr

# OCR timeout frequency
grep "OCR_TIMEOUT" /var/log/app/app.log | wc -l

# Average OCR processing time
grep "OCR processing time" /var/log/app/app.log | awk '{print $NF}' | awk '{sum+=$1; count++} END {print sum/count}'
```

## Error Resolution Flowchart

```
Document Upload
       ↓
   PDF Extraction
       ↓
   Text Sufficient? ──Yes──→ Success
       ↓ No
   OCR Available? ──No───→ OCR_UNAVAILABLE
       ↓ Yes
   Start OCR Processing
       ↓
   Timeout? ──Yes──→ OCR_TIMEOUT
       ↓ No
   Processing Error? ──Yes──→ OCR_PROCESSING_ERROR
       ↓ No
   Text Quality OK? ──No───→ INSUFFICIENT_TEXT_QUALITY
       ↓ Yes
   Success
```

This comprehensive error code documentation helps developers and administrators understand, diagnose, and resolve OCR-related issues effectively.