# Vendor Encryption Mismatch Fix

## Problem Summary

The vendor encryption mismatch was caused by inconsistent key derivation parameters between the API container and OCR worker container. This resulted in:

- **API Container**: Could not decrypt vendor data encrypted by OCR worker
- **OCR Worker**: Could decrypt its own encrypted data but API container could not
- **Root Cause**: Different `KEY_DERIVATION_ITERATIONS` values between containers

## Technical Details

### Issue Identification

1. **Same Base Key**: Both containers had identical tenant keys (`heZSbCbXC1/B4HiEMxF285waNDc2mZq5v1MDDd199AI=`)
2. **Different Derived Keys**: 
   - API Container: `026df1c76bb23f6d0caff4f13ec6c95d8a97c9e468a8fe2ad04ef3f1e059881d`
   - OCR Worker (before fix): `a7617a0aa902ed206c7bf829c6de238de560f7a57806bcfae2735115415d3c13`
3. **Environment Variable Mismatch**:
   - API Container: `KEY_DERIVATION_ITERATIONS=100000`
   - OCR Worker: `KEY_DERIVATION_ITERATIONS=NOT_SET` (defaulted to 10000)

### Root Cause

The OCR worker service in `docker-compose.yml` was missing the `KEY_DERIVATION_ITERATIONS` environment variable, causing it to use the default value of 10,000 iterations while the API container used 100,000 iterations.

## Solution Applied

### Step 1: Fix Docker Compose Configuration

Updated `docker-compose.yml` to include the missing environment variable in the OCR worker service:

```yaml
# Database Encryption Configuration
- ENCRYPTION_ENABLED=${ENCRYPTION_ENABLED:-true}
- ENCRYPTION_ALGORITHM=${ENCRYPTION_ALGORITHM:-AES-256-GCM}
- KEY_DERIVATION_ITERATIONS=${KEY_DERIVATION_ITERATIONS:-100000}  # Added this line
- KEY_VAULT_PROVIDER=${KEY_VAULT_PROVIDER:-local}
- MASTER_KEY_ID=${MASTER_KEY_ID:-default-master-key}
- MASTER_KEY_PATH=${MASTER_KEY_PATH:-/app/keys/master.key}
```

### Step 2: Restart OCR Worker

Restarted the OCR worker container to apply the new environment variable:

```bash
docker-compose down ocr-worker
docker-compose up -d ocr-worker
```

### Step 3: Re-encrypt Problematic Data

The old encrypted data was still encrypted with the wrong key derivation parameters. Used the fix script to re-encrypt the problematic vendor data:

```bash
docker exec invoice_app_api python fix_vendor_encryption_mismatch.py
```

This script:
1. Decrypted the known plaintext value ("GoodLife Fitness")
2. Re-encrypted it using the correct key derivation parameters
3. Updated the database with the new encrypted value

### Step 4: Verification

Verified that both containers can now:
1. Use the same derived encryption key
2. Successfully decrypt the re-encrypted vendor data
3. Encrypt/decrypt new data consistently

## Files Modified

1. **docker-compose.yml**: Added `KEY_DERIVATION_ITERATIONS` to OCR worker
2. **api/fix_vendor_encryption_mismatch.py**: Script to re-encrypt problematic data
3. **Database**: Updated expense record ID 9 with re-encrypted vendor data

## Diagnostic Scripts Created

1. **check_encryption_env.py**: Compare environment variables between containers
2. **debug_encryption_mismatch.py**: Step-by-step decryption debugging
3. **test_fixed_encryption.py**: Verify both containers can decrypt fixed data

## Prevention

To prevent this issue in the future:

1. **Environment Variable Consistency**: Ensure all encryption-related environment variables are consistently defined across all services in docker-compose.yml
2. **Configuration Validation**: Add startup checks to verify encryption configuration consistency
3. **Monitoring**: Set up alerts for encryption/decryption failures
4. **Documentation**: Maintain clear documentation of required environment variables

## Key Learnings

1. **PBKDF2 Sensitivity**: Small differences in key derivation parameters (iterations, salt) result in completely different derived keys
2. **Container Configuration**: Environment variables must be consistently defined across all services that share encrypted data
3. **Debugging Approach**: Step-by-step decryption debugging was crucial to identify the exact point of failure
4. **Data Migration**: When fixing encryption mismatches, existing encrypted data must be re-encrypted with correct parameters

## Status

✅ **RESOLVED**: Both API container and OCR worker now use consistent encryption parameters and can successfully encrypt/decrypt shared data.

## Test Results

- ✅ Both containers derive identical encryption keys
- ✅ Both containers can decrypt the fixed vendor data
- ✅ Fresh encryption/decryption works consistently
- ✅ End-to-end OCR workflow functions without encryption errors
- ✅ No more authentication tag verification failures