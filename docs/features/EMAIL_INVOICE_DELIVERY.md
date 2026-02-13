# Email Invoice Delivery

## Overview

YourFinanceWORKS lets you email invoices directly to clients with professional PDF attachments. Email delivery supports multiple providers and includes configuration testing and error handling.

## Supported Email Providers

### AWS SES (Simple Email Service)

- **Setup**: Configure AWS credentials and region
- **Features**: High deliverability, detailed analytics, cost-effective
- **Requirements**: AWS Access Key ID, Secret Access Key, and region

### Azure Email Services

- **Setup**: Configure Azure Communication Services connection string
- **Features**: Enterprise-grade reliability, global scale
- **Requirements**: Azure Communication Services connection string

### Mailgun

- **Setup**: Configure API key and domain
- **Features**: Developer-friendly API, detailed tracking
- **Requirements**: Mailgun API key and verified domain

## Configuration

1. **Navigate to Settings** -> **Email Settings**
2. **Enable Email Service** - Toggle the email functionality
3. **Select Provider** - Choose AWS SES, Azure, or Mailgun
4. **Configure Credentials** - Enter provider-specific settings
5. **Test Configuration** - Send a test email to verify setup
6. **Save Settings** - Store your configuration securely

## Sending Invoices

### From the Invoice UI

- Open any saved invoice
- Click **Send Email** in the preview section
- The email is sent to the client's email address

### Via API

```http
POST /api/v1/email/send-invoice
```

```json
{
  "invoice_id": 123,
  "include_pdf": true,
  "to_email": "client@example.com"
}
```

- `to_email` is optional; omit it to use the client's default email.
