# SSO Invitation Support Implementation

## Overview

This update allows users who have been invited to an organization to use SSO (Single Sign-On) for authentication, provided the organization has a valid SSO license. Previously, invited users would be assigned to new organizations during SSO login, regardless of existing invitations.

## Problem Statement

Before this implementation:
1. When a user tried to sign in via SSO, the system would create a new tenant/organization for them
2. Users with pending invitations were not assigned to the inviting organization
3. SSO license checks were performed on the newly created tenant, not the inviting tenant
4. This prevented invited users from joining their intended organization via SSO

## Solution

### Key Changes

1. **Invitation Detection**: Added `check_user_has_valid_invite()` function to detect pending invitations for a user's email
2. **Tenant Assignment Logic**: Modified SSO callbacks to assign users to their inviting tenant instead of creating new ones
3. **Role Preservation**: Users are assigned the role specified in their invitation (admin, user, viewer)
4. **Invitation Completion**: Invitations are marked as accepted when users sign in via SSO

### Implementation Details

#### Files Modified
- `/api/commercial/sso/router.py` - Updated Google and Azure SSO callbacks

#### New Functions
```python
def check_user_has_valid_invite(db: Session, email: str) -> Optional[Invite]:
    """Check if email has valid invitation for any tenant"""
    return db.query(Invite).filter(
        func.lower(Invite.email) == func.lower(email),
        Invite.is_accepted == False,
        Invite.expires_at > datetime.now(timezone.utc)
    ).first()
```

#### Modified SSO Flow

**Google SSO Callback (`/auth/google/callback`)**:
1. Extract user email from Google OAuth response
2. Check for valid invitation before creating new tenant
3. If invitation exists: assign user to inviting tenant
4. If no invitation: create new tenant (existing behavior)
5. Mark invitation as accepted and assign proper role
6. Perform SSO license check on the correct tenant

**Azure SSO Callback (`/auth/azure/callback`)**:
- Same logic as Google SSO callback

## User Experience

### For Invited Users
1. User receives email invitation to join organization
2. User clicks SSO login button (Google/Azure)
3. System detects pending invitation
4. User is authenticated and assigned to inviting organization
5. User gains access with the role specified in invitation
6. Invitation is marked as accepted

### For Non-Invited Users
- No change in behavior - new tenant is created as before

### License Enforcement
- SSO license is still required and respected
- License check is performed on the user's assigned tenant
- Organizations without SSO license will still block SSO access

## Security Considerations

1. **Invitation Validation**: Only valid, unexpired invitations are accepted
2. **Email Matching**: Case-insensitive email matching for invitations
3. **Role Assignment**: Users receive the role specified in their invitation
4. **License Compliance**: SSO license checks remain in place and are enforced

## Testing Scenarios

### Test Case 1: Invited User with Valid SSO License
1. Create invitation for user@example.com to Organization A
2. Ensure Organization A has valid SSO license
3. User signs in via SSO
4. **Expected**: User is assigned to Organization A with invitation role

### Test Case 2: Invited User without SSO License
1. Create invitation for user@example.com to Organization B
2. Organization B does not have SSO license
3. User signs in via SSO
4. **Expected**: User receives SSO license required error

### Test Case 3: Non-Invited User
1. User without invitation signs in via SSO
2. **Expected**: New tenant created (existing behavior)

## Migration Notes

- No database schema changes required
- Existing invitations continue to work
- No impact on current SSO users
- Backward compatible with existing authentication flows

## Future Enhancements

1. **Multiple Invitations**: Handle cases where user has invitations to multiple organizations
2. **Invitation Selection**: Allow users to choose which organization to join when multiple invitations exist
3. **Audit Logging**: Add audit events for SSO invitation acceptance
4. **Email Notifications**: Send confirmation emails when invitations are accepted via SSO
