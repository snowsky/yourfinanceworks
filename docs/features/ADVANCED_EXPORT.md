# Advanced Export & Cloud Destinations

YourFinanceWORKS provides enterprise-grade data export capabilities, allowing you to securely transfer your financial data and processed documents to major cloud storage providers for archiving, further analysis, or integration with other business systems.

## 🚀 Key Features

- **Multi-Cloud Support**: Export data directly to AWS S3, Azure Blob Storage, Google Cloud Storage, or Google Drive.
- **Secure Handling**: All cloud credentials are encrypted using tenant-specific keys and are never exposed in logs or API responses.
- **Automated CSV Generation**: Rich data exports containing extracted vendor info, line items, and audit trails.
- **Presigned URLs**: Secure, time-limited download links (24-hour expiry) for generated exports.
- **Cloud Provenance**: Exports include direct links to the original processed files stored in your cloud bucket.
- **Retry Resilience**: Automatic exponential backoff (up to 5 attempts) for reliable uploads even during network instability.

## ☁️ Supported Destinations

| Provider           | Authentication          | Features                                             |
| :----------------- | :---------------------- | :--------------------------------------------------- |
| **AWS S3**         | Access Key / Secret     | Bucket-based storage, Presigned URLs, Path prefixes. |
| **Azure Blob**     | Connection String / Key | Container storage, SAS tokens, Metadata tagging.     |
| **GCloud Storage** | Service Account JSON    | Signed URLs, Bucket organization, Global reach.      |
| **Google Drive**   | OAuth2 Flow             | Folder-based storage, Shareable links.               |

## 🛠️ Configuration

Export destinations are managed in the **Settings → Export Destinations** tab.

### 1. Connection Testing

Before saving, use the **Test Connection** feature to verify that your credentials have the necessary write permissions for the specified bucket or folder.

### 2. Default Destination

You can set a primary export destination. This bucket will be used automatically for all batch processing jobs unless otherwise specified.

## 📊 Data Export Format

The standard CSV export includes comprehensive fields:

- **Identity**: `file_name`, `original_filename`, `cloud_file_url`.
- **Financials**: `amount`, `currency`, `tax_amount`, `date`.
- **Classification**: `vendor`, `category`, `document_type`.
- **Details**: `line_items` (JSON), `attachment_paths`.

## 🔒 Security Best Practices

- **Least Privilege**: Configure your cloud IAM roles with the minimum permissions required (only `PutObject` for the specific export bucket).
- **Path Prefixes**: Use prefixes (e.g., `finance-works/exports/`) to organize data and restrict access to specific namespaces.
- **Sandbox Mode**: Test your export configurations in a non-production environment first.

---

### Pro Tips

- **Custom Fields**: When using the API, you can specify exactly which columns to include in your CSV export to match your ERP's import format.
- **Metadata**: Many cloud providers support metadata tagging. Our service automatically tags exports with the Job ID and Tenant ID for easier indexing.
- **Local Fallback**: If no cloud destination is configured, the system still generates and stores exports locally for immediate download.

For API implementation details, see the [Export Destinations API Guide](../technical-notes/EXPORT_DESTINATIONS_API.md).
