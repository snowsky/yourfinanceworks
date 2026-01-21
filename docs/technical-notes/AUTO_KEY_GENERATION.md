# Automatic License Key Generation

## Overview

The license system now automatically generates RSA key pairs on first startup if no keys are found. This eliminates manual key generation steps and makes initial setup seamless.

## How It Works

### Startup Process

1. **Check for keys** in this order:
   - Environment variables (`LICENSE_PUBLIC_KEY_V2`, etc.)
   - Files in `api/core/keys/` directory (`public_key_*.pem`)
   - Default file (`api/core/keys/public_key.pem`)

2. **If no keys found**:
   - Automatically generates a new 2048-bit RSA key pair
   - Saves to `api/core/keys/private_key_{version}.pem` and `public_key_{version}.pem`
   - Sets secure file permissions (600 for private, 644 for public)
   - Creates a README with security notes
   - Loads the public key for immediate use

3. **Application starts** with the generated keys ready to use

### Generated Files

```
api/core/keys/
├── private_key_v2.pem    # Auto-generated private key (600 permissions)
├── public_key_v2.pem     # Auto-generated public key (644 permissions)
└── README.md             # Auto-generated security notes
```

## Benefits

✅ **Zero Configuration**: Works out of the box  
✅ **Development Friendly**: No manual setup needed  
✅ **Secure by Default**: Proper file permissions set automatically  
✅ **Production Ready**: Generated keys are production-grade (2048-bit RSA)  
✅ **Clear Warnings**: Displays security notes on generation  

## First Startup Example

```bash
# Start the application for the first time
docker-compose up api

# Console output:
============================================================
No license keys found - generating new key pair...
============================================================

Generating new RSA key pair (2048-bit)...
✓ Saved private key to: /app/keys/private_key_v2.pem
✓ Saved public key to: /app/keys/public_key_v2.pem

============================================================
⚠️  IMPORTANT SECURITY NOTES:
============================================================
- Private key saved to: private_key_v2.pem
- Keep the private key SECURE and NEVER commit to version control
- Add 'private_key_v2.pem' to .gitignore
- Public key saved to: public_key_v2.pem
- The public key is safe to distribute with the application
============================================================

✓ Generated and loaded new key pair as version v2
Loaded public key v2 from /app/keys/public_key_v2.pem
```

## Security Considerations

### Automatic Generation is Safe When:

✅ **Development**: Perfect for local development and testing  
✅ **First Deployment**: Good for initial production setup  
✅ **Isolated Environments**: Each environment gets its own keys  
✅ **Containerized**: Keys persist in volumes  

### Use Manual Generation When:

⚠️ **Shared Keys Needed**: Multiple instances need the same keys  
⚠️ **Key Rotation**: Upgrading from one key version to another  
⚠️ **Compliance**: Security policies require manual key management  
⚠️ **HSM Integration**: Using hardware security modules  

## Production Deployment

### Option 1: Auto-Generate (Simplest)

```bash
# First deployment - keys auto-generate
docker-compose up -d api

# Backup the generated keys
docker cp api:/app/keys/private_key_v2.pem ./backup/
docker cp api:/app/keys/public_key_v2.pem ./backup/

# Store backup securely (encrypted)
gpg -c backup/private_key_v2.pem
```

### Option 2: Pre-Generate (More Control)

```bash
# Generate keys before deployment
cd license_server
python generate_new_key_version.py --version v2

# Copy to application
cp keys/public_key_v2.pem ../api/core/keys/

# Deploy - uses pre-generated keys
docker-compose up -d api
```

### Option 3: Environment Variables (Cloud-Native)

```bash
# Generate keys
cd license_server
python generate_new_key_version.py --version v2

# Set as environment variables
export LICENSE_PUBLIC_KEY_V2="$(cat keys/public_key_v2.pem)"

# Deploy - no auto-generation needed
docker-compose up -d api
```

## Key Persistence

### Docker Volumes

```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - license-keys:/app/keys  # Persist generated keys

volumes:
  license-keys:
```

### Kubernetes Persistent Volume

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: license-keys
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Mi

---
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: api
    volumeMounts:
    - name: license-keys
      mountPath: /app/keys
  volumes:
  - name: license-keys
    persistentVolumeClaim:
      claimName: license-keys
```

## Disabling Auto-Generation

If you want to require manual key management:

```python
# In api/services/license_service.py
# Change the auto-generation section to:

if not public_keys:
    raise RuntimeError(
        "No license keys found. Please provide keys via:\n"
        "1. Files in api/core/keys/ directory\n"
        "2. Environment variables (LICENSE_PUBLIC_KEY_V2, etc.)\n"
        "3. Run: python api/scripts/generate_license_keys.py"
    )
```

Or set an environment variable:

```bash
# Disable auto-generation
export LICENSE_DISABLE_AUTO_GENERATION=true
```

## Troubleshooting

### Keys Not Persisting

**Problem**: Keys regenerate on every restart

**Solution**: Use Docker volumes or persistent storage
```bash
docker-compose down
# Add volume to docker-compose.yml
docker-compose up -d
```

### Permission Denied

**Problem**: Cannot write to keys directory

**Solution**: Check directory permissions
```bash
# Make keys directory writable
chmod 755 api/core/keys/

# Or run with appropriate user
docker-compose run --user $(id -u):$(id -g) api
```

### Import Error

**Problem**: `ImportError: cryptography package is required`

**Solution**: Install cryptography package
```bash
# Add to requirements.txt
echo "cryptography>=41.0.0" >> api/requirements.txt

# Rebuild container
docker-compose build api
```

### Keys Generated But Not Used

**Problem**: Keys generated but application uses different keys

**Solution**: Check loading priority
```bash
# Check what keys are loaded
docker-compose exec api python -c "
from services.license_service import PUBLIC_KEYS
print('Loaded keys:', list(PUBLIC_KEYS.keys()))
"
```

## Best Practices

### Development

1. **Let it auto-generate** on first run
2. **Commit public key** to version control (optional)
3. **Add private key to .gitignore**
4. **Share keys** with team via secure channel if needed

### Staging

1. **Auto-generate** or copy from development
2. **Use separate keys** from production
3. **Test key rotation** procedures
4. **Document key locations**

### Production

1. **Auto-generate on first deployment** OR pre-generate
2. **Immediately backup** generated keys
3. **Store backup encrypted** in secure location
4. **Document key version** and generation date
5. **Set up monitoring** for key usage
6. **Plan key rotation** schedule (annually)

## Migration from Hardcoded Keys

If you previously had hardcoded keys:

### Step 1: Extract Old Key

```bash
# Find old public key in git history
git log -p api/services/license_service.py | grep -A 10 "BEGIN PUBLIC KEY" > old_key.txt

# Save as v1 (for old licenses)
cat > api/core/keys/public_key_v1.pem << 'EOF'
-----BEGIN PUBLIC KEY-----
[paste old key]
-----END PUBLIC KEY-----
EOF
```

### Step 2: Generate New Key

```bash
# Let it auto-generate as v2
rm api/core/keys/public_key_v2.pem  # If exists
docker-compose restart api

# Or manually generate
cd license_server
python generate_new_key_version.py --version v2
cp keys/public_key_v2.pem ../api/core/keys/
```

### Step 3: Update Default

```bash
# Set v2 as default for new licenses
echo "LICENSE_DEFAULT_KEY_ID=v2" >> api/.env
docker-compose restart api
```

Now both old (v1) and new (v2) licenses work!

## Comparison: Manual vs Auto-Generation

### Manual Generation

**Pros**:
- Full control over key generation
- Can use specific key sizes (4096-bit)
- Can integrate with HSM
- Audit trail of generation

**Cons**:
- Extra setup step
- Easy to forget
- Requires documentation
- Slows down development

### Auto-Generation

**Pros**:
- Zero setup required
- Works immediately
- Perfect for development
- Reduces errors

**Cons**:
- Less control
- Fixed key size (2048-bit)
- May regenerate if not persisted
- Requires backup strategy

## Recommendation

**Development**: Use auto-generation (default)  
**Staging**: Use auto-generation with backups  
**Production**: Use auto-generation on first deploy, then backup and manage manually  
**Enterprise**: Pre-generate with HSM integration  

## Summary

Auto-generation makes license key management effortless while maintaining security. The system:

✅ Generates keys automatically when needed  
✅ Sets secure permissions by default  
✅ Provides clear security warnings  
✅ Works seamlessly in containers  
✅ Supports manual override when needed  
✅ Maintains backward compatibility  

For most use cases, auto-generation is the best choice. For advanced scenarios, manual key management is still fully supported.
