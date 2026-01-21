# Export Destination Feature Gating

## Overview
Export destinations is a commercial feature that requires the `cloud_storage` feature to be enabled. This is because export destinations are used to export data to cloud storage providers.

## Implementation

### Feature ID
- **Feature ID:** `cloud_storage` (shared with cloud storage configuration)
- **Type:** Commercial feature
- **License Requirement:** Business license (trial or paid)

### Protected Endpoints
All export destination endpoints now require the `cloud_storage` feature to be enabled:

1. **POST /api/v1/export-destinations/** - Create export destination
2. **GET /api/v1/export-destinations/** - List export destinations
3. **GET /api/v1/export-destinations/{destination_id}** - Get specific destination
4. **PUT /api/v1/export-destinations/{destination_id}** - Update destination
5. **POST /api/v1/export-destinations/{destination_id}/test** - Test connection
6. **DELETE /api/v1/export-destinations/{destination_id}** - Delete destination

### Implementation Details

**File:** `api/commercial/export/router.py`

Added feature check to all endpoints:
```python
from core.utils.feature_gate import check_feature

# In each endpoint:
check_feature("cloud_storage", db)
```

### Error Response
When the feature is not licensed, endpoints return HTTP 402 (Payment Required):

```json
{
  "error": "FEATURE_NOT_LICENSED",
  "message": "The 'cloud_storage' feature requires a valid license...",
  "feature_id": "cloud_storage",
  "license_status": "invalid|trial|expired|active",
  "trial_active": false,
  "in_grace_period": false,
  "upgrade_required": true
}
```

## License Requirements

### Trial License
- Export destinations are available during trial period
- Feature becomes unavailable when trial expires (unless in grace period)

### Business License
- Export destinations are included in business licenses
- Feature is available as long as license is active

### Personal License
- Export destinations are NOT available for personal use licenses
- Users must upgrade to business license to access this feature

## Configuration

The feature is controlled by the license service. To enable/disable for testing:

1. **Via License:** Activate a business license or start a trial
2. **Via Environment:** Set feature flags in the license configuration
3. **Via Database:** Update the installation_info table with appropriate license status

## Relationship to Cloud Storage

Export destinations share the `cloud_storage` feature gate because:
1. Both features deal with cloud storage providers (S3, Azure, GCS)
2. Export destinations are used to export data to cloud storage
3. Simplifies licensing - one feature gate for all cloud storage functionality
4. Consistent with the feature matrix where cloud storage is a business-only feature

## Related Files
- `api/commercial/export/router.py` - Export destination endpoints
- `api/commercial/cloud_storage/router.py` - Cloud storage configuration endpoints
- `api/core/utils/feature_gate.py` - Feature gating utilities
- `api/core/services/license_service.py` - License service
- `api/core/constants/export_destination.py` - Export destination constants
