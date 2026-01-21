# Encryption System Runbooks

## Overview

This document contains step-by-step runbooks for critical encryption system operations. Each runbook provides detailed procedures that can be executed by operations staff during normal operations or emergency situations.

## Table of Contents

1. [Key Rotation Runbook](#key-rotation-runbook)
2. [Emergency Key Compromise Response](#emergency-key-compromise-response)
3. [Encryption Service Recovery](#encryption-service-recovery)
4. [Key Vault Failover](#key-vault-failover)
5. [Data Recovery from Encrypted Backups](#data-recovery-from-encrypted-backups)
6. [New Tenant Encryption Setup](#new-tenant-encryption-setup)
7. [Encryption System Health Check](#encryption-system-health-check)

---

## Key Rotation Runbook

### Purpose
Perform scheduled or manual key rotation for tenant encryption keys.

### Prerequisites
- Access to production environment
- Key vault credentials
- Database access

### Procedure

#### Step 1: Pre-rotation Checks
```bash
# 1.1 Check current system health
curl -f http://localhost:8000/health/encryption
if [ $? -ne 0 ]; then
    echo "ERROR: Encryption service unhealthy. Abort rotation."
    exit 1
fi

# 1.2 Verify key vault connectivity
python -c "
from integrations.key_vault_factory import KeyVaultFactory
vault = KeyVaultFactory.create_key_vault()
if not vault.test_connection():
    print('ERROR: Key vault connectivity failed')
    exit(1)
print('Key vault connectivity: OK')
"

# 1.3 Create backup before rotation
python scripts/backup_encryption_keys.py --output /backup/pre-rotation-$(date +%Y%m%d-%H%M%S)
```

#### Step 2: Identify Tenants for Rotation
```python
# 2.1 Check rotation schedule
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

status = rotation_service.get_rotation_status()
print(f"Tenants due for rotation: {len(status['due_for_rotation'])}")
print(f"Overdue tenants: {len(status['overdue'])}")

# 2.2 List specific tenants
for tenant_id in status['due_for_rotation']:
    print(f"Tenant {tenant_id}: Due for rotation")
```

#### Step 3: Perform Rotation
```bash
# 3.1 For scheduled rotation (all due tenants)
python scripts/rotate_scheduled_keys.py --dry-run
# Review output, then execute:
python scripts/rotate_scheduled_keys.py --execute

# 3.2 For specific tenant rotation
python scripts/rotate_tenant_keys.py --tenant-id <TENANT_ID> --dry-run
# Review output, then execute:
python scripts/rotate_tenant_keys.py --tenant-id <TENANT_ID> --execute
```

#### Step 4: Verify Rotation
```python
# 4.1 Test encryption with new keys
from services.encryption_service import EncryptionService

service = EncryptionService()
test_data = "rotation-test-data"

# Test for each rotated tenant
for tenant_id in rotated_tenants:
    try:
        encrypted = service.encrypt_data(test_data, tenant_id)
        decrypted = service.decrypt_data(encrypted, tenant_id)
        assert decrypted == test_data
        print(f"Tenant {tenant_id}: Rotation verified")
    except Exception as e:
        print(f"ERROR: Tenant {tenant_id} rotation failed: {e}")
```

#### Step 5: Post-rotation Tasks
```bash
# 5.1 Update rotation logs
python scripts/log_rotation_completion.py --tenants <TENANT_IDS>

# 5.2 Clean up old keys (after verification period)
# Wait 24-48 hours before cleanup
python scripts/cleanup_old_keys.py --older-than 48h --dry-run
```

### Rollback Procedure
If rotation fails:
```bash
# 1. Stop application services
docker-compose stop api ocr-worker

# 2. Restore previous keys
python scripts/restore_encryption_keys.py --backup-dir /backup/pre-rotation-TIMESTAMP

# 3. Restart services
docker-compose start api ocr-worker

# 4. Verify rollback
python scripts/test_encryption_functionality.py
```

---

## Emergency Key Compromise Response

### Purpose
Respond to suspected or confirmed encryption key compromise.

### Prerequisites
- Incident response team activated
- Emergency access credentials
- Communication channels established

### Procedure

#### Step 1: Immediate Response (0-15 minutes)
```bash
# 1.1 Alert security team
python scripts/send_security_alert.py --severity CRITICAL --message "Key compromise suspected"

# 1.2 Stop all data processing
docker-compose stop api ocr-worker

# 1.3 Create emergency backup
python scripts/emergency_backup.py --all-tenants --output /emergency-backup/$(date +%Y%m%d-%H%M%S)

# 1.4 Document incident
echo "$(date): Key compromise response initiated" >> /var/log/security-incidents.log
```

#### Step 2: Assess Compromise Scope (15-30 minutes)
```python
# 2.1 Identify potentially compromised keys
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

# Check key access logs
compromised_keys = key_mgmt.identify_suspicious_access()
print(f"Potentially compromised keys: {compromised_keys}")

# 2.2 Identify affected tenants
affected_tenants = []
for key_id in compromised_keys:
    tenants = key_mgmt.get_tenants_for_key(key_id)
    affected_tenants.extend(tenants)

print(f"Affected tenants: {set(affected_tenants)}")
```

#### Step 3: Emergency Key Rotation (30-60 minutes)
```bash
# 3.1 Generate new master key
python scripts/emergency_master_key_rotation.py --force

# 3.2 Rotate all potentially compromised tenant keys
for tenant_id in affected_tenants; do
    python scripts/emergency_tenant_key_rotation.py --tenant-id $tenant_id --force
done

# 3.3 Verify new keys are active
python scripts/verify_emergency_rotation.py --tenants $(echo $affected_tenants | tr ' ' ',')
```

#### Step 4: System Recovery (60-90 minutes)
```bash
# 4.1 Update key vault access policies
python scripts/update_key_vault_policies.py --revoke-compromised --apply-new

# 4.2 Restart services with new keys
docker-compose start api ocr-worker

# 4.3 Verify system functionality
python scripts/test_full_system_functionality.py
```

#### Step 5: Post-Incident Actions
```bash
# 5.1 Audit all key access
python scripts/audit_key_access.py --since "24 hours ago" --output /audit/key-access-audit.json

# 5.2 Update security monitoring
python scripts/enhance_security_monitoring.py --based-on-incident

# 5.3 Document lessons learned
python scripts/generate_incident_report.py --incident-id $(date +%Y%m%d-%H%M%S)
```

---

## Encryption Service Recovery

### Purpose
Recover encryption service from failure or corruption.

### Prerequisites
- Service monitoring alerts
- Access to logs and metrics
- Backup availability

### Procedure

#### Step 1: Assess Service Status
```bash
# 1.1 Check service health
docker-compose ps api
curl -f http://localhost:8000/health/encryption || echo "Service unhealthy"

# 1.2 Review recent logs
docker-compose logs api --since 1h | grep -i encryption

# 1.3 Check resource usage
docker stats api --no-stream
```

#### Step 2: Attempt Service Restart
```bash
# 2.1 Graceful restart
docker-compose restart api

# 2.2 Wait for startup
sleep 30

# 2.3 Test functionality
python scripts/test_encryption_basic.py
```

#### Step 3: If Restart Fails - Investigate
```bash
# 3.1 Check configuration
python scripts/validate_encryption_config.py

# 3.2 Test key vault connectivity
python scripts/test_key_vault_connection.py

# 3.3 Check database connectivity
python scripts/test_database_connection.py
```

#### Step 4: Recovery Actions
```bash
# 4.1 If configuration issue
cp api/.env.encryption.production api/.env.encryption
docker-compose restart api

# 4.2 If key vault issue
export KEY_VAULT_PROVIDER=backup_vault
docker-compose restart api

# 4.3 If database issue
python scripts/repair_encryption_tables.py
docker-compose restart api
```

#### Step 5: Verify Recovery
```python
# 5.1 Test all encryption operations
from services.encryption_service import EncryptionService

service = EncryptionService()
test_cases = [
    ("test-data-1", 1),
    ("test-data-2", 2),
    ("special-chars-!@#$%", 3)
]

for data, tenant_id in test_cases:
    try:
        encrypted = service.encrypt_data(data, tenant_id)
        decrypted = service.decrypt_data(encrypted, tenant_id)
        assert decrypted == data
        print(f"Tenant {tenant_id}: OK")
    except Exception as e:
        print(f"Tenant {tenant_id}: FAILED - {e}")
```

---

## Key Vault Failover

### Purpose
Switch to backup key vault when primary vault is unavailable.

### Prerequisites
- Backup key vault configured
- Failover credentials available
- Monitoring alerts active

### Procedure

#### Step 1: Detect Primary Vault Failure
```bash
# 1.1 Test primary vault connectivity
python -c "
from integrations.key_vault_factory import KeyVaultFactory
import os

# Test primary vault
os.environ['KEY_VAULT_PROVIDER'] = 'primary_vault'
try:
    vault = KeyVaultFactory.create_key_vault()
    vault.test_connection()
    print('Primary vault: OK')
except Exception as e:
    print(f'Primary vault: FAILED - {e}')
"
```

#### Step 2: Prepare for Failover
```bash
# 2.1 Create backup of current state
python scripts/backup_current_state.py --output /backup/pre-failover-$(date +%Y%m%d-%H%M%S)

# 2.2 Verify backup vault availability
export KEY_VAULT_PROVIDER=backup_vault
python scripts/test_key_vault_connection.py
```

#### Step 3: Execute Failover
```bash
# 3.1 Stop services
docker-compose stop api ocr-worker

# 3.2 Update configuration for backup vault
cp api/.env.encryption.backup api/.env.encryption

# 3.3 Start services with backup vault
docker-compose start api ocr-worker

# 3.4 Wait for services to stabilize
sleep 60
```

#### Step 4: Verify Failover
```python
# 4.1 Test encryption with backup vault
from services.encryption_service import EncryptionService

service = EncryptionService()
test_data = "failover-test"

# Test multiple tenants
for tenant_id in [1, 2, 3]:
    try:
        encrypted = service.encrypt_data(test_data, tenant_id)
        decrypted = service.decrypt_data(encrypted, tenant_id)
        assert decrypted == test_data
        print(f"Tenant {tenant_id}: Failover successful")
    except Exception as e:
        print(f"Tenant {tenant_id}: Failover failed - {e}")
```

#### Step 5: Monitor and Plan Recovery
```bash
# 5.1 Set up enhanced monitoring
python scripts/setup_failover_monitoring.py

# 5.2 Plan primary vault recovery
python scripts/plan_primary_vault_recovery.py --output /recovery-plan.md

# 5.3 Schedule regular failover tests
python scripts/schedule_failover_tests.py --interval weekly
```

---

## Data Recovery from Encrypted Backups

### Purpose
Recover tenant data from encrypted backups.

### Prerequisites
- Encrypted backup files available
- Encryption keys accessible
- Target database prepared

### Procedure

#### Step 1: Prepare Recovery Environment
```bash
# 1.1 Verify backup integrity
python scripts/verify_backup_integrity.py --backup-file /backup/tenant_123_backup.enc

# 1.2 Ensure encryption keys are available
python scripts/verify_recovery_keys.py --tenant-id 123

# 1.3 Prepare target database
python scripts/prepare_recovery_database.py --tenant-id 123
```

#### Step 2: Decrypt Backup Data
```python
# 2.1 Initialize decryption service
from services.encrypted_backup_service import EncryptedBackupService

backup_service = EncryptedBackupService()

# 2.2 Decrypt backup file
backup_file = "/backup/tenant_123_backup.enc"
decrypted_data = backup_service.decrypt_backup(backup_file, tenant_id=123)

print(f"Decrypted {len(decrypted_data)} records")
```

#### Step 3: Restore Data
```bash
# 3.1 Import decrypted data
python scripts/import_decrypted_data.py --tenant-id 123 --data-file /tmp/decrypted_data.json

# 3.2 Verify data integrity
python scripts/verify_restored_data.py --tenant-id 123

# 3.3 Re-encrypt with current keys
python scripts/reencrypt_restored_data.py --tenant-id 123
```

#### Step 4: Validate Recovery
```python
# 4.1 Test data access
from models.models_per_tenant import get_tenant_models

models = get_tenant_models(123)
sample_records = models.Invoice.query.limit(10).all()

for record in sample_records:
    print(f"Invoice {record.id}: {record.description}")

# 4.2 Test encryption functionality
from services.encryption_service import EncryptionService

service = EncryptionService()
test_data = "recovery-test"
encrypted = service.encrypt_data(test_data, 123)
decrypted = service.decrypt_data(encrypted, 123)

assert decrypted == test_data
print("Recovery validation: PASSED")
```

---

## New Tenant Encryption Setup

### Purpose
Set up encryption for a new tenant.

### Prerequisites
- Tenant created in master database
- Encryption system operational
- Key vault accessible

### Procedure

#### Step 1: Generate Tenant Keys
```python
# 1.1 Initialize key management
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
key_mgmt = KeyManagementService(vault)

# 1.2 Generate keys for new tenant
tenant_id = 456  # Replace with actual tenant ID
key_mgmt.generate_tenant_keys(tenant_id)

print(f"Keys generated for tenant {tenant_id}")
```

#### Step 2: Initialize Tenant Database
```bash
# 2.1 Create encrypted tenant database
python scripts/create_encrypted_tenant_db.py --tenant-id 456

# 2.2 Run migrations with encryption
python scripts/run_tenant_migrations.py --tenant-id 456 --with-encryption

# 2.3 Verify database setup
python scripts/verify_tenant_encryption.py --tenant-id 456
```

#### Step 3: Test Tenant Encryption
```python
# 3.1 Test basic encryption operations
from services.encryption_service import EncryptionService

service = EncryptionService()
test_data = "new-tenant-test"

encrypted = service.encrypt_data(test_data, 456)
decrypted = service.decrypt_data(encrypted, 456)

assert decrypted == test_data
print(f"Tenant {tenant_id} encryption: WORKING")

# 3.2 Test with actual data models
from models.models_per_tenant import get_tenant_models

models = get_tenant_models(456)
test_invoice = models.Invoice(
    description="Test encrypted invoice",
    amount=100.00
)

# Data should be automatically encrypted when saved
test_invoice.save()
print("Encrypted data storage: WORKING")
```

#### Step 4: Configure Monitoring
```bash
# 4.1 Add tenant to monitoring
python scripts/add_tenant_monitoring.py --tenant-id 456

# 4.2 Set up alerts
python scripts/setup_tenant_alerts.py --tenant-id 456

# 4.3 Schedule key rotation
python scripts/schedule_tenant_key_rotation.py --tenant-id 456
```

---

## Encryption System Health Check

### Purpose
Perform comprehensive health check of the encryption system.

### Prerequisites
- System access
- Monitoring tools available
- Test data prepared

### Procedure

#### Step 1: Service Health
```bash
# 1.1 Check service status
docker-compose ps | grep -E "(api|ocr-worker)"

# 1.2 Test API endpoints
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/encryption

# 1.3 Check resource usage
docker stats --no-stream | grep -E "(api|ocr-worker)"
```

#### Step 2: Key Vault Connectivity
```python
# 2.1 Test all configured key vaults
from integrations.key_vault_factory import KeyVaultFactory

providers = ['aws_kms', 'azure_kv', 'hashicorp_vault', 'local']

for provider in providers:
    try:
        vault = KeyVaultFactory.create_key_vault(provider)
        result = vault.test_connection()
        print(f"{provider}: {'OK' if result else 'FAILED'}")
    except Exception as e:
        print(f"{provider}: ERROR - {e}")
```

#### Step 3: Encryption Performance
```python
# 3.1 Test encryption performance
from services.encryption_service import EncryptionService
import time

service = EncryptionService()
test_data = "performance-test-data" * 100  # ~2KB

# Test multiple tenants
for tenant_id in [1, 2, 3]:
    start_time = time.time()
    
    # Perform 100 encryption operations
    for i in range(100):
        encrypted = service.encrypt_data(f"{test_data}-{i}", tenant_id)
        decrypted = service.decrypt_data(encrypted, tenant_id)
    
    duration = time.time() - start_time
    ops_per_sec = 100 / duration
    
    print(f"Tenant {tenant_id}: {ops_per_sec:.2f} ops/sec")
```

#### Step 4: Key Rotation Status
```python
# 4.1 Check rotation schedule
from services.key_rotation_service import KeyRotationService
from integrations.key_vault_factory import KeyVaultFactory

vault = KeyVaultFactory.create_key_vault()
rotation_service = KeyRotationService(vault)

status = rotation_service.get_rotation_status()

print(f"Total tenants: {status['total_tenants']}")
print(f"Up to date: {len(status['up_to_date'])}")
print(f"Due for rotation: {len(status['due_for_rotation'])}")
print(f"Overdue: {len(status['overdue'])}")

if status['overdue']:
    print(f"ALERT: Overdue tenants: {status['overdue']}")
```

#### Step 5: Generate Health Report
```bash
# 5.1 Generate comprehensive report
python scripts/generate_health_report.py --output /reports/encryption-health-$(date +%Y%m%d).json

# 5.2 Send report to monitoring system
python scripts/send_health_metrics.py --report-file /reports/encryption-health-$(date +%Y%m%d).json

# 5.3 Update dashboard
python scripts/update_health_dashboard.py
```

---

## Emergency Contacts

- **Operations Team**: ops@company.com, +1-555-0123
- **Security Team**: security@company.com, +1-555-0124
- **Engineering Manager**: eng-manager@company.com, +1-555-0125
- **On-Call Engineer**: oncall@company.com, +1-555-0126

## Escalation Matrix

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 15 minutes | Security Team + Engineering Manager |
| High | 1 hour | Operations Team + On-Call Engineer |
| Medium | 4 hours | Operations Team |
| Low | Next business day | Operations Team |