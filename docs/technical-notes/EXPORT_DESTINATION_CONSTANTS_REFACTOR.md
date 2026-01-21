# Export Destination Constants Refactor

## Problem
The allowed destination types were duplicated in multiple files:
- `api/core/schemas/export_destination.py` - In the validator
- `api/core/services/export_destination_service.py` - In the create_destination method

This violated DRY (Don't Repeat Yourself) principle and made maintenance harder.

## Solution

### Created Constants Module
**File:** `api/core/constants/export_destination.py`

Centralized all export destination constants:
```python
# Supported export destination types
EXPORT_DESTINATION_TYPES = ['s3', 'azure', 'gcs', 'google_drive', 'local']

# Destination types that support connection testing
TESTABLE_DESTINATION_TYPES = ['s3', 'azure', 'gcs', 'google_drive']

# Destination type labels for UI
DESTINATION_TYPE_LABELS = {
    's3': 'AWS S3',
    'azure': 'Azure Blob Storage',
    'gcs': 'Google Cloud Storage',
    'google_drive': 'Google Drive',
    'local': 'Local File System',
}
```

### Created Constants Package Init
**File:** `api/core/constants/__init__.py`

Exports constants for easy importing:
```python
from core.constants import (
    EXPORT_DESTINATION_TYPES,
    TESTABLE_DESTINATION_TYPES,
    DESTINATION_TYPE_LABELS,
)
```

### Updated Schema
**File:** `api/core/schemas/export_destination.py`

Now imports and uses the constant:
```python
from core.constants import EXPORT_DESTINATION_TYPES

@validator('destination_type')
def validate_destination_type(cls, v):
    if v not in EXPORT_DESTINATION_TYPES:
        raise ValueError(f"Destination type must be one of: {', '.join(EXPORT_DESTINATION_TYPES)}")
    return v
```

### Updated Service
**File:** `api/core/services/export_destination_service.py`

Now imports and uses the constant:
```python
from core.constants import EXPORT_DESTINATION_TYPES

if destination_type not in EXPORT_DESTINATION_TYPES:
    raise ValueError(f"Invalid destination type. Must be one of: {', '.join(EXPORT_DESTINATION_TYPES)}")
```

## Benefits
- ✅ Single source of truth for destination types
- ✅ Easier to add new destination types (only update one place)
- ✅ Consistent validation across the codebase
- ✅ Reusable constants for UI and other components
- ✅ Better maintainability and reduced duplication

## Future Usage
Additional constants can be added to the module as needed:
- Credential field requirements per destination type
- Environment variable mappings
- Default configurations
- Feature flags per destination type
