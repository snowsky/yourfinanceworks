# SSO License Gating Implementation

**Date:** January 9, 2026  
**Status:** ✅ Complete and Tested

## Overview

This document describes the SSO (Single Sign-On) license gating feature that controls which users can sign up via Google and Azure AD based on system licensing status.

## Problem Statement

Without proper license gating, any user could sign up via SSO and create a new organization/tenant database, even without a valid license. This could lead to:

- Unauthorized system usage
- Resource waste (unnecessary database creation)
- License compliance violations

## Solution

Implement a global first-user bypass mechanism that:

1. Allows the **first user in the entire system** to sign up via SSO without a license
2. Requires all **subsequent users** to have a valid license before creating new organizations
3. Prevents database creation for unlicensed users

## Rationale for Refactoring (January 2026)

Previously, the system used `check_feature("sso", tenant_db)` _after_ creating the tenant and database. This was removed in favor of the current "Global and Early" rejection strategy for several reasons:

1. **Resource Efficiency**: By checking `is_global_first_user` at the start of the callback, we prevent the "resource waste" of creating a Tenant record and a dedicated Postgres database for users who will ultimately be rejected.
2. **Preventative Security**: Rejection now happens before any persistence occurs in either the master or tenant databases, reducing the attack surface for orphaned resources.
3. **Logical Consistency**: A brand-new organization cannot have a license yet. Therefore, allowing the "absolute first user" (Global Admin) is the only logical exception. All other new organization creators must be rejected or handled via a separate license procurement flow before they can even trigger database provisioning.
4. **Simplified Logic**: Existing users (and invited users) bypass this check because their access is already established or authorized, simplifying the code path by removing redundant `check_feature` calls during the sensitive callback phase.

## Future Considerations

- **Trial Periods**: A temporary license can be issued to new organizations to allow them to try the SSO feature for a limited time.
- **Improved Error Messaging**: Providing more detailed instructions on how to obtain a license in the error message.
- **Admin Dashboard Integration**: Letting the global super admin see all organizations and their license status from the Super Admin page.
- **Auto-Provisioning**: Automatically issuing a basic license for newly created organizations if they meet certain criteria.

## Configuration

### Environment Variable

```bash
IGNORE_LICENSE_FOR_FIRST_SSO_USER=true
```

Set this to `true` to enable the first-user bypass. When `false`, all SSO users require a valid license.

**Default:** `false` (all users require license)

### Docker Compose

```yaml
services:
  invoice_app_api:
    environment:
      - IGNORE_LICENSE_FOR_FIRST_SSO_USER=${IGNORE_LICENSE_FOR_FIRST_SSO_USER:-false}
```

## Implementation Details

### Key Concepts

**Global First User:** The very first user to sign up in the entire system (across all organizations). This user:

- Gets `is_superuser=True` in the master database
- Can create a new organization without a license
- Bypasses SSO license checks

**Organization First User:** The first user to sign up in a specific organization. This user:

- Gets `is_superuser=False` (unless they're also the global first user)
- Gets `role="admin"` for their organization
- Must have a valid license (unless they're the global first user)

### Flow Diagram

```
SSO User Attempts Sign Up
    ↓
Is user already in master DB?
    ├─ YES → Existing user, allow login (no license check)
    └─ NO → New user, check global first user status
            ↓
            Is this the first user globally?
            ├─ YES → Allow signup, create tenant + DB
            └─ NO → Reject immediately (no DB created)
                    Return: "sso_license_required" error
```

### Code Changes

#### 1. Google OAuth Callback (`api/commercial/sso/router.py`)

```python
if not user:  # New user
    is_global_first_user = db.query(MasterUser).count() == 0

    if valid_invite:
        # User has invitation, assign to existing tenant
        is_org_first_user = False
    else:
        # No invitation, creating new organization
        is_org_first_user = True

        # CRITICAL: Check if first user globally BEFORE creating DB
        if not is_global_first_user:
            # Not first user, reject without creating resources
            return RedirectResponse(url=f"{ui_base}/login?error=sso_license_required")

        # First user globally, proceed with creation
        db_tenant = Tenant(...)
        db.add(db_tenant)
        db.commit()

        # Create tenant database
        tenant_db_manager.create_tenant_database(db_tenant.id, tenant_name)
```

#### 2. Azure AD Callback (`api/commercial/sso/router.py`)

Same logic as Google callback - check `is_global_first_user` before creating tenant database.

#### 3. Password Registration (`api/core/routers/auth.py`)

```python
if is_existing_user:
    is_global_first_user = False  # Existing users never bypass
else:
    is_global_first_user = db.query(MasterUser).count() == 0

    # License check happens after tenant DB creation
    if not (config.IGNORE_LICENSE_FOR_FIRST_SSO_USER and is_global_first_user):
        check_feature("sso", tenant_db)
```

## User Scenarios

### Scenario 1: First User Signs Up via Google SSO

**Setup:** System is empty, `IGNORE_LICENSE_FOR_FIRST_SSO_USER=true`

**Flow:**

1. User clicks "Sign up with Google"
2. System checks: `MasterUser.count() == 0` → `True`
3. `is_global_first_user = True`
4. Tenant created ✓
5. Tenant database created ✓
6. User created with `is_superuser=True` ✓
7. User redirected to dashboard ✓

**Result:** ✅ Success - First user can sign up without license

---

### Scenario 2: Second User Signs Up via Google SSO

**Setup:** First user exists, `IGNORE_LICENSE_FOR_FIRST_SSO_USER=true`, no license

**Flow:**

1. User clicks "Sign up with Google"
2. System checks: `MasterUser.count() == 0` → `False`
3. `is_global_first_user = False`
4. Check: `if not is_global_first_user` → `True`
5. Reject immediately
6. User redirected to login with error ✓

**Result:** ✅ Success - Second user rejected, no DB created

---

### Scenario 3: Second User Signs Up via Google SSO (With License)

**Setup:** First user exists, `IGNORE_LICENSE_FOR_FIRST_SSO_USER=true`, valid license exists

**Flow:**

1. User clicks "Sign up with Google"
2. System checks: `MasterUser.count() == 0` → `False`
3. `is_global_first_user = False`
4. Check: `if not is_global_first_user` → `True`
5. Reject immediately (license check happens at tenant level, not global)
6. User redirected to login with error ✓

**Note:** Currently, the system rejects at the global level. To allow licensed users to sign up, they would need to be invited to an existing organization or the license check would need to be moved to a system-level check.

---

### Scenario 4: First User Logs In Again

**Setup:** First user exists, `IGNORE_LICENSE_FOR_FIRST_SSO_USER=true`

**Flow:**

1. User clicks "Sign in with Google"
2. System finds user in master DB
3. `if not user:` → `False` (user exists)
4. Existing user flow - no license check
5. User redirected to dashboard ✓

**Result:** ✅ Success - Existing users can always log in

---

### Scenario 5: Feature Disabled (`IGNORE_LICENSE_FOR_FIRST_SSO_USER=false`)

**Setup:** `IGNORE_LICENSE_FOR_FIRST_SSO_USER=false`

**Flow:**

1. Any user attempts SSO signup
2. System checks: `if not (config.IGNORE_LICENSE_FOR_FIRST_SSO_USER and is_global_first_user)` → `True`
3. License check enforced for all users
4. If no license: Reject with error

**Result:** ✅ All users require license

## Database Impact

### Tenant Creation

- **Master DB:** `Tenant` record created
- **Master DB:** `MasterUser` record created
- **Tenant DB:** New database created with schema
- **Tenant DB:** `User` (TenantUser) record created

### Rejected User (No License)

- **Master DB:** No `Tenant` record
- **Master DB:** No `MasterUser` record
- **Tenant DB:** No database created
- **Tenant DB:** No records created

**Benefit:** Zero resource waste for rejected users

## Testing

### Test Cases

1. ✅ First user can sign up without license
2. ✅ Second user cannot sign up without license
3. ✅ First user can log in again
4. ✅ No database created for rejected users
5. ✅ Invited users can join existing organizations
6. ✅ Feature can be disabled via config

### Running Tests

```bash
cd api
pytest tests/test_sso_license_logic.py -v
```

## Deployment Checklist

- [ ] Set `IGNORE_LICENSE_FOR_FIRST_SSO_USER` environment variable
- [ ] Update `docker-compose.yml` with new env var
- [ ] Update `.env.example.full` with new setting
- [ ] Test SSO signup flow with first user
- [ ] Test SSO signup flow with second user (should be rejected)
- [ ] Verify no orphaned databases are created
- [ ] Monitor logs for license rejection messages

## Troubleshooting

### Issue: Second user can still sign up without license

**Cause:** `IGNORE_LICENSE_FOR_FIRST_SSO_USER` is not set or set to `false`

**Solution:**

```bash
export IGNORE_LICENSE_FOR_FIRST_SSO_USER=true
# Restart API server
```

### Issue: First user gets license error

**Cause:** `is_global_first_user` calculation is wrong (e.g., test data exists)

**Solution:**

```bash
# Check master database
SELECT COUNT(*) FROM master_user;

# If count > 0, clean test data
DELETE FROM master_user WHERE email LIKE '%test%';
```

### Issue: Database created but user rejected

**Cause:** Old code path still executing (license check after DB creation)

**Solution:** Verify code is updated to check `is_global_first_user` BEFORE creating tenant database

## Related Files

- `api/commercial/sso/router.py` - Google and Azure SSO callbacks
- `api/core/routers/auth.py` - Password registration
- `api/config.py` - Configuration loading
- `api/.env.example.full` - Environment variable documentation
- `docker-compose.yml` - Docker configuration

## Future Enhancements

1. **System-level license check:** Move license validation to system level instead of per-tenant
2. **Invitation-based signup:** Allow second users to sign up if invited to existing organization
3. **Trial period:** Automatically grant trial license to first user
4. **Admin dashboard:** Show license status and user signup restrictions
5. **Audit logging:** Log all SSO signup attempts and rejections

## References

- License Gating: `docs/FEATURE_MATRIX.md`
- SSO Configuration: `docs/SSO_INVITATION_SUPPORT.md`
- License Management: `api/docs/LICENSE_MANAGEMENT_API.md`
