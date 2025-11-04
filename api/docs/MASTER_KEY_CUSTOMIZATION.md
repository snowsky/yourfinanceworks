# Master Key Customization Guide

This guide explains how to customize the master encryption key for your database encryption system.

## Overview

The master key is a 256-bit (32-byte) AES key used to encrypt tenant-specific data encryption keys. It's stored as a base64-encoded string.

## Key Requirements

- **Length**: Exactly 32 bytes (256 bits) when decoded
- **Format**: Base64 encoded string
- **Algorithm**: Used with AES-256-GCM encryption
- **Storage**: File-based or environment variable

## Customization Methods

### Method 1: Generate Random Key (Recommended)

```bash
# Using the provided script
./api/scripts/create_simple_master_key.sh random

# Or manually with OpenSSL
openssl rand -base64 32 > /app/keys/master.key
chmod 600 /app/keys/master.key
```

### Method 2: Derive from Passphrase

```bash
# Using the script
./api/scripts/create_simple_master_key.sh passphrase "your-secure-passphrase"

# Or using the Python generator
python api/scripts/generate_custom_master_key.py
```

### Method 3: Use Existing Base64 Key

```bash
# If you have an existing base64 key
./api/scripts/create_simple_master_key.sh custom "your-base64-encoded-key-here"
```

### Method 4: Environment Variable (Production Recommended)

Instead of a file, set the key as an environment variable:

```bash
export MASTER_KEY="your-base64-encoded-key-here"
```

## Configuration Options

### File-Based Storage (Default)

```env
KEY_VAULT_PROVIDER=local
MASTER_KEY_PATH=/app/keys/master.key
MASTER_KEY_ID=your-custom-key-id
```

### Environment Variable Storage

```env
KEY_VAULT_PROVIDER=local
MASTER_KEY=your-base64-encoded-key-here
MASTER_KEY_ID=your-custom-key-id
```

### External Key Vaults

#### AWS KMS
```env
KEY_VAULT_PROVIDER=aws_kms
AWS_KMS_MASTER_KEY_ID=your-kms-key-id
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

#### Azure Key Vault
```env
KEY_VAULT_PROVIDER=azure_keyvault
AZURE_KEYVAULT_URL=https://your-vault.vault.azure.net/
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
```

#### HashiCorp Vault
```env
KEY_VAULT_PROVIDER=hashicorp_vault
HASHICORP_VAULT_URL=https://your-vault.example.com
HASHICORP_VAULT_TOKEN=your-vault-token
HASHICORP_VAULT_NAMESPACE=your-namespace
```

## Key Rotation

Enable automatic key rotation:

```env
KEY_ROTATION_ENABLED=true
KEY_ROTATION_INTERVAL_DAYS=90
```

## Security Best Practices

### 1. File Permissions
```bash
# Ensure only owner can read/write
chmod 600 /app/keys/master.key
chown app:app /app/keys/master.key
```

### 2. Directory Security
```bash
# Secure the keys directory
chmod 700 /app/keys
chown app:app /app/keys
```

### 3. Backup Strategy
```bash
# Create secure backups
mkdir -p /backup/keys/$(date +%Y%m%d)
cp /app/keys/master.key /backup/keys/$(date +%Y%m%d)/
chmod 600 /backup/keys/$(date +%Y%m%d)/master.key
```

### 4. Environment Variables (Production)
- Use environment variables instead of files in production
- Store in secure secret management systems
- Rotate regularly

## Validation

### Check Key Format
```bash
# Verify base64 format and length
KEY_CONTENT=$(cat /app/keys/master.key)
echo "$KEY_CONTENT" | base64 -d | wc -c  # Should output: 32
```

### Test Key Loading
```python
# Test with Python
import base64
with open('/app/keys/master.key', 'rb') as f:
    encoded_key = f.read()
    decoded_key = base64.b64decode(encoded_key)
    print(f"Key length: {len(decoded_key)} bytes")  # Should be 32
```

## Troubleshooting

### Common Issues

1. **Wrong Key Length**
   ```
   Error: Key must be 32 bytes (256 bits)
   ```
   Solution: Regenerate key with correct length

2. **Invalid Base64**
   ```
   Error: Failed to decode master key
   ```
   Solution: Ensure key is properly base64 encoded

3. **Permission Denied**
   ```
   Error: Cannot read master key file
   ```
   Solution: Check file permissions and ownership

4. **Key Not Found**
   ```
   Error: Master key file not found
   ```
   Solution: Create key file or set MASTER_KEY environment variable

## Migration

### From File to Environment Variable
```bash
# Read existing key
EXISTING_KEY=$(cat /app/keys/master.key)

# Set as environment variable
export MASTER_KEY="$EXISTING_KEY"

# Update configuration
unset MASTER_KEY_PATH
```

### From Environment to File
```bash
# Create key file from environment
echo "$MASTER_KEY" > /app/keys/master.key
chmod 600 /app/keys/master.key

# Update configuration
export MASTER_KEY_PATH="/app/keys/master.key"
unset MASTER_KEY
```

## Examples

### Generate and Use Custom Key
```bash
# Generate custom key
python api/scripts/generate_custom_master_key.py

# Or use simple script
./api/scripts/create_simple_master_key.sh random

# Verify in application
docker-compose exec api python -c "
from services.key_management_service import KeyManagementService
from encryption_config import EncryptionConfig
config = EncryptionConfig()
kms = KeyManagementService(config)
print('Master key loaded successfully:', len(kms.get_master_key()) > 0)
"
```

### Custom Passphrase-Based Key
```bash
# Generate from passphrase
python api/scripts/generate_custom_master_key.py
# Choose option 2, enter your passphrase

# Or use OpenSSL
echo -n "your-secure-passphrase" | openssl dgst -sha256 -binary | openssl base64 > /app/keys/master.key
```

This customization allows you to have full control over your encryption keys while maintaining security best practices.