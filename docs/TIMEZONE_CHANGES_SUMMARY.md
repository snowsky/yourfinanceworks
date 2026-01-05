# Timezone-Aware Timestamps Implementation

## Summary
Added tenant-specific timezone support for all entity timestamps with seconds precision across the entire application.

## Changes Made

### 1. Created Timezone Utility Module
**File**: `api/core/utils/timezone.py`

- `get_tenant_timezone(db)`: Retrieves tenant timezone setting from database (defaults to UTC)
- `get_tenant_timezone_aware_datetime(db)`: Returns current datetime in tenant timezone with seconds precision
- `convert_to_tenant_timezone(dt, db)`: Converts any datetime to tenant timezone

Features:
- Uses tenant's timezone setting from Settings table with key "timezone"
- Falls back to UTC if setting not found or invalid
- Handles missing pytz dependency gracefully
- Rounds microseconds to seconds precision (>= 500000 rounds up, < 500000 rounds down)
- Proper error handling and logging

### 2. Updated Expense Router
**File**: `api/core/routers/expenses.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments to use tenant timezone:
  - Single expense creation (`created_at`, `updated_at`)
  - Bulk expense creation (`created_at`, `updated_at`)
  - Bulk label updates (`updated_at`)
  - Expense updates (`updated_at`)
  - Expense soft delete (`deleted_at`, `updated_at`)
  - Expense restore (`updated_at`)
  - Single expense delete (`deleted_at`, `updated_at`)
  - Attachment uploads (`updated_at`)

### 3. Updated Invoice Router
**File**: `api/core/routers/invoices.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments:
  - Invoice creation (`created_at`, `updated_at`)
  - Invoice cloning (`created_at`, `updated_at`)
  - Bulk label updates (`updated_at`)
  - Invoice restore (`updated_at`)
  - Invoice updates (`updated_at`)
  - Invoice item updates (`updated_at`)
  - Invoice soft delete (`deleted_at`, `updated_at`)
  - Attachment operations (`updated_at`)

### 4. Updated Payment Router
**File**: `api/core/routers/payments.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments:
  - Payment creation (`created_at`, `updated_at`)
  - Payment updates (`updated_at`)

### 5. Updated Client Router
**File**: `api/core/routers/clients.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments:
  - Client creation (`created_at`, `updated_at`)
  - Client updates (`updated_at`)
  - Bulk label updates (`updated_at`)

### 6. Updated Statements Router
**File**: `api/core/routers/statements.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments:
  - Statement processing (`analysis_updated_at`)
  - Bulk label updates (`updated_at`)
  - Statement restore (`updated_at`)
  - Statement soft delete (`deleted_at`, `updated_at`)

### 7. Updated Currency Router
**File**: `api/core/routers/currency.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all timestamp assignments:
  - Currency rate creation/updates (`updated_at`)
  - Supported currency operations (`updated_at`)

### 8. Updated OCR Service
**File**: `api/core/services/ocr_service.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated `analysis_updated_at` assignment to use tenant timezone

### 9. Updated OCR Consumer
**File**: `api/workers/ocr_consumer.py`

- Added import: `from core.utils.timezone import get_tenant_timezone_aware_datetime`
- Updated all `analysis_updated_at` assignments for bank statements to use tenant timezone

### 10. Updated UI Components
**Files**: `ui/src/pages/Expenses.tsx`, `ui/src/pages/Invoices.tsx`, `ui/src/pages/Statements.tsx`

- Added timezone settings fetching and locale-aware formatting
- **Expenses Page**: Added new "Created" column displaying `created_at` in tenant timezone
- **Invoices Page**: Updated `created_at` and `due_date` columns to use tenant timezone formatting
- **Statements Page**: Updated `created_at` column and detail view to use tenant timezone formatting
- All date displays now use `toLocaleString()` with tenant timezone and proper locale settings

## Benefits

1. **Tenant-Specific Timezones**: Each tenant can set their preferred timezone
2. **Seconds Precision**: Timestamps now have consistent seconds precision instead of microseconds
3. **Backward Compatibility**: Falls back to UTC if timezone not set
4. **Graceful Degradation**: Works even if pytz is not available
5. **Comprehensive Coverage**: All entity timestamps use tenant timezone
6. **Consistent Behavior**: All CRUD operations across all entities use the same timezone logic
7. **UI Display**: All timestamps in the UI now display in tenant's timezone with proper formatting

## Usage

### Setting Tenant Timezone
The timezone can be set via the settings API with key "timezone":
```json
{
  "timezone": "America/New_York"
}
```

### Automatic Usage
All entity creation and updates will automatically use the tenant's timezone for timestamps:
- New entities get `created_at` in tenant timezone
- All updates get `updated_at` in tenant timezone
- OCR processing updates get `analysis_updated_at` in tenant timezone
- Soft deletes get `deleted_at` in tenant timezone
- Currency rates get `updated_at` in tenant timezone

### UI Display
All timestamps in the user interface now automatically display in the tenant's configured timezone:
- **Expenses Table**: Added "Created" column showing `created_at` in tenant timezone
- **Invoices Table**: Updated `created_at` and `due_date` columns to use tenant timezone
- **Statements Table**: Updated `created_at` column and detail view to use tenant timezone
- **Date Formatting**: Uses locale-aware formatting with proper timezone conversion

## Entities Updated
- **Expenses**: All CRUD operations, bulk operations, attachments, OCR processing
- **Invoices**: Creation, updates, cloning, items, attachments, soft delete/restore
- **Payments**: Creation and updates
- **Clients**: Creation, updates, bulk label operations
- **Bank Statements**: Processing, updates, soft delete/restore
- **Currency Rates**: Creation and updates
- **Supported Currencies**: Creation and updates

## Testing

Created comprehensive unit tests that verify:
- Default timezone (UTC) when no setting exists
- Custom timezone retrieval from settings
- Empty/invalid timezone handling
- Seconds precision rounding
- Graceful fallback when pytz unavailable
- Datetime conversion functionality

All tests pass successfully, confirming the implementation works correctly.

## Database Schema Impact

No schema changes required. The existing `DateTime(timezone=True)` columns in all models continue to work as before, but now receive timezone-aware values instead of UTC-only values.

## Migration Notes

- Existing entities will continue to work with their original UTC timestamps
- New entities will use tenant timezone
- The change is transparent to existing API consumers
- No data migration required
- All routers now consistently use the same timezone utility
