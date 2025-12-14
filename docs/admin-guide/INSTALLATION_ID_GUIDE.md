# Installation ID Guide

## Overview

This guide explains the Installation ID mechanism used in the Invoice Management System's licensing system. Installation IDs provide security and prevent unauthorized license sharing between different organizations.

## Table of Contents

1. [What is an Installation ID?](#what-is-an-installation-id)
2. [How Installation IDs Work](#how-installation-ids-work)
3. [Security Benefits](#security-benefits)
4. [Installation ID Management](#installation-id-management)
5. [Common Scenarios](#common-scenarios)
6. [Troubleshooting](#troubleshooting)
7. [Technical Details](#technical-details)

---

## What is an Installation ID?

An Installation ID is a **unique UUID (Universally Unique Identifier)** automatically generated when the Invoice Management System is first installed. It serves as a digital fingerprint for each specific installation.

### Key Characteristics

- **Unique**: Each installation gets its own UUID
- **Persistent**: Remains the same across server migrations (if database is preserved)
- **Automatic**: Generated on first startup without user intervention
- **Secure**: Cryptographically bound to licenses

### Format

```
Installation ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## How Installation IDs Work

### 1. Generation Process

When the system starts for the first time:

1. Checks if an `InstallationInfo` record exists in the database
2. If not found, generates a new UUID using `uuid.uuid4()`
3. Stores it in the `installation_info` table

```python
# From license_service.py
installation = InstallationInfo(
    installation_id=str(uuid.uuid4()),
    license_status="invalid",
    usage_type=None,
    # ... other fields
)
```

### 2. License Binding

When a customer purchases a license:

1. The license generation system includes the Installation ID in the JWT payload
2. The license is cryptographically signed with RSA keys
3. The license becomes permanently bound to that Installation ID

### 3. Validation Process

During license activation:

1. System extracts the Installation ID from the license JWT
2. Compares it with the current installation's stored Installation ID
3. Only allows activation if they match exactly

```python
# Validation check in license_service.py
if license_installation_id != installation.installation_id:
    return {
        "success": False,
        "message": "This license is not valid for this installation",
        "error": "INSTALLATION_ID_MISMATCH"
    }
```

---

## Security Benefits

### Prevents License Sharing

- **No Cross-Organization Use**: Licenses cannot be shared between different companies
- **No Piracy**: Cannot copy license keys to unauthorized installations
- **Revenue Protection**: Ensures each organization purchases their own license

### Maintains Privacy

- **No Personal Data**: Installation IDs contain no personal or organizational information
- **Local Storage**: Stored locally in the database, not transmitted externally
- **Cryptographic Security**: Bound to licenses using unforgeable digital signatures

---

## Installation ID Management

### Viewing the Installation ID

Administrators can view the current Installation ID through:

1. **Database Query**:
   ```sql
   SELECT installation_id FROM installation_info LIMIT 1;
   ```

2. **API Endpoint**:
   ```
   GET /api/license/status
   ```
   (Response includes installation_id field)

3. **License Management UI**: Available in the Settings → License page

### Server Migration

When migrating to a new server:

- **Database Migration**: If you migrate the database, the Installation ID remains the same
- **New Installation**: If you start with a fresh database, a new Installation ID is generated
- **License Transfer**: Licenses work after migration if the database (and thus Installation ID) is preserved

---

## Common Scenarios

### Scenario 1: Fresh Installation

**Process**: New system → New Installation ID → New license required

**Outcome**: Customer purchases license bound to this Installation ID

### Scenario 2: Server Migration

**Process**: Old server → Migrate database → Same Installation ID → Existing licenses work

**Outcome**: No new license needed, existing licenses remain valid

### Scenario 3: Database Reset

**Process**: Fresh database → New Installation ID → Existing licenses invalid

**Outcome**: Customer needs new license (contact support for migration assistance)

### Scenario 4: License Sharing Attempt

**Process**: Copy license from Installation A → Try to activate on Installation B

**Outcome**: "Installation ID mismatch" error - activation blocked

---

## Troubleshooting

### Common Errors

#### "Installation ID mismatch"

**Cause**: Trying to activate a license generated for a different installation

**Solutions**:
1. Verify you're using the correct license for this installation
2. Check if this is a new installation requiring a new license
3. Contact support if you believe this is an error

#### "Missing installation_id field"

**Cause**: License was generated before Installation ID binding was implemented

**Solutions**:
1. Contact support for a license re-issue
2. Generate a new license with proper Installation ID binding

### Support Information

When contacting support about Installation ID issues, provide:

- Current Installation ID (from database or API)
- License key (if available)
- Error message
- Migration history (if applicable)

---

## Technical Details

### Database Schema

```sql
CREATE TABLE installation_info (
    id INTEGER PRIMARY KEY,
    installation_id VARCHAR(36) UNIQUE NOT NULL,  -- UUID
    license_status VARCHAR(20) DEFAULT 'invalid',
    -- ... other fields
);
```

### JWT License Structure

```json
{
  "customer_email": "user@example.com",
  "features": ["ai_invoice", "ai_expense"],
  "installation_id": "550e8400-e29b-41d4-a716-446655440000",
  "exp": 1740000000,
  "kid": "v2"
}
```

### Security Considerations

- **Cryptographic Binding**: Installation IDs are included in signed JWT tokens
- **No Spoofing**: Cannot modify Installation ID in license without breaking signature
- **Privacy**: Installation IDs contain no identifiable information
- **Offline Validation**: Works without internet connection

---

## Best Practices

### For Administrators

1. **Document Installation ID**: Keep a record of your Installation ID for support requests
2. **Database Backups**: Preserve database during migrations to maintain Installation ID
3. **License Management**: Track which licenses belong to which installations

### For Developers

1. **Never Hardcode IDs**: Always retrieve Installation ID from database
2. **Handle Migrations**: Preserve Installation ID during database upgrades
3. **Error Messages**: Provide clear guidance for Installation ID mismatch errors

### For Support Staff

1. **Verify Installation ID**: Always confirm customer's Installation ID
2. **Migration Assistance**: Help customers preserve Installation ID during migrations
3. **License Re-issuance**: Re-issue licenses when Installation IDs change legitimately

---

## FAQ

**Q: Can two installations have the same Installation ID?**

A: No. UUID generation ensures global uniqueness. The probability of collision is astronomically low.

**Q: Can I change my Installation ID?**

A: Not directly. Installation IDs are designed to be persistent. Changing it would invalidate all existing licenses.

**Q: Is my Installation ID secret?**

A: No. Installation IDs are not sensitive and can be shared with support staff. They contain no personal or organizational information.

**Q: What happens if I delete the installation_info table?**

A: A new Installation ID will be generated on next startup, but all existing licenses will become invalid.

**Q: Can Installation IDs be tracked across organizations?**

A: No. Installation IDs are random UUIDs with no embedded information about the organization or location.

---

**Last Updated:** December 2025  
**Version:** 1.0  
**Related Documents:** [License Activation Guide](../user-guide/LICENSE_ACTIVATION_GUIDE.md), [License Administration Guide](LICENSE_ADMINISTRATION_GUIDE.md)