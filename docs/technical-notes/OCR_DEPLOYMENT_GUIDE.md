# OCR Fallback Deployment Guide

This guide provides comprehensive instructions for deploying the OCR fallback functionality for bank statement processing in production environments.

## Overview

The OCR fallback system enhances bank statement processing by automatically detecting when PDF text extraction fails and seamlessly falling back to OCR-based text extraction. This deployment guide covers:

- Production deployment requirements
- Configuration management
- Migration from existing installations
- Troubleshooting common deployment issues
- Performance optimization
- Monitoring and maintenance

## Pre-Deployment Requirements

### System Requirements

#### Minimum Hardware Requirements
- **CPU**: 2+ cores (4+ recommended for high-volume processing)
- **RAM**: 4GB minimum (8GB+ recommended)
- **Storage**: 10GB free space for temporary OCR processing
- **Network**: Stable internet connection (if using Unstructured API)

#### Operating System Support
- Ubuntu 18.04+ / Debian 9+
- CentOS 7+ / RHEL 7+
- Amazon Linux 2
- Docker containers (recommended)

### Dependencies Checklist

Before deployment, ensure the following are installed:

- [ ] Tesseract OCR engine (4.0+)
- [ ] Python 3.8+ with pip
- [ ] Required Python packages (see requirements.txt)
- [ ] Sufficient disk space for temporary files
- [ ] Network access (for API mode)

## Deployment Steps

### Step 1: Install System Dependencies

#### Ubuntu/Debian
```bash
# Update package list
sudo apt-get update

# Install Tesseract and language packs
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa

# Verify installation
tesseract --version
```

#### CentOS/RHEL
```bash
# Install EPEL repository (if not already installed)
sudo yum install -y epel-release

# Install Tesseract
sudo yum install -y tesseract tesseract-langpack-eng

# Verify installation
tesseract --version
```

#### Docker Deployment (Recommended)
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

# Set Tesseract path
ENV TESSERACT_CMD=/usr/bin/tesseract

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Create directories for temporary files
RUN mkdir -p /app/temp /app/logs

# Set proper permissions
RUN chmod 755 /app/temp /app/logs

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2: Configure Environment Variables

Create or update your `.env` file with OCR-specific settings:

```bash
# OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
BANK_OCR_MIN_TEXT_THRESHOLD=50
BANK_OCR_MIN_WORD_THRESHOLD=10

# Tesseract Configuration
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG=--oem 3 --psm 6

# UnstructuredLoader Configuration
UNSTRUCTURED_STRATEGY=hi_res
UNSTRUCTURED_MODE=single

# Optional: Unstructured API (for cloud processing)
UNSTRUCTURED_USE_API=false
UNSTRUCTURED_API_KEY=
UNSTRUCTURED_API_URL=https://api.unstructured.io

# Performance Tuning
OCR_MAX_CONCURRENT_JOBS=2
OCR_TEMP_DIR=/tmp/ocr_processing
OCR_CLEANUP_INTERVAL=3600
```

### Step 3: Install Python Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Verify OCR packages are installed
python -c "import pytesseract; print('pytesseract:', pytesseract.__version__)"
python -c "from unstructured.partition.pdf import partition_pdf; print('unstructured: OK')"
```

### Step 4: Validate Configuration

Run the built-in configuration validator:

```bash
# Check OCR dependencies
python -c "
from settings.ocr_config import check_ocr_dependencies, is_ocr_available, log_ocr_status
print('Dependencies:', check_ocr_dependencies())
print('OCR Available:', is_ocr_available())
log_ocr_status()
"

# Test OCR functionality
python -c "
from settings.ocr_config import test_ocr_configuration
results = test_ocr_configuration()
print('Test Results:', results)
"
```

### Step 5: Deploy Application

#### Standard Deployment
```bash
# Start the application
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Or using gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Docker Compose Deployment
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - BANK_OCR_ENABLED=true
      - TESSERACT_CMD=/usr/bin/tesseract
      - BANK_OCR_TIMEOUT=300
      - OCR_MAX_CONCURRENT_JOBS=2
    volumes:
      - ./attachments:/app/attachments
      - ./temp:/app/temp
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Migration from Existing Installations

### Pre-Migration Checklist

- [ ] Backup existing database
- [ ] Document current configuration
- [ ] Test OCR functionality in staging environment
- [ ] Plan maintenance window
- [ ] Prepare rollback plan

### Migration Steps

#### 1. Backup Current System
```bash
# Backup database
pg_dump your_database > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup configuration files
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
cp -r attachments attachments.backup.$(date +%Y%m%d_%H%M%S)
```

#### 2. Install OCR Dependencies
Follow the installation steps above without stopping the current application.

#### 3. Update Configuration
Add OCR configuration to your existing `.env` file:
```bash
# Add these lines to existing .env
echo "BANK_OCR_ENABLED=true" >> .env
echo "BANK_OCR_TIMEOUT=300" >> .env
echo "TESSERACT_CMD=/usr/bin/tesseract" >> .env
```

#### 4. Deploy Updated Application
```bash
# Stop current application
sudo systemctl stop your-app

# Update application code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Validate configuration
python -c "from settings.ocr_config import is_ocr_available; print('OCR Ready:', is_ocr_available())"

# Start application
sudo systemctl start your-app
```

#### 5. Verify Migration
```bash
# Check application logs
tail -f /var/log/your-app/app.log

# Test OCR functionality
curl -X POST http://localhost:8000/api/test-ocr \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

### Rollback Plan

If issues occur during migration:

#### 1. Quick Rollback
```bash
# Disable OCR fallback
export BANK_OCR_ENABLED=false

# Restart application
sudo systemctl restart your-app
```

#### 2. Full Rollback
```bash
# Stop application
sudo systemctl stop your-app

# Restore previous version
git checkout previous-version-tag

# Restore configuration
cp .env.backup.YYYYMMDD_HHMMSS .env

# Restart application
sudo systemctl start your-app
```

## Configuration Management

### Production Configuration Template

```bash
# Production OCR Configuration
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
BANK_OCR_MIN_TEXT_THRESHOLD=50
BANK_OCR_MIN_WORD_THRESHOLD=10

# Tesseract Optimization for Production
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG=--oem 3 --psm 6

# Performance Settings
OCR_MAX_CONCURRENT_JOBS=4
OCR_TEMP_DIR=/var/tmp/ocr_processing
OCR_CLEANUP_INTERVAL=1800

# Monitoring
OCR_LOG_LEVEL=INFO
OCR_METRICS_ENABLED=true

# High-Volume Processing
UNSTRUCTURED_STRATEGY=fast
UNSTRUCTURED_MODE=single
```

### Environment-Specific Settings

#### Development
```bash
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=120
OCR_MAX_CONCURRENT_JOBS=1
OCR_LOG_LEVEL=DEBUG
```

#### Staging
```bash
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=240
OCR_MAX_CONCURRENT_JOBS=2
OCR_LOG_LEVEL=INFO
```

#### Production
```bash
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
OCR_MAX_CONCURRENT_JOBS=4
OCR_LOG_LEVEL=WARNING
```

## Troubleshooting Common Deployment Issues

### Issue 1: Tesseract Not Found

**Symptoms:**
- `TesseractNotFoundError: tesseract is not installed`
- OCR processing fails immediately

**Solutions:**
```bash
# Check if Tesseract is installed
which tesseract

# Install if missing
sudo apt-get install tesseract-ocr

# Set correct path in environment
export TESSERACT_CMD=$(which tesseract)
```

### Issue 2: Permission Denied Errors

**Symptoms:**
- `PermissionError: [Errno 13] Permission denied`
- OCR processing fails with permission errors

**Solutions:**
```bash
# Check file permissions
ls -la /usr/bin/tesseract

# Fix permissions if needed
sudo chmod +x /usr/bin/tesseract

# Create temp directory with proper permissions
sudo mkdir -p /var/tmp/ocr_processing
sudo chown app:app /var/tmp/ocr_processing
sudo chmod 755 /var/tmp/ocr_processing
```

### Issue 3: Memory Issues

**Symptoms:**
- `MemoryError` during OCR processing
- Process killed by OOM killer
- Slow OCR processing

**Solutions:**
```bash
# Monitor memory usage
htop

# Reduce concurrent OCR jobs
export OCR_MAX_CONCURRENT_JOBS=1

# Use faster processing strategy
export UNSTRUCTURED_STRATEGY=fast

# Increase swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Issue 4: Timeout Issues

**Symptoms:**
- OCR processing times out
- `OCRTimeoutError` in logs

**Solutions:**
```bash
# Increase timeout
export BANK_OCR_TIMEOUT=600

# Check system load
uptime

# Optimize Tesseract settings
export TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0"
```

### Issue 5: API Connectivity Issues

**Symptoms:**
- Unstructured API calls fail
- Network timeout errors

**Solutions:**
```bash
# Test API connectivity
curl -I https://api.unstructured.io

# Check API key
curl -H "Authorization: Bearer $UNSTRUCTURED_API_KEY" \
     https://api.unstructured.io/general/v0/general

# Fall back to local processing
export UNSTRUCTURED_USE_API=false
```

## Performance Optimization

### System-Level Optimizations

#### CPU Optimization
```bash
# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase process priority
nice -n -10 python main.py
```

#### Memory Optimization
```bash
# Increase shared memory
echo "kernel.shmmax = 268435456" | sudo tee -a /etc/sysctl.conf
echo "kernel.shmall = 2097152" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### Disk I/O Optimization
```bash
# Use SSD for temp directory
export OCR_TEMP_DIR=/mnt/ssd/ocr_temp

# Enable disk caching
echo "vm.dirty_ratio = 15" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_background_ratio = 5" | sudo tee -a /etc/sysctl.conf
```

### Application-Level Optimizations

#### Configuration Tuning
```bash
# Optimize for speed over accuracy
UNSTRUCTURED_STRATEGY=fast
TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0"

# Reduce text quality thresholds
BANK_OCR_MIN_TEXT_THRESHOLD=30
BANK_OCR_MIN_WORD_THRESHOLD=5

# Increase concurrent processing
OCR_MAX_CONCURRENT_JOBS=8
```

## Monitoring and Maintenance

### Health Checks

Create a health check endpoint:
```python
@app.get("/health/ocr")
async def ocr_health_check():
    from settings.ocr_config import is_ocr_available, check_ocr_dependencies
    
    status = {
        "ocr_available": is_ocr_available(),
        "dependencies": check_ocr_dependencies(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return status
```

### Log Monitoring

Monitor OCR-specific logs:
```bash
# Monitor OCR processing logs
tail -f /var/log/app/ocr.log | grep -E "(OCR|tesseract|unstructured)"

# Monitor error rates
grep -c "OCRError" /var/log/app/app.log

# Monitor processing times
grep "OCR processing time" /var/log/app/app.log | awk '{print $NF}' | sort -n
```

### Metrics Collection

Key metrics to monitor:
- OCR processing success rate
- Average processing time (PDF vs OCR)
- Memory usage during OCR operations
- Disk space usage in temp directories
- API usage (if using Unstructured API)

### Maintenance Tasks

#### Daily
- Check disk space in temp directories
- Monitor error rates
- Verify OCR service availability

#### Weekly
- Clean up old temporary files
- Review performance metrics
- Update language packs if needed

#### Monthly
- Update OCR dependencies
- Review and optimize configuration
- Test disaster recovery procedures

### Automated Maintenance Script

```bash
#!/bin/bash
# ocr_maintenance.sh

# Clean up old temp files
find /var/tmp/ocr_processing -type f -mtime +1 -delete

# Check disk space
df -h /var/tmp/ocr_processing

# Test OCR functionality
python -c "from settings.ocr_config import test_ocr_configuration; print(test_ocr_configuration())"

# Log maintenance completion
echo "$(date): OCR maintenance completed" >> /var/log/app/maintenance.log
```

Add to crontab:
```bash
# Run daily at 2 AM
0 2 * * * /path/to/ocr_maintenance.sh
```

## Security Considerations

### File Security
- Ensure temporary files are properly cleaned up
- Set appropriate file permissions (600 for sensitive files)
- Use secure temporary directories

### API Security
- Store API keys in environment variables, not code
- Use HTTPS for all API communications
- Monitor API usage for anomalies
- Implement rate limiting

### Network Security
- Restrict outbound connections if using local processing only
- Use VPN or private networks for API communications
- Monitor network traffic for unusual patterns

## Support and Troubleshooting

### Diagnostic Commands

```bash
# Check OCR system status
python -c "
from settings.ocr_config import log_ocr_status
log_ocr_status()
"

# Test with sample document
python -c "
from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
extractor = EnhancedPDFTextExtractor()
text, method = extractor.extract_text('sample.pdf')
print(f'Method: {method}, Text length: {len(text)}')
"

# Check system resources
free -h
df -h
ps aux | grep -E "(tesseract|python)"
```

### Log Analysis

Common log patterns to monitor:
```bash
# OCR fallback triggers
grep "falling back to OCR" /var/log/app/app.log

# Processing times
grep "OCR processing time" /var/log/app/app.log

# Error patterns
grep -E "(OCRError|TesseractError)" /var/log/app/app.log
```

### Getting Help

1. Check application logs for detailed error messages
2. Use built-in diagnostic tools
3. Verify system dependencies are properly installed
4. Test with sample documents to isolate issues
5. Review this deployment guide for common solutions

For additional support, ensure you have:
- System information (OS, version, architecture)
- Application logs with error details
- Configuration settings (sanitized)
- Steps to reproduce the issue