# Encryption System Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting procedures for the tenant database encryption system. It covers common issues, diagnostic procedures, and resolution steps.

## Table of Contents

1. [Common Issues and Solutions](#common-issues-and-solutions)
2. [Diagnostic Procedures](#diagnostic-procedures)
3. [Performance Issues](#performance-issues)
4. [Key Management Issues](#key-management-issues)
5. [Integration Issues](#integration-issues)
6. [Emergency Troubleshooting](#emergency-troubleshooting)
7. [Monitoring and Alerting Issues](#monitoring-and-alerting-issues)

## Common Issues and Solutions

### Issue 1: Encryption Service Not Starting

**Symptoms:**
- API service fails to start
- "Encryption initialization failed" in logs
- HTTP 500 errors on all endpoints

**Diagnostic Steps:**
```bash
# Check service status
docker-compose ps api

# Check logs for encryption errors
docker-compose logs api | grep -i encryption | tail -20

# Test encryption configuration
python scripts/validate_encryption_config.py
```

**Common Causes and Solutions:**

#### Cause: Missing Environment Variables
```bash
# Check required environment variables
env | grep -E "(ENCRYPTION|KEY_VAULT|MASTER_KEY)"

# Solution: Set missing variables
export ENCRYPTION_ENABLED=true
export KEY_VAULT_PROVIDER=local
export MASTER_KEY_ID=default-master-key
```

#### Cause: Key Vault Connectivity Issues
```python
# Test key vault connection
from integrations.key_vault_factory import KeyVaultFactory

try:
    vault = KeyVaultFactory.create_key_vault()
    result = vault.test_connection()
    print(f"Key vault connection: {'OK' if result else 'FAILED'}")
except Exception as e:
    print(f"Key vault error: {e}")
```

**Solution:**
```bash
# For AWS KMS issues
aws sts get-caller-identity  # Verify AWS credentials
aws kms describe-key --key-id $AWS_KMS_KEY_ID  # Verify key access

# For Azure Key Vault issues
az account show  # Verify Azure login
az keyvault key show --vault-name $AZURE_KEY_VAULT_NAME --name $AZURE_KEY_VAULT_KEY_NAME

# For HashiCorp Vault issues
vault auth -method=token token=$VAULT_TOKEN
vault kv get $VAULT_MOUNT_PATH/$VAULT_KEY_PATH
```

#### Cause: Missing Master Key
```python
# Check if master key exists
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

if not key_mgmt.master_key_exists():
    print("Master key missing - generating new key")
    key_mgmt.generate_master_key()
else:
    print("Master key exists")
```

### Issue 2: Encryption Operations Failing

**Symptoms:**
- "Encryption failed" errors in logs
- Data not being encrypted/decrypted properly
- Intermittent encryption failures

**Diagnostic Steps:**
```python
# Test basic encryption functionality
from services.encryption_service import EncryptionService

service = EncryptionService()
test_data = "test-encryption-data"
tenant_id = 1

try:
    # Test encryption
    encrypted = service.encrypt_data(test_data, tenant_id)
    print(f"Encryption successful: {bool(encrypted)}")
    
    # Test decryption
    decrypted = service.decrypt_data(encrypted, tenant_id)
    print(f"Decryption successful: {decrypted == test_data}")
    
except Exception as e:
    print(f"Encryption test failed: {e}")
```

**Common Causes and Solutions:**

#### Cause: Tenant Key Missing
```python
# Check if tenant has encryption keys
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

tenant_id = 1  # Replace with actual tenant ID
if not key_mgmt.tenant_key_exists(tenant_id):
    print(f"Generating keys for tenant {tenant_id}")
    key_mgmt.generate_tenant_keys(tenant_id)
```

#### Cause: Key Cache Issues
```bash
# Clear key cache
redis-cli FLUSHDB  # If using Redis for caching

# Or restart service to clear in-memory cache
docker-compose restart api
```

#### Cause: Corrupted Keys
```python
# Verify key integrity
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

# Test key integrity for all tenants
tenant_ids = key_mgmt.get_all_tenant_ids()
for tenant_id in tenant_ids:
    try:
        key_mgmt.verify_tenant_keys(tenant_id)
        print(f"Tenant {tenant_id}: Keys OK")
    except Exception as e:
        print(f"Tenant {tenant_id}: Key corruption detected - {e}")
        # Regenerate corrupted keys
        key_mgmt.regenerate_tenant_keys(tenant_id)
```

### Issue 3: Key Rotation Failures

**Symptoms:**
- "Key rotation failed" alerts
- Overdue key rotation warnings
- Some tenants unable to decrypt data after rotation

**Diagnostic Steps:**
```python
# Check rotation status
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

status = rotation_service.get_rotation_status()
print(f"Due for rotation: {len(status['due_for_rotation'])}")
print(f"Overdue: {len(status['overdue'])}")
print(f"Failed rotations: {len(status['failed'])}")
```

**Common Causes and Solutions:**

#### Cause: Insufficient Key Vault Permissions
```bash
# Check key vault permissions
# For AWS KMS
aws kms get-key-policy --key-id $AWS_KMS_KEY_ID --policy-name default

# For Azure Key Vault
az keyvault show --name $AZURE_KEY_VAULT_NAME --query properties.accessPolicies

# Solution: Update permissions
python scripts/update_key_vault_permissions.py
```

#### Cause: Database Lock During Rotation
```python
# Check for long-running transactions
from sqlalchemy import text
from database import get_db

db = next(get_db())
result = db.execute(text("""
    SELECT pid, state, query_start, query 
    FROM pg_stat_activity 
    WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes'
"""))

for row in result:
    print(f"Long-running query: PID {row.pid}, Started: {row.query_start}")
    print(f"Query: {row.query[:100]}...")
```

**Solution:**
```bash
# Kill long-running queries if safe
# Be very careful with this command
sudo -u postgres psql -c "SELECT pg_terminate_backend(PID);"

# Or wait for queries to complete and retry rotation
python scripts/retry_failed_rotations.py
```

### Issue 4: Performance Degradation

**Symptoms:**
- Slow API responses
- High encryption/decryption latency
- Timeout errors

**Diagnostic Steps:**
```bash
# Check encryption performance metrics
curl http://localhost:8000/metrics | grep encryption_duration

# Monitor system resources
docker stats api --no-stream

# Check key cache hit rate
curl http://localhost:8000/metrics | grep key_cache_hit_rate
```

**Common Causes and Solutions:**

#### Cause: Low Key Cache Hit Rate
```python
# Check cache configuration
from config.encryption_config import EncryptionConfig

print(f"Cache TTL: {EncryptionConfig.KEY_CACHE_TTL}")
print(f"Cache size: {EncryptionConfig.KEY_CACHE_SIZE}")

# Increase cache TTL if appropriate
export ENCRYPTION_KEY_CACHE_TTL=7200  # 2 hours
docker-compose restart api
```

#### Cause: Key Vault Latency
```python
# Test key vault response times
import time
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()

# Test key retrieval time
start_time = time.time()
vault.get_key("test-key-id")
retrieval_time = time.time() - start_time

print(f"Key retrieval time: {retrieval_time:.3f} seconds")

if retrieval_time > 0.1:  # 100ms threshold
    print("WARNING: High key vault latency detected")
```

**Solution:**
```bash
# Switch to backup key vault if primary is slow
export KEY_VAULT_PROVIDER=backup_vault
docker-compose restart api

# Or optimize key vault configuration
python scripts/optimize_key_vault_config.py
```

## Diagnostic Procedures

### Comprehensive System Health Check

```python
#!/usr/bin/env python3
"""
Comprehensive encryption system health check
"""

import time
import json
from datetime import datetime
from services.encryption_service import EncryptionService
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

def health_check():
    """Perform comprehensive health check."""
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': 'UNKNOWN',
        'checks': {}
    }
    
    # Check 1: Service availability
    try:
        service = EncryptionService()
        results['checks']['service_availability'] = {
            'status': 'PASS',
            'message': 'Encryption service is available'
        }
    except Exception as e:
        results['checks']['service_availability'] = {
            'status': 'FAIL',
            'message': f'Encryption service unavailable: {e}'
        }
    
    # Check 2: Key vault connectivity
    try:
        vault = KeyVaultFactory.create_key_vault()
        vault_ok = vault.test_connection()
        results['checks']['key_vault_connectivity'] = {
            'status': 'PASS' if vault_ok else 'FAIL',
            'message': 'Key vault connectivity OK' if vault_ok else 'Key vault connectivity failed'
        }
    except Exception as e:
        results['checks']['key_vault_connectivity'] = {
            'status': 'FAIL',
            'message': f'Key vault error: {e}'
        }
    
    # Check 3: Master key availability
    try:
        key_mgmt = KeyManagementService(vault)
        master_key_ok = key_mgmt.master_key_exists()
        results['checks']['master_key'] = {
            'status': 'PASS' if master_key_ok else 'FAIL',
            'message': 'Master key available' if master_key_ok else 'Master key missing'
        }
    except Exception as e:
        results['checks']['master_key'] = {
            'status': 'FAIL',
            'message': f'Master key check failed: {e}'
        }
    
    # Check 4: Encryption performance
    try:
        start_time = time.time()
        test_data = "performance-test-data"
        encrypted = service.encrypt_data(test_data, 1)
        decrypted = service.decrypt_data(encrypted, 1)
        duration = time.time() - start_time
        
        performance_ok = duration < 0.1 and decrypted == test_data
        results['checks']['encryption_performance'] = {
            'status': 'PASS' if performance_ok else 'WARN',
            'message': f'Encryption round-trip: {duration:.3f}s',
            'duration': duration
        }
    except Exception as e:
        results['checks']['encryption_performance'] = {
            'status': 'FAIL',
            'message': f'Performance test failed: {e}'
        }
    
    # Check 5: Key rotation status
    try:
        rotation_service = KeyRotationService(vault)
        rotation_status = rotation_service.get_rotation_status()
        
        overdue_count = len(rotation_status.get('overdue', []))
        rotation_ok = overdue_count == 0
        
        results['checks']['key_rotation'] = {
            'status': 'PASS' if rotation_ok else 'WARN',
            'message': f'Overdue rotations: {overdue_count}',
            'overdue_count': overdue_count
        }
    except Exception as e:
        results['checks']['key_rotation'] = {
            'status': 'FAIL',
            'message': f'Rotation status check failed: {e}'
        }
    
    # Determine overall status
    statuses = [check['status'] for check in results['checks'].values()]
    if 'FAIL' in statuses:
        results['overall_status'] = 'FAIL'
    elif 'WARN' in statuses:
        results['overall_status'] = 'WARN'
    else:
        results['overall_status'] = 'PASS'
    
    return results

def generate_health_report():
    """Generate and save health report."""
    
    results = health_check()
    
    # Save detailed report
    report_file = f"/var/log/encryption_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print(f"Encryption System Health Check - {results['overall_status']}")
    print(f"Report saved to: {report_file}")
    
    for check_name, check_result in results['checks'].items():
        status_icon = "✓" if check_result['status'] == 'PASS' else "⚠" if check_result['status'] == 'WARN' else "✗"
        print(f"{status_icon} {check_name}: {check_result['message']}")
    
    return results

if __name__ == "__main__":
    generate_health_report()
```

### Log Analysis Tools

```bash
#!/bin/bash
# Encryption log analysis script

LOG_FILE="/var/log/encryption.log"
ANALYSIS_PERIOD="${1:-24h}"  # Default to last 24 hours

echo "Analyzing encryption logs for the last $ANALYSIS_PERIOD"

# Error analysis
echo "=== ERROR ANALYSIS ==="
grep -i error "$LOG_FILE" | tail -20

# Performance analysis
echo "=== PERFORMANCE ANALYSIS ==="
grep "encryption_duration" "$LOG_FILE" | awk '{print $NF}' | sort -n | tail -10

# Key rotation analysis
echo "=== KEY ROTATION ANALYSIS ==="
grep -i "key.*rotation" "$LOG_FILE" | tail -10

# Alert analysis
echo "=== ALERT ANALYSIS ==="
grep -i alert "$LOG_FILE" | tail -10

# Generate summary report
echo "=== SUMMARY ==="
echo "Total log entries: $(wc -l < "$LOG_FILE")"
echo "Error entries: $(grep -c -i error "$LOG_FILE")"
echo "Warning entries: $(grep -c -i warn "$LOG_FILE")"
echo "Key rotation events: $(grep -c -i "key.*rotation" "$LOG_FILE")"
```

## Performance Issues

### High Encryption Latency

**Diagnosis:**
```python
# Measure encryption performance
import time
from services.encryption_service import EncryptionService

service = EncryptionService()
test_sizes = [100, 1000, 10000, 100000]  # bytes

for size in test_sizes:
    test_data = "x" * size
    
    start_time = time.time()
    encrypted = service.encrypt_data(test_data, 1)
    encryption_time = time.time() - start_time
    
    start_time = time.time()
    decrypted = service.decrypt_data(encrypted, 1)
    decryption_time = time.time() - start_time
    
    print(f"Size: {size} bytes")
    print(f"  Encryption: {encryption_time:.3f}s ({size/encryption_time:.0f} bytes/s)")
    print(f"  Decryption: {decryption_time:.3f}s ({size/decryption_time:.0f} bytes/s)")
```

**Solutions:**

1. **Optimize Key Caching:**
```python
# Increase cache size and TTL
export ENCRYPTION_KEY_CACHE_SIZE=10000
export ENCRYPTION_KEY_CACHE_TTL=3600
```

2. **Batch Operations:**
```python
# Use batch encryption for multiple records
from services.encryption_service import EncryptionService

service = EncryptionService()
data_batch = ["data1", "data2", "data3"]
encrypted_batch = service.encrypt_batch(data_batch, tenant_id=1)
```

3. **Async Processing:**
```python
# Use async encryption for non-blocking operations
import asyncio
from services.async_encryption_service import AsyncEncryptionService

async def encrypt_async():
    service = AsyncEncryptionService()
    result = await service.encrypt_data_async("test-data", 1)
    return result
```

### Memory Usage Issues

**Diagnosis:**
```bash
# Monitor memory usage
docker stats api --no-stream

# Check for memory leaks
python scripts/memory_profiler.py
```

**Solutions:**

1. **Optimize Key Cache:**
```python
# Implement LRU cache with size limits
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_key(tenant_id):
    # Key retrieval logic
    pass
```

2. **Garbage Collection:**
```python
# Force garbage collection after batch operations
import gc

def process_large_batch():
    # Process data
    pass
    # Force cleanup
    gc.collect()
```

## Key Management Issues

### Key Corruption Detection and Recovery

**Detection:**
```python
# Detect corrupted keys
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

def detect_key_corruption():
    """Detect corrupted encryption keys."""
    
    corrupted_tenants = []
    tenant_ids = key_mgmt.get_all_tenant_ids()
    
    for tenant_id in tenant_ids:
        try:
            # Test key by encrypting/decrypting test data
            test_data = f"corruption-test-{tenant_id}"
            encrypted = service.encrypt_data(test_data, tenant_id)
            decrypted = service.decrypt_data(encrypted, tenant_id)
            
            if decrypted != test_data:
                corrupted_tenants.append(tenant_id)
                
        except Exception as e:
            print(f"Tenant {tenant_id}: Key corruption detected - {e}")
            corrupted_tenants.append(tenant_id)
    
    return corrupted_tenants

corrupted = detect_key_corruption()
if corrupted:
    print(f"Corrupted keys detected for tenants: {corrupted}")
```

**Recovery:**
```python
# Recover corrupted keys
def recover_corrupted_keys(tenant_ids):
    """Recover corrupted keys for specified tenants."""
    
    for tenant_id in tenant_ids:
        try:
            # Backup existing data before key regeneration
            backup_service.backup_tenant_data(tenant_id)
            
            # Regenerate keys
            key_mgmt.regenerate_tenant_keys(tenant_id)
            
            # Re-encrypt existing data with new keys
            reencrypt_tenant_data(tenant_id)
            
            print(f"Tenant {tenant_id}: Key recovery completed")
            
        except Exception as e:
            print(f"Tenant {tenant_id}: Key recovery failed - {e}")
```

### Key Synchronization Issues

**Diagnosis:**
```python
# Check key synchronization across services
def check_key_synchronization():
    """Check if keys are synchronized across all services."""
    
    services = ['api', 'ocr-worker', 'background-tasks']
    tenant_id = 1
    
    key_versions = {}
    
    for service in services:
        try:
            # Get key version from each service
            key_version = get_key_version_from_service(service, tenant_id)
            key_versions[service] = key_version
        except Exception as e:
            print(f"Failed to get key version from {service}: {e}")
    
    # Check if all versions match
    versions = list(key_versions.values())
    if len(set(versions)) > 1:
        print(f"Key synchronization issue detected: {key_versions}")
        return False
    
    return True
```

**Solution:**
```bash
# Force key synchronization
python scripts/synchronize_keys.py --all-services

# Restart all services to reload keys
docker-compose restart api ocr-worker
```

## Integration Issues

### AWS KMS Integration Issues

**Common Issues:**

1. **Authentication Failures:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Test KMS access
aws kms describe-key --key-id $AWS_KMS_KEY_ID
```

2. **Permission Issues:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:user/encryption-service"
      },
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey"
      ],
      "Resource": "*"
    }
  ]
}
```

3. **Rate Limiting:**
```python
# Implement exponential backoff
import time
import random

def kms_operation_with_retry(operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return operation()
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### Azure Key Vault Integration Issues

**Common Issues:**

1. **Authentication:**
```bash
# Check Azure authentication
az account show

# Test Key Vault access
az keyvault key show --vault-name $AZURE_KEY_VAULT_NAME --name $AZURE_KEY_VAULT_KEY_NAME
```

2. **Network Access:**
```python
# Test network connectivity
import requests

vault_url = os.getenv('AZURE_KEY_VAULT_URL')
response = requests.get(f"{vault_url}/keys?api-version=7.3")
print(f"Network connectivity: {response.status_code}")
```

### HashiCorp Vault Integration Issues

**Common Issues:**

1. **Token Expiration:**
```bash
# Check token status
vault token lookup

# Renew token if needed
vault token renew
```

2. **Policy Issues:**
```hcl
# Required Vault policy
path "secret/encryption-keys/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

## Emergency Troubleshooting

### Complete System Failure

**Emergency Response Checklist:**

1. **Immediate Assessment:**
```bash
# Check all services
docker-compose ps

# Check system resources
df -h
free -h
```

2. **Service Recovery:**
```bash
# Stop all services
docker-compose down

# Check for corrupted containers
docker system prune -f

# Restart with fresh containers
docker-compose up -d --force-recreate
```

3. **Data Integrity Check:**
```python
# Verify data integrity after recovery
python scripts/verify_data_integrity.py --all-tenants
```

### Data Recovery Emergency

**When Encrypted Data Cannot Be Decrypted:**

1. **Immediate Actions:**
```bash
# Stop all write operations
docker-compose stop api ocr-worker

# Create emergency backup
python scripts/emergency_backup.py --raw-data
```

2. **Key Recovery Attempts:**
```python
# Try backup keys
python scripts/try_backup_keys.py --tenant-id $TENANT_ID

# Try key vault recovery
python scripts/recover_from_key_vault.py --tenant-id $TENANT_ID
```

3. **Last Resort - Restore from Backup:**
```bash
# Restore from last known good backup
python scripts/restore_from_backup.py --timestamp $LAST_GOOD_BACKUP
```

## Monitoring and Alerting Issues

### Missing Alerts

**Check Alert Configuration:**
```python
# Verify alert rules
from services.encryption_alerting_service import EncryptionAlertingService

alerting = EncryptionAlertingService()
rules = alerting.get_alert_rules()

for rule in rules:
    print(f"Rule: {rule['name']}, Enabled: {rule['enabled']}")
```

**Test Alert Delivery:**
```python
# Test alert delivery
alerting.send_test_alert("Test encryption alert")
```

### Metric Collection Issues

**Check Metrics Endpoint:**
```bash
# Test metrics endpoint
curl http://localhost:8000/metrics | grep encryption

# Check metric collection service
docker-compose logs prometheus
```

**Verify Metric Labels:**
```python
# Check metric labels
from services.encryption_monitoring_service import EncryptionMonitoringService

monitoring = EncryptionMonitoringService()
metrics = monitoring.get_current_metrics()

for metric_name, metric_value in metrics.items():
    print(f"{metric_name}: {metric_value}")
```

This troubleshooting guide provides comprehensive procedures for diagnosing and resolving encryption system issues, ensuring minimal downtime and data protection.