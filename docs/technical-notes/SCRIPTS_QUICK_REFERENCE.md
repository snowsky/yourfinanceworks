# Cloud Storage Scripts Quick Reference

## 🚀 Quick Start Commands

### Validate Configuration
```bash
# Basic validation
python scripts/validate_cloud_storage_config.py

# Test specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3 --verbose

# JSON output for automation
python scripts/validate_cloud_storage_config.py --json
```

### Interactive Setup
```bash
# Full interactive setup
python scripts/setup_cloud_storage.py --interactive

# Dry run (no changes)
python scripts/setup_cloud_storage.py --dry-run --verbose

# Setup specific provider
python scripts/setup_cloud_storage.py --provider aws_s3
```

### Deployment Check
```bash
# Production readiness check
python scripts/cloud_storage_deployment_check.py --environment production

# Auto-fix issues
python scripts/cloud_storage_deployment_check.py --fix-issues --verbose

# Staging environment
python scripts/cloud_storage_deployment_check.py --environment staging --json
```

### Configuration Management
```bash
# Generate environment config
python scripts/manage_cloud_storage_config.py generate production --providers aws_s3 azure_blob

# Validate environment
python scripts/manage_cloud_storage_config.py validate production

# Deploy configuration
python scripts/manage_cloud_storage_config.py deploy production

# Compare environments
python scripts/manage_cloud_storage_config.py compare staging production

# Backup current config
python scripts/manage_cloud_storage_config.py backup

# List available configs
python scripts/manage_cloud_storage_config.py list configs
```

## 📋 Script Overview

| Script | Purpose | Key Features |
|--------|---------|--------------|
| `validate_cloud_storage_config.py` | Configuration validation & connectivity testing | ✅ Syntax validation<br>🔗 Provider connectivity<br>📊 JSON output |
| `setup_cloud_storage.py` | Interactive setup wizard | 🎯 Guided setup<br>🏗️ Resource creation<br>🧪 Configuration testing |
| `cloud_storage_deployment_check.py` | Pre-deployment readiness checks | 🔍 Comprehensive checks<br>🔧 Auto-fix capabilities<br>📈 Deployment scoring |
| `manage_cloud_storage_config.py` | Environment configuration management | 🌍 Multi-environment<br>📦 Backup/restore<br>🔄 Config comparison |

## 🎯 Common Use Cases

### First-Time Setup
```bash
# 1. Interactive setup
python scripts/setup_cloud_storage.py --interactive

# 2. Validate configuration
python scripts/validate_cloud_storage_config.py --verbose

# 3. Check deployment readiness
python scripts/cloud_storage_deployment_check.py --environment production
```

### Environment Management
```bash
# Generate configs for all environments
python scripts/manage_cloud_storage_config.py generate development
python scripts/manage_cloud_storage_config.py generate staging --providers aws_s3
python scripts/manage_cloud_storage_config.py generate production --providers aws_s3 azure_blob

# Deploy to staging
python scripts/manage_cloud_storage_config.py deploy staging

# Compare staging vs production
python scripts/manage_cloud_storage_config.py compare staging production
```

### CI/CD Integration
```bash
# Validation pipeline
python scripts/validate_cloud_storage_config.py --json > validation.json
python scripts/cloud_storage_deployment_check.py --environment production --json > deployment.json

# Check exit codes
if [ $? -eq 0 ]; then
    echo "✅ Ready for deployment"
else
    echo "❌ Deployment blocked"
    exit 1
fi
```

### Troubleshooting
```bash
# Debug configuration issues
python scripts/validate_cloud_storage_config.py --verbose

# Test specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3 --verbose

# Check deployment issues
python scripts/cloud_storage_deployment_check.py --environment production --verbose
```

## 🔧 Configuration Files

### Templates
- `.env.cloud-storage.example` - Complete configuration template
- `config/environments/development.env` - Development settings
- `config/environments/staging.env` - Staging settings
- `config/environments/production.env` - Production settings

### Backups
- `config/backups/` - Configuration backups with timestamps
- Format: `{name}_backup_{YYYYMMDD_HHMMSS}.env`

## 🚨 Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| `0` | Success | ✅ Continue |
| `1` | Failure/Issues | ❌ Fix issues before proceeding |

## 🔍 Output Formats

### Human-Readable (Default)
```
✅ Configuration validation: PASSED
🔗 Provider connectivity: aws_s3 CONNECTED, local CONNECTED
📊 Summary: Ready for deployment
```

### JSON (--json flag)
```json
{
  "config_validation": {"valid": true, "errors": [], "warnings": []},
  "connectivity": {"aws_s3": {"success": true}, "local": {"success": true}},
  "summary": {"deployment_ready": true}
}
```

## 🛠️ Environment Variables

### Required for AWS S3
```bash
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=your-bucket
AWS_S3_REGION=us-east-1
AWS_S3_ACCESS_KEY_ID=your-key
AWS_S3_SECRET_ACCESS_KEY=your-secret
```

### Required for Azure Blob
```bash
AZURE_BLOB_ENABLED=true
AZURE_STORAGE_ACCOUNT_NAME=youraccount
AZURE_STORAGE_ACCOUNT_KEY=your-key
AZURE_CONTAINER_NAME=attachments
```

### Required for GCP Storage
```bash
GCP_STORAGE_ENABLED=true
GCP_PROJECT_ID=your-project
GCP_BUCKET_NAME=your-bucket
GCP_CREDENTIALS_PATH=/path/to/key.json
```

## 🆘 Quick Troubleshooting

### Import Errors
```bash
# Ensure correct directory
cd /path/to/invoice_app
python api/scripts/validate_cloud_storage_config.py
```

### Permission Errors
```bash
# Check file permissions
ls -la api/scripts/
chmod +x api/scripts/*.py
```

### Configuration Errors
```bash
# Use verbose mode for details
python scripts/validate_cloud_storage_config.py --verbose

# Check specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3 --verbose
```

### Connectivity Issues
```bash
# Test network connectivity
curl -I https://s3.amazonaws.com
curl -I https://youraccount.blob.core.windows.net

# Check credentials
aws sts get-caller-identity  # For AWS
az account show              # For Azure
gcloud auth list            # For GCP
```

## 📚 Documentation Links

- **Complete Guide**: `docs/CLOUD_STORAGE_DEPLOYMENT_GUIDE.md`
- **Script Reference**: `docs/CLOUD_STORAGE_SCRIPTS_REFERENCE.md`
- **Configuration Guide**: `api/config/README.md`

## 💡 Pro Tips

1. **Always validate before deploying**: Run validation scripts in CI/CD pipelines
2. **Use environment-specific configs**: Keep separate configurations for dev/staging/prod
3. **Backup before changes**: Use the backup command before making configuration changes
4. **Test connectivity regularly**: Schedule periodic validation checks
5. **Use JSON output for automation**: Integrate with monitoring and alerting systems
6. **Enable verbose logging for debugging**: Use `--verbose` flag when troubleshooting
7. **Check exit codes in scripts**: Use exit codes for automated decision making