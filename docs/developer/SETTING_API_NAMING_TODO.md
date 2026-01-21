# Settings API Naming Inconsistency - TODO

## Issue

There is a naming inconsistency between backend and frontend API functions for settings management.

## Current State

### Backend Functions (`api/core/routers/settings.py`)
```python
# Individual setting operations
GET /settings/value/{key}    → get_setting_value()
PUT /settings/value/{key}    → update_setting_value()

# Bulk operations  
GET /settings/               → get_settings()
PUT /settings/               → update_settings()
```

### Frontend API Client (`ui/src/lib/api.ts`)
```typescript
// Individual setting operations
getSetting: (key: string) => apiRequest(`/settings/value/${key}`),
updateSetting: (key: string, value: any) => apiRequest(`/settings/value/${key}`, { method: 'PUT' }),

// Bulk operations
getSettings: () => apiRequest('/settings'),
updateSettings: (data: any) => apiRequest('/settings', { method: 'PUT' }),
```

## Naming Inconsistencies

1. **Individual Settings**:
   - Backend: `get_setting_value()` vs Frontend: `getSetting()`
   - Backend: `update_setting_value()` vs Frontend: `updateSetting()`

2. **Bulk Settings**:
   - Backend: `get_settings()` vs Frontend: `getSettings()` ✅ Consistent
   - Backend: `update_settings()` vs Frontend: `updateSettings()` ✅ Consistent

## Impact

- Confusing for developers debugging API calls
- Inconsistent naming conventions across the codebase
- Makes code harder to understand and maintain

## Refactoring Plan

### Option 1: Standardize on Frontend Naming (Recommended)
Change backend function names to match frontend:
```python
# Rename backend functions
get_setting_value() → get_setting()
update_setting_value() → update_setting()
```

### Option 2: Standardize on Backend Naming
Change frontend function names to match backend:
```typescript
// Rename frontend functions  
getSetting → get_setting_value
updateSetting → update_setting_value
```

### Option 3: Use Consistent Naming Everywhere
Standardize both to use clear, consistent naming:
```python
# Backend
get_individual_setting()
update_individual_setting()
get_all_settings()
update_all_settings()
```

```typescript
// Frontend
getIndividualSetting()
updateIndividualSetting()
getAllSettings()
updateAllSettings()
```

## Files to Update

### Backend:
- `api/core/routers/settings.py` - Function definitions
- Any test files that reference these functions

### Frontend:
- `ui/src/lib/api.ts` - API client functions
- `ui/src/components/settings/AIConfigTab.tsx` - Usage of getSetting/updateSetting
- Any other components using these functions

## Usage Locations

Currently only used in:
- `ui/src/components/settings/AIConfigTab.tsx` (4 usages)
  - `getSetting('review_worker_enabled')`
  - `getSetting('reviewer_ai_config')`  
  - `updateSetting('review_worker_enabled', ...)`
  - `updateSetting('reviewer_ai_config', ...)`

## Priority

**Low** - This is a cosmetic issue that doesn't affect functionality. The code works correctly despite the naming inconsistency.

## Considerations

1. **Backward Compatibility**: If changing API endpoints, ensure backward compatibility or update all clients
2. **Test Coverage**: Update any existing tests that reference the old function names
3. **Documentation**: Update API documentation if endpoint names change
4. **Mobile App**: Check if mobile app uses these same API endpoints

## Recommendation

Go with **Option 1** - rename backend functions to match frontend naming since:
- Frontend naming is more concise (`getSetting` vs `get_setting_value`)
- Bulk operations already follow this pattern consistently
- Minimal impact since only used in one frontend component
- Backend function names are internal and don't affect API contracts

---

**Created**: January 17, 2026  
**Status**: TODO - Awaiting refactoring
