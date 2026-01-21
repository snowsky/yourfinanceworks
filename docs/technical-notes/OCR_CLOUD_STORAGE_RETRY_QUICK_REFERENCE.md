# OCR Cloud Storage Retry Fix - Quick Reference

## Problem Summary
OCR worker was downloading the same file from cloud storage on every retry attempt (up to 5 times), causing excessive API calls and bandwidth usage.

## Solution Summary
Implemented local file caching after first cloud storage download. Retries now use the cached file instead of re-downloading.

## What Changed

| Component | Change | Impact |
|-----------|--------|--------|
| `ExpenseAttachment` model | Added `local_cache_path` field | Stores local path of downloaded cloud file |
| `process_attachment_inline()` | Added cache lookup logic | Checks cache before downloading from cloud |
| Database | New migration | Adds `local_cache_path` column |

## Deployment Steps

```bash
# 1. Pull latest code
git pull

# 2. Run database migration
cd api
alembic upgrade head

# 3. Restart OCR worker
# (Your deployment process)
```

## Verification

### Check Logs
```bash
# Look for cache hit messages
grep "Using cached local file" /var/log/ocr_worker.log

# Look for cache storage messages
grep "Cached local file path" /var/log/ocr_worker.log
```

### Monitor Cloud Storage
- Cloud storage API call count should decrease significantly
- Retry success rate should improve (faster processing)

### Expected Behavior

**Before Fix:**
- 5 cloud storage downloads for 5 retry attempts
- Slow retries due to download latency

**After Fix:**
- 1 cloud storage download for 5 retry attempts
- Fast retries using cached file

## Rollback

If needed, rollback the migration:

```bash
cd api
alembic downgrade -1
```

## Key Files

- **Model**: `api/core/models/models_per_tenant.py` (ExpenseAttachment class)
- **Logic**: `api/core/services/ocr_service.py` (process_attachment_inline function)
- **Migration**: `api/alembic/versions/003_add_local_cache_path_to_expense_attachments.py`

## Monitoring Metrics

Track these metrics to verify the fix:

1. **Cloud Storage API Calls**: Should decrease by ~80%
2. **OCR Retry Success Rate**: Should improve
3. **OCR Processing Time**: Should be faster on retries
4. **Cache Hit Rate**: Monitor "Using cached local file" log messages

## FAQ

**Q: Will this affect existing attachments?**
A: No. Existing attachments will have `NULL` cache paths. Cache will be populated on next OCR attempt.

**Q: What if the cached file is deleted?**
A: The system detects this and re-downloads from cloud storage automatically.

**Q: Does this work with local file uploads?**
A: Yes. Local files are used directly; cache is only used for cloud storage files.

**Q: Can I disable caching?**
A: The cache is automatic and transparent. If you need to disable it, set `local_cache_path = NULL` in the database.

## Support

For issues or questions:
1. Check logs for error messages
2. Verify migration ran successfully: `alembic current`
3. Check database: `SELECT COUNT(*) FROM expense_attachments WHERE local_cache_path IS NOT NULL;`
