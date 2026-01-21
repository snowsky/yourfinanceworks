# OCR Fallback Migration Notes

This document provides detailed migration instructions for existing installations to add OCR fallback functionality to the bank statement processing system.

## Migration Overview

The OCR fallback feature is designed to be backward compatible and can be deployed without disrupting existing functionality. The migration process involves:

1. Installing OCR dependencies
2. Updating configuration
3. Deploying updated application code
4. Validating functionality
5. Monitoring performance

## Pre-Migration Assessment

### System Compatibility Check

Before starting migration, verify your system meets the requirements:

```bash
# Check operating system compatibility
cat /etc/os-release

# Check available disk space (minimum 10GB recommended)
df -h

# Check available memory (minimum 4GB recommended)
free -h

# Check Python version (3.8+ required)
python --version

# Check current application version
git describe --tags
```

### Current Configuration Backup

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"

# Backup configuration files
cp .env $BACKUP_DIR/
cp -r config/ $BACKUP_DIR/ 2>/dev/null || true

# Backup database
pg_dump your_database > $BACKUP_DIR/database_backup.sql

# Backup attachments directory
tar -czf $BACKUP_DIR/attachments_backup.tar.gz attachments/

# Document current system state
python -c "
import sys
print('Python version:', sys.version)
import pkg_resources
installed_packages = [d for d in pkg_resources.working_set]
with open('$BACKUP_DIR/installed_packages.txt', 'w') as f:
    for package in sorted(installed_packages, key=lambda x: x.project_name):
        f.write(f'{package.project_name}=={package.version}\n')
"

echo "Backup completed in: $BACKUP_DIR"
```

## Migration Scenarios

### Scenario 1: Standard Production Migration

For production systems with minimal downtime requirements.

#### Phase 1: Preparation (No Downtime)

```bash
# 1. Install system dependencies (parallel to running system)
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# 2. Verify Tesseract installation
tesseract --version

# 3. Test OCR functionality
echo "Test OCR installation" | tesseract stdin stdout

# 4. Prepare updated requirements.txt
cat >> requirements.txt << EOF
# OCR Dependencies
unstructured[pdf]==0.10.30
langchain-unstructured==0.1.0
pytesseract==0.3.10
tesseract==0.1.3
EOF

# 5. Install Python dependencies in virtual environment
python -m venv ocr_test_env
source ocr_test_env/bin/activate
pip install -r requirements.txt
deactivate
```

#### Phase 2: Configuration Update (Minimal Downtime)

```bash
# 1. Add OCR configuration to .env (system still running)
cat >> .env << EOF

# OCR Fallback Configuration
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
UNSTRUCTURED_USE_API=false

# Performance Settings
OCR_MAX_CONCURRENT_JOBS=2
OCR_TEMP_DIR=/tmp/ocr_processing
OCR_CLEANUP_INTERVAL=3600
EOF

# 2. Create OCR temp directory
sudo mkdir -p /tmp/ocr_processing
sudo chown $USER:$USER /tmp/ocr_processing
sudo chmod 755 /tmp/ocr_processing
```

#### Phase 3: Application Update (Brief Downtime)

```bash
# 1. Stop application
sudo systemctl stop your-app

# 2. Update application code
git pull origin main

# 3. Install new dependencies
pip install -r requirements.txt

# 4. Validate OCR configuration
python -c "
from settings.ocr_config import is_ocr_available, check_ocr_dependencies
print('OCR Available:', is_ocr_available())
print('Dependencies:', check_ocr_dependencies())
"

# 5. Start application
sudo systemctl start your-app

# 6. Verify application is running
curl -f http://localhost:8000/health || echo "Application not responding"
```

#### Phase 4: Validation and Monitoring

```bash
# 1. Test OCR functionality
python -c "
from settings.ocr_config import test_ocr_configuration
results = test_ocr_configuration()
print('OCR Test Results:', results)
"

# 2. Monitor application logs
tail -f /var/log/your-app/app.log | grep -E "(OCR|tesseract)"

# 3. Test with sample document
curl -X POST http://localhost:8000/api/bank-statements/process \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_scanned_statement.pdf"
```

### Scenario 2: Docker-Based Migration

For containerized deployments.

#### Update Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies including OCR
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

# Copy application
COPY . /app
WORKDIR /app

# Create OCR temp directory
RUN mkdir -p /app/temp && chmod 755 /app/temp
ENV OCR_TEMP_DIR=/app/temp

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Update Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      # Existing environment variables
      - DATABASE_URL=${DATABASE_URL}
      
      # New OCR configuration
      - BANK_OCR_ENABLED=true
      - TESSERACT_CMD=/usr/bin/tesseract
      - BANK_OCR_TIMEOUT=300
      - OCR_MAX_CONCURRENT_JOBS=2
    volumes:
      - ./attachments:/app/attachments
      - ./temp:/app/temp  # OCR temp directory
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Migration Steps

```bash
# 1. Build new image
docker-compose build

# 2. Test new image
docker-compose up -d --no-deps api-test

# 3. Validate OCR functionality
docker-compose exec api-test python -c "
from settings.ocr_config import is_ocr_available
print('OCR Available:', is_ocr_available())
"

# 4. Deploy to production (rolling update)
docker-compose up -d

# 5. Clean up old images
docker image prune -f
```

### Scenario 3: Kubernetes Migration

For Kubernetes deployments.

#### Update Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bank-statement-api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    spec:
      containers:
      - name: api
        image: your-registry/bank-statement-api:latest
        env:
        # Existing environment variables
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        
        # New OCR configuration
        - name: BANK_OCR_ENABLED
          value: "true"
        - name: TESSERACT_CMD
          value: "/usr/bin/tesseract"
        - name: BANK_OCR_TIMEOUT
          value: "300"
        - name: OCR_MAX_CONCURRENT_JOBS
          value: "2"
        - name: OCR_TEMP_DIR
          value: "/tmp/ocr"
        
        volumeMounts:
        - name: ocr-temp
          mountPath: /tmp/ocr
        
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"  # Increased for OCR processing
            cpu: "1000m"   # Increased for OCR processing
      
      volumes:
      - name: ocr-temp
        emptyDir:
          sizeLimit: 10Gi
```

#### Migration Steps

```bash
# 1. Apply new configuration
kubectl apply -f deployment.yaml

# 2. Monitor rollout
kubectl rollout status deployment/bank-statement-api

# 3. Validate OCR functionality
kubectl exec -it deployment/bank-statement-api -- python -c "
from settings.ocr_config import is_ocr_available
print('OCR Available:', is_ocr_available())
"

# 4. Check logs
kubectl logs -f deployment/bank-statement-api | grep -E "(OCR|tesseract)"
```

## Database Migration Requirements

The OCR fallback feature doesn't require database schema changes, but you may want to track OCR usage:

### Optional: Add OCR Tracking Fields

```sql
-- Add OCR tracking to existing tables (optional)
ALTER TABLE bank_statement_processing_logs 
ADD COLUMN extraction_method VARCHAR(20) DEFAULT 'pdf_loader',
ADD COLUMN ocr_processing_time FLOAT,
ADD COLUMN ocr_confidence_score FLOAT;

-- Create index for analytics
CREATE INDEX idx_extraction_method ON bank_statement_processing_logs(extraction_method);
```

### Migration Script

```python
# migration_add_ocr_tracking.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add OCR tracking columns
    op.add_column('bank_statement_processing_logs', 
                  sa.Column('extraction_method', sa.String(20), default='pdf_loader'))
    op.add_column('bank_statement_processing_logs', 
                  sa.Column('ocr_processing_time', sa.Float))
    op.add_column('bank_statement_processing_logs', 
                  sa.Column('ocr_confidence_score', sa.Float))
    
    # Create index
    op.create_index('idx_extraction_method', 'bank_statement_processing_logs', ['extraction_method'])

def downgrade():
    op.drop_index('idx_extraction_method')
    op.drop_column('bank_statement_processing_logs', 'ocr_confidence_score')
    op.drop_column('bank_statement_processing_logs', 'ocr_processing_time')
    op.drop_column('bank_statement_processing_logs', 'extraction_method')
```

## Configuration Migration

### Environment Variable Mapping

Map existing configuration to new OCR settings:

```bash
# Existing AI configuration
AI_ENABLED=true
AI_TIMEOUT=120

# New OCR configuration (derived from AI settings)
BANK_OCR_ENABLED=${AI_ENABLED:-true}
BANK_OCR_TIMEOUT=${AI_TIMEOUT:-300}  # Increased for OCR processing
```

### Configuration Migration Script

```python
#!/usr/bin/env python3
# migrate_ocr_config.py

import os
import shutil
from datetime import datetime

def migrate_configuration():
    """Migrate existing configuration to include OCR settings."""
    
    # Backup existing .env
    if os.path.exists('.env'):
        backup_name = f'.env.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        shutil.copy('.env', backup_name)
        print(f"Backed up .env to {backup_name}")
    
    # Read existing configuration
    existing_config = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    existing_config[key] = value
    
    # Add OCR configuration
    ocr_config = {
        'BANK_OCR_ENABLED': existing_config.get('AI_ENABLED', 'true'),
        'BANK_OCR_TIMEOUT': '300',  # Default 5 minutes
        'BANK_OCR_MIN_TEXT_THRESHOLD': '50',
        'BANK_OCR_MIN_WORD_THRESHOLD': '10',
        'TESSERACT_CMD': '/usr/bin/tesseract',
        'TESSERACT_CONFIG': '--oem 3 --psm 6',
        'UNSTRUCTURED_STRATEGY': 'hi_res',
        'UNSTRUCTURED_MODE': 'single',
        'UNSTRUCTURED_USE_API': 'false',
        'OCR_MAX_CONCURRENT_JOBS': '2',
        'OCR_TEMP_DIR': '/tmp/ocr_processing',
        'OCR_CLEANUP_INTERVAL': '3600'
    }
    
    # Write updated configuration
    with open('.env', 'a') as f:
        f.write('\n# OCR Fallback Configuration (added during migration)\n')
        for key, value in ocr_config.items():
            if key not in existing_config:
                f.write(f'{key}={value}\n')
    
    print("OCR configuration added to .env")
    print("Please review and adjust settings as needed")

if __name__ == '__main__':
    migrate_configuration()
```

## Testing Migration

### Pre-Migration Testing

```bash
# Test current system with problematic documents
python test_current_system.py

# Document current performance
python benchmark_current_system.py
```

### Post-Migration Testing

```bash
# Test OCR functionality
python -c "
from settings.ocr_config import test_ocr_configuration
results = test_ocr_configuration()
print('OCR Test Results:', results)
"

# Test with sample documents
python test_ocr_migration.py

# Performance comparison
python benchmark_with_ocr.py
```

### Test Script Example

```python
#!/usr/bin/env python3
# test_ocr_migration.py

import os
import time
from services.enhanced_pdf_extractor import EnhancedPDFTextExtractor

def test_migration():
    """Test OCR migration with sample documents."""
    
    test_documents = [
        'samples/text_based_statement.pdf',
        'samples/scanned_statement.pdf',
        'samples/mixed_content_statement.pdf'
    ]
    
    extractor = EnhancedPDFTextExtractor()
    
    for doc_path in test_documents:
        if not os.path.exists(doc_path):
            print(f"Skipping {doc_path} - file not found")
            continue
        
        print(f"\nTesting {doc_path}:")
        start_time = time.time()
        
        try:
            text, method = extractor.extract_text(doc_path)
            processing_time = time.time() - start_time
            
            print(f"  Method: {method}")
            print(f"  Text length: {len(text)} characters")
            print(f"  Processing time: {processing_time:.2f} seconds")
            print(f"  Success: ✓")
            
        except Exception as e:
            print(f"  Error: {e}")
            print(f"  Success: ✗")

if __name__ == '__main__':
    test_migration()
```

## Rollback Procedures

### Quick Rollback (Disable OCR)

```bash
# Disable OCR without code changes
export BANK_OCR_ENABLED=false

# Restart application
sudo systemctl restart your-app

# Verify OCR is disabled
python -c "
from settings.ocr_config import is_ocr_available
print('OCR Available:', is_ocr_available())
"
```

### Full Rollback

```bash
# Stop application
sudo systemctl stop your-app

# Restore previous version
git checkout previous-version-tag

# Restore configuration
cp .env.backup.YYYYMMDD_HHMMSS .env

# Restore Python environment
pip install -r requirements.txt.backup

# Start application
sudo systemctl start your-app

# Verify rollback
curl -f http://localhost:8000/health
```

### Docker Rollback

```bash
# Rollback to previous image
docker-compose down
docker-compose up -d --scale api=0
docker tag your-registry/bank-statement-api:previous your-registry/bank-statement-api:latest
docker-compose up -d
```

## Post-Migration Monitoring

### Key Metrics to Monitor

1. **Processing Success Rate**
   ```bash
   # Monitor success rates
   grep -c "successfully processed" /var/log/app/app.log
   grep -c "processing failed" /var/log/app/app.log
   ```

2. **OCR Usage Statistics**
   ```bash
   # Monitor OCR fallback usage
   grep -c "falling back to OCR" /var/log/app/app.log
   grep -c "using pdf_loader" /var/log/app/app.log
   ```

3. **Performance Impact**
   ```bash
   # Monitor processing times
   grep "processing time" /var/log/app/app.log | awk '{print $NF}' | sort -n
   ```

4. **System Resources**
   ```bash
   # Monitor memory usage
   free -h
   
   # Monitor CPU usage
   top -bn1 | grep "Cpu(s)"
   
   # Monitor disk usage
   df -h /tmp/ocr_processing
   ```

### Monitoring Script

```bash
#!/bin/bash
# monitor_ocr_migration.sh

LOG_FILE="/var/log/app/app.log"
REPORT_FILE="ocr_migration_report.txt"

echo "OCR Migration Monitoring Report - $(date)" > $REPORT_FILE
echo "================================================" >> $REPORT_FILE

# Processing statistics
echo "Processing Statistics:" >> $REPORT_FILE
echo "  Total processes: $(grep -c 'bank statement' $LOG_FILE)" >> $REPORT_FILE
echo "  PDF loader used: $(grep -c 'using pdf_loader' $LOG_FILE)" >> $REPORT_FILE
echo "  OCR fallback used: $(grep -c 'falling back to OCR' $LOG_FILE)" >> $REPORT_FILE
echo "  Processing failures: $(grep -c 'processing failed' $LOG_FILE)" >> $REPORT_FILE

# Performance statistics
echo "Performance Statistics:" >> $REPORT_FILE
avg_time=$(grep "processing time" $LOG_FILE | awk '{print $NF}' | awk '{sum+=$1; count++} END {print sum/count}')
echo "  Average processing time: ${avg_time}s" >> $REPORT_FILE

# System resources
echo "System Resources:" >> $REPORT_FILE
echo "  Memory usage: $(free -h | grep Mem | awk '{print $3"/"$2}')" >> $REPORT_FILE
echo "  Disk usage (OCR temp): $(df -h /tmp/ocr_processing | tail -1 | awk '{print $3"/"$2" ("$5")"}')" >> $REPORT_FILE

# Recent errors
echo "Recent Errors:" >> $REPORT_FILE
tail -100 $LOG_FILE | grep -i error | tail -5 >> $REPORT_FILE

cat $REPORT_FILE
```

## Common Migration Issues

### Issue 1: Dependency Installation Failures

**Problem**: Tesseract installation fails on older systems.

**Solution**:
```bash
# For older Ubuntu/Debian systems
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:alex-p/tesseract-ocr-devel
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### Issue 2: Permission Issues After Migration

**Problem**: OCR processing fails with permission errors.

**Solution**:
```bash
# Fix permissions
sudo chown -R $USER:$USER /tmp/ocr_processing
sudo chmod -R 755 /tmp/ocr_processing

# Update systemd service if needed
sudo systemctl edit your-app
# Add:
# [Service]
# User=your-app-user
# Group=your-app-group
```

### Issue 3: Performance Degradation

**Problem**: System becomes slow after OCR migration.

**Solution**:
```bash
# Reduce OCR concurrency
export OCR_MAX_CONCURRENT_JOBS=1

# Use faster OCR strategy
export UNSTRUCTURED_STRATEGY=fast

# Increase system resources or add swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## Migration Checklist

### Pre-Migration
- [ ] System requirements verified
- [ ] Backup completed (database, configuration, attachments)
- [ ] Dependencies tested in staging environment
- [ ] Migration plan reviewed and approved
- [ ] Rollback procedure documented

### During Migration
- [ ] System dependencies installed
- [ ] Python dependencies updated
- [ ] Configuration updated
- [ ] Application code deployed
- [ ] OCR functionality validated
- [ ] System monitoring active

### Post-Migration
- [ ] OCR functionality tested with sample documents
- [ ] Performance metrics collected
- [ ] Error rates monitored
- [ ] User feedback collected
- [ ] Documentation updated
- [ ] Team trained on new functionality

## Support During Migration

### Migration Support Contacts

- **Technical Lead**: [Contact information]
- **System Administrator**: [Contact information]
- **Database Administrator**: [Contact information]

### Emergency Procedures

If critical issues occur during migration:

1. **Immediate Response**: Disable OCR (`BANK_OCR_ENABLED=false`)
2. **Escalation**: Contact technical lead
3. **Rollback**: Execute rollback procedure if necessary
4. **Communication**: Notify stakeholders of status

### Documentation Updates

After successful migration, update:

- [ ] System architecture documentation
- [ ] Operational procedures
- [ ] Monitoring runbooks
- [ ] User documentation
- [ ] Training materials

This migration guide ensures a smooth transition to OCR fallback functionality while maintaining system stability and performance.