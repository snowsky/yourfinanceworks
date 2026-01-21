# Reports API Documentation

This document describes the comprehensive Reports API endpoints that provide report generation, template management, scheduling, and history tracking capabilities.

## Base URL
All endpoints are prefixed with `/api/v1/reports`

## Authentication
All endpoints require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

## Endpoints Overview

### Report Types
- `GET /types` - Get available report types and their configurations

### Report Generation
- `POST /generate` - Generate a report with specified parameters
- `POST /preview` - Preview a report with limited results

### Template Management
- `GET /templates` - List user's report templates
- `POST /templates` - Create a new report template
- `PUT /templates/{template_id}` - Update an existing template
- `DELETE /templates/{template_id}` - Delete a template

### Scheduled Reports
- `GET /scheduled` - List user's scheduled reports
- `POST /scheduled` - Create a new scheduled report
- `PUT /scheduled/{schedule_id}` - Update a scheduled report
- `DELETE /scheduled/{schedule_id}` - Delete a scheduled report

### Report History & Downloads
- `GET /history` - Get user's report generation history
- `GET /download/{report_id}` - Download a generated report file
- `POST /regenerate/{report_id}` - Regenerate a report with current data

## Detailed Endpoint Documentation

### GET /types
Get available report types and their configuration options.

**Response:**
```json
{
  "report_types": [
    {
      "type": "client",
      "name": "Client Reports",
      "description": "Comprehensive client analysis with financial history",
      "filters": [
        {"name": "date_from", "type": "datetime", "required": false},
        {"name": "date_to", "type": "datetime", "required": false},
        {"name": "client_ids", "type": "list[int]", "required": false},
        {"name": "include_inactive", "type": "boolean", "required": false},
        {"name": "balance_min", "type": "float", "required": false},
        {"name": "balance_max", "type": "float", "required": false}
      ],
      "columns": [
        "client_name", "email", "phone", "total_invoiced", 
        "total_paid", "outstanding_balance", "last_invoice_date", "payment_terms"
      ]
    }
  ]
}
```

### POST /generate
Generate a report with specified parameters.

**Request Body:**
```json
{
  "report_type": "client",
  "filters": {
    "date_from": "2024-01-01T00:00:00",
    "date_to": "2024-01-31T23:59:59",
    "include_inactive": false
  },
  "columns": ["client_name", "total_invoiced", "total_paid"],
  "export_format": "json",
  "template_id": 123
}
```

**Response (JSON format):**
```json
{
  "success": true,
  "data": {
    "report_type": "client",
    "summary": {
      "total_records": 25,
      "total_amount": 150000.00,
      "currency": "USD",
      "key_metrics": {}
    },
    "data": [
      {
        "client_name": "Acme Corp",
        "total_invoiced": 50000.00,
        "total_paid": 45000.00
      }
    ],
    "metadata": {
      "generated_at": "2024-01-15T10:30:00Z",
      "generated_by": 123,
      "export_format": "json"
    }
  }
}
```

**Response (File formats):**
```json
{
  "success": true,
  "report_id": 456,
  "download_url": "/api/v1/reports/download/456"
}
```

### POST /preview
Preview a report with limited results to validate filters.

**Request Body:**
```json
{
  "report_type": "invoice",
  "filters": {
    "date_from": "2024-01-01T00:00:00",
    "status": ["pending", "overdue"]
  },
  "limit": 10
}
```

### POST /templates
Create a new report template.

**Request Body:**
```json
{
  "name": "Monthly Client Summary",
  "report_type": "client",
  "filters": {
    "include_inactive": false
  },
  "columns": ["client_name", "total_invoiced", "outstanding_balance"],
  "formatting": {
    "currency": "USD",
    "date_format": "YYYY-MM-DD"
  },
  "is_shared": false
}
```

### POST /scheduled
Create a scheduled report.

**Request Body:**
```json
{
  "template_id": 123,
  "schedule_config": {
    "schedule_type": "monthly",
    "time_of_day": "09:00",
    "day_of_month": 1,
    "timezone": "UTC"
  },
  "recipients": ["admin@company.com", "manager@company.com"],
  "export_format": "pdf",
  "is_active": true
}
```

## Report Types

### Client Reports
- **Type:** `client`
- **Description:** Comprehensive client analysis with financial history
- **Available Filters:**
  - `date_from`, `date_to`: Date range filters
  - `client_ids`: Specific client IDs to include
  - `include_inactive`: Include inactive clients
  - `balance_min`, `balance_max`: Balance range filters
  - `currency`: Currency filter

### Invoice Reports
- **Type:** `invoice`
- **Description:** Detailed invoice analysis with payment tracking
- **Available Filters:**
  - `date_from`, `date_to`: Date range filters
  - `client_ids`: Filter by specific clients
  - `status`: Invoice statuses (pending, paid, overdue, etc.)
  - `amount_min`, `amount_max`: Amount range filters
  - `include_items`: Include line item details
  - `is_recurring`: Filter by recurring status

### Payment Reports
- **Type:** `payment`
- **Description:** Cash flow analysis and payment tracking
- **Available Filters:**
  - `date_from`, `date_to`: Date range filters
  - `client_ids`: Filter by specific clients
  - `payment_methods`: Payment method filters
  - `amount_min`, `amount_max`: Amount range filters
  - `include_unmatched`: Include unmatched payments

### Expense Reports
- **Type:** `expense`
- **Description:** Business expense tracking and categorization
- **Available Filters:**
  - `date_from`, `date_to`: Date range filters
  - `categories`: Expense categories
  - `labels`: Expense labels/tags
  - `vendor`: Vendor name filter
  - `status`: Expense statuses
  - `include_attachments`: Include attachment information

### Statement Reports
- **Type:** `statement`
- **Description:** Bank transaction analysis and reconciliation
- **Available Filters:**
  - `date_from`, `date_to`: Date range filters
  - `account_ids`: Bank account IDs
  - `transaction_types`: Transaction type filters
  - `amount_min`, `amount_max`: Amount range filters
  - `include_reconciliation`: Include reconciliation status

## Export Formats

- **JSON:** Immediate response with data
- **PDF:** Professional formatted report
- **CSV:** Comma-separated values for spreadsheet import
- **EXCEL:** Excel workbook format

## Schedule Types

- **DAILY:** Run every day at specified time
- **WEEKLY:** Run weekly on specified day and time
- **MONTHLY:** Run monthly on specified day and time
- **YEARLY:** Run yearly on specified date and time
- **CRON:** Custom cron expression for complex schedules

## Error Responses

All endpoints return standard HTTP status codes:

- **200:** Success
- **400:** Bad Request (validation errors)
- **401:** Unauthorized (missing or invalid token)
- **403:** Forbidden (insufficient permissions)
- **404:** Not Found (resource doesn't exist)
- **500:** Internal Server Error

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Rate Limits

- Report generation: 10 requests per minute per user
- Template operations: 50 requests per minute per user
- History/download: 100 requests per minute per user

## Security Features

- **Authentication:** All endpoints require valid JWT token
- **Authorization:** Users can only access their own templates and reports
- **Template Sharing:** Templates can be shared with other users in the organization
- **File Expiration:** Generated report files expire after 30 days
- **Audit Logging:** All operations are logged for security and compliance

## Usage Examples

### Generate a Client Report
```bash
curl -X POST "/api/v1/reports/generate" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "client",
    "filters": {
      "date_from": "2024-01-01T00:00:00",
      "include_inactive": false
    },
    "export_format": "json"
  }'
```

### Create a Template
```bash
curl -X POST "/api/v1/reports/templates" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly Sales Report",
    "report_type": "invoice",
    "filters": {
      "status": ["paid"]
    },
    "columns": ["invoice_number", "client_name", "amount", "date"]
  }'
```

### Schedule a Monthly Report
```bash
curl -X POST "/api/v1/reports/scheduled" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": 123,
    "schedule_config": {
      "schedule_type": "monthly",
      "day_of_month": 1,
      "time_of_day": "09:00"
    },
    "recipients": ["admin@company.com"],
    "export_format": "pdf"
  }'
```