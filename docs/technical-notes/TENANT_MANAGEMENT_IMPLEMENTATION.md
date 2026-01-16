# Tenant Management Implementation

## Overview

This implementation adds tenant management functionality based on license limits to the invoice application. The system enforces tenant limits and provides super admin functionality to manage which tenants are enabled.

## Features Implemented

### 1. Database Schema Changes
- Added `is_enabled` field to the `Tenant` model in `core/models/models.py`
- Created Alembic migration to add the field to existing databases
- Default value is `True` for backward compatibility

### 2. Tenant Management Service
- Created `TenantManagementService` in `core/services/tenant_management_service.py`
- Handles tenant limit enforcement based on license
- Supports single tenant limitation (only super admin's tenant enabled)
- Supports reduced tenant limits (super admin can select which tenants to enable)

### 3. License Integration
- Updated `LicenseService.activate_license()` to automatically enforce tenant limits
- Tenant limits are enforced whenever a new license is activated
- Graceful handling if tenant enforcement fails (doesn't break license activation)

### 4. Super Admin Endpoints
Added three new endpoints to `/api/v1/super-admin/`:

#### GET `/tenants/status`
- Returns current tenant status and license information
- Shows enabled/disabled tenants and limits
- Requires super admin privileges

#### POST `/tenants/enforce-limits`
- Manually enforces tenant limits based on current license
- Useful for testing or manual enforcement
- Requires super admin privileges

#### POST `/tenants/select-enabled`
- Allows super admin to select which tenants to enable
- Request body: `{"tenant_ids": [1, 2, 3]}`
- Automatically includes super admin's tenant
- Requires super admin privileges

### 5. Access Control Updates
- Updated tenant context middleware to check `is_enabled` status
- Updated tenant router endpoints to respect enablement status
- Regular users cannot access disabled tenants
- Super admins can see all tenants (enabled and disabled)

## Behavior Scenarios

### Single Tenant License (max_tenants = 1)
- Only the super admin's primary tenant remains enabled
- All other tenants are automatically disabled
- Regular users cannot access disabled tenants
- Super admin can still manage all tenants but only access their own

### Reduced Tenant License (e.g., from 10 to 5 tenants)
- Super admin's tenant is always kept enabled
- Up to 4 additional tenants can be enabled (total of 5)
- System tries to preserve currently enabled tenants first
- If more than 5 tenants are enabled, the first 5 remain enabled
- Super admin can use the selection endpoint to choose which tenants to enable

### Personal/Trial Licenses
- No tenant limits enforced (999999 tenants allowed)
- All tenants remain enabled regardless of count

## API Examples

### Get Tenant Status
```bash
GET /api/v1/super-admin/tenants/status
Authorization: Bearer <super_admin_token>

Response:
{
  "max_tenants": 5,
  "total_tenants": 8,
  "enabled_tenants": 3,
  "disabled_tenants": 5,
  "tenant_details": {
    "enabled": [
      {"id": 1, "name": "Super Admin Tenant", ...},
      {"id": 2, "name": "Tenant A", ...},
      {"id": 3, "name": "Tenant B", ...}
    ],
    "disabled": [
      {"id": 4, "name": "Tenant C", ...},
      ...
    ]
  }
}
```

### Select Enabled Tenants
```bash
POST /api/v1/super-admin/tenants/select-enabled
Authorization: Bearer <super_admin_token>
Content-Type: application/json

{
  "tenant_ids": [1, 2, 3, 4, 5]
}

Response:
{
  "success": true,
  "message": "Successfully enabled 5 tenants.",
  "enabled_tenants": ["Super Admin Tenant", "Tenant A", "Tenant B", "Tenant C", "Tenant D"],
  "disabled_tenants": ["Tenant E", "Tenant F"],
  "max_tenants": 5
}
```

## Security Considerations

1. **Super Admin Protection**: Super admin's tenant is always protected and cannot be disabled
2. **Access Control**: Regular users cannot access disabled tenants at any level
3. **Audit Logging**: All tenant management actions are logged to the audit trail
4. **Graceful Degradation**: License enforcement failures don't break license activation

## Database Migration

Run the migration to add the `is_enabled` field:

```bash
cd api
alembic upgrade head
```

## Testing

1. Activate a license with `max_tenants: 1` - only super admin's tenant should remain enabled
2. Activate a license with `max_tenants: 5` - up to 5 tenants can be enabled
3. Use super admin endpoints to manage tenant selection
4. Verify regular users cannot access disabled tenants

## Files Modified/Created

### New Files
- `api/core/services/tenant_management_service.py` - Tenant management service
- `api/alembic/versions/add_is_enabled_to_tenants.py` - Database migration

### Modified Files
- `api/core/models/models.py` - Added is_enabled field to Tenant model
- `api/core/services/license_service.py` - Added tenant limit enforcement
- `api/core/routers/super_admin.py` - Added tenant management endpoints
- `api/core/middleware/tenant_context_middleware.py` - Added tenant enablement checks
- `api/core/routers/tenant.py` - Updated endpoints to respect enablement status

## Notes

- The implementation maintains backward compatibility
- Existing tenants will have `is_enabled = True` by default
- Super admin functionality is protected by existing RBAC system
- All actions are properly logged for audit purposes
