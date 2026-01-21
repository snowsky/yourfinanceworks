# Rate Limiting and Quotas

## Overview

The batch processing system implements comprehensive rate limiting and quota enforcement to prevent API abuse and ensure fair resource allocation across API clients.

## Features

### 1. Per-API-Client Rate Limiting

Rate limits are enforced across three time windows:
- **Per Minute**: Default 60 requests/minute
- **Per Hour**: Default 1,000 requests/hour  
- **Per Day**: Default 10,000 requests/day

When a rate limit is exceeded, the API returns:
- HTTP 429 (Too Many Requests)
- `Retry-After` header indicating seconds to wait
- Error message specifying which limit was exceeded

### 2. Concurrent Job Limits

API clients are limited in the number of batch processing jobs they can have running simultaneously:
- **Default**: 5 concurrent jobs
- Jobs in `pending` or `processing` status count toward the limit
- When limit is exceeded, returns HTTP 429 with active job count

### 3. Custom Quotas

API clients can have custom quotas configured via the `custom_quotas` JSON field:

```json
{
  "rate_limit_per_minute": 100,
  "rate_limit_per_hour": 5000,
  "rate_limit_per_day": 50000,
  "max_concurrent_jobs": 10
}
```

Custom quotas override the default limits when present.

## Implementation

### Rate Limiter Service

The `RateLimiterService` provides thread-safe, in-memory rate limiting:

```python
from services.rate_limiter_service import get_rate_limiter

rate_limiter = get_rate_limiter()

# Check rate limits
allowed, error_message, retry_after = rate_limiter.check_rate_limit(
    api_client_id="client_123",
    rate_limit_per_minute=60,
    rate_limit_per_hour=1000,
    rate_limit_per_day=10000,
    custom_quotas={"rate_limit_per_minute": 100}  # Optional
)

if not allowed:
    # Rate limit exceeded
    print(f"Error: {error_message}")
    print(f"Retry after: {retry_after} seconds")
```

### Concurrent Job Checking

```python
# Check concurrent job limits
allowed, error_message, active_count = rate_limiter.check_concurrent_jobs(
    api_client_id="client_123",
    db=db_session,
    max_concurrent_jobs=5,
    custom_quotas={"max_concurrent_jobs": 10}  # Optional
)

if not allowed:
    print(f"Error: {error_message}")
    print(f"Active jobs: {active_count}")
```

## API Client Configuration

### Default Limits

When creating an API client, default limits are applied:

```python
api_client = APIClient(
    client_name="My Integration",
    rate_limit_per_minute=60,
    rate_limit_per_hour=1000,
    rate_limit_per_day=10000
)
```

### Custom Quotas

For premium or enterprise clients, configure custom quotas:

```python
api_client.custom_quotas = {
    "rate_limit_per_minute": 200,
    "rate_limit_per_hour": 10000,
    "rate_limit_per_day": 100000,
    "max_concurrent_jobs": 20
}
```

## HTTP Response Examples

### Rate Limit Exceeded

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{
  "detail": "Rate limit exceeded: 60/60 requests per minute"
}
```

### Concurrent Job Limit Exceeded

```http
HTTP/1.1 429 Too Many Requests
X-Active-Jobs: 5
Content-Type: application/json

{
  "detail": "Concurrent job limit exceeded: 5/5 active jobs. Please wait for existing jobs to complete."
}
```

## Monitoring and Usage Tracking

### Get Current Usage

```python
usage = rate_limiter.get_current_usage("client_123")
print(f"Minute: {usage['minute']}")
print(f"Hour: {usage['hour']}")
print(f"Day: {usage['day']}")
```

### Reset Limits (Admin Only)

```python
# Reset all rate limits for a client (useful for testing)
rate_limiter.reset_limits("client_123")
```

## Database Schema

### APIClient Model

The `api_clients` table includes rate limiting fields:

```sql
CREATE TABLE api_clients (
    id INTEGER PRIMARY KEY,
    client_id VARCHAR(36) UNIQUE NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    
    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day INTEGER DEFAULT 10000,
    
    -- Custom quotas (JSON)
    custom_quotas JSON,
    
    -- Usage tracking
    total_requests INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    ...
);
```

## Best Practices

### For API Clients

1. **Implement Exponential Backoff**: When receiving 429 responses, wait the specified `Retry-After` duration before retrying
2. **Monitor Usage**: Track your request counts to stay within limits
3. **Batch Requests**: Combine multiple files into single batch jobs when possible
4. **Request Quota Increases**: Contact support if you consistently hit limits

### For Administrators

1. **Set Appropriate Defaults**: Configure reasonable default limits based on system capacity
2. **Monitor Abuse**: Track clients that frequently hit rate limits
3. **Custom Quotas for Premium Clients**: Offer higher limits for enterprise customers
4. **Regular Review**: Periodically review and adjust limits based on usage patterns

## Testing

Run the rate limiting tests:

```bash
python api/test_rate_limiting.py
```

This verifies:
- ✓ Requests within limits are allowed
- ✓ Requests exceeding limits are blocked
- ✓ Custom quotas override defaults
- ✓ Usage tracking is accurate
- ✓ Retry-After headers are calculated correctly

## Future Enhancements

Potential improvements for production deployments:

1. **Redis Backend**: Replace in-memory storage with Redis for distributed rate limiting
2. **Dynamic Limits**: Adjust limits based on system load
3. **Quota Alerts**: Notify clients when approaching limits
4. **Usage Analytics**: Detailed reporting on API usage patterns
5. **Tiered Pricing**: Automatic quota adjustments based on subscription tier

## Related Documentation

- [Batch Processing API](BATCH_PROCESSING_API.md)
- [API Key Authentication](../routers/batch_processing.py)
- [Export Destinations](EXPORT_DESTINATIONS_API.md)
