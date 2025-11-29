# License Key Rotation Guide

## Overview

This guide explains how to rotate license signing keys without invalidating existing customer licenses. Key rotation is necessary when:

- Private key is compromised or suspected to be compromised
- Regular security maintenance (recommended annually)
- Migrating to stronger key algorithms
- Private key is lost and needs to be regenerated

## How Key Rotation Works

The system supports multiple public keys simultaneously through a versioning system:

1. **Key Versioning**: Each key pair has a version identifier (e.g., "v1", "v2", "v3")
2. **License Tagging**: New licenses include a `kid` (key ID) field identifying which key signed them
3. **Multi-Key Verification**: The application tries to verify licenses with the appropriate public key
4. **Backward Compatibility**: Old licenses continue to work as long as their public key remains in the system

## Key Rotation Process

### Step 1: Generate New Key Pair

Generate a new RSA key pair for the new version:

```bash
cd license_server

# Generate new key pair (will be saved as private_key_v3.pem and public_key_v3.pem)
python generate_new_key_version.py --version v3
```

Or manually:

```bash
# Generate new private key
openssl genrsa -out keys/private_key_v3.pem 2048

# Extract public key
openssl rsa -in keys/private_key_v3.pem -pubout -out keys/public_key_v3.pem

# Secure the private key
chmod 600 keys/private_key_v3.pem
```

### Step 2: Add New Public Key to Application

You have **three options** for adding the new public key:

#### Option 1: File-based (Recommended)

Copy the public key file to the keys directory:

```bash
# Copy new public key
cp license_server/keys/public_key_v3.pem api/core/keys/

# The application will automatically load all public_key_*.pem files
# No code changes needed!
```

#### Option 2: Environment Variable

Set environment variable for the new key:

```bash
# In .env or docker-compose.yml
LICENSE_PUBLIC_KEY_V3="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

# Update default key ID
LICENSE_DEFAULT_KEY_ID=v3
```

#### Option 3: Code-based (Legacy)

Update `api/services/license_service.py` to include the new public key:

```python
PUBLIC_KEYS = {
    # Current key (v3) - used for new licenses
    "v3": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA... (new key)
-----END PUBLIC KEY-----""",
    
    # Previous key (v2) - still valid for existing licenses
    "v2": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzexH7ckqeuCg2ZmyiMFS...
-----END PUBLIC KEY-----""",
    
    # Keep old keys as long as customers have licenses signed with them
}

# Update default key ID
DEFAULT_KEY_ID = "v3"
```

**Recommended**: Use Option 1 (file-based) for easier management and deployment.

### Step 3: Update License Generator

Update `license_server/license_generator.py`:

```python
class LicenseGenerator:
    # Update to new key version
    CURRENT_KEY_VERSION = "v3"
    
    # Update path to new private key
    PRIVATE_KEY_PATH = Path(__file__).parent / "keys" / "private_key_v3.pem"
```

### Step 4: Deploy Application Update

Deploy the updated application with the new public key:

```bash
# Build and deploy
docker-compose build api
docker-compose up -d api

# Verify deployment
curl http://localhost:8000/api/v1/license/status
```

### Step 5: Update License Server

Update the license server to use the new private key:

```bash
cd license_server

# Update .env to point to new key
echo "PRIVATE_KEY_PATH=keys/private_key_v3.pem" >> .env
echo "KEY_VERSION=v3" >> .env

# Restart license server
docker-compose restart license-server
```

### Step 6: Test New License Generation

Generate a test license and verify it works:

```bash
cd license_server

# Generate test license
python generate_license_cli.py \
  --email test@example.com \
  --name "Test Customer" \
  --features ai_invoice,batch_processing \
  --days 365

# Test activation in application
# (Use the generated license key in the UI)
```

### Step 7: Verify Old Licenses Still Work

Test that existing customer licenses continue to work:

```bash
# Test an old license (signed with v2)
python test_license_verification.py --license-key "eyJ..."

# Should show: "✓ License valid (signed with key v2)"
```

## Key Deprecation Strategy

### When to Remove Old Keys

Remove old public keys only when:

1. **All customers have migrated**: No active licenses signed with that key
2. **Grace period expired**: Sufficient time given for customers to upgrade
3. **Security incident**: Key is compromised (force migration)

### Recommended Timeline

- **Month 0**: Generate and deploy new key (v3)
- **Month 1-3**: Issue all new licenses with v3
- **Month 6**: Send migration notice to customers with v2 licenses
- **Month 12**: Remove v2 public key from application

### Forced Migration Process

If you need to force migration (e.g., security incident):

1. **Notify customers immediately** via email
2. **Provide free license replacement** for affected customers
3. **Set short grace period** (e.g., 30 days)
4. **Remove compromised key** from application
5. **Monitor support requests** for migration issues

## Emergency Key Rotation

If a private key is compromised:

### Immediate Actions (Within 24 hours)

1. **Generate new key pair immediately**
   ```bash
   python generate_new_key_version.py --version v3 --emergency
   ```

2. **Deploy new public key to all installations**
   ```bash
   # Emergency deployment
   ./scripts/emergency_key_rotation.sh v3
   ```

3. **Revoke compromised key**
   ```python
   # Remove from PUBLIC_KEYS in license_service.py
   # Or add to revocation list
   REVOKED_KEY_IDS = ["v2"]
   ```

4. **Notify all customers**
   ```bash
   python scripts/send_key_rotation_notice.py --emergency
   ```

### Follow-up Actions (Within 7 days)

1. **Regenerate all active licenses** with new key
2. **Send replacement licenses** to all customers
3. **Update documentation** and security policies
4. **Conduct security audit** to identify breach source

## Automation Scripts

### Generate New Key Version

Create `license_server/generate_new_key_version.py`:

```python
#!/usr/bin/env python3
"""Generate a new key version for key rotation"""

import argparse
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pathlib import Path

def generate_key_version(version: str, key_size: int = 2048):
    """Generate new key pair with version identifier"""
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Save keys
    keys_dir = Path(__file__).parent / "keys"
    keys_dir.mkdir(exist_ok=True)
    
    private_path = keys_dir / f"private_key_{version}.pem"
    public_path = keys_dir / f"public_key_{version}.pem"
    
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    
    # Secure private key
    private_path.chmod(0o600)
    
    print(f"✓ Generated key pair version {version}")
    print(f"  Private: {private_path}")
    print(f"  Public: {public_path}")
    print(f"\nNext steps:")
    print(f"1. Add public key to api/services/license_service.py")
    print(f"2. Update CURRENT_KEY_VERSION in license_generator.py")
    print(f"3. Deploy application update")
    
    return private_pem, public_pem

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate new key version")
    parser.add_argument("--version", required=True, help="Key version (e.g., v3)")
    parser.add_argument("--key-size", type=int, default=2048, help="Key size in bits")
    parser.add_argument("--emergency", action="store_true", help="Emergency rotation")
    
    args = parser.parse_args()
    
    if args.emergency:
        print("⚠️  EMERGENCY KEY ROTATION")
        print("This will generate a new key for immediate deployment.")
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            exit(1)
    
    generate_key_version(args.version, args.key_size)
```

### Test License Verification

Create `license_server/test_license_verification.py`:

```python
#!/usr/bin/env python3
"""Test license verification with multiple keys"""

import sys
import jwt
from pathlib import Path

# Import from application
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
from services.license_service import LicenseService

def test_license(license_key: str):
    """Test license verification"""
    
    # Decode without verification to see key ID
    try:
        unverified = jwt.decode(license_key, options={"verify_signature": False})
        key_id = unverified.get("kid", "unknown")
        print(f"License signed with key: {key_id}")
    except Exception as e:
        print(f"✗ Failed to decode license: {e}")
        return
    
    # Verify with LicenseService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    db = Session()
    
    service = LicenseService(db)
    result = service.verify_license(license_key)
    
    if result["valid"]:
        print(f"✓ License valid")
        print(f"  Customer: {result['payload']['customer_email']}")
        print(f"  Features: {', '.join(result['payload']['features'])}")
    else:
        print(f"✗ License invalid: {result['error']}")
        print(f"  Error code: {result['error_code']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_license_verification.py <license_key>")
        sys.exit(1)
    
    test_license(sys.argv[1])
```

## Monitoring and Alerts

### Track Key Usage

Add logging to track which keys are being used:

```python
# In license_service.py verify_license()
logger.info(f"License verified with key {key_id}")

# Monitor key usage distribution
SELECT kid, COUNT(*) as count
FROM license_validation_log
WHERE validation_result = 'success'
GROUP BY kid
ORDER BY count DESC;
```

### Set Up Alerts

Configure alerts for:

- **Old key usage spike**: Indicates customers haven't migrated
- **Unknown key ID**: Potential security issue
- **Verification failures**: May indicate key rotation issues

## Best Practices

1. **Never delete private keys immediately**: Keep backups for at least 1 year
2. **Test thoroughly**: Verify both old and new licenses work before deployment
3. **Communicate early**: Give customers advance notice of key rotation
4. **Maintain key inventory**: Document all key versions and their status
5. **Regular rotation**: Rotate keys annually as part of security maintenance
6. **Secure key storage**: Use hardware security modules (HSM) for production keys
7. **Audit trail**: Log all key generation and rotation events

## Troubleshooting

### Old Licenses Stop Working

**Symptom**: Customers report "Invalid license signature" errors

**Solution**:
1. Check if old public key is still in `PUBLIC_KEYS`
2. Verify `DEFAULT_KEY_ID` matches most recent key
3. Check license `kid` field matches available keys

### New Licenses Not Working

**Symptom**: Newly issued licenses fail verification

**Solution**:
1. Verify public key in application matches private key used for signing
2. Check `CURRENT_KEY_VERSION` in license generator
3. Ensure application was redeployed with new public key

### Key ID Mismatch

**Symptom**: License has `kid` but verification fails

**Solution**:
```python
# Check available keys
print(PUBLIC_KEYS.keys())

# Check license key ID
import jwt
payload = jwt.decode(license_key, options={"verify_signature": False})
print(f"License kid: {payload.get('kid')}")
```

## Security Considerations

1. **Private key protection**: Never commit private keys to version control
2. **Key transmission**: Use secure channels (encrypted) for key distribution
3. **Access control**: Limit who can access private keys
4. **Audit logging**: Log all key generation and usage
5. **Backup strategy**: Encrypted backups of private keys in secure location
6. **Incident response**: Have a plan for compromised keys

## Support

For questions or issues with key rotation:

- Email: support@yourcompany.com
- Documentation: https://docs.yourcompany.com/key-rotation
- Emergency hotline: +1-XXX-XXX-XXXX
