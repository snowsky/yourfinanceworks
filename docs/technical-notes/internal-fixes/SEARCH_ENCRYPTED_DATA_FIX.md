# Search Encrypted Data Fix

## Problem
Global search was displaying encrypted client data (base64-encoded strings) instead of decrypted client names in search results.

## Root Cause
When client data failed to decrypt or was stored in encrypted form, the search service was indexing and displaying the raw encrypted values without sanitization.

## Solution
Implemented encryption detection and sanitization in the search service:

### 1. Added Helper Functions
- `_looks_like_encrypted_data()`: Detects base64-encoded encrypted data by checking:
  - String length (>30 characters)
  - Base64 pattern matching
  - Absence of common plaintext patterns (spaces, email format)
  
- `_sanitize_value()`: Replaces detected encrypted data with a fallback value (e.g., "Unknown")

### 2. Applied Sanitization in Key Locations
- **OpenSearch Indexing**:
  - `index_invoice()`: Sanitizes `client_name` in both document fields and `searchable_text`
  - `index_payment()`: Sanitizes `client_name` in both document fields and `searchable_text`
  
- **Database Fallback Search**:
  - `_database_fallback_search()`: Sanitizes `client_name` when OpenSearch is unavailable

### 3. Fixed Field Name
- Changed `total_amount` to `amount` in search router to match the actual data structure

## Files Modified
- `api/core/services/search_service.py`: Added encryption detection and sanitization
- `api/core/routers/search.py`: Fixed field name from `total_amount` to `amount`
- `api/scripts/test_search_encryption_fix.py`: Created validation test script

## Testing
Run the validation script:
```bash
docker-compose exec api python scripts/test_search_encryption_fix.py
```

All tests pass:
- ✓ Encryption detection (7/7 tests)
- ✓ Value sanitization (5/5 tests)

## Deployment Steps

### 1. Restart API Server
```bash
docker-compose restart api
```

### 2. Reindex Search Data
After the API restarts, reindex all search data to apply the fix to existing records:

**Via API:**
```bash
curl -X POST http://localhost:8000/api/search/reindex \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Or via UI:**
Navigate to Settings → Advanced → Reindex Search Data

### 3. Verify Fix
1. Open the global search (Cmd/Ctrl + K)
2. Search for invoices
3. Verify that client names display properly (not encrypted strings)

## Expected Behavior
- **Before**: `Client: EIMkyGgKc7ZOg1QlBodtUO2X6WpRNUXm2CbGgMeZvMM= • $0`
- **After**: `Client: Unknown • $0` (or actual client name if decryption works)

## Notes
- The fix is defensive - it detects and replaces encrypted data at display time
- The root cause of why data is encrypted should still be investigated separately
- This prevents sensitive encrypted data from being exposed in search results
- The "Unknown" fallback provides a better user experience than showing encrypted strings

## Related Issues
- Encryption key management
- Client data decryption failures
- Search indexing pipeline
