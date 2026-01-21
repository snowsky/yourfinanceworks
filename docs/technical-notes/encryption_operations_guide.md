# Database Encryption Operations Guide

## Overview

This guide provides comprehensive operational procedures for managing the tenant database encryption system. It covers day-to-day operations, maintenance procedures, emergency responses, and troubleshooting.

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Daily Operations](#daily-operations)
3. [Key Management Procedures](#key-management-procedures)
4. [Monitoring and Alerting](#monitoring-and-alerting)
5. [Backup and Recovery](#backup-and-recovery)
6. [Emergency Procedures](#emergency-procedures)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Maintenance Procedures](#maintenance-procedures)

## System Architecture Overview

### Components

- **Encryption Service**: Core encryption/decryption functionality
- **Key Management Service**: Handles encryption key lifecycle
- **Key Vault Providers**: External key storage (AWS KMS, Azure Key Vault, HashiCorp Vault)
- **Monitoring Service**: Tracks encryption metrics and health
- **Alerting Service**: Sends notifications for encryption events

### Key Concepts

- **Master Key**: Root encryption key stored in external key vault
- **Data Encryption Keys (DEKs)**: Per-tenant keys for data encryption
- **Key Rotation**: Periodic replacement of encryption keys
- **Envelope Encryption**: Two-tier encryption architecture

## Daily Operations

### Health Checks

Perform these checks daily to ensure system health:

```bash
# Check encryption service status
curl -f http://localhost:8000/health/encryption

# Verify key vault connectivity
python -c "
from integrations.key_vault_factory import KeyVaultFactory
vault = KeyVaultFactory.create_key_vault()
print('Key vault connectivity:', vault.test_connection())
"

# Check encryption metrics
curl http://localhost:8000/metrics | grep encryption
```

### Log Review

Review encryption-related logs daily:

```bash
# Check for encryption errors
docker-compose logs api | grep -i "encryption.*error"

# Review key rotation logs
docker-compose logs api | grep -i "key.*rotation"

# Check monitoring alerts
docker-compose logs api | grep -i "encryption.*alert"
```

### Performance Monitoring

Monitor encryption performance metrics:

- Encryption/decryption latency
- Key retrieval times
- Cache hit rates
- Error rates

## Key Management Procedures

### Key Rotation

#### Scheduled Key Rotation

Automatic key rotation runs based on `KEY_ROTATION_INTERVAL_DAYS` setting.

To check rotation status:

```python
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

# Check rotation status for all tenants
status = rotation_service.get_rotation_status()
print(f"Tenants due for rotation: {len(status['due_for_rotation'])}")
```

#### Manual Key Rotation

To manually rotate keys for a specific tenant:

```python
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

# Rotate keys for tenant ID 123
tenant_id = 123
rotation_service.rotate_tenant_keys(tenant_id)
print(f"Key rotation completed for tenant {tenant_id}")
```

#### Emergency Key Rotation

In case of suspected key compromise:

1. **Immediate Response**:
   ```bash
   # Stop all application services
   docker-compose stop api ocr-worker
   
   # Rotate compromised keys
   python scripts/emergency_key_rotation.py --tenant-id <TENANT_ID>
   
   # Restart services
   docker-compose start api ocr-worker
   ```

2. **Verify Rotation**:
   ```python
   # Verify new keys are active
   from services.encryption_service import EncryptionService
   service = EncryptionService()
   
   # Test encryption with new keys
   test_data = "test-after-rotation"
   encrypted = service.encrypt_data(test_data, tenant_id)
   decrypted = service.decrypt_data(encrypted, tenant_id)
   assert decrypted == test_data
   ```

### Key Backup and Recovery

#### Backup Procedures

```bash
# Backup encryption keys (for local key vault)
mkdir -p /backup/encryption-keys/$(date +%Y%m%d)
cp -r /app/keys/* /backup/encryption-keys/$(date +%Y%m%d)/

# Backup key metadata
python scripts/backup_key_metadata.py --output /backup/key-metadata-$(date +%Y%m%d).json
```

#### Recovery Procedures

```bash
# Restore encryption keys
cp -r /backup/encryption-keys/YYYYMMDD/* /app/keys/

# Restore key metadata
python scripts/restore_key_metadata.py --input /backup/key-metadata-YYYYMMDD.json

# Verify restoration
python scripts/verify_key_integrity.py
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Encryption Performance**:
   - `encryption_operations_total`: Total encryption operations
   - `encryption_duration_seconds`: Encryption operation duration
   - `decryption_duration_seconds`: Decryption operation duration

2. **Key Management**:
   - `key_rotation_last_success`: Last successful key rotation timestamp
   - `key_vault_connectivity`: Key vault connection status
   - `active_keys_count`: Number of active encryption keys

3. **Error Rates**:
   - `encryption_errors_total`: Total encryption errors
   - `key_retrieval_errors_total`: Key retrieval failures
   - `key_rotation_failures_total`: Key rotation failures

### Alert Thresholds

Configure alerts for:

- Encryption error rate > 1%
- Key vault connectivity failures
- Key rotation overdue (> 7 days past schedule)
- Encryption latency > 100ms (95th percentile)

### Monitoring Dashboard

Access the monitoring dashboard at: `http://localhost:3000/dashboards/encryption`

Key panels:
- Encryption operations per second
- Error rate trends
- Key rotation status
- Performance metrics

## Backup and Recovery

### Encrypted Data Backup

```bash
# Create encrypted backup of tenant data
python scripts/create_encrypted_backup.py --tenant-id <TENANT_ID> --output /backup/

# Verify backup integrity
python scripts/verify_backup_integrity.py --backup-file /backup/tenant_<ID>_backup.enc
```

### Backup Encryption Keys

```bash
# Backup all encryption keys
python scripts/backup_encryption_keys.py --output /backup/keys/

# Test key backup restoration
python scripts/test_key_restoration.py --backup-dir /backup/keys/
```

### Recovery Procedures

#### Full System Recovery

1. **Restore Infrastructure**:
   ```bash
   # Deploy application infrastructure
   ./scripts/deploy_with_encryption.sh production
   ```

2. **Restore Encryption Keys**:
   ```bash
   # Restore master keys
   python scripts/restore_master_keys.py --backup-dir /backup/keys/
   
   # Restore tenant keys
   python scripts/restore_tenant_keys.py --backup-dir /backup/keys/
   ```

3. **Restore Encrypted Data**:
   ```bash
   # Restore tenant databases
   python scripts/restore_encrypted_data.py --backup-dir /backup/data/
   ```

4. **Verify Recovery**:
   ```bash
   # Test encryption functionality
   python scripts/test_encryption_recovery.py
   ```

#### Partial Recovery (Single Tenant)

```bash
# Restore specific tenant
python scripts/restore_tenant.py --tenant-id <TENANT_ID> --backup-dir /backup/

# Verify tenant data integrity
python scripts/verify_tenant_data.py --tenant-id <TENANT_ID>
```

## Emergency Procedures

### Encryption Service Failure

1. **Immediate Response**:
   ```bash
   # Check service status
   docker-compose ps api
   
   # Check logs for errors
   docker-compose logs api | tail -100
   
   # Restart encryption service
   docker-compose restart api
   ```

2. **If Restart Fails**:
   ```bash
   # Disable encryption temporarily (emergency only)
   export ENCRYPTION_ENABLED=false
   docker-compose up -d api
   
   # Alert operations team
   python scripts/send_emergency_alert.py --message "Encryption service failure"
   ```

### Key Vault Connectivity Loss

1. **Switch to Backup Key Vault**:
   ```bash
   # Update configuration to backup vault
   export KEY_VAULT_PROVIDER=backup_vault
   export VAULT_URL=https://backup-vault.example.com
   
   # Restart services
   docker-compose restart api ocr-worker
   ```

2. **Verify Connectivity**:
   ```python
   from integrations.key_vault_factory import KeyVaultFactory
   vault = KeyVaultFactory.create_key_vault()
   assert vault.test_connection(), "Backup vault connection failed"
   ```

### Data Corruption Detection

1. **Immediate Actions**:
   ```bash
   # Stop data modifications
   docker-compose stop api ocr-worker
   
   # Create emergency backup
   python scripts/emergency_backup.py --all-tenants
   ```

2. **Assess Damage**:
   ```python
   # Check data integrity
   python scripts/check_data_integrity.py --all-tenants
   
   # Identify affected tenants
   python scripts/identify_corrupted_data.py
   ```

3. **Recovery**:
   ```bash
   # Restore from last known good backup
   python scripts/restore_from_backup.py --timestamp <LAST_GOOD_BACKUP>
   ```

## Troubleshooting Guide

### Common Issues

#### Issue: Encryption Operations Failing

**Symptoms**:
- HTTP 500 errors on API endpoints
- "Encryption failed" in logs
- High error rates in metrics

**Diagnosis**:
```bash
# Check encryption service logs
docker-compose logs api | grep -i encryption

# Test encryption manually
python -c "
from services.encryption_service import EncryptionService
service = EncryptionService()
try:
    result = service.encrypt_data('test', 1)
    print('Encryption working:', bool(result))
except Exception as e:
    print('Encryption error:', e)
"
```

**Resolution**:
1. Check key vault connectivity
2. Verify encryption configuration
3. Restart encryption service
4. Check for key expiration

#### Issue: Key Rotation Failures

**Symptoms**:
- "Key rotation failed" alerts
- Overdue key rotation warnings
- Authentication errors with key vault

**Diagnosis**:
```python
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

# Check rotation status
status = rotation_service.get_rotation_status()
print("Rotation status:", status)
```

**Resolution**:
1. Verify key vault permissions
2. Check rotation schedule configuration
3. Manually trigger rotation for failed tenants
4. Update key vault credentials if expired

#### Issue: Performance Degradation

**Symptoms**:
- Slow API responses
- High encryption latency
- Timeout errors

**Diagnosis**:
```bash
# Check encryption metrics
curl http://localhost:8000/metrics | grep encryption_duration

# Monitor key cache performance
curl http://localhost:8000/metrics | grep key_cache
```

**Resolution**:
1. Increase key cache TTL
2. Optimize key retrieval batch size
3. Scale encryption service instances
4. Review key vault performance

### Diagnostic Commands

```bash
# Test encryption end-to-end
python scripts/test_encryption_e2e.py

# Verify key vault connectivity
python scripts/test_key_vault_connection.py

# Check encryption configuration
python scripts/validate_encryption_config.py

# Monitor encryption performance
python scripts/monitor_encryption_performance.py --duration 300
```

## Maintenance Procedures

### Weekly Maintenance

1. **Review Metrics**:
   - Check encryption performance trends
   - Review error rates and patterns
   - Verify key rotation schedules

2. **Update Documentation**:
   - Update operational logs
   - Review and update procedures
   - Document any configuration changes

3. **Test Procedures**:
   - Test backup and recovery procedures
   - Verify emergency response procedures
   - Test monitoring and alerting

### Monthly Maintenance

1. **Security Review**:
   - Review access logs
   - Audit key vault permissions
   - Check for security updates

2. **Performance Optimization**:
   - Analyze performance metrics
   - Optimize configuration parameters
   - Review capacity planning

3. **Disaster Recovery Testing**:
   - Test full system recovery
   - Verify backup integrity
   - Update recovery procedures

### Quarterly Maintenance

1. **Security Audit**:
   - Comprehensive security review
   - Penetration testing
   - Compliance verification

2. **Capacity Planning**:
   - Review growth trends
   - Plan infrastructure scaling
   - Update resource allocations

3. **Documentation Review**:
   - Update all operational procedures
   - Review and update emergency contacts
   - Validate all runbooks

## Contact Information

### Emergency Contacts

- **Operations Team**: ops@company.com
- **Security Team**: security@company.com
- **On-Call Engineer**: +1-555-0123

### Escalation Procedures

1. **Level 1**: Operations team member
2. **Level 2**: Senior operations engineer
3. **Level 3**: Security team and engineering manager
4. **Level 4**: CTO and executive team

## Appendix

### Configuration Reference

See `api/.env.encryption.example` for complete configuration options.

### API Reference

See `api/docs/encryption_api.md` for encryption API documentation.

### Monitoring Queries

See `api/docs/encryption_monitoring_queries.md` for monitoring query examples.