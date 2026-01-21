# Encryption Backup and Recovery Procedures

## Overview

This document provides comprehensive procedures for backing up and recovering encrypted data and encryption keys. It covers both routine backup operations and emergency recovery scenarios.

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Encryption Key Backup](#encryption-key-backup)
3. [Encrypted Data Backup](#encrypted-data-backup)
4. [Recovery Procedures](#recovery-procedures)
5. [Testing and Validation](#testing-and-validation)
6. [Automation Scripts](#automation-scripts)

## Backup Strategy

### Backup Types

1. **Full Backup**: Complete backup of all encrypted data and keys
2. **Incremental Backup**: Changes since last backup
3. **Differential Backup**: Changes since last full backup
4. **Key-Only Backup**: Encryption keys without data

### Backup Schedule

- **Daily**: Incremental backups of encrypted data
- **Weekly**: Full backup of all tenant data
- **Monthly**: Complete system backup including keys
- **Before Key Rotation**: Emergency backup of keys and data

### Retention Policy

- **Daily backups**: Retain for 30 days
- **Weekly backups**: Retain for 12 weeks
- **Monthly backups**: Retain for 12 months
- **Key backups**: Retain for 7 years (compliance requirement)

## Encryption Key Backup

### Master Key Backup

```bash
#!/bin/bash
# Backup master encryption keys

BACKUP_DIR="/backup/keys/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup local keys (if using local key vault)
if [ "$KEY_VAULT_PROVIDER" = "local" ]; then
    cp -r /app/keys/* "$BACKUP_DIR/"
    chmod 600 "$BACKUP_DIR"/*
fi

# Export key metadata
python scripts/export_key_metadata.py --output "$BACKUP_DIR/key_metadata.json"

# Create encrypted archive
tar -czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_DIR" .
gpg --symmetric --cipher-algo AES256 --output "$BACKUP_DIR.tar.gz.gpg" "$BACKUP_DIR.tar.gz"

# Clean up unencrypted files
rm -rf "$BACKUP_DIR" "$BACKUP_DIR.tar.gz"

echo "Master key backup completed: $BACKUP_DIR.tar.gz.gpg"
```

### Tenant Key Backup

```python
#!/usr/bin/env python3
"""
Backup tenant-specific encryption keys
"""

import os
import json
import tarfile
import subprocess
from datetime import datetime
from services.key_management_service import KeyManagementService
from integrations.key_vault_factory import KeyVaultFactory

def backup_tenant_keys(tenant_id, backup_dir):
    """Backup keys for a specific tenant."""
    
    vault = KeyVaultFactory.create_key_vault()
    key_mgmt = KeyManagementService(vault)
    
    # Create tenant backup directory
    tenant_backup_dir = os.path.join(backup_dir, f"tenant_{tenant_id}")
    os.makedirs(tenant_backup_dir, exist_ok=True)
    
    # Export tenant keys
    keys = key_mgmt.export_tenant_keys(tenant_id)
    
    # Save key data
    key_file = os.path.join(tenant_backup_dir, "keys.json")
    with open(key_file, 'w') as f:
        json.dump(keys, f, indent=2)
    
    # Save key metadata
    metadata = key_mgmt.get_tenant_key_metadata(tenant_id)
    metadata_file = os.path.join(tenant_backup_dir, "metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Tenant {tenant_id} keys backed up to {tenant_backup_dir}")

def backup_all_tenant_keys():
    """Backup keys for all tenants."""
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = f"/backup/tenant-keys/{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Get list of all tenants
    vault = KeyVaultFactory.create_key_vault()
    key_mgmt = KeyManagementService(vault)
    tenant_ids = key_mgmt.get_all_tenant_ids()
    
    # Backup each tenant
    for tenant_id in tenant_ids:
        try:
            backup_tenant_keys(tenant_id, backup_dir)
        except Exception as e:
            print(f"Failed to backup tenant {tenant_id}: {e}")
    
    # Create encrypted archive
    archive_path = f"{backup_dir}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(backup_dir, arcname=os.path.basename(backup_dir))
    
    # Encrypt archive
    encrypted_path = f"{archive_path}.gpg"
    subprocess.run([
        "gpg", "--symmetric", "--cipher-algo", "AES256",
        "--output", encrypted_path, archive_path
    ], check=True)
    
    # Clean up
    subprocess.run(["rm", "-rf", backup_dir, archive_path], check=True)
    
    print(f"All tenant keys backed up to {encrypted_path}")

if __name__ == "__main__":
    backup_all_tenant_keys()
```

### Key Vault Backup

```python
#!/usr/bin/env python3
"""
Backup key vault configuration and access policies
"""

import json
import os
from datetime import datetime
from integrations.key_vault_factory import KeyVaultFactory

def backup_key_vault_config():
    """Backup key vault configuration."""
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = f"/backup/key-vault-config/{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup configuration for each provider
    providers = ['aws_kms', 'azure_kv', 'hashicorp_vault']
    
    for provider in providers:
        try:
            vault = KeyVaultFactory.create_key_vault(provider)
            config = vault.export_configuration()
            
            config_file = os.path.join(backup_dir, f"{provider}_config.json")
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            print(f"Backed up {provider} configuration")
            
        except Exception as e:
            print(f"Failed to backup {provider}: {e}")
    
    print(f"Key vault configuration backed up to {backup_dir}")

if __name__ == "__main__":
    backup_key_vault_config()
```

## Encrypted Data Backup

### Full Tenant Backup

```python
#!/usr/bin/env python3
"""
Create full backup of encrypted tenant data
"""

import os
import subprocess
import json
from datetime import datetime
from services.encrypted_backup_service import EncryptedBackupService
from models.models_per_tenant import get_tenant_models

def backup_tenant_data(tenant_id, backup_dir):
    """Create full backup of tenant data."""
    
    backup_service = EncryptedBackupService()
    
    # Create tenant backup directory
    tenant_backup_dir = os.path.join(backup_dir, f"tenant_{tenant_id}")
    os.makedirs(tenant_backup_dir, exist_ok=True)
    
    # Get tenant models
    models = get_tenant_models(tenant_id)
    
    # Backup each model
    for model_name, model_class in models.items():
        try:
            # Export encrypted data
            data = backup_service.export_model_data(model_class, tenant_id)
            
            # Save to file
            backup_file = os.path.join(tenant_backup_dir, f"{model_name}.json")
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Backed up {model_name}: {len(data)} records")
            
        except Exception as e:
            print(f"Failed to backup {model_name}: {e}")
    
    # Create backup metadata
    metadata = {
        'tenant_id': tenant_id,
        'backup_timestamp': datetime.now().isoformat(),
        'backup_type': 'full',
        'models_backed_up': list(models.keys())
    }
    
    metadata_file = os.path.join(tenant_backup_dir, "backup_metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Tenant {tenant_id} data backed up to {tenant_backup_dir}")

def backup_all_tenants():
    """Backup data for all tenants."""
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = f"/backup/tenant-data/{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Get list of all tenants
    from services.key_management_service import KeyManagementService
    from integrations.key_vault_factory import KeyVaultFactory
    
    vault = KeyVaultFactory.create_key_vault()
    key_mgmt = KeyManagementService(vault)
    tenant_ids = key_mgmt.get_all_tenant_ids()
    
    # Backup each tenant
    for tenant_id in tenant_ids:
        try:
            backup_tenant_data(tenant_id, backup_dir)
        except Exception as e:
            print(f"Failed to backup tenant {tenant_id}: {e}")
    
    # Create compressed archive
    archive_path = f"{backup_dir}.tar.gz"
    subprocess.run([
        "tar", "-czf", archive_path, "-C", os.path.dirname(backup_dir),
        os.path.basename(backup_dir)
    ], check=True)
    
    # Clean up uncompressed backup
    subprocess.run(["rm", "-rf", backup_dir], check=True)
    
    print(f"All tenant data backed up to {archive_path}")

if __name__ == "__main__":
    backup_all_tenants()
```

### Incremental Backup

```python
#!/usr/bin/env python3
"""
Create incremental backup of changed encrypted data
"""

import os
import json
from datetime import datetime, timedelta
from services.encrypted_backup_service import EncryptedBackupService

def incremental_backup_tenant(tenant_id, since_timestamp, backup_dir):
    """Create incremental backup since specified timestamp."""
    
    backup_service = EncryptedBackupService()
    
    # Create tenant backup directory
    tenant_backup_dir = os.path.join(backup_dir, f"tenant_{tenant_id}")
    os.makedirs(tenant_backup_dir, exist_ok=True)
    
    # Get changed records since timestamp
    changes = backup_service.get_changes_since(tenant_id, since_timestamp)
    
    # Save changes
    changes_file = os.path.join(tenant_backup_dir, "changes.json")
    with open(changes_file, 'w') as f:
        json.dump(changes, f, indent=2)
    
    # Create backup metadata
    metadata = {
        'tenant_id': tenant_id,
        'backup_timestamp': datetime.now().isoformat(),
        'backup_type': 'incremental',
        'since_timestamp': since_timestamp.isoformat(),
        'changes_count': len(changes)
    }
    
    metadata_file = os.path.join(tenant_backup_dir, "backup_metadata.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Incremental backup for tenant {tenant_id}: {len(changes)} changes")

def daily_incremental_backup():
    """Perform daily incremental backup."""
    
    # Calculate since timestamp (24 hours ago)
    since_timestamp = datetime.now() - timedelta(hours=24)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = f"/backup/incremental/{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Get list of all tenants
    from services.key_management_service import KeyManagementService
    from integrations.key_vault_factory import KeyVaultFactory
    
    vault = KeyVaultFactory.create_key_vault()
    key_mgmt = KeyManagementService(vault)
    tenant_ids = key_mgmt.get_all_tenant_ids()
    
    # Backup changes for each tenant
    total_changes = 0
    for tenant_id in tenant_ids:
        try:
            incremental_backup_tenant(tenant_id, since_timestamp, backup_dir)
        except Exception as e:
            print(f"Failed incremental backup for tenant {tenant_id}: {e}")
    
    print(f"Daily incremental backup completed: {backup_dir}")

if __name__ == "__main__":
    daily_incremental_backup()
```

## Recovery Procedures

### Master Key Recovery

```bash
#!/bin/bash
# Recover master encryption keys from backup

BACKUP_FILE="$1"
RECOVERY_DIR="/recovery/keys/$(date +%Y%m%d-%H%M%S)"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz.gpg>"
    exit 1
fi

# Create recovery directory
mkdir -p "$RECOVERY_DIR"

# Decrypt backup
gpg --decrypt "$BACKUP_FILE" > "$RECOVERY_DIR/backup.tar.gz"

# Extract backup
tar -xzf "$RECOVERY_DIR/backup.tar.gz" -C "$RECOVERY_DIR"

# Restore keys
if [ "$KEY_VAULT_PROVIDER" = "local" ]; then
    # Stop services
    docker-compose stop api ocr-worker
    
    # Backup current keys
    cp -r /app/keys /app/keys.backup.$(date +%Y%m%d-%H%M%S)
    
    # Restore keys
    cp -r "$RECOVERY_DIR"/* /app/keys/
    chmod 600 /app/keys/*
    
    # Restart services
    docker-compose start api ocr-worker
fi

# Import key metadata
python scripts/import_key_metadata.py --input "$RECOVERY_DIR/key_metadata.json"

echo "Master key recovery completed"
```

### Tenant Data Recovery

```python
#!/usr/bin/env python3
"""
Recover tenant data from encrypted backup
"""

import os
import json
import tarfile
from services.encrypted_backup_service import EncryptedBackupService
from models.models_per_tenant import get_tenant_models

def recover_tenant_data(tenant_id, backup_file, target_timestamp=None):
    """Recover tenant data from backup."""
    
    backup_service = EncryptedBackupService()
    
    # Extract backup
    recovery_dir = f"/recovery/tenant_{tenant_id}"
    os.makedirs(recovery_dir, exist_ok=True)
    
    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(recovery_dir)
    
    # Find tenant backup directory
    tenant_backup_dir = os.path.join(recovery_dir, f"tenant_{tenant_id}")
    
    if not os.path.exists(tenant_backup_dir):
        raise ValueError(f"Tenant {tenant_id} not found in backup")
    
    # Load backup metadata
    metadata_file = os.path.join(tenant_backup_dir, "backup_metadata.json")
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    print(f"Recovering tenant {tenant_id} from backup created at {metadata['backup_timestamp']}")
    
    # Get tenant models
    models = get_tenant_models(tenant_id)
    
    # Recover each model
    for model_name in metadata['models_backed_up']:
        if model_name not in models:
            print(f"Warning: Model {model_name} not found in current schema")
            continue
        
        model_class = models[model_name]
        backup_file = os.path.join(tenant_backup_dir, f"{model_name}.json")
        
        if not os.path.exists(backup_file):
            print(f"Warning: Backup file for {model_name} not found")
            continue
        
        # Load backup data
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        # Restore data
        restored_count = backup_service.restore_model_data(
            model_class, backup_data, tenant_id, target_timestamp
        )
        
        print(f"Restored {model_name}: {restored_count} records")
    
    print(f"Tenant {tenant_id} recovery completed")

def point_in_time_recovery(tenant_id, target_timestamp):
    """Perform point-in-time recovery for a tenant."""
    
    backup_service = EncryptedBackupService()
    
    # Find appropriate backups
    full_backup = backup_service.find_full_backup_before(tenant_id, target_timestamp)
    incremental_backups = backup_service.find_incremental_backups_between(
        tenant_id, full_backup['timestamp'], target_timestamp
    )
    
    print(f"Point-in-time recovery to {target_timestamp}")
    print(f"Using full backup: {full_backup['file']}")
    print(f"Applying {len(incremental_backups)} incremental backups")
    
    # Restore from full backup
    recover_tenant_data(tenant_id, full_backup['file'], target_timestamp)
    
    # Apply incremental backups
    for inc_backup in incremental_backups:
        apply_incremental_backup(tenant_id, inc_backup['file'], target_timestamp)
    
    print(f"Point-in-time recovery completed for tenant {tenant_id}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python recover_tenant_data.py <tenant_id> <backup_file> [target_timestamp]")
        sys.exit(1)
    
    tenant_id = int(sys.argv[1])
    backup_file = sys.argv[2]
    target_timestamp = sys.argv[3] if len(sys.argv) > 3 else None
    
    recover_tenant_data(tenant_id, backup_file, target_timestamp)
```

### Complete System Recovery

```bash
#!/bin/bash
# Complete system recovery from backups

BACKUP_DIR="$1"
RECOVERY_TYPE="${2:-full}"  # full, partial, keys-only

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory> [recovery_type]"
    echo "Recovery types: full, partial, keys-only"
    exit 1
fi

echo "Starting $RECOVERY_TYPE system recovery from $BACKUP_DIR"

# Step 1: Stop all services
echo "Stopping services..."
docker-compose down

# Step 2: Recover encryption keys
echo "Recovering encryption keys..."
./scripts/recover_master_keys.sh "$BACKUP_DIR/keys/master_keys.tar.gz.gpg"
./scripts/recover_tenant_keys.sh "$BACKUP_DIR/keys/tenant_keys.tar.gz.gpg"

# Step 3: Recover databases (if full recovery)
if [ "$RECOVERY_TYPE" = "full" ]; then
    echo "Recovering databases..."
    
    # Recover master database
    docker-compose up -d postgres-master
    sleep 30
    
    gunzip -c "$BACKUP_DIR/databases/master_backup.sql.gz" | \
        docker-compose exec -T postgres-master psql -U postgres
    
    # Recover tenant databases
    for tenant_backup in "$BACKUP_DIR"/databases/tenant_*.sql.gz; do
        if [ -f "$tenant_backup" ]; then
            echo "Recovering $(basename "$tenant_backup")"
            gunzip -c "$tenant_backup" | \
                docker-compose exec -T postgres-master psql -U postgres
        fi
    done
fi

# Step 4: Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 60

# Step 5: Verify recovery
echo "Verifying recovery..."
python scripts/verify_system_recovery.py

# Step 6: Test encryption functionality
echo "Testing encryption functionality..."
python scripts/test_encryption_after_recovery.py

echo "System recovery completed"
```

## Testing and Validation

### Backup Integrity Testing

```python
#!/usr/bin/env python3
"""
Test backup integrity and recoverability
"""

import os
import tempfile
import shutil
from services.encrypted_backup_service import EncryptedBackupService

def test_backup_integrity(backup_file):
    """Test if backup can be successfully restored."""
    
    backup_service = EncryptedBackupService()
    
    # Create temporary recovery environment
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract backup
            backup_service.extract_backup(backup_file, temp_dir)
            
            # Validate backup structure
            required_files = ['backup_metadata.json']
            for req_file in required_files:
                if not os.path.exists(os.path.join(temp_dir, req_file)):
                    return False, f"Missing required file: {req_file}"
            
            # Test data integrity
            integrity_result = backup_service.verify_backup_integrity(temp_dir)
            
            return integrity_result, "Backup integrity verified"
            
        except Exception as e:
            return False, f"Backup integrity test failed: {e}"

def test_recovery_process(tenant_id, backup_file):
    """Test complete recovery process."""
    
    # Create test environment
    test_db = f"test_recovery_{tenant_id}"
    
    try:
        # Perform recovery in test environment
        recovery_result = recover_tenant_data(tenant_id, backup_file, test_environment=test_db)
        
        # Verify recovered data
        verification_result = verify_recovered_data(tenant_id, test_db)
        
        return recovery_result and verification_result
        
    finally:
        # Clean up test environment
        cleanup_test_environment(test_db)

def automated_backup_testing():
    """Automated testing of all recent backups."""
    
    backup_dir = "/backup"
    test_results = []
    
    # Test recent backups
    for backup_file in os.listdir(backup_dir):
        if backup_file.endswith('.tar.gz'):
            backup_path = os.path.join(backup_dir, backup_file)
            
            # Test integrity
            integrity_ok, integrity_msg = test_backup_integrity(backup_path)
            
            test_results.append({
                'backup_file': backup_file,
                'integrity_test': integrity_ok,
                'integrity_message': integrity_msg
            })
    
    # Generate test report
    generate_backup_test_report(test_results)

if __name__ == "__main__":
    automated_backup_testing()
```

### Recovery Testing

```python
#!/usr/bin/env python3
"""
Disaster recovery testing procedures
"""

import os
import subprocess
import tempfile
from datetime import datetime

def test_full_disaster_recovery():
    """Test complete disaster recovery procedure."""
    
    print("Starting disaster recovery test...")
    
    # Step 1: Create test backup
    print("Creating test backup...")
    test_backup_dir = create_test_backup()
    
    # Step 2: Simulate disaster (destroy test environment)
    print("Simulating disaster...")
    test_env = create_isolated_test_environment()
    
    try:
        # Step 3: Perform recovery
        print("Performing recovery...")
        recovery_success = perform_test_recovery(test_backup_dir, test_env)
        
        # Step 4: Validate recovery
        print("Validating recovery...")
        validation_success = validate_test_recovery(test_env)
        
        # Step 5: Test functionality
        print("Testing functionality...")
        functionality_success = test_recovered_functionality(test_env)
        
        # Generate report
        test_result = {
            'timestamp': datetime.now().isoformat(),
            'recovery_success': recovery_success,
            'validation_success': validation_success,
            'functionality_success': functionality_success,
            'overall_success': all([recovery_success, validation_success, functionality_success])
        }
        
        generate_disaster_recovery_test_report(test_result)
        
        return test_result['overall_success']
        
    finally:
        # Clean up test environment
        cleanup_test_environment(test_env)

def monthly_recovery_test():
    """Monthly disaster recovery test."""
    
    print("Starting monthly disaster recovery test...")
    
    # Test different recovery scenarios
    scenarios = [
        'full_system_recovery',
        'partial_tenant_recovery',
        'key_only_recovery',
        'point_in_time_recovery'
    ]
    
    results = {}
    
    for scenario in scenarios:
        print(f"Testing scenario: {scenario}")
        results[scenario] = test_recovery_scenario(scenario)
    
    # Generate comprehensive report
    generate_monthly_test_report(results)
    
    # Alert if any tests failed
    if not all(results.values()):
        send_test_failure_alert(results)

if __name__ == "__main__":
    monthly_recovery_test()
```

## Automation Scripts

### Automated Backup Script

```bash
#!/bin/bash
# Automated backup script for cron scheduling

# Configuration
BACKUP_ROOT="/backup"
LOG_FILE="/var/log/encryption-backup.log"
RETENTION_DAYS=30

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Main backup function
perform_backup() {
    local backup_type="$1"
    local timestamp=$(date +%Y%m%d-%H%M%S)
    
    log "Starting $backup_type backup"
    
    case "$backup_type" in
        "daily")
            # Daily incremental backup
            python scripts/daily_incremental_backup.py
            ;;
        "weekly")
            # Weekly full backup
            python scripts/backup_all_tenants.py
            python scripts/backup_all_tenant_keys.py
            ;;
        "monthly")
            # Monthly complete system backup
            python scripts/complete_system_backup.py
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        log "$backup_type backup completed successfully"
    else
        log "ERROR: $backup_type backup failed"
        send_backup_failure_alert "$backup_type"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days"
    
    find "$BACKUP_ROOT" -type f -name "*.tar.gz*" -mtime +$RETENTION_DAYS -delete
    
    log "Backup cleanup completed"
}

# Send failure alert
send_backup_failure_alert() {
    local backup_type="$1"
    python scripts/send_alert.py --severity HIGH --message "Backup failure: $backup_type"
}

# Main execution
case "${1:-daily}" in
    "daily")
        perform_backup "daily"
        ;;
    "weekly")
        perform_backup "weekly"
        cleanup_old_backups
        ;;
    "monthly")
        perform_backup "monthly"
        ;;
    *)
        echo "Usage: $0 [daily|weekly|monthly]"
        exit 1
        ;;
esac
```

### Cron Configuration

```bash
# Add to crontab for automated backups

# Daily incremental backup at 2 AM
0 2 * * * /path/to/automated_backup.sh daily

# Weekly full backup on Sundays at 1 AM
0 1 * * 0 /path/to/automated_backup.sh weekly

# Monthly complete backup on 1st of month at midnight
0 0 1 * * /path/to/automated_backup.sh monthly

# Daily backup verification at 6 AM
0 6 * * * /path/to/verify_backups.sh

# Monthly disaster recovery test on 15th at 3 AM
0 3 15 * * /path/to/monthly_recovery_test.sh
```

## Compliance and Auditing

### Backup Audit Trail

```python
#!/usr/bin/env python3
"""
Generate backup audit trail for compliance
"""

import json
import os
from datetime import datetime, timedelta

def generate_backup_audit_report(days=30):
    """Generate backup audit report for specified period."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    audit_data = {
        'report_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'backup_summary': {},
        'compliance_status': {},
        'recommendations': []
    }
    
    # Analyze backup logs
    backup_logs = parse_backup_logs(start_date, end_date)
    
    # Generate summary
    audit_data['backup_summary'] = {
        'total_backups': len(backup_logs),
        'successful_backups': len([b for b in backup_logs if b['status'] == 'success']),
        'failed_backups': len([b for b in backup_logs if b['status'] == 'failed']),
        'backup_types': count_backup_types(backup_logs)
    }
    
    # Check compliance
    audit_data['compliance_status'] = check_backup_compliance(backup_logs)
    
    # Generate recommendations
    audit_data['recommendations'] = generate_backup_recommendations(backup_logs)
    
    # Save report
    report_file = f"/audit/backup_audit_{end_date.strftime('%Y%m%d')}.json"
    with open(report_file, 'w') as f:
        json.dump(audit_data, f, indent=2)
    
    print(f"Backup audit report generated: {report_file}")
    return audit_data

if __name__ == "__main__":
    generate_backup_audit_report()
```

This comprehensive backup and recovery documentation provides detailed procedures for protecting and recovering encrypted data and keys, ensuring business continuity and compliance with data protection requirements.