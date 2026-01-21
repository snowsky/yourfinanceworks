# API Key Management Feature Documentation

## Overview

The API Key Management feature provides a comprehensive system for external applications to securely integrate with the Invoice App. This feature enables users to create, manage, and use API keys for programmatic access to submit financial transactions and retrieve data.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Backend Implementation](#backend-implementation)
3. [Frontend Implementation](#frontend-implementation)
4. [Security Features](#security-features)
5. [API Endpoints](#api-endpoints)
6. [Usage Examples](#usage-examples)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)

## Architecture Overview

The API key system follows a multi-layered architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend UI   │    │   FastAPI API    │    │   Database      │
│   (React)       │◄──►│   (Python)       │◄──►│   (PostgreSQL)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────▼──────┐
                       │ Middleware  │
                       │ (Auth/Rate) │
                       └─────────────┘
```

### Key Components:

- **Frontend**: React-based UI integrated into Settings page
- **Backend**: FastAPI routes with authentication middleware
- **Database**: PostgreSQL with dedicated API client tables
- **Security**: SHA-256 hashing, rate limiting, IP restrictions
- **Multi-tenancy**: Full tenant isolation support

## Backend Implementation

### Database Models

#### APIClient Model (`api/models/api_models.py`)
```python
class APIClient(Base):
    __tablename__ = "api_clients"
    
    # Core identification
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(36), unique=True, nullable=False)
    client_name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("master_users.id"))
    
    # Authentication
    api_key_hash = Column(String(255), nullable=False, unique=True)
    api_key_prefix = Column(String(10), nullable=False)
    
    # Permissions & Limits
    allowed_transaction_types = Column(JSON, nullable=False)
    allowed_currencies = Column(JSON, nullable=True)
    max_transaction_amount = Column(Numeric(precision=15, scale=2))
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    
    # Security
    allowed_ip_addresses = Column(JSON, nullable=True)
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    
    # Status & Audit
    is_active = Column(Boolean, default=True)
    is_sandbox = Column(Boolean, default=False)
    total_requests = Column(Integer, default=0)
    total_transactions_submitted = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
```

#### ExternalTransaction Model
```python
class ExternalTransaction(Base):
    __tablename__ = "external_transactions"
    
    # Core transaction data
    external_transaction_id = Column(String(36), unique=True)
    user_id = Column(Integer, ForeignKey("master_users.id"))
    external_client_id = Column(Integer, ForeignKey("api_clients.id"))
    transaction_type = Column(String(20), nullable=False)
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String(3), default="USD")
    date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=False)
    
    # Extended fields
    category = Column(String(100), nullable=True)
    source_system = Column(String(100), nullable=False)
    invoice_reference = Column(String(255), nullable=True)
    payment_method = Column(String(50), nullable=True)
    
    # Tax information
    sales_tax_amount = Column(Numeric(precision=15, scale=2), default=0)
    vat_amount = Column(Numeric(precision=15, scale=2), default=0)
    other_tax_amount = Column(Numeric(precision=15, scale=2), default=0)
    
    # Status & Review
    status = Column(String(20), default="pending")
    requires_review = Column(Boolean, default=True)
    reviewed_by = Column(Integer, ForeignKey("master_users.id"))
    reviewed_at = Column(DateTime, nullable=True)
    
    # Duplicate detection
    duplicate_check_hash = Column(String(64), index=True)
    is_duplicate = Column(Boolean, default=False)
```

### Authentication Service (`api/services/external_api_auth_service.py`)

The `ExternalAPIAuthService` handles:

- **API Key Generation**: Cryptographically secure 256-bit keys
- **Hashing**: SHA-256 with salt for secure storage
- **Authentication**: Validates API keys and creates auth contexts
- **Rate Limiting**: Enforces per-minute/hour/day limits
- **Permission Checks**: Validates transaction types, amounts, currencies
- **IP Restrictions**: Optional IP address whitelisting
- **OAuth Support**: Enterprise OAuth 2.0 client management

Key methods:
```python
async def authenticate_api_key(self, db: Session, api_key: str, client_ip: str) -> Optional[AuthContext]
async def check_api_client_permissions(self, db: Session, api_client: APIClient, transaction_type: str, amount: float, currency: str) -> Tuple[bool, str]
async def check_rate_limits(self, db: Session, api_client: APIClient) -> Tuple[bool, str]
```

### API Routes (`api/routers/external_api_auth.py`)

#### Management Endpoints:
- `POST /api/v1/external-auth/api-keys` - Create API key
- `GET /api/v1/external-auth/api-keys` - List API keys
- `GET /api/v1/external-auth/api-keys/{client_id}` - Get specific API key
- `PUT /api/v1/external-auth/api-keys/{client_id}` - Update API key
- `DELETE /api/v1/external-auth/api-keys/{client_id}` - Revoke API key
- `POST /api/v1/external-auth/api-keys/{client_id}/regenerate` - Regenerate key

#### OAuth Endpoints:
- `POST /api/v1/external-auth/oauth/clients` - Create OAuth client
- `GET /api/v1/external-auth/permissions` - List available permissions

### Transaction Endpoints (`api/routers/external_transactions.py`)

- `POST /api/v1/external-transactions/transactions` - Submit transaction
- `GET /api/v1/external-transactions/transactions` - List transactions
- `GET /api/v1/external-transactions/transactions/{transaction_id}` - Get transaction
- `PUT /api/v1/external-transactions/transactions/{transaction_id}` - Update transaction

### Middleware (`api/middleware/external_api_auth_middleware.py`)

The `ExternalAPIAuthMiddleware` provides:

- **Automatic Authentication**: Intercepts requests to external API endpoints
- **API Key Validation**: Validates `X-API-Key` header
- **Rate Limiting**: Enforces client-specific rate limits
- **Request Context**: Populates auth context for downstream handlers
- **Error Handling**: Returns appropriate HTTP status codes

## Frontend Implementation

### Settings Integration (`ui/src/pages/Settings.tsx`)

The API key management is integrated as a tab within the Settings page:

```tsx
<TabsTrigger value="api-keys" className="text-xs md:text-sm">API Keys</TabsTrigger>

<TabsContent value="api-keys" className="mt-6">
  <APIClientManagement />
</TabsContent>
```

### API Client Management Component (`ui/src/components/APIClientManagement/APIClientManagement.tsx`)

Features:
- **Create API Keys**: Form with comprehensive configuration options
- **List Management**: Display all API keys with status and usage stats
- **Key Operations**: Revoke, regenerate, copy to clipboard
- **OAuth Clients**: Create and manage OAuth 2.0 clients
- **Real-time Stats**: Request counts, last used timestamps
- **Security Display**: Show key prefixes (never full keys after creation)

Key UI Elements:
```tsx
// API Key Creation Form
<form onSubmit={createApiKey}>
  <Input name="client_name" placeholder="My Accounting System" />
  <Textarea name="client_description" />
  <Switch name="is_sandbox" label="Sandbox Mode" />
  
  // Transaction Types
  {TRANSACTION_TYPES.map(type => (
    <Switch key={type.value} onCheckedChange={handleTransactionTypeToggle} />
  ))}
  
  // Rate Limits
  <Input name="rate_limit_per_minute" type="number" />
  <Input name="rate_limit_per_hour" type="number" />
  <Input name="rate_limit_per_day" type="number" />
  
  // IP Restrictions (optional)
  <Input name="allowed_ip_addresses" placeholder="192.168.1.0/24" />
  
  // Webhook Configuration
  <Input name="webhook_url" placeholder="https://api.example.com/webhooks" />
</form>
```

## Security Features

### 1. Secure Key Generation
- **Algorithm**: Cryptographically secure random generation
- **Length**: 256-bit keys (44 characters base64)
- **Format**: `ak_` prefix + random string
- **Uniqueness**: Database-level unique constraints

### 2. Secure Storage
- **Hashing**: SHA-256 with salt
- **No Plain Text**: Keys never stored in plain text
- **Prefix Display**: Only first 8 characters shown in UI

### 3. Authentication & Authorization
- **Header-based**: `X-API-Key` header required
- **Context Isolation**: Each key tied to specific user/tenant
- **Permission Matrix**: Granular transaction type permissions
- **Amount Limits**: Optional maximum transaction amounts

### 4. Rate Limiting
- **Multi-tier**: Per minute, hour, and day limits
- **Client-specific**: Individual limits per API key
- **Configurable**: Adjustable through UI
- **Enforcement**: Middleware-level blocking

### 5. IP Restrictions
- **Optional Whitelisting**: Restrict keys to specific IP addresses
- **CIDR Support**: Support for IP ranges
- **Bypass Option**: Can be disabled for flexibility

### 6. Audit & Monitoring
- **Usage Tracking**: Request counts and timestamps
- **Transaction Logging**: All API submissions logged
- **Status Monitoring**: Active/inactive key management
- **Review Workflow**: Transactions require review by default

## New Features

### AI Recognition Control

The API now supports an optional `disable_ai_recognition` parameter that allows API clients to skip AI document processing when creating expenses or external transactions. This is useful when the API call already contains complete information and AI processing is unnecessary.

#### Usage Examples:

**Creating an expense with AI recognition disabled:**
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

**Creating an external transaction with AI recognition disabled:**
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

#### Behavior:

- When `disable_ai_recognition` is set to `true`:
  - For expenses: The analysis status is set to "skipped" and no OCR/AI processing is triggered
  - For external transactions: The field is stored for reference but doesn't affect processing
  - Receipt uploads will still be processed normally unless this flag is set on the expense
- When `disable_ai_recognition` is `false` or omitted (default): Normal AI processing occurs
- This helps optimize performance and costs when complete data is already available

## API Endpoints

### Authentication Header
All external API requests must include:
```http
X-API-Key: ak_your_api_key_here
```

### Submit Transaction
```http
POST /api/v1/external-transactions/transactions
Content-Type: application/json
X-API-Key: ak_your_api_key_here

{
  "transaction_type": "expense",
  "amount": 100.50,
  "currency": "USD",
  "date": "2024-01-15T10:30:00Z",
  "description": "Office supplies purchase",
  "source_system": "Accounting Software",
  "category": "Office Supplies",
  "business_purpose": "Monthly office supply restocking",
  "vendor_name": "Office Depot",
  "invoice_reference": "INV-2024-001",
  "payment_method": "Credit Card",
  "sales_tax_amount": 8.50,
  "receipt_url": "https://example.com/receipts/001.pdf"
}
```

### Response Format
```json
{
  "id": 1,
  "external_transaction_id": "txn_abc123",
  "transaction_type": "expense",
  "amount": "100.50",
  "currency": "USD",
  "date": "2024-01-15T10:30:00Z",
  "description": "Office supplies purchase",
  "status": "pending",
  "requires_review": true,
  "created_at": "2024-01-15T10:30:01Z",
  "updated_at": "2024-01-15T10:30:01Z"
}
```

### List Transactions
```http
GET /api/v1/external-transactions/transactions
X-API-Key: ak_your_api_key_here
```

## Usage Examples

### 1. Create API Key (Web UI)
1. Navigate to **Settings → API Keys**
2. Click **"Create API Key"**
3. Fill in client details:
   - Name: "My Accounting System"
   - Description: "Integration with QuickBooks"
   - Transaction Types: Select "Income" and "Expense"
   - Rate Limits: 60/min, 1000/hour, 10000/day
   - Sandbox Mode: Enable for testing
4. Click **"Create API Key"**
5. Copy the generated key (shown only once)

### 2. Submit Transaction (cURL)
```bash
curl -X POST "https://your-domain.com/api/v1/external-transactions/transactions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_your_api_key_here" \
  -d '{
    "transaction_type": "expense",
    "amount": 150.75,
    "currency": "USD",
    "date": "2024-01-15T14:30:00Z",
    "description": "Software subscription",
    "source_system": "Expense Tracker",
    "category": "Software",
    "vendor_name": "Adobe",
    "payment_method": "Credit Card"
  }'
```

### 3. Python Integration Example
```python
import requests
import json
from datetime import datetime

class InvoiceAppAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        }
    
    def submit_transaction(self, transaction_data):
        url = f"{self.base_url}/api/v1/external-transactions/transactions"
        response = requests.post(url, headers=self.headers, json=transaction_data)
        return response.json()
    
    def list_transactions(self):
        url = f"{self.base_url}/api/v1/external-transactions/transactions"
        response = requests.get(url, headers=self.headers)
        return response.json()

# Usage
api = InvoiceAppAPI("https://your-domain.com", "ak_your_api_key_here")

transaction = {
    "transaction_type": "expense",
    "amount": 99.99,
    "currency": "USD",
    "date": datetime.now().isoformat(),
    "description": "Monthly software license",
    "source_system": "Python Integration",
    "category": "Software",
    "vendor_name": "Software Vendor"
}

result = api.submit_transaction(transaction)
print(f"Transaction created: {result['external_transaction_id']}")
```

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/invoice_app

# Security
SECRET_KEY=your-secret-key-here

# Rate Limiting (optional)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE=redis://localhost:6379

# Webhook Configuration (optional)
WEBHOOK_TIMEOUT=30
WEBHOOK_RETRY_ATTEMPTS=3
```

### Default Limits
- **API Keys per User**: 2 maximum
- **Rate Limits**: 60/min, 1000/hour, 10000/day (configurable)
- **Key Length**: 44 characters (256-bit)
- **Transaction Amount**: No default limit (configurable per key)

## Troubleshooting

### Common Issues

#### 1. "Invalid API key" Error
**Cause**: API key not found, revoked, or malformed
**Solution**: 
- Verify key is correctly copied (44 characters starting with `ak_`)
- Check if key is active in Settings → API Keys
- Regenerate key if necessary

#### 2. "Rate limit exceeded" Error
**Cause**: Too many requests within time window
**Solution**:
- Check current rate limits in API key settings
- Implement exponential backoff in client code
- Contact admin to increase limits if needed

#### 3. "Permission denied" Error
**Cause**: Transaction type or amount not allowed
**Solution**:
- Verify transaction type is in allowed list
- Check if amount exceeds maximum limit
- Update API key permissions if needed

#### 4. "IP address not allowed" Error
**Cause**: Request from non-whitelisted IP
**Solution**:
- Add client IP to allowed addresses list
- Remove IP restrictions if not needed
- Use VPN or proxy if IP is dynamic

### Debug Steps

1. **Check API Key Status**:
   ```bash
   curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
        https://your-domain.com/api/v1/external-auth/api-keys
   ```

2. **Test Authentication**:
   ```bash
   curl -H "X-API-Key: ak_your_key" \
        https://your-domain.com/api/v1/external-transactions/transactions
   ```

3. **Monitor Logs**:
   ```bash
   docker-compose logs api | grep "external_api_auth"
   ```

### Performance Optimization

1. **Database Indexing**: Ensure indexes on frequently queried fields
2. **Caching**: Implement Redis caching for rate limit counters
3. **Connection Pooling**: Use database connection pooling
4. **Async Processing**: Consider async webhook delivery

## Migration & Deployment

### Database Migration
```bash
# Create API key tables
docker-compose exec api python scripts/create_api_key_tables.py

# Verify tables created
docker-compose exec postgres psql -U postgres -d invoice_app -c "\dt api_*"
```

### Production Deployment Checklist

- [ ] Set strong `SECRET_KEY` environment variable
- [ ] Configure production database with SSL
- [ ] Enable rate limiting with Redis backend
- [ ] Set up monitoring and alerting
- [ ] Configure webhook endpoints with proper SSL
- [ ] Test API key functionality end-to-end
- [ ] Document API keys for client integration
- [ ] Set up backup procedures for API client data

## Support & Maintenance

### Monitoring Metrics
- API key usage statistics
- Rate limit violations
- Failed authentication attempts
- Transaction submission rates
- Webhook delivery success rates

### Regular Maintenance
- Review and rotate API keys periodically
- Monitor for suspicious activity
- Update rate limits based on usage patterns
- Clean up inactive or expired keys
- Backup API client configurations

### Security Auditing
- Regular security reviews of API key permissions
- Monitor for unusual transaction patterns
- Review IP address restrictions
- Audit webhook endpoints for security
- Check for compliance with data protection regulations

---

## Conclusion

The API Key Management feature provides a robust, secure, and scalable solution for external system integration with the Invoice App. It supports both simple API key authentication and enterprise-grade OAuth 2.0 flows, with comprehensive security controls and monitoring capabilities.

For additional support or feature requests, please contact the development team or create an issue in the project repository.

**Last Updated**: December 2024  
**Version**: 1.0  
**Author**: Invoice App Development Team
