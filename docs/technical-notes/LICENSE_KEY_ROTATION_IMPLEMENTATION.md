# License Key Rotation Implementation

## Problem

When the private key used to sign licenses is lost or regenerated, all previously issued licenses become invalid because the application only has one public key for verification. This causes:

- Customer licenses stop working
- Need to regenerate and redistribute all licenses
- Service disruption for all customers
- Support burden

## Solution

Implemented a **multi-key verification system** that supports key rotation without invalidating existing licenses.

### Key Features

1. **Key Versioning**: Each key pair has a version identifier (e.g., "v1", "v2", "v3")
2. **License Tagging**: New licenses include a `kid` (key ID) field in both JWT header and payload
3. **Multi-Key Support**: Application maintains multiple public keys simultaneously
4. **Backward Compatibility**: Old licenses continue to work as long as their public key is available
5. **Graceful Fallback**: Licenses without `kid` use the default key ID

## Implementation Details

### 1. License Service (`api/services/license_service.py`)

**Before:**
```python
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
...single key...
-----END PUBLIC KEY-----"""

def verify_license(self, license_key: str):
    payload = jwt.decode(license_key, PUBLIC_KEY, algorithms=["RS256"])
```

**After:**
```python
PUBLIC_KEYS = {
    "v2": """-----BEGIN PUBLIC KEY-----
    ...current key...
    -----END PUBLIC KEY-----""",
    "v1": """-----BEGIN PUBLIC KEY-----
    ...old key (if needed)...
    -----END PUBLIC KEY-----""",
}

DEFAULT_KEY_ID = "v2"

def verify_license(self, license_key: str):
    # Extract key ID from license
    unverified = jwt.decode(license_key, options={"verify_signature": False})
    key_id = unverified.get("kid", DEFAULT_KEY_ID)
    
    # Get appropriate public key
    public_key = PUBLIC_KEYS.get(key_id)
    if not public_key:
        return {"valid": False, "error": f"Unknown key ID: {key_id}"}
    
    # Verify with correct key
    payload = jwt.decode(license_key, public_key, algorithms=["RS256"])
```

### 2. License Generator (`license_server/license_generator.py`)

**Added:**
```python
class LicenseGenerator:
    CURRENT_KEY_VERSION = "v2"  # Increment when rotating keys
    
    def __init__(self, private_key_path=None, key_version=None):
        self.key_version = key_version or self.CURRENT_KEY_VERSION
    
    def generate_license(self, ...):
        payload = {
            ...
            "kid": self.key_version,  # Add key ID to payload
        }
        
        # Add key ID to JWT header
        license_key = jwt.encode(
            payload, 
            private_key, 
            algorithm="RS256",
            headers={"kid": self.key_version}
        )
```

### 3. Key Rotation Tools

Created helper scripts:

- **`license_server/generate_new_key_version.py`**: Generate new key pairs with version identifiers
- **`license_server/test_license_verification.py`**: Test multi-key verification
- **`docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md`**: Complete rotation procedures

## Usage

### Generate New Key Version

```bash
cd license_server
python generate_new_key_version.py --version v3
```

This will:
1. Generate `keys/private_key_v3.pem` and `keys/public_key_v3.pem`
2. Display the public key formatted for copying
3. Provide step-by-step deployment instructions

### Add New Key to Application

Update `api/services/license_service.py`:

```python
PUBLIC_KEYS = {
    "v3": """-----BEGIN PUBLIC KEY-----
    ...new key...
    -----END PUBLIC KEY-----""",
    "v2": """-----BEGIN PUBLIC KEY-----
    ...old key (still valid)...
    -----END PUBLIC KEY-----""",
}

DEFAULT_KEY_ID = "v3"  # Use new key for new licenses
```

### Update License Generator

Update `license_server/license_generator.py`:

```python
CURRENT_KEY_VERSION = "v3"
PRIVATE_KEY_PATH = Path(__file__).parent / "keys" / "private_key_v3.pem"
```

### Test Verification

```bash
# Test new license generation
cd license_server
python test_license_verification.py

# Test specific license
python test_license_verification.py "eyJ..."
```

## Key Rotation Workflow

1. **Generate new key pair** (v3)
2. **Add new public key** to application (keep old keys)
3. **Deploy application** with updated PUBLIC_KEYS
4. **Update license server** to use new private key
5. **Test** that both old and new licenses work
6. **Issue new licenses** with v3 key
7. **Monitor** key usage distribution
8. **Remove old keys** after migration period (6-12 months)

## Benefits

✅ **Zero Downtime**: Existing licenses continue working during rotation  
✅ **Gradual Migration**: No need to regenerate all licenses immediately  
✅ **Security**: Can rotate keys regularly without customer impact  
✅ **Recovery**: Can recover from lost private keys by adding new ones  
✅ **Flexibility**: Support multiple key versions simultaneously  

## Migration Path for Existing Deployments

If you already have licenses issued without `kid`:

1. **Current key becomes "v2"**: Rename existing key in PUBLIC_KEYS
2. **Set DEFAULT_KEY_ID = "v2"**: Old licenses without kid will use v2
3. **Generate v3 for new licenses**: Future licenses use v3
4. **Both work simultaneously**: No customer disruption

## Security Considerations

- **Private keys**: Never commit to version control, use `.gitignore`
- **Key storage**: Use secure, encrypted storage for private keys
- **Access control**: Limit who can access private keys
- **Backup**: Maintain encrypted backups of all key versions
- **Monitoring**: Track which key versions are in use
- **Deprecation**: Remove old keys only after all customers migrate

## Testing

Run the test suite to verify multi-key support:

```bash
cd license_server
python test_license_verification.py
```

Expected output:
```
Test 1: Standard License
✓ Verification: PASSED
  Key ID: v2
  Customer: Test Company
  Features: ai_invoice, ai_expense, batch_processing
```

## Documentation

- **Admin Guide**: `docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md`
- **Implementation**: This document
- **Error Handling**: `docs/LICENSE_ACTIVATION_ERROR_HANDLING_FIX.md`

## Future Enhancements

- [ ] Automated key rotation scheduling
- [ ] Key usage analytics dashboard
- [ ] Automatic license migration tool
- [ ] Hardware Security Module (HSM) integration
- [ ] Key revocation list support
- [ ] Automated customer notification system
