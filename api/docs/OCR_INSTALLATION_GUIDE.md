# OCR Installation Guide

This guide covers the installation and configuration of OCR (Optical Character Recognition) dependencies for bank statement processing fallback functionality.

## Overview

The OCR fallback system uses two main approaches:
1. **Local Tesseract OCR** - Runs OCR processing locally using Tesseract engine
2. **Unstructured API** - Uses cloud-based OCR processing via Unstructured.io API

## System Dependencies

### Tesseract OCR Engine

Tesseract is required for local OCR processing. Install it based on your operating system:

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

#### CentOS/RHEL/Fedora
```bash
# CentOS/RHEL
sudo yum install tesseract tesseract-langpack-eng

# Fedora
sudo dnf install tesseract tesseract-langpack-eng
```

#### macOS
```bash
# Using Homebrew
brew install tesseract

# Using MacPorts
sudo port install tesseract3 +universal
```

#### Windows
1. Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer and note the installation path
3. Add Tesseract to your PATH or set TESSERACT_CMD environment variable

#### Docker
If running in Docker, add to your Dockerfile:
```dockerfile
# For Ubuntu-based images
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# For Alpine-based images
RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-eng
```

### Additional Language Packs (Optional)

For processing documents in languages other than English:

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr-fra tesseract-ocr-deu tesseract-ocr-spa

# CentOS/RHEL
sudo yum install tesseract-langpack-fra tesseract-langpack-deu tesseract-langpack-spa

# macOS
brew install tesseract-lang
```

## Python Dependencies

The required Python packages are already included in `requirements.txt`:

```
unstructured[pdf]==0.10.30
langchain-unstructured==0.1.0
pytesseract==0.3.10
tesseract==0.1.3
```

Install them with:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Configure OCR settings in your `.env` file:

```bash
# Enable/disable OCR fallback
BANK_OCR_ENABLED=true

# OCR processing timeout (seconds)
BANK_OCR_TIMEOUT=300

# Text quality thresholds for triggering OCR
BANK_OCR_MIN_TEXT_THRESHOLD=50
BANK_OCR_MIN_WORD_THRESHOLD=10

# Tesseract configuration
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG=--oem 3 --psm 6

# UnstructuredLoader settings
UNSTRUCTURED_STRATEGY=hi_res
UNSTRUCTURED_MODE=single

# Optional: Use Unstructured API instead of local processing
UNSTRUCTURED_USE_API=false
UNSTRUCTURED_API_KEY=your-api-key-here
UNSTRUCTURED_API_URL=https://api.unstructured.io
```

### Tesseract Configuration Options

The `TESSERACT_CONFIG` variable accepts Tesseract command-line options:

- `--oem 3`: Use LSTM OCR Engine Mode (recommended)
- `--psm 6`: Assume uniform block of text (good for bank statements)
- `--psm 1`: Automatic page segmentation with OSD
- `--psm 4`: Assume single column of text of variable sizes

Common configurations:
```bash
# Default (recommended for bank statements)
TESSERACT_CONFIG=--oem 3 --psm 6

# For documents with mixed layouts
TESSERACT_CONFIG=--oem 3 --psm 1

# For single column documents
TESSERACT_CONFIG=--oem 3 --psm 4
```

## Verification

### Check Installation

Use the built-in dependency checker:

```python
from settings.ocr_config import check_ocr_dependencies, is_ocr_available, log_ocr_status

# Check individual dependencies
deps = check_ocr_dependencies()
print(deps)

# Check overall availability
available = is_ocr_available()
print(f"OCR Available: {available}")

# Log comprehensive status
log_ocr_status()
```

### Test OCR Functionality

```python
from settings.ocr_config import test_ocr_configuration

# Run comprehensive tests
results = test_ocr_configuration()
print(results)
```

### Command Line Verification

Test Tesseract installation:
```bash
# Check Tesseract version
tesseract --version

# Test OCR on a sample image
tesseract sample.png output.txt

# List available languages
tesseract --list-langs
```

## Troubleshooting

### Common Issues

#### 1. Tesseract Not Found
**Error**: `TesseractNotFoundError: tesseract is not installed`

**Solutions**:
- Install Tesseract using system package manager
- Set `TESSERACT_CMD` environment variable to correct path
- On Windows, add Tesseract to PATH

#### 2. Permission Denied
**Error**: `PermissionError: [Errno 13] Permission denied`

**Solutions**:
- Check file permissions on Tesseract binary
- Run with appropriate user permissions
- In Docker, ensure proper user context

#### 3. Language Data Missing
**Error**: `TesseractError: (1, 'Error opening data file')`

**Solutions**:
- Install language packs: `sudo apt-get install tesseract-ocr-eng`
- Verify language data location: `/usr/share/tesseract-ocr/*/tessdata/`

#### 4. Memory Issues
**Error**: `MemoryError` or process killed

**Solutions**:
- Increase available memory
- Reduce image resolution before OCR
- Use `fast` strategy instead of `hi_res`
- Implement processing timeouts

#### 5. API Key Issues (Unstructured API)
**Error**: `AuthenticationError: Invalid API key`

**Solutions**:
- Verify API key is correct
- Check API key permissions
- Ensure API URL is correct

### Performance Optimization

#### Local Processing
- Use `fast` strategy for quicker processing: `UNSTRUCTURED_STRATEGY=fast`
- Reduce timeout for faster failures: `BANK_OCR_TIMEOUT=120`
- Preprocess images to improve OCR accuracy

#### API Processing
- Use Unstructured API for better accuracy: `UNSTRUCTURED_USE_API=true`
- Configure appropriate timeout values
- Monitor API usage and costs

### Monitoring

#### Log Analysis
OCR operations are logged with the following information:
- Processing method used (PDF loader vs OCR)
- Processing time
- Text extraction results
- Error details

#### Health Checks
Regular health checks verify:
- Tesseract availability
- Python package availability
- API connectivity (if using Unstructured API)
- Configuration validity

## Docker Deployment

### Dockerfile Example
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . /app
WORKDIR /app

# Set Tesseract path
ENV TESSERACT_CMD=/usr/bin/tesseract

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  api:
    build: .
    environment:
      - BANK_OCR_ENABLED=true
      - TESSERACT_CMD=/usr/bin/tesseract
      - BANK_OCR_TIMEOUT=300
    volumes:
      - ./attachments:/app/attachments
```

## Security Considerations

### Local Processing
- Ensure Tesseract binary is from trusted source
- Limit file access permissions
- Validate input files before processing

### API Processing
- Store API keys securely (environment variables, not code)
- Use HTTPS for API communications
- Monitor API usage for anomalies
- Consider data privacy implications of cloud processing

## Performance Benchmarks

Typical processing times (varies by document complexity):

| Method | Small Document | Medium Document | Large Document |
|--------|---------------|-----------------|----------------|
| PDF Loader | 0.1-0.5s | 0.2-1s | 0.5-2s |
| Local OCR | 2-5s | 5-15s | 15-60s |
| API OCR | 1-3s | 3-8s | 8-20s |

## Support

For additional support:
1. Check application logs for detailed error messages
2. Use the built-in diagnostic tools
3. Verify system dependencies are properly installed
4. Test with sample documents to isolate issues