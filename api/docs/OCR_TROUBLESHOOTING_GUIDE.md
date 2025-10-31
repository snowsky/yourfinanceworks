# OCR Troubleshooting Guide

This guide provides comprehensive troubleshooting steps for OCR fallback functionality issues in the bank statement processing system.

## Quick Diagnostic Checklist

Before diving into specific issues, run this quick diagnostic:

```bash
# 1. Check OCR availability
python -c "from settings.ocr_config import is_ocr_available; print('OCR Available:', is_ocr_available())"

# 2. Check dependencies
python -c "from settings.ocr_config import check_ocr_dependencies; print(check_ocr_dependencies())"

# 3. Test basic functionality
python -c "from settings.ocr_config import test_ocr_configuration; print(test_ocr_configuration())"

# 4. Check system resources
free -h && df -h

# 5. Verify Tesseract installation
tesseract --version
```

## Common Issues and Solutions

### 1. OCR Not Available / Disabled

#### Symptoms
- OCR fallback never triggers
- Log messages: "OCR not available, skipping fallback"
- Bank statements with poor PDF text extraction fail completely

#### Diagnostic Steps
```bash
# Check if OCR is enabled
echo $BANK_OCR_ENABLED

# Check OCR configuration
python -c "
from settings.ocr_config import get_ocr_config
config = get_ocr_config()
print('OCR Config:', config)
"

# Check AI configuration
python -c "
from services.ocr_service import OCRService
service = OCRService()
print('AI Config allows OCR:', service.ai_config.get('ocr_enabled', False))
"
```

#### Solutions
```bash
# Enable OCR in environment
export BANK_OCR_ENABLED=true

# Check AI configuration in database
python -c "
from models.database import get_db
from models.models import AIConfig
db = next(get_db())
config = db.query(AIConfig).first()
if config:
    print('OCR enabled in AI config:', config.ocr_enabled)
else:
    print('No AI config found')
"

# Update AI configuration if needed
python -c "
from models.database import get_db
from models.models import AIConfig
db = next(get_db())
config = db.query(AIConfig).first()
if config:
    config.ocr_enabled = True
    db.commit()
    print('OCR enabled in AI config')
"
```

### 2. Tesseract Installation Issues

#### Symptoms
- `TesseractNotFoundError: tesseract is not installed`
- `FileNotFoundError: [Errno 2] No such file or directory: 'tesseract'`
- OCR processing fails immediately

#### Diagnostic Steps
```bash
# Check if Tesseract is installed
which tesseract
tesseract --version

# Check Tesseract path configuration
echo $TESSERACT_CMD

# Test Tesseract directly
echo "Test text" | tesseract stdin stdout
```

#### Solutions

##### Ubuntu/Debian
```bash
# Install Tesseract
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Verify installation
tesseract --version

# Set environment variable
export TESSERACT_CMD=/usr/bin/tesseract
```

##### CentOS/RHEL
```bash
# Install EPEL repository
sudo yum install -y epel-release

# Install Tesseract
sudo yum install -y tesseract tesseract-langpack-eng

# Set environment variable
export TESSERACT_CMD=/usr/bin/tesseract
```

##### macOS
```bash
# Using Homebrew
brew install tesseract

# Set environment variable
export TESSERACT_CMD=/usr/local/bin/tesseract
```

##### Docker
```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

ENV TESSERACT_CMD=/usr/bin/tesseract
```

### 3. Python Package Issues

#### Symptoms
- `ImportError: No module named 'pytesseract'`
- `ImportError: No module named 'unstructured'`
- `ModuleNotFoundError: No module named 'unstructured'`

#### Diagnostic Steps
```bash
# Check installed packages
pip list | grep -E "(tesseract|unstructured|langchain)"

# Check Python path
python -c "import sys; print(sys.path)"

# Test imports individually
python -c "import pytesseract; print('pytesseract OK')"
python -c "from unstructured.partition.pdf import partition_pdf; print('unstructured OK')"
python -c "import unstructured; print('unstructured OK')"
```

#### Solutions
```bash
# Install missing packages
pip install pytesseract==0.3.10
pip install langchain-unstructured==0.1.0
pip install "unstructured[pdf]==0.10.30"

# Or install all requirements
pip install -r requirements.txt

# For virtual environment issues
source venv/bin/activate
pip install -r requirements.txt

# For permission issues
pip install --user -r requirements.txt
```

### 4. Memory and Performance Issues

#### Symptoms
- `MemoryError` during OCR processing
- Process killed by system (OOM killer)
- Very slow OCR processing
- High CPU usage during OCR

#### Diagnostic Steps
```bash
# Monitor memory usage
free -h
htop

# Check swap space
swapon --show

# Monitor during OCR processing
watch -n 1 'free -h && ps aux | grep -E "(tesseract|python)" | head -10'

# Check system limits
ulimit -a
```

#### Solutions

##### Increase Memory Limits
```bash
# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

##### Optimize OCR Settings
```bash
# Reduce concurrent OCR jobs
export OCR_MAX_CONCURRENT_JOBS=1

# Use faster processing strategy
export UNSTRUCTURED_STRATEGY=fast

# Reduce timeout to fail faster
export BANK_OCR_TIMEOUT=120

# Optimize Tesseract settings
export TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_do_invert=0"
```

##### Application-Level Fixes
```python
# In your configuration
OCR_CONFIG = {
    'max_concurrent_jobs': 1,
    'timeout': 120,
    'strategy': 'fast',
    'cleanup_temp_files': True
}
```

### 5. File Permission Issues

#### Symptoms
- `PermissionError: [Errno 13] Permission denied`
- OCR processing fails with access denied errors
- Cannot create temporary files

#### Diagnostic Steps
```bash
# Check Tesseract permissions
ls -la /usr/bin/tesseract

# Check temp directory permissions
ls -la /tmp/
ls -la $OCR_TEMP_DIR

# Check current user
whoami
id

# Test file creation
touch /tmp/test_ocr_file
rm /tmp/test_ocr_file
```

#### Solutions
```bash
# Fix Tesseract permissions
sudo chmod +x /usr/bin/tesseract

# Create and fix temp directory
sudo mkdir -p /var/tmp/ocr_processing
sudo chown $USER:$USER /var/tmp/ocr_processing
sudo chmod 755 /var/tmp/ocr_processing

# Set temp directory in environment
export OCR_TEMP_DIR=/var/tmp/ocr_processing

# For Docker containers
RUN mkdir -p /app/temp && chmod 755 /app/temp
ENV OCR_TEMP_DIR=/app/temp
```

### 6. Timeout Issues

#### Symptoms
- `OCRTimeoutError: OCR processing timed out`
- OCR processing hangs indefinitely
- Slow document processing

#### Diagnostic Steps
```bash
# Check current timeout setting
echo $BANK_OCR_TIMEOUT

# Monitor processing time
time tesseract sample.pdf output.txt

# Check system load
uptime
iostat 1 5
```

#### Solutions
```bash
# Increase timeout for complex documents
export BANK_OCR_TIMEOUT=600

# Optimize Tesseract for speed
export TESSERACT_CONFIG="--oem 3 --psm 6"

# Use faster processing strategy
export UNSTRUCTURED_STRATEGY=fast

# Reduce image quality for faster processing
export UNSTRUCTURED_MODE=single
```

### 7. Text Quality Issues

#### Symptoms
- OCR extracts garbled or incorrect text
- Poor recognition accuracy
- Missing text from documents

#### Diagnostic Steps
```bash
# Test with sample document
tesseract sample.pdf output.txt
cat output.txt

# Check document quality
file sample.pdf
pdfinfo sample.pdf

# Test different OCR settings
tesseract sample.pdf output1.txt --oem 3 --psm 6
tesseract sample.pdf output2.txt --oem 3 --psm 1
```

#### Solutions

##### Optimize Tesseract Configuration
```bash
# For bank statements (structured documents)
export TESSERACT_CONFIG="--oem 3 --psm 6"

# For mixed layout documents
export TESSERACT_CONFIG="--oem 3 --psm 1"

# For single column text
export TESSERACT_CONFIG="--oem 3 --psm 4"

# Enable additional processing
export TESSERACT_CONFIG="--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,-$"
```

##### Use High-Resolution Strategy
```bash
# Use high-resolution processing
export UNSTRUCTURED_STRATEGY=hi_res

# Enable OCR enhancement
export UNSTRUCTURED_OCR_LANGUAGES=eng
```

##### Preprocess Documents
```python
# Example preprocessing function
def preprocess_for_ocr(pdf_path):
    """Preprocess PDF for better OCR results."""
    # Convert to high-resolution images
    # Apply image enhancement
    # Remove noise
    # Adjust contrast
    pass
```

### 8. API Connectivity Issues (Unstructured API)

#### Symptoms
- `ConnectionError: Failed to connect to API`
- `AuthenticationError: Invalid API key`
- API requests timeout

#### Diagnostic Steps
```bash
# Test API connectivity
curl -I https://api.unstructured.io

# Test API authentication
curl -H "Authorization: Bearer $UNSTRUCTURED_API_KEY" \
     https://api.unstructured.io/general/v0/general

# Check API key
echo $UNSTRUCTURED_API_KEY

# Test network connectivity
ping api.unstructured.io
nslookup api.unstructured.io
```

#### Solutions
```bash
# Verify API key is set correctly
export UNSTRUCTURED_API_KEY="your-actual-api-key"

# Test API key validity
curl -H "Authorization: Bearer $UNSTRUCTURED_API_KEY" \
     -X POST \
     -F "files=@sample.pdf" \
     https://api.unstructured.io/general/v0/general

# Fall back to local processing
export UNSTRUCTURED_USE_API=false

# Configure proxy if needed
export HTTPS_PROXY=http://proxy.company.com:8080
export HTTP_PROXY=http://proxy.company.com:8080
```

### 9. Kafka Worker Issues

#### Symptoms
- OCR processing jobs stuck in queue
- Kafka consumer errors related to OCR
- OCR timeout not handled properly

#### Diagnostic Steps
```bash
# Check Kafka consumer status
python -c "
from workers.ocr_consumer import OCRConsumer
consumer = OCRConsumer()
print('Consumer status:', consumer.is_running())
"

# Check Kafka topics
kafka-topics.sh --list --bootstrap-server localhost:9092

# Monitor Kafka consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group ocr-consumer-group
```

#### Solutions
```bash
# Restart Kafka consumer
sudo systemctl restart kafka-consumer

# Increase consumer timeout
export KAFKA_CONSUMER_TIMEOUT=600

# Configure OCR-specific consumer settings
export OCR_CONSUMER_MAX_POLL_RECORDS=1
export OCR_CONSUMER_SESSION_TIMEOUT=300
```

### 10. Configuration Issues

#### Symptoms
- OCR settings not taking effect
- Inconsistent behavior across environments
- Configuration validation errors

#### Diagnostic Steps
```bash
# Check all OCR environment variables
env | grep -E "(OCR|TESSERACT|UNSTRUCTURED)"

# Validate configuration
python -c "
from settings.ocr_config import validate_ocr_config
result = validate_ocr_config()
print('Config valid:', result)
"

# Check configuration precedence
python -c "
from settings.ocr_config import get_effective_config
config = get_effective_config()
print('Effective config:', config)
"
```

#### Solutions
```bash
# Create comprehensive configuration
cat > .env.ocr << EOF
# OCR Core Settings
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
BANK_OCR_MIN_TEXT_THRESHOLD=50
BANK_OCR_MIN_WORD_THRESHOLD=10

# Tesseract Settings
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG=--oem 3 --psm 6

# UnstructuredLoader Settings
UNSTRUCTURED_STRATEGY=hi_res
UNSTRUCTURED_MODE=single
UNSTRUCTURED_USE_API=false

# Performance Settings
OCR_MAX_CONCURRENT_JOBS=2
OCR_TEMP_DIR=/tmp/ocr_processing
OCR_CLEANUP_INTERVAL=3600

# Logging
OCR_LOG_LEVEL=INFO
EOF

# Source the configuration
source .env.ocr
```

## Advanced Troubleshooting

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Enable debug logging
export OCR_LOG_LEVEL=DEBUG
export PYTHONPATH=$PYTHONPATH:.

# Run with debug output
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)

from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor
extractor = EnhancedPDFTextExtractor()
text, method = extractor.extract_text('problematic.pdf')
print(f'Method: {method}, Text length: {len(text)}')
"
```

### Performance Profiling

Profile OCR performance to identify bottlenecks:

```python
import cProfile
import pstats
from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor

def profile_ocr():
    extractor = EnhancedPDFTextExtractor()
    text, method = extractor.extract_text('sample.pdf')
    return text, method

# Run profiler
cProfile.run('profile_ocr()', 'ocr_profile.stats')

# Analyze results
stats = pstats.Stats('ocr_profile.stats')
stats.sort_stats('cumulative').print_stats(20)
```

### Memory Profiling

Monitor memory usage during OCR processing:

```python
import tracemalloc
from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor

# Start memory tracing
tracemalloc.start()

# Run OCR
extractor = EnhancedPDFTextExtractor()
text, method = extractor.extract_text('large_document.pdf')

# Get memory statistics
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")

tracemalloc.stop()
```

### System Resource Monitoring

Monitor system resources during OCR processing:

```bash
#!/bin/bash
# monitor_ocr.sh

echo "Starting OCR monitoring..."
echo "Timestamp,CPU%,Memory%,DiskIO,NetworkIO" > ocr_metrics.csv

while true; do
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    memory=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    diskio=$(iostat -d 1 1 | tail -n +4 | awk '{print $4}')
    networkio=$(cat /proc/net/dev | grep eth0 | awk '{print $2+$10}')
    
    echo "$timestamp,$cpu,$memory,$diskio,$networkio" >> ocr_metrics.csv
    sleep 5
done
```

## Recovery Procedures

### Emergency Disable OCR

If OCR is causing system issues:

```bash
# Quick disable
export BANK_OCR_ENABLED=false

# Restart application
sudo systemctl restart your-app

# Or kill OCR processes
pkill -f tesseract
pkill -f "python.*ocr"
```

### Clean Up Stuck Processes

```bash
# Find stuck OCR processes
ps aux | grep -E "(tesseract|ocr)" | grep -v grep

# Kill stuck processes
pkill -f tesseract
pkill -f "python.*ocr"

# Clean up temp files
find /tmp -name "*ocr*" -type f -mmin +60 -delete
find $OCR_TEMP_DIR -type f -mmin +60 -delete
```

### Reset OCR Configuration

```bash
# Backup current config
cp .env .env.backup

# Reset to defaults
cat > .env.ocr.defaults << EOF
BANK_OCR_ENABLED=true
BANK_OCR_TIMEOUT=300
TESSERACT_CMD=/usr/bin/tesseract
TESSERACT_CONFIG=--oem 3 --psm 6
UNSTRUCTURED_STRATEGY=hi_res
OCR_MAX_CONCURRENT_JOBS=2
EOF

# Apply defaults
source .env.ocr.defaults
```

## Getting Additional Help

### Information to Collect

When seeking support, collect the following information:

```bash
# System information
uname -a
cat /etc/os-release

# OCR status
python -c "from settings.ocr_config import log_ocr_status; log_ocr_status()"

# Configuration
env | grep -E "(OCR|TESSERACT|UNSTRUCTURED)" | sort

# Recent logs
tail -100 /var/log/app/app.log | grep -E "(OCR|tesseract|error)"

# System resources
free -h
df -h
ps aux | grep -E "(tesseract|python)" | head -10
```

### Support Checklist

Before contacting support:

- [ ] Reviewed this troubleshooting guide
- [ ] Checked system requirements
- [ ] Verified all dependencies are installed
- [ ] Tested with sample documents
- [ ] Collected system information and logs
- [ ] Attempted basic recovery procedures

### Common Support Scenarios

1. **New Installation Issues**: Usually dependency or permission problems
2. **Performance Problems**: Often memory or configuration issues
3. **Accuracy Issues**: Typically document quality or OCR settings
4. **Integration Issues**: Usually configuration or API connectivity problems

Remember to sanitize any sensitive information (API keys, file paths, etc.) before sharing logs or configuration details.