# License Key Generation Improvements for Docker

## Summary

Enhanced the RSA key pair generation system to be more robust for Docker container environments, addressing the issue of missing private/public keys when the API container starts.

**Important**: This is about RSA key pairs (private_key.pem/public_key.pem) used to sign and verify license JWTs, NOT about generating actual licenses.

## Changes Made

### 1. Enhanced Key Generation Script (`generate_license_keys.py`)

**Improvements:**
- Added `--non-interactive` flag for automated/Docker environments
- Added symlink fallback for Windows/systems without symlink support
- Better error handling with graceful degradation

**Key Changes:**
```python
# Non-interactive mode for Docker
parser.add_argument('--non-interactive', action='store_true',
                    help='Run in non-interactive mode (auto-confirm)')

# Symlink fallback
try:
    os.symlink(target, link_path)
except (OSError, NotImplementedError) as e:
    # Fallback: copy file if symlinks not supported
    shutil.copy2(os.path.join(os.path.dirname(link_path), target), link_path)
```

### 2. Docker Build-Time Key Generation (`Dockerfile`)

**Added:**
- Key directory creation during build
- Optional pre-generation of keys during image build
- Graceful failure if generation fails

```dockerfile
# Create directories
RUN mkdir -p /app/data /app/core/keys

# Pre-generate license keys during build (optional)
RUN python scripts/generate_license_keys.py --non-interactive --force || echo "Key generation skipped"
```

### 3. License Service Improvements (`license_service.py`)

**Enhanced:**
- Better distinction between master server keys and local signing keys
- Environment variable control: `LICENSE_AUTO_GENERATE`
- Improved error messages and warnings

**Key Logic:**
```python
# Check if we have LOCAL signing keys (not just the master server key)
local_keys = {k: v for k, v in public_keys.items() if k not in ["server_v1"]}

# Check environment variable to control auto-generation
auto_generate_keys = os.getenv("LICENSE_KEY_AUTO_GENERATE", "true").lower() == "true"

if not local_keys and auto_generate_keys:
    # Auto-generate keys
    ...
elif not local_keys and not auto_generate:
    # Warning only, don't fail
    print("WARNING: No local license keys found and auto-generation is disabled")
```

### 4. Environment Configuration (`.env.license.example`)

**Created:**
- Configuration file for RSA key pair settings
- Control auto-generation behavior

```bash
# Auto-generate RSA key pairs (private/public keys) on startup if missing
# These keys are used to sign and verify license JWTs
LICENSE_KEY_AUTO_GENERATE=true

# Key version to use (optional)
# LICENSE_KEY_VERSION=v1
```

## How It Works

### Two-Layer Approach

1. **Build Time (Optional)**
   - Keys can be pre-generated during Docker image build
   - Fails gracefully if generation fails
   - Useful for production images

2. **Runtime (Primary)**
   - License service checks for RSA key pairs on module import
   - Auto-generates if enabled and none found
   - Can be disabled via `LICENSE_KEY_AUTO_GENERATE=false`

### Key Detection Logic

The system now correctly distinguishes between:
- **Master Public Key** (`master_public_key.pem` / `server_v1`) - For verifying server-issued licenses
- **Local RSA Key Pairs** (`private_key_v*.pem`, `public_key_v*.pem`) - For signing own licenses

Only generates new RSA key pairs if **local signing keys** are missing, not when only the master key exists.

## Benefits

1. **Robust Startup**: Runtime auto-generation ensures keys exist when needed
2. **Docker-Friendly**: Non-interactive mode works in automated environments
3. **Flexible**: Can disable auto-generation for production security
4. **Cross-Platform**: Symlink fallback for Windows compatibility
5. **Clear Messaging**: Better error messages and warnings
6. **Simple**: Two-layer approach (build + runtime) is easy to understand

## Usage

### Development (Auto-Generate)
```bash
# Default behavior - auto-generates keys
docker-compose up --build
```

### Production (Pre-Generated)
```bash
# Generate RSA key pairs before building
python api/scripts/generate_license_keys.py --force

# Build with keys included
docker-compose up --build

# Or disable auto-generation
export LICENSE_KEY_AUTO_GENERATE=false
docker-compose up --build
```

### Manual Generation
```bash
# Generate specific version
python api/scripts/generate_license_keys.py --version v2 --force

# Non-interactive mode
python api/scripts/generate_license_keys.py --non-interactive --force
```

## Security Considerations

1. **Private Key Protection**: RSA private keys are generated with secure permissions (600)
2. **Gitignore**: All `.pem` files are excluded from version control
3. **Production Control**: Can disable auto-generation via environment variable
4. **Audit Trail**: RSA key pair generation is logged for security monitoring

## Testing

To verify the improvements work:

```bash
# Remove existing keys
rm -rf api/core/keys/*.pem

# Start containers
docker-compose up --build

# Check logs for key generation
docker-compose logs api | grep -i "license key"

# Verify keys exist
docker-compose exec api ls -la /app/core/keys/
```

## Troubleshooting

If RSA key pairs are still missing:

1. Check `LICENSE_KEY_AUTO_GENERATE` is not set to `false`
2. Verify directory permissions: `mkdir -p api/core/keys`
3. Check Docker logs: `docker-compose logs api`
4. Manually generate: `docker-compose exec api python scripts/generate_license_keys.py --force`
5. Verify cryptography package: `docker-compose exec api pip list | grep cryptography`

## Related Files

- `api/scripts/generate_license_keys.py` - Key generation script
- `api/core/services/license_service.py` - License service with auto-generation
- `api/Dockerfile` - Docker build configuration
- `docker-compose.yml` - Container orchestration
- `api/.env.license.example` - Environment configuration example
