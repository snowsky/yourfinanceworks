# Encryption Backup Security Feature

## Overview

This document describes the encryption backup security feature that prevents unauthorized access to encrypted data during backup import operations. The feature ensures that encrypted data exported from one tenant cannot be imported and decrypted by another tenant, providing robust data isolation and security.

## Security Problem Addressed

### The Risk
When users export their data as SQLite files through the `/settings/export-data` endpoint, the exported file contains all tenant data including encrypted fields. If this file were to be imported by another tenant through the `/settings/import-data` endpoint, the importing tenant would receive encrypted data that they cannot decrypt, since each tenant uses their own unique encryption keys.

### Expected Behavior
- **Export**: Data is exported in plain SQLite format with encrypted fields as-is
- **Import**: When importing, decryption fails gracefully with "decryption failed" errors
- **Security**: Other tenants cannot access the encrypted data content

## How the Security Works

### 1. Tenant-Specific Encryption Keys

Each tenant has their own unique encryption key derived from:
- Master encryption key (stored securely in key vault)
- Tenant-specific salt and key derivation parameters
- PBKDF2 key derivation with tenant ID as salt component

```python
# From encryption_service.py
def get_tenant_key(self, tenant_id: int) -> bytes:
    tenant_key_material = self.key_management.retrieve_tenant_key(tenant_id)
    derived_key = self._derive_key(tenant_key_material, tenant_id)
    return derived_key

def _derive_key(self, key_material: str, tenant_id: int) -> bytes:
    salt = f"{self.config.KEY_DERIVATION_SALT}:{tenant_id}".encode('utf-8')
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=...)
    return kdf.derive(key_bytes)
```

### 2. AES-256-GCM Encryption

Data is encrypted using AES-256-GCM with:
- Unique 12-byte nonce per encryption operation
- Authentication tag for integrity verification
- Base64 encoding for database storage

```python
def encrypt_data(self, data: str, tenant_id: int) -> str:
    key = self.get_tenant_key(tenant_id)
    cipher = AESGCM(key)
    nonce = os.urandom(12)
    encrypted_data = cipher.encrypt(nonce, data.encode('utf-8'), None)
    combined = nonce + encrypted_data
    return base64.b64encode(combined).decode('ascii')
```

### 3. Decryption with Tenant Isolation

Decryption requires the exact same tenant key:
```python
def decrypt_data(self, encrypted_data: str, tenant_id: int) -> str:
    key = self.get_tenant_key(tenant_id)  # Wrong tenant = wrong key
    # GCM authentication will fail with wrong key
```

### 4. Backup Import Process

During import (`/settings/import-data` endpoint):
1. SQLite file is uploaded and parsed
2. Data is inserted into importing tenant's database
3. Encrypted fields remain as encrypted strings
4. Any attempt to decrypt shows "decryption failed" because:
   - The data was encrypted with source tenant's key
   - Import tenant has different key
   - AES-GCM authentication tag verification fails

## Security Benefits

### 1. Data Isolation
- Encrypted data from one tenant cannot be decrypted by another
- Cross-tenant data leakage is prevented at the cryptographic level

### 2. Graceful Failure
- Import succeeds structurally (database schema is maintained)
- Encrypted data appears as corrupted/unreadable rather than causing crashes
- Users see "decryption failed" messages instead of security breaches

### 3. No Backdoors
- No mechanism exists to decrypt another tenant's data
- Even administrators cannot access encrypted data from other tenants
- Key vault providers (AWS KMS, Azure Key Vault, etc.) enforce access controls

### 4. Audit Trail
- All import operations are logged in audit trails
- Failed decryption attempts are logged for monitoring
- Import operations track which user performed the action

## Implementation Details

### Export Process (`/settings/export-data`)
```python
# Direct ORM copy - encrypted fields remain encrypted
for obj in db.query(Invoice).all():
    sqlite_session.add(Invoice(**{c.name: getattr(obj, c.name) for c in Invoice.__table__.columns}))
```

### Import Process (`/settings/import-data`)
```python
# Data inserted as-is, encryption keys don't match
new_invoice = Invoice(
    number=invoice.number,
    amount=invoice.amount,  # Still encrypted with source tenant's key
    # ... other fields
)
db.add(new_invoice)
```

### Decryption Failure Handling
```python
# From encryption_service.py
try:
    decrypted_data = cipher.decrypt(nonce, ciphertext, None)
    return decrypted_data.decode('utf-8')
except InvalidTag:
    raise DecryptionError("Authentication tag verification failed (wrong key or corrupted data)")
```

## Testing the Security Feature

### Manual Testing
1. Export data from Tenant A
2. Import the SQLite file into Tenant B
3. Attempt to view encrypted fields (invoices, clients, etc.)
4. Observe "decryption failed" errors in logs and UI

### Automated Testing
```python
def test_cross_tenant_encryption_isolation():
    # Create data in tenant A
    encrypted_data_a = encrypt_data("sensitive info", tenant_a_id)

    # Attempt to decrypt with tenant B's key
    try:
        decrypt_data(encrypted_data_a, tenant_b_id)
        assert False, "Should not be able to decrypt other tenant's data"
    except DecryptionError:
        assert "Authentication tag verification failed" in str(e)
```

## Compliance and Standards

### Data Protection
- **GDPR**: Prevents unauthorized data processing across tenants
- **CCPA**: Maintains data minimization and purpose limitation
- **ISO 27001**: Implements access controls and data segregation

### Encryption Standards
- **AES-256-GCM**: NIST-approved encryption standard
- **PBKDF2**: Secure key derivation with high iteration count
- **Base64**: Safe transport encoding for database storage

## Monitoring and Alerting

### Security Events
- Failed decryption attempts are logged at WARNING level
- Import operations are audited with user context
- Key access patterns are monitored for anomalies

### Alerts
- Unusual number of decryption failures
- Cross-tenant import attempts
- Key vault access errors

## Best Practices

### For Users
- Always verify data integrity after import
- Be aware that imported encrypted data may be unreadable
- Use the feature for legitimate backup/restore within the same tenant

### For Administrators
- Monitor audit logs for suspicious import activities
- Ensure key vault access controls are properly configured
- Regularly test backup and recovery procedures

### For Developers
- Never expose decryption keys across tenant boundaries
- Always validate tenant context before decryption operations
- Implement proper error handling for decryption failures

## Conclusion

This encryption backup security feature provides robust protection against cross-tenant data access while maintaining usability for legitimate backup and restore operations. The cryptographic isolation ensures that tenant data remains secure even when exported and imported across different tenant environments, implementing a defense-in-depth approach to multi-tenant data security.