# Local Export Destination Support

## Problem
When listing export destinations, local destinations were causing errors:
```
WARNING:core.services.export_destination_service:No credentials configured for local destination. Attempting to use environment variable fallback for tenant 1
ERROR:core.services.export_destination_service:Failed to get credentials for destination 1: Unknown destination type: local
WARNING:commercial.export.router:Failed to decrypt credentials for destination 1: Unknown destination type: local
```

Additionally, the test button was being shown for local destinations, which don't need connection testing.

## Solution

### 1. Added Local Destination Type Support
**File:** `api/core/services/export_destination_service.py`

Added handling for 'local' destination type in `_get_fallback_credentials`:
```python
elif destination_type == 'local':
    # Local destination doesn't require credentials
    logger.info("Local destination type - no credentials required")
    return {
        'type': 'local',
        'path': os.getenv('LOCAL_EXPORT_PATH', 'exports')
    }
```

### 2. Skip Connection Testing for Local Destinations
**File:** `api/core/services/export_destination_service.py`

Updated `test_connection` method to skip testing for local destinations:
```python
# Local destinations don't need testing
if destination.destination_type == 'local':
    logger.info(f"Local destination {destination_id} - skipping connection test")
    destination.last_test_at = datetime.now(timezone.utc)
    destination.last_test_success = True
    destination.last_test_error = None
    self.db.commit()
    return True, None
```

### 3. Added Testable Field to Response Schema
**File:** `api/core/schemas/export_destination.py`

Added `testable` field to `ExportDestinationResponse`:
```python
testable: bool = Field(default=True, description="Whether this destination supports connection testing")
```

### 4. Updated Router to Set Testable Flag
**File:** `api/commercial/export/router.py`

Updated all response creations to set `testable=False` for local destinations:
```python
testable=destination_config.destination_type != 'local'
```

## Impact
- ✅ Local destinations no longer cause credential decryption errors
- ✅ Test button is disabled for local destinations (testable=false)
- ✅ Local destinations are properly supported alongside cloud storage providers
- ✅ No credentials required for local destinations

## Supported Destination Types
- `s3` - AWS S3 (testable)
- `azure` - Azure Blob Storage (testable)
- `gcs` - Google Cloud Storage (testable)
- `google_drive` - Google Drive (testable)
- `local` - Local file system (not testable)

## Frontend Implementation
The UI should check the `testable` field to conditionally show/hide the test button:
```typescript
{destination.testable && (
  <button onClick={() => testConnection(destination.id)}>
    Test Connection
  </button>
)}
```
