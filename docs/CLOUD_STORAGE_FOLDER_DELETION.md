# Cloud Storage Folder Deletion Implementation

## Overview
Implemented folder deletion functionality across all cloud storage providers (AWS S3, Azure Blob, and GCP Storage) to support batch job cleanup operations.

## Problem
The original implementation had a bug where the `delete_folder` method in `CloudStorageService` was importing the wrong `StorageProvider` enum, causing the factory to not recognize registered providers. This resulted in the warning:
```
WARNING:services.cloud_storage.factory:No provider class registered for aws_s3
WARNING:services.cloud_storage_service:No S3 provider available for folder deletion
```

Additionally, only AWS S3 had folder deletion capability through direct client access, while Azure Blob and GCP Storage providers lacked this functionality.

## Solution

### 1. Fixed StorageProvider Enum Import Issue
**File:** `api/services/cloud_storage_service.py`

- Removed incorrect import of `StorageProvider` from `settings.cloud_storage_config`
- Used the correct `StorageProvider` enum already imported from `services.cloud_storage.provider`
- Fixed indentation issues in the `delete_folder` method

### 2. Implemented Folder Deletion for All Providers

#### AWS S3 Provider
**File:** `api/services/cloud_storage/aws_s3_provider.py`

Added `delete_folder` method that:
- Uses S3 paginator to list all objects with the given prefix
- Deletes objects in batches (up to 1000 per request)
- Includes security validation through `_generate_s3_key`
- Provides comprehensive logging

```python
async def delete_folder(self, folder_prefix: str) -> bool:
    """Delete all objects with a given prefix (folder) from AWS S3."""
```

#### Azure Blob Provider
**File:** `api/services/cloud_storage/azure_blob_provider.py`

Added `delete_folder` method that:
- Lists all blobs with the given prefix
- Deletes each blob individually
- Includes security validation through `_generate_blob_name`
- Handles errors gracefully with per-blob error logging

```python
async def delete_folder(self, folder_prefix: str) -> bool:
    """Delete all blobs with a given prefix (folder) from Azure Blob Storage."""
```

#### GCP Storage Provider
**File:** `api/services/cloud_storage/gcp_storage_provider.py`

Added `delete_folder` method that:
- Lists all objects with the given prefix
- Deletes each object individually
- Includes security validation through `_generate_object_name`
- Handles errors gracefully with per-object error logging

```python
async def delete_folder(self, folder_prefix: str) -> bool:
    """Delete all objects with a given prefix (folder) from Google Cloud Storage."""
```

### 3. Enhanced CloudStorageService

**File:** `api/services/cloud_storage_service.py`

Updated `delete_folder` method to:
- Iterate through all cloud providers (AWS S3, Azure Blob, GCP Storage)
- Use each provider's `delete_folder` method if available
- Maintain backward compatibility with direct S3 client access as fallback
- Return success if at least one provider successfully deletes the folder
- Provide comprehensive logging for each provider attempt

## Features

### Security
- All implementations include path traversal protection
- Tenant isolation is maintained through provider-specific key generation
- Access control validation is performed before deletion

### Error Handling
- Graceful handling of missing providers
- Per-file/blob/object error logging without failing the entire operation
- Comprehensive exception logging with stack traces

### Logging
- Info-level logs for successful operations
- Warning-level logs for failed attempts
- Debug-level logs for individual file deletions
- Error-level logs with full exception details

## Usage

The folder deletion is used in batch processing cleanup:

```python
from services.cloud_storage_service import CloudStorageService

storage_service = CloudStorageService(db)
result = await storage_service.delete_folder(
    folder_prefix="exported/job-id/",
    tenant_id="2",
    bucket_name=None,  # Optional, uses config default
    aws_credentials=None  # Optional, uses config default
)
```

## Testing

The implementation can be tested by:
1. Creating a batch processing job that uploads files to a folder
2. Deleting the statement/job
3. Verifying that all files are removed from all configured cloud providers
4. Checking logs for successful deletion messages

## Benefits

1. **Consistency**: All cloud providers now have the same interface
2. **Reliability**: Deletion attempts on all configured providers
3. **Maintainability**: Provider-specific logic is encapsulated in provider classes
4. **Flexibility**: Easy to add new providers with folder deletion support
5. **Robustness**: Errors in one provider don't prevent cleanup in others

## Related Files

- `api/services/cloud_storage_service.py` - Main orchestration service
- `api/services/cloud_storage/aws_s3_provider.py` - AWS S3 implementation
- `api/services/cloud_storage/azure_blob_provider.py` - Azure Blob implementation
- `api/services/cloud_storage/gcp_storage_provider.py` - GCP Storage implementation
- `api/routers/statements.py` - Usage in batch job cleanup

## Migration Notes

No migration is required. The changes are backward compatible and enhance existing functionality.
