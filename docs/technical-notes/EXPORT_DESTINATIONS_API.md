# Export Destinations API Documentation

## Overview

The Export Destinations API provides endpoints for managing cloud storage export configurations. It supports AWS S3, Azure Blob Storage, Google Cloud Storage, and Google Drive as export destinations for batch file processing results.

## Base URL

```
/api/v1/export-destinations
```

## Authentication

All endpoints require JWT authentication via the `Authorization: Bearer <token>` header. The authenticated user must belong to a tenant and have appropriate permissions.

### Permission Requirements

- **Create/Update**: Non-viewer role (editor, admin)
- **Read/List**: Any authenticated user
- **Delete**: Admin role only
- **Test**: Any authenticated user

## Endpoints

### 1. Create Export Destination

Create a new export destination configuration with encrypted credentials.

**Endpoint:** `POST /api/v1/export-destinations`

**Request Body:**

```json
{
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "credentials": {
    "access_key_id": "AKIA...",
    "secret_access_key": "...",
    "region": "us-east-1",
    "bucket_name": "my-exports",
    "path_prefix": "batch-results/"
  },
  "config": {
    "retention_days": 30
  },
  "is_default": false
}
```

**Destination Types:**

- `s3` - AWS S3
- `azure` - Azure Blob Storage
- `gcs` - Google Cloud Storage
- `google_drive` - Google Drive

**Response:** `201 Created`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": false,
  "config": {
    "retention_days": 30
  },
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****key1",
    "region": "****st-1",
    "bucket_name": "****orts",
    "path_prefix": "****lts/"
  },
  "last_test_at": null,
  "last_test_success": null,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:30:00Z",
  "created_by": 1
}
```

### 2. List Export Destinations

List all export destinations for the authenticated tenant.

**Endpoint:** `GET /api/v1/export-destinations`

**Query Parameters:**

- `active_only` (boolean, optional): Filter to only active destinations
- `destination_type` (string, optional): Filter by destination type
- `skip` (integer, optional, default: 0): Pagination offset
- `limit` (integer, optional, default: 100): Pagination limit

**Response:** `200 OK`

```json
{
  "destinations": [
    {
      "id": 1,
      "tenant_id": 1,
      "name": "Production S3 Bucket",
      "destination_type": "s3",
      "is_active": true,
      "is_default": true,
      "config": {},
      "masked_credentials": {
        "access_key_id": "****AKIA",
        "secret_access_key": "****key1"
      },
      "last_test_at": "2025-11-08T10:35:00Z",
      "last_test_success": true,
      "last_test_error": null,
      "created_at": "2025-11-08T10:30:00Z",
      "updated_at": "2025-11-08T10:35:00Z",
      "created_by": 1
    }
  ],
  "total": 1
}
```

### 3. Get Export Destination

Get a specific export destination by ID.

**Endpoint:** `GET /api/v1/export-destinations/{destination_id}`

**Response:** `200 OK`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Production S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": true,
  "config": {},
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****key1"
  },
  "last_test_at": "2025-11-08T10:35:00Z",
  "last_test_success": true,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:35:00Z",
  "created_by": 1
}
```

### 4. Update Export Destination

Update an existing export destination configuration.

**Endpoint:** `PUT /api/v1/export-destinations/{destination_id}`

**Request Body:**

```json
{
  "name": "Updated S3 Bucket",
  "credentials": {
    "access_key_id": "AKIA...",
    "secret_access_key": "..."
  },
  "is_active": true
}
```

**Note:** You can update individual fields without providing all fields. Credentials will be re-encrypted after update.

**Response:** `200 OK`

```json
{
  "id": 1,
  "tenant_id": 1,
  "name": "Updated S3 Bucket",
  "destination_type": "s3",
  "is_active": true,
  "is_default": true,
  "config": {},
  "masked_credentials": {
    "access_key_id": "****AKIA",
    "secret_access_key": "****key2"
  },
  "last_test_at": "2025-11-08T10:35:00Z",
  "last_test_success": true,
  "last_test_error": null,
  "created_at": "2025-11-08T10:30:00Z",
  "updated_at": "2025-11-08T10:40:00Z",
  "created_by": 1
}
```

### 5. Test Export Destination Connection

Test connection to an export destination using stored credentials.

**Endpoint:** `POST /api/v1/export-destinations/{destination_id}/test`

**Response:** `200 OK`

```json
{
  "success": true,
  "message": "Connection test successful",
  "error_details": null,
  "tested_at": "2025-11-08T10:45:00Z"
}
```

**Error Response:**

```json
{
  "success": false,
  "message": "Connection test failed",
  "error_details": "S3 error (AccessDenied): Access Denied",
  "tested_at": "2025-11-08T10:45:00Z"
}
```

### 6. Delete Export Destination

Soft delete an export destination (sets `is_active=false`).

**Endpoint:** `DELETE /api/v1/export-destinations/{destination_id}`

**Response:** `204 No Content`

**Note:** This endpoint requires admin permissions and validates that no active batch jobs are using this destination.

## Credential Schemas

### AWS S3 Credentials

```json
{
  "access_key_id": "string",
  "secret_access_key": "string",
  "region": "string",
  "bucket_name": "string",
  "path_prefix": "string (optional)"
}
```

### Azure Blob Storage Credentials (Connection String)

```json
{
  "connection_string": "string",
  "container_name": "string",
  "path_prefix": "string (optional)"
}
```

### Azure Blob Storage Credentials (Account Key)

```json
{
  "account_name": "string",
  "account_key": "string",
  "container_name": "string",
  "path_prefix": "string (optional)"
}
```

### Google Cloud Storage Credentials (Service Account)

```json
{
  "service_account_json": "string (JSON content)",
  "bucket_name": "string",
  "path_prefix": "string (optional)"
}
```

### Google Drive Credentials

```json
{
  "oauth_token": "string",
  "refresh_token": "string",
  "folder_id": "string"
}
```

## Environment Variable Fallback

If no credentials are configured for a destination, the system will attempt to use environment variables as fallback:

### S3 Fallback Variables

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `AWS_S3_BUCKET`
- `AWS_S3_PATH_PREFIX` (optional)

### Azure Fallback Variables

- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER`
- `AZURE_STORAGE_PATH_PREFIX` (optional)

### GCS Fallback Variables

- `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON file)
- `GCS_BUCKET_NAME`
- `GCS_PATH_PREFIX` (optional)

**Note:** Google Drive does not support environment variable fallback (OAuth2 required).

## Security

### Credential Encryption

All credentials are encrypted using tenant-specific encryption keys before storage. The encryption is handled by the `EncryptionService` which uses the tenant's encryption key from the `KeyManagementService`.

### Credential Masking

When credentials are returned in API responses, they are masked to show only the last 4 characters:

```
"access_key_id": "****AKIA"
```

### Audit Logging

All operations (create, update, delete, test) are logged to the audit log with:

- User ID and email
- Action type
- Resource type and ID
- Timestamp
- Operation status

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid destination type. Must be one of: s3, azure, gcs, google_drive"
}
```

### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

```json
{
  "detail": "Insufficient permissions to create export destinations"
}
```

### 404 Not Found

```json
{
  "detail": "Export destination 123 not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Failed to create export destination"
}
```

## Usage Examples

### Create S3 Destination

```bash
curl -X POST "http://localhost:8000/api/v1/export-destinations" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production S3",
    "destination_type": "s3",
    "credentials": {
      "access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "region": "us-east-1",
      "bucket_name": "my-exports"
    },
    "is_default": true
  }'
```

### List Destinations

```bash
curl -X GET "http://localhost:8000/api/v1/export-destinations?active_only=true" \
  -H "Authorization: Bearer <token>"
```

### Test Connection

```bash
curl -X POST "http://localhost:8000/api/v1/export-destinations/1/test" \
  -H "Authorization: Bearer <token>"
```

### Update Destination

```bash
curl -X PUT "http://localhost:8000/api/v1/export-destinations/1" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Production S3",
    "is_active": true
  }'
```

### Delete Destination

```bash
curl -X DELETE "http://localhost:8000/api/v1/export-destinations/1" \
  -H "Authorization: Bearer <token>"
```

## Integration with Batch Processing

Export destinations are used by the batch file processing system to determine where to upload CSV results after processing is complete. When creating a batch processing job, you specify an `export_destination_id` which references one of these configured destinations.

The batch processing system will:

1. Retrieve the destination configuration
2. Decrypt the credentials
3. Generate the CSV results
4. Upload to the specified destination
5. Return the export URL in the job status

## Future Enhancements

- Support for additional cloud storage providers (Dropbox, OneDrive, etc.)
- Webhook notifications for connection test failures
- Automatic credential rotation
- Usage statistics and cost tracking
- Multi-region support for better performance
