# Export Destination Encryption Key Fix

## Problem
When creating an export destination, the system was failing with:
```
ERROR:core.services.encryption_service:Failed to get tenant key for 1: Tenant key not found for tenant 1
ERROR:core.services.export_destination_service:Failed to encrypt credentials for destination 'aws': Failed to encrypt data: Tenant key not found for tenant 1
```

The issue occurred because tenant encryption keys were not being generated during database initialization, causing credential encryption to fail when creating export destinations.

## Root Cause
1. The `KeyManagementService` had missing attribute initialization (`_storage_lock`, `_key_storage`, `_key_metadata`)
2. Tenant encryption keys were not being auto-generated during database initialization
3. The `DB_INIT_PHASE` flag prevented auto-generation of keys during startup

## Solution

### 1. Fixed KeyManagementService Initialization
**File:** `api/core/services/key_management_service.py`

Added missing attribute initialization in `__init__`:
```python
self._storage_lock = Lock()  # Lock for thread-safe access to storage
self._key_storage: Dict[int, str] = {}  # Storage for encrypted keys
self._key_metadata: Dict[int, Dict[str, Any]] = {}  # Metadata for keys
```

### 2. Added Tenant Key Generation During Database Initialization
**File:** `api/db_init.py`

Added key generation step after clearing the `DB_INIT_PHASE` flag:
```python
# Generate encryption keys for all tenants
logger.info("Generating encryption keys for all tenants...")
try:
    from core.services.key_management_service import KeyManagementService
    key_management = KeyManagementService()
    
    for tenant in tenants:
        try:
            # Check if tenant key already exists
            existing_keys = key_management.list_tenant_keys()
            if tenant.id not in existing_keys:
                logger.info(f"Generating encryption key for tenant {tenant.id}...")
                key_management.generate_tenant_key(tenant.id)
                logger.info(f"Generated encryption key for tenant {tenant.id}")
            else:
                logger.info(f"Encryption key already exists for tenant {tenant.id}")
        except Exception as e:
            logger.error(f"Failed to generate encryption key for tenant {tenant.id}: {str(e)}")
except Exception as e:
    logger.error(f"Failed to initialize encryption keys: {str(e)}")
```

## Impact
- ✅ Export destinations can now be created successfully with encrypted credentials
- ✅ Tenant encryption keys are automatically generated during database initialization
- ✅ Credentials are properly encrypted using tenant-specific keys
- ✅ No manual key generation steps required

## Testing
After the fix, export destinations can be created successfully:
```
✓ Export destination created successfully!
  ID: 1
  Name: Test S3 Destination
  Type: s3
```

## Related Files
- `api/core/services/key_management_service.py` - Key management service
- `api/core/services/encryption_service.py` - Encryption service
- `api/core/services/export_destination_service.py` - Export destination service
- `api/commercial/export/router.py` - Export destination API endpoints
- `api/db_init.py` - Database initialization
