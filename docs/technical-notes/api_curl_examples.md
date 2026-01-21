# API Key cURL Examples

This document contains individual curl commands for testing the API key functionality.

## Prerequisites

1. Make sure the API server is running: `docker-compose up -d`
2. Have a valid user account (e.g., `apitest@example.com` / `testpassword123`)
3. Have created an API key through the web UI or API

## Environment Variables

Set these for easier testing:

```bash
export BASE_URL="http://localhost:8000"
export API_KEY="ak_your_api_key_here"
export JWT_TOKEN="your_jwt_token_here"
```

## Authentication Commands

### 1. User Login (Get JWT Token)
```bash
curl -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "apitest@example.com",
    "password": "testpassword123"
  }'
```

### 2. Health Check
```bash
curl -X GET "$BASE_URL/health"
```

## API Key Management Commands

### 3. List API Keys
```bash
curl -X GET "$BASE_URL/api/v1/external-auth/api-keys" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 4. Create API Key

```bash
curl -X POST "$BASE_URL/api/v1/external-auth/api-keys" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "client_name": "Test Integration",
    "client_description": "Testing API integration",
    "allowed_transaction_types": ["income", "expense"],
    "allowed_currencies": ["USD", "EUR"],
    "rate_limit_per_minute": 60,
    "rate_limit_per_hour": 1000,
    "rate_limit_per_day": 10000
  }'
```

### 5. Create External Transaction with AI Recognition Disabled

```bash
curl -X POST "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_type": "expense",
    "amount": 150.00,
    "currency": "USD",
    "date": "2025-09-14T10:00:00Z",
    "description": "Flight to NYC",
    "category": "Travel",
    "vendor_name": "Delta Airlines",
    "disable_ai_recognition": true
  }'
```

### 6. Create Expense with AI Recognition Disabled

```bash
curl -X POST "$BASE_URL/api/v1/expenses/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "amount": 150.00,
    "currency": "USD",
    "expense_date": "2025-09-14",
    "category": "Travel",
    "vendor": "Delta Airlines",
    "disable_ai_recognition": true
  }'
```

### 7. Create API Key
```bash
curl -X POST "$BASE_URL/api/v1/external-auth/api-keys" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "client_name": "My Test Client",
    "client_description": "Testing API integration",
    "allowed_transaction_types": ["income", "expense"],
    "allowed_currencies": ["USD", "EUR"],
    "max_transaction_amount": 5000.00,
    "rate_limit_per_minute": 60,
    "rate_limit_per_hour": 1000,
    "rate_limit_per_day": 10000,
    "is_sandbox": true,
    "webhook_url": "https://webhook.site/your-unique-url"
  }'
```

### 5. Get Specific API Key Details
```bash
curl -X GET "$BASE_URL/api/v1/external-auth/api-keys/CLIENT_ID_HERE" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 6. Regenerate API Key
```bash
curl -X POST "$BASE_URL/api/v1/external-auth/api-keys/CLIENT_ID_HERE/regenerate" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 7. Update API Key
```bash
curl -X PUT "$BASE_URL/api/v1/external-auth/api-keys/CLIENT_ID_HERE" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "client_name": "Updated Client Name",
    "rate_limit_per_minute": 120,
    "is_active": true
  }'
```

### 8. Revoke API Key
```bash
curl -X DELETE "$BASE_URL/api/v1/external-auth/api-keys/CLIENT_ID_HERE" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 9. Get Available Permissions
```bash
curl -X GET "$BASE_URL/api/v1/external-auth/permissions" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## Transaction Commands (Using API Key)

### 10. Submit Transaction
```bash
curl -X POST "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "transaction_type": "expense",
    "amount": 150.75,
    "currency": "USD",
    "date": "2024-01-15T14:30:00Z",
    "description": "Office supplies purchase",
    "source_system": "My Accounting App",
    "category": "Office Supplies",
    "subcategory": "Stationery",
    "business_purpose": "Monthly office supply restocking",
    "vendor_name": "Office Depot",
    "invoice_reference": "INV-2024-001",
    "payment_method": "Credit Card",
    "sales_tax_amount": 12.50,
    "vat_amount": 0.00,
    "other_tax_amount": 0.00,
    "receipt_url": "https://example.com/receipts/001.pdf",
    "external_reference_id": "EXT-REF-001",
    "submission_metadata": {
      "app_version": "1.0.0",
      "user_agent": "MyApp/1.0"
    }
  }'
```

### 11. Submit Income Transaction
```bash
curl -X POST "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "transaction_type": "income",
    "amount": 2500.00,
    "currency": "USD",
    "date": "2024-01-15T10:00:00Z",
    "description": "Consulting services payment",
    "source_system": "CRM System",
    "category": "Consulting",
    "business_purpose": "Q1 consulting project completion",
    "vendor_name": "ABC Corp",
    "invoice_reference": "INV-CONS-001",
    "payment_method": "Bank Transfer"
  }'
```

### 12. List Transactions
```bash
curl -X GET "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "X-API-Key: $API_KEY"
```

### 13. List Transactions with Filters
```bash
curl -X GET "$BASE_URL/api/v1/external-transactions/transactions?transaction_type=expense&limit=10&offset=0" \
  -H "X-API-Key: $API_KEY"
```

### 14. Get Specific Transaction
```bash
curl -X GET "$BASE_URL/api/v1/external-transactions/transactions/TRANSACTION_ID_HERE" \
  -H "X-API-Key: $API_KEY"
```

### 15. Update Transaction
```bash
curl -X PUT "$BASE_URL/api/v1/external-transactions/transactions/TRANSACTION_ID_HERE" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "description": "Updated transaction description",
    "category": "Updated Category",
    "business_purpose": "Updated business purpose"
  }'
```

## OAuth Client Commands

### 16. Create OAuth Client
```bash
curl -X POST "$BASE_URL/api/v1/external-auth/oauth/clients" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "client_name": "My OAuth App",
    "client_description": "OAuth integration for enterprise app",
    "redirect_uris": [
      "https://myapp.com/oauth/callback",
      "https://myapp.com/oauth/callback2"
    ],
    "scopes": ["read", "write", "invoices:read", "expenses:write"],
    "allowed_transaction_types": ["income", "expense"],
    "rate_limit_per_minute": 100,
    "rate_limit_per_hour": 2000,
    "rate_limit_per_day": 20000
  }'
```

## Testing Commands

### 17. Test Invalid API Key
```bash
curl -X GET "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "X-API-Key: ak_invalid_key_for_testing"
```

### 18. Test Missing API Key
```bash
curl -X GET "$BASE_URL/api/v1/external-transactions/transactions"
```

### 19. Test Rate Limiting
```bash
# Send multiple rapid requests
for i in {1..10}; do
  echo "Request $i:"
  curl -s -w "HTTP %{http_code}\n" -X GET "$BASE_URL/api/v1/external-transactions/transactions" \
    -H "X-API-Key: $API_KEY"
  sleep 0.1
done
```

### 20. Test Transaction Validation
```bash
# Test with invalid data
curl -X POST "$BASE_URL/api/v1/external-transactions/transactions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "transaction_type": "invalid_type",
    "amount": -100,
    "currency": "INVALID",
    "date": "invalid_date",
    "description": "",
    "source_system": ""
  }'
```

## Batch Testing

### 21. Submit Multiple Transactions
```bash
# Submit 3 test transactions
for i in {1..3}; do
  echo "Submitting transaction $i..."
  curl -X POST "$BASE_URL/api/v1/external-transactions/transactions" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
      \"transaction_type\": \"expense\",
      \"amount\": $((100 + i * 50)).00,
      \"currency\": \"USD\",
      \"date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
      \"description\": \"Batch test transaction $i\",
      \"source_system\": \"Batch Test Script\",
      \"category\": \"Testing\"
    }"
  echo ""
done
```

## Response Examples

### Successful Transaction Response
```json
{
  "id": 1,
  "external_transaction_id": "txn_abc123def456",
  "user_id": 2,
  "external_client_id": 1,
  "external_reference_id": "EXT-REF-001",
  "transaction_type": "expense",
  "amount": "150.75",
  "currency": "USD",
  "date": "2024-01-15T14:30:00Z",
  "description": "Office supplies purchase",
  "category": "Office Supplies",
  "subcategory": "Stationery",
  "source_system": "My Accounting App",
  "status": "pending",
  "requires_review": true,
  "is_duplicate": false,
  "created_at": "2024-01-15T14:30:01Z",
  "updated_at": "2024-01-15T14:30:01Z"
}
```

### API Key Creation Response
```json
{
  "client_id": "client_abc123def456",
  "api_key": "ak_abcdef123456789...",
  "api_key_prefix": "ak_abcd...",
  "client_name": "My Test Client",
  "allowed_transaction_types": ["income", "expense"],
  "rate_limits": {
    "per_minute": 60,
    "per_hour": 1000,
    "per_day": 10000
  },
  "expires_at": null,
  "created_at": "2024-01-15T14:30:01Z"
}
```

### Error Response Examples
```json
// Invalid API Key
{
  "detail": "Invalid API key"
}

// Rate Limit Exceeded
{
  "detail": "Rate limit exceeded. Try again later."
}

// Validation Error
{
  "detail": [
    {
      "loc": ["body", "amount"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt",
      "ctx": {"limit_value": 0}
    }
  ]
}
```

## Tips

1. **Save your API key securely** - It's only shown once during creation
2. **Use environment variables** - Don't hardcode API keys in scripts
3. **Test in sandbox mode first** - Enable sandbox mode for testing
4. **Monitor rate limits** - Check your usage in the web UI
5. **Use proper error handling** - Always check HTTP status codes
6. **Validate data** - Ensure your transaction data meets the schema requirements

## Troubleshooting

- **401 Unauthorized**: Check your API key is correct and active
- **403 Forbidden**: Check transaction type/amount permissions
- **422 Validation Error**: Check your request data format
- **429 Rate Limited**: Wait and retry, or request higher limits
- **500 Server Error**: Check server logs for issues
