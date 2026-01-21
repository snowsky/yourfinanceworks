# External Transactions & API Integration

YourFinanceWORKS provides a robust API for integrating third-party financial data, processing bank statements with AI, and managing external transactions through automated workflows.

## 🚀 Key Features

- **AI-Powered Statement Processing**: Upload bank statement PDFs or CSVs and let our AI extract transactions with high accuracy.
- **Unified Transaction API**: Programmatically create, list, and manage transactions from any external source.
- **Secure Authentication**: Manage multiple API keys with granular permissions and rate limiting.
- **Review & Approval Workflow**: Integrated UI for administrators to review and approve/reject externally submitted transactions.
- **Webhook Notifications**: Receive real-time alerts when transactions are created, updated, or reviewed.
- **Duplicate Protection**: Intelligent hashing logic prevent accidental duplicate data entry.

## 🔑 Authentication

The API supports standard header-based authentication:

```bash
# Recommended
Authorization: Bearer your_api_key

# Alternative
X-API-Key: your_api_key
```

## 🛠️ Core Endpoints

| Endpoint                                          | Description                                  |
| :------------------------------------------------ | :------------------------------------------- |
| `POST /api/v1/statements/process`                 | Upload and process a bank statement PDF/CSV. |
| `POST /api/v1/external-transactions/transactions` | Submit a new financial transaction.          |
| `GET /api/v1/external-transactions/transactions`  | List and filter submitted transactions.      |
| `POST /api/v1/external-auth/api-keys`             | Generate and manage API integration keys.    |

## 🔒 Security & Testing

- **Sandbox Mode**: Use sandbox API keys to test your integration without affecting live financial data.
- **Tenant Isolation**: All transactions are logically isolated by organization, ensuring data privacy.
- **Rate Limiting**: Configurable quotas per minute, hour, and day to prevent API abuse.

## 📦 Bulk Processing

For high-volume scenarios, use the **Batch Processing** system to upload and process multiple files simultaneously:

- Upload up to 50 files per request (invoices, expenses, bank statements)
- Process asynchronously with automatic retry logic
- Export results to AWS S3, Azure, Google Cloud Storage, or Google Drive
- Track progress with real-time job status monitoring
- Receive webhook notifications when jobs complete

See [Batch Processing & External API Access](./BATCH_PROCESSING_API_ACCESS.md) for detailed documentation.

---

### Pro Tips

- **Check Health**: Use the `/api/v1/statements/health` endpoint to verify your API client's permissions and AI service status.
- **Metadata Support**: Pass custom JSON in the `submission_metadata` field to store source-specific identifiers with your transactions.
- **AI Recognition**: Use the `disable_ai_recognition` flag if you've already categorized your data and want to bypass the AI classification engine.
- **Batch for Scale**: Use batch processing endpoints for bulk imports instead of individual transaction submissions.

For a full technical reference, see the [External API Usage Guide](../technical-notes/EXTERNAL_API_USAGE.md).
