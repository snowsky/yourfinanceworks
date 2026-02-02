# Cross-Storage Attachment Synchronization

## Overview

The synchronization system supports **storage-agnostic data transfer**, enabling sync between instances with different storage configurations (e.g., source with S3, target with local storage).

## Quick Reference: When Are Files Transferred?

| Source Storage     | Target Storage     | Files Transferred? | Optimization          |
| ------------------ | ------------------ | ------------------ | --------------------- |
| **Same S3 bucket** | **Same S3 bucket** | ❌ **NO**          | ⚡ Auto-skipped       |
| **S3**             | **Local**          | ✅ Yes             | ⬇️ Downloaded from S3 |
| **S3 bucket A**    | **S3 bucket B**    | ✅ Yes             | ⬇️⬆️ Cloud-to-cloud   |
| **Local**          | **S3**             | ✅ Yes             | ⬆️ Uploaded to S3     |
| **Local**          | **Local**          | ✅ Yes             | 📦 Direct transfer    |

**Key Insight**: Files are only skipped when **both instances share the exact same cloud storage** (same bucket/container).

## How It Works

### Storage Identity Detection

The system uses **storage fingerprinting** to detect whether instances share the same storage backend:

```python
# From sync_service.py
def get_storage_identity() -> Dict[str, Any]:
    """Generate a unique fingerprint for the storage configuration."""
    identity = {"type": "local"}

    # Check for cloud storage configuration
    if cloud_config.CLOUD_STORAGE_ENABLED:
        if cloud_config.PRIMARY_PROVIDER == "aws_s3":
            identity = {
                "type": "s3",
                "bucket": cloud_config.AWS_S3_BUCKET_NAME,
                "region": cloud_config.AWS_REGION
            }
        # Similar for Azure, GCP...

    return identity
```

### Automatic Optimization (Shared Storage)

When both instances use the **same cloud storage**:

```python
# From sync.py router
if local_storage == remote_storage:
    logger.info("Shared cloud storage detected. Skipping attachment transfer.")
    actual_include_attachments = False  # Skip file transfer
```

### Cloud-to-Local Pre-fetching

When storage configurations **differ**, the system pre-fetches cloud files before packaging:

```python
# From sync_service.py
async def _ensure_attachments_on_disk(db: Session, tenant_id: int):
    """Download missing cloud files to local disk before packaging."""

    for model, fields in attachment_models:
        for record in db.query(model).all():
            file_key = getattr(record, field)
            local_path = Path("attachments") / file_key

            if not local_path.exists():
                # Download from cloud storage
                result = await cloud_service.retrieve_file(
                    file_key=file_key,
                    tenant_id=str(tenant_id),
                    user_id=0,
                    generate_url=False
                )

                # Write to local disk
                if result.success and result.file_content:
                    with open(local_path, 'wb') as f:
                        f.write(result.file_content)
```

## Detailed Scenarios

### Scenario 1: Both Instances Share Same Cloud Storage

**Example**: Both configured with `AWS_S3_BUCKET_NAME=my-shared-bucket`

- **Detection**: Storage identity fingerprints match
- **Packaging**: Attachments automatically skipped
- **Transfer**: Only database records
- **Result**: Fast sync, minimal bandwidth
- **Requirements**: Cloud credentials on both sides

### Scenario 2: Source with Cloud, Target without Cloud

**Example**: Source has S3 credentials, target uses local storage

- **Detection**: Storage identities differ (cloud vs local)
- **Packaging**: Cloud files downloaded to local disk, then zipped
- **Transfer**: ZIP contains file bytes
- **Extraction**: Files written to target's `attachments/` folder
- **Result**: Target can access files locally without cloud credentials
- **Requirements**: Cloud credentials only on source

### Scenario 3: Different Cloud Storage Buckets

**Example**: Source uses `s3://bucket-a`, target uses `s3://bucket-b`

- **Detection**: Storage identities differ (different buckets)
- **Packaging**: Files downloaded from source cloud, zipped
- **Transfer**: ZIP contains file bytes
- **Extraction**: Files uploaded to target's cloud storage
- **Result**: Each instance maintains its own cloud storage
- **Requirements**: Cloud credentials on both sides (different configs)

### Scenario 4: Both Use Local Storage

**Example**: Both instances use local storage on different servers

- **Detection**: Storage identities differ (different paths)
- **Packaging**: Local files zipped directly
- **Transfer**: ZIP contains file bytes
- **Extraction**: Files written to target's local folder
- **Result**: Standard file transfer
- **Requirements**: No cloud credentials needed

## Implementation Details

### Modified Components

1. **`SyncService._ensure_attachments_on_disk`** (NEW)
   - Pre-fetches cloud files to local disk
   - Handles 8 attachment models (Invoices, Expenses, Bank Statements, Items, etc.)

2. **`SyncService.package_data`** (UPDATED)
   - Now `async` to support cloud downloads
   - Calls pre-fetch logic when `include_attachments=True`

3. **`StorageResult`** (UPDATED)
   - Added `file_content: Optional[bytes]` field
   - All providers return file bytes for sync

4. **Cloud Storage Providers** (UPDATED)
   - AWS S3, Azure Blob, GCP Storage, Local Storage
   - All `download_file` methods populate `file_content`

### Attachment Models Covered

- `ExpenseAttachment` (file_path)
- `BankStatementAttachment` (file_path)
- `ItemAttachment` (file_path, thumbnail_path)
- `InvoiceAttachment` (file_path)
- `BankStatement` (file_path)
- `ReportHistory` (file_path)
- `InvoiceProcessingTask` (file_path)
- `BatchFileProcessing` (file_path)

## Usage Examples

### Example 1: Sync from S3 to Local

```bash
# Source instance (with S3)
export AWS_S3_BUCKET_NAME=my-bucket
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Target instance (local only)
# No cloud credentials needed

# Perform sync via UI or API
# Result: All S3 files downloaded and transferred to target
```

### Example 2: Sync with Shared S3

```bash
# Both instances
export AWS_S3_BUCKET_NAME=shared-bucket
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Perform sync via UI or API
# Result: Only database synced, files already accessible
```

## Benefits

1. **Storage Flexibility**: Sync works regardless of storage configuration differences
2. **No Credential Sharing**: Target doesn't need cloud credentials (scenario 2)
3. **Offline Capability**: Target can operate fully offline with local files
4. **Automatic Optimization**: Skips file transfer when storage is shared
5. **Backward Compatible**: Existing sync behavior unchanged

## Testing

### Manual Verification

1. **Setup instances with different storage configs**
2. **Upload attachments on source**
3. **Perform sync push**
4. **Verify on target**:
   - Check `attachments/tenant_X/` directory
   - Open PDF previews
   - Download attachments
   - All should work without cloud credentials

### Automated Testing

```python
async def test_cross_storage_sync():
    # Upload to S3 on source
    source_result = await source_cloud_service.store_file(...)

    # Package data (downloads from S3)
    package_bytes = await SyncService.package_data(source_db, tenant_id)

    # Apply to target (local only)
    SyncService.apply_package(package_bytes, tenant_id)

    # Verify file exists locally
    assert Path(f"attachments/tenant_{tenant_id}/...").exists()
```

## Related Documentation

- [Attachment Migration Plan](./attachment_migration_plan.md)
- [Sync Architectural Scope](../../.gemini/antigravity/brain/105db6a1-5b28-40b5-a978-ce7b91a3342b/sync_architectural_scope.md)
- [Sync Usage Recommendations](../../.gemini/antigravity/brain/105db6a1-5b28-40b5-a978-ce7b91a3342b/sync_usage_recommendations.md)
