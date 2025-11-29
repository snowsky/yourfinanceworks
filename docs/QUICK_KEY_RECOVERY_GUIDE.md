# Quick Key Recovery Guide

## Your Situation

You lost the old private key and generated a new one. Now old licenses don't work because they were signed with the old key.

## Immediate Solution

You have **two options**:

### Option 1: Keep Old Licenses Working (Recommended)

If you still have the **old public key**, you can support both old and new licenses:

1. **Find your old public key** (it was embedded in `api/services/license_service.py`)
2. **Add it to PUBLIC_KEYS** as "v1"
3. **Add new key** as "v2"
4. **Both work simultaneously**

```python
# In api/services/license_service.py
PUBLIC_KEYS = {
    "v2": """-----BEGIN PUBLIC KEY-----
    ...your new public key...
    -----END PUBLIC KEY-----""",
    
    "v1": """-----BEGIN PUBLIC KEY-----
    ...your old public key (from git history or backup)...
    -----END PUBLIC KEY-----""",
}

DEFAULT_KEY_ID = "v2"  # New licenses use v2
```

**How to find old public key:**
```bash
# Check git history
git log -p api/services/license_service.py | grep -A 10 "BEGIN PUBLIC KEY"

# Or check backups
grep -r "BEGIN PUBLIC KEY" backups/
```

### Option 2: Regenerate All Licenses (If Old Key Lost)

If you **don't have the old public key**, you must regenerate licenses:

1. **Update application** with new public key (already done)
2. **Regenerate all customer licenses** with new key
3. **Send new licenses** to all customers
4. **Provide support** for activation issues

## Step-by-Step Recovery

### Step 1: Check What You Have

```bash
# Check current public key in application
grep -A 10 "PUBLIC_KEY" api/services/license_service.py

# Check license server keys
ls -la license_server/keys/
ls -la api/core/keys/
```

### Step 2: Implement Multi-Key Support (Already Done!)

The code has been updated to support multiple keys. Now you just need to configure them.

### Step 3: Add Old Public Key (If Available)

```bash
# Find old public key from git
cd api
git log --all -p services/license_service.py | grep -B 2 -A 10 "BEGIN PUBLIC KEY" > /tmp/old_keys.txt
cat /tmp/old_keys.txt
```

Copy the old public key and add it to `PUBLIC_KEYS` as "v1".

### Step 4: Configure Current Setup

Update `api/services/license_service.py`:

```python
PUBLIC_KEYS = {
    # Current key - for new licenses
    "v2": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzexH7ckqeuCg2ZmyiMFS
7E9M7BUQn5Sase7Aus3pXwo9O5Kw0gq2ukgR32m6isAo5CV/CpyUgjPgVnJqPyYW
gm7fvoU5NrKESPjdnvqZrpy9ygcfAp67RX0wQaqqSSAFboq4AbPPR3tlTYIIGOC/
sy8MvcwsepJyDvUWxc07YJh8X1JVYuyQn/fD9D7OTMjQkevDC/LGhGgvm3dcxutt
wyVLDzTYV9zdw0bLzi45xLcevDFQxag20ZjTwWR7LWCVqJd4jRgktHmhUzDAAVs2
QVZyeUOG6EdWQcPZ7lArmtrb4rnWRgsthFggKBZWHDBhhiaOjH5mUSNcPKV99rK0
DwIDAQAB
-----END PUBLIC KEY-----""",
    
    # Add old key here if you have it:
    # "v1": """-----BEGIN PUBLIC KEY-----
    # ...old key...
    # -----END PUBLIC KEY-----""",
}

DEFAULT_KEY_ID = "v2"
```

### Step 5: Test

```bash
# Test that new licenses work
cd license_server
python test_license_verification.py

# Test an old license (if you have one)
python test_license_verification.py "eyJ..."
```

### Step 6: Deploy

```bash
# Rebuild and restart
docker-compose build api
docker-compose up -d api

# Verify
curl http://localhost:8000/api/v1/license/status
```

## For Your Specific Case

Since you mentioned the old private key is gone:

### If You Have Old Public Key

✅ **Best option**: Add it to PUBLIC_KEYS as "v1"  
✅ Old licenses continue working  
✅ No customer disruption  

### If You Don't Have Old Public Key

⚠️ **Must regenerate licenses**:

1. Generate new licenses for all customers:
```bash
cd license_server
python generate_license_cli.py \
  --email customer@example.com \
  --name "Customer Name" \
  --features ai_invoice,batch_processing \
  --days 365
```

2. Send new licenses to customers via email

3. Update documentation with new activation instructions

## Preventing This in the Future

1. **Backup keys regularly**:
```bash
cd license_server
tar czf keys_backup_$(date +%Y%m%d).tar.gz keys/
gpg -c keys_backup_*.tar.gz
# Store .gpg file in secure location
```

2. **Use version control for public keys** (safe to commit)

3. **Document key locations** in team wiki

4. **Set calendar reminder** for annual key rotation

5. **Use the new multi-key system** - makes recovery easier

## Quick Commands

```bash
# Generate new key version
cd license_server
python generate_new_key_version.py --version v3

# Test verification
python test_license_verification.py

# Generate test license
python generate_license_cli.py \
  --email test@example.com \
  --name "Test" \
  --features ai_invoice \
  --days 30

# Check what keys are configured
grep -A 2 "PUBLIC_KEYS = {" api/services/license_service.py
```

## Need Help?

1. Check if old public key exists in git history
2. Check if you have any backups
3. Check if old public key is in production deployment
4. If all else fails, regenerate licenses for affected customers

## Summary

✅ **Code updated** to support multiple keys  
✅ **New licenses** will include key version (v2)  
✅ **Old licenses** can work if you add old public key  
✅ **Future-proof** - can rotate keys without this problem  

The key insight: **Public keys are safe to keep forever**. Even if you lose the private key, keeping the old public key allows old licenses to continue working.
