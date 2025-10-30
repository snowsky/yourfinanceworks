# Cloud Storage Deployment Guide

This guide provides step-by-step instructions for deploying the cloud file storage system in different environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Provider Configuration](#provider-configuration)
4. [Deployment Steps](#deployment-steps)
5. [Validation and Testing](#validation-and-testing)
6. [Troubleshooting](#troubleshooting)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)

## Prerequisites

### System Requirements

- Python 3.8 or higher
- PostgreSQL or SQLite database
- Network access to cloud providers (if using cloud storage)
- Sufficient disk space for local storage fallback

### Required Python Packages

The system will automatically install required packages, but you can install them manually:

```bash
# For AWS S3 support
pip install boto3

# For Azure Blob Storage support
pip install azure-storage-blob

# For Google Cloud Storage support
pip install google-cloud-storage
```

### Cloud Provider Accounts

Ensure you have accounts and appropriate permissions for the cloud providers you plan to use:

- **AWS S3**: AWS account with S3 access
- **Azure Blob Storage**: Azure subscription with Storage Account
- **Google Cloud Storage**: GCP project with Cloud Storage API enabled

## Environment Setup

### 1. Configuration Templates

The system provides configuration templates for different environments:

```bash
# Copy the cloud storage environment template
cp api/.env.cloud-storage.example api/.env.cloud-storage

# Edit the configuration file
nano api/.env.cloud-storage
```

### 2. Environment-Specific Configuration

#### Development Environment

```bash
# Minimal configuration for development
CLOUD_STORAGE_ENABLED=false
CLOUD_STORAGE_PRIMARY_PROVIDER=local
CLOUD_STORAGE_FALLBACK_ENABLED=true
```

#### Staging Environment

```bash
# Test cloud providers in staging
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true

# AWS S3 Configuration
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=myapp-staging-attachments
AWS_S3_REGION=us-east-1
```

#### Production Environment

```bash
# Full cloud storage configuration
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
```

## Provider Configuration

### AWS S3 Configuration

#### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://your-app-attachments --region us-east-1

# Enable versioning (optional)
aws s3api put-bucket-versioning \
    --bucket your-app-attachments \
    --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
    --bucket your-app-attachments \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'
```

#### 2. IAM Policy

Create an IAM policy for the application:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-app-attachments",
                "arn:aws:s3:::your-app-attachments/*"
            ]
        }
    ]
}
```

#### 3. Environment Variables

```bash
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=your-app-attachments
AWS_S3_REGION=us-east-1
AWS_S3_ACCESS_KEY_ID=your-access-key-id
AWS_S3_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_SERVER_SIDE_ENCRYPTION=AES256
```

### Azure Blob Storage Configuration

#### 1. Create Storage Account

```bash
# Using Azure CLI
az storage account create \
    --name yourappstorage \
    --resource-group your-resource-group \
    --location eastus \
    --sku Standard_LRS \
    --encryption-services blob

# Create container
az storage container create \
    --name attachments \
    --account-name yourappstorage
```

#### 2. Environment Variables

```bash
AZURE_BLOB_ENABLED=true
AZURE_STORAGE_ACCOUNT_NAME=yourappstorage
AZURE_STORAGE_ACCOUNT_KEY=your-account-key
AZURE_CONTAINER_NAME=attachments
AZURE_BLOB_TIER=Hot
AZURE_BLOB_ENCRYPTION_ENABLED=true
```

### Google Cloud Storage Configuration

#### 1. Create GCS Bucket

```bash
# Using gcloud CLI
gsutil mb -p your-project-id -c STANDARD -l us-central1 gs://your-app-attachments

# Enable versioning (optional)
gsutil versioning set on gs://your-app-attachments
```

#### 2. Service Account

Create a service account with appropriate permissions:

```bash
# Create service account
gcloud iam service-accounts create storage-service-account \
    --display-name="Storage Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:storage-service-account@your-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Create and download key
gcloud iam service-accounts keys create storage-key.json \
    --iam-account=storage-service-account@your-project-id.iam.gserviceaccount.com
```

#### 3. Environment Variables

```bash
GCP_STORAGE_ENABLED=true
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=your-app-attachments
GCP_STORAGE_REGION=us-central1
GCP_CREDENTIALS_PATH=/path/to/storage-key.json
GCP_STORAGE_CLASS=STANDARD
```

## Deployment Steps

### 1. Interactive Setup (Recommended)

Use the interactive setup script for guided configuration:

```bash
cd api
python scripts/setup_cloud_storage.py --interactive --verbose
```

This script will:
- Guide you through provider selection
- Help configure authentication
- Test connectivity
- Create necessary resources
- Generate configuration files

### 2. Manual Setup

If you prefer manual setup:

#### Step 1: Copy Configuration

```bash
# Copy environment template
cp .env.cloud-storage.example .env

# Edit configuration
nano .env
```

#### Step 2: Validate Configuration

```bash
# Run configuration validation
python scripts/validate_cloud_storage_config.py --verbose

# Check specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3
```

#### Step 3: Run Deployment Check

```bash
# Check deployment readiness
python scripts/cloud_storage_deployment_check.py --environment production --verbose

# Fix issues automatically (if possible)
python scripts/cloud_storage_deployment_check.py --fix-issues
```

### 3. Database Migration

Run database migrations to create cloud storage tables:

```bash
# Run Alembic migrations
alembic upgrade head

# Or use the application's migration script
python scripts/run_all_migrations.py
```

### 4. Start Application

```bash
# Start the application
python main.py

# Or using Docker
docker-compose up -d
```

## Validation and Testing

### 1. Configuration Validation

```bash
# Validate all configuration
python scripts/validate_cloud_storage_config.py

# Output results in JSON format
python scripts/validate_cloud_storage_config.py --json
```

### 2. Connectivity Testing

```bash
# Test connectivity to all providers
python scripts/validate_cloud_storage_config.py --verbose

# Test specific provider
python scripts/validate_cloud_storage_config.py --provider aws_s3
```

### 3. File Operations Testing

Test file operations through the API:

```bash
# Upload test file
curl -X POST "http://localhost:8000/api/files/upload" \
     -H "Authorization: Bearer your-token" \
     -F "file=@test-file.pdf" \
     -F "attachment_type=document"

# Download file
curl -X GET "http://localhost:8000/api/files/download/file-id" \
     -H "Authorization: Bearer your-token"

# Delete file
curl -X DELETE "http://localhost:8000/api/files/delete/file-id" \
     -H "Authorization: Bearer your-token"
```

### 4. Migration Testing

Test file migration from local to cloud storage:

```bash
# Run migration for specific tenant (dry run)
python -c "
import asyncio
from services.attachment_migration_service import AttachmentMigrationService
from models.database import get_db

async def test_migration():
    db = next(get_db())
    migration_service = AttachmentMigrationService(None, db)
    result = await migration_service.migrate_tenant_attachments('tenant_1', dry_run=True)
    print(result)

asyncio.run(test_migration())
"
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**AWS S3 Authentication Failed**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify IAM permissions
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::account:user/username \
    --action-names s3:GetObject s3:PutObject \
    --resource-arns arn:aws:s3:::bucket-name/*
```

**Azure Blob Authentication Failed**
```bash
# Test Azure CLI authentication
az account show

# Test storage account access
az storage blob list --container-name attachments --account-name youraccount
```

**GCP Authentication Failed**
```bash
# Check service account authentication
gcloud auth activate-service-account --key-file=storage-key.json

# Test bucket access
gsutil ls gs://your-bucket-name
```

#### 2. Network Connectivity Issues

```bash
# Test network connectivity
curl -I https://s3.amazonaws.com
curl -I https://youraccount.blob.core.windows.net
curl -I https://storage.googleapis.com

# Check DNS resolution
nslookup s3.amazonaws.com
nslookup youraccount.blob.core.windows.net
nslookup storage.googleapis.com
```

#### 3. Permission Issues

**S3 Permission Denied**
- Verify IAM policy allows required actions
- Check bucket policy doesn't deny access
- Ensure bucket exists and is in correct region

**Azure Blob Permission Denied**
- Verify storage account key is correct
- Check container exists and is accessible
- Ensure storage account allows blob access

**GCS Permission Denied**
- Verify service account has Storage Object Admin role
- Check bucket IAM policies
- Ensure service account key is valid

#### 4. Configuration Issues

```bash
# Debug configuration
python -c "
from config.cloud_storage_config import CloudStorageConfig, CloudStorageConfigValidator
config = CloudStorageConfig()
validator = CloudStorageConfigValidator(config)
result = validator.validate()
print('Errors:', result['errors'])
print('Warnings:', result['warnings'])
"
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment variables
export LOG_LEVEL=DEBUG
export STORAGE_OPERATION_LOGGING_ENABLED=true

# Run with verbose output
python scripts/validate_cloud_storage_config.py --verbose
```

### Log Analysis

Check application logs for storage-related errors:

```bash
# Filter storage logs
grep -i "storage\|s3\|azure\|gcs" /var/log/app.log

# Check specific error patterns
grep -E "(StorageError|ConnectionError|AuthenticationError)" /var/log/app.log
```

## Monitoring and Maintenance

### 1. Health Monitoring

Set up monitoring for cloud storage health:

```bash
# Check storage health endpoint
curl http://localhost:8000/api/storage/health

# Monitor circuit breaker status
curl http://localhost:8000/api/storage/circuit-breakers
```

### 2. Performance Monitoring

Monitor storage performance metrics:

```bash
# Get storage metrics
curl http://localhost:8000/api/storage/metrics

# Check operation logs
curl http://localhost:8000/api/storage/operations?limit=100
```

### 3. Cost Monitoring

Monitor storage costs:

```bash
# Get cost analysis
curl http://localhost:8000/api/storage/cost-analysis

# Check optimization recommendations
curl http://localhost:8000/api/storage/cost-optimization
```

### 4. Backup and Recovery

Implement backup procedures:

```bash
# Backup configuration
cp .env .env.backup.$(date +%Y%m%d)

# Test disaster recovery
python scripts/test_disaster_recovery.py
```

### 5. Regular Maintenance

Schedule regular maintenance tasks:

```bash
# Weekly health check
0 2 * * 1 /path/to/python scripts/validate_cloud_storage_config.py

# Monthly cost analysis
0 1 1 * * /path/to/python scripts/generate_cost_report.py

# Quarterly disaster recovery test
0 3 1 */3 * /path/to/python scripts/test_disaster_recovery.py
```

## Security Best Practices

### 1. Credential Management

- Use IAM roles instead of access keys in production
- Rotate credentials regularly
- Store sensitive credentials in secure vaults
- Never commit credentials to version control

### 2. Network Security

- Use VPC endpoints for AWS S3 access
- Configure private endpoints for Azure Blob Storage
- Use private Google Access for GCS
- Implement network access controls

### 3. Encryption

- Enable server-side encryption for all providers
- Use customer-managed keys when possible
- Encrypt data in transit (HTTPS/TLS)
- Implement client-side encryption for sensitive data

### 4. Access Control

- Implement least-privilege access policies
- Use tenant isolation for multi-tenant applications
- Enable audit logging for all operations
- Regular access reviews and cleanup

### 5. Compliance

- Implement data retention policies
- Enable compliance logging
- Regular security assessments
- Document security procedures

## Performance Optimization

### 1. Connection Pooling

Configure connection pooling for better performance:

```bash
# AWS S3 connection pooling
AWS_S3_MAX_POOL_CONNECTIONS=20

# Azure Blob connection settings
AZURE_BLOB_MAX_CONNECTIONS=10

# GCS connection settings
GCP_STORAGE_MAX_CONNECTIONS=15
```

### 2. Caching

Implement caching for frequently accessed files:

```bash
# Enable URL caching
STORAGE_URL_CACHE_ENABLED=true
STORAGE_URL_CACHE_TTL=3600

# Enable metadata caching
STORAGE_METADATA_CACHE_ENABLED=true
STORAGE_METADATA_CACHE_TTL=1800
```

### 3. Optimization Settings

Configure optimization settings:

```bash
# Enable cost optimization
STORAGE_COST_OPTIMIZATION_ENABLED=true
STORAGE_TIER_TRANSITION_DAYS=30

# Performance monitoring
STORAGE_PERFORMANCE_MONITORING_ENABLED=true
STORAGE_SLOW_OPERATION_THRESHOLD=5000
```

## Conclusion

This deployment guide provides comprehensive instructions for setting up cloud file storage in various environments. Follow the steps carefully and use the provided scripts for validation and testing. Regular monitoring and maintenance ensure optimal performance and security.

For additional support, refer to the troubleshooting section or contact the development team.