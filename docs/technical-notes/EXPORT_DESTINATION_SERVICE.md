# Export Destination Service Implementation

## Overview

The Export Destination Service provides secure management of cloud storage export configurations for the batch file processing system. It supports multiple cloud providers with encrypted credential storage and connection testing.

## Components Implemented

### 1. Pydantic Schemas (`api/schemas/export_destination.py`)

#### Credential Schemas

- **S3Credentials**: AWS S3 credentials with validation
  - `access_key_id`, `secret_access_key`, `region`, `bucket_name`, `path_prefix`
- **AzureCredentials**: Azure Blob Storage credentials (two variants)
  - `AzureCredentialsConnectionString`: Using connection string
  - `AzureCredentialsAccountKey`: Using account name and key
- **GCSCredentials**: Google Cloud Storage credentials (two variants)
  - `GCSCredentialsServiceAccount`: Using service account JSON
  - `GCSCredentialsProjectId`: Using project ID and credentials
- **GoogleDriveCredentials**: Google Drive OAuth2 credentials
  - `oauth_token`, `refresh_token`, `folder_id`

#### API Schemas

- **ExportDestinationCreate**: Schema for creating destinations
- **ExportDestinationUpdate**: Schema for updating destinations
- **ExportDestinationResponse**: Schema for API responses with masked credentials
- **ExportDestinationTestResult**: Schema for connection test results
- **ExportDestinationList**: Schema for listing destinations

### 2. Export Destination Service (`api/services/export_destination_service.py`)

#### Core Methods

##### Destination Management

- `create_destination()`: Create new export destination with encrypted credentials
- `update_destination()`: Update existing destination (supports partial updates)
- `get_destination()`: Retrieve specific destination
- `list_destinations()`: List all destinations with filtering
- `delete_destination()`: Soft delete destination (set is_active=False)

##### Credential Management

- `get_decrypted_credentials()`: Decrypt and retrieve credentials
- `mask_credentials()`: Mask sensitive values for API responses
- `_get_fallback_credentials()`: Get credentials from environment variables

##### Connection Testing Methods

- `test_connection()`: Test connection to destination
- `_test_s3_connection()`: Test AWS S3 connection
- `_test_azure_connection()`: Test Azure Blob Storage connection
- `_test_gcs_connection()`: Test Google Cloud Storage connection
- `_test_google_drive_connection()`: Test Google Drive connection

## Security Features

### Credential Encryption

- All credentials encrypted using tenant-specific encryption keys
- Uses existing `EncryptionService` with AES-256-GCM
- Credentials stored as encrypted text in database
- Never returned in plain text via API

### Tenant Isolation

- All operations scoped to tenant_id
- Database queries filtered by tenant
- Encryption keys are tenant-specific

### Credential Masking

- API responses show only last 4 characters of sensitive values
- Full credentials only accessible via `get_decrypted_credentials()`

## Environment Variable Fallback

When no credentials are configured in the database, the service falls back to environment variables:

### S3

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (default: us-east-1)
- `AWS_S3_BUCKET`
- `AWS_S3_PATH_PREFIX` (optional)

### Azure

- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER`
- `AZURE_STORAGE_PATH_PREFIX` (optional)

### GCS

- `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON)
- `GCS_BUCKET_NAME`
- `GCS_PATH_PREFIX` (optional)

### Google Drive

- No environment variable fallback (OAuth2 required)

## Storage Philosophy & Strictness

It is important to distinguish between **Application-Level Cloud Storage** and **Advanced Export Destinations**.

### 1. Application-Level Cloud Storage (`cloud_storage`)

- **Purpose**: Internal storage for the application (invoices, receipts, attachments).
- **Control**: Managed by system administrators via server environment variables.
- **Fallback**: Defaults to **Local File Storage** if no cloud provider is configured.
- **Usage**: Always active for core app operations.

### 2. Advanced Export Destinations (`advanced_export`)

- **Purpose**: User-controlled data portability (exporting batch results to external buckets).
- **Control**: Managed by end-users (admins) via the **Export Destinations** settings tab.
- **Strictness**: **A configuration record MUST exist in the database** to trigger an export. The system will NOT automatically use the application's internal storage settings if no export destination is configured.
- **Fallback Strategy**:
  - **UI Config + UI Credentials**: Uses credentials provided in the UI (stored encrypted).
  - **UI Config + Empty Credentials**: Triggers the **Environment Variable Fallback**. It will use the `AWS_S3_*`, `AZURE_STORAGE_*`, or `GCS_*` variables from the server to authenticate.
  - **No UI Config**: Export fails.

| Scenario                                  | Export Behavior                                                |
| :---------------------------------------- | :------------------------------------------------------------- |
| **No Destination set in UI**              | **Error**. System will not guess/fallback to internal storage. |
| **Destination set, Credentials empty**    | **Env Fallback**. Uses server environment variables.           |
| **Destination set, Credentials provided** | **Direct Use**. Uses the specific keys provided in the UI.     |

## Connection Testing

Each destination type has a specific connection test:

- **S3**: Attempts to list bucket contents (max 1 object)
- **Azure**: Attempts to list container blobs (max 1)
- **GCS**: Attempts to list bucket blobs (max 1)
- **Google Drive**: Attempts to get folder metadata and verify it's a folder

Test results are stored in the database:

- `last_test_at`: Timestamp of last test
- `last_test_success`: Boolean success status
- `last_test_error`: Error message if failed

## Usage Examples

### Creating a Destination

```python
from services.export_destination_service import ExportDestinationService

service = ExportDestinationService(db, tenant_id=1)

# Create S3 destination
destination = service.create_destination(
    name="Production S3",
    destination_type="s3",
    credentials={
        "access_key_id": "AKIA...",
        "secret_access_key": "...",
        "region": "us-east-1",
        "bucket_name": "my-exports",
        "path_prefix": "batch-results/"
    },
    user_id=1,
    is_default=True
)
```

### Testing Connection

```python
success, error = await service.test_connection(destination.id)
if success:
    print("Connection successful!")
else:
    print(f"Connection failed: {error}")
```

### Getting Decrypted Credentials

```python
credentials = service.get_decrypted_credentials(destination.id)
# Use credentials for export operations
```

### Listing Destinations

```python
# List all active destinations
destinations = service.list_destinations(active_only=True)

# List only S3 destinations
s3_destinations = service.list_destinations(destination_type="s3")
```

## Database Model

The service uses the `ExportDestinationConfig` model from `api/models/models_per_tenant.py`:

```python
class ExportDestinationConfig(Base):
    id: int
    tenant_id: int
    name: str
    destination_type: str  # s3, azure, gcs, google_drive
    is_active: bool
    is_default: bool
    encrypted_credentials: str  # Encrypted JSON blob
    config: dict  # Additional configuration
    last_test_at: datetime
    last_test_success: bool
    last_test_error: str
    created_at: datetime
    updated_at: datetime
    created_by: int
```

## Dependencies

### Python Packages Required

```text
boto3  # For AWS S3
azure-storage-blob  # For Azure Blob Storage
google-cloud-storage  # For Google Cloud Storage
google-api-python-client  # For Google Drive
google-auth  # For Google authentication
```

### Internal Dependencies

- `services.encryption_service.EncryptionService`
- `services.key_management_service.KeyManagementService`
- `models.models_per_tenant.ExportDestinationConfig`
- `schemas.export_destination.*`

## Error Handling

The service raises appropriate exceptions:

- `ValueError`: Invalid input or destination not found
- `EncryptionError`: Credential encryption failed
- `DecryptionError`: Credential decryption failed

All errors are logged with appropriate context for debugging.

## Logging

The service logs:

- Destination creation/updates/deletions
- Connection test results
- Environment variable fallback usage
- Encryption/decryption operations
- All errors with full context

## Next Steps

To complete the batch processing feature, the following components need to be implemented:

1. **API Endpoints** (Task 3): REST endpoints for destination management
2. **UI Components** (Task 4): Settings page for destination configuration
3. **Batch Processing Service** (Task 5): Core batch processing logic
4. **Export Service** (Task 7): CSV generation and upload to destinations

## Testing

Unit tests should cover:

- Credential encryption/decryption
- Connection testing for each provider
- Environment variable fallback
- Tenant isolation
- Error handling

Integration tests should verify:

- End-to-end destination creation and testing
- Actual connections to cloud providers (with test credentials)
- Credential masking in API responses
