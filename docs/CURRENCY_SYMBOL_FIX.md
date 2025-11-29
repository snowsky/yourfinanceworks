# Currency Symbol Validation Fix

## Problem

Expense 115 was failing to update with a 400 Bad Request error. Investigation revealed that the expense had "$" stored in the `currency` field instead of the proper ISO currency code "USD".

### Root Cause

The OCR/AI extraction service was extracting currency symbols (like "$", "€", "£") from receipts and saving them directly to the database without converting them to ISO currency codes. This caused validation errors when trying to update these expenses.

## Solution

### 1. Fixed the Specific Expense

```sql
UPDATE expenses SET currency = 'USD' WHERE id = 115;
```

### 2. Added Currency Symbol Mapping

Updated three locations to handle currency symbol conversion:

#### a. OCR Service - Simple Extraction (`api/core/services/ocr_service.py` line ~354)
Added comprehensive currency symbol mapping when extracting from amount patterns:
- `$` → `USD`
- `€` → `EUR`
- `£` → `GBP`
- And 15+ other common currency symbols

#### b. OCR Service - AI Extraction (`api/core/services/ocr_service.py` line ~1604)
Added validation and conversion logic when AI extracts currency:
- Converts symbols to ISO codes
- Validates 3-letter ISO codes
- Defaults to USD for unknown formats

#### c. Pydantic Schema Validation (`api/core/schemas/expense.py`)
Added `@field_validator('currency')` to both `ExpenseBase` and `ExpenseUpdate`:
- Automatically converts currency symbols to ISO codes
- Validates ISO code format (3 letters, alphabetic)
- Provides clear error messages for invalid formats

### 3. Enhanced Error Logging

Added detailed logging in `api/main.py` and `api/core/routers/expenses.py`:
- Logs Pydantic validation errors with full details
- Shows request body and validation errors
- Makes debugging much easier

## Supported Currency Symbols

| Symbol | ISO Code | Currency |
|--------|----------|----------|
| $ | USD | US Dollar |
| € | EUR | Euro |
| £ | GBP | British Pound |
| ¥ | JPY/CNY | Japanese Yen / Chinese Yuan |
| ₹ | INR | Indian Rupee |
| C$ | CAD | Canadian Dollar |
| A$ | AUD | Australian Dollar |
| NZ$ | NZD | New Zealand Dollar |
| HK$ | HKD | Hong Kong Dollar |
| S$ | SGD | Singapore Dollar |
| R$ | BRL | Brazilian Real |
| R | ZAR | South African Rand |
| ₽ | RUB | Russian Ruble |
| ₩ | KRW | South Korean Won |
| ₺ | TRY | Turkish Lira |
| kr | SEK | Swedish Krona |
| CHF | CHF | Swiss Franc |

## Migration Script

Created `api/scripts/fix_currency_symbols.py` to fix any existing expenses with currency symbols:

```bash
docker exec invoice_app_api python scripts/fix_currency_symbols.py
```

This script:
- Scans all tenant databases
- Finds expenses with currency symbols
- Converts them to proper ISO codes
- Reports on all changes made

## Testing

### Manual Test
```bash
docker exec invoice_app_api python -c "
import sys; sys.path.insert(0, '/app')
from core.schemas.expense import ExpenseUpdate
e = ExpenseUpdate(currency='$')
print(f'Symbol $ converted to: {e.currency}')
"
```

Expected output: `Symbol $ converted to: USD`

### API Test
Try updating expense 115 from the UI - it should now work without errors.

## Prevention

Going forward:
1. All currency symbols are automatically converted to ISO codes at the schema level
2. OCR extraction converts symbols before saving
3. Invalid currency codes are rejected with clear error messages
4. Validation happens at multiple layers (schema, service, database)

## Files Changed

- `api/core/services/ocr_service.py` - Added currency symbol mapping in 2 locations
- `api/core/schemas/expense.py` - Added currency validation to ExpenseBase and ExpenseUpdate
- `api/main.py` - Added RequestValidationError handler for better error logging
- `api/core/routers/expenses.py` - Enhanced error logging in update_expense endpoint
- `api/scripts/fix_currency_symbols.py` - Migration script to fix existing data
- `api/scripts/test_currency_validation.py` - Test script for validation
- `api/scripts/test_expense_update.py` - Debug script for expense updates

## Impact

- ✅ Expense 115 can now be updated successfully
- ✅ Future OCR extractions will use proper ISO codes
- ✅ Better error messages for invalid currency codes
- ✅ Automatic conversion of common currency symbols
- ✅ No breaking changes - existing valid ISO codes work as before
