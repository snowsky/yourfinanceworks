# Expense Amount Consistency Fix

## Problem

When creating an expense with an initial amount (e.g., $10) and then uploading a receipt that AI extracts a different total (e.g., $15.79), the expense would show inconsistent values:

- **Amount**: $10.00 (original user input - not updated)
- **Total**: $15.79 (AI extracted from receipt)

This created confusion because:
1. The two fields showed different values
2. The receipt's actual total wasn't reflected in the amount
3. Users expected the AI to correct their initial estimate

## Root Cause

The OCR service had logic that **preserved the user's original amount**:

```python
# Old logic - only update if amount is None or 0
expense.amount = amt if expense.amount in (None, 0) else expense.amount
```

This meant:
- If user entered $10, it stayed $10
- But `total_amount` was updated to $15.79 from the receipt
- Result: Inconsistent data

## Solution

Changed the logic to **conditionally update amount based on AI extraction**:

```python
# New logic - only update if AI extracted an amount
if tt is not None:
    # AI found explicit total - override both
    expense.amount = tt
    expense.total_amount = tt
elif extracted_amount is not None:
    # AI found an amount - override amount
    expense.amount = extracted_amount
    if expense.total_amount in (None, 0):
        expense.total_amount = extracted_amount
# else: AI didn't extract amount - keep original user input
```

## Behavior After Fix

### Scenario 1: AI extracts amount from receipt
1. User creates expense with amount = $10
2. User uploads receipt
3. AI extracts total = $15.79
4. **Both `amount` and `total_amount` are updated to $15.79** ✅

### Scenario 2: AI cannot extract amount from receipt
1. User creates expense with amount = $10
2. User uploads receipt (poor quality, no clear total)
3. AI cannot extract amount (returns null)
4. **Amount stays $10** (original user input preserved) ✅

### Scenario 3: Create expense without amount, AI extracts it
1. User creates expense with amount = 0 or None
2. User uploads receipt
3. AI extracts total = $15.79
4. **Both `amount` and `total_amount` are set to $15.79** ✅

### Scenario 4: Receipt has subtotal and total with tax
1. User uploads receipt
2. AI extracts:
   - Subtotal: $14.00
   - Tax: $1.79
   - Total: $15.79
3. **Both `amount` and `total_amount` are set to $15.79** (the total) ✅

## Fields Explained

- **`amount`**: The base expense amount (before tax, or the total if no tax breakdown)
- **`total_amount`**: The final total including tax
- **`tax_amount`**: The tax portion
- **`tax_rate`**: The tax rate percentage

After this fix:
- If receipt has a clear total, both `amount` and `total_amount` are set to that total
- This ensures consistency in the UI
- Users see the actual receipt amount, not their initial estimate

## Why This Is Better

1. **Consistency**: Amount and total always match (or total = amount + tax)
2. **Accuracy**: Receipt data takes precedence over user estimates
3. **Trust**: Users trust AI to extract the correct amount
4. **Simplicity**: No confusion about which field to look at

## Edge Cases

### What if user wants to keep their original amount?
- They can manually edit the expense after AI processing
- The `manual_override` flag prevents further AI updates

### What if AI extracts wrong amount?
- User can manually correct it
- Set `manual_override = true` to prevent AI from changing it again

### What if receipt has both subtotal and total?
- AI extracts both
- `total_amount` gets the total (with tax)
- `amount` also gets the total for consistency
- `tax_amount` stores the tax portion

## Testing

To verify the fix:

1. **Create expense with initial amount**:
   ```
   POST /expenses
   {
     "amount": 10.00,
     "currency": "USD",
     "category": "Other"
   }
   ```

2. **Upload receipt with different total**:
   ```
   POST /expenses/{id}/attachments
   (Upload receipt showing $15.79)
   ```

3. **Wait for AI processing**

4. **Verify both fields updated**:
   ```
   GET /expenses/{id}
   {
     "amount": 15.79,      // Updated to match receipt
     "total_amount": 15.79, // Updated to match receipt
     "tax_amount": 1.79,    // If extracted
     ...
   }
   ```

## Migration

Existing expenses are not affected - this only applies to new OCR processing.

If you want to reprocess existing expenses:
1. Set `analysis_status = 'pending'`
2. Re-upload the receipt
3. AI will reprocess and update amounts

## Related Files

- `api/services/ocr_service.py` - OCR processing logic
- `api/schemas/expense.py` - Expense schema definitions
- `api/models/models_per_tenant.py` - Expense model
