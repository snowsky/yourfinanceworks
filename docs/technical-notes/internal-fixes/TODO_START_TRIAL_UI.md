# TODO: Add Start Trial Button to License Management UI

## Overview
The License Management page in the UI is missing a "Start Trial" button. Users with an active license that doesn't include certain features (like batch processing) have no way to start a trial to unlock all features.

## Current State
- License Management page exists at `ui/src/pages/LicenseManagement.tsx`
- Backend has `LicenseService.start_trial()` method that works correctly
- API endpoint exists: `POST /api/v1/license/start-trial`
- No UI button to trigger the trial start

## What Needs to Be Done

### 1. Update LicenseManagement.tsx
- Add a "Start Trial" button in the license status section
- Button should only show when:
  - User doesn't have an active trial
  - User doesn't have a personal use license
  - User has an active license (optional - could allow trial even with active license)
- Add loading state while trial is being started
- Show success/error messages

### 2. Add API Call
- Create function in `ui/src/lib/api.ts` to call `POST /api/v1/license/start-trial`
- Handle errors gracefully
- Return trial status after successful start

### 3. UI/UX Considerations
- Button placement: Near the license status display
- Button styling: Use primary action color (likely blue/green)
- Success message: "Trial started! All features are now available for 30 days"
- Error handling: Show specific error messages from backend
- Refresh license status after trial starts

### 4. Testing
- Test with active license (no trial)
- Test with existing trial (button should be disabled/hidden)
- Test with personal use license (button should be hidden)
- Test error cases (network errors, backend errors)

## Related Files
- `ui/src/pages/LicenseManagement.tsx` - Main component to update
- `ui/src/lib/api.ts` - Add API call function
- `api/core/routers/license.py` - Backend endpoint (already exists)
- `api/core/services/license_service.py` - Business logic (already exists)

## Backend Reference
The backend already supports this via:
```python
# In LicenseService
def start_trial(self, user_id: int) -> dict:
    """Start a trial for the installation"""
    # Returns: {"success": bool, "message": str, "trial_start_date": datetime, ...}
```

## Priority
Medium - Users need a way to enable all features for testing/evaluation without needing to activate a paid license.
