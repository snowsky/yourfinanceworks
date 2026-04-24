# Cloud Storage & Attachments

YourFinanceWORKS supports flexible file storage options for all your attachments, receipts, and bank statements.

## 📁 Storage Options

The system supports a hybrid-cloud storage model:

- **Local Storage**: Default for development and small deployments. Files are stored on the server's disk.
- **AWS S3**: Scalable object storage for production environments.
- **Azure Blob Storage**: Enterprise-grade storage for Microsoft ecosystems.
- **Google Cloud Storage (GCS)**: Robust storage for GCP-based deployments.

## 🚀 Configuration

Enable and configure your preferred provider via environment variables:

```bash
# General Settings
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3  # Options: local, aws_s3, azure, gcs
CLOUD_STORAGE_FALLBACK_ENABLED=true     # Switch to local if cloud is down

# AWS S3 Configuration example
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_S3_REGION=us-east-1
AWS_S3_ACCESS_KEY_ID=your-key
AWS_S3_SECRET_ACCESS_KEY=your-secret
```

## 🔒 Security & Isolation

- **Tenant Isolation**: Files are logically separated by organization ID, ensuring no cross-tenant data access.
- **Encryption**: Support for Server-Side Encryption (SSE) for all cloud providers.
- **Private Access**: Attachments are non-public. The API generates short-lived signed URLs for secure viewing and download.

## 🛠️ Maintenance & Tools

The system includes built-in scripts for managing storage:

- **Setup Script**: `python scripts/setup_cloud_storage.py` - Interactive guide for configuration.
- **Health Check**: `python scripts/validate_cloud_storage_config.py` - Verify connectivity and permissions.
- **Deployment Check**: `python scripts/cloud_storage_deployment_check.py` - Pre-flight check for production.

## Storage Usage Reporting

The Super Admin Dashboard shows organization storage from application metadata:

- Database size comes from PostgreSQL `pg_database_size`.
- Attachment size comes from `file_size` values stored on attachment records.

This works for both local and cloud storage when uploads or migrations preserve attachment metadata. The dashboard does not list S3/Azure/GCS objects live on every page load, because provider scans can be slow, rate-limited, and billable. Files that exist only in cloud storage without a matching attachment row, or records with missing `file_size`, will not be reflected in the dashboard total.

Use cloud-provider usage reports or a scheduled storage usage job for billing-grade totals.

---

### Pro Tips

- **Enable Fallback**: Always keep `CLOUD_STORAGE_FALLBACK_ENABLED=true` to ensure system availability even during cloud provider outages.
- **IAM Policies**: Use the "Least Privilege" principle when setting up IAM roles for AWS S3. See our [S3 Permissions Guide](../technical-notes/S3_PERMISSIONS_SETUP.md) for details.
