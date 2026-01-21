# License Key File Loading - Implementation Summary

## Overview

Updated the license verification system to load public keys from files or environment variables instead of hardcoding them in the source code. This makes key management much easier and more flexible.

## What Changed

### Before
```python
# Hardcoded in api/services/license_service.py
PUBLIC_KEYS = {
    "v2": """-----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
    -----END PUBLIC KEY-----""",
}
```

**Problems**:
- Need to edit code to add/update keys
- Need to redeploy code for key changes
- Keys mixed with application logic
- Difficult to manage multiple environments

### After
```python
# Automatically loaded from files or env vars
def load_public_keys() -> Dict[str, str]:
    """Load public keys from api/core/keys/*.pem or environment variables"""
    # Priority: env vars > files > embedded fallback
    
PUBLIC_KEYS = load_public_keys()  # Auto-loaded on startup
```

**Benefits**:
✅ No code changes needed to add keys  
✅ Just copy files or set env vars  
✅ Easier key rotation  
✅ Better separation of concerns  
✅ Environment-specific configuration  

## How It Works

### Loading Priority (Highest to Lowest)

1. **Environment Variables** (highest priority)
   - `LICENSE_PUBLIC_KEY_V2`, `LICENSE_PUBLIC_KEY_V3`, etc.
   - Good for cloud deployments, secrets management

2. **Versioned Files**
   - `api/core/keys/public_key_v2.pem`, `api/core/keys/public_key_v3.pem`, etc.
   - Good for local development, version control

3. **Default File**
   - `api/core/keys/public_key.pem` (maps to DEFAULT_KEY_ID)
   - Good for simple single-key setups

4. **Embedded Fallback** (lowest priority)
   - Hardcoded in code for backward compatibility
   - Used only if no other keys found

### File Naming Convention

The version is extracted from the filename:

- `public_key_v2.pem` → key version "v2"
- `public_key_v3.pem` → key version "v3"
- `public_key.pem` → maps to DEFAULT_KEY_ID (from env or "v2")

## Usage Examples

### Example 1: File-based (Recommended)

```bash
# Copy public keys to api/core/keys/
cp license_server/keys/public_key_v2.pem api/core/keys/
cp license_server/keys/public_key_v3.pem api/core/keys/

# Set default key version
echo "LICENSE_DEFAULT_KEY_ID=v3" >> api/.env

# Restart application
docker-compose restart api

# Check logs
docker-compose logs api | grep "Loaded public key"
# Output:
# Loaded public key v2 from /app/keys/public_key_v2.pem
# Loaded public key v3 from /app/keys/public_key_v3.pem
```

### Example 2: Environment Variables

```bash
# In docker-compose.yml or .env
LICENSE_PUBLIC_KEY_V2="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

LICENSE_PUBLIC_KEY_V3="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"

LICENSE_DEFAULT_KEY_ID=v3
```

### Example 3: Hybrid Approach

```bash
# Use files for stable keys
cp license_server/keys/public_key_v2.pem api/core/keys/

# Use env var for latest key (easier to update)
export LICENSE_PUBLIC_KEY_V3="$(cat license_server/keys/public_key_v3.pem)"
export LICENSE_DEFAULT_KEY_ID=v3

# v2 from file, v3 from env var
```

### Example 4: Docker Compose

```yaml
services:
  api:
    environment:
      - LICENSE_DEFAULT_KEY_ID=v3
      - LICENSE_PUBLIC_KEY_V3=${LICENSE_PUBLIC_KEY_V3}
    volumes:
      - ./api/core/keys:/app/keys:ro  # Mount keys directory (read-only)
```

### Example 5: Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: license-keys
data:
  public_key_v2.pem: |
    -----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
    -----END PUBLIC KEY-----
  public_key_v3.pem: |
    -----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
    -----END PUBLIC KEY-----

---
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: api
    env:
    - name: LICENSE_DEFAULT_KEY_ID
      value: "v3"
    volumeMounts:
    - name: license-keys
      mountPath: /app/keys
      readOnly: true
  volumes:
  - name: license-keys
    configMap:
      name: license-keys
```

## Key Rotation Workflow

### Old Way (Code Changes Required)

```bash
1. Edit api/services/license_service.py
2. Add new key to PUBLIC_KEYS dict
3. Commit code changes
4. Build new Docker image
5. Deploy new image
6. Restart application
```

### New Way (No Code Changes)

```bash
# Just copy the new public key file
cp license_server/keys/public_key_v3.pem api/core/keys/

# Update default key version
echo "LICENSE_DEFAULT_KEY_ID=v3" >> api/.env

# Restart (no rebuild needed!)
docker-compose restart api
```

**Time saved**: Minutes instead of hours!

## Benefits by Use Case

### Development
✅ Easy to test different keys  
✅ No code changes needed  
✅ Fast iteration  
✅ Can use local files  

### Staging
✅ Environment-specific keys  
✅ Easy to sync with production  
✅ Can test key rotation  
✅ Separate from code deployment  

### Production
✅ No code deployment for key changes  
✅ Can use secrets management  
✅ Zero-downtime key rotation  
✅ Audit trail in file system  

### Multi-tenant
✅ Different keys per environment  
✅ Easy to manage multiple versions  
✅ Gradual rollout of new keys  
✅ Tenant-specific keys possible  

## Configuration Options

### Option 1: All Files (Simple)

```bash
api/core/keys/
├── public_key_v2.pem
├── public_key_v3.pem
└── README.md
```

**Pros**: Simple, version control friendly, easy to backup  
**Cons**: Need file system access to update  

### Option 2: All Environment Variables (Cloud-native)

```bash
LICENSE_PUBLIC_KEY_V2="..."
LICENSE_PUBLIC_KEY_V3="..."
LICENSE_DEFAULT_KEY_ID=v3
```

**Pros**: No files needed, good for containers, dynamic  
**Cons**: Env var size limits, harder to read  

### Option 3: Hybrid (Flexible)

```bash
# Stable keys in files
api/core/keys/public_key_v2.pem

# Latest key in env var
LICENSE_PUBLIC_KEY_V3="..."
LICENSE_DEFAULT_KEY_ID=v3
```

**Pros**: Best of both worlds, flexible, easy to update latest  
**Cons**: Need to manage both files and env vars  

## Migration Guide

### For Existing Deployments

If you already have keys hardcoded in `license_service.py`:

1. **Extract current key to file**:
   ```bash
   # Copy the public key from license_service.py
   cat > api/core/keys/public_key_v2.pem << 'EOF'
   -----BEGIN PUBLIC KEY-----
   MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
   -----END PUBLIC KEY-----
   EOF
   ```

2. **Deploy updated code**:
   ```bash
   # The new code will load from file
   docker-compose build api
   docker-compose up -d api
   ```

3. **Verify**:
   ```bash
   docker-compose logs api | grep "Loaded public key"
   # Should see: Loaded public key v2 from /app/keys/public_key_v2.pem
   ```

4. **Remove hardcoded key** (optional):
   - The embedded fallback will remain for safety
   - But keys will load from files first

### For New Deployments

1. **Copy public keys**:
   ```bash
   cp license_server/keys/public_key_*.pem api/core/keys/
   ```

2. **Set default key**:
   ```bash
   echo "LICENSE_DEFAULT_KEY_ID=v2" >> api/.env
   ```

3. **Deploy**:
   ```bash
   docker-compose up -d api
   ```

## Troubleshooting

### Keys Not Loading

**Check files exist**:
```bash
ls -la api/core/keys/public_key_*.pem
```

**Check file permissions**:
```bash
chmod 644 api/core/keys/public_key_*.pem
```

**Check logs**:
```bash
docker-compose logs api | grep -i "public key"
```

### Wrong Key Used

**Check default key ID**:
```bash
docker-compose exec api env | grep LICENSE_DEFAULT_KEY_ID
```

**Check loaded keys**:
```python
from services.license_service import PUBLIC_KEYS
print(list(PUBLIC_KEYS.keys()))
```

### Environment Variable Not Working

**Check format**:
```bash
# Must be: LICENSE_PUBLIC_KEY_V2 (uppercase, underscores)
# Not: license_public_key_v2 or LICENSE-PUBLIC-KEY-V2
```

**Check value**:
```bash
docker-compose exec api env | grep LICENSE_PUBLIC_KEY
```

## Security Considerations

### File-based
✅ Public keys are safe to commit to version control  
✅ Use read-only mounts in production  
✅ Set appropriate file permissions (644)  
⚠️ Ensure keys directory is not writable by application  

### Environment Variables
✅ Good for secrets management systems  
✅ Can be encrypted at rest  
✅ Easy to rotate without file system access  
⚠️ Be careful with logging (don't log env vars)  
⚠️ Some systems have env var size limits  

## Performance

- Keys loaded once on startup (not on every request)
- Minimal performance impact
- No disk I/O during license verification
- Keys cached in memory

## Testing

```bash
# Test key loading
cd api
python -c "
from services.license_service import PUBLIC_KEYS, DEFAULT_KEY_ID
print(f'Loaded keys: {list(PUBLIC_KEYS.keys())}')
print(f'Default key: {DEFAULT_KEY_ID}')
"

# Test license verification
cd license_server
python test_license_verification.py
```

## Documentation

- **Keys Directory README**: `api/core/keys/README.md`
- **Key Rotation Guide**: `docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md`
- **Implementation Details**: `docs/LICENSE_KEY_ROTATION_IMPLEMENTATION.md`
- **Quick Reference**: `license_server/KEY_ROTATION_QUICK_REF.md`

## Summary

The file-based key loading system provides:

✅ **Flexibility**: Load from files, env vars, or both  
✅ **Simplicity**: No code changes for key updates  
✅ **Security**: Separation of keys from code  
✅ **Scalability**: Easy to manage multiple key versions  
✅ **Maintainability**: Clear configuration, easy to audit  
✅ **Compatibility**: Backward compatible with embedded keys  

This makes key rotation and management significantly easier while maintaining security and reliability.
