# Approval Workflows UI License Handling

## Problem
When the approvals feature is not licensed, the UI was silently failing to fetch approvers. The error was caught but not displayed to the user, resulting in:
- Empty "Select Approver" dropdown
- No indication that the feature requires a license
- Confusing user experience

## Solution
Updated the UI to gracefully handle license errors and display a helpful message to users.

## Changes Made

### 1. Error Handling in API Calls
Updated three pages to detect and handle 402 Payment Required errors:
- `ui/src/pages/ExpensesEdit.tsx`
- `ui/src/pages/ExpensesNew.tsx`
- `ui/src/pages/Expenses.tsx`

Each page now:
1. Catches errors when fetching approvers
2. Detects license-related error messages
3. Sets a flag (`approvalsNotLicensed`) when the feature is not licensed
4. Clears the approvers list to prevent showing empty dropdowns

### 2. UI Feedback
When `approvalsNotLicensed` is true, the UI displays:
- An amber alert box with a warning icon
- Clear message: "Approval workflows require a commercial license. Please upgrade your license to use this feature."
- The approver selection dropdown is hidden

### 3. Implementation Details

#### State Management
```typescript
const [approvalsNotLicensed, setApprovalsNotLicensed] = useState(false);
```

#### Error Detection
```typescript
const fetchApprovers = async () => {
  try {
    const response = await approvalApi.getApprovers();
    setAvailableApprovers(response);
    setApprovalsNotLicensed(false);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    // Check if it's a license error (402 Payment Required)
    if (errorMessage.includes('not included in your current license') || 
        errorMessage.includes('requires a valid license')) {
      setApprovalsNotLicensed(true);
      setAvailableApprovers([]);
    } else {
      console.error('Failed to fetch approvers:', error);
      setAvailableApprovers([]);
    }
  }
};
```

#### UI Rendering
```typescript
{submitForApproval && (
  <div className="mt-3 space-y-3">
    {approvalsNotLicensed ? (
      <Alert className="border-amber-200 bg-amber-50">
        <AlertCircle className="h-4 w-4 text-amber-600" />
        <AlertDescription className="text-amber-800">
          Approval workflows require a commercial license. 
          Please upgrade your license to use this feature.
        </AlertDescription>
      </Alert>
    ) : (
      <>
        {/* Approver selection UI */}
      </>
    )}
  </div>
)}
```

## User Experience Flow

### Before (Broken)
1. User checks "Submit for approval"
2. "Select Approver" dropdown appears but is empty
3. No indication why it's empty
4. User is confused

### After (Fixed)
1. User checks "Submit for approval"
2. Clear message appears: "Approval workflows require a commercial license"
3. User understands they need to upgrade
4. Approver selection is hidden to prevent confusion

## Files Modified
- `ui/src/pages/ExpensesEdit.tsx`
- `ui/src/pages/ExpensesNew.tsx`
- `ui/src/pages/Expenses.tsx`

## Testing Recommendations

1. **Without License**
   - Uncheck the approvals feature or remove license
   - Try to submit an expense for approval
   - Verify the license warning appears
   - Verify the approver dropdown is hidden

2. **With License**
   - Activate a commercial license with approvals enabled
   - Try to submit an expense for approval
   - Verify the approver dropdown shows available users
   - Verify no license warning appears

3. **Error Handling**
   - Test with network errors (should show generic error in console)
   - Test with license errors (should show license warning)
   - Verify the UI remains functional in both cases

## Internationalization
The error message uses the translation key `common.feature_not_licensed` with a default fallback:
```typescript
t('common.feature_not_licensed', { 
  defaultValue: 'Approval workflows require a commercial license. Please upgrade your license to use this feature.' 
})
```

Add translations for this key in:
- `ui/src/i18n/locales/en.json`
- `ui/src/i18n/locales/es.json`
- `ui/src/i18n/locales/fr.json`
- `ui/src/i18n/locales/de.json`

## Related Components
- `FeatureContext` - Provides feature availability information
- `Alert` and `AlertDescription` - Display the license warning
- `approvalApi.getApprovers()` - API call that returns 402 when not licensed

## Future Improvements
1. Add a link to the license management page in the warning
2. Show trial information if available
3. Add analytics to track how many users encounter this error
4. Consider showing a "Upgrade Now" button that navigates to settings
