# Invoice Management API Guide

This guide provides comprehensive documentation for the Invoice Management API, covering all available endpoints for creating, managing, and processing invoices.

## Overview

The Invoice API provides a complete invoicing solution with support for:

- Full CRUD operations (Create, Read, Update, Delete)
- File attachments and PDF generation
- Email delivery
- Multi-currency support
- Inventory integration
- Payment tracking
- Audit trails and history
- Soft delete with recycle bin functionality

## Base Configuration

### Base URL

```
https://your-api-domain.com
```

### Authentication

All requests require a valid API token in the Authorization header:

```
Authorization: Bearer YOUR_API_TOKEN
```

### Content Types

- JSON requests: `Content-Type: application/json`
- File uploads: `Content-Type: multipart/form-data`

## Core Invoice Operations

### 1. Create Invoice

**Endpoint:** `POST /invoices/`

```bash
curl -X POST "https://your-api-domain.com/invoices/" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 123,
    "amount": 1500.00,
    "currency": "USD",
    "due_date": "2024-11-28",
    "status": "draft",
    "notes": "Website development project",
    "description": "Custom website development and design",
    "is_recurring": false,
    "discount_type": "percentage",
    "discount_value": 10,
    "show_discount_in_pdf": true,
    "items": [
      {
        "description": "Frontend Development",
        "quantity": 40,
        "price": 75.00,
        "inventory_item_id": null,
        "unit_of_measure": "hours"
      },
      {
        "description": "Backend Development", 
        "quantity": 30,
        "price": 85.00,
        "inventory_item_id": null,
        "unit_of_measure": "hours"
      }
    ],
    "custom_fields": {
      "project_code": "WEB-2024-001",
      "department": "Development"
    }
  }'
```

**Success Response:**

```json
{
  "id": 456,
  "number": "INV-2024-001",
  "amount": 6075.00,
  "currency": "USD",
  "due_date": "2024-11-28",
  "status": "draft",
  "notes": "Website development project",
  "description": "Custom website development and design",
  "client_id": 123,
  "client_name": "Acme Corporation",
  "client_company": "Acme Corp",
  "created_at": "2024-10-28T10:30:00Z",
  "updated_at": "2024-10-28T10:30:00Z",
  "total_paid": 0.00,
  "is_recurring": false,
  "recurring_frequency": null,
  "discount_type": "percentage",
  "discount_value": 10.0,
  "subtotal": 6750.00,
  "items": [
    {
      "id": 789,
      "invoice_id": 456,
      "inventory_item_id": null,
      "description": "Frontend Development",
      "quantity": 40.0,
      "price": 75.0,
      "amount": 3000.0,
      "unit_of_measure": "hours"
    },
    {
      "id": 790,
      "invoice_id": 456,
      "inventory_item_id": null,
      "description": "Backend Development",
      "quantity": 30.0,
      "price": 85.0,
      "amount": 2550.0,
      "unit_of_measure": "hours"
    }
  ],
  "custom_fields": {
    "project_code": "WEB-2024-001",
    "department": "Development"
  },
  "show_discount_in_pdf": true,
  "has_attachment": false,
  "attachment_filename": null,
  "attachments": [],
  "attachment_count": 0
}
```

### 2. List Invoices

**Endpoint:** `GET /invoices/`

```bash
curl -X GET "https://your-api-domain.com/invoices/?skip=0&limit=50&status_filter=draft" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Query Parameters:**

- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum records to return (default: 100)
- `status_filter` (string): Filter by status ("draft", "sent", "paid", "overdue", "all")

### 3. Get Invoice Details

**Endpoint:** `GET /invoices/{invoice_id}`

```bash
curl -X GET "https://your-api-domain.com/invoices/456" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### 4. Update Invoice

**Endpoint:** `PUT /invoices/{invoice_id}`

```bash
curl -X PUT "https://your-api-domain.com/invoices/456" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "sent",
    "notes": "Updated project scope - website development project",
    "amount": 1650.00
  }'
```

### 5. Delete Invoice (Soft Delete)

**Endpoint:** `DELETE /invoices/{invoice_id}`

```bash
curl -X DELETE "https://your-api-domain.com/invoices/456" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Response:**

```json
{
  "success": true,
  "message": "Invoice moved to recycle bin",
  "invoice_id": 456
}
```

## Invoice Management Operations

### Clone Invoice

**Endpoint:** `POST /invoices/{invoice_id}/clone`

```bash
curl -X POST "https://your-api-domain.com/invoices/456/clone" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

Creates a new draft invoice with a new number, copying all details from the original.

### Send Invoice via Email

**Endpoint:** `POST /invoices/{invoice_id}/send-email`

```bash
curl -X POST "https://your-api-domain.com/invoices/456/send-email" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "client@example.com",
    "subject": "Invoice INV-2024-001 from Your Company",
    "message": "Please find attached your invoice. Payment is due within 30 days."
  }'
```

### Download Invoice PDF

**Endpoint:** `GET /invoices/{invoice_id}/pdf`

```bash
curl -X GET "https://your-api-domain.com/invoices/456/pdf" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -o "invoice-456.pdf"
```

## File Attachment Operations

### Upload Attachment (Recommended)

**Endpoint:** `POST /invoices/{invoice_id}/attachments` *(New/Enhanced)*

```bash
curl -X POST "https://your-api-domain.com/invoices/456/attachments" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -F "file=@/path/to/contract.pdf" \
  -F "attachment_type=document" \
  -F "document_type=legal" \
  -F "description=Signed service contract"
```

**Parameters:**

- `file` (required): The file to upload
- `attachment_type` (optional): "image" or "document" (default: "document")
- `document_type` (optional): Classification like "legal", "contract", "receipt"
- `description` (optional): Human-readable description

**Supported File Types:**

- PDF documents (`.pdf`)
- Images (`.jpg`, `.jpeg`, `.png`, `.gif`)
- Documents (`.doc`, `.docx`, `.txt`)
- Spreadsheets (`.xls`, `.xlsx`, `.csv`)

### Upload Attachment (Legacy)

**Endpoint:** `POST /invoices/{invoice_id}/upload-attachment` *(Legacy - Still Active)*

```bash
curl -X POST "https://your-api-domain.com/invoices/456/upload-attachment" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -F "file=@/path/to/contract.pdf"
```

**Note:** This is the legacy endpoint with limited file type support (PDF, DOC, DOCX, JPG, PNG). Use the `/attachments` endpoint for new integrations.

### List Attachments

**Endpoint:** `GET /invoices/{invoice_id}/attachments`

```bash
curl -X GET "https://your-api-domain.com/invoices/456/attachments" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Response:**

```json
{
  "invoice_id": 456,
  "attachments": [
    {
      "id": 789,
      "filename": "contract.pdf",
      "file_size": 245760,
      "content_type": "application/pdf",
      "attachment_type": "contract",
      "document_type": "legal",
      "description": "Signed service contract",
      "created_at": "2024-10-28T11:00:00Z",
      "uploaded_by": 123
    }
  ],
  "total_count": 1
}
```

### Download Attachment

**Endpoint:** `GET /invoices/{invoice_id}/download-attachment`

```bash
curl -X GET "https://your-api-domain.com/invoices/456/download-attachment?filename=contract.pdf" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -o "downloaded-contract.pdf"
```

## Recycle Bin Operations

### List Deleted Invoices

**Endpoint:** `GET /invoices/recycle-bin`

```bash
curl -X GET "https://your-api-domain.com/invoices/recycle-bin" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Restore Invoice

**Endpoint:** `POST /invoices/{invoice_id}/restore`

```bash
curl -X POST "https://your-api-domain.com/invoices/456/restore" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Permanently Delete Invoice

**Endpoint:** `DELETE /invoices/{invoice_id}/permanent`

```bash
curl -X DELETE "https://your-api-domain.com/invoices/456/permanent" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Empty Recycle Bin

**Endpoint:** `POST /invoices/recycle-bin/empty`

```bash
curl -X POST "https://your-api-domain.com/invoices/recycle-bin/empty" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

## Analytics and Statistics

### Get Total Income

**Endpoint:** `GET /invoices/stats/comprehensive`

```bash
curl -X GET "https://your-api-domain.com/invoices/stats/comprehensive?period=month" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Query Parameters:**

- `period` (string): "day", "week", "month", "quarter", "year"
- `start_date` (string): ISO date format (optional)
- `end_date` (string): ISO date format (optional)

**Response:**

```json
{
  "total_income": 15750.00,
  "currency": "USD",
  "period": "month",
  "invoice_count": 12,
  "average_invoice_amount": 1312.50,
  "paid_invoices": 8,
  "pending_invoices": 4
}
```

### Calculate Discount

**Endpoint:** `POST /invoices/calculate-discount`

```bash
curl -X POST "https://your-api-domain.com/invoices/calculate-discount" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subtotal": 1000.00,
    "discount_type": "percentage",
    "discount_value": 15
  }'
```

**Response:**

```json
{
  "subtotal": 1000.00,
  "discount_amount": 150.00,
  "total_amount": 850.00,
  "discount_type": "percentage",
  "discount_value": 15
}
```

## History and Audit Trail

### Get Invoice History

**Endpoint:** `GET /invoices/{invoice_id}/history`

```bash
curl -X GET "https://your-api-domain.com/invoices/456/history" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Response:**

```json
{
  "invoice_id": 456,
  "history": [
    {
      "id": 123,
      "action": "creation",
      "details": "Invoice INV-2024-001 created",
      "user_id": 789,
      "timestamp": "2024-10-28T10:30:00Z",
      "previous_values": null,
      "current_values": {
        "number": "INV-2024-001",
        "amount": 1500.00,
        "status": "draft"
      }
    },
    {
      "id": 124,
      "action": "status_change",
      "details": "Status changed from draft to sent",
      "user_id": 789,
      "timestamp": "2024-10-28T14:15:00Z",
      "previous_values": {"status": "draft"},
      "current_values": {"status": "sent"}
    }
  ]
}
```

### Add History Entry

**Endpoint:** `POST /invoices/{invoice_id}/history`

```bash
curl -X POST "https://your-api-domain.com/invoices/456/history" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "client_contact",
    "details": "Called client to discuss payment terms"
  }'
```

## Advanced Features

### AI Status Check

**Endpoint:** `GET /invoices/ai-status`

```bash
curl -X GET "https://your-api-domain.com/invoices/ai-status" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

Checks the status of AI-powered features like automatic data extraction from uploaded documents.

### Inventory Integration

When creating invoices with inventory items:

```bash
curl -X POST "https://your-api-domain.com/invoices/" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 123,
    "items": [
      {
        "inventory_item_id": 456,
        "quantity": 5,
        "price": 0
      }
    ]
  }'
```

The system will automatically populate item details and pricing from inventory.

## Error Handling

### Common HTTP Status Codes

- `200 OK`: Successful operation
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Invalid or missing API token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Invoice or resource not found
- `409 Conflict`: Duplicate invoice number
- `413 Payload Too Large`: File too large
- `422 Unprocessable Entity`: Validation errors
- `500 Internal Server Error`: Server error

### Common Error Responses

#### Invoice Not Found

```json
{
  "detail": "Invoice not found"
}
```

#### Duplicate Invoice Number

```json
{
  "detail": "Invoice number 'INV-2024-001' is already in use. Please choose a different number."
}
```

#### Invalid Currency

```json
{
  "detail": "Invalid currency code: XYZ"
}
```

#### Client Not Found

```json
{
  "detail": "Client with ID 123 not found. Please create a client first."
}
```

#### File Too Large

```json
{
  "detail": "File size exceeds maximum allowed size"
}
```

## Invoice Status Workflow

### Status Values

- `draft`: Invoice is being prepared
- `sent`: Invoice has been sent to client
- `paid`: Invoice has been fully paid
- `overdue`: Invoice is past due date
- `cancelled`: Invoice has been cancelled

### Status Transitions

```
draft → sent → paid
draft → cancelled
sent → overdue (automatic based on due_date)
sent → paid
overdue → paid
```

## Best Practices

### 1. Invoice Numbering

- Use the auto-generated invoice numbers for consistency
- If providing custom numbers, ensure uniqueness
- Consider including year/month prefixes (e.g., "2024-10-001")

### 2. Currency Handling

- Always specify currency for international clients
- Use ISO 4217 currency codes (USD, EUR, GBP, etc.)
- Consider client's preferred currency for better UX

### 3. File Attachments

- Use descriptive filenames
- Specify attachment_type for better organization
- Keep file sizes reasonable (under 10MB recommended)
- Use appropriate document_type classifications

### 4. Error Handling

- Always check response status codes
- Implement retry logic for temporary failures
- Validate data before sending requests
- Handle rate limiting gracefully

### 5. Security

- Never expose API tokens in client-side code
- Use HTTPS for all API communications
- Implement proper access controls
- Regularly rotate API tokens

## Example Integration Workflows

### Complete Invoice Creation Workflow

```bash
#!/bin/bash

API_BASE="https://your-api-domain.com"
API_TOKEN="YOUR_API_TOKEN"

# Step 1: Create invoice
INVOICE_RESPONSE=$(curl -s -X POST "$API_BASE/invoices/" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 123,
    "amount": 1500.00,
    "currency": "USD",
    "due_date": "2024-11-28",
    "status": "draft",
    "notes": "Website development project"
  }')

INVOICE_ID=$(echo $INVOICE_RESPONSE | jq -r '.id')

if [ "$INVOICE_ID" != "null" ]; then
  echo "Created invoice with ID: $INVOICE_ID"
  
  # Step 2: Upload contract attachment
  curl -X POST "$API_BASE/invoices/$INVOICE_ID/attachments" \
    -H "Authorization: Bearer $API_TOKEN" \
    -F "file=@contract.pdf" \
    -F "attachment_type=contract"
  
  # Step 3: Generate and download PDF
  curl -X GET "$API_BASE/invoices/$INVOICE_ID/pdf" \
    -H "Authorization: Bearer $API_TOKEN" \
    -o "invoice-$INVOICE_ID.pdf"
  
  # Step 4: Send invoice via email
  curl -X POST "$API_BASE/invoices/$INVOICE_ID/send-email" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "recipient_email": "client@example.com",
      "subject": "Your Invoice is Ready"
    }'
  
  echo "Invoice workflow completed successfully"
else
  echo "Failed to create invoice"
fi
```

### Bulk Invoice Processing

```bash
#!/bin/bash

API_BASE="https://your-api-domain.com"
API_TOKEN="YOUR_API_TOKEN"

# Get all draft invoices
DRAFTS=$(curl -s -X GET "$API_BASE/invoices/?status_filter=draft" \
  -H "Authorization: Bearer $API_TOKEN")

# Process each draft invoice
echo $DRAFTS | jq -r '.[] | .id' | while read invoice_id; do
  echo "Processing invoice $invoice_id"
  
  # Update status to sent
  curl -X PUT "$API_BASE/invoices/$invoice_id" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status": "sent"}'
  
  # Add history entry
  curl -X POST "$API_BASE/invoices/$invoice_id/history" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "action": "bulk_processing",
      "details": "Invoice processed in bulk operation"
    }'
done
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Standard tier**: 1000 requests per hour
- **Premium tier**: 5000 requests per hour
- **Enterprise tier**: Unlimited

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1635724800
```

## Support and Troubleshooting

### Common Issues

1. **Invoice number conflicts**: Use auto-generated numbers or check uniqueness
2. **Client not found**: Ensure client exists before creating invoice
3. **Currency validation**: Use valid ISO 4217 currency codes
4. **File upload failures**: Check file size and format requirements
5. **Permission errors**: Verify API token has required permissions

### Getting Help

- Check API response error messages for specific guidance
- Verify authentication and permissions
- Ensure request format matches documentation
- Test with smaller datasets first

---

*Last updated: October 28, 2024*
