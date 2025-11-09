# API Examples

This directory contains examples for using various APIs including batch file processing, bank statement processing, and more.

## Files

### Batch File Processing
- `batch_processing_client.py` - Complete Python client with all features (upload, monitoring, export destinations)
- `batch_processing_quickstart.py` - Simple quick-start example for batch processing

### Bank Statement Processing
- `external_api_example.py` - Complete Python example with API key creation and statement processing
- `curl_examples.sh` - Shell script with curl commands for testing the API

### Other Examples
- `unified_ocr_integration_example.py` - OCR integration examples
- `storage_monitoring_example.py` - Cloud storage monitoring examples
- `README.md` - This file

## Batch File Processing Examples

### Quick Start

The simplest way to get started with batch file processing:

```bash
# 1. Edit the configuration in batch_processing_quickstart.py
# 2. Run the example
python batch_processing_quickstart.py
```

### Full Client Example

For more advanced usage including export destination management:

```python
from batch_processing_client import BatchProcessingClient

# Initialize client
client = BatchProcessingClient(
    base_url="https://your-domain.com",
    auth_token="your_jwt_token"
)

# Upload batch
job = client.upload_batch(
    files=['invoice1.pdf', 'invoice2.pdf'],
    export_destination_id=1
)

# Wait for completion
final_status = client.wait_for_completion(
    job_id=job['job_id'],
    callback=lambda s: print(f"Progress: {s['progress']['progress_percentage']}%")
)

# Download results
if final_status['export']['export_file_url']:
    client.download_export_file(
        export_url=final_status['export']['export_file_url'],
        output_path='results.csv'
    )
```

### Export Destination Setup

```python
# Create S3 destination
destination = client.create_export_destination(
    name="Production S3",
    destination_type="s3",
    credentials={
        "access_key_id": "AKIA...",
        "secret_access_key": "...",
        "region": "us-east-1",
        "bucket_name": "my-exports"
    },
    is_default=True
)

# Test connection
test_result = client.test_export_destination(destination['id'])
print(f"Connection test: {'✓' if test_result['success'] else '✗'}")
```

### Using cURL

```bash
# Upload batch
curl -X POST "https://your-domain.com/api/v1/batch-processing/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "export_destination_id=1"

# Check status
curl -X GET "https://your-domain.com/api/v1/batch-processing/jobs/JOB_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all jobs
curl -X GET "https://your-domain.com/api/v1/batch-processing/jobs" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Bank Statement Processing Examples

### 1. Create an API Key

First, log into your account and create an API key via the web interface or API:

```bash
# Login and create API key
curl -X POST "https://your-domain.com/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"

# Use the access token to create API key
curl -X POST "https://your-domain.com/api/v1/external-auth/api-keys" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Integration",
    "client_description": "PDF processing integration",
    "allowed_transaction_types": ["income", "expense"],
    "rate_limit_per_minute": 60,
    "rate_limit_per_hour": 1000,
    "rate_limit_per_day": 10000
  }'
```

### 2. Process a Bank Statement

```bash
# Process PDF and get CSV
curl -X POST "https://your-domain.com/api/v1/statements/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@bank_statement.pdf" \
  -F "format=csv" \
  -o transactions.csv

# Process PDF and get JSON
curl -X POST "https://your-domain.com/api/v1/statements/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@bank_statement.pdf" \
  -F "format=json"
```

### 3. Monitor Usage

```bash
# Check API health
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-domain.com/api/v1/statements/health

# Get usage statistics
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-domain.com/api/v1/statements/usage
```

## Python Example

```python
from external_api_example import BankStatementAPI

# Initialize with your API key
client = BankStatementAPI("https://your-domain.com", "your_api_key")

# Process a statement
transactions = client.process_statement("bank_statement.pdf", format="json")
print(f"Found {len(transactions['transactions'])} transactions")

# Check usage
usage = client.get_usage_stats()
print(f"Total requests: {usage['total_requests']}")
```

## Authentication

The API supports two authentication methods:

1. **Authorization Header (Recommended)**:

   ```
   Authorization: Bearer your_api_key
   ```

2. **X-API-Key Header**:

   ```
   X-API-Key: your_api_key
   ```

## Supported File Types

- **PDF**: Bank statement PDFs (max 20MB)
- **CSV**: Bank statement exports (max 20MB)

## Response Formats

### CSV Format

```csv
date,description,amount,transaction_type,category,balance
2024-01-15,GROCERY STORE,-45.67,debit,Food,1234.56
2024-01-16,SALARY DEPOSIT,2500.00,credit,Income,3689.89
```

### JSON Format

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
    }
  ]
}
```

## Error Handling

Common HTTP status codes:

- `200` - Success
- `401` - Invalid or missing API key
- `403` - Insufficient permissions
- `422` - No transactions found in file
- `429` - Rate limit exceeded
- `503` - Service temporarily unavailable

## Rate Limits

Default limits (configurable per API key):

- 60 requests per minute
- 1,000 requests per hour
- 10,000 requests per day

## Security

- Always use HTTPS
- Store API keys securely
- Monitor usage regularly
- Rotate keys periodically
- Use IP restrictions when possible
