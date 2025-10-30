# Cloud Storage Configuration Tools

This directory contains configuration management tools for the cloud file storage system.

## Files

### Configuration Templates

- **`.env.cloud-storage.example`** - Complete environment variable template with all cloud storage settings
- **`cloud_storage_config.py`** - Configuration classes and validation logic

### Management Scripts

- **`scripts/setup_cloud_storage.py`** - Interactive setup wizard for cloud storage providers
- **`scripts/validate_cloud_storage_config.py`** - Configuration validation and connectivity testing
- **`scripts/cloud_storage_deployment_check.py`** - Pre-deployment readiness checks
- **`scripts/manage_cloud_storage_config.py`** - Configuration management across environments

## Quick Start

### 1. Interactive Setup (Recommended)

```bash
cd api
python scripts/setup_cloud_storage.py --interactive --verbose
```

This will guide you through:
- Provider selection (AWS S3, Azure Blob, GCP Storage)
- Authentication configuration
- Resource creation (buckets/containers)
- Configuration file generation

### 2. Manual Configuration

```bash
# Copy template
cp .env.cloud-storage.example .env

# Edit configuration
nano .env

# Validate configuration
python scripts/validate_cloud_storage_config.py --verbose
```

### 3. Environment Management

```bash
# Generate configuration for different environments
python scripts/manage_cloud_storage_config.py generate production --providers aws_s3 azure_blob
python scripts/manage_cloud_storage_config.py generate staging --providers aws_s3
python scripts/manage_cloud_storage_config.py generate development

# Validate environment configuration
python scripts/manage_cloud_storage_config.py validate production

# Deploy configuration
python scripts/manage_cloud_storage_config.py deploy production

# Compare environments
python scripts/manage_cloud_storage_config.py compare staging production
```

### 4. Deployment Readiness Check

```bash
# Check if ready for deployment
python scripts/cloud_storage_deployment_check.py --environment production --verbose

# Fix issues automatically (if possible)
python scripts/cloud_storage_deployment_check.py --fix-issues
```

## Configuration Examples

### Development Environment

```bash
# Minimal local-only configuration
CLOUD_STORAGE_ENABLED=false
CLOUD_STORAGE_PRIMARY_PROVIDER=local
CLOUD_STORAGE_FALLBACK_ENABLED=true
```

### Staging Environment

```bash
# Test cloud providers
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true

AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=myapp-staging-attachments
AWS_S3_REGION=us-east-1
```

### Production Environment

```bash
# Full cloud storage with security
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true

# Security settings
STORAGE_TENANT_ISOLATION_ENABLED=true
STORAGE_AUDIT_LOGGING_ENABLED=true
STORAGE_OPERATION_LOGGING_ENABLED=true

# Performance settings
STORAGE_PERFORMANCE_MONITORING_ENABLED=true
STORAGE_COST_OPTIMIZATION_ENABLED=true

# AWS S3 with encryption
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=myapp-prod-attachments
AWS_S3_REGION=us-east-1
AWS_S3_SERVER_SIDE_ENCRYPTION=aws:kms
```

## Provider-Specific Setup

### AWS S3

1. **Create S3 Bucket**:
   ```bash
   aws s3 mb s3://your-app-attachments --region us-east-1
   ```

2. **Set up IAM Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
       "Resource": ["arn:aws:s3:::your-app-attachments", "arn:aws:s3:::your-app-attachments/*"]
     }]
   }
   ```

3. **Environment Variables**:
   ```bash
   AWS_S3_ENABLED=true
   AWS_S3_BUCKET_NAME=your-app-attachments
   AWS_S3_REGION=us-east-1
   # Use IAM roles in production instead of keys
   AWS_S3_ACCESS_KEY_ID=your-access-key
   AWS_S3_SECRET_ACCESS_KEY=your-secret-key
   ```

### Azure Blob Storage

1. **Create Storage Account**:
   ```bash
   az storage account create --name yourappstorage --resource-group your-rg --location eastus
   az storage container create --name attachments --account-name yourappstorage
   ```

2. **Environment Variables**:
   ```bash
   AZURE_BLOB_ENABLED=true
   AZURE_STORAGE_ACCOUNT_NAME=yourappstorage
   AZURE_STORAGE_ACCOUNT_KEY=your-account-key
   AZURE_CONTAINER_NAME=attachments
   ```

### Google Cloud Storage

1. **Create GCS Bucket**:
   ```bash
   gsutil mb -p your-project-id -c STANDARD -l us-central1 gs://your-app-attachments
   ```

2. **Create Service Account**:
   ```bash
   gcloud iam service-accounts create storage-service-account
   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:storage-service-account@your-project-id.iam.gserviceaccount.com" \
     --role="roles/storage.objectAdmin"
   gcloud iam service-accounts keys create storage-key.json \
     --iam-account=storage-service-account@your-project-id.iam.gserviceaccount.com
   ```

3. **Environment Variables**:
   ```bash
   GCP_STORAGE_ENABLED=true
   GCP_PROJECT_ID=your-project-id
   GCP_BUCKET_NAME=your-app-attachments
   GCP_CREDENTIALS_PATH=/path/to/storage-key.json
   ```

## Validation and Testing

### Configuration Validation

```bash
# Validate all settings
python scripts/validate_cloud_storage_config.py

# Test specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3

# JSON output for automation
python scripts/validate_cloud_storage_config.py --json
```

### Deployment Checks

```bash
# Pre-deployment validation
python scripts/cloud_storage_deployment_check.py --environment production

# Check with automatic fixes
python scripts/cloud_storage_deployment_check.py --fix-issues --verbose
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify credentials are correct
   - Check IAM permissions
   - Ensure service accounts have proper roles

2. **Network Connectivity**:
   - Test network access to cloud providers
   - Check firewall rules
   - Verify DNS resolution

3. **Configuration Errors**:
   - Run validation script to identify issues
   - Check environment variable syntax
   - Verify required settings are present

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python scripts/validate_cloud_storage_config.py --verbose
```

## Security Best Practices

1. **Use IAM Roles**: Prefer IAM roles over access keys in production
2. **Enable Encryption**: Use server-side encryption for all providers
3. **Tenant Isolation**: Enable tenant isolation for multi-tenant applications
4. **Audit Logging**: Enable comprehensive audit logging
5. **Network Security**: Use VPC endpoints and private access when possible

## Performance Optimization

1. **Connection Pooling**: Configure appropriate connection pool sizes
2. **Caching**: Enable URL and metadata caching
3. **Cost Optimization**: Use lifecycle policies and storage classes
4. **Monitoring**: Enable performance monitoring and alerting

## Support

For additional help:
1. Check the deployment guide: `docs/CLOUD_STORAGE_DEPLOYMENT_GUIDE.md`
2. Run validation scripts with `--verbose` flag
3. Review application logs for detailed error messages
4. Contact the development team for complex issues