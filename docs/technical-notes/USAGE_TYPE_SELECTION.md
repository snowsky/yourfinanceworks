# Usage Type Selection Flow

## Overview

The licensing system now starts with an **invalid** license status. Users must explicitly choose their usage type before they can use the application:

1. **Personal Use** - Free forever with all features enabled
2. **Business Use** - 30-day trial period, then requires a paid license

## Flow

### Initial State
- When the application is first installed, `license_status` is set to `"invalid"`
- `usage_type` is `null`
- No features are available until usage type is selected

### User Selection

#### Option 1: Personal Use
- User selects "Personal Use"
- `usage_type` is set to `"personal"`
- `license_status` is set to `"personal"`
- All features are enabled **forever** for free
- No trial period, no expiration

#### Option 2: Business Use
- User selects "Business Use"
- `usage_type` is set to `"business"`
- `license_status` is set to `"trial"`
- 30-day trial period starts
- All features are enabled during trial
- After trial expires, user must activate a paid license

### One-Time Selection
- Usage type can only be selected **once** per installation
- Once selected, it cannot be changed (prevents abuse)
- To change, user would need to reinstall or contact support

## API Endpoints

### POST /api/v1/license/select-usage-type
Select usage type (personal or business).

**Request:**
```json
{
  "usage_type": "personal"  // or "business"
}
```

**Response (Personal):**
```json
{
  "success": true,
  "message": "Personal use selected. All features are available for free.",
  "usage_type": "personal",
  "license_status": "personal"
}
```

**Response (Business):**
```json
{
  "success": true,
  "message": "Business trial started. 30 days remaining.",
  "usage_type": "business",
  "license_status": "trial",
  "trial_days_remaining": 30,
  "trial_end_date": "2024-12-19T10:30:00Z"
}
```

### GET /api/v1/license/usage-type-status
Check if usage type has been selected.

**Response:**
```json
{
  "usage_type": "personal",  // or "business", or null
  "usage_type_selected": true,
  "usage_type_selected_at": "2024-11-19T10:30:00Z",
  "license_status": "personal"
}
```

### GET /api/v1/license/status
Get comprehensive license status (includes usage type info).

**Response:**
```json
{
  "installation_id": "550e8400-e29b-41d4-a716-446655440000",
  "license_status": "personal",
  "usage_type": "personal",
  "usage_type_selected": true,
  "is_licensed": false,
  "is_personal": true,
  "is_trial": false,
  "trial_info": {
    "is_trial": false,
    "trial_active": false,
    "trial_start_date": null,
    "trial_end_date": null,
    "days_remaining": 0,
    "in_grace_period": false,
    "grace_period_end": null
  },
  "license_info": null,
  "enabled_features": ["all"],
  "has_all_features": true
}
```

## Database Schema Changes

### New Columns in `installation_info` table:

```sql
-- Usage type selection
usage_type VARCHAR(20) NULL,  -- 'personal', 'business', or NULL
usage_type_selected_at TIMESTAMP WITH TIME ZONE NULL,

-- Modified columns (now nullable)
trial_start_date TIMESTAMP WITH TIME ZONE NULL,  -- Only set for business use
trial_end_date TIMESTAMP WITH TIME ZONE NULL,    -- Only set for business use

-- Modified default
license_status VARCHAR(20) DEFAULT 'invalid'  -- Changed from 'trial'
```

### License Status Values:
- `invalid` - Initial state, no usage type selected
- `personal` - Personal use, free forever
- `trial` - Business trial active
- `active` - Paid license active
- `expired` - License or trial expired
- `grace_period` - In grace period after trial expiration

## Migration

Run the migration to update existing installations:

```bash
cd api
alembic upgrade head
```

The migration will:
1. Add new `usage_type` and `usage_type_selected_at` columns
2. Make `trial_start_date` and `trial_end_date` nullable
3. Change default `license_status` from `'trial'` to `'invalid'`
4. Migrate existing installations: if `trial_start_date` exists, set `usage_type='business'` and `license_status='trial'`

## UI Implementation

### On First Launch
1. Check `/api/v1/license/usage-type-status`
2. If `usage_type_selected` is `false`, show usage type selection modal
3. User cannot proceed until they select a usage type

### Usage Type Selection Modal
```
Welcome to {APP_NAME}!

How will you be using this application?

[ Personal Use ]
- Free forever
- All features included
- Perfect for individuals and personal projects

[ Business Use ]
- 30-day free trial
- All features included
- Requires paid license after trial

[Continue]
```

### After Selection
- Personal: Show success message, proceed to app
- Business: Show trial banner with days remaining

## Benefits

1. **Clear Intent**: Users explicitly choose their use case
2. **Prevents Abuse**: Can't switch from business to personal to avoid payment
3. **Better UX**: Personal users never see trial warnings
4. **Compliance**: Clear distinction between personal and commercial use
5. **Flexibility**: Business users get full trial before committing

## Testing

### Test Personal Use Flow
```bash
# Select personal use
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "personal"}'

# Check status
curl http://localhost:8000/api/v1/license/status \
  -H "Authorization: Bearer $TOKEN"
```

### Test Business Use Flow
```bash
# Select business use
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "business"}'

# Check status (should show trial)
curl http://localhost:8000/api/v1/license/status \
  -H "Authorization: Bearer $TOKEN"
```

### Test One-Time Selection
```bash
# Try to select again (should fail)
curl -X POST http://localhost:8000/api/v1/license/select-usage-type \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_type": "business"}'

# Expected: 400 error with "ALREADY_SELECTED"
```
