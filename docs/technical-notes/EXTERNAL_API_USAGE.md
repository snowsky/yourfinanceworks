# External API for PDF Statement Processing

This document explains how to use the external API to process bank statement PDFs and extract transactions using API keys.

## Overview

The external API allows third-party applications to:
1. Upload PDF or CSV bank statement files
2. Extract transactions using AI/LLM processing
3. Receive transaction data in CSV or JSON format
4. Manage API keys for authentication

## Authentication

All API requests require authentication using an API key. You can provide the API key in two ways:

### Option 1: Authorization Header (Recommended)
```bash
Authorization: Bearer your_api_key_here
```

### Option 2: X-API-Key Header
```bash
X-API-Key: your_api_key_here
```

## Getting Started

### 1. Create an API Key

First, log into your account and create an API key:

**POST** `/api/v1/external-auth/api-keys`

```json
{
  "client_name": "My Integration",
  "client_description": "Integration for processing bank statements",
  "allowed_transaction_types": ["income", "expense"],
  "allowed_currencies": ["USD", "EUR"],
  "max_transaction_amount": 10000.00,
  "rate_limit_per_minute": 60,
  "rate_limit_per_hour": 1000,
  "rate_limit_per_day": 10000,
  "is_sandbox": false
}
```

**Response:**
```json
{
  "client_id": "client_abc123",
  "api_key": "ak_your_generated_api_key_here",
  "api_key_prefix": "ak_your...",
  "client_name": "My Integration",
  "allowed_transaction_types": ["income", "expense"],
  "rate_limits": {
    "per_minute": 60,
    "per_hour": 1000,
    "per_day": 10000
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

⚠️ **Important**: Save the `api_key` value securely. It's only shown once during creation.

### 2. Process a Bank Statement

Upload a PDF or CSV bank statement file to extract transactions:

**POST** `/api/v1/statements/process`

```bash
curl -X POST "https://your-domain.com/api/v1/statements/process" \
  -H "Authorization: Bearer ak_your_generated_api_key_here" \
  -F "file=@bank_statement.pdf" \
  -F "format=csv"
```

**Parameters:**
- `file`: PDF or CSV bank statement file (max 20MB)
- `format`: Response format - "csv" (default) or "json"

**Response (CSV format):**
```csv
date,description,amount,transaction_type,category,balance
2024-01-15,GROCERY STORE,-45.67,debit,Food,1234.56
2024-01-16,SALARY DEPOSIT,2500.00,credit,Income,3689.89
```

**Response (JSON format):**
```json
{
  "transactions": [
    {
      "date": "2024-01-15",
      "description": "GROCERY STORE",
      "amount": -45.67,
      "transaction_type": "debit",
      "category": "Food",
      "balance": 1234.56
    },
    {
      "date": "2024-01-16",
      "description": "SALARY DEPOSIT",
      "amount": 2500.00,
      "transaction_type": "credit",
      "category": "Income",
      "balance": 3689.89
    }
  ]
}
```

## API Endpoints

### Health Check
**GET** `/api/v1/statements/health`

Check API client status and service availability.

```bash
curl -H "Authorization: Bearer your_api_key" \
  https://your-domain.com/api/v1/statements/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "api_client": "client_abc123",
  "authentication_method": "api_key",
  "permissions": ["read", "write", "document_processing"],
  "services": {
    "ai_processing": "available"
  },
  "message": "All services operational"
}
```

### Usage Statistics
**GET** `/api/v1/statements/usage`

Get usage statistics for your API client.

```bash
curl -H "Authorization: Bearer your_api_key" \
  https://your-domain.com/api/v1/statements/usage
```

## API Key Management

### List Your API Keys
**GET** `/api/v1/external-auth/api-keys`

### Get API Key Details
**GET** `/api/v1/external-auth/api-keys/{client_id}`

### Update API Key Settings
**PUT** `/api/v1/external-auth/api-keys/{client_id}`

### Regenerate API Key
**POST** `/api/v1/external-auth/api-keys/{client_id}/regenerate`

### Revoke API Key
**DELETE** `/api/v1/external-auth/api-keys/{client_id}`

## Rate Limits

API requests are subject to rate limits configured for your API key:
- Per minute: Default 60 requests
- Per hour: Default 1,000 requests  
- Per day: Default 10,000 requests

When rate limits are exceeded, you'll receive a `429 Too Many Requests` response.

## Error Handling

### Common Error Responses

**401 Unauthorized**
```json
{
  "detail": "API key required. Provide via Authorization header (Bearer <key>) or X-API-Key header."
}
```

**403 Forbidden**
```json
{
  "detail": "Document processing permission required"
}
```

**422 Unprocessable Entity**
```json
{
  "detail": "No transactions found in the provided file. This could mean: 1) The file doesn't contain transaction data, 2) The file format is not supported, or 3) The AI service needs to be configured in Settings > AI Configuration."
}
```

**429 Too Many Requests**
```json
{
  "detail": "Rate limit exceeded"
}
```

**503 Service Unavailable**
```json
{
  "detail": "AI processing service is not available. Please ensure the AI provider is configured in Settings > AI Configuration and the service is running."
}
```

## Supported File Types

- **PDF**: Bank statement PDFs with text content
- **CSV**: Bank statement exports in CSV format
- **Maximum file size**: 20MB

## Transaction Data Format

Each transaction includes:
- `date`: Transaction date (YYYY-MM-DD format)
- `description`: Transaction description/merchant name
- `amount`: Transaction amount (negative for debits, positive for credits)
- `transaction_type`: "debit" or "credit"
- `category`: Automatically categorized transaction type
- `balance`: Account balance after transaction (if available)

## Security Best Practices

1. **Store API keys securely**: Never commit API keys to version control
2. **Use HTTPS**: Always use HTTPS for API requests
3. **Rotate keys regularly**: Regenerate API keys periodically
4. **Monitor usage**: Check usage statistics regularly
5. **IP restrictions**: Configure allowed IP addresses if possible
6. **Sandbox testing**: Use sandbox mode for development and testing

## Example Integration (Python)

```python
import requests

class BankStatementProcessor:
    def __init__(self, api_key, base_url="https://your-domain.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}"
        }
    
    def process_statement(self, file_path, format="csv"):
        """Process a bank statement file and return transactions."""
        url = f"{self.base_url}/api/v1/statements/process"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'format': format}
            
            response = requests.post(
                url, 
                headers=self.headers,
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            if format == "json":
                return response.json()
            else:
                return response.text  # CSV content
        else:
            response.raise_for_status()
    
    def get_usage_stats(self):
        """Get API usage statistics."""
        url = f"{self.base_url}/api/v1/statements/usage"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

# Usage
processor = BankStatementProcessor("ak_your_api_key_here")
transactions = processor.process_statement("statement.pdf", format="json")
print(f"Found {len(transactions['transactions'])} transactions")
```

## Troubleshooting

### No Transactions Found (422 Error)

If you receive a 422 error with "No transactions found", try these steps:

1. **Check AI Configuration**:
   - Log into the web interface
   - Go to Settings > AI Configuration
   - Ensure an AI provider (OpenAI, Ollama, etc.) is configured
   - Test the configuration to verify it's working

2. **Verify File Format**:
   - Ensure the file is a valid PDF or CSV bank statement
   - Check that the file contains actual transaction data
   - Try with a different file to isolate the issue

3. **Check Service Status**:
   ```bash
   curl -H "Authorization: Bearer your_api_key" \
     https://your-domain.com/api/v1/statements/health
   ```

### AI Service Unavailable (503 Error)

If you receive a 503 error about AI service unavailability:

1. **Configure AI Provider**:
   - Go to Settings > AI Configuration in the web interface
   - Set up OpenAI API key or Ollama endpoint
   - Test the configuration

2. **Check Service Status**:
   - For Ollama: Ensure Ollama is running (`ollama serve`)
   - For OpenAI: Verify API key is valid and has credits
   - Check network connectivity to the AI service

3. **Health Check**:
   Use the health endpoint to check service status:
   ```bash
   curl -H "Authorization: Bearer your_api_key" \
     https://your-domain.com/api/v1/statements/health
   ```

## Support

For API support and questions:
1. Check the troubleshooting section above
2. Use the health check endpoint to diagnose issues
3. Review error messages and status codes
4. Monitor your usage statistics
5. Contact support if issues persist

## Changelog

- **v1.0**: Initial release with PDF/CSV processing and API key authentication