# Tax Service Integration

This document describes the integration between the Invoice App and Tax Service, allowing users to send expenses and invoices to the tax service for automated tax tracking and reporting.

## Overview

The integration enables seamless data flow from the Invoice App to the Tax Service:
- **Expenses** are sent as expense transactions to the tax service
- **Invoices** are sent as income transactions to the tax service
- All data is mapped and transformed to match the tax service's API format
- Full error handling and retry logic is included

## Architecture

```
Invoice App ──HTTP/API──► Tax Service
     │                           │
     ├── Expenses ─────────────► Expense Transactions
     └── Invoices ─────────────► Income Transactions
```

## Configuration

### Environment Variables

Add the following environment variables to your Invoice App's `.env` file:

```bash
# Enable/disable the integration
TAX_SERVICE_ENABLED=true

# Tax service connection details
TAX_SERVICE_BASE_URL=http://localhost:8000
TAX_SERVICE_API_KEY=your-api-key-here

# Optional: customize timeouts and retries
TAX_SERVICE_TIMEOUT=30
TAX_SERVICE_RETRY_ATTEMPTS=3
```

### Setup Script

Use the provided setup script to configure the integration:

```bash
cd /path/to/invoice_app/api/scripts
chmod +x setup_tax_integration.sh
./setup_tax_integration.sh
```

## API Endpoints

### Status and Configuration

- `GET /api/v1/tax-integration/status` - Get integration status
- `GET /api/v1/tax-integration/settings` - Get current settings (masked)
- `POST /api/v1/tax-integration/test-connection` - Test connection to tax service

### Send Data

- `POST /api/v1/tax-integration/send` - Send single expense or invoice
- `POST /api/v1/tax-integration/send-bulk` - Send multiple items

### Debugging

- `GET /api/v1/tax-integration/expenses/{id}/tax-transaction` - Preview expense mapping
- `GET /api/v1/tax-integration/invoices/{id}/tax-transaction` - Preview invoice mapping

## Usage Examples

### Send Single Expense

```bash
curl -X POST "http://localhost:8000/api/v1/tax-integration/send" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": 123,
    "item_type": "expense"
  }'
```

### Send Single Invoice

```bash
curl -X POST "http://localhost:8000/api/v1/tax-integration/send" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": 456,
    "item_type": "invoice"
  }'
```

### Send Multiple Items

```bash
curl -X POST "http://localhost:8000/api/v1/tax-integration/send-bulk" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "item_ids": [1, 2, 3],
    "item_type": "expense"
  }'
```

### Check Status

```bash
curl -X GET "http://localhost:8000/api/v1/tax-integration/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Data Mapping

### Expense to Transaction Mapping

Invoice App expense fields are mapped to Tax Service transaction fields:

```json
{
  "external_transaction_id": "invoice_app_expense_{id}_{timestamp}",
  "amount": "expense.amount (absolute value)",
  "currency": "expense.currency",
  "date": "expense.expense_date",
  "description": "expense.notes or 'Expense: {vendor}'",
  "source_system": "invoice_app",
  "category": "expense.category",
  "vendor": "expense.vendor",
  "reference_number": "expense.reference_number",
  "payment_method": "expense.payment_method",
  "tax_amount": "expense.tax_amount",
  "tax_rate": "expense.tax_rate",
  "labels": "expense.labels",
  "metadata": {
    "invoice_app_id": "expense.id",
    "integration_type": "expense",
    "total_amount": "expense.total_amount",
    "status": "expense.status"
  }
}
```

### Invoice to Transaction Mapping

Invoice App invoice fields are mapped to Tax Service transaction fields:

```json
{
  "external_transaction_id": "invoice_app_invoice_{id}_{timestamp}",
  "amount": "invoice.amount",
  "currency": "invoice.currency",
  "date": "invoice.created_at",
  "description": "Invoice: {number} - {client_name}",
  "source_system": "invoice_app",
  "category": "income",
  "client_name": "client.name",
  "invoice_number": "invoice.number",
  "due_date": "invoice.due_date",
  "status": "invoice.status",
  "tax_amount": "invoice.tax_amount",
  "discount_amount": "invoice.discount_value",
  "subtotal": "invoice.subtotal",
  "metadata": {
    "invoice_app_id": "invoice.id",
    "integration_type": "invoice",
    "client_id": "invoice.client_id",
    "total_paid": "invoice.total_paid",
    "items_count": "len(invoice.items)"
  }
}
```

## Error Handling

The integration includes comprehensive error handling:

- **Network errors**: Automatic retry with configurable attempts
- **Authentication errors**: Clear error messages for API key issues
- **Validation errors**: Detailed validation feedback
- **Rate limiting**: Built-in delays between bulk operations
- **Timeout handling**: Configurable request timeouts

## Security

- API keys are stored securely in environment variables
- Sensitive data is masked in API responses
- All requests include proper authentication headers
- HTTPS is recommended for production deployments

## Monitoring and Logging

- All integration activities are logged
- Success/failure metrics are tracked
- Detailed error information for troubleshooting
- Connection status monitoring

## Testing

Use the provided test script to verify the integration:

```bash
cd /path/to/invoice_app/api/scripts
chmod +x test_tax_integration.sh
# Edit the script to set your AUTH_TOKEN
./test_tax_integration.sh
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check if tax service is running
   - Verify TAX_SERVICE_BASE_URL is correct
   - Ensure TAX_SERVICE_API_KEY is valid

2. **Authentication Error**
   - Verify API key is correct and active
   - Check tax service API key permissions

3. **Data Mapping Issues**
   - Use preview endpoints to verify data transformation
   - Check logs for detailed mapping information

### Debug Mode

Enable debug logging by setting the log level:

```python
import logging
logging.getLogger('tax_integration_service').setLevel(logging.DEBUG)
```

## Future Enhancements

- Webhook notifications for integration events
- Batch processing for large datasets
- Custom field mapping configuration
- Integration status dashboard
- Automated retry queues
- Data synchronization monitoring

## Support

For issues or questions:
1. Check the logs in your Invoice App
2. Verify tax service is accessible
3. Use the test script to isolate issues
4. Review the API documentation for both services

---

## File Structure

```
invoice_app/api/
├── services/
│   └── tax_integration_service.py    # Core integration service
├── routers/
│   └── tax_integration.py            # API endpoints
├── config.py                         # Configuration management
├── main.py                           # App initialization
└── scripts/
    ├── setup_tax_integration.sh      # Setup script
    └── test_tax_integration.sh       # Test script
```
