# License Keys Directory

This directory contains RSA public keys used for license verification.

## Overview

The application automatically loads public keys from this directory to verify license signatures. Multiple key versions can coexist to support key rotation without invalidating existing licenses.

## File Naming Convention

Public keys should follow these naming patterns:

- `public_key.pem` - Default public key (maps to DEFAULT_KEY_ID)
- `public_key_v2.pem` - Public key version 2
- `public_key_v3.pem` - Public key version 3
- `public_key_v4.pem` - Public key version 4
- etc.

**Important**: Private keys should NEVER be stored here. They belong on the license server only.

## How It Works

On startup, the application:

1. Scans this directory for `public_key_*.pem` files
2. Extracts the version from the filename (e.g., `v2` from `public_key_v2.pem`)
3. Loads each key into memory
4. Uses the appropriate key based on the license's `kid` (key ID) field

## Loading Priority

Public keys are loaded in this order (highest priority first):

1. **Environment variables**: `LICENSE_PUBLIC_KEY_V2`, `LICENSE_PUBLIC_KEY_V3`, etc.
2. **Versioned files**: `public_key_v2.pem`, `public_key_v3.pem`, etc.
3. **Default file**: `public_key.pem` (maps to DEFAULT_KEY_ID)
4. **Embedded fallback**: Hardcoded key in code (for backward compatibility)

## Configuration Methods

### Method 1: File-based (Recommended)

```bash
# Copy public keys from license server
cp ../license_server/keys/public_key_v2.pem api/core/keys/
cp ../license_server/keys/public_key_v3.pem api/core/keys/

# Application automatically loads them on startup
docker-compose restart api
```

### Method 2: Environment Variables

```bash
# In .env file
LICENSE_PUBLIC_KEY_V2="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

LICENSE_PUBLIC_KEY_V3="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

# Set default key version
LICENSE_DEFAULT_KEY_ID=v3
```

### Method 3: Docker Compose

```yaml
services:
  api:
    environment:
      - LICENSE_DEFAULT_KEY_ID=v3
      - LICENSE_PUBLIC_KEY_V3=${LICENSE_PUBLIC_KEY_V3}
      - LICENSE_PUBLIC_KEY_V2=${LICENSE_PUBLIC_KEY_V2}
    volumes:
      - ./api/core/keys:/app/keys:ro  # Mount keys directory (read-only)
```

## Key Rotation Workflow

### Step 1: Generate New Key Pair

```bash
cd license_server
python generate_new_key_version.py --version v3
```

### Step 2: Add New Public Key

```bash
# Copy to application keys directory
cp license_server/keys/public_key_v3.pem api/core/keys/

# Keep old keys for existing licenses
ls -la api/core/keys/
# Should show: public_key_v2.pem, public_key_v3.pem
```

### Step 3: Update Default Key

```bash
# In .env or docker-compose.yml
LICENSE_DEFAULT_KEY_ID=v3
```

### Step 4: Restart Application

```bash
docker-compose restart api

# Check logs for confirmation
# Should see: "Loaded public key v3 from /app/keys/public_key_v3.pem"
```

### Step 5: Update License Server

```bash
cd license_server
# Update license_generator.py to use new key
# CURRENT_KEY_VERSION = "v3"
# PRIVATE_KEY_PATH = Path(__file__).parent / "keys" / "private_key_v3.pem"
```

Now both old (v2) and new (v3) licenses will work!

## Security

✅ **Public keys are safe to commit** to version control  
✅ **Public keys can be distributed** with the application  
✅ **Multiple versions can coexist** for key rotation  
✅ **Read-only permissions recommended** (chmod 644)

⚠️ **Private keys should NEVER be here** - they belong on the license server only  
⚠️ **Private keys should NEVER be committed** to version control  
⚠️ **This directory is for public keys only**

## Verification

### Check Loaded Keys

```bash
# Start application and check logs
docker-compose up api

# Expected output:
# Loaded public key v2 from /app/keys/public_key_v2.pem
# Loaded public key v3 from /app/keys/public_key_v3.pem
```

### Programmatic Check

```python
from services.license_service import PUBLIC_KEYS, DEFAULT_KEY_ID

print(f"Available keys: {list(PUBLIC_KEYS.keys())}")
print(f"Default key: {DEFAULT_KEY_ID}")
```

### Test License Verification

```bash
cd license_server
python test_license_verification.py "eyJhbGc..."
```

## Troubleshooting

### No Keys Loaded

**Symptom**: "Warning: No public keys found in files or environment"

**Solutions**:

- Check files exist: `ls -la api/core/keys/public_key_*.pem`
- Check file permissions: `chmod 644 api/core/keys/public_key_*.pem`
- Check file format: Should start with `-----BEGIN PUBLIC KEY-----`
- Check path: Keys should be in `api/core/keys/` directory

### Old Licenses Don't Work

**Symptom**: "Invalid license signature" or "Unknown key ID: v2"

**Solutions**:

- Ensure old public key exists: `ls api/core/keys/public_key_v2.pem`
- Check license key ID:

  ```python
  import jwt
  payload = jwt.decode(license_key, options={"verify_signature": False})
  print(f"License kid: {payload.get('kid')}")
  ```

- Verify public key matches the private key that signed the license
- Restart application to reload keys

### Key Version Mismatch

**Symptom**: License has `kid: v3` but verification fails

**Solutions**:

- Check if `public_key_v3.pem` exists in this directory
- Verify file content matches public key from license server:

  ```bash
  diff api/core/keys/public_key_v3.pem license_server/keys/public_key_v3.pem
  ```

- Restart application: `docker-compose restart api`

### Environment Variable Not Working

**Symptom**: Key set in env var but not loaded

**Solutions**:

- Check env var name format: `LICENSE_PUBLIC_KEY_V3` (uppercase, underscores)
- Verify env var is set: `docker-compose exec api env | grep LICENSE`
- Check for newlines in env var value (should be preserved)
- Restart application after changing env vars

## Examples

### Single Key Setup (Simple)

```bash
# Copy current public key
cp license_server/keys/public_key.pem api/core/keys/

# Application uses it as default (v2)
docker-compose restart api
```

### Multi-Key Setup (Key Rotation)

```bash
# Copy all public key versions
cp license_server/keys/public_key_v2.pem api/core/keys/
cp license_server/keys/public_key_v3.pem api/core/keys/

# Set default to latest
echo "LICENSE_DEFAULT_KEY_ID=v3" >> .env

# Restart
docker-compose restart api

# Both v2 and v3 licenses will work
```

### Environment Variable Setup (Cloud)

```bash
# Set in cloud provider's environment config
export LICENSE_PUBLIC_KEY_V3="$(cat license_server/keys/public_key_v3.pem)"
export LICENSE_DEFAULT_KEY_ID=v3

# No files needed - loaded from env vars
```

### Docker Secrets (Production)

```yaml
services:
  api:
    secrets:
      - license_public_key_v3
    environment:
      - LICENSE_PUBLIC_KEY_V3_FILE=/run/secrets/license_public_key_v3
      - LICENSE_DEFAULT_KEY_ID=v3

secrets:
  license_public_key_v3:
    file: ./license_server/keys/public_key_v3.pem
```

## Key Specifications

- **Algorithm**: RSA
- **Key Size**: 2048 bits (minimum), 4096 bits (recommended for new keys)
- **Format**: PEM
- **Signature Algorithm**: RS256 (RSA with SHA-256)
- **Encoding**: UTF-8

## Best Practices

1. **Keep Old Keys**: Don't delete old public keys until all customers have migrated
2. **Version Everything**: Always use versioned filenames (public_key_v2.pem, not public_key.pem)
3. **Document Versions**: Keep a log of which key versions are in use
4. **Test Before Deploy**: Verify both old and new licenses work before production deployment
5. **Monitor Usage**: Track which key versions are being used in production
6. **Regular Rotation**: Rotate keys annually as part of security maintenance
7. **Backup Keys**: Keep encrypted backups of all key versions

## Related Documentation

- **Key Rotation Guide**: `docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md`
- **Implementation Details**: `docs/LICENSE_KEY_ROTATION_IMPLEMENTATION.md`
- **Quick Recovery**: `docs/QUICK_KEY_RECOVERY_GUIDE.md`
- **Quick Reference**: `license_server/KEY_ROTATION_QUICK_REF.md`

## Support

For questions or issues with license keys:

- Check the troubleshooting section above
- Review the key rotation documentation
- Test with `license_server/test_license_verification.py`
- Check application logs for key loading messages
